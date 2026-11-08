# 配色 + 字體 token（Anthropic / Claude 官方品牌風）

> ⭐ 預設會在蓋章時套「居家先生 CI」（mrl 主題）：下面這組 Anthropic token 是**變數名的標準**與**找不到 CI 時的退回樣式**。流程見 § 品牌主題（mrl，預設）。

每個 HTML 起手式都複製這段 CSS、不要自創顏色 / 字體。風格參考 Anthropic 官方品牌（ivory + clay + serif/sans/mono 三字體）— editorial / book / magazine 質感。

> 這套 token 的實際樣張（色票、墨色規則、字級、元件）見 `examples/anthropic-gallery/index.html`（風格總覽頁；最初的版面參考自 Thariq〈The unreasonable effectiveness of HTML〉的官方 gallery）。

## 完整 design tokens

放在 `<style>` 區的 `:root {}` 內。**包含 Anthropic palette + 舊變數 alias**（讓 `component-library.md` 內舊 snippet 仍能直接用）：

```css
:root {
  /* ── 暖色底 / 深近黑 ──────────── */
  --ivory:  #FAF9F5;   /* 頁面底色（不用純白）*/
  --paper:  #FFFFFF;   /* 卡片底色 */
  --slate:  #141413;   /* 主要文字 / 標題 */

  /* ── Anthropic 招牌色 ──────────── */
  --clay:   #D97757;   /* 主 accent — 連結 / 強調（換字重）/ hover */
  --clay-d: #B85C3E;   /* 深 clay — 主要 CTA */
  --oat:    #E3DACC;   /* 燕麥 — hover bg / 裝飾 */
  --olive:  #788C5D;   /* 橄欖綠 — 次強調 / 成功 / 採納 */

  /* ── Warm gray scale ─────────── */
  --g100:   #F0EEE6;   /* 最淺 — section bg */
  --g200:   #E6E3DA;   /* 卡片次層 */
  --g300:   #D1CFC5;   /* 邊線色（最常用）*/
  --g500:   #87867F;   /* 邊框、分隔、圖示（當小字只有 3.47:1，小字改用 --text-soft）*/

  /* ── 墨色：24px 以下的字只用這組（每個在 ivory／paper／g100／各 *-soft 底上都 ≥ 4.5:1）── */
  --text-soft:  #6C6B65;   /* 弱化文字、metadata、mono 標籤 */
  --clay-ink:   #A64B2E;   /* 赤陶色的小字：連結、區段編號、強調詞、小節 badge */
  --green-ink:  #566B40;   /* 綠色狀態字 */
  --yellow-ink: #7D6019;   /* 黃色警示字 */
  --g700:   #3D3D3A;   /* 內文淺色 */

  /* ── 字體三套 ──────────────────── */
  --serif: "VTDigits", ui-serif, Georgia, "Songti TC", "Noto Serif TC", "Source Han Serif TC", "Times New Roman", serif;  /* VTDigits 見「serif 數字」；中文襯線要點名，否則換台機器就換字 */
  --sans:  system-ui, -apple-system, "Segoe UI", Roboto, "PingFang TC", "Noto Sans TC", Helvetica, Arial, sans-serif;
  --mono:  ui-monospace, "SF Mono", Menlo, Monaco, Consolas, monospace;

  /* ── 兼容舊變數名（讓通用元件 snippet 不需修改）─────── */
  --bg:           var(--ivory);
  --bg-card:      var(--paper);
  --bg-soft:      var(--g100);
  --bg-soft-2:    var(--g200);
  --border:       var(--g300);
  --border-strong:var(--g500);
  --text:         var(--slate);
  --text-muted:   var(--g700);
  --accent:       var(--clay);
  --accent-soft:  #FBE9DF;
  --accent-strong:var(--clay-d);
}
```

## 品牌主題（mrl，預設）

本 skill 預設套「居家先生 CI」。**CI 規則不存在本 skill 裡**：每次 `verify.py` 蓋章時，`scripts/brand.py` 現場去找 `mr-living-presentation` skill、讀它的 `SKILL.md`（色票、字型、版本、Logo 路徑、Logo 留白）與 `references/visual-tokens.md`（色階表），轉成下表的變數值。

