#!/usr/bin/env python3
"""
品牌主題（mrl）— 每次蓋章時「現場」去找居家先生 CI skill（mr-living-presentation），
讀出色票、字型、版本與 Logo，轉成本 skill 既有的 CSS 變數值。

為什麼不寫死：CI 由另一個 skill 維護，它升版（例如品牌藍換值）時，這裡要自動跟上；
寫死一份等於多一份會過期的副本。

全有或全無：找不到 skill、或必要項目缺任何一個，整頁退回原生樣式並印出原因。
不會出現「一部分 CI、一部分原生」的半套頁面。

主題怎麼決定（先到先贏）：
  1. 指令參數 --theme=mrl|default（verify.py、stamp.py、本工具都吃）
  2. 頁面 <html data-vt-theme="default|mrl">
  3. 環境變數 HTML_VISUALIZER_THEME
  4. 設定檔 tokens.theme（profile.py set tokens.theme=default）
  5. 預設 mrl

找 skill 的順序（第一個「有 SKILL.md」的目錄就用；同一層有多個取 SKILL.md 最新的）：
  1. 環境變數 HTML_VISUALIZER_BRAND_DIR（手動指定）
  2. ~/.claude/skills/mr-living-presentation、~/.agents/skills/mr-living-presentation
  3. ~/.claude/plugins/ 底下的 cache／marketplaces 安裝位置
  4. ~/Library/Application Support/Claude/local-agent-mode-sessions/<uuid>/<uuid>/rpm/plugin_*/skills/mr-living-presentation
  逐層惰性搜尋：前一層找到就停，不會為了後面幾層去掃整個 session 資料夾。
  測試用：HTML_VISUALIZER_BRAND_SEARCH=off 只看第 1 項（模擬「其他地方都找不到」）。

用法：
  python3 brand.py show [--json] [--theme=mrl|default]   這次蓋章會用哪個主題、為什麼
"""
import base64
import colorsys
import glob
import json
import math
import os
import re
import sys
from html.parser import HTMLParser

SKILL_NAME = "mr-living-presentation"
THEMES = ("mrl", "default")
HERE = os.path.dirname(os.path.abspath(__file__))
OVERLAY_CSS = os.path.join(os.path.dirname(HERE), "assets", "themes", "mrl.css")

# 必要的 CI 項目：名稱 → 在 SKILL.md 哪一種寫法裡找。缺任何一個＝解析失敗
REQUIRED_PY = ("INK", "BLUE", "GREIGE", "GREIGE_2")            # 色票 python 區塊：NAME = "1A1A1A"
REQUIRED_CSS = ("--brand-bg", "--brand-light-blue", "--brand-promo", "--brand-white")  # 色票 css 區塊
LOGOS = {  # 用途 → 檔名（路徑從 SKILL.md 讀，檔案要真的存在）
    "symbol": "logo-symbol-on-light.png",
    "slogan": "logo-with-slogan.png",
    "wordmark": "typography-c.png",
}
# 中文字型名 → CSS 用的系統名稱（CI 表格寫中文俗名）
FONT_ALIAS = {"微軟正黑體": "Microsoft JhengHei", "蘋方": "PingFang TC", "思源黑體": "Noto Sans TC"}
# 易混字形規則：數字「1」跟大寫「I」／小寫「l」幾乎一樣的字型（「SAP B1」讀成「SAP BI」、「01」像「0I」）。
# 這些字型不排任何網頁文字——CI 字型清單裡遇到就跳過、往下一順位找。刻意偏離 CI，理由見
# references/color-and-typography.md § 品牌主題「對 CI 的刻意偏離」。前綴比對：Gill Sans MT／Nova 也算。
AMBIGUOUS_ONE = ("Gill Sans",)


def ambiguous_one(name):
    """這個字型的「1」會不會被看成「I」。"""
    n = name.strip().strip("\"'").lower()
    return any(n.startswith(a.lower()) for a in AMBIGUOUS_ONE)


class BrandError(Exception):
    pass


# ── 1. 找 skill ─────────────────────────────────────────────
def _home(*p):
    return os.path.join(os.path.expanduser("~"), *p)


