/**
 * 共用：找 playwright 套件。各健檢腳本與 render-video.mjs 都 import 這支，搜尋順序只在這裡改。
 *
 * 本 skill 是全域裝的，playwright 不會在 skill 自己旁邊，所以依序試：
 *   1. 環境變數 HTML_VISUALIZER_PLAYWRIGHT_ROOT（pnpm 專案或自訂位置用）
 *   2. ~/.local/share/html-visualizer/playwright/node_modules（預設安裝位置）
 *   3. ~/.cache/hv-pw/node_modules（舊位置，相容用；~/.cache 依慣例可隨時清除，新裝別放這）
 *   4. 目前工作目錄（在已裝 playwright 的專案根執行時）
 *   5. 這支腳本自己旁邊
 */
import path from "node:path";
import os from "node:os";
import { createRequire } from "node:module";

export const PW_HOME = path.join(os.homedir(), ".local", "share", "html-visualizer", "playwright");
const LEGACY_HOME = path.join(os.homedir(), ".cache", "hv-pw");

// 都找不到時給人看的安裝指令（裝到預設位置；有 Google Chrome 可省略最後一段）
export const PW_INSTALL_CMD =
  "mkdir -p ~/.local/share/html-visualizer/playwright && npm --prefix ~/.local/share/html-visualizer/playwright i playwright && (cd ~/.local/share/html-visualizer/playwright && npx playwright install chromium)";

export function playwrightRoots() {
  return [
    process.env.HTML_VISUALIZER_PLAYWRIGHT_ROOT,
    path.join(PW_HOME, "node_modules"),
    path.join(LEGACY_HOME, "node_modules"),
    process.cwd(),
  ].filter(Boolean);
}

export function loadPlaywright() {
  for (const r of playwrightRoots()) {
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