```text
verify.py 蓋章
   │
   ├─ 決定主題：--theme > <html data-vt-theme> > HTML_VISUALIZER_THEME > 設定檔 tokens.theme > 預設 mrl
   │
   ├─ 找 skill：HTML_VISUALIZER_BRAND_DIR → ~/.claude/skills → ~/.agents/skills
   │            → ~/.claude/plugins（cache／marketplaces）→ Claude 桌面版 local-agent-mode-sessions/**（取最新）
   │
   ├─ 解析：必要項目缺一個就失敗 ──┐
   │                                ▼
   ├─ 成功 → <head> 寫入變數＋覆寫層＋來源 meta    失敗／找不到 → 整頁原生樣式
   │         插槽填 Logo                            <meta name="vt-theme" content="default" data-reason="…">
   │                                                verify 印「沒找到居家先生 CI，改用原本樣式：…」
   └─ 冪等：重跑會整段換新；切回 default 會整段拿掉（不留半套）
```

**寫進 HTML 的標記只留版本號、不留路徑**（產出會分享出去，本機路徑、`~` 縮寫、session id 都不能出現；verify 會檢查）：

```html
<!-- 居家先生 CI 來源：MR. LIVING CI v0.6 -->
<meta name="vt-theme" content="mrl" data-source="MR. LIVING CI v0.6" data-version="v0.6" data-promo="#C34135">
<!-- 退回原生時 -->
<meta name="vt-theme" content="default" data-reason="找不到 mr-living-presentation">
```

skill 實際在哪個路徑、試過哪些地方，只印在終端機（`brand.py show`、verify 的輸出），方便除錯。

**必要項目**（名稱對值抓，不看行號）：`INK`、`BLUE`、`GREIGE`、`GREIGE_2`（python 色票區塊）、`--brand-bg`、`--brand-light-blue`、`--brand-promo`、`--brand-white`（css 色票區塊）、字型表的「中文」「英文」兩列、三個 Logo 檔（`logo-symbol-on-light.png`、`logo-with-slogan.png`、`typography-c.png`）真的存在。版本號讀 H1 的 `vX.Y`，讀不到標「版本不明」但不算失敗。

**變數怎麼對**（只換值、不換名；推導值都從讀到的色算出來，不寫死色碼）：

| 變數 | 來源 |
|---|---|
| `--ivory` `--bg` | `--brand-bg` |
| `--paper` `--bg-card` | `--brand-white` |
| `--slate` `--text` | `INK` |
| `--clay` `--accent` | `BLUE` |
| `--clay-d` `--accent-strong` | `BLUE` 加深 20%（推導） |
| `--oat` | `--brand-light-blue` |
| `--olive`、新增 `--greige-2` | `GREIGE_2` |
| 新增 `--greige` | `GREIGE`：只當線條與色塊（eyebrow 前的短線等） |
| 新增 `--greige-ink` | 粗體小標的字色（eyebrow、表頭、計數、右上小標）：`GREIGE` 同色相往 `INK` 加深到品牌底色對比 ≥ 4.5（推導；上游 0.3 的小字對比檢查量實際底色） |
| `--g100` / `--g200` / `--g300` | 淺灰 40%／暖灰 20%／暖灰 40%（CI 色階表；表上沒有就跟白混） |
| `--g500` `--text-soft` | `GREIGE` 往 `INK` 加深到品牌底色（`--brand-bg`，比白深）對比 ≥ 4.5（推導；灰褐原色當小字不夠清楚） |
| `--clay-ink` `--green-ink` `--yellow-ink` `--orange-ink` `--blue-ink`；字色 `--green` `--red` `--yellow` | 上游 0.3 的墨色 token：品牌藍與狀態色往 `INK` 加深到底色對比 ≥ 4.5（`--blue-ink` 量淺藍底）（推導） |
| `--g700` `--text-muted` | `GREIGE` 與 `INK` 混 75%（推導） |
| `--clay-soft` `--accent-soft` | 淺藍 20% |
| `--red*`（警示、變差） | **暫代**：從 `--brand-promo` 的色相往紫紅轉 20° 起、字色加深到對比 ≥ 6，直到跟促銷紅差 ΔE ≥ 20（推導）。**不是促銷紅**。見下方「對 CI 的刻意偏離」 |
| `--green*`（好轉）`--yellow*`（注意）`--orange*` | CI 沒有。從 `BLUE` 的飽和度打折、換色相（135°／40°）；淺底 L=94%、字色加深到淺底與白底都 ≥ 4.5（推導，跟著品牌藍變）。`--orange*` 同 `--yellow*` |
| `--sans` `--serif` `--num-font` | CI 英文字型清單**跳過「1 像 I」的字型**（易混字形規則，目前是 Gill Sans）→ 下一順位（Century Gothic → Arial）→ 中文字型。CI 沒有襯線字，標題與內文同一套；`--mono` 不動（程式碼要等寬） |
| `--chart-1`～`--chart-4` | 圖表序列：中性灰褐由深到淺（`GREIGE_2`／`GREIGE` 跟 `INK`、白混出來，推導） |
| `--chart-focus` | 圖表重點那一條／一根：`BLUE`。一張圖只給一個序列 |
| `--purple*` | 原生是第三個裝飾色；mrl 改成中性灰褐（品牌藍不當裝飾色） |
| `--brand-promo` | 促銷紅：只宣告、不指派給任何語意變數 |