def _newest(paths):
    ok = [p for p in paths if os.path.isfile(os.path.join(p, "SKILL.md"))]
    return max(ok, key=lambda p: os.path.getmtime(os.path.join(p, "SKILL.md"))) if ok else None


# 桌面版 session 的實際結構：.../local-agent-mode-sessions/<uuid>/<uuid>/rpm/plugin_*/skills/<skill>。
# 用固定深度的 glob，不用 ** 遞迴（session 資料夾動輒數千個檔，遞迴每次蓋章都要掃一遍）
SESSION_PATS = (f"*/*/rpm/plugin_*/skills/{SKILL_NAME}",)
PLUGIN_PATS = (
    f"cache/*/{SKILL_NAME}/*/skills/{SKILL_NAME}",
    f"cache/*/*/*/skills/{SKILL_NAME}",
    f"marketplaces/*/plugins/*/skills/{SKILL_NAME}",
    f"marketplaces/*/skills/{SKILL_NAME}",
)


def _globs(base, pats):
    return lambda: sorted({p for pat in pats for p in glob.glob(os.path.join(glob.escape(base), pat))})


def search_tiers():
    """逐層產生 (說明, 取候選目錄的函式)。惰性：前一層找到就不會再跑後面的 glob。"""
    env = os.environ.get("HTML_VISUALIZER_BRAND_DIR")
    if env:
        yield "環境變數 HTML_VISUALIZER_BRAND_DIR", (lambda: [os.path.expanduser(env)])
    if os.environ.get("HTML_VISUALIZER_BRAND_SEARCH", "").lower() in ("off", "0", "no", "false"):
        return
    yield "~/.claude/skills", (lambda: [_home(".claude", "skills", SKILL_NAME)])
    yield "~/.agents/skills", (lambda: [_home(".agents", "skills", SKILL_NAME)])
    yield "~/.claude/plugins", _globs(_home(".claude", "plugins"), PLUGIN_PATS)
    yield ("Claude 桌面版 local-agent-mode-sessions",
           _globs(_home("Library", "Application Support", "Claude", "local-agent-mode-sessions"), SESSION_PATS))


def find_skill():
    """回傳 (目錄 或 None, 試過的說明清單)。"""
    tried = []
    for label, get in search_tiers():
        cands = get()
        hit = _newest(cands)
        if hit:
            return hit, tried
        exists = [c for c in cands if os.path.isdir(c)]
        tried.append(f"{label}（{'目錄不存在' if not exists else '有目錄但沒有 SKILL.md'}）")
    return None, tried


# ── 2. 解析 ─────────────────────────────────────────────────
_HEX = r"#?([0-9A-Fa-f]{6})\b"


def _hex(v):
    return "#" + v.upper()


def _read(path):
    """檔案不存在回 ""；存在但讀不了（權限、非 UTF-8）一律轉 BrandError → 整頁退回原生。"""
    if not os.path.exists(path):
        return ""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError) as e:
        raise BrandError(f"{os.path.basename(path)} 讀不了（{type(e).__name__}）") from e


# 寫進產出 HTML 的值一律先過白名單：CI 檔是別的 skill 維護的 Markdown，不能信任它的內容
_SAFE_HEX = re.compile(r"#[0-9A-F]{6}")
_SAFE_FONT = re.compile(r"[^\W_][\w .\-]{0,63}")  # 字母／數字／CJK 開頭，只含字母數字、空白、. - _
_SAFE_VERSION = re.compile(r"v\d{1,4}(?:\.\d{1,4}){1,3}")
_SAFE_TOKEN = re.compile(r"[#\w\s,.()%\"-]+")  # 組好的 CSS 值：不准 < > ; { } \ 等能跳出宣告的字元
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
LOGO_MAX_BYTES = 2 * 1024 * 1024


def _check_font(name):
    if not _SAFE_FONT.fullmatch(name):
        raise BrandError(f"字型名稱含不允許的字元：{name[:40]!r}")
    return name


def css_str(s):
    """CSS 字串跳脫（字型名已過白名單，這裡是第二道保險）。"""
    return '"' + re.sub(r'(["\\])', r"\\\1", s).replace("\n", " ") + '"'


