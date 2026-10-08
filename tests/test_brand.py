#!/usr/bin/env python3
"""mrl 品牌主題（scripts/brand.py ＋ stamp.py ＋ verify.check_promo）的單元測試。

不依賴本機有沒有裝居家先生 skill：每個測試在暫存目錄現做一份最小的 SKILL.md 與 Logo。
跑法：python3 tests/test_brand.py
"""
import base64
import importlib.util
import os
import re
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "html-visualizer", "scripts")
ASSETS = os.path.join(ROOT, "skills", "html-visualizer", "assets")
sys.path.insert(0, SCRIPTS)


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


brand = _load("vt_brand_t", "brand.py")
stamp = _load("vt_stamp_t", "stamp.py")
verify = _load("vt_verify_t", "verify.py")

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")

SKILL = """# MR. LIVING 居家先生｜品牌簡報 CI 規範 Skill v9.9

```python
INK      = "1A1A1A"
BLUE     = "1865FF"
GREIGE   = "A09C8E"
GREIGE_2 = "A9998C"
```

| 用途 | 字型 | Fallback |
|---|---|---|
| 中文 | Noto Sans TC（思源黑體） | 微軟正黑體 → 蘋方 |
| 英文／數字 | Gill Sans → Century Gothic → Arial | （三層 fallback） |

```css
--brand-bg:        #E4E4E4;
--brand-light-blue:#C9DAEA;
--brand-white:     #FFFFFF;
--brand-promo:     #C34135;
```

| `assets/logos/logo-symbol-on-light.png` | 符號 |
| `assets/extras/logo-with-slogan.png` | Slogan |
| `assets/extras/typography-c.png` | 字標 |
| **安全區** | Logo 四周保留 ≥ Logo 短邊 1/2 的留白 |
"""


