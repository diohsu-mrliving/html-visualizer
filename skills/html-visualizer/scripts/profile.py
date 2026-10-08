#!/usr/bin/env python3
"""
使用者設定檔 — 描述這個人要的頁面長相，verify.py 蓋章時套用。

設定檔只記「使用者明確選過的」項目。沒寫的鍵＝沿用範本原值，蓋章不碰。
理由：五份範本的配色與字型本來就不完全相同（spec-alignment 是另一組暖色），
把完整預設值蓋到每一頁，等於把沒人要求的改動強加上去。

位置：~/.config/html-visualizer/profile.json，環境變數 HTML_VISUALIZER_PROFILE 可覆寫。
這支工具給 AI 用，不是給使用者打的：使用者在頁面上調好、複製摘要貼回對話，
摘要裡的「設定檔變更」段落就是一行本工具的 set 指令。

用法：
  python3 profile.py show            人看的摘要
  python3 profile.py show --json     整份 JSON
  python3 profile.py show --rules    只印文字規則（生成頁面前讀）
  python3 profile.py set 鍵=值 ...    寫入；缺檔自動建立，寫完印出前後差異
"""
import json
import os
import sys

PROFILE_PATH = os.environ.get(
    "HTML_VISUALIZER_PROFILE",
    os.path.join(os.path.expanduser("~"), ".config", "html-visualizer", "profile.json"),
)

# 設定檔鍵 → 頁面上的 CSS 變數。同一個語意在不同範本叫法不同，全部一起蓋
COLOR_VARS = {
    "bg": ["--ivory", "--bg"],
    "surface": ["--paper", "--bg-card"],
    "text": ["--slate", "--ink", "--text"],
    "textMuted": ["--g700", "--text-muted"],
    "textSoft": ["--g500", "--text-soft"],
    "border": ["--g300", "--border", "--line"],
    "accent": ["--clay", "--accent"],
    "accentStrong": ["--clay-d", "--accent-strong"],
    "accentSoft": ["--clay-soft", "--accent-soft"],
    "secondary": ["--olive"],
}
FONT_VARS = {"body": "--sans", "heading": "--serif", "mono": "--mono"}
DENSITY = {"compact": 0.75, "standard": 1, "relaxed": 1.3}

# set 接受的鍵與型別；其他鍵一律拒絕（打錯字不會默默寫進去）
SCHEMA = {
    "tokens.type.scale": float,
    "tokens.layout.density": str,
    "tokens.layout.maxWidth": int,
    "checks.noEmoji": bool,
    "checkWidths": list,
    "tokens.theme": str,  # mrl（預設，現場讀居家先生 CI）/ default（原本樣式）；見 brand.py
}
THEMES = ("mrl", "default")
for k in FONT_VARS:
    SCHEMA[f"tokens.type.{k}"] = str
for k in COLOR_VARS:
    SCHEMA[f"tokens.color.{k}"] = str

# checkWidths 不放預設：只在使用者明確選過時才寫進檔案，沒寫就由 verify 用 390／768／1440
EMPTY = {"version": 1, "tokens": {}, "checks": {"noEmoji": False}, "rules": []}


def load():
    """讀設定檔；不存在就回傳空白設定（不報錯、不建檔）。"""
    if not os.path.exists(PROFILE_PATH):
        return json.loads(json.dumps(EMPTY)), False
    with open(PROFILE_PATH, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except ValueError as e:  # 手改 rules 時最容易寫壞（少逗號、多逗號）
            raise ValueError(f"設定檔 JSON 壞了（{PROFILE_PATH}）：{e}") from None
    merged = json.loads(json.dumps(EMPTY))
    merged.update(data)
    return merged, True


def save(profile):
    os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
    tmp = PROFILE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, PROFILE_PATH)


def _get(d, dotted):
    for part in dotted.split("."):
        if not isinstance(d, dict) or part not in d:
            return None
        d = d[part]
    return d


def _put(d, dotted, value):
    parts = dotted.split(".")
    for part in parts[:-1]:
        d = d.setdefault(part, {})
    d[parts[-1]] = value


