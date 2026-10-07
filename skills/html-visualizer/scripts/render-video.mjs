#!/usr/bin/env node
/**
 * 影片模式 — 把有場景的 HTML（一頁版、逐步頁或簡報）錄成帶旁白的 mp4 解說影片。
 * 簡報（<html data-layout="slides">）：一張 slide ＝ 一幕，旁白取 data-narration，沒有就念講者備註。
 *
 * 流程：
 *   1. 讀頁面的場景與旁白（window.__getScenes()：#video-scenes JSON 優先，否則 data-narration）
 *   2. 每幕旁白產生配音：預設 macOS `say`（免費、本機）；設了 ELEVENLABS_API_KEY 就用 ElevenLabs
 *   3. 用 ffprobe 量每段配音長度 → 決定每幕秒數
 *   4. Playwright 無頭 Chromium（1920×1080）逐幕 __goToScene(n)，
 *      **暫停所有 CSS 動畫、逐格設定時間再截圖**（決定性：同一份 HTML 每次錄出一樣的畫面，
 *      不受機器快慢影響；動畫結束後只截一張靜止畫面撐滿該幕剩下的時間）
 *   5. ffmpeg 合成 H.264 + AAC 的 mp4，另產 .srt 字幕（--burn-subs 燒進畫面）
 *
 * 用法：
 *   node render-video.mjs <page.html> [--out out.mp4] [--fps 30] [--tts auto|say|elevenlabs]
 *        [--voice Meijia] [--rate 0] [--gap 0.6] [--tail 1.2] [--scenes 1-3] [--burn-subs] [--keep-work] [--dry-run]
 *   --scenes：只錄其中幾幕（例：2-4、1,3,5）——簡報張數多時先錄一段試看
 *
 * 規則與疑難排解：references/video-explainer.md
 */
import { pathToFileURL } from "node:url";
import path from "node:path";
import os from "node:os";
import fs from "node:fs";
import { execFileSync, spawnSync } from "node:child_process";
import { createRequire } from "node:module";