另外內嵌 `assets/themes/mrl.css` 覆寫層（只用變數、沒有色碼；測試會擋色碼）。共同原則：無襯線、小標用粗體灰褐（不用等寬字）、細線方正（圓角 ≤ 4px）、品牌藍只給重點。

| 頁型 | 覆寫層管什麼 |
|---|---|
| 捲動式頁面（base-template、explainer、marathon-decision-sheet、spec-alignment，`html:not([data-layout])`）| H1 收斂到 28–36px（範例頁行內寫的字級也收）；編號（`.idx`／`.sec-idx`／`.section-num`）一律數字字型＋品牌藍、不加框；等寬小標（`.eyebrow`、`.stat-label`、`.mock-label`、`.myth .h`、`.tag`…）改粗體灰褐無襯線；卡片圓角 4px、小元件 2px；襯線斜體大數字改數字字型粗體；範例頁寫死的暖色字改吃語意變數；裝飾性的藍點、藍邊條改中性色。**mock 樣張不動**（代表產品畫面） |
| 一頁版（`data-layout="onepage"`）| 版面不動。eyebrow／右欄小標改粗體灰褐、H1 無襯線粗體、主圖框與重點卡方正、重點卡左邊條改墨色（編號保留藍）、頁尾字標 |
| 簡報（`data-layout="slides"`）| 版面不動。小標、圖示、條列編號、完成節點改中性色；藍只留給標題強調、大數字、圖表重點、表格重點列（CI 一張 2–3 處）|

**品牌藍用量軟提醒**：`slides-check.mjs` 在 mrl 頁逐張數「看得到藍的元素」（字、底、邊線、SVG 填色／描邊、`::before` 點；包在已算過的藍元素裡不重算），超過 3 處印 `!`，`verify.py` 標黃燈「品牌藍用量」——**不算未過**。捲動式頁面目前只靠圖表預設中性色＋人工看截圖。

### 對 CI 的刻意偏離（兩項）

1. **不用 Gill Sans 排網頁文字（易混字形規則）**。Gill Sans 的「1」幾乎是一條直線，跟大寫「I」、小寫「l」分不出來：「SAP B1」讀成「SAP BI」、「B1iF」像「BIiF」、章節號「01」像「0I」。我們的內容大量出現料號、系統名、編號，這是可讀性錯誤、不是風格問題。
   - **規則不寫死字型**：`brand.py` 的 `AMBIGUOUS_ONE` 清單（前綴比對，Gill Sans MT／Nova 也算）。解析 CI 字型表時遇到就跳過、往下一順位找（現在是 Century Gothic → Arial；Mac 沒有 Century Gothic 時落到 Arial，兩者的「1」都有明顯旗角）；CI 英文字型全在清單裡時退到中文字型的拉丁字（Noto Sans TC）。CI 換字型時照讀，規則只擋清單裡的字。
   - **為什麼整個跳過、不留給「不含數字的英文標題」**：CSS 沒辦法逐字串判斷有沒有數字，而標題、小標常帶 Q3、2026、B1、01；品牌辨識由官方 Logo PNG（頁首、頁尾、字標）承擔，不靠網頁字型。
   - 連帶解決：之前為了擋 Gill Sans UltraBold 做的 `local()` 字重別名拿掉了（實測簡報「−99%」用的是 GillSans-Bold，不是 UltraBold；粗寬是 Gill Sans Bold 的數字本身＋260px＋負字距造成，換字型後消失）。
   - `verify.py` 在 mrl 頁檢查「作者自己又指定了清單裡的字型」（`<style>`、`style=""`、SVG `font-family`、腳本字串），有就 ✗。
