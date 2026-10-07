# 影片模式（解說影片）

> SKILL.md § 輸出階梯 第四階的細節。腳本：`scripts/render-video.mjs`。範例：`examples/video-demo/`。

## 是什麼

把一頁版（或任何有場景的頁）錄成 mp4：畫面逐幕長出來，旁白同步念，另附字幕。風格學 3Blue1Brown：**一幕一個想法，畫面跟著旁白一步步組起來**。

```
HTML（data-scene + #video-scenes）
   │
   ├─▶ 每幕旁白 ──▶ say／ElevenLabs ──▶ 配音檔 ──▶ ffprobe 量長度
   │                                                  │ 每幕秒數
   ├─▶ Playwright 1920×1080：__goToScene(n)            ▼
   │     暫停 CSS 動畫 → 逐格推時間 → 截圖 ─────────▶ 畫面序列
   │                                                  │
   └──────────────────────────────▶ ffmpeg ──▶ out.mp4（H.264＋AAC）＋ out.srt
```

## 場景怎麼寫

頁面要有三樣東西（`assets/onepage-template.html` 都內建）：

| 東西 | 寫法 |
|---|---|
| 場景標記 | 元素加 `data-scene="N"`：第 N 幕才出現，之後一直留著（逐幕累加）。SVG 裡放在**沒有 `transform` 屬性**的外層 `<g>` |
| 旁白 | `<script type="application/json" id="video-scenes">{"scenes":[{"scene":1,"narration":"…"}]}</script>`；沒有這段時改收各幕元素的 `data-narration` |
| 場景引擎 | `window.__goToScene(n)`：只切 class，動畫交給 CSS。同一個 n 永遠同一個畫面 |

平常開頁面時**全部顯示**（靜態幀資訊完整，跟 `diagram-design` 的 `animation.md` 同一原則）。網址加 `?scene=1` 進場景模式，用 ← → 鍵手動預覽每一幕。

可用的進場效果（CSS 已寫好）：

- 淡入＋上移 14px：HTML 元素預設
- 淡入：SVG 元素預設
- 畫線：路徑加 `pathLength="1" class="draw"`，進場時從頭畫到尾（虛線不要加，會變實線）
- 當前幕加重：`.scene-now .box` 換 clay 色框，視線跟著旁白走

動畫只用 CSS transition／animation。**不要用 JS 計時器或 requestAnimationFrame 做動畫**——錄影靠暫停 CSS 動畫逐格截圖，JS 動畫錄不到、或錄出來每次不一樣。

## 3b1b 寫法規則

| 規則 | 數字 |
|---|---|
| 一幕一個想法 | 這幕只加一樣新東西（一個節點、一條線、一條重點） |
| 逐步組起來 | 第 1 幕放最少的東西；最後一幕＝完整的一頁版 |
| 幕數 | ≤ 8 幕；多了拆成兩支片 |
| 每幕旁白 | ≤ 15 秒、≤ 3 句、每句 ≤ 20 字（中文約每秒 4.5 字） |
| 旁白與畫面 | 旁白講的東西，這一幕畫面上一定看得到 |
| 用字 | 照 `writing-ste.md`：主動語態、一詞一義、數字取代形容詞；不寫括號（念不出來）；數字寫成念法（「四十毫秒」）比較不會念錯 |

`verify.py` 會檢查：幕數 ≤ 8、有 `__goToScene`、每幕有旁白、旁白估計 ≤ 15 秒、每幕都有 `data-scene` 元素。

## 執行

需要：Node 18 以上、`ffmpeg`／`ffprobe`、Playwright、macOS `say`（或 ElevenLabs）。

```bash
# 1. Playwright 沒裝過：裝在固定資料夾，不用全域安裝
mkdir -p ~/.cache/hv-pw && npm --prefix ~/.cache/hv-pw i playwright
export HTML_VISUALIZER_PLAYWRIGHT_ROOT=~/.cache/hv-pw/node_modules
# 有 Google Chrome 就直接用；沒有再跑：npx --prefix ~/.cache/hv-pw playwright install chromium

# 2. 出片
node <skill>/scripts/render-video.mjs page.html --out ~/Documents/claude-html/2026-10/topic.mp4
```