def _coerce(key, raw):
    typ = SCHEMA[key]
    if typ is list:
        widths = [int(x) for x in raw.split(",") if x.strip()]
        if not widths or any(w < 280 or w > 3000 for w in widths):
            raise ValueError(f"{key} 要逗號分隔的寬度（280～3000），收到 {raw}")
        return widths
    if typ is bool:
        if raw.lower() in ("true", "1", "yes", "on"):
            return True
        if raw.lower() in ("false", "0", "no", "off"):
            return False
        raise ValueError(f"{key} 要 true/false，收到 {raw}")
    if key == "tokens.theme" and raw not in THEMES:
        raise ValueError(f"{key} 只能是 {'/'.join(THEMES)}，收到 {raw}")
    if key == "tokens.layout.density" and raw not in DENSITY:
        raise ValueError(f"{key} 只能是 {'/'.join(DENSITY)}，收到 {raw}")
    if key == "tokens.type.scale":
        v = float(raw)
        if not 0.9 <= v <= 2:  # 跟「風格設定」的滑桿範圍一致
            raise ValueError(f"{key} 要在 0.9～2 之間，收到 {raw}")
        return v
    return typ(raw)


def css_vars(profile):
    """設定檔 → :root 變數宣告（只含使用者選過的）。只寫變數、不寫元素規則：
    Tailwind CDN 的樣式在執行期排在頁面最後，元素規則同權重會輸給它。"""
    t = profile.get("tokens") or {}
    out = []
    for k, var in FONT_VARS.items():
        v = _get(t, f"type.{k}")
        if v:
            out.append(f"{var}: {v};")
    scale = _get(t, "type.scale")
    if scale is not None:
        out.append(f"--fs: {scale};")
    for k, vars_ in COLOR_VARS.items():
        v = _get(t, f"color.{k}")
        if v:
            out += [f"{var}: {v};" for var in vars_]
    mw = _get(t, "layout.maxWidth")
    if mw:
        out.append(f"--wrap-max: {int(mw)}px;")
    dens = _get(t, "layout.density")
    if dens in DENSITY:
        out.append(f"--dens: {DENSITY[dens]};")
    return out


def cmd_show(args):
    try:
        profile, exists = load()
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    if "--json" in args:
        print(json.dumps(profile, ensure_ascii=False, indent=2))
        return 0
    if "--rules" in args:
        rules = profile.get("rules") or []
        if not rules:
            print("（設定檔沒有文字規則）")
        for r in rules:
            print(f"- {r}")
        return 0
    print(f"設定檔：{PROFILE_PATH}" + ("" if exists else "（不存在，全部沿用範本原值）"))
    decls = css_vars(profile)
    print("蓋章會寫入的變數：" + (" ".join(decls) if decls else "（無，沿用範本原值）"))
    print(f"品牌主題：{_get(profile, 'tokens.theme') or '未設定（預設 mrl，brand.py show 看這次會不會套上）'}")
    print(f"版面檢查寬度：{profile.get('checkWidths') or '未設定（用 390／768／1440）'}")
    print(f"不用 emoji：{'是' if (profile.get('checks') or {}).get('noEmoji') else '否'}")
    print(f"文字規則：{len(profile.get('rules') or [])} 條（show --rules 看全文）")
    return 0


def cmd_set(args):
    if not args:
        print("用法：profile.py set 鍵=值 ...", file=sys.stderr)
        return 64
    try:
        profile, _ = load()
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    changes = []
    for a in args:
        if "=" not in a:
            print(f"✗ 看不懂 {a}（要 鍵=值）", file=sys.stderr)
            return 64
        key, raw = a.split("=", 1)
        if key not in SCHEMA:
            print(f"✗ 不認得的鍵 {key}。可用：{', '.join(sorted(SCHEMA))}", file=sys.stderr)
            return 64
        try:
            value = _coerce(key, raw)
        except ValueError as e:
            print(f"✗ {e}", file=sys.stderr)
            return 64
        before = _get(profile, key)
        _put(profile, key, value)
        changes.append((key, before, value))
    save(profile)
    print(f"已寫入 {PROFILE_PATH}")
    for key, before, after in changes:
        print(f"  {key}：{'（未設定）' if before is None else before} → {after}")
    return 0


def main(argv):
    if not argv or argv[0] not in ("show", "set"):
        print(__doc__.strip())
        return 64
    return {"show": cmd_show, "set": cmd_set}[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