def _tint_table(md):
    """visual-tokens.md 的色階表：{基準 hex: {100: hex, 80: …, 20: …}}。表頭要有 100% … 20%。"""
    out = {}
    header = None
    for line in md.splitlines():
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        pcts = [re.fullmatch(r"(\d+)%", c) for c in cells[1:]]
        if all(pcts):
            header = [int(m.group(1)) for m in pcts]
            continue
        if header and len(cells) - 1 == len(header):
            vals = [re.fullmatch(_HEX, c) for c in cells[1:]]
            if all(vals):
                row = {p: _hex(v.group(1)) for p, v in zip(header, vals)}
                if 100 in row:
                    out[row[100]] = row
        elif not line.strip().startswith("|"):
            header = None
    return out


def _fonts(md):
    """§字型規範表：| 中文 | 主字型（說明） | 後備 → 後備 | 與 | 英文／數字 | A → B → C | … |。"""
    def row(label):
        m = re.search(r"^\|\s*" + label + r"[^|]*\|([^|]+)\|([^|]*)\|", md, re.M)
        if not m:
            return None
        names = []
        for cell in (m.group(1), m.group(2)):
            cell = cell.strip()
            if cell.startswith(("（", "(")):
                continue  # 「（三層 fallback）」這類說明
            for part in re.split(r"\s*→\s*", cell):
                part = re.sub(r"[（(].*?[）)]", "", part).strip()
                if part:
                    names.append(_check_font(FONT_ALIAS.get(part, part)))
        return names or None

    zh, en = row("中文"), row("英文")
    if not zh or not en:
        raise BrandError("字型規範表缺「中文」或「英文」那一列")
    skipped = [n for n in en if ambiguous_one(n)]
    usable = [n for n in en if not ambiguous_one(n)] or [n for n in zh if not ambiguous_one(n)]
    seen, stack = set(), []
    for n in usable + zh:
        if n not in seen and not ambiguous_one(n):
            seen.add(n)
            stack.append(n)
    return {"ci_en": en, "en": usable, "stack": stack, "skipped": skipped}


def parse(skill_dir):
    """讀 SKILL.md（＋ references/visual-tokens.md）→ CI dict。缺必要項目丟 BrandError。"""
    md = _read(os.path.join(skill_dir, "SKILL.md"))
    if not md:
        raise BrandError("SKILL.md 讀不到")
    vt = _read(os.path.join(skill_dir, "references", "visual-tokens.md"))

    colors, missing = {}, []
    for name in REQUIRED_PY:
        m = re.search(r"^\s*" + re.escape(name) + r"\s*=\s*[\"']" + _HEX + r"[\"']", md, re.M)
        (colors.__setitem__(name, _hex(m.group(1))) if m else missing.append(name))
    for name in REQUIRED_CSS:
        m = re.search(re.escape(name) + r"\s*:\s*" + _HEX, md)
        (colors.__setitem__(name, _hex(m.group(1))) if m else missing.append(name))
    if missing:
        raise BrandError("SKILL.md 缺必要色票：" + "、".join(missing))

    fonts = _fonts(md)

    logos, logo_data = {}, {}
    for key, fname in LOGOS.items():
        m = re.search(r"(assets/[\w./-]*" + re.escape(fname) + r")", md)
        if not m:
            raise BrandError(f"SKILL.md 沒寫 {fname} 的路徑")
        logos[key] = _logo_path(skill_dir, m.group(1))
        logo_data[key] = _load_png(logos[key], m.group(1))

    ver = re.search(r"^#\s.*?\bv(\d+(?:\.\d+)+)", md, re.M) or re.search(SKILL_NAME + r"\s+v(\d+(?:\.\d+)+)", md)
    version = "v" + ver.group(1) if ver else "版本不明"
    if ver and not _SAFE_VERSION.fullmatch(version):
        raise BrandError(f"版本號格式不對：{version[:20]!r}")
    safe = re.search(r"安全區.*?短邊\s*(\d+)\s*/\s*(\d+)", md)
    if safe and int(safe.group(2)) == 0:
        raise BrandError("Logo 安全區比例的分母是 0")
    ratio = min(4.0, max(0.5, int(safe.group(1)) / int(safe.group(2)))) if safe else 0.5  # 至少 1/2（取較嚴）
    return {
        "dir": skill_dir,
        "version": version,
        "colors": colors,
        "tints": _tint_table(vt),
        "fonts": fonts,
        "logos": logos,
        "logo_safe_ratio": ratio,
        "_logo_data": logo_data,  # 預載好的 data URI；底線開頭的欄位不輸出到 show --json
    }


