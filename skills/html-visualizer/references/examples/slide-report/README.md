# slide-report：真實的 12 張簡報

「個人知識庫｜Ingest・Lint・Query 的完整生命週期」報告，是簡報模式的視覺來源：`assets/slides-template.html` 的主題 token、卡片、eyebrow＋badge、callout、頁尾都取自這份。

## 什麼時候看它

- 要做資訊比較密的簡報（每張有圖＋卡片＋callout），想看真實內容怎麼排
- 要換成這套 ChatGPT 風以外的主題前，先看元件在真內容上長怎樣
- 要用範本沒有的元件：hub（來源 → 中心 → 問題）、三層分工、可信度履歷、議程卡、目錄樹、示意對話

## 結構

和範本同一個引擎與主題（直接比對兩份的 `<style>` 前半段與 `<script>`）。每張標了版型：

| 張 | 版型 | 主要元件 |
|---|---|---|
| 1 | flow | hub＋三張卡 |
| 2、8 | flow | SVG 流程圖（`.flow-wrap`） |
| 3、7 | compare | 兩欄卡片（目錄樹／孤兒頁兩種情況） |
| 4、5、6、9、10、11 | bullets | 三問卡、三層、檢查列、履歷欄位 |
| 12 | closing | 議程卡（待決事項） |

範例專屬元件的 CSS 在 `<style>` 裡「以下是 slide-report 自己的元件」那段，數值是原本 1440 寬版本的 px × 1.4。這份內容較密，上下留白比範本少一點（同一段開頭）。

## 怎麼驗

```bash
python3 <skill>/scripts/verify.py references/examples/slide-report/index.html
```

「簡報」那段每張一行、附 1920×1080 截圖。
