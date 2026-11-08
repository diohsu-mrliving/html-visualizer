#!/usr/bin/env node
/**
 * 字級覆蓋率檢查 — 把字級倍率拉到 200%（調整面板的上限），量頁面上的文字有多少真的變大、有沒有橫向溢出。
 *
 * 為什麼要量：蓋章會把頁面寫死的字級改成乘倍率，但有幾種寫法它改不到——腳本在執行期寫進去的
 * 行內樣式、Tailwind 的任意值 class（text-[13px]）等。改不到的字在拉滑桿時不會動，
 * 同一頁會大小字混雜。靜態掃描看不出漏了哪些，只有量得出來。
 * 不吃倍率的區塊（結構圖、畫面樣張、頁面介面本身、data-tw-lock）不列入分母。
 *
 * 用法：node scale-check.mjs <file.html> [--json]
 * exit 0 通過 / 1 未達標 / 2 找不到 playwright 或瀏覽器（代表「無法驗證」，不是「通過」）。
 */
import { pathToFileURL } from "node:url";
import path from "node:path";
import { loadPlaywright } from "./find-playwright.mjs";

const file = process.argv[2];
const asJson = process.argv.includes("--json");
if (!file) {
  console.error("用法：node scale-check.mjs <file.html> [--json]");
  process.exit(64);
}
const THRESHOLD = 0.95;


const pw = loadPlaywright();
if (!pw) {
  console.error("NO_PLAYWRIGHT");
  process.exit(2);
}
async function launchBrowser() {
  try {
    return await pw.chromium.launch();
  } catch {
    try {
      return await pw.chromium.launch({ channel: "chrome" });
    } catch {
      console.error("NO_BROWSER");
      process.exit(2);
    }
  }
}

// 與 assets/tweaks.css 的排除清單一致
const EXEMPT =
  "svg, .mock, [data-tw-lock], .vt-tw-root, .vt-comment-trigger, .vt-comment-popup, .vt-comment-pill, .vt-comment-list, .vt-session-badge";
const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(pathToFileURL(path.resolve(file)).href, {
  waitUntil: "networkidle",
});
await page.waitForTimeout(300);

// 跟 tweaks.js 的 apply 同步：設倍率時一起切 html.vt-fs（Tailwind 文字 class 的覆寫掛在它底下）。
// 只設 --fs 不切 class，倍率 1 載入的頁拉到 200% 時 Tailwind 字不會動，會被誤報成沒變
function setScale(v) {
  document.documentElement.style.setProperty("--fs", v);
  document.documentElement.classList.toggle("vt-fs", parseFloat(v) !== 1);
}

function measure(exempt) {
  const out = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const t = walker.currentNode;
    if (!t.textContent.trim()) continue;
    const el = t.parentElement;
    if (!el || seen.has(el)) continue;
    seen.add(el);
    if (el.closest(exempt) || el.closest("script,style,template,noscript"))
      continue;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height || (el.checkVisibility && !el.checkVisibility()))
      continue;
    out.push(el);
  }
  window.__vtScaleEls = out;
  return out.map((e) => parseFloat(getComputedStyle(e).fontSize));
}
function remeasure() {
  return window.__vtScaleEls.map((e) =>
    parseFloat(getComputedStyle(e).fontSize),
  );
}
function sample(idx) {
  return idx.map((i) => {
    const e = window.__vtScaleEls[i];
    const cls =
      typeof e.className === "string" && e.className
        ? "." + e.className.trim().split(/\s+/).join(".")
        : "";
    return `${e.tagName.toLowerCase()}${cls}「${e.textContent.trim().slice(0, 18)}」${getComputedStyle(e).fontSize}`;
  });
}

// 基準一律在倍率 1 下量：設定檔可能把預設倍率存成 1.5，直接量再拉到 2 只放大 1.33 倍，
// 會把每個字都誤判成「沒變」
await page.evaluate(setScale, "1");
await page.waitForTimeout(100);
const base = await page.evaluate(measure, EXEMPT);
await page.evaluate(setScale, "2");
await page.waitForTimeout(100);
const at2 = await page.evaluate(remeasure);
const unchanged = [];
base.forEach((v, i) => {
  if (!(at2[i] > v * 1.5)) unchanged.push(i);
});
const ratio = base.length ? 1 - unchanged.length / base.length : 1;
const samples = await page.evaluate(sample, unchanged.slice(0, 5));
const overflow = await page.evaluate(
  () =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth,
);
await browser.close();

// 200% 溢出只提醒、不擋：舊頁或自由排版的頁在兩倍字級時略有橫捲仍可用（verify 另報 !）
const ok = ratio >= THRESHOLD;
const result = {
  total: base.length,
  unchanged: unchanged.length,
  ratio: Math.round(ratio * 1000) / 10,
  overflowAt200: overflow,
  samples,
  ok,
};
if (asJson) console.log(JSON.stringify(result));
else {
  console.log(
    `字級 200% 時 ${result.ratio}% 的文字跟著變大（${base.length - unchanged.length}/${base.length}，門檻 ${THRESHOLD * 100}%）`,
  );
  if (samples.length) console.log("沒變的例子：" + samples.join("；"));
  console.log(`字級 200% 時 1440 寬度橫向溢出 ${overflow}px`);
}
process.exit(ok ? 0 : 1);
