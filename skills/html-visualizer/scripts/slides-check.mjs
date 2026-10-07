#!/usr/bin/env node
/**
 * 簡報檢查 — 簡報（<html data-layout="slides">）每一張在 1920×1080 放得下、版型認得、沒超過該版型的上限。
 *
 * 為什麼要真的渲染：「這張放不放得下」取決於字型、換行、圖的縮放，標記看不出來。
 * 簡報每張是固定畫布（overflow: hidden），超出的部分會被默默切掉——不量就不知道。
 *
 * 每張量：
 *   1. 版型：section[data-layout] 是不是 10 種之一
 *   2. 放得下：.slide 的 scrollHeight／scrollWidth ≤ 1080／1920；有元素凸出畫布 → 列出最外層幾個
 *   3. 文字被切：葉節點 scrollWidth > clientWidth
 *   4. 字級：HTML 文字 ≥ 16px、SVG 文字實際顯示 ≥ 14px（投影最後一排要讀得到）
 *   5. 版型上限（references/slides.md）：條列 3–5 條、比較 2 欄每欄 ≤ 4 點、流程 ≤ 7 節點、
 *      時間軸 3–6 點、表格 ≤ 6 列 ≤ 5 欄、圖表 1 張、結論行動 ≤ 4 條……
 *   6. 旁白（影片用）：每張有沒有 data-narration 或講者備註；估計秒數
 * 每張另存一張 1920×1080 截圖。
 *
 * 用法：node slides-check.mjs <file.html> [--pdf out.pdf] [--json]
 *   --pdf：順便用列印樣式輸出 PDF（一張一頁、1920×1080），印出頁數
 * exit 0 = 全部放得下；1 = 有張放不下或超量；2 = 找不到 playwright／瀏覽器（無法驗證，不是通過）
 */
import { pathToFileURL } from "node:url";
import path from "node:path";
import os from "node:os";
import fs from "node:fs";
import { createRequire } from "node:module";

const argv = process.argv.slice(2);
const file = argv.find((a, i) => !a.startsWith("--") && argv[i - 1] !== "--pdf");
if (!file) {
  console.error("用法：node slides-check.mjs <file.html> [--pdf out.pdf] [--json]");
  process.exit(64);
}
const pdfOut = argv.includes("--pdf") ? argv[argv.indexOf("--pdf") + 1] : null;
const asJson = argv.includes("--json");
const W = 1920;
const H = 1080;
const TOL = 1.5;

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
if (!pw) {
  console.error("NO_PLAYWRIGHT");
  process.exit(2);
}
let browser;
try {
  browser = await pw.chromium.launch();
} catch {
  try {
    browser = await pw.chromium.launch({ channel: "chrome" });
  } catch {
    console.error("NO_BROWSER");
    process.exit(2);
  }
}

const page = await browser.newPage({ viewport: { width: W, height: H } });
const pageErrors = [];
page.on("pageerror", (e) => pageErrors.push(String(e).split("\n")[0]));
// ?video：藏掉操作列與頁面工具，截圖就是投影畫面
await page.goto(pathToFileURL(path.resolve(file)).href + "?video=1", { waitUntil: "load", timeout: 30000 });
await page.evaluate(() => document.fonts && document.fonts.ready);
await page.waitForTimeout(1200); // Tailwind CDN 與字型套上
await page.waitForFunction(() => window.__chartsReady !== false, null, { timeout: 15000 }).catch(() => {});

const hasDeck = await page.evaluate(() => !!(window.__deck && document.querySelector(".deck .slide")));
if (!hasDeck) {
  console.log("  ✗ 找不到簡報引擎（window.__deck）或 .slide——從 assets/slides-template.html 複製起手");
  await browser.close();
  process.exit(1);
}
const count = await page.evaluate(() => window.__deck.count);

const shotDir = process.env.HTML_VISUALIZER_SHOT_DIR || path.join(os.tmpdir(), "html-visualizer-shots");
fs.mkdirSync(shotDir, { recursive: true });
const base = path.basename(file, ".html");

