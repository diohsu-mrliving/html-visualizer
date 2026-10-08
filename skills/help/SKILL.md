---
name: help
description: 顯示 html-visualizer plugin 的使用說明：能做哪些東西、每種怎麼開口、品牌風格怎麼切換。使用者打 /html-visualizer:help，或問「html-visualizer 怎麼用／help／這個 skill 可以做什麼」時用；要直接做報告、圖表或簡報時不要用。
---

# html-visualizer 使用說明（help）

使用者想知道「這個 plugin 怎麼用、能做什麼」時才用本 skill。**使用者是要做東西**（「整理成報告」「畫個流程圖」「做成簡報」）→ 不要用本 skill，直接交給 `html-visualizer`／`chart`／`diagram-design`。

## 要做的事（照順序，只有這兩步）

1. **原樣輸出說明**：Read `references/help.md`，把 `<!-- help:begin -->` 與 `<!-- help:end -->` 之間的內容**一字不改**貼進回覆（標記本身不要貼）。不要摘要、不要改寫、不要加自己的補充、不要另做 HTML。
2. **顯示目前套用的風格**：跑下面這行（讀 `brand.py show --json` 的欄位，只組出風格與版本，不帶任何本機路徑）：

   ```bash
   python3 "<本 skill 目錄>/../html-visualizer/scripts/brand.py" show --json | python3 -c 'import json,sys; r=json.load(sys.stdin); print("居家先生 CI " + r["ci"]["version"] if r["theme"] == "mrl" else "原本樣式（原因：" + (r.get("html_reason") or r["why"]) + "）")'
   ```

   - `<本 skill 目錄>` 是本 `SKILL.md` 所在的資料夾；在 Claude Code plugin 裡同一支檔案就是 `${CLAUDE_PLUGIN_ROOT}/skills/html-visualizer/scripts/brand.py`。
   - 在說明最後接一行：`**目前套用的風格**：<那一行輸出>`，例如 `居家先生 CI v0.6` 或 `原本樣式（原因：環境變數 HTML_VISUALIZER_THEME）`。輸出原樣貼上，不要改寫、不要補路徑。
   - 檔案不存在或指令失敗（例如只單獨上傳了本 skill）→ 改寫一行：`**目前套用的風格**：查不到（找不到 html-visualizer 的 brand.py；做頁面時自檢會再告訴你）`。不要猜是哪個風格。

除此之外不做任何事：不改設定檔、不建頁面、不跑 `verify.py`。