def _base():
    with open(os.path.join(ASSETS, "base-template.html"), encoding="utf-8") as f:
        return f.read()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.skill = os.path.join(self.tmp, "mr-living-presentation")
        for sub in ("assets/logos", "assets/extras"):
            os.makedirs(os.path.join(self.skill, sub))
        for p in ("assets/logos/logo-symbol-on-light.png", "assets/extras/logo-with-slogan.png",
                  "assets/extras/typography-c.png"):
            with open(os.path.join(self.skill, p), "wb") as f:
                f.write(PNG)
        self.write_skill(SKILL)
        self.env = {k: os.environ.get(k) for k in
                    ("HTML_VISUALIZER_BRAND_DIR", "HTML_VISUALIZER_BRAND_SEARCH", "HTML_VISUALIZER_THEME")}
        os.environ["HTML_VISUALIZER_BRAND_DIR"] = self.skill
        os.environ["HTML_VISUALIZER_BRAND_SEARCH"] = "off"
        os.environ.pop("HTML_VISUALIZER_THEME", None)

    def tearDown(self):
        shutil.rmtree(self.tmp)
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def write_skill(self, text):
        with open(os.path.join(self.skill, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(text)


class TestParse(Base):
    def test_parse_ok(self):
        res = brand.resolve()
        self.assertEqual(res["theme"], "mrl", res["reason"])
        self.assertEqual(res["ci"]["version"], "v9.9")
        t = brand.tokens(res["ci"])
        self.assertEqual(t["--clay"], "#1865FF")
        self.assertEqual(t["--ivory"], "#E4E4E4")
        self.assertIn('"PingFang TC"', t["--sans"])

    def test_missing_blue_falls_back(self):
        self.write_skill(SKILL.replace('BLUE     = "1865FF"\n', ""))
        res = brand.resolve()
        self.assertEqual(res["theme"], "default")
        self.assertFalse(res["ok"])
        self.assertIn("BLUE", res["reason"])

    def test_missing_logo_falls_back(self):
        os.remove(os.path.join(self.skill, "assets/extras/typography-c.png"))
        res = brand.resolve()
        self.assertEqual(res["theme"], "default")
        self.assertIn("typography-c", res["reason"])

    def test_rule_change_followed(self):
        self.write_skill(SKILL.replace('"1865FF"', '"E0218A"'))
        t = brand.tokens(brand.resolve()["ci"])
        self.assertEqual(t["--clay"], "#E0218A")
        self.assertEqual(t["--accent"], "#E0218A")

    def test_not_found(self):
        os.environ["HTML_VISUALIZER_BRAND_DIR"] = os.path.join(self.tmp, "nope")
        res = brand.resolve()
        self.assertEqual(res["theme"], "default")
        self.assertIn("找不到", res["reason"])
        self.assertIn("沒找到居家先生 CI", brand.message(res))

    def test_promo_never_semantic(self):
        t = brand.tokens(brand.resolve()["ci"])
        hits = [k for k, v in t.items() if v.upper() == "#C34135" and k != "--brand-promo"]
        self.assertEqual(hits, [])

    def test_theme_precedence(self):
        self.assertEqual(brand.choose_theme()[0], "mrl")
        self.assertEqual(brand.choose_theme(profile={"tokens": {"theme": "default"}})[0], "default")
        os.environ["HTML_VISUALIZER_THEME"] = "mrl"
        self.assertEqual(brand.choose_theme(profile={"tokens": {"theme": "default"}})[0], "mrl")
        page = '<html data-vt-theme="default">'
        self.assertEqual(brand.choose_theme(html=page)[0], "default")
        self.assertEqual(brand.choose_theme(cli="mrl", html=page)[0], "mrl")


class TestFontRule(Base):
    """易混字形規則：「1」像「I」的字型（Gill Sans）不排任何網頁文字，改用 CI 清單的下一順位。"""

    def test_gill_sans_skipped_everywhere(self):
        ci = brand.resolve()["ci"]
        self.assertEqual(ci["fonts"]["skipped"], ["Gill Sans"])
        t = brand.tokens(ci)
        for var in ("--sans", "--serif", "--num-font"):
            self.assertNotIn("Gill Sans", t[var], var)
        # 下一順位：Century Gothic → Arial（照 CI 順序）
        self.assertTrue(t["--num-font"].startswith('"Century Gothic", "Arial"'))
        self.assertTrue(t["--sans"].startswith('"Century Gothic", "Arial", "Noto Sans TC"'))

    def test_rule_is_prefix_not_hardcoded_stack(self):
        self.assertTrue(brand.ambiguous_one("Gill Sans MT"))
        self.assertTrue(brand.ambiguous_one('"Gill Sans Nova"'))
        self.assertFalse(brand.ambiguous_one("Arial"))
        # CI 換成別的英文字型：照讀，不受規則影響
        self.write_skill(SKILL.replace("Gill Sans → Century Gothic → Arial", "Futura → Arial"))
        t = brand.tokens(brand.resolve()["ci"])
        self.assertTrue(t["--num-font"].startswith('"Futura", "Arial"'))

    def test_all_latin_ambiguous_falls_to_chinese_font(self):
        self.write_skill(SKILL.replace("Gill Sans → Century Gothic → Arial", "Gill Sans"))
        t = brand.tokens(brand.resolve()["ci"])
        self.assertTrue(t["--num-font"].startswith('"Noto Sans TC"'))
        self.assertNotIn("Gill Sans", t["--sans"])

    def test_no_weight_alias_face(self):
        out, _ = stamp.stamp_page(_base(), {"tokens": {}})
        blk = out[out.index("<!-- vt-theme:begin"):out.index("<!-- vt-theme:end -->")]
        self.assertNotIn("Gill Sans", blk.split("data-font-skip=")[1].split(">", 1)[1])
        self.assertIn('data-font-skip="Gill Sans"', blk)

    def test_verify_flags_author_gill_sans(self):
        out, _ = stamp.stamp_page(_base(), {"tokens": {}})
        self.assertEqual(verify.check_ambiguous_font(out), [])
        bad = out.replace("</head>", '<style>.kpi { font-family: "Gill Sans", sans-serif; }</style></head>', 1)
        self.assertTrue(verify.check_ambiguous_font(bad))
        svg = out.replace("<body>", '<body><svg><text font-family="Gill Sans">B1</text></svg>', 1)
        self.assertTrue(verify.check_ambiguous_font(svg))


class TestStatusColors(Base):
    """好轉／注意／警示三色：由讀到的色推導、警示≠促銷紅且明顯可分、三者一眼可分、小字可讀。"""

    def test_warning_not_promo_and_distinct(self):
        t = brand.tokens(brand.resolve()["ci"])
        promo = "#C34135"
        for k in ("--red", "--red-soft", "--red-border"):
            self.assertNotEqual(t[k].upper(), promo, k)
        self.assertGreaterEqual(brand.delta_e(t["--red"], promo), brand.SEMANTIC_MIN_DE)
        # 看得出是紅：色相落在紅（330°–360°／0°–15°）
        h = brand._hls(t["--red"])[0]
        self.assertTrue(h >= 330 or h <= 15, h)

    def test_three_labels_distinguishable(self):
        t = brand.tokens(brand.resolve()["ci"])
        names = ("--green", "--yellow", "--red")
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                self.assertGreaterEqual(brand.delta_e(t[a], t[b]), brand.SEMANTIC_MIN_DE, (a, b))
                self.assertGreaterEqual(brand.delta_e(t[a + "-soft"], t[b + "-soft"]), 5, (a, b))
            # 標籤是「淺底＋字色」：字色在淺底與白底上都要 ≥ 4.5
            self.assertGreaterEqual(brand.contrast(t[a], t[a + "-soft"]), 4.5, a)
            self.assertGreaterEqual(brand.contrast(t[a], "#FFFFFF"), 4.5, a)

    def test_derived_follows_ci(self):
        """促銷紅換值，警示色跟著重新推導，仍跟它拉開。"""
        self.write_skill(SKILL.replace("#C34135", "#D8304A"))
        t = brand.tokens(brand.resolve()["ci"])
        self.assertGreaterEqual(brand.delta_e(t["--red"], "#D8304A"), brand.SEMANTIC_MIN_DE)


class TestChartAndBlue(Base):
    def test_chart_series_neutral_focus_blue(self):
        t = brand.tokens(brand.resolve()["ci"])
        self.assertEqual(t["--chart-focus"], "#1865FF")
        for i in range(1, 5):
            self.assertNotEqual(t[f"--chart-{i}"], "#1865FF")
            self.assertGreater(brand.delta_e(t[f"--chart-{i}"], "#1865FF"), 40)

    def test_overlay_has_no_hex(self):
        with open(brand.OVERLAY_CSS, encoding="utf-8") as f:
            css = f.read()
        import re
        self.assertEqual(re.findall(r"#[0-9A-Fa-f]{3,8}\b", css), [])


class TestSlots(Base):
    """範例頁型都要有頁首、頁尾插槽；自動補的頁首落在 session 色帶下方（header 裡、不在 body 最前面）。"""

    def test_example_templates_have_slots(self):
        ex = os.path.join(ROOT, "skills", "html-visualizer", "references", "examples")
        for name in ("explainer", "marathon-decision-sheet", "spec-alignment"):
            with open(os.path.join(ex, name, "index.html"), encoding="utf-8") as f:
                html = f.read()
            self.assertIn("<!-- vt-brand:header --><!-- /vt-brand:header -->", html, name)
            self.assertIn("<!-- vt-brand:footer --><!-- /vt-brand:footer -->", html, name)
            out, rep = stamp.stamp_page(html, {"tokens": {}})
            self.assertIn('class="vt-brand-sym"', out, name)
            self.assertIn('class="vt-brand-foot"', out, name)
            self.assertEqual(stamp.stamp_page(out, {"tokens": {}})[0], out, name)
            back, _ = stamp.stamp_page(out, {"tokens": {}}, theme="default")
            # 退回原生：範本自帶的空頁尾容器不能被 verify 誤判成「半套」
            self.assertIsNone(verify.BRAND_IMG.search(back), name)
            self.assertNotIn('id="vt-theme"', back, name)

    def test_auto_header_goes_inside_header(self):
        page = ('<!doctype html><html><head><title>t</title></head><body>\n<header class="hd"><h1>x</h1></header>'
                "<main>m</main></body></html>")
        out, _ = stamp.stamp_page(page, {"tokens": {}})
        self.assertIn('<header class="hd"><!-- vt-brand:auto -->', out)
        self.assertIn("vt-brand-footwrap", out)
        sticky = page.replace('class="hd"', 'class="sticky top-0"')
        out2, _ = stamp.stamp_page(sticky, {"tokens": {}})
        self.assertIn("</header><!-- vt-brand:auto -->", out2)
        # 冪等＋切回原生乾淨
        self.assertEqual(stamp.stamp_page(out, {"tokens": {}})[0], out)
        back, _ = stamp.stamp_page(out, {"tokens": {}}, theme="default")
        self.assertNotIn("vt-brand:auto", back)


class TestStamp(Base):
    def page(self):
        with open(os.path.join(ASSETS, "base-template.html"), encoding="utf-8") as f:
            return f.read()

    def test_all_or_nothing_and_idempotent(self):
        once, rep = stamp.stamp_page(self.page(), {"tokens": {}})
        self.assertEqual(rep["theme"], "mrl")
        self.assertIn('<meta name="vt-theme" content="mrl"', once)
        self.assertIn('data-version="v9.9"', once)
        self.assertIn('class="vt-brand-sym"', once)
        self.assertIn('class="vt-brand-foot"', once)
        twice, _ = stamp.stamp_page(once, {"tokens": {}})
        self.assertEqual(once, twice)
        # 切回原生：Logo 與變數區塊整個拿掉，插槽留空
        back, rep = stamp.stamp_page(once, {"tokens": {}}, theme="default")
        self.assertEqual(rep["theme"], "default")
        self.assertNotIn("vt-brand-sym", back)
        self.assertNotIn('id="vt-theme"', back)
        self.assertIn("<!-- vt-brand:header --><!-- /vt-brand:header -->", back)

    def test_fallback_after_mrl_removes_everything(self):
        once, _ = stamp.stamp_page(self.page(), {"tokens": {}})
        self.write_skill(SKILL.replace("--brand-promo", "--brand-xxx"))
        back, rep = stamp.stamp_page(once, {"tokens": {}})
        self.assertFalse(rep["theme_ok"])
        self.assertNotIn("vt-brand-", back.replace("vt-brand:", ""))
        self.assertIn('data-reason="', back)

    def test_auto_header_when_no_slot(self):
        html = self.page().replace("<!-- vt-brand:header --><!-- /vt-brand:header -->", "")
        out, _ = stamp.stamp_page(html, {"tokens": {}})
        self.assertIn("<!-- vt-brand:auto -->", out)
        self.assertNotIn("<!-- vt-brand:auto -->", stamp.unstamp(out))

    def test_no_local_path_in_html(self):
        """產出 HTML 只留版本號／原因，不含任何本機路徑（含 ~ 縮寫、session id）。"""
        bad = ("/Users", "~/", "local-agent-mode-sessions", self.tmp)
        # skill 放在像桌面版 session 的路徑底下
        deep = os.path.join(self.tmp, "local-agent-mode-sessions", "abc-123", "mr-living-presentation")
        shutil.copytree(self.skill, deep)
        os.environ["HTML_VISUALIZER_BRAND_DIR"] = deep
        out, rep = stamp.stamp_page(self.page(), {"tokens": {}})
        self.assertEqual(rep["theme"], "mrl")
        self.assertIn("<!-- 居家先生 CI 來源：MR. LIVING CI v9.9 -->", out)
        self.assertIn('data-source="MR. LIVING CI v9.9"', out)
        for k in bad:
            self.assertNotIn(k, out)
        # 終端機訊息可以保留路徑
        self.assertIn("mr-living-presentation", brand.message(brand.resolve()))
        # 退回原生：解析失敗（Logo 不見）與找不到，原因都不留路徑
        os.remove(os.path.join(deep, "assets", "logos", "logo-symbol-on-light.png"))
        back, rep = stamp.stamp_page(out, {"tokens": {}})
        self.assertFalse(rep["theme_ok"])
        self.assertIn('data-reason="mr-living-presentation 解析失敗', back)
        os.environ["HTML_VISUALIZER_BRAND_DIR"] = os.path.join(self.tmp, "local-agent-mode-sessions", "nope")
        gone, rep = stamp.stamp_page(out, {"tokens": {}})
        self.assertIn("試過", brand.resolve()["reason"])
        for html in (back, gone):
            for k in bad:
                self.assertNotIn(k, html)

    def test_tweaks_panel_has_no_local_path(self):
        """調整面板不再把 profile.py 的本機位置寫進頁面；存檔指令改用 skill 內相對路徑。"""
        home = os.path.expanduser("~")
        for theme in ("mrl", "default"):
            out, _ = stamp.stamp_page(self.page(), {"tokens": {}}, theme=theme)
            self.assertNotIn("data-profile-tool", out, theme)
            self.assertNotIn(SCRIPTS, out, theme)
            self.assertNotIn(home + os.sep, out, theme)
            self.assertNotIn("$HOME", out, theme)
            self.assertIn('var tool = "scripts/profile.py";', out, theme)
            self.assertEqual(stamp.local_path_leaks(out), [], theme)

    def test_leak_check_scope(self):
        """verify 的本機路徑檢查：蓋章區塊全查、作者正文不查、內嵌圖不誤判。"""
        out, _ = stamp.stamp_page(self.page(), {"tokens": {}})
        self.assertEqual(stamp.local_path_leaks(out), [])
        # 舊版面板（data-profile-tool 帶 $HOME 路徑）要被抓到
        old = out.replace('<script id="vt-tweaks-js">',
                          '<script id="vt-tweaks-js" data-profile-tool="$HOME/x/scripts/profile.py">', 1)
        self.assertNotEqual(old, out)
        self.assertEqual([n for n, _ in stamp.local_path_leaks(old)], ["調整面板"])
        for bad in ("/Users/someone/a", "/home/someone/a", "~/x", r"C:\Users\x", "local-agent-mode-sessions/1"):
            leaked = out.replace("<!-- vt-theme:end -->", f"<!-- {bad} -->\n<!-- vt-theme:end -->", 1)
            self.assertEqual([n for n, _ in stamp.local_path_leaks(leaked)], ["主題標記"], bad)
        # 作者正文提到路徑（安裝教學）不算
        body = re.sub(r"(<body\b[^>]*>)", r"\1<p>把檔案放到 ~/.config 或 /Users/you/Desktop</p>", out, count=1)
        self.assertIn("/Users/you/Desktop", body)
        self.assertEqual(stamp.local_path_leaks(body), [])
        # 品牌插槽裡的內嵌圖：base64 剛好含 /Users 字樣也不算
        fake = "data:image/png;base64,AAAA/Users/BBBB=="
        slot = out.replace('src="data:image/png;base64,', f'src="{fake}" data-x="', 1)
        self.assertIn(fake, slot)
        self.assertEqual(stamp.local_path_leaks(slot), [])

    def test_promo_check(self):
        out, _ = stamp.stamp_page(self.page(), {"tokens": {}})
        is_mrl, bad = verify.check_promo(out)
        self.assertTrue(is_mrl)
        self.assertEqual(bad, [])
        misuse = out.replace("</head>", "<style>.warn { color: #c34135; }</style></head>", 1)
        self.assertTrue(verify.check_promo(misuse)[1])
        misuse2 = out.replace("<body>", '<body><span style="color: var(--brand-promo)">x</span>', 1)
        self.assertTrue(verify.check_promo(misuse2)[1])
        ok = out.replace("</head>", "<style>.promo-tag { color: var(--brand-promo); }</style></head>", 1)
        self.assertEqual(verify.check_promo(ok)[1], [])


class TestInjection(Base):
    """#1 CI 的 Markdown 不可信：字型名、色碼、版本號、註解都不能把東西塞進產出 HTML。"""

    def test_font_name_injection_falls_back(self):
        for evil in ('Arial</style><script>alert(1)</script>', 'Arial"; } body { x: y', "Arial;color:red",
                     "Arial\\\"", "Ar<ial"):
            self.write_skill(SKILL.replace("Gill Sans → Century Gothic → Arial", evil))
            res = brand.resolve()
            self.assertEqual(res["theme"], "default", evil)
            self.assertIn("字型名稱", res["reason"])
            out, rep = stamp.stamp_page(_base(), {"tokens": {}})
            self.assertFalse(rep["theme_ok"])
            self.assertNotIn("<script>alert", out)
            self.assertNotIn('id="vt-theme"', out)

    def test_cjk_font_name_still_ok(self):
        self.write_skill(SKILL.replace("微軟正黑體 → 蘋方", "華康黑體 → 蘋方"))
        res = brand.resolve()
        self.assertEqual(res["theme"], "mrl", res["reason"])
        self.assertIn('"華康黑體"', brand.tokens(res["ci"])["--sans"])

    def test_css_str_escapes(self):
        self.assertEqual(brand.css_str('a"b\\c'), '"a\\"b\\\\c"')

    def test_validate_rejects_bad_values(self):
        ci = brand.resolve()["ci"]
        for mutate in (lambda c: c["colors"].__setitem__("BLUE", "#1865FG"),
                       lambda c: c["colors"].__setitem__("INK", "#1A1A1A;}"),
                       lambda c: c.__setitem__("version", "v1.0 --><script>"),
                       lambda c: c["fonts"]["stack"].append("x</style>"),
                       lambda c: c["tints"].setdefault("#E4E4E4", {})[40] if False else
                       c["tints"].__setitem__("#E4E4E4", {100: "#E4E4E4", 40: "red;}"})):
            bad = dict(ci, colors=dict(ci["colors"]), fonts={k: list(v) for k, v in ci["fonts"].items()},
                       tints={k: dict(v) for k, v in ci["tints"].items()})
            mutate(bad)
            with self.assertRaises(brand.BrandError):
                brand.validate(bad)

    def test_comment_and_attr_escaping(self):
        c = brand._comment("MR. LIVING CI v1 --> <script>-- x-")
        self.assertNotIn("--", c)
        self.assertNotIn("<", c)
        self.assertNotIn(">", c)
        self.assertFalse(c.endswith("-"))
        self.assertEqual(brand._attr("a\"'<>&"), "a&quot;&#39;&lt;&gt;&amp;")

    def test_header_has_no_double_dash_in_comment(self):
        out, _ = stamp.stamp_page(_base(), {"tokens": {}})
        m = re.search(r"<!-- 居家先生 CI 來源：(.*?) -->", out)
        self.assertTrue(m)
        self.assertNotIn("--", m.group(1))


class TestLogoSafety(Base):
    """#2 Logo 路徑不可逃出 skill 目錄、不跟外部 symlink、要是 PNG、不超過上限。"""

    def test_dotdot_escape(self):
        outside = os.path.join(self.tmp, "outside")
        os.makedirs(outside)
        with open(os.path.join(outside, "logo-symbol-on-light.png"), "wb") as f:
            f.write(PNG)
        self.write_skill(SKILL.replace("assets/logos/logo-symbol-on-light.png",
                                       "assets/../../outside/logo-symbol-on-light.png"))
        res = brand.resolve()
        self.assertEqual(res["theme"], "default")
        self.assertIn("跑出 skill 目錄外", res["reason"])

    def test_symlink_outside(self):
        secret = os.path.join(self.tmp, "secret.png")
        with open(secret, "wb") as f:
            f.write(PNG)
        p = os.path.join(self.skill, "assets/logos/logo-symbol-on-light.png")
        os.remove(p)
        os.symlink(secret, p)
        res = brand.resolve()
        self.assertEqual(res["theme"], "default")
        self.assertIn("跑出 skill 目錄外", res["reason"])

    def test_symlink_inside_ok(self):
        p = os.path.join(self.skill, "assets/logos/logo-symbol-on-light.png")
        real = os.path.join(self.skill, "assets/logos/real.png")
        os.rename(p, real)
        os.symlink(real, p)
        self.assertEqual(brand.resolve()["theme"], "mrl")

    def test_not_png(self):
        with open(os.path.join(self.skill, "assets/extras/typography-c.png"), "wb") as f:
            f.write(b"<svg onload=alert(1)>")
        res = brand.resolve()
        self.assertEqual(res["theme"], "default")
        self.assertIn("不是 PNG", res["reason"])

    def test_too_big(self):
        with open(os.path.join(self.skill, "assets/extras/typography-c.png"), "wb") as f:
            f.write(PNG + b"\0" * (brand.LOGO_MAX_BYTES + 1))
        res = brand.resolve()
        self.assertEqual(res["theme"], "default")
        self.assertIn("太大", res["reason"])


class TestRobust(Base):
    """#3 預期內的解析／讀取錯誤一律退回原生，不讓蓋章中止；資源預載好才套用。"""

    def assert_fallback(self):
        res = brand.resolve()
        self.assertEqual(res["theme"], "default")
        self.assertFalse(res["ok"])
        out, rep = stamp.stamp_page(_base(), {"tokens": {}})
        self.assertFalse(rep["theme_ok"])
        self.assertIn('<meta name="vt-theme" content="default"', out)
        return res

    def test_zero_denominator(self):
        self.write_skill(SKILL.replace("短邊 1/2", "短邊 1/0"))
        self.assertIn("分母", self.assert_fallback()["reason"])

    def test_non_utf8_skill(self):
        with open(os.path.join(self.skill, "SKILL.md"), "wb") as f:
            f.write(SKILL.encode("utf-8") + b"\xff\xfe\x80")
        self.assertIn("讀不了", self.assert_fallback()["reason"])

    def test_non_utf8_visual_tokens(self):
        os.makedirs(os.path.join(self.skill, "references"))
        with open(os.path.join(self.skill, "references", "visual-tokens.md"), "wb") as f:
            f.write(b"\xff\xfe\x80")
        self.assert_fallback()

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root 讀得到 000 權限的檔")
    def test_unreadable_logo(self):
        p = os.path.join(self.skill, "assets/extras/typography-c.png")
        os.chmod(p, 0)
        try:
            self.assertIn("讀不了", self.assert_fallback()["reason"])
        finally:
            os.chmod(p, 0o644)

    def test_overlay_missing(self):
        old = brand.OVERLAY_CSS
        brand.OVERLAY_CSS = os.path.join(self.tmp, "nope.css")
        try:
            self.assertIn("覆寫層", brand.resolve()["reason"])
        finally:
            brand.OVERLAY_CSS = old

    def test_preloaded_so_stamp_never_touches_disk(self):
        """resolve 之後檔案才不見（或壞掉），蓋章照樣用預載的資料完成，不會丟例外。"""
        res = brand.resolve()
        self.assertEqual(res["theme"], "mrl")
        shutil.rmtree(os.path.join(self.skill, "assets"))
        old = brand.OVERLAY_CSS
        brand.OVERLAY_CSS = os.path.join(self.tmp, "nope.css")
        try:
            html = stamp.stamp_theme(_base(), res)
        finally:
            brand.OVERLAY_CSS = old
        self.assertIn('class="vt-brand-sym"', html)
        self.assertIn('id="vt-theme"', html)

    def test_show_json_omits_preloaded_blobs(self):
        import contextlib
        import io
        import json
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            brand.main(["show", "--json"])
        out = json.loads(buf.getvalue())
        self.assertEqual(out["ci"]["version"], "v9.9")
        self.assertNotIn("_logo_data", out["ci"])
        self.assertNotIn("_overlay", out["ci"])


class TestSlotsOpaque(Base):
    """#4 插槽替換只動真正的標記：script 字串、textarea 範例裡的插槽字樣原封不動。"""

    def test_script_and_textarea_untouched(self):
        marker = "<!-- vt-brand:header --><!-- /vt-brand:header -->"
        js = f'<script>var tpl = "{marker}<!-- vt-brand:auto -->x<!-- /vt-brand:auto -->";</script>'
        ta = f"<textarea>{marker}\n<!-- vt-brand:footer --><!-- /vt-brand:footer --></textarea>"
        page = _base().replace("</head>", js + "</head>", 1).replace("<body>", "<body>" + ta, 1)
        self.assertIn(js, page)
        self.assertIn(ta, page)
        out, _ = stamp.stamp_page(page, {"tokens": {}})
        self.assertIn(js, out)
        self.assertIn(ta, out)
        self.assertIn('class="vt-brand-sym"', out)  # 真插槽照填
        self.assertEqual(stamp.stamp_page(out, {"tokens": {}})[0], out)
        back, _ = stamp.stamp_page(out, {"tokens": {}}, theme="default")
        self.assertIn(js, back)
        self.assertIn(ta, back)
        self.assertNotIn("vt-brand-sym", back)

    def test_auto_header_ignores_slot_text_in_script(self):
        """頁面沒有真插槽、只有腳本字串裡有：仍要自動補頁首。"""
        page = ('<!doctype html><html><head><script>var s = "<!-- vt-brand:header -->'
                '<!-- /vt-brand:header -->";</script></head><body><main>m</main></body></html>')
        out, _ = stamp.stamp_page(page, {"tokens": {}})
        self.assertIn('<!-- vt-brand:auto --><div class="vt-brand-auto">', out)
        self.assertIn('var s = "<!-- vt-brand:header --><!-- /vt-brand:header -->";', out)


class TestPageTheme(Base):
    """#5 讀真正的根標籤 <html data-vt-theme>。"""

    def test_variants(self):
        cases = {
            '<!doctype html><html data-vt-theme=default><body>': "default",
            "<html lang='zh' data-vt-theme='default'>": "default",
            '<HTML DATA-VT-THEME="Default">': "default",
            '<!-- <html data-vt-theme="default"> --><html data-vt-theme="mrl">': "mrl",
            '<!-- <html data-vt-theme="default"> --><html lang="zh">': None,
            '<html><head><script>var x = \'<html data-vt-theme="default">\';</script>': None,
            '<div><html data-vt-theme="default">': None,
            '<html data-vt-theme>': None,
            "": None,
        }
        for html, want in cases.items():
            self.assertEqual(brand.page_theme(html), want, html)

    def test_choose_theme_uses_root(self):
        self.assertEqual(brand.choose_theme(html="<html data-vt-theme=default>")[0], "default")
        self.assertEqual(brand.choose_theme(html='<!-- <html data-vt-theme="default"> --><html>')[0], "mrl")


class TestSearch(Base):
    """#6 逐層惰性搜尋：前一層找到就不跑後面的 glob；session 資料夾用固定深度。"""

    def setUp(self):
        super().setUp()
        self.home = os.environ.get("HOME")
        os.environ["HOME"] = os.path.join(self.tmp, "home")
        os.environ["HTML_VISUALIZER_BRAND_SEARCH"] = "on"

    def tearDown(self):
        os.environ["HOME"] = self.home
        super().tearDown()

    def test_env_hit_skips_globs(self):
        calls = []
        real = brand.glob.glob
        brand.glob.glob = lambda *a, **k: calls.append(a) or real(*a, **k)
        try:
            skill, _ = brand.find_skill()
        finally:
            brand.glob.glob = real
        self.assertEqual(skill, self.skill)
        self.assertEqual(calls, [])

    def test_session_layout(self):
        os.environ.pop("HTML_VISUALIZER_BRAND_DIR")
        sess = os.path.join(os.environ["HOME"], "Library", "Application Support", "Claude", "local-agent-mode-sessions")
        good = os.path.join(sess, "u1", "u2", "rpm", "plugin_abc", "skills", "mr-living-presentation")
        shutil.copytree(self.skill, good)
        skill, _ = brand.find_skill()
        self.assertEqual(skill, good)
        # 更深、結構不對的不再被遞迴掃到
        shutil.rmtree(os.path.join(sess, "u1"))
        deep = os.path.join(sess, "a", "b", "c", "d", "e", "skills", "mr-living-presentation")
        shutil.copytree(self.skill, deep)
        skill, tried = brand.find_skill()
        self.assertIsNone(skill)
        self.assertTrue(any("local-agent-mode-sessions" in t for t in tried))

    def test_tiers_are_lazy(self):
        import types
        self.assertIsInstance(brand.search_tiers(), types.GeneratorType)


class TestGrayBrand(Base):
    """#7 品牌藍／促銷紅是灰色時，推導的綠黃紅仍要彼此分得開、文字可讀。"""

    def test_gray_swatches(self):
        for blue, promo in (("808080", "#888888"), ("1A1A1A", "#E4E4E4"), ("FFFFFF", "#000000")):
            self.write_skill(SKILL.replace('"1865FF"', f'"{blue}"').replace("#C34135", promo))
            res = brand.resolve()
            self.assertEqual(res["theme"], "mrl", (blue, promo, res["reason"]))
            t = brand.tokens(res["ci"])
            names = ("--green", "--yellow", "--red")
            for i, a in enumerate(names):
                for b in names[i + 1:]:
                    self.assertGreaterEqual(brand.delta_e(t[a], t[b]), brand.SEMANTIC_MIN_DE, (blue, a, b))
                self.assertGreaterEqual(brand.contrast(t[a], t[a + "-soft"]), 4.5, (blue, a))
                self.assertGreaterEqual(brand.contrast(t[a], "#FFFFFF"), 4.5, (blue, a))

    def test_real_ci_unchanged_by_floor(self):
        """飽和度下限不影響原本的品牌藍（推導值跟加下限前一樣）。"""
        t = brand.tokens(brand.resolve()["ci"])
        _, _, bs = brand._hls("#1865FF")
        self.assertGreater(bs * 0.55, brand.MIN_SAT["green"])
        self.assertGreater(bs * 0.9, brand.MIN_SAT["yellow"])
        self.assertTrue(t["--green"].startswith("#"))

    def test_collision_rejected(self):
        old = brand.status_colors
        brand.status_colors = lambda *a: {k: ("#555555", "#EEEEEE", "#CCCCCC") for k in ("green", "yellow", "red")}
        try:
            res = brand.resolve()
        finally:
            brand.status_colors = old
        self.assertEqual(res["theme"], "default")
        self.assertIn("太接近", res["reason"])


class TestInstall(unittest.TestCase):
    """#8 install.sh 只動自己裝的東西；help 獨立安裝改名 html-visualizer-help。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = os.path.join(self.tmp, "home")
        self.sk = os.path.join(self.home, ".agents", "skills")
        os.makedirs(os.path.join(self.sk, "help"))
        with open(os.path.join(self.sk, "help", "SKILL.md"), "w") as f:
            f.write("someone else")
        os.symlink("/nonexistent/chart", os.path.join(self.sk, "chart"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_sh(self, *args):
        import subprocess
        env = dict(os.environ, HOME=self.home)
        return subprocess.run(["bash", os.path.join(ROOT, "install.sh"), *args], env=env,
                              capture_output=True, text=True, check=True)

    def test_install_uninstall_respects_foreign(self):
        r = self.run_sh()
        self.assertIn("chart", r.stderr)
        self.assertEqual(os.readlink(os.path.join(self.sk, "chart")), "/nonexistent/chart")
        with open(os.path.join(self.sk, "help", "SKILL.md")) as f:
            self.assertEqual(f.read(), "someone else")
        hv = os.path.join(self.sk, "html-visualizer")
        self.assertEqual(os.readlink(hv), os.path.join(ROOT, "skills", "html-visualizer"))
        helpdir = os.path.join(self.sk, "html-visualizer-help")
        with open(os.path.join(helpdir, "SKILL.md"), encoding="utf-8") as f:
            self.assertIn("\nname: html-visualizer-help\n", f.read())
        self.assertTrue(os.path.isfile(os.path.join(helpdir, "references", "help.md")))
        self.run_sh()  # 重跑：覆蓋自己的，不出錯
        self.run_sh("--uninstall")
        self.assertFalse(os.path.lexists(hv))
        self.assertFalse(os.path.lexists(helpdir))
        self.assertTrue(os.path.isfile(os.path.join(self.sk, "help", "SKILL.md")))
        self.assertTrue(os.path.islink(os.path.join(self.sk, "chart")))

    def test_copy_mode_and_legacy_help(self):
        d = os.path.join(self.tmp, "t")
        os.makedirs(d)
        os.symlink(os.path.join(ROOT, "skills", "help"), os.path.join(d, "help"))  # 舊版腳本裝的
        self.run_sh("--copy", "--dir", d)
        self.assertFalse(os.path.lexists(os.path.join(d, "help")))
        self.assertTrue(os.path.isdir(os.path.join(d, "chart")) and not os.path.islink(os.path.join(d, "chart")))
        self.run_sh("--copy", "--dir", d)
        os.makedirs(os.path.join(d, "diagram-design-foreign"))
        self.run_sh("--uninstall", "--dir", d)
        self.assertEqual(sorted(os.listdir(d)), ["diagram-design-foreign"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