/** 在頁面裡跑：量第 i 張。 */
function probe({ i, W, H, TOL }) {
  const KNOWN = ["cover", "section", "bullets", "big-number", "compare", "flow", "timeline", "table", "chart", "closing"];
  const s = document.querySelectorAll(".deck .slide")[i];
  const layout = s.getAttribute("data-layout") || "";
  const issues = [];
  const warns = [];
  if (!KNOWN.includes(layout))
    issues.push(layout ? `版型「${layout}」不在 10 種之內（${KNOWN.join(" / ")}）` : "沒寫 data-layout（10 種版型擇一）");

  // 2. 放得下：overflow:hidden 的畫布，scrollHeight 仍量得到被切掉的內容
  if (s.scrollHeight > H + TOL) issues.push(`內容高 ${s.scrollHeight}px，超出畫布 ${s.scrollHeight - H}px（會被切掉）`);
  if (s.scrollWidth > W + TOL) issues.push(`內容寬 ${s.scrollWidth}px，橫向超出 ${s.scrollWidth - W}px`);
  const sb = s.getBoundingClientRect();
  const k = sb.width / W || 1; // 目前的縮放比例（量的時候視窗就是 1920×1080，通常 = 1）
  const label = (el) => {
    const cls = (el.getAttribute("class") || "").split(/\s+/).filter(Boolean).slice(0, 2).join(".");
    const txt = (el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 22);
    return el.tagName.toLowerCase() + (cls ? "." + cls : "") + (txt ? ` 「${txt}」` : "");
  };
  const over = [];
  const clipped = [];
  const tiny = [];
  for (const el of s.querySelectorAll("*")) {
    if (el.closest(".notes, script, style, template, .symbols")) continue;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") continue;
    const r = el.getBoundingClientRect();
    if (!r.width && !r.height) continue;
    const isSvg = el instanceof SVGElement;
    if (!isSvg || el.tagName.toLowerCase() === "svg") {
      const by = Math.max(r.bottom - sb.bottom, r.right - sb.right, sb.left - r.left, sb.top - r.top) / k;
      if (by > TOL) over.push({ el, by });
    }
    if (!isSvg && el.children.length === 0 && el.scrollWidth > el.clientWidth + TOL && !["auto", "scroll"].includes(cs.overflowX))
      clipped.push({ el, cut: el.scrollWidth - el.clientWidth });
    // 4. 字級：只看直接有文字的元素
    const ownText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!ownText) continue;
    let px;
    if (isSvg) {
      const m = el.getScreenCTM && el.getScreenCTM();
      px = parseFloat(cs.fontSize) * (m ? Math.hypot(m.a, m.b) : 1) / k;
      if (px < 14 - 0.05) tiny.push({ el, px });
    } else {
      px = parseFloat(cs.fontSize);
      if (px < 16 - 0.05) tiny.push({ el, px });
    }
  }
  const outer = over.filter((a) => !over.some((b) => b.el !== a.el && b.el.contains(a.el)));
  for (const o of outer.slice(0, 4)) issues.push(`凸出畫布 ${Math.round(o.by)}px：${label(o.el)}`);
  for (const c of clipped.slice(0, 3)) issues.push(`文字被切掉 ${Math.round(c.cut)}px：${label(c.el)}`);
  for (const t of tiny.slice(0, 3)) issues.push(`字太小 ${t.px.toFixed(1)}px（HTML ≥ 16、圖上 ≥ 14）：${label(t.el)}`);

  // 5. 版型上限
  const n = (sel) => s.querySelectorAll(sel).length;
  const title = (s.querySelector("h1, h2") || {}).textContent || "";
  const tlen = title.replace(/\s+/g, "").length;
  const lim = (cond, msg) => cond || issues.push(msg);
  switch (layout) {
    case "cover":
      lim(n("h1") === 1, `封面要有 1 個 h1（現在 ${n("h1")}）`);
      break;
    case "section":
      lim(n("ul, ol, table, svg:not(.icon)") === 0, "章節頁只放章節號、標題、一句說明（不放清單／表格／圖）");
      break;
    case "bullets": {
      // 一條＝條列項目；slide-report 的元件也算：檢查列、三層、履歷欄位、主格線裡的卡片（取第一組有的）
      const groups = [".bl-list > li", ".checklist > .checkrow", ".layers > .layer", ".passport .field", ".slide > .grid > .card"];
      const k2 = groups.map((g) => [...s.querySelectorAll(g)].filter((e) => e.closest(".slide") === s).length).find((x) => x > 0) || 0;
      lim(k2 >= 3 && k2 <= 5, `重點條列要 3–5 條（現在 ${k2}）——多了拆成兩張`);
      break;
    }
    case "big-number":
      lim(n(".bn-num") === 1, `大數字一張只放 1 個數字（現在 ${n(".bn-num")}）`);
      break;
    case "compare": {
      const cols = n(".grid.g2 > .card, .cp-col");
      lim(cols === 2, `左右比較要剛好 2 欄（現在 ${cols}）`);
      const most = Math.max(0, ...[...s.querySelectorAll(".grid.g2 > .card, .cp-col")].map((c) => c.querySelectorAll("li").length));
      lim(most <= 4, `比較每欄 ≤ 4 點（最多一欄 ${most} 點）`);
      break;
    }
    case "flow": {
      const svgs = n("svg.diagram, .fl-fig svg, .hub");
      lim(svgs === 1, `流程圖一張放 1 張圖（svg.diagram 或 .hub；現在 ${svgs}）`);
      lim(n("svg .node") <= 7, `流程圖節點 ≤ 7（現在 ${n("svg .node")}）——多了拆兩張或改成總覽＋細節`);
      break;
    }
    case "timeline": {
      const k3 = n(".tl-item");
      lim(k3 >= 3 && k3 <= 6, `時間軸 3–6 個節點（現在 ${k3}）`);
      break;
    }
    case "table": {
      const rows = n("tbody tr");
      const cols = Math.max(0, ...[...s.querySelectorAll("tr")].map((tr) => tr.children.length));
      lim(n("table") === 1, `表格一張放 1 個表（現在 ${n("table")}）`);
      lim(rows <= 6, `表格 ≤ 6 列（現在 ${rows}）——多的放附錄或拆張`);
      lim(cols <= 5, `表格 ≤ 5 欄（現在 ${cols}）`);
      break;
    }
    case "chart":
      lim(n(".ch-plot") === 1, `圖表一張放 1 張圖（現在 ${n(".ch-plot")}）`);
      lim(n(".ch-side > *") <= 2, `圖表旁的解讀 ≤ 2 條（現在 ${n(".ch-side > *")}）`);
      if (n(".ch-plot") && !s.querySelector(".ch-plot svg") && !s.querySelector(".ch-fallback"))
        warns.push("圖表還沒畫出來（CDN 慢或資料錯）");
      if (s.querySelector(".ch-fallback")) warns.push("圖表沒畫出來：" + s.querySelector(".ch-fallback").textContent.trim());
      break;
    case "closing":
      lim(n(".cl-list > li") <= 4, `下一步 ≤ 4 條（現在 ${n(".cl-list > li")}）`);
      lim(n(".cl-decisions > li") <= 3, `已拍板 ≤ 3 條（現在 ${n(".cl-decisions > li")}）`);
      break;
  }
  if (tlen > 28) warns.push(`標題 ${tlen} 字（建議 ≤ 28，一行講完）`);

  const narr = (s.getAttribute("data-narration") || (s.querySelector(".notes") || {}).textContent || "").trim();
  return { layout, issues, warns, narrSrc: s.getAttribute("data-narration") ? "data-narration" : narr ? "notes" : "" };
}