2. **警示色（`--red*`）是推導出來的暫代色**。CI 只有促銷紅 `--brand-promo`，限促銷活動頁；沒有一般用途的紅。舊版用深暖棕代替，結果「注意（黃）」與「警示（紅）」都是棕色、問題標註看起來不像警告。現在由促銷紅推導一個「看得出是警告、又跟促銷紅明顯不同」的深紫紅（色相轉開、加深；ΔE ≥ 20，測試會擋）。**⚠️ 暫代，待設計部門給正式警示色**；給了以後在 CI skill 加一個色票、`brand.py` 改成直接讀。

**踩過的坑（保留）**：

- 灰褐 `#A09C8E` 白底對比只有 2.7:1、品牌底色上 2.2:1 → 原色只當線條色塊；小標字用 `--greige-ink`，一般弱化字用加深過的 `--g500`。簡報章節頁是深底，小標改回原色 `--greige`（深底上加深版反而看不清）。
- 促銷紅 CI 限促銷頁 → 不當警示色。要用就寫在 class 含 `promo` 的元素上；其他地方出現 `verify.py` 判 ✗。
- Logo 四周留白 ≥ 短邊 1/2（SKILL.md 寫 1/2、VI 寫 1/3X，取較嚴）。留白寫成變數，不吃「密度」縮放。
- Gill Sans 的「1」像「I」→ 易混字形規則整個跳過（見上方「對 CI 的刻意偏離」）。也不嵌任何英文字型檔（網頁授權另計），用系統裝的 Century Gothic／Arial。
- 狀態標籤是「淺底＋字色」：三色的字色要彼此 ΔE ≥ 20、在淺底與白底都 ≥ 4.5；只換字色不換淺底時，黃紅兩種標籤會分不出來（舊版踩過）。
- 圖表別整片藍：序列用 `--chart-1`～`--chart-4`（中性灰褐），重點那一條才用 `--chart-focus`。
- Noto Sans TC 由 Google Fonts 載入；離線時退回蘋方／微軟正黑體。
- SVG 圖的顏色寫成 `style="fill: var(--…)"` 才會跟著換主題；寫死 `fill="#…"` 的圖會保留原生配色。

**插槽**（範本已放好，蓋章時填）：`<!-- vt-brand:header -->`（報告頁頁首：符號＋字標＋右上小標）、`<!-- vt-brand:footer -->`（頁尾 Logo＋Slogan）、`<!-- vt-brand:mark -->`（一頁版頁尾、簡報封面右上的字標）。base-template、explainer、marathon-decision-sheet、spec-alignment 都已放好頁首與頁尾插槽。Logo 以 data URI 內嵌，產出單檔可攜。

**品牌頁首一定在 session 色帶下方**：色帶由腳本在執行期插到「第一個 `<header>` 的最前面」（沒有 header 就是 `<body>` 最前面），所以插槽要放在那個 header 裡面（或之後）。捲動式頁面漏了插槽時，蓋章自動補：頁首補在第一個 `<header>` 裡最前面（那個 header 是 sticky／fixed 就補在它後面，Logo 才不會一直佔畫面；沒有 header 才補在 `<body>` 後）；頁尾補在 `</body>` 前。

**怎麼關**：`verify.py <file> --theme=default`、`<html data-vt-theme="default">`、`HTML_VISUALIZER_THEME=default`、`profile.py set tokens.theme=default`（優先序同上圖）。

**測試用環境變數**：`HTML_VISUALIZER_BRAND_DIR=<目錄>` 指定 CI skill；`HTML_VISUALIZER_BRAND_SEARCH=off` 只看指定目錄（模擬「其他地方都找不到」）。

## 配色語意（Anthropic 風）