def _logo_path(skill_dir, rel):
    """Logo 路徑 resolve（含 symlink）後必須還在該 skill 目錄裡：擋 ../ 與指到外面的 symlink。"""
    root = os.path.realpath(skill_dir)
    p = os.path.realpath(os.path.join(skill_dir, rel))
    if os.path.commonpath([root, p]) != root:
        raise BrandError(f"Logo 路徑跑出 skill 目錄外：{rel}")
    if not os.path.isfile(p):
        raise BrandError(f"Logo 檔不存在：{rel}")
    return p


def _load_png(path, rel):
    """讀成 data URI。要真的是 PNG（magic bytes）、不超過 LOGO_MAX_BYTES。"""
    try:
        if os.path.getsize(path) > LOGO_MAX_BYTES:
            raise BrandError(f"Logo 檔太大（上限 {LOGO_MAX_BYTES // 1024 // 1024}MB）：{rel}")
        with open(path, "rb") as f:
            data = f.read(LOGO_MAX_BYTES + 1)
    except OSError as e:
        raise BrandError(f"Logo 檔讀不了（{type(e).__name__}）：{rel}") from e
    if len(data) > LOGO_MAX_BYTES:
        raise BrandError(f"Logo 檔太大：{rel}")
    if not data.startswith(PNG_MAGIC):
        raise BrandError(f"Logo 檔不是 PNG：{rel}")
    return "data:image/png;base64," + base64.b64encode(data).decode()


def validate(ci):
    """套用前把會寫進 HTML 的東西全部驗過一次；任何一項不合格 → BrandError（整頁退回原生）。"""
    for k, v in list(ci["colors"].items()) + [(f"色階 {b}", h) for b, row in ci["tints"].items() for h in row.values()]:
        if not _SAFE_HEX.fullmatch(v):
            raise BrandError(f"色碼格式不對：{k}")
    for n in ci["fonts"]["stack"] + ci["fonts"]["en"] + ci["fonts"]["skipped"]:
        _check_font(n)
    if not (ci["version"] == "版本不明" or _SAFE_VERSION.fullmatch(ci["version"])):
        raise BrandError("版本號格式不對")
    t = tokens(ci)
    bad = [k for k, v in t.items() if not _SAFE_TOKEN.fullmatch(v)]
    if bad:
        raise BrandError("組出的 CSS 值含不允許的字元：" + "、".join(bad))
    names = ("--green", "--yellow", "--red")
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if delta_e(t[a], t[b]) < SEMANTIC_MIN_DE:
                raise BrandError(f"推導的狀態色 {a} 與 {b} 太接近（ΔE < {SEMANTIC_MIN_DE}）")
        if contrast(t[a], t[a + "-soft"]) < 4.5 or contrast(t[a], t["--paper"]) < 4.5:
            raise BrandError(f"推導的狀態色 {a} 文字對比不足 4.5")
    return t


def load(skill_dir):
    """解析＋驗證＋預載全部品牌資源（Logo、覆寫層樣式）。全部成功才回傳；預期內的錯誤一律轉成 BrandError，
    蓋章時就不會再碰檔案系統、不會半路丟例外。"""
    try:
        ci = parse(skill_dir)
        validate(ci)
        if not os.path.isfile(OVERLAY_CSS):
            raise BrandError(f"本 skill 的覆寫層樣式不見了：{OVERLAY_CSS}")
        overlay = _read(OVERLAY_CSS)
        if re.search(r"</style", overlay, re.I):
            raise BrandError("覆寫層樣式裡有 </style 字樣")
        ci["_overlay"] = overlay
        return ci
    except BrandError:
        raise
    except (OSError, ValueError, ArithmeticError, LookupError, TypeError, re.error) as e:
        raise BrandError(f"解析時出錯（{type(e).__name__}）") from e