const rows = [];
for (let i = 0; i < count; i++) {
  await page.evaluate((n) => window.__goToScene(n), i + 1);
  // 進場動畫直接跳到結束，量最終畫面；圖表在 slide 看得到時才畫，等兩個 frame
  await page.evaluate(
    () =>
      new Promise((res) =>
        requestAnimationFrame(() =>
          requestAnimationFrame(() => {
            document.getAnimations().forEach((a) => {
              try {
                a.finish();
              } catch (e) {
                /* 無限循環的動畫 finish 會丟錯，略過 */
              }
            });
            res();
          }),
        ),
      ),
  );
  if (await page.evaluate((n) => !!document.querySelectorAll(".deck .slide")[n].querySelector(".ch-plot"), i))
    await page.waitForTimeout(400);
  const r = await page.evaluate(probe, { i, W, H, TOL });
  const shot = path.join(shotDir, `${base}-slide-${String(i + 1).padStart(2, "0")}-${r.layout || "unknown"}.png`);
  await page.screenshot({ path: shot });
  rows.push({ n: i + 1, shot, ...r });
}

const scenes = await page.evaluate(() => (window.__getScenes ? window.__getScenes() : []));
let pdfInfo = null;
if (pdfOut) {
  await page.evaluate(() => window.__deck.grid(true)); // 每張都畫過一次（圖表要看得到才畫得出來）
  await page.waitForTimeout(800);
  await page.emulateMedia({ media: "print" });
  await page.pdf({ path: path.resolve(pdfOut), preferCSSPageSize: true, printBackground: true });
  const buf = fs.readFileSync(path.resolve(pdfOut), "latin1");
  pdfInfo = { path: path.resolve(pdfOut), pages: (buf.match(/\/Type\s*\/Page[^s]/g) || []).length };
}
await browser.close();