| 參數 | 預設 | 說明 |
|---|---|---|
| `--out` | 與 HTML 同名 `.mp4` | 字幕同名 `.srt` 放旁邊 |
| `--tts` | `auto` | `auto`＝有 `ELEVENLABS_API_KEY` 用 ElevenLabs，否則 `say`（ElevenLabs 某幕失敗會退回 `say`）；可強制 `say`／`elevenlabs`（強制時失敗就停下，不退回）|
| `--voice` | 依頁面 `lang` 自動 | 中文挑 Meijia（台灣）→ Tingting → 同語系任一；英文挑 Samantha |
| `--rate` | 語音預設 | `say` 每分鐘字數 |
| `--gap` / `--tail` | 0.6 / 1.2 秒 | 每幕念完多停幾秒／最後一幕再多停幾秒 |
| `--burn-subs` | 關 | 把字幕燒進畫面（需要有 libass 的 ffmpeg，如 `ffmpeg-full`） |
| `--fps` | 30 | |
| `--dry-run` | | 只產配音、印每幕秒數，不錄畫面 |
| `--keep-work` | | 保留工作目錄（截圖、配音）方便除錯 |

ElevenLabs 另可設 `ELEVENLABS_VOICE_ID`（預設一個內建多語聲音）與 `ELEVENLABS_MODEL`（預設 `eleven_multilingual_v2`）。某幕呼叫失敗時：`--tts auto` 那幕自動改用 `say`（會印出警告）；明確指定 `--tts elevenlabs` 則直接停下報錯（錯誤訊息裡的金鑰會遮掉），不偷偷換聲音。

找 ffmpeg 的順序：環境變數 `FFMPEG`／`FFPROBE` → PATH → `/opt/homebrew/opt/ffmpeg-full/bin` → `/opt/homebrew/bin`。

出片後用這行確認有影像＋聲音、長度合理：

```bash
ffprobe -v error -show_entries stream=codec_type,codec_name,duration -of compact out.mp4
```

## 為什麼這樣錄（決定性）

- **不用 Playwright 內建錄影**：它的影格率跟著機器忙碌程度飄，聲音對不準；而且要另外下載它專用的 ffmpeg。
- **暫停動畫、逐格設時間再截圖**：`document.getAnimations()` 全部 `pause()`，每格設 `currentTime`。同一份 HTML 在快慢不同的機器錄出同一支片。
- **動畫結束後只截一張**：靜止畫面用符號連結鋪滿剩下的格數，不重複截圖。依累計時間取整到格，整支片的影音漂移 ≤ 1 格。
- 每幕的配音補靜音到整幕長度再接起來，所以每一幕的聲音和畫面同時開始。

## 疑難排解

| 症狀 | 原因與解法 |
|---|---|
| `找不到 playwright 套件` | 照上面「執行」第 1 步裝，設 `HTML_VISUALIZER_PLAYWRIGHT_ROOT`；或在已裝 playwright 的專案根目錄執行 |
| `chromium 與系統 Chrome 都起不來` | 安裝 Google Chrome，或 `npx playwright install chromium` |
| `頁面沒有 window.__goToScene(n)` | 複製 `assets/onepage-template.html` 的「場景引擎」script 與場景 CSS |
| 某幕畫面沒變 | 那幕沒有 `data-scene="N"` 的元素（`verify.py` 會報）；或 N 寫錯 |
| SVG 節點跑到左上角 | `data-scene` 放在有 `transform` 的 `<g>` 上，CSS transform 蓋掉了位置。改包一層沒有 transform 的 `<g>` |
| 虛線變實線 | 虛線路徑加了 `class="draw"`。拿掉 |
| 念錯字、斷句怪 | 改旁白用字：數字寫成國字念法、拆短句；或換 `--voice` |
| 聲音是英文腔 | 頁面 `<html lang>` 不是 `zh-TW`，或系統沒有中文語音（系統設定 → 輔助使用 → 朗讀內容 → 系統語音 → 管理語音，下載 Meijia） |
| `--burn-subs` 沒效果 | 這個 ffmpeg 沒有 libass，只會輸出 `.srt`；改用 `brew install ffmpeg-full` 的版本（設 `FFMPEG`） |
| 畫面上出現評論鈕／風格設定鈕 | 腳本已自動藏掉 `vt-` 介面元件；自訂的固定按鈕要自己加 `.video-mode` 隱藏規則 |
