#!/usr/bin/env node
/**
 * 一頁檢查 — 一頁版（<html data-layout="onepage">）在 1920×1080 一個畫面放得下、不用捲動。
 *
 * 為什麼要真的渲染：「放不放得下」取決於字型、換行、圖的縮放，標記看不出來。
 * 只有量 scrollHeight 算數。
 *
 * 量四件事：
 *   1. 整頁高度 ≤ 視窗高（不用捲動）、寬度不溢出
 *   2. 有元素的底邊超出視窗 → 列出最外層的幾個
 *   3. 重點（[data-takeaway]）≤ 3 條
 *   4. 有場景時：最後一幕（全部出現）也放得下；場景數 ≤ 8
 *
 * 用法：node onepage-check.mjs <file.html> [--width 1920] [--height 1080]
 * exit 0 = 放得下；1 = 放不下或超量；2 = 找不到 playwright／瀏覽器（無法驗證，不是通過）
 */
import { pathToFileURL } from "node:url";
import path from "node:path";
import os from "node:os";
import fs from "node:fs";
import { createRequire } from "node:module";

const file = process.argv[2];
if (!file) {
  console.error("用法：node onepage-check.mjs <file.html> [--width 1920] [--height 1080]");
  process.exit(64);
}
const arg = (k, d) => {
  const i = process.argv.indexOf(k);
  return i > 0 ? parseInt(process.argv[i + 1], 10) || d : d;
};
const W = arg("--width", 1920);
const H = arg("--height", 1080);
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
await page.goto(pathToFileURL(path.resolve(file)).href, { waitUntil: "load", timeout: 20000 });
await page.waitForTimeout(1200); // 等 Tailwind CDN 與字型套上

// 有場景就跳到最後一幕（全部出現），量的是最滿的那個畫面
const scenes = await page.evaluate(() => {
  if (typeof window.__goToScene !== "function") return 0;
  const n = typeof window.__sceneCount === "function" ? window.__sceneCount() : 0;
  if (n) window.__goToScene(n);
  return n;
});
if (scenes) await page.waitForTimeout(1500);

const r = await page.evaluate(({ H, TOL }) => {
  const de = document.documentElement;
  const vw = window.innerWidth;
  const over = [];
  for (const el of document.querySelectorAll("body *")) {
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || cs.position === "fixed") continue;
    const b = el.getBoundingClientRect();
    if (!b.width && !b.height) continue;
    if (b.bottom > H + TOL) over.push({ el, by: b.bottom - H });
  }
  const outer = over.filter((a) => !over.some((b) => b.el !== a.el && b.el.contains(a.el)));
  const label = (el) => {
    const cls = (el.getAttribute("class") || "").split(/\s+/).filter(Boolean).slice(0, 2).join(".");
    const txt = (el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 24);
    return el.tagName.toLowerCase() + (cls ? "." + cls : "") + (txt ? ` 「${txt}」` : "");
  };
  return {
    docH: de.scrollHeight,
    docW: de.scrollWidth,
    vw,
    takeaways: document.querySelectorAll("[data-takeaway]").length,
    svgs: document.querySelectorAll("main svg, .op-fig svg").length,
    over: outer.slice(0, 5).map((x) => ({ what: label(x.el), by: Math.round(x.by) })),
  };
}, { H, TOL });

const shotDir = process.env.HTML_VISUALIZER_SHOT_DIR || path.join(os.tmpdir(), "html-visualizer-shots");
fs.mkdirSync(shotDir, { recursive: true });
const shot = path.join(shotDir, `${path.basename(file, ".html")}-onepage-${W}x${H}.png`);
await page.screenshot({ path: shot });
await browser.close();

const issues = [];
if (r.docH > H + TOL) issues.push(`頁面高 ${r.docH}px，超出 ${H}px 視窗 ${r.docH - H}px（要捲動）`);
if (r.docW > r.vw + TOL) issues.push(`橫向溢出 ${r.docW - r.vw}px`);
for (const o of r.over) issues.push(`底邊超出視窗 ${o.by}px：${o.what}`);
if (r.takeaways > 3) issues.push(`重點 ${r.takeaways} 條（上限 3）`);
if (scenes > 8) issues.push(`場景 ${scenes} 幕（上限 8）`);

const facts = `高 ${r.docH}/${H}px · 重點 ${r.takeaways} 條 · 主圖 SVG ${r.svgs} 張` + (scenes ? ` · 場景 ${scenes} 幕（量最後一幕）` : "");
if (issues.length) {
  console.log(`  ${W}×${H}  ✗ ${issues.length} 項  ${facts}  截圖 ${shot}`);
  for (const i of issues) console.log(`         ${i}`);
  process.exit(1);
}
console.log(`  ${W}×${H}  ✓ 一個畫面放得下  ${facts}  截圖 ${shot}`);
process.exit(0);