if (asJson) {
  console.log(JSON.stringify({ count, rows, scenes, pdfInfo, pageErrors }));
  process.exit(rows.some((r) => r.issues.length) || pageErrors.length ? 1 : 0);
}

let bad = 0;
if (pageErrors.length) {
  bad++;
  console.log(`  ✗ 載入時腳本出錯：${pageErrors[0]}`);
}
for (const r of rows) {
  const tag = `第 ${String(r.n).padStart(2, "0")} 張 ${r.layout || "?"}`;
  if (r.issues.length) {
    bad++;
    console.log(`  ✗ ${tag}  ${r.issues.length} 項  截圖 ${r.shot}`);
    for (const x of r.issues) console.log(`         ${x}`);
  } else console.log(`  ✓ ${tag}  1920×1080 放得下  截圖 ${r.shot}`);
  for (const w of r.warns) console.log(`         ! ${w}`);
}
// 旁白：只要有一張寫了 data-narration，就當作要出影片，檢查每張都有
const withData = rows.filter((r) => r.narrSrc === "data-narration").length;
const empty = scenes.filter((s) => !(s.narration || "").trim()).map((s) => s.scene);
const est = scenes.map((s) => {
  const t = s.narration || "";
  const cjk = (t.match(/[㐀-鿿]/g) || []).length;
  return cjk / 4.5 + (t.length - cjk) / 15;
});
const longest = est.length ? Math.max(...est) : 0;
console.log(
  `  旁白：${scenes.length - empty.length}/${scenes.length} 張有（data-narration ${withData} 張，其餘取講者備註）` +
    (scenes.length ? `；最長約 ${longest.toFixed(0)} 秒；全片約 ${est.reduce((a, b) => a + b + 0.6, 0).toFixed(0)} 秒` : ""),
);
if (withData && empty.length) console.log(`         ! 第 ${empty.join("、")} 張沒有旁白，出影片時這幾張會被擋下`);
if (longest > 15) console.log(`         ! 有張旁白估計超過 15 秒（每張 ≤ 3 句、每句 ≤ 20 字）`);
if (pdfInfo) console.log(`  PDF：${pdfInfo.pages} 頁 → ${pdfInfo.path}`);
console.log(`  共 ${count} 張；${bad ? `${bad} 張有問題` : "全部放得下"}`);
process.exit(bad ? 1 : 0);