# ── 3. 轉成網頁 token ───────────────────────────────────────
def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(c))):02X}" for c in rgb)


def mix(a, b, t):
    """a 往 b 走 t（0～1）。"""
    ra, rb = _rgb(a), _rgb(b)
    return _to_hex(tuple(x + (y - x) * t for x, y in zip(ra, rb)))


def _lum(h):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _darken_until(color, toward, bg, target=4.5):
    """color 往 toward 一步步加深，直到在 bg 上的對比 ≥ target（小字門檻）。"""
    for i in range(0, 101):
        c = mix(color, toward, i / 100)
        if contrast(c, bg) >= target:
            return c
    return toward


def _hls(h):
    r, g, b = (c / 255 for c in _rgb(h))
    hh, l, s = colorsys.rgb_to_hls(r, g, b)
    return hh * 360, l, s


def _from_hls(hue_deg, l, s):
    r, g, b = colorsys.hls_to_rgb((hue_deg % 360) / 360, max(0, min(1, l)), max(0, min(1, s)))
    return _to_hex((r * 255, g * 255, b * 255))


def _lab(h):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in _rgb(h))
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116  # noqa: E731
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def delta_e(a, b):
    """兩色的感知差距（CIE76）。≥ 20 一眼看得出是不同色；< 10 容易混。"""
    return math.dist(_lab(a), _lab(b))


SEMANTIC_MIN_DE = 20  # 三種狀態色彼此、以及警示色與促銷紅之間，至少要差這麼多
MIN_SAT = {"green": 0.4, "yellow": 0.6, "red": 0.5}  # 推導狀態色的最低飽和度（HLS）


def _semantic(hue_deg, sat, white, target=4.5):
    """一組狀態色：(字色, 淺底, 邊線)。字色在淺底與白底上都要到 target 對比（小字可讀）。"""
    soft = _from_hls(hue_deg, 0.94, sat)
    border = _from_hls(hue_deg, 0.80, sat * 0.85)
    fg = _from_hls(hue_deg, 0.05, sat)
    for i in range(100, 4, -1):
        c = _from_hls(hue_deg, i / 200, sat)
        if contrast(c, soft) >= target and contrast(c, white) >= target:
            fg = c
            break
    return fg, soft, border


def status_colors(blue, promo, white):
    """CI 沒有非促銷用的紅、也沒有成功／注意色——這裡從讀到的色推導，不寫死任何色碼。

    好轉（綠）、注意（琥珀黃）：拿品牌藍的飽和度打折、換色相。
    警示（紅）：從促銷紅的色相往紫紅轉、加深（字色對比 ≥ 6），跟促銷紅拉開；
    轉了還不夠遠（ΔE < SEMANTIC_MIN_DE）就再轉、再加深，直到夠遠。
    【暫代】待設計部門給正式警示色；給了以後改成從 CI 讀。"""
    _, _, bs = _hls(blue)
    ph, _, ps = _hls(promo)
    # 飽和度設下限：品牌藍／促銷紅若是灰色（飽和度 0），不設下限三色會全變成同一個灰
    green = _semantic(135, max(MIN_SAT["green"], bs * 0.55), white)
    yellow = _semantic(40, max(MIN_SAT["yellow"], min(1, bs * 0.9)), white)
    rsat = max(MIN_SAT["red"], min(1, ps * 1.3))
    red = None
    for shift in range(20, 65, 5):
        for target in (6, 7, 8):
            cand = _semantic(ph - shift, rsat, white, target)
            if delta_e(cand[0], promo) >= SEMANTIC_MIN_DE:
                red = cand
                break
        if red:
            break
    red = red or _semantic(ph - 60, rsat, white, 8)
    return {"green": green, "yellow": yellow, "red": red}


def chart_series(ci):
    """圖表序列色：預設中性灰褐（由深到淺），品牌藍只留給 --chart-focus（重點那一條／一根）。
    CI：品牌藍是強調色，一張 2–3 處；整片藍的圖會把強調用光。"""
    c = ci["colors"]
    ink, greige, brown, white = c["INK"], c["GREIGE"], c["GREIGE_2"], c["--brand-white"]
    return [mix(brown, ink, 0.45), greige, mix(brown, white, 0.45), mix(greige, ink, 0.75)]