| 角色 | 顏色 | 用法 |
|---|---|---|
| 頁面底 | `--ivory` | body 背景、不用純白 |
| 卡片底 | `--paper` | 卡片 / 主要區塊 |
| 主要文字 | `--slate` | h1 h2 標題、主要文字 |
| 次要文字 | `--g700` | 內文、副說明 |
| 弱化文字 | `--text-soft` | metadata / mono label / 註腳（`--g500` 只當邊框與圖示） |
| 主 accent | `--clay` | 填色、邊框、圖示、進度線、24px 以上的展示數字 |
| 赤陶小字 | `--clay-ink` | 連結、區段編號、小節 badge、內文強調 |
| 標題強調 | `--clay-d` | h1–h3 的 `em`（大字 4.3:1）、主要按鈕底色（白字 4.53:1） |
| Hover 區塊底 | `--oat` | card thumbnail hover、輕微 emphasis |
| 次 accent | `--olive` | 圖示分色、次強調、成功 |
| 邊線 | `--g300` | 1.5px 細邊（不是 1px、不是 2px）|
| 弱底色 | `--g100` | section 弱化背景 / 卡片次層 |
| 強調底 | `--g200` | thumbnail bg / deep card |

### 狀態 semantic（語意保留、低調用）

預設 Anthropic warm palette 不太使用 cool 綠 / 紅。但有 status 強對比需求時（例：成功 / 失敗 / 警告 chip）：

```css
:root {
  /* 對齊 warm palette、不刺眼 */
  --green:        var(--green-ink);  /* 字色。填色用 --olive */
  --green-soft:   #EFF1E8;
  --green-border: #C8D2B8;

  --red:          var(--clay-ink);   /* 字色 */
  --red-soft:     #FAEBE3;
  --red-border:   #E8C4AF;

  --yellow:       var(--yellow-ink); /* 字色。邊線／圖示用 --yellow-line */
  --yellow-line:  #C49845;
  --yellow-soft:  #F8EFD9;
  --yellow-border: #E8D4A0;

  /* 元件庫 snippet 會用到的延伸組（olive = green 別名、clay-soft = accent-soft 別名） */
  --olive-soft:   #EFF1E8;
  --olive-border: #C8D2B8;
  --clay-soft:    #FBE9DF;
  --orange:       #C9740A;
  --orange-soft:  #FBEEDC;
  --orange-border: #ECCFA3;
}
```

→ Status badge 用這套 token、保持 warm palette 一致性、不破壞 editorial 風格。

## 對比規則（2026-10-27 起，自檢會量）

小字（24px 以下、或 18.66px 以下的粗體）對底色要 ≥ 4.5:1，大字 ≥ 3:1。品牌色本身大多不夠：

| 顏色 | 米白底對比 | 能當小字嗎 | 改用 |
|---|---|---|---|
| `--clay` #D97757 | 2.96 | 不能（連大字的 3:1 都不到） | 小字 `--clay-ink`；標題強調 `--clay-d` |
| `--olive` #788C5D | 3.49 | 不能 | `--green-ink` |
| `#C49845`（黃） | 2.52 | 不能 | `--yellow-ink` |
| `--g500` #87867F | 3.47 | 不能 | `--text-soft` |
| 白字配 `--clay` 底 | 3.12 | 不能 | 按鈕底改 `--clay-d`（4.53） |
| `--text-soft` 配 `--oat` 底 | 3.86 | 不能 | oat 底上只用 `--slate`／`--g700` |

`verify.py` 的版面健檢會逐元素量（「小字對比不足」），有 ✗ 就修。SVG `<text>` 的底色是旁邊的圖形、不是 DOM 祖先，量不準所以不量——SVG 裡的小字自己挑墨色。

**要示範「改前對比不及格」時**（健檢報告、設計審查）：用色塊＋比值數字（例：一個 `#D97757` 色塊旁寫「2.96:1」），或用 24px 以上的大字示範；不要真的排一行不及格的小字——版面健檢分不出示範與正文，一樣會報 ✗，讀者也真的讀不到。

## 字體規則（最重要的差異）

### 標題用 serif，但強調不用斜體

