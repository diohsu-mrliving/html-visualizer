# CLAUDE.md — html-visualizer repo 規範

三個 skill（`skills/html-visualizer`、`skills/chart`、`skills/diagram-design`）同時發布到兩種環境，限制以較嚴的那邊為準。

## claude.ai / Cowork 上傳限制（動 skill 前先看這段）

claude.ai 網頁版與 Claude Cowork 不讀本機檔案系統，skill 要打包成 zip 從帳號設定上傳，上傳器有驗證。Claude Code 直接讀 `SKILL.md`、沒有驗證，所以在 Claude Code 測得過不代表上傳得過。2026-09-11 兩條各撞一次，使用者回報才知道：

| 限制 | 值 | 出處 |
|---|---|---|
| frontmatter `description` 長度 | ≤ 200 字元（Unicode 字元數） | 說明中心「How to create custom skills」；Agent Skills 規格寫 1024，上傳器用較嚴的 |
| 一個 zip 的檔案數 | ≤ 200（目錄項目也算） | 文件沒寫；上傳錯誤訊息 `Zip contains too many files (maximum 200)` |
| `name` | 小寫、數字、連字號；與資料夾同名 | 官方文件 |
| zip 結構 | skill 資料夾本身是 zip 根目錄，一個 skill 一個 zip | 說明中心 |

目前用量（2026-09-24 v0.2.0）：diagram-design **167 檔**、html-visualizer 31、chart 4。**diagram-design 離上限只剩 33 個檔**，往 `assets/` 或 `references/` 加東西前先算；要加超過就得先砍（已砍過 47 個 `example-*-dark.html`，下一刀候選是 `example-*-full.html`）。

**每次改 `skills/**` 後、commit 前跑：**

```
python3 tests/check-frontmatter.py
```

超過任一限制它會紅。沒有 CI 或 hook 兜底，靠這一行。

## 發版

本 repo 是 GitHub fork（上游 `chenjackle45/html-visualizer`，remote 名 `upstream`），版本分兩種，tag 不可混用：

**上游版本（`vX.Y.Z`）**——不自己打，從上游抓：

```
git fetch upstream --tags
git merge --ff-only upstream/main
git push origin main vX.Y.Z
```

自己 `git tag -a` 建的同名 tag 跟上游的 tag object 不同，之後 fetch 上游會撞名被拒，所以上游版號一律直接用上游的 tag。

**我們自己的版本（`vX.Y.Z-mrl.N`）**——在上游 `X.Y.Z` 之上加我們的改動時：

1. 改 `.claude-plugin/plugin.json` 的 `version` 為 `X.Y.Z-mrl.N`（只有這一檔帶版本號；`X.Y.Z` 是目前基底的上游版本，`N` 從 1 起跳，換上游基底就歸 1）
2. commit `chore: bump plugin version to X.Y.Z-mrl.N`
3. `git tag -a vX.Y.Z-mrl.N -m "..."`，push commit 與 tag

合上游新版時 `plugin.json` 的 `version` 會撞，改成新的上游版號（或其上的 `-mrl.1`）。

Claude Code plugin 使用者靠 tag 拿更新；claude.ai / Cowork 使用者要重新 clone、依 README「claude.ai / Cowork」段打包上傳。

## 其他

- `skills/diagram-design` 是 cathrynlavery/diagram-design v2.6 的 fork，與上游的差異列在該 `SKILL.md` 頂部註解；改上游內容時同步更新那段。
- 本機 `~/.claude/skills/` 的三份是作者個人版，含專案專用註記，不等於本 repo；改公開版不要順手動它。
