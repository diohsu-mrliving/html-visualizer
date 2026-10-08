# help 說明全文

本檔是 `help` skill 要原樣輸出的固定說明。改內容時，裡面出現的指令、參數、路徑都要先對過 `skills/html-visualizer/scripts/` 的實際程式。

<!-- help:begin -->
## html-visualizer 怎麼用

**一句話**：把 AI 的長篇回答變成一份好讀的網頁（報告、簡報、圖表、流程圖），自動存檔、自動打開給你看。

### 裡面有三個小幫手（skill）

| Skill | 做什麼 | 什麼時候會用到 |
|---|---|---|
| `html-visualizer` | 主要入口。挑版型、做頁面、自己檢查、打開給你看 | 你說「整理成報告」「做成簡報」「列選項讓我選」 |
| `chart` | 資料圖表：柱狀、折線、圓餅、KPI、dashboard | 你有一組數字，想看趨勢或比例 |
| `diagram-design` | 結構圖：流程、架構、時序、狀態機、泳道等 39 種 | 你要畫「誰交給誰、先做什麼」的關係圖 |

你不用記哪個是哪個。照平常講話，AI 會自己挑。

### 可以做哪些東西（直接照著說就行）

| 想要的東西 | 直接可以說的一句話 |
|---|---|
| 報告／文件 | 「把剛剛的分析整理成一份報告給我看」 |
| 一頁版（一頁講完、不用捲） | 「一頁講完這個，給老闆一眼看懂」 |
| 簡報 | 「把這份內容做成簡報，我下週要上台報告」 |
| 解說影片 | 「把這一頁做成有旁白的解說影片」 |
| 結構圖 | 「幫我畫這個請款流程的泳道圖」（也可以說流程圖、架構圖、時序圖、狀態機） |
| 資料圖表／dashboard | 「把這份月營收做成趨勢圖」「做一個進度 dashboard」 |
| 待拍板選項頁 | 「列出這幾個方案讓我選，選完可以一鍵複製回來」 |
| 教學頁 | 「教我 prompt cache 是怎麼運作的」 |

小提醒：
- **簡報**用 ← → 換頁，N 看講者備註，O 看總覽，P 列印或存 PDF（一張一頁）。
- **解說影片**需要電腦裝好 Node 18 以上、ffmpeg、Playwright；旁白預設用 macOS 內建語音。
- **選項頁**在網頁上點選好，按複製，再貼回對話給 AI 就行。

### 品牌風格：預設是居家先生 CI

- 每次做頁面，最後自檢時會**現場**去讀居家先生 CI skill（`mr-living-presentation`），套用品牌色、字型與 Logo。CI 改版時，這裡會自動跟上。
- **找不到 CI 或讀不懂**，整頁自動改用原本樣式（米白底、赤陶色），並印一行原因。不會出現一半一半的頁面。
- **想切回原本樣式**，選一種：

| 範圍 | 怎麼做 |
|---|---|
| 以後都用原本樣式 | 跟 AI 說「以後都用原本樣式」，它會執行 `profile.py set tokens.theme=default` |
| 只有這一頁 | 頁面開頭寫 `<html data-vt-theme="default">` |
| 只有這一次自檢 | `verify.py <檔案> --theme=default` |
| 這個終端機視窗裡都用原本樣式 | 設定環境變數 `HTML_VISUALIZER_THEME=default` |

- 想換回居家先生風格：`profile.py set tokens.theme=mrl`。
- 同時有好幾個設定時，先到先贏：指令參數 → 頁面標記 → 環境變數 → 設定檔 → 預設（居家先生）。
- 想看這次會套哪個風格：`python3 <html-visualizer 目錄>/scripts/brand.py show`。

### 做好的頁面在哪、怎麼檢查

- **存在** `~/Documents/claude-html/年-月/` 底下，例如 `~/Documents/claude-html/2026-10/`。索引頁是 `~/Documents/claude-html/index.html`，可以回頭找「上禮拜那份」。想換位置就設環境變數 `HTML_VISUALIZER_ARCHIVE_DIR`。
- **檢查**：AI 給你看之前會先跑 `verify.py`（`python3 <html-visualizer 目錄>/scripts/verify.py <檔案>`），一次查完排版、按鈕能不能按、手機會不會跑版。你不用自己跑。

### 常見問題

**問：說了「整理一下」，AI 卻只回一段文字？**
答：內容太短時，它刻意不做網頁。想要網頁就直接說「做成網頁給我看」。

**問：檢查結果寫「未驗證」，是壞掉了嗎？**
答：不是。「未驗證」表示「沒檢查」，不是「有問題」。排版檢查要用瀏覽器自動化工具 Playwright。電腦有 Chrome 時，跑 `npm i -D playwright` 就夠了。

**問：頁面不是居家先生的樣子？**
答：看自檢的輸出有沒有「沒找到居家先生 CI，改用原本樣式」這一行，後面會寫原因。最常見的原因是沒裝 `mr-living-presentation` skill。也可能是你之前設過 `tokens.theme=default`。

**問：我的偏好（字大一點、不要 emoji）可以記住嗎？**
答：可以。在頁面底部按「風格設定」→「存成我的預設」，或直接跟 AI 說「以後不要用 emoji」。偏好存在 `~/.config/html-visualizer/profile.json`。claude.ai 網頁版每次都是新環境，存不住，只影響當次。
<!-- help:end -->