```css
h1, h2, h3 {
  font-family: var(--serif);
  font-weight: 500;       /* 不是 700、Anthropic 風偏細 */
  letter-spacing: -0.012em;
  color: var(--slate);
}

h1 {
  font-size: clamp(38px, 5.4vw, 62px);  /* 響應式大標 */
  line-height: 1.06;
  letter-spacing: -0.018em;
}

h2 {
  font-size: 27px;
  letter-spacing: -0.012em;
}

h3 {
  font-size: 19px;
  letter-spacing: -0.008em;
}

/* B · 換字重（預設強調手法） */
h1 em, h2 em, h3 em {
  font-style: normal;
  font-weight: 700;
  color: var(--clay-d);   /* --clay 在米白底 2.96:1，連大字 3:1 都不到 */
}

/* C · 螢光筆（語氣更重、一頁最多一兩次） */
.hl {
  background: linear-gradient(transparent 58%, #f7d9a0 58%);
  font-style: normal;
}

/* E · 保險絲（全域、擋掉所有合成字形） */
body { font-synthesis: none; }
```

```html
<h1>造工廠，還是寫<em>配方</em>？</h1>
<h1>能用，但大半<span class="hl">不該</span>從這裡拿</h1>
```

🔴 **中文沒有斜體**（2026-09-20 定案：B＋C＋E 三招並用）。漢字字形沒有義大利體傳統，
瀏覽器遇到 `font-style: italic` 只能機械傾斜漢字，筆畫變形。本規範原本寫「serif +
italic 強調」、範本也內建 `h1 em { font-style: italic }`——**實測當月 38／45 份產出的
主標題都在犯這個**，因為範本的示範文字就是這樣寫的。

**強調手段對照表**（中文替代西文的 italic；參考 huashu-design 的排印分冊）：

| 西文慣例 | 中文替代 | 怎麼寫 | 什麼時候用 |
|---|---|---|---|
| italic 強調 | **換字重**（預設） | `font-weight: 700` ＋ `--clay-d` 色 | 多數情況。安靜、不打斷閱讀 |
| italic 書名／引用 | **螢光筆底色** | `.hl` 的線性漸層 | 語氣要重、想讓人停一下。一頁最多一兩次 |
| italic 專名 | **著重號** | `text-emphasis: dot; text-emphasis-position: under` | 中文原生手法、最雅緻，但小字級幾乎看不見 |
| —（防呆） | **保險絲** | `body { font-synthesis: none }` | 一律加。寫錯了也不會變形，自動退回正體 |

⚠️ **保險絲的副作用：內文的 `<em>` 會失去強調**（2026-09-21 實測）。瀏覽器預設讓 `em` 斜體，保險絲擋掉合成斜體後，中文 em 會跟正文**一模一樣**——不再歪，但也看不出來了。所以範本另加 `em { font-weight: 600 }`：中文靠字重被看見，英文仍用真的義大利體（字重加上去也不衝突）。只改標題 em 不改內文 em，等於把「歪但看得到」換成「正但看不到」。

⚠️ **混字體強調是外行**（taste-skill §4.1）：要強調標題裡的字，用**同一個字體**的
字重或斜體，不要在無襯線標題裡插一個襯線字（或反過來）。本規範的 B 就是同字體換字重。

> Serif 當預設字體在別的情境是有爭議的——taste-skill 把它列為「最常被測出來的 AI
> 破綻」。但它自己列的兩個例外（品牌明訂 serif、定位真的是 editorial）**本規範兩條都
> 符合**：serif 來自 Anthropic 官方品牌，產出定位就是 editorial。所以 serif 留著，
> 只拿掉斜體。

### 排印細節（白拿的品質）

```css
/* 段落尾行不要留孤字；標題不要斷得難看 */
p, li, td { text-wrap: pretty; }
h1, h2, h3 { text-wrap: balance; }
```

`text-wrap` 現代瀏覽器都支援，成本為零、效果直接（參考 huashu-design：「白拿的排印
品質」）。本庫原本 0 處使用。`pretty` 避免段落最後一行只剩一兩個字，`balance` 讓多行
標題的每一行長度接近。

**中文標題斷行**（2026-10-26 加）：`balance` 只負責讓各行等長，不懂中文的詞；中文標題
自己會在任兩個字之間斷，常把一個詞切成兩行（「三個答／案」）。另加：

```css
h1, h2, h3 { word-break: keep-all; overflow-wrap: anywhere; }
.ph { display: inline-block; }   /* 語意片段：片段內不斷行 */
```

