#!/usr/bin/env python3
"""
蓋章 — verify.py 在檢查前對產出頁做的三件事，全部冪等（重跑不會疊加）：

1. 字級與間距正規化：頁面裡所有寫死的字級（<style> 區塊與 style="" 屬性）改成
   calc(原值 * var(--fs, 1))、px 間距改成 calc(原值 * var(--dens, 1))，調整面板的
   字級與密度才推得動它們。
   為什麼要對每份產出跑、不只改範本：近 25 份產出約 44% 的字級是 AI 在該頁
   自己寫的；只改範本，拉滑桿時會大小字混雜。
2. 設定檔變數：<style id="vt-profile"> 只寫使用者選過的 :root 變數。
3. 調整面板：缺就注入 assets/tweaks.{css,js}，舊版整段替換成現行版。
0. 品牌主題（最先做）：預設 mrl＝現場找居家先生 CI skill、讀出色票與 Logo 套上（scripts/brand.py）；
   找不到或解析失敗就整頁用原本樣式，並在 <head> 留 meta 記原因。插槽 <!-- vt-brand:header|footer|mark -->
   有就填，一般報告頁沒有 header 插槽時在 <body> 後補一條品牌頁首。

用法（通常由 verify.py 呼叫；手動除錯可直接跑）：python3 stamp.py <file.html> [--theme=mrl|default]
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
import importlib.util as _ilu  # noqa: E402

# 用檔案路徑載入：標準庫也有一個 profile 模組（效能分析），用 import profile 可能拿錯
_spec = _ilu.spec_from_file_location("vt_profile", os.path.join(HERE, "profile.py"))
profile_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(profile_mod)
_bspec = _ilu.spec_from_file_location("vt_brand", os.path.join(HERE, "brand.py"))
brand_mod = _ilu.module_from_spec(_bspec)
_bspec.loader.exec_module(brand_mod)

ASSETS = os.path.join(os.path.dirname(HERE), "assets")

# ── 1. 字級正規化 ───────────────────────────────────────────
# 只轉絕對單位：px、rem，以及只含絕對單位與 vw/vh 的 clamp()/min()/max()。
# em 與 % 跳過：它們相對父層，父層已經乘過倍率，再乘一次會變平方。
_ABS = re.compile(r"^-?\d*\.?\d+(px|rem)$")
_FUNC = re.compile(r"^(clamp|min|max)\((.*)\)$", re.S)
_FUNC_UNITS = {"px", "rem", "vw", "vh", "vmin", "vmax", ""}


def _scalable(v):
    v = v.strip()
    if not v or "var(" in v or "calc(" in v:
        return False
    if _ABS.match(v):
        return True
    m = _FUNC.match(v)
    if m:
        units = set(re.findall(r"\d([a-z%]*)", m.group(2).lower()))
        return bool(units) and units <= _FUNC_UNITS
    return False


def _wrap(v):
    return f"calc({v.strip()} * var(--fs, 1))"


_FONT_SHORTHAND = re.compile(
    r"^((?:(?:italic|oblique|normal|bold|bolder|lighter|small-caps|[1-9]00)\s+)*)"
    r"(-?\d*\.?\d+(?:px|rem))"
    r"(?:(\s*/\s*)(-?\d*\.?\d+(?:px|rem)|[\d.]+|normal))?"
    r"(\s+.+)$",
    re.S,
)


_PX_TOKEN = re.compile(r"(?<![\w.-])(-?\d*\.?\d+px)\b")
_SPACING = re.compile(
    r"(padding|margin)(-(top|right|bottom|left|block|inline)(-(start|end))?)?|gap|row-gap|column-gap", re.I
)


def _convert_decls(body):
    """一段宣告（不含大括號）→ 轉換後字串、轉了幾處。"""
    n = 0

    def rep(m):
        nonlocal n
        prop, sep, val, imp, end = m.group(1), m.group(2), m.group(3), m.group(4) or "", m.group(5)
        low = prop.lower()
        if _SPACING.fullmatch(low):
            # 密度：間距裡每個 px 值乘 --dens；已含 var()/calc() 的不碰（冪等）
            if "var(" in val or "calc(" in val or "px" not in val:
                return m.group(0)
            new = _PX_TOKEN.sub(lambda t: f"calc({t.group(1)} * var(--dens, 1))", val)
            n += 1
            return f"{prop}{sep}{new}{imp}{end}"
        if low in ("font-size", "line-height"):
            if low == "line-height" and not _ABS.match(val.strip()):
                return m.group(0)  # 行高只轉 px/rem；無單位與 em 本來就跟著字級走
            if not _scalable(val):
                return m.group(0)
            n += 1
            return f"{prop}{sep}{_wrap(val)}{imp}{end}"
        if low == "font":
            fm = _FONT_SHORTHAND.match(val.strip())
            if not fm:
                return m.group(0)
            pre, size, slash, lh, fam = fm.groups()
            new = pre + _wrap(size)
            if slash:
                new += slash + (_wrap(lh) if _ABS.match(lh) else lh)
            new += fam
            n += 1
            return f"{prop}{sep}{new}{imp}{end}"
        return m.group(0)

    out = re.sub(
        r"(?<![-\w])(font-size|line-height|font|(?:padding|margin)(?:-[a-z]+){0,2}|gap|row-gap|column-gap)"
        r"(\s*:\s*)([^;{}]*?)(\s*!important)?(\s*(?:;|$))",
        rep,
        body,
        flags=re.I | re.S,
    )
    return out, n


_ATTR_SEL = re.compile(r"\[style\*=([\"'])([^\"']*)\1\]")
_ATTR_PX = re.compile(
    r"^((?:font-size|line-height|(?:padding|margin)(?:-[a-z]+){0,2}|gap|row-gap|column-gap)\s*:\s*)(-?\d*\.?\d+px)"
)


def _patch_attr_selectors(sel):
    """[style*="margin-left: 50px"] 這類「用行內樣式文字選元素」的規則：行內值被改成
    calc(50px * …) 後就對不上了（base-template 的手機縮排規則就是這樣）。補一個對應新寫法的選擇器，舊的保留。"""
    alts = []
    for m in _ATTR_SEL.finditer(sel):
        am = _ATTR_PX.match(m.group(2))
        if not am:
            continue
        q = m.group(1)
        new_attr = f"[style*={q}{am.group(1)}calc({am.group(2)}{q}]"
        if new_attr in sel:
            continue
        alts.append(sel.strip().replace(m.group(0), new_attr))
    if not alts:
        return sel
    lead = sel[: len(sel) - len(sel.lstrip())]
    return lead + sel.strip() + ", " + ", ".join(alts) + " "


def _convert_css(css):
    """整段 CSS：逐條規則轉，html 與 :root 上的字級不轉（會讓 rem 變平方）。"""
    total = 0

    def rule(m):
        nonlocal total
        sel, body = m.group(1), m.group(2)
        s = sel.strip().split("\n")[-1].strip()
        if re.fullmatch(r"(html|:root)(\s*,\s*(html|:root))*", s):
            return m.group(0)
        new, n = _convert_decls(body)
        total += n
        if "[style*=" in sel:
            sel = _patch_attr_selectors(sel)
        return sel + "{" + new + "}"

    out = re.sub(r"([^{}]*)\{([^{}]*)\}", rule, css)
    return out, total


_TAG = re.compile(
    r"<[a-zA-Z][^\s>/]*(?:\s+[^\s=>/]+(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+))?)*\s*/?>"
)
_STYLE_ATTR = re.compile(r"(\sstyle\s*=\s*)(\"[^\"]*\"|'[^']*')", re.I)
# 這些區塊的內容不是標記，裡面長得像 style="…" 的字串不能碰
_OPAQUE = re.compile(r"(<script\b[^>]*>.*?</script\s*>|<!--.*?-->|<textarea\b[^>]*>.*?</textarea\s*>)", re.I | re.S)
_STYLE_BLOCK = re.compile(r"(<style\b[^>]*>)(.*?)(</style\s*>)", re.I | re.S)


def normalize_fonts(html):
    total = 0
    parts = _OPAQUE.split(html)
    for i in range(0, len(parts), 2):  # 偶數索引＝一般標記
        seg = parts[i]

        def style_block(m):
            nonlocal total
            new, n = _convert_css(m.group(2))
            total += n
            return m.group(1) + new + m.group(3)

        seg = _STYLE_BLOCK.sub(style_block, seg)

        def tag(m):
            def attr(a):
                nonlocal total
                q = a.group(2)[0]
                new, n = _convert_decls(a.group(2)[1:-1])
                total += n
                return a.group(1) + q + new + q

            return _STYLE_ATTR.sub(attr, m.group(0))

        seg = _TAG.sub(tag, seg)
        parts[i] = seg
    return "".join(parts), total


def _find_outside_opaque(html, needle, last):
    """在腳本／註解／textarea 以外的一般標記裡找 needle（不分大小寫）。
    為什麼：頁面腳本字串裡可能有 "</head>"（用 JS 組 iframe 內容的原型頁就有），
    rfind 會找到字串裡那個、把區塊插進 JS 字串中間，整段腳本炸掉。"""
    low = html.lower()
    spans = [(m.start(), m.end()) for m in _OPAQUE.finditer(html)]
    hits = [m.start() for m in re.finditer(re.escape(needle), low)]
    hits = [i for i in hits if not any(a <= i < b for a, b in spans)]
    if not hits:
        return -1
    return hits[-1] if last else hits[0]


def _insert(html, block, prefer_head):
    """把 block＋換行插在 </head>（或 </body>）前。移除時刪同一段字串，重跑才不會累積空白。
    HTML5 允許省略這些標籤（spec-alignment 範本就沒有），找不到就退到下一個位置、最後放檔尾。"""
    if prefer_head:
        idx = _find_outside_opaque(html, "</head>", last=False)
        if idx < 0:
            idx = _find_outside_opaque(html, "<body", last=False)
    else:
        idx = _find_outside_opaque(html, "</body>", last=True)
        if idx < 0:
            idx = _find_outside_opaque(html, "</html>", last=True)
    if idx < 0:
        return html + block + "\n"
    return html[:idx] + block + "\n" + html[idx:]


# ── 0. 品牌主題 ─────────────────────────────────────────────
_THEME_BLOCK = re.compile(r"<!-- vt-theme:begin[^>]*-->.*?<!-- vt-theme:end -->\n", re.S)
_SLOT = re.compile(r"(<!-- vt-brand:(header|footer|mark) -->).*?(<!-- /vt-brand:\2 -->)", re.S)
_AUTO = re.compile(r"<!-- vt-brand:auto -->.*?<!-- /vt-brand:auto -->\n?", re.S)
_HEADER_SLOT = re.compile(re.escape("<!-- vt-brand:header -->"))
_FOOTER_SLOT = re.compile(re.escape("<!-- vt-brand:footer -->"))
_BODY_OPEN = re.compile(r"<body\b[^>]*>", re.I)
_LABEL = re.compile(r"<meta\s+name=[\"']vt-brand-label[\"']\s+content=[\"']([^\"']*)[\"']", re.I)


_HEADER_OPEN = re.compile(r"<header\b([^>]*)>", re.I)
# 品牌插槽／自動頁首／主題區塊的替換只做在「真正的標記」裡：腳本與 textarea 的內容是文字，
# 裡面寫著 <!-- vt-brand:header --> 的（JS 組頁面的字串、教學用的 textarea 範例）不能被填進 Logo。
# 不沿用 _OPAQUE 整組：它把 HTML 註解也當不透明，插槽標記本身就是註解，會連真插槽一起跳過
_RAW_TEXT = re.compile(r"(<script\b[^>]*>.*?</script\s*>|<textarea\b[^>]*>.*?</textarea\s*>)", re.I | re.S)


def _sub_markup(rx, repl, html):
    """rx.sub，但跳過 script／textarea 內容。"""
    parts = _RAW_TEXT.split(html)
    for i in range(0, len(parts), 2):
        parts[i] = rx.sub(repl, parts[i])
    return "".join(parts)


def _search_markup(rx, html):
    for i, part in enumerate(_RAW_TEXT.split(html)):
        if i % 2 == 0:
            m = rx.search(part)
            if m:
                return m
    return None


def _header_spot(html, free):
    """自動品牌頁首插在哪：第一個 <header> 裡最前面——session 色帶執行期會插到 header 的第一個子元素，
    所以品牌列一定落在色帶「下方」。那個 header 是固定／黏頂的（marathon 的頂部列）就改插在它後面，
    不然 Logo 會一直佔著畫面。沒有 header 才退到 <body> 後面（色帶那時插在 body 最前面，仍在上方）。"""
    for m in _HEADER_OPEN.finditer(html):
        if not free(m.start()):
            continue
        if re.search(r"sticky|fixed", m.group(1), re.I):
            end = html.find("</header>", m.end())
            return end + len("</header>") if end >= 0 else None
        return m.end()
    m = _BODY_OPEN.search(html)
    return m.end() if m and free(m.start()) else None


def stamp_theme(html, res):
    """全有或全無：mrl 時 head 區塊＋所有插槽一起填；default 時一起清空，只留 meta 記原因。"""
    html = _sub_markup(_THEME_BLOCK, "", html)
    html = _sub_markup(_AUTO, "", html)
    lab = _search_markup(_LABEL, html)
    fill = brand_mod.slots(res, lab.group(1) if lab else "")
    html = _sub_markup(_SLOT, lambda m: m.group(1) + fill[m.group(2)] + m.group(3), html)
    block = f"<!-- vt-theme:begin {res['theme']} -->\n{brand_mod.theme_head(res)}\n<!-- vt-theme:end -->"
    html = _insert(html, block, prefer_head=True)
    # 捲動式頁面（沒有 data-layout）漏了插槽：自動補，整頁才不會少了品牌識別
    if res["theme"] == "mrl" and not re.search(r"<html[^>]*\bdata-layout=", html):
        spans = [(a.start(), a.end()) for a in _OPAQUE.finditer(html)]
        free = lambda i: not any(a <= i < b for a, b in spans)  # noqa: E731
        if not _search_markup(_HEADER_SLOT, html):
            auto = f'<!-- vt-brand:auto --><div class="vt-brand-auto">{fill["header"]}</div><!-- /vt-brand:auto -->\n'
            at = _header_spot(html, free)
            if at is not None:
                html = html[:at] + auto + html[at:]
        if not _search_markup(_FOOTER_SLOT, html):
            auto = (f'<!-- vt-brand:auto --><div class="vt-brand-auto vt-brand-footwrap">{fill["footer"]}</div>'
                    "<!-- /vt-brand:auto -->")
            html = _insert(html, auto, prefer_head=False)
    return html


# ── 2. 設定檔變數 ───────────────────────────────────────────
_PROFILE_BLOCK = re.compile(r"<style id=\"vt-profile\"[^>]*>.*?</style>\n", re.S)


def profile_block(profile):
    decls = profile_mod.css_vars(profile)
    h = hashlib.sha1("\n".join(decls).encode()).hexdigest()[:10]
    body = (":root { " + " ".join(decls) + " }") if decls else ""
    return f'<style id="vt-profile" data-profile-hash="{h}">{body}</style>', h


def stamp_profile(html, profile):
    # 頁面沒用 --wrap-max（舊產出、自己寫版面的頁）就不寫寬度：寫了面板會出現寬度項、按了卻沒反應
    if "var(--wrap-max" not in html and ((profile.get("tokens") or {}).get("layout") or {}).get("maxWidth"):
        profile = json.loads(json.dumps(profile))
        profile["tokens"]["layout"].pop("maxWidth", None)
    block, h = profile_block(profile)
    html = _PROFILE_BLOCK.sub("", html)
    return _insert(html, block, prefer_head=True), h


# ── 3. 調整面板 ─────────────────────────────────────────────
_TWEAKS_BLOCK = re.compile(r"<!-- vt-tweaks:begin[^>]*-->.*?<!-- vt-tweaks:end -->\n", re.S)


def tweaks_block():
    css = open(os.path.join(ASSETS, "tweaks.css"), encoding="utf-8").read()
    js = open(os.path.join(ASSETS, "tweaks.js"), encoding="utf-8").read()
    # 內嵌腳本裡只要出現 script 結尾標籤，瀏覽器就在那裡切斷整段（註解裡的用法範例也算）
    if "</script" in js.lower() or "</style" in css.lower():
        raise ValueError("tweaks 資產裡出現 script／style 的結尾標籤字樣，內嵌會被切斷")
    ver = hashlib.sha1((css + js).encode()).hexdigest()[:10]
    # 不寫 profile.py 的位置：產出頁會被轉寄、打包給別人，不能帶本機路徑（家目錄、使用者名稱、工作區）。
    # 「存成我的預設」的指令改用 skill 內的相對路徑 scripts/profile.py，由收到指令的 AI 在 skill 目錄執行
    return (
        f"<!-- vt-tweaks:begin v={ver} -->\n"
        f"<style id=\"vt-tweaks-css\">\n{css}\n</style>\n"
        f"<script id=\"vt-tweaks-js\">\n{js}\n</script>\n"
        f"<!-- vt-tweaks:end -->"
    ), ver


def stamp_tweaks(html):
    block, ver = tweaks_block()
    html = _TWEAKS_BLOCK.sub("", html)
    return _insert(html, block, prefer_head=False), ver


# Tailwind 的文字 class（text-sm、text-[10px]）是 rem／class，stamp 改不到它的樣式；頁面有 Tailwind 時補一段覆寫。
# 規則都掛在 html.vt-fs 底下（tweaks.js 只在倍率≠1 時加這個 class）：倍率 1 時完全不生效，
# 外觀保證不變——之前常駐的版本會蓋過同元素的 leading-*、改到非 Tailwind 頁上剛好叫 text-sm 的元素。
# 有 leading-* 的不改行高（它本來就跟著字級走）；有 md:text-* 這類響應式字級的不碰（覆寫會蓋掉斷點）。
_TW_NAMED = {
    "xs": ("0.75rem", "1rem"), "sm": ("0.875rem", "1.25rem"), "base": ("1rem", "1.5rem"),
    "lg": ("1.125rem", "1.75rem"), "xl": ("1.25rem", "1.75rem"), "2xl": ("1.5rem", "2rem"),
    "3xl": ("1.875rem", "2.25rem"), "4xl": ("2.25rem", "2.5rem"), "5xl": ("3rem", None), "6xl": ("3.75rem", None),
}
_TW_ARB = re.compile(r"(?<![\w:-])text-\[(\d*\.?\d+)(px|rem)\]")
_TW_BLOCK = re.compile(r"<style id=\"vt-tw-scale\">.*?</style>\n", re.S)


# 給 verify 的靜態檢查用：還原成作者寫的樣子（不寫回檔案）。蓋章會加頁首樣式、把字級與間距改成算式、
# 在頁尾接面板，頁面變長會讓按篇幅算的檢查（第一題位置、長文件）誤判
_CALC = re.compile(r"calc\((-?[\d.]+(?:px|rem)|(?:clamp|min|max)\([^()]*\)) \* var\(--(?:fs|dens), 1\)\)")


def unstamp(html):
    for rx in (_TWEAKS_BLOCK, _PROFILE_BLOCK, _TW_BLOCK):
        html = rx.sub("", html)
    for rx in (_THEME_BLOCK, _AUTO):
        html = _sub_markup(rx, "", html)
    html = _sub_markup(_SLOT, lambda m: m.group(1) + m.group(3), html)  # Logo 內嵌圖很長，會讓按篇幅算的檢查誤判
    return _CALC.sub(r"\1", html)


# 蓋章注入的所有區塊（給 verify 的「不含本機路徑」檢查用）：主題、品牌插槽、自動頁首頁尾、設定檔變數、
# Tailwind 覆寫、調整面板。只回傳這些區塊，不含作者正文——正文可能本來就在談路徑（例如安裝教學），不該誤判
_REGIONS = (("主題標記", _THEME_BLOCK), ("品牌插槽", _SLOT), ("自動品牌頁首／頁尾", _AUTO),
            ("設定檔變數", _PROFILE_BLOCK), ("Tailwind 覆寫", _TW_BLOCK), ("調整面板", _TWEAKS_BLOCK))
_DATA_URI = re.compile(r"data:[\w/+.-]+;base64,[A-Za-z0-9+/=]+")
# 本機路徑的樣子：macOS／Linux 家目錄、$HOME／~ 開頭、Windows 使用者目錄、Cowork 的 session 資料夾
LOCAL_PATH = re.compile(r"/Users/|/home/[^/\s]+/|\$HOME\b|\$\{HOME\}|(?<![\w.])~/|[A-Za-z]:\\Users\\|local-agent-mode-sessions")


def stamped_regions(html):
    """[(區塊名, 內容)]。內嵌圖（data: URI）先去掉：base64 字元裡可能剛好拼出 /Users 之類的字樣。"""
    out = []
    for name, rx in _REGIONS:
        for m in rx.finditer(html):
            out.append((name, _DATA_URI.sub("data:…", m.group(0))))
    return out


def local_path_leaks(html):
    """蓋章區塊裡出現的本機路徑片段 → [(區塊名, 片段)]。"""
    leaks = []
    for name, text in stamped_regions(html):
        for m in LOCAL_PATH.finditer(text):
            leaks.append((name, text[max(0, m.start() - 20): m.end() + 30].replace("\n", " ")))
    return leaks


def stamp_tailwind(html):
    html = _TW_BLOCK.sub("", html)
    if "cdn.tailwindcss.com" not in html:
        return html, 0
    classes = " ".join(re.findall(r'class="([^"]*)"', html))
    used = sorted({c for c in _TW_NAMED if re.search(r"(?<![\w:-])text-" + re.escape(c) + r"(?![\w-])", classes)})
    arb = sorted(set(_TW_ARB.findall(classes)))
    if not used and not arb:
        return html, 0
    skip = ':not([class*=":text-"])'
    rules = []
    for c in used:
        size, lh = _TW_NAMED[c]
        sel = f"html.vt-fs .text-{c}{skip}"
        rules.append(f"{sel} {{ font-size: calc({size} * var(--fs, 1)); }}")
        if lh:
            rules.append(f'{sel}:not([class*="leading-"]) {{ line-height: calc({lh} * var(--fs, 1)); }}')
    for n, u in arb:
        rules.append(f"html.vt-fs .text-\\[{n}{u}\\]{skip} {{ font-size: calc({n}{u} * var(--fs, 1)); }}")
    return _insert(html, '<style id="vt-tw-scale">' + " ".join(rules) + "</style>", prefer_head=True), len(used) + len(arb)


def stamp_page(html, profile=None, theme=None):
    """回傳 (新 html, 報告 dict)。先蓋面板與設定檔、最後正規化（面板自己的樣式已是 calc，不會被重轉）。
    theme：指令參數 --theme 的值（None＝照頁面／環境變數／設定檔／預設 mrl 決定）。"""
    if profile is None:
        profile, _ = profile_mod.load()
    # 順序有意義：主題 → 設定檔 → Tailwind 覆寫 → 面板。主題排在設定檔前面，使用者明確選過的值才蓋得過 CI。
    # 沒有 </head>、<body 的頁全部放檔尾，面板腳本執行時要讀得到前面的設定檔樣式（順序反了面板會把 150% 顯示成 100%）
    res = brand_mod.resolve(cli=theme, html=html, profile=profile)
    html = stamp_theme(html, res)
    html, h = stamp_profile(html, profile)
    html, tw = stamp_tailwind(html)
    html, ver = stamp_tweaks(html)
    html, n = normalize_fonts(html)
    return html, {"converted": n, "tailwind": tw, "profile_hash": h, "tweaks_ver": ver,
                  "theme": res["theme"], "theme_msg": brand_mod.message(res), "theme_ok": res["ok"]}


def main(argv):
    if not argv:
        print(__doc__.strip())
        return 64
    files = [a for a in argv if not a.startswith("--")]
    theme = next((a.split("=", 1)[1] for a in argv if a.startswith("--theme=")), None)
    path = files[0]
    src = open(path, encoding="utf-8").read()
    out, rep = stamp_page(src, theme=theme)
    print(rep["theme_msg"])
    if out != src:
        with open(path, "w", encoding="utf-8") as f:
            f.write(out)
    print(rep)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