def tokens(ci):
    """CI → {CSS 變數: 值}。只換值不換名；兩種命名（base/onepage 與 slides）一起給。"""
    c = ci["colors"]
    ink, blue, greige, brown = c["INK"], c["BLUE"], c["GREIGE"], c["GREIGE_2"]
    bg, light, white, promo = c["--brand-bg"], c["--brand-light-blue"], c["--brand-white"], c["--brand-promo"]

    def tint(col, pct):  # CI 色階表有就照表，沒有（例如品牌藍換了值）就跟白色混
        return ci["tints"].get(col, {}).get(pct) or mix(col, white, 1 - pct / 100)

    muted = _darken_until(greige, ink, white)          # 灰褐只當小標；一般弱化字要可讀
    st = status_colors(blue, promo, white)             # 好轉／注意／警示（推導；警示色暫代）
    green, yellow, red = st["green"], st["yellow"], st["red"]
    series = chart_series(ci)
    # 易混字形規則：CI 英文字型裡「1」像「I」的（Gill Sans）已在解析時跳過，這裡拿到的是下一順位
    font = ", ".join(css_str(f) for f in ci["fonts"]["stack"]) + ", sans-serif"
    num = ", ".join(css_str(f) for f in ci["fonts"]["en"]) + ", sans-serif"
    t = {
        "--ivory": bg, "--bg": bg,
        "--paper": white, "--bg-card": white,
        "--slate": ink, "--ink": ink, "--text": ink,
        "--clay": blue, "--accent": blue,
        "--clay-d": mix(blue, "#000000", 0.2), "--accent-strong": mix(blue, "#000000", 0.2),
        "--oat": light,
        "--olive": brown,
        "--greige": greige, "--greige-2": brown,
        "--g100": tint(bg, 40), "--bg-soft": tint(bg, 40),
        "--g200": tint(greige, 20), "--bg-soft-2": tint(greige, 20),
        "--g300": tint(greige, 40), "--border": tint(greige, 40), "--line": tint(greige, 40),
        "--g500": muted, "--text-soft": muted, "--border-strong": muted,
        "--g700": mix(greige, ink, 0.75), "--text-muted": mix(greige, ink, 0.75),
        "--clay-soft": tint(light, 20), "--accent-soft": tint(light, 20), "--clay-border": light,
        "--green": green[0], "--green-soft": green[1], "--green-border": green[2],
        "--red": red[0], "--red-soft": red[1], "--red-border": red[2],
        "--yellow": yellow[0], "--yellow-soft": yellow[1], "--yellow-border": yellow[2],
        "--orange": yellow[0], "--orange-soft": yellow[1], "--orange-border": yellow[2],
        "--olive-soft": tint(brown, 20), "--olive-border": tint(brown, 40),
        "--purple": series[1], "--purple-soft": tint(greige, 20), "--purple-border": tint(greige, 40),
        "--blue": blue, "--blue-soft": tint(light, 20), "--blue-border": light,
        # slides 專用
        "--bg-glass": bg + "F5", "--bg-overlay": white + "A6", "--bg-dark": ink,
        "--on-dark-text": white, "--on-dark-muted": light, "--on-dark-accent": light,
        "--diagram-line": greige, "--diagram-line-strong": muted,
        # 圖表：序列預設中性灰褐，藍只給重點（--chart-focus）。chart skill／slides 範本讀這組
        "--chart-1": series[0], "--chart-2": series[1], "--chart-3": series[2], "--chart-4": series[3],
        "--chart-focus": blue,
        "--deck-backdrop": mix(ink, "#000000", 0.3),
        "--heading-weight": "700", "--heading-tracking": "0",
        # 字型：CI 沒有襯線字，標題與內文同一套；--mono 不動（程式碼要等寬）
        "--sans": font, "--serif": font, "--num-font": num,
        # 促銷紅只宣告、不指派給任何語意變數；要用得自己寫在 .promo 規則裡（verify 會查）
        "--brand-promo": promo,
        "--vt-brand-rule": mix(ink, brown, 0.15),
    }
    return t