```html
<h1><span class="ph">為什麼登入</span><span class="ph">要發兩張憑證</span></h1>
```

`keep-all` 讓中文只在標點與空白處換行；沒有標點的長標題會整串擠在一起，這時用 `.ph`
把它切成兩三個語意片段，瀏覽器只會在片段之間換行。`overflow-wrap: anywhere` 是退路：
整串沒有斷點、又寬過容器時才硬斷，不會撐破版面。不要靠 `text-wrap: balance` 切中文。
自檢會量「標題有一行只剩一個字」（2026-10-27 起）。
什麼時候切（2026-10-27 派工端裁定）：**超過 12 個中文字的 h1／h2 才切；h3 不切**——h3 字小、斷在哪都讀得懂，切了反而在窄欄裡留孤字。

強調詞兩側不要加半形空格：寫「從<em>常常空白</em>修到」，不是「從 <em>常常空白</em> 修到」。

### serif 數字（等高數字，2026-10-26 加）

Georgia 的數字是**舊式字形**（0 和小寫 o 一樣高、3 4 5 7 9 往下掉），而 macOS 的 Chrome
不認 `ui-serif`，標題實際用的就是 Georgia。Georgia 也**不吃** `font-variant-numeric:
lining-nums`（2026-10-26 實測截圖：加了照樣是舊式）。做法兩件一起：

```css
/* 1. 只含數字（與 , - . / :）的字族，排在 --serif 最前面：數字改用 Times 的等高字形，漢字與字母照舊 */
@font-face { font-family: "VTDigits"; src: local("Times New Roman"), local("Times"); unicode-range: U+0030-0039, U+002C-002F, U+003A; }
:root { --serif: "VTDigits", ui-serif, Georgia, "Songti TC", "Noto Serif TC", "Source Han Serif TC", "Times New Roman", serif; }

/* 2. 標題與大數字要等高、等寬；設定檔換掉 --serif（VTDigits 跟著不見）時，支援 lnum 的字型靠這行 */
h1, h2, h3, .stat-value { font-variant-numeric: lining-nums tabular-nums; }
```

`base-template.html` 與五份範例
都已內建；自己做大數字元件時，把那個 class 加進第 2 條。

### 內文用 system sans

```css
body {
  font-family: var(--sans);
  font-size: 16.5px;       /* 內文略大、editorial 感 */
  line-height: 1.55;
  color: var(--slate);
}

.intro {
  font-size: 16.5px;
  color: var(--g700);
  max-width: 620px;
}

.desc, .body-text {
  font-size: 13.5px;
  color: var(--g700);
  line-height: 1.5;
}
```

### Eyebrow / metadata / file path 用 mono uppercase

```css
.eyebrow {
  font-family: var(--mono);
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-soft);
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 前面加一條 clay 短線裝飾 */
.eyebrow::before {
  content: "";
  width: 24px;
  height: 1.5px;
  background: var(--clay);
}
```

```html
<div class="eyebrow">— Companion to the blog post</div>
```

→ Eyebrow 是 Anthropic 風的 signature 元素、給 section / hero 一個 mono uppercase 的 metadata header。

### Mono 用法

| 用法 | 範例 |
|---|---|
| Eyebrow / 副標 | `Companion to the blog post` |
| Section index 編號 | `01 · 章名`（mono 12px `--clay-ink`，前面一條 clay 短線；見 base-template `.sec-head .idx`）|
| File path / 檔名 | `01-exploration-code-approaches.html` |
| Pill count | `3 項`（sans 12.5px `--g700`、`white-space: nowrap`；中文不用 mono，也不低於 12px）|
| Code inline | `<code>.html</code>` |

## 字體大小階層（Anthropic 風）

| 層級 | size | family | weight | 用途 |
|---|---|---|---|---|
| Hero | 36-64px clamp | serif | 500 | 主標題 |
| Section | 26-36px clamp | serif | 500 | 區段標 |
| Card | 19-20px | serif | 500 | 卡片標 |
| Lead | 16.5-19px clamp | sans | 400 | hero 一句話 |
| Body | 14.5-16px | sans | 400 | 內文 |
| Card desc | 13.5px | sans | 400 | 卡內次要文字 |
| Eyebrow | 12px | mono | 600 | metadata（`--text-soft`）|
| Index | 12px | mono | 600 | section 編號（`--clay-ink`）|
| Pill | 12.5px | sans | 400 | TOC pill |
| File path | 12px | mono | 400 | 檔名 / 註腳（中文字下限 12px；純數字或英文 mono 可 11px）|