// ── 參數 ──────────────────────────────────────────
const argv = process.argv.slice(2);
const file = argv.find((a) => !a.startsWith("--") && !isValueOf(a));
function isValueOf(a) {
  const i = argv.indexOf(a);
  return i > 0 && ["--out", "--fps", "--tts", "--voice", "--rate", "--gap", "--tail", "--width", "--height", "--scenes"].includes(argv[i - 1]);
}
const opt = (k, d) => {
  const i = argv.indexOf(k);
  return i >= 0 && argv[i + 1] !== undefined ? argv[i + 1] : d;
};
const flag = (k) => argv.includes(k);
if (!file || flag("--help")) {
  console.log(fs.readFileSync(new URL(import.meta.url), "utf8").split("*/")[0].replace(/^#!.*\n\/\*\*?/, ""));
  process.exit(file ? 0 : 64);
}
const SRC = path.resolve(file);
if (!fs.existsSync(SRC)) die(`找不到檔案：${SRC}`);
const OUT = path.resolve(opt("--out", SRC.replace(/\.html?$/i, "") + ".mp4"));
const FPS = parseInt(opt("--fps", "30"), 10);
const W = parseInt(opt("--width", "1920"), 10);
const H = parseInt(opt("--height", "1080"), 10);
const GAP = parseFloat(opt("--gap", "0.6")); // 每幕旁白念完後多停幾秒
const TAIL = parseFloat(opt("--tail", "1.2")); // 最後一幕再多停幾秒
const TTS = opt("--tts", "auto");
const RATE = parseInt(opt("--rate", "0"), 10); // say 的每分鐘字數；0 = 用語音預設
const WORK = fs.mkdtempSync(path.join(os.tmpdir(), "hv-video-"));

function die(msg, code = 1) {
  console.error("✗ " + msg);
  process.exit(code);
}
function log(msg) {
  console.log("  " + msg);
}

// ── 外部工具 ──────────────────────────────────────
function findBin(name) {
  const env = process.env[name.toUpperCase()];
  if (env && fs.existsSync(env)) return env;
  const r = spawnSync("/usr/bin/which", [name], { encoding: "utf8" });
  if (r.status === 0 && r.stdout.trim()) return r.stdout.trim();
  for (const p of [`/opt/homebrew/opt/ffmpeg-full/bin/${name}`, `/opt/homebrew/bin/${name}`, `/usr/local/bin/${name}`]) {
    if (fs.existsSync(p)) return p;
  }
  return null;
}
const FFMPEG = findBin("ffmpeg");
const FFPROBE = findBin("ffprobe");
if (!FFMPEG || !FFPROBE)
  die("找不到 ffmpeg／ffprobe。安裝：brew install ffmpeg（或設環境變數 FFMPEG、FFPROBE 指到執行檔）");

function ff(args, cwd = WORK) {
  const r = spawnSync(FFMPEG, ["-hide_banner", "-loglevel", "error", "-y", ...args], { cwd, encoding: "utf8" });
  if (r.status !== 0) die(`ffmpeg 失敗：${(r.stderr || "").trim().slice(0, 600)}`);
}
function duration(f) {
  const out = execFileSync(FFPROBE, ["-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", f], {
    encoding: "utf8",
  });
  return parseFloat(out.trim());
}

function loadPlaywright() {
  const roots = [process.env.HTML_VISUALIZER_PLAYWRIGHT_ROOT, process.cwd()].filter(Boolean);
  for (const r of roots) {
    try {
      const req = createRequire(path.join(r, "noop.js"));
      return req(req.resolve("playwright", { paths: [r] }));
    } catch {
      /* 換下一個 */
    }
  }
  try {
    return createRequire(import.meta.url)("playwright");
  } catch {
    return null;
  }
}
const pw = loadPlaywright();
if (!pw)
  die(
    [
      "找不到 playwright 套件。任選一種：",
      "  ① 在某個資料夾裝：mkdir -p ~/.cache/hv-pw && npm --prefix ~/.cache/hv-pw i playwright",
      "     然後 export HTML_VISUALIZER_PLAYWRIGHT_ROOT=~/.cache/hv-pw/node_modules",
      "  ② 在已經裝了 playwright 的專案根目錄執行本指令",
      "瀏覽器：有裝 Google Chrome 就會直接用；沒有就再跑 npx playwright install chromium",
    ].join("\n"),
    2,
  );

// ── 1. 開頁面、讀場景 ─────────────────────────────
let browser;
try {
  browser = await pw.chromium.launch();
} catch {
  try {
    browser = await pw.chromium.launch({ channel: "chrome" });
  } catch {
    die("playwright 自帶 chromium 與系統 Chrome 都起不來。跑 npx playwright install chromium，或安裝 Google Chrome", 2);
  }
}
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
const pageErrors = [];
page.on("pageerror", (e) => pageErrors.push(String(e).split("\n")[0]));
const url = pathToFileURL(SRC).href + "?video=1&scene=0";
await page.goto(url, { waitUntil: "load", timeout: 30000 });
await page.evaluate(() => document.fonts && document.fonts.ready);
await page.waitForTimeout(1200); // Tailwind CDN 與字型套上
// 簡報的圖表從 CDN 載入（@unovis），畫好前別開錄；沒有圖表的頁旗標一開始就是 true
await page.waitForFunction(() => window.__chartsReady !== false, null, { timeout: 15000 }).catch(() => {});
// 不管頁面有沒有內建 video-mode 樣式，都把介面元件藏掉（蓋章注入的風格設定按鈕也在內）
await page.addStyleTag({
  content:
    ".vt-comment-trigger,.vt-comment-pill,.vt-comment-popup,.vt-comment-list,.vt-session-badge,.vt-tw-root,#vt-manual-copy-box{display:none!important}",
});
if (pageErrors.length) die(`頁面載入就出錯：${pageErrors[0]}`);

const hasEngine = await page.evaluate(() => typeof window.__goToScene === "function");
if (!hasEngine)
  die("頁面沒有 window.__goToScene(n)。一頁版複製 assets/onepage-template.html 的「場景引擎」；簡報從 assets/slides-template.html 起手");
const isDeck = await page.evaluate(() => document.documentElement.getAttribute("data-layout") === "slides");
let scenes = await page.evaluate(() => (window.__getScenes ? window.__getScenes() : []));
// --scenes 2-4 / 1,3,5：只錄其中幾幕（幕號照頁面原本的編號，__goToScene 跳得到）
const pick = opt("--scenes", null);
if (pick) {
  const want = new Set();
  for (const part of pick.split(",")) {
    const m = part.trim().match(/^(\d+)(?:-(\d+))?$/);
    if (!m) die(`--scenes 看不懂：「${part}」（寫成 2-4 或 1,3,5）`);
    for (let k = +m[1]; k <= +(m[2] || m[1]); k++) want.add(k);
  }
  scenes = scenes.filter((s, i) => want.has(Number(s.scene) || i + 1));
  if (!scenes.length) die(`--scenes ${pick} 一幕都沒選到`);
}
if (!scenes.length) die("頁面沒有場景：加 <script type=\"application/json\" id=\"video-scenes\">，或在元素上寫 data-scene／data-narration");
const empty = scenes.filter((s) => !(s.narration || "").trim());
if (empty.length) die(`第 ${empty.map((s) => s.scene).join("、")} 幕沒有旁白`);
if (scenes.length > 8 && !isDeck) log(`! ${scenes.length} 幕超過建議上限 8 幕（一幕一個想法，考慮拆兩支片）`);
const lang = await page.evaluate(() => document.documentElement.lang || "zh-TW");
log(`▸ ${path.basename(SRC)}：${scenes.length} ${isDeck ? "張簡報（一張一幕）" : "幕"}，語言 ${lang}`);

// ── 2. 配音 ───────────────────────────────────────
function sayVoices() {
  const r = spawnSync("say", ["-v", "?"], { encoding: "utf8" });
  if (r.status !== 0) return null;
  return r.stdout
    .split("\n")
    // 新版 macOS 的格式是「Meijia (Chinese (Taiwan)) zh_TW    # …」，舊版是「Meijia   zh_TW  # …」
    .map((l) => l.match(/^(.+?)\s+([a-z]{2,3}_[A-Z0-9]{2,3})\s+#/))
    .filter(Boolean)
    .map((m) => ({ name: m[1].replace(/\s*\(.*\)\s*$/, "").trim(), locale: m[2] }));
}
function pickSayVoice() {
  const voices = sayVoices();
  if (!voices) return null;
  const want = opt("--voice", null);
  if (want) {
    if (voices.some((v) => v.name === want)) return want;
    log(`! 找不到語音「${want}」，改用自動挑選`);
  }
  const loc = lang.toLowerCase().startsWith("en") ? "en_US" : lang.replace("-", "_");
  const prefer = loc.startsWith("en") ? ["Samantha", "Alex"] : ["Meijia", "Tingting", "Sinji"];
  for (const p of prefer) if (voices.some((v) => v.name === p)) return p;
  const same = voices.find((v) => v.locale === loc) || voices.find((v) => v.locale.startsWith(loc.slice(0, 2)));
  return same ? same.name : ""; // "" = 系統預設語音
}

async function ttsEleven(text, outMp3) {
  const key = process.env.ELEVENLABS_API_KEY;
  const voice = process.env.ELEVENLABS_VOICE_ID || "JBFqnCBsd6RMkjVDRZzb";
  const model = process.env.ELEVENLABS_MODEL || "eleven_multilingual_v2";
  const res = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${voice}?output_format=mp3_44100_128`, {
    method: "POST",
    headers: { "xi-api-key": key, "content-type": "application/json", accept: "audio/mpeg" },
    body: JSON.stringify({ text, model_id: model }),
  });
  if (!res.ok) throw new Error(`ElevenLabs ${res.status}: ${(await res.text()).slice(0, 200)}`);
  fs.writeFileSync(outMp3, Buffer.from(await res.arrayBuffer()));
}
function ttsSay(text, outAiff, voice) {
  const txt = outAiff.replace(/\.aiff$/, ".txt");
  fs.writeFileSync(txt, text);
  const args = ["-o", outAiff, "-f", txt];
  if (voice) args.unshift("-v", voice);
  if (RATE > 0) args.unshift("-r", String(RATE));
  const r = spawnSync("say", args, { encoding: "utf8" });
  if (r.status !== 0) throw new Error(`say 失敗：${r.stderr}`);
}

let engine = TTS;
if (engine === "auto") engine = process.env.ELEVENLABS_API_KEY ? "elevenlabs" : "say";
if (engine === "elevenlabs" && !process.env.ELEVENLABS_API_KEY) die("--tts elevenlabs 需要環境變數 ELEVENLABS_API_KEY");
const sayVoice = engine === "say" ? pickSayVoice() : null;
if (engine === "say" && sayVoice === null) die("這台機器沒有 macOS `say`。設 ELEVENLABS_API_KEY 改用 ElevenLabs");
log(`配音：${engine === "say" ? `macOS say（語音 ${sayVoice || "系統預設"}）` : "ElevenLabs"}`);

const plan = []; // {scene, narration, wav, audio, dur}
for (let i = 0; i < scenes.length; i++) {
  const s = scenes[i];
  const n = i + 1;
  const raw = path.join(WORK, `voice-${n}.${engine === "say" ? "aiff" : "mp3"}`);
  if (engine === "elevenlabs") {
    try {
      await ttsEleven(s.narration, raw);
    } catch (e) {
      const key = process.env.ELEVENLABS_API_KEY || "";
      const msg = key ? String(e.message).split(key).join("[REDACTED]") : String(e.message);
      // 使用者明講 --tts elevenlabs 就不偷偷換聲音：整支片會混兩種聲音，而且看不出來是 key／額度出問題
      if (TTS === "elevenlabs") die(`第 ${n} 幕 ElevenLabs 配音失敗：${msg}\n（明確指定 --tts elevenlabs 時不退回 say；要自動退回請用 --tts auto）`);
      log(`! 第 ${n} 幕 ${msg} → 這幕改用 say（--tts auto）`);
      ttsSay(s.narration, raw.replace(/\.mp3$/, ".aiff"), pickSayVoice());
    }
  } else ttsSay(s.narration, raw, sayVoice);
  const src = fs.existsSync(raw) ? raw : raw.replace(/\.mp3$/, ".aiff");
  const audio = duration(src);
  const dur = audio + GAP + (n === scenes.length ? TAIL : 0);
  const wav = path.join(WORK, `scene-${n}.wav`);
  // 每幕的聲音補靜音到整幕長度 → 之後直接接起來就和畫面對齊
  ff(["-i", src, "-af", `apad=whole_dur=${dur.toFixed(3)}`, "-ar", "48000", "-ac", "1", wav]);
  plan.push({ scene: Number(s.scene) || n, narration: s.narration, wav, audio, dur });
  log(`  第 ${Number(s.scene) || n} 幕  旁白 ${audio.toFixed(1)} 秒 → 本幕 ${dur.toFixed(1)} 秒${audio > 15 ? "  ! 超過 15 秒建議上限" : ""}`);
}
const total = plan.reduce((a, p) => a + p.dur, 0);
if (flag("--dry-run")) {
  log(`(dry-run) 總長 ${total.toFixed(1)} 秒` + (flag("--keep-work") ? `；工作目錄 ${WORK}` : ""));
  await browser.close();
  if (!flag("--keep-work")) fs.rmSync(WORK, { recursive: true, force: true });
  process.exit(0);
}

// ── 3. 逐幕截圖（暫停動畫、逐格推時間 → 決定性）──────
const frames = []; // {file, dur}
let fno = 0;
const shot = async (dur) => {
  const f = path.join(WORK, `f${String(++fno).padStart(5, "0")}.png`);
  await page.screenshot({ path: f });
  frames.push({ file: path.basename(f), dur });
};
for (let i = 0; i < plan.length; i++) {
  const p = plan[i];
  await page.evaluate((n) => window.__goToScene(n), p.scene);
  // 等兩個 frame 讓樣式變化產生 CSS transition／animation，再全部暫停在第 0 毫秒
  const animEnd = await page.evaluate(
    () =>
      new Promise((res) =>
        requestAnimationFrame(() =>
          requestAnimationFrame(() => {
            // 簡報的操作列進度條等介面也有 transition，但已被 video-mode 藏起來；只收看得到的動畫
            const as = document.getAnimations();
            let end = 0;
            for (const a of as) {
              a.pause();
              a.currentTime = 0;
              const t = a.effect && a.effect.getComputedTiming();
              end = Math.max(end, t && isFinite(t.endTime) ? t.endTime : 3000); // 無限循環最多錄 3 秒
            }
            window.__hvAnims = as;
            res(end);
          }),
        ),
      ),
  );
  const animSec = Math.min(animEnd / 1000, p.dur - 1 / FPS);
  const n = Math.max(0, Math.ceil(animSec * FPS));
  for (let k = 0; k < n; k++) {
    await page.evaluate((t) => window.__hvAnims.forEach((a) => (a.currentTime = t)), (k * 1000) / FPS);
    await shot(1 / FPS);
  }
  // 動畫收尾：有限的直接跳到結束，無限循環停在錄到的最後一格
  await page.evaluate((t) => window.__hvAnims.forEach((a) => {
    try {
      const ct = a.effect.getComputedTiming();
      if (isFinite(ct.endTime)) a.finish();
      else a.currentTime = t;
    } catch (e) {}
  }), animSec * 1000);
  await shot(p.dur - n / FPS);
  log(`  第 ${p.scene} 幕  動畫 ${n} 格 + 靜止 ${(p.dur - n / FPS).toFixed(1)} 秒`);
}
await browser.close();

// ── 4. 字幕（句子依字數分配時間）────────────────────
function srtTime(t) {
  const ms = Math.round(t * 1000);
  const h = Math.floor(ms / 3600000), m = Math.floor((ms % 3600000) / 60000), s = Math.floor((ms % 60000) / 1000);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")},${String(ms % 1000).padStart(3, "0")}`;
}
const cues = [];
let t0 = 0;
for (const p of plan) {
  const parts = p.narration.split(/(?<=[。！？!?；;])\s*/).map((x) => x.trim()).filter(Boolean);
  const chars = parts.reduce((a, x) => a + x.length, 0) || 1;
  let t = t0;
  for (const x of parts) {
    const d = (p.audio * x.length) / chars;
    cues.push({ a: t, b: t + d, text: x });
    t += d;
  }
  t0 += p.dur;
}
const srt = cues.map((c, i) => `${i + 1}\n${srtTime(c.a)} --> ${srtTime(c.b)}\n${c.text}\n`).join("\n");
fs.writeFileSync(path.join(WORK, "subs.srt"), srt);

// ── 5. 合成 ───────────────────────────────────────
// 畫面序列：每張截圖依它要撐的時間鋪成 N 格（用符號連結，不複製檔案）。
// 依「累計時間」取整到格，整支片的漂移 ≤ 1 格，聲音與畫面每幕都對得上。
// （不用 concat demuxer 的 duration：圖片輸入會被捨入成 25fps 的時間基準，實測整支多出 1 秒多）
const SEQ = path.join(WORK, "seq");
fs.mkdirSync(SEQ);
let tCum = 0, made = 0;
for (const f of frames) {
  tCum += f.dur;
  const until = Math.round(tCum * FPS);
  for (; made < until; made++)
    fs.symlinkSync(path.join(WORK, f.file), path.join(SEQ, `${String(made + 1).padStart(6, "0")}.png`));
}
fs.writeFileSync(path.join(WORK, "audio.txt"), plan.map((p) => `file '${path.basename(p.wav)}'`).join("\n") + "\n");
ff(["-f", "concat", "-safe", "0", "-i", "audio.txt", "-c:a", "pcm_s16le", "narration.wav"]);

let vf = "null";
if (flag("--burn-subs")) {
  const hasLibass = spawnSync(FFMPEG, ["-hide_banner", "-filters"], { encoding: "utf8" }).stdout.includes(" subtitles ");
  if (hasLibass) {
    const font = lang.toLowerCase().startsWith("en") ? "Helvetica" : "PingFang TC";
    vf += `,subtitles=subs.srt:force_style='FontName=${font},FontSize=13,PrimaryColour=&H00141413,OutlineColour=&H00F5F9FA,BorderStyle=1,Outline=2,Shadow=0,MarginV=28'`;
  } else log("! 這個 ffmpeg 沒有 libass，不能燒字幕；只輸出 .srt（brew install ffmpeg-full）");
}
vf += ",format=yuv420p";
fs.mkdirSync(path.dirname(OUT), { recursive: true });
ff([
  "-framerate", String(FPS), "-i", "seq/%06d.png",
  "-i", "narration.wav",
  "-vf", vf,
  "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
  "-c:a", "aac", "-b:a", "160k",
  "-movflags", "+faststart",
  OUT,
]);
const OUT_SRT = OUT.replace(/\.mp4$/i, "") + ".srt";
fs.copyFileSync(path.join(WORK, "subs.srt"), OUT_SRT);
if (!flag("--keep-work")) fs.rmSync(WORK, { recursive: true, force: true });

log(`✓ ${OUT}（${duration(OUT).toFixed(1)} 秒，${frames.length} 張截圖）`);
log(`  字幕 ${OUT_SRT}` + (flag("--keep-work") ? `；工作目錄 ${WORK}` : ""));