# ── 4. 主題決定與總入口 ─────────────────────────────────────
class _RootTheme(HTMLParser):
    """只看真正的根標籤 <html>：註解、腳本字串裡長得像 <html …> 的不算；有無引號、單雙引號都吃。"""

    class Done(Exception):
        pass

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.theme = None

    def handle_starttag(self, tag, attrs):
        if tag == "html":
            v = dict(attrs).get("data-vt-theme")
            self.theme = v.strip().lower() if v and v.strip() else None
        raise self.Done  # 第一個開始標籤不是 <html> ＝ 沒有根標籤屬性可讀


def page_theme(html):
    p = _RootTheme()
    try:
        p.feed(html or "")
        p.close()
    except _RootTheme.Done:
        pass
    except Exception:  # 壞掉的 HTML：當作頁面沒指定
        return None
    return p.theme


def choose_theme(cli=None, html=None, profile=None):
    """回傳 (主題, 由誰決定)。"""
    prof = ((profile or {}).get("tokens") or {}).get("theme")
    for val, why in ((cli, "指令參數 --theme"), (page_theme(html), "頁面 data-vt-theme"),
                     (os.environ.get("HTML_VISUALIZER_THEME"), "環境變數 HTML_VISUALIZER_THEME"),
                     (prof, "設定檔 tokens.theme")):
        if val:
            v = str(val).lower()
            if v not in THEMES:
                return "default", f"{why}={val} 不認得（可用 {'/'.join(THEMES)}），改用原本樣式"
            return v, why
    return "mrl", "預設"


def resolve(cli=None, html=None, profile=None):
    """總入口。回傳 dict：
    {"theme": "mrl"|"default", "why": 誰決定, "ok": bool, "reason": 退回原因, "ci": CI dict 或 None}"""
    theme, why = choose_theme(cli, html, profile)
    # reason 給終端機看（可含路徑，方便除錯）；html_reason 寫進產出 HTML（不得含任何路徑）
    res = {"theme": theme, "why": why, "ok": True, "reason": "", "html_reason": "", "ci": None}
    if theme != "mrl":
        return res
    skill, tried = find_skill()
    if not skill:
        res.update(theme="default", ok=False, reason="找不到 mr-living-presentation（試過：" + "；".join(tried) + "）",
                   html_reason="找不到 mr-living-presentation")
        return res
    try:
        ci = load(skill)
    except BrandError as e:
        res.update(theme="default", ok=False, reason=f"{_short(skill)} 解析失敗：{e}",
                   html_reason=f"mr-living-presentation 解析失敗：{_scrub(str(e))}")
        return res
    res["ci"] = ci
    return res


def message(res):
    """給人看的一行。"""
    if res["theme"] == "mrl":
        return f"套用居家先生 CI {res['ci']['version']}（{res['why']}；來源 {_short(res['ci']['dir'])}）"
    if not res["ok"]:
        return f"沒找到居家先生 CI，改用原本樣式：{res['reason']}"
    return f"使用原本樣式（{res['why']}）"


def ci_label(ci):
    """寫進 HTML 的 CI 來源：只留版本號，不留任何路徑。"""
    return f"MR. LIVING CI {ci['version']}"


_PATHISH = re.compile(r"(?:~|\.{0,2}/)?(?:[^\s/；，、：（）()\"'<>]+/)+[^\s/；，、：（）()\"'<>]*")


def _scrub(s):
    """把字串裡像路徑的片段換成檔名（產出 HTML 不能留本機路徑）。"""
    return _PATHISH.sub(lambda m: os.path.basename(m.group(0).rstrip("/")) or "（路徑）", s)


def _short(p):
    home = os.path.expanduser("~")
    return "~" + p[len(home):] if p.startswith(home + os.sep) else p


# ── 5. 產出頁要的區塊 ───────────────────────────────────────
def _comment(s):
    """放進 <!-- … --> 的文字：不得出現「--」（會提早結束或讓註解不合法）、也不留 < >。"""
    s = s.replace("<", "").replace(">", "")
    while "--" in s:
        s = s.replace("--", "-\u2011")
    return s.rstrip("-")