## 邊線 / 圓角 / 陰影（Anthropic 風）

```css
/* 邊線：1.5px、不是 1px、不是 2px */
.card     { border: 1.5px solid var(--g300); border-radius: 14px; }
.thumb    { border-bottom: 1.5px solid var(--g200); }
.toc-pill { border: 1.5px solid var(--g300); border-radius: 999px; }
header.masthead { border-bottom: 1.5px solid var(--g300); }

/* Hover 邊框變深近黑 */
.card:hover { border-color: var(--slate); }

/* Hover 淡陰影（暖色調）。不再浮起位移：可點的卡才需要 hover，位移讓讀者分心又不給新資訊 */
a.link-card:hover {
  box-shadow: 0 10px 30px rgba(20, 20, 19, 0.10);
}

/* hero 卡片陰影更深 */
.hero-fig .pane.html {
  box-shadow: 0 12px 32px rgba(20, 20, 19, 0.10);
}
```

## 間距系統

```
主容器寬度：min(94vw, 1760px)  ← 寬版、吃滿寬螢幕不浪費兩側留白（取代舊 1400px）
長段落護欄：max-width: 72ch     ← 文字塊限行長、寬螢幕下避免一行上百字難讀（grid/卡片/表格不受限）
頁面 padding：32px    ← 兩側（桌機）
手機 padding：16px    ← ≤640px；32px 在 390px 螢幕上吃掉 16% 寬度，卡片內距同時收到 18px
                        （手機版型邊界盡量少。範本已內建 640px 斷點）
Hero 上下 padding：clamp(40px, 6vw, 88px) / clamp(32px, 4vw, 56px)
Section 上 padding：clamp(56px, 7vw, 96px)  ← 章節之間的呼吸；再大讀者會以為頁面結束了
Section intro：不縮排（舊版左縮 50px 對齊編號，手機上標題反而比內文縮得多，2026-10-27 拿掉）
卡片 padding：22-24px
卡片 grid：repeat(auto-fit, minmax(min(100%, 280px), 1fr))，gap 16px
TOC pill gap：8px
```

## 為什麼這套 token

- **暖色不刺眼**：`#FAF9F5` ivory 比純白柔和、長閱讀不疲勞
- **clay 是 Anthropic 招牌**：對齊官方品牌、立刻識別「這是 Claude 做的」
- **Serif 標題**：editorial / book / magazine 質感、提升閱讀儀式感（強調改用字重或螢光筆，中文沒有斜體）
- **三字體分工**：serif（標題權威）/ sans（內文可讀）/ mono（metadata 機器感）— 角色清楚不混
- **Warm gray**：g100-g700 是暖灰、跟 ivory 同色系、不會出現「黑白藍」科技感
- **1.5px 邊線**：比 1px 厚實、比 2px 不刺、editorial 風的 detail
- **語意色 = warm 對齊**：成功用 olive 不用 emerald、失敗用 clay-d 不用 ruby、整體調性一致

## 風格對照（vs 純功能 / 科技風）

| 維度 | Anthropic 風（推薦）| 純功能風（過去版本）|
|---|---|---|
| 底色 | `#FAF9F5` ivory | `#fafafa` 冷白 |
| 主 accent | `#D97757` clay 赤陶 | `#2563eb` cool 藍 |
| 標題字體 | serif（Georgia）| sans only |
| 標題強調 | h1 em 換字重 ＋ `--clay-d` 色（不用斜體）| 不用 |
| Eyebrow | mono uppercase + clay 短線 | 不用 |
| Section 編號 | eyebrow「01 · 章名」；小節用方框 badge | 圈號 ②③ 或字母 ABC |
| 卡片邊 | 1.5px g300 | 1px 冷灰 |
| 灰階 | warm gray | cool gray |
| Hover | 可點的卡淡陰影 ＋ 邊框變深 | border 變深 |
| 整體 | editorial / book | dashboard / functional |

→ **預設用 Anthropic 風**。除非使用者明確要「dashboard / 工程儀表板」風格、再用純功能風。