def theme_head(res):
    """<head> 裡的整段（含來源標記）。mrl：meta＋字型＋:root＋覆寫層；default：只留 meta 記原因。"""
    if res["theme"] != "mrl":
        reason = _scrub(res.get("html_reason") or res["why"]).replace('"', "'")
        return f'<meta name="vt-theme" content="default" data-reason="{_attr(reason)}">'
    ci = res["ci"]
    src = _comment(ci_label(ci))  # 只留版本號；註解裡不能出現連續兩個減號
    t = tokens(ci)
    pad = math.ceil(44 * ci["logo_safe_ratio"])  # 頁首符號高 44px
    root = " ".join(f"{k}: {v};" for k, v in t.items())
    root += f" --vt-logo-pad: {pad}px; --vt-logo-foot-pad: {math.ceil(72 * ci['logo_safe_ratio'])}px;"
    overlay = ci["_overlay"]  # resolve 時已預載並檢查過
    return (
        f"<!-- 居家先生 CI 來源：{src} -->\n"
        f'<meta name="vt-theme" content="mrl" data-source="{_attr(ci_label(ci))}" '
        f'data-version="{_attr(ci["version"])}" data-promo="{_attr(ci["colors"]["--brand-promo"])}" '
        f'data-warn="{_attr(t["--red"])}" data-font-skip="{_attr(", ".join(ci["fonts"]["skipped"]))}">\n'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap">\n'
        f'<style id="vt-theme">\n:root {{ {root} }}\n{overlay}\n</style>'
    )


def _attr(s):
    return (s.replace("&", "&amp;").replace('"', "&quot;").replace("'", "&#39;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def slots(res, label=""):
    """頁面插槽內容：header（品牌頁首）、footer（Logo＋Slogan）、mark（小字標，一頁版／簡報封面）。"""
    if res["theme"] != "mrl":
        return {"header": "", "footer": "", "mark": ""}
    lg = res["ci"]["_logo_data"]  # resolve 時已預載、驗過是 PNG
    sym, word, slogan = lg["symbol"], lg["wordmark"], lg["slogan"]
    lab = f'<div class="vt-brand-label">{_attr(label)}</div>' if label else ""
    return {
        "header": (
            '<div class="vt-brandbar"><div class="vt-brand-lockup">'
            f'<img class="vt-brand-sym" src="{sym}" alt="MR. LIVING 品牌符號">'
            f'<img class="vt-brand-word" src="{word}" alt="MR.LIVING 居家先生">'
            f"</div>{lab}</div>"
        ),
        "footer": f'<img class="vt-brand-foot" src="{slogan}" alt="MR. LIVING 居家先生 好生活．不將就">',
        "mark": f'<img class="vt-brand-mark" src="{word}" alt="MR.LIVING 居家先生">',
    }


# ── CLI ─────────────────────────────────────────────────────
def main(argv):
    if not argv or argv[0] != "show":
        print(__doc__.strip())
        return 64
    cli = next((a.split("=", 1)[1] for a in argv if a.startswith("--theme=")), None)
    profile = None
    try:
        import importlib.util as ilu
        spec = ilu.spec_from_file_location("vt_profile", os.path.join(HERE, "profile.py"))
        mod = ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        profile, _ = mod.load()
    except Exception:
        pass
    res = resolve(cli=cli, profile=profile)
    if "--json" in argv:
        out = dict(res)
        if res["ci"]:
            out["ci"] = {k: v for k, v in res["ci"].items() if not k.startswith("_")}
            out["tokens"] = tokens(res["ci"])
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(message(res))
        if res["ci"]:
            c = res["ci"]["colors"]
            print("  色票：" + " ".join(f"{k}={v}" for k, v in c.items()))
            f = res["ci"]["fonts"]
            print("  字型：" + " → ".join(f["stack"]))
            if f["skipped"]:
                print(f"  跳過（數字 1 像 I，易混字形規則）：{'、'.join(f['skipped'])}")
            t = tokens(res["ci"])
            print(f"  狀態色：好轉 {t['--green']}　注意 {t['--yellow']}　警示 {t['--red']}（暫代）"
                  f"　警示與促銷紅 ΔE={delta_e(t['--red'], c['--brand-promo']):.0f}")
            print(f"  Logo 留白：≥ 短邊 × {res['ci']['logo_safe_ratio']:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
