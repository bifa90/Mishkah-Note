#!/usr/bin/env python3
"""Build ``docs/G3B_CHECKLIST.html`` — the manual gate as a page you can fill in.

Why a page and not a markdown table: the table answers *what* to test, not *why*
or *what happens if it fails*, and it cannot hold a verdict, a note, or a
drawing.  This generator writes a self-contained HTML file (no network, no
dependencies) with one card per item: what to run, what to expect, a small
diagram, the impact of failure, my recommendation, and three answer options plus
empty note.

    python tools/build_g3b_checklist.py            # writes docs/G3B_CHECKLIST.html
    python tools/build_g3b_checklist.py --check    # fails if the file is stale

Verdicts live in the browser's localStorage and export as markdown; nothing is
sent anywhere.
"""

from __future__ import annotations

import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "G3B_CHECKLIST.html"

GROUPS = {
    "a": "أ · الإقلاع",
    "b": "ب · العربية والاتجاه",
    "c": "ج · اللغات والخطوط",
    "d": "د · الملفات والسلامة",
    "e": "هـ · العرض والطباعة",
}

# ---------------------------------------------------------------- diagrams
# Every shape is a 240×104 inline SVG drawn from four primitives.  Colours are
# presentation attributes, not classes: the diagram must look the same in the
# browser, in a print-to-PDF, in an e-mail client, and in QSvgRenderer (which is
# how tools/check_checklist_shapes.py proves they are not blank).

W, H = 240, 104

INK, DIM, TINY = "#1f2d34", "#7d94a1", "#9fb3bd"
BRAND, BRANDINK = "#5FC1EA", "#1b6f8f"
OK, BAD, WARN = "#1e8e52", "#c8382f", "#b1761b"
PANE, PANE2, LINE, CHIP = "#ffffff", "#eef6fa", "#dbe6ec", "#eef6fa"
WARNBG, WARNS = "#fdf1d8", "#ecd39a"
DARKBK, DARKCHIP, DARKINK, DARKDIM = "#111b20", "#1b2a31", "#dbe9ef", "#8fa6b1"
HIGHLIGHT = "#ffe066"


def _svg(body: str) -> str:
    return (f'<svg class="shape" viewBox="0 0 {W} {H}" role="img" '
            f'aria-hidden="true">{body}</svg>')


def _frame(inner: str, title: str = "") -> str:
    head = (f'<text x="10" y="14" font-size="8" fill="{TINY}" '
            f'font-family="monospace">{escape(title)}</text>') if title else ""
    return (f'<rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="7" '
            f'fill="{PANE}" stroke="{LINE}"/>'
            f'<line x1="2" y1="22" x2="{W - 2}" y2="22" stroke="{LINE}"/>' + head + inner)


def _t(x, y, text, fill=INK, size=9, anchor="start", weight="") -> str:
    extra = f' font-weight="{weight}"' if weight else ""
    return (f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" '
            f'fill="{fill}"{extra}>{escape(text)}</text>')


def _rect(x, y, w, h, fill=INK, r=2, stroke="") -> str:
    edge = f' stroke="{stroke}"' if stroke else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" '
            f'fill="{fill}"{edge}/>')


def _chip(x, y, w, h) -> str:
    return _rect(x, y, w, h, CHIP, 4, LINE)


def _lines(rows) -> str:
    """Right-aligned text lines with a highlighted insertion point."""
    return "".join(rows)


def shape_terminal() -> str:
    rows = [_t(12, 38, "$ mishkah --version", DIM, 9),
            _t(12, 56, "1.0.02", OK, 12, weight="600"),
            _t(12, 76, "$ mishkah --help", DIM, 9),
            _t(12, 90, "--version  --help  --new", INK, 8)]
    return _svg(_frame("".join(rows), "terminal"))


def _brand_block(hl: str = "") -> str:
    """The welcome page block: mark, Arabic name, English name, version."""
    body = [] if hl else [_t(232, 34, "ملف  تحرير  عرض  تنسيق", DIM, 7, "end")]
    body += [
        _rect(186, 40, 30, 30, BRAND, 5),
        _t(201, 61, "\u25c6", PANE, 12, "middle"),
        _t(232, 85, "مفكرة مشكاة", INK, 12, "end", "700"),
        _t(232, 97, "Mishkah Note", DIM, 8, "end"),
    ]
    if hl:
        body.append(f'<rect x="150" y="30" width="90" height="74" rx="6" '
                    f'fill="none" stroke="{BRAND}" stroke-width="1.6" '
                    f'stroke-dasharray="4 3"/>')
        body.append(_t(154, 44, hl, BRANDINK, 8))
    return _svg(_frame("".join(body), "welcome · RTL"))


def shape_home_brand() -> str:
    return _brand_block()


def shape_home_round4() -> str:
    return _brand_block("جولة 4")


def shape_tab_close() -> str:
    body = "".join([
        _rect(10, 28, 54, 16, PANE2, 3, LINE), _t(16, 40, "البداية", INK, 7),
        _t(54, 40, "×", DIM, 9),
        _t(80, 40, "+", DIM, 9),
        _t(12, 66, "Ctrl+W  →  آخر تبويب", DIM, 8),
        _rect(10, 74, 220, 20, PANE2, 3, LINE),
        _t(222, 88, "تعود صفحة البداية", OK, 8, "end"),
    ])
    return _svg(_frame(body, "tabs"))


def shape_rtl_lines() -> str:
    body = "".join([
        _rect(40, 32, 188, 3, INK, 1), _rect(90, 42, 138, 3, INK, 1),
        _rect(120, 52, 108, 3, DIM, 1), _rect(70, 62, 158, 3, INK, 1),
        _rect(228, 28, 2, 14, BRAND, 0),
        _t(232, 88, "المحاذاة من اليمين ↤", OK, 8, "end"),
    ])
    return _svg(_frame(body, "RTL"))


def shape_bidi() -> str:
    body = "".join([
        _t(228, 38, "مرحبا hello 123", INK, 8, "end"),
        _rect(120, 42, 108, 2, DIM, 1),
        _t(12, 62, "third paragraph", INK, 8),
        _rect(12, 66, 74, 2, DIM, 1),
        _t(228, 88, "عربية ← يمين · English ← يسار", OK, 7, "end"),
    ])
    return _svg(_frame(body, "mixed"))


def shape_direction_lock() -> str:
    body = "".join([
        _t(12, 40, "Ctrl+Shift+→ · ← · A", DIM, 8),
        _chip(12, 48, 60, 18), _t(42, 61, "RTL", INK, 8, "middle"),
        _chip(78, 48, 60, 18), _t(108, 61, "LTR", INK, 8, "middle"),
        _chip(144, 48, 60, 18), _t(174, 61, "Auto", INK, 8, "middle"),
        _t(12, 86, "★ «معدَّل» لا تظهر", OK, 8),
        _t(232, 86, "★ ✗", BAD, 10, "end"),
    ])
    return _svg(_frame(body, "direction"))


def shape_menu_font() -> str:
    body = "".join([
        _t(232, 34, "فائل  ترميم  نظارہ  شکل  ٹیب  مدد", INK, 8, "end"),
        f'<rect x="150" y="26" width="86" height="12" rx="3" fill="none" '
        f'stroke="{BRAND}" stroke-width="1.4" stroke-dasharray="4 3"/>',
        _t(12, 56, "النستعليق في 12px:", DIM, 7),
        _t(12, 70, "ذيل يصطدم بالسطر ↓", BAD, 7),
        _t(12, 90, "Noto Sans Arabic ← مستقيم", OK, 8),
    ])
    return _svg(_frame(body, "chrome face"))


def shape_lang_switch() -> str:
    body = "".join([
        _t(12, 40, "ar → ur → ru → en", DIM, 8),
        _chip(12, 48, 210, 14),
        _t(208, 59, "كل النصوص تتبع اللغة الحالية", OK, 7, "end"),
        _t(12, 80, "لا كلمة عالقة بلغة سابقة", INK, 8),
        _t(232, 92, "✓", OK, 12, "end"),
    ])
    return _svg(_frame(body, "switch"))


def shape_font_rows() -> str:
    rows = [
        _t(10, 36, "lang", DIM, 7), _t(58, 36, "asked", DIM, 7),
        _t(128, 36, "resolved", DIM, 7),
        _t(10, 54, "ar", INK, 8), _t(58, 54, "IBM Plex", DIM, 8),
        _t(128, 54, "IBM Plex Sans Arabic", OK, 8),
        _t(10, 70, "ur", INK, 8), _t(58, 70, "Noto Sans", DIM, 8),
        _t(128, 70, "Noto Sans Arabic", OK, 8),
        _t(10, 90, "ٹ ڈ ڑ ں ے ھ   →   ok", INK, 8),
    ]
    return _svg(_frame("".join(rows), "font_report"))


def shape_bytes() -> str:
    body = "".join([
        _t(12, 40, "plan.md  →  plan-copy.md", DIM, 8),
        _chip(12, 48, 30, 12), _chip(46, 48, 30, 12),
        _chip(80, 48, 30, 12), _chip(114, 48, 30, 12),
        _t(160, 58, "بايتات متطابقة", OK, 8),
        _t(12, 82, "EF BB BF (BOM) ✗", BAD, 8),
        _t(232, 82, "CRLF ✗", BAD, 8, "end"),
    ])
    return _svg(_frame(body, "bytes"))


def shape_external_change() -> str:
    body = "".join([
        _rect(12, 30, 62, 30, PANE2, 3, LINE), _t(18, 44, "المحرّر", INK, 7),
        _t(18, 56, "الخارج", DIM, 7),
        _rect(96, 30, 62, 30, PANE2, 3, LINE), _t(102, 44, "القرص", INK, 7),
        _t(102, 56, "+سطر", BAD, 7),
        _t(170, 50, "≠", BAD, 13),
        _rect(12, 70, 216, 20, WARNBG, 3, WARNS),
        _t(222, 84, "تغيّر الملف — لن أكتب فوقه", INK, 7, "end"),
    ])
    return _svg(_frame(body, "conflict"))


def shape_big_file() -> str:
    body = "".join([
        _t(12, 40, "big.txt · 50 MB", INK, 8),
        _rect(12, 48, 216, 10, CHIP, 5),
        _rect(12, 48, 120, 10, BRAND, 5),
        _t(12, 74, "معاينة للقراءة فقط + «افتح الملف كاملًا»", DIM, 7),
        _t(232, 92, "بلا تجمّد", OK, 8, "end"),
    ])
    return _svg(_frame(body, "large file"))


def shape_encoding_chip() -> str:
    body = "".join([
        _t(228, 40, "نص بترميز ويندوز العربي", INK, 9, "end"),
        _chip(150, 62, 82, 18),
        _t(191, 75, "Windows-1256", INK, 8, "middle"),
        _t(12, 75, "الحفظ بالترميز نفسه", OK, 7),
    ])
    return _svg(_frame(body, "encoding"))


def shape_markdown_toggle() -> str:
    body = "".join([
        _t(12, 44, "# عنوان", DIM, 9),
        _t(78, 44, "→", DIM, 9),
        _t(104, 44, "عنوان", INK, 11, weight="700"),
        _rect(12, 56, 216, 1, LINE, 0),
        _t(12, 74, "البايتات لا تتغيّر · ★ لا تظهر", OK, 8),
        _t(232, 94, "Ctrl+Shift+M", DIM, 7, "end"),
    ])
    return _svg(_frame(body, "markdown"))


def shape_pdf_pages() -> str:
    pages = "".join([
        f'<rect x="{34 + i * 14}" y="{38 - i * 3}" width="48" height="44" rx="3" '
        f'fill="{PANE2}" stroke="{LINE}" transform="rotate({(i - 1) * 4} 58 60)"/>'
        for i in range(3)
    ])
    body = pages + "".join([
        _t(140, 46, "PDF", INK, 11, weight="700"),
        _t(140, 60, "عربي غير مقطوع", OK, 7),
        _t(140, 72, "ترقيم مستمر", DIM, 7),
        _t(140, 88, "افتحه بعينك", BAD, 7),
    ])
    return _svg(_frame(body, "print → file"))


def shape_search_dark() -> str:
    body = "".join([
        _rect(2, 2, W - 4, H - 4, DARKBK, 7),
        _rect(12, 26, 150, 14, DARKCHIP, 3),
        _t(18, 36, "بحث: تسليم", DARKINK, 7),
        _t(226, 36, "Esc ✕", DARKDIM, 7, "end"),
        _rect(12, 50, 216, 42, DARKCHIP, 3),
        _t(20, 66, "… الجمعة  تسليم  في …", DARKINK, 8),
        _rect(66, 59, 46, 11, HIGHLIGHT, 2),
        _t(20, 86, "التظليل مقروء · F3 ينتقل", OK, 7),
    ])
    return _svg(body)


SHAPES = {
    "terminal": shape_terminal,
    "home": shape_home_brand,
    "home4": shape_home_round4,
    "tabs": shape_tab_close,
    "rtl": shape_rtl_lines,
    "bidi": shape_bidi,
    "direction": shape_direction_lock,
    "menufont": shape_menu_font,
    "langswitch": shape_lang_switch,
    "fontrows": shape_font_rows,
    "bytes": shape_bytes,
    "conflict": shape_external_change,
    "bigfile": shape_big_file,
    "encoding": shape_encoding_chip,
    "markdown": shape_markdown_toggle,
    "pdf": shape_pdf_pages,
    "darksearch": shape_search_dark,
}

# ------------------------------------------------------------------- items
# rec: what I recommend you expect, and how sure I am (the "توصية" badge).
# if_fail: what I would look at first, so a ❌ arrives with a starting point.

ITEMS = [
    dict(n=1, group="a", title="رقم الإصدار والمساعدة",
         shape="terminal",
         cmd="mishkah --version && mishkah --help",
         do="شغّل الأمرين في الطرفية.",
         expect="`1.0.02` وحدها في الأول، وقائمة خيارات في الثاني بلا أثر استثناء.",
         why="كل حزمة ووسم صفحة تنزيل تقرأ هذا الرقم؛ رقم خاطئ = مستخدم يظن أنه "
             "نزّل إصدارًا وهو نزّل غيره، وبوابة النشر تمرّ على رقم لا يطابق الملف.",
         rec="أتوقع النجاح — ثقة عالية (اختبار آلي يغطيه)",
         level="high",
         if_fail="أفحص `_version.txt` والوسم أولًا؛ الفشل هنا يوقف النشر كله."),
    dict(n=2, group="a", title="الإقلاع بلا ملفات",
         shape="home",
         cmd="mishkah",
         do="شغّل التطبيق من مجلد فارغ ولا تفتح شيئًا.",
         expect="صفحة البداية: الشعار والاسم والإصدار والأزرار — لا مستند فارغ، "
                "ولا لافتة خطأ، ولا نافذة منبثقة.",
         why="أول ثانيتين يحكم فيهما المستخدم على البرنامج. مستند فارغ إضافي يعني "
             "تبويبًا يجب إغلاقه يدويًا قبل أي عمل.",
         rec="أتوقع النجاح — ثقة عالية",
         level="high",
         if_fail="أتحقق من إعداد `restore_session` ومن مسار `show_home()`."),
    dict(n=3, group="a", title="إغلاق آخر تبويب",
         shape="tabs",
         cmd="Ctrl+N ثم Ctrl+W",
         do="أنشئ تبويبًا ثم أغلقه.",
         expect="تعود صفحة البداية ولا تُغلق النافذة (إلا إن كان إعداد «آخر تبويب "
                "← إغلاق النافذة» مفعّلًا عندك).",
         why="من يغلق تبويبه الأخير لا يريد أن يخرج من البرنامج؛ هذا قرار مُعلن "
             "في الإعدادات، وكل مستخدم يمرّ به يوميًا.",
         rec="أتوقع النجاح — ثقة متوسطة (يعتمد على إعدادك)",
         level="medium",
         if_fail="أذكر قيمة `last_tab_action` في البلاغ قبل أن أعده عيبًا."),
    dict(n=4, group="b", title="الكتابة العربية من أول حرف",
         shape="rtl",
         cmd="Ctrl+N ثم اكتب: مرحبًا، هذه أول فقرة.",
         do="اكتب فقرتين عربيتين، ثم `Enter` بينهما.",
         expect="المحاذاة من اليمين، والمؤشر في أول السطر على اليمين، والسطر الأول "
                "لا يُزحزح ولا يترك فراغًا تحته.",
         why="الاتجاه الخاطئ لا يجعل التطبيق «أقل جودة» بل بلا معنى لجمهوره "
             "العربي؛ لهذا وُضع قبل أي ميزة في ترتيب الأولويات.",
         rec="أتوقع النجاح — ثقة عالية",
         level="high",
         if_fail="أراجع كشف الاتجاه التلقائي (`text_direction`) وافتراض الاتجاه."),
    dict(n=5, group="b", title="خلط العربية والإنجليزية في مستند",
         shape="bidi",
         cmd="افتح mixed.txt",
         do="افتح ملفًا فيه فقرات عربية وإنجليزية متبادلة.",
         expect="كل فقرة تأخذ اتجاهها من أول حرف قوي فيها، بلا لمس أي مفتاح اتجاه.",
         why="أكثر مستند حقيقي فيه لغتان: اسم برنامج، أمر طرفية، رابط. إن فشل هذا "
             "فسيفشل في معظم الملفات لا في حالة نادرة.",
         rec="أتوقع النجاح — ثقة عالية",
         level="high",
         if_fail="أختبر بمستندك نفسه؛ قد يكون السبب حرفًا محايدًا في بداية الفقرة."),
    dict(n=6, group="b", title="تثبيت الاتجاه لا يعلّم «معدَّل»",
         shape="direction",
         cmd="Ctrl+Shift+→ ثم ← ثم Ctrl+Shift+A",
         do="بدّل الاتجاه يمينًا ويسارًا ثم أعد التلقائي في مستند غير معدَّل.",
         expect="الاتجاه يتغيّر فورًا، وعلامة «معدَّل» لا تظهر، و`Ctrl+S` لا يسأل "
                "عن حفظ شيء.",
         why="«معدَّل» كاذبة تدفع إلى حفظ لا حاجة له، أو إلى خوف من إغلاق يظن "
             "المستخدم أنه سيفقد شيئًا.",
         rec="أتوقع النجاح — ثقة عالية",
         level="high",
         if_fail="أفصل تغيير العرض عن تغيير المستند في `DocumentModel`."),
    dict(n=7, group="b", title="صفحة البداية: الكتلة الثابتة (جولة 4)",
         shape="home4",
         cmd="افتح التطبيق بلا ملفات والتقط لقطة",
         do="تأمّل أعلى صفحة البداية.",
         expect="بالترتيب: الشعار ← **مفكرة مشكاة** ← **Mishkah Note** ← "
                "**الإصدار 1.0.02**، والكتلة كلها مع الأزرار على **يمين** الشاشة.",
         why="هذا ما أصلحناه للتو: الاسم كان ينفصل عن الأزرار، والكلام في القوائم "
             "اليسرى كان يبقى يسارًا في واجهة عربية. اختبار البكسلات يثبته، ولقطتك "
             "تثبت ما يراه إنسان.",
         rec="أتوقع النجاح — ثقة عالية (مُثبت بفحص يقرأ البكسلات)",
         level="high",
         if_fail="أراجع `_align_to_direction()` و`AlignAbsolute` في بيئتك."),
    dict(n=8, group="c", title="الأردية: قوائم بخط مستقيم",
         shape="menufont",
         cmd="Format ▸ Language ▸ اردو",
         do="بدّل لغة الواجهة إلى الأردية.",
         expect="الواجهة تنقلب يمينًا، والقوائم تُعاد كتابتها **فورًا** بخط نسخي "
                "مستقيم (Noto Sans Arabic)، لا بالنستعليق المائل.",
         why="النستعليق خط كتابة ممتاز وواجهة رديئة: ذيوله تصطدم بالأسطر التالية "
             "عند 11–13 بكسل، وهو ما جعل قوائم الأردية تبدو مكسورة.",
         rec="أتوقع النجاح — ثقة عالية (الخط مضغوط داخل الحزمة)",
         level="high",
         if_fail="أطلب ناتج `font_report.py` من جهازك — إن ظهر DejaVu فالمضمّن لم يُسجَّل."),
    dict(n=9, group="c", title="تبديل سريع بين اللغات",
         shape="langswitch",
         cmd="ar → ur → ru → en",
         do="بدّل أربع لغات بسرعة ثم ارجع إلى صفحة البداية.",
         expect="لا نص عالق بلغة سابقة: القوائم والأزرار والسطر التعريفي بلغة "
                "الواجهة الحالية، والاسم والإصدار كما هما دائمًا.",
         why="الميزة معلنة («تبديل فوري بلا إعادة تشغيل»)؛ نص عالق يجعلها ميزة "
             "موجودة في الوصف وغائبة في الاستخدام.",
         rec="أتوقع النجاح — ثقة عالية",
         level="high",
         if_fail="أبحث عن أي واجهة لا تُستدعى لها `retranslate()`."),
    dict(n=10, group="c", title="تقرير الخطوط على جهازك",
         shape="fontrows",
         cmd="python tools/font_report.py --check; echo $?",
         do="شغّل الأمر داخل بيئة التطبيق.",
         expect="`ar` ← IBM Plex Sans Arabic، و`ur` ← Noto Sans Arabic، وعمود "
                "الحروف الأردية `ok`، والنتيجة `0`.",
         why="هذا يحوّل «لم يُختبر على macOS/Windows» إلى شيء قابل للفحص: أرسل "
             "المخرجات من جهازك، فتصبح مُختبرة أو كاشفة لعيب قبل النشر.",
         rec="أتوقع النجاح — ثقة عالية على لينكس، **متوسطة على macOS/Windows**",
         level="medium",
         if_fail="انسخ السطور التي تبدأ بـ`!`؛ كل واحدة تحدد الملف أو العائلة الغائبة."),
    dict(n=11, group="d", title="الحفظ لا يضيف بايتًا",
         shape="bytes",
         cmd="cmp ملفَين أو سكربت البايتات في الدليل",
         do="انسخ ملفًا، عدّل كلمة واحدة، احفظ، ثم قارن البايتات.",
         expect="لا BOM مضاف، ولا تحوّل LF إلى CRLF، والفرق محصور في الكلمة المعدَّلة.",
         why="ملفات git تُقرأ بايتًا بايتًا: إضافة BOM تجعل كل سطر «معدَّلًا» في "
             "تاريخ المستودع، والمستخدم يظن أنه أفسد ملفه.",
         rec="أتوقع النجاح — ثقة عالية",
         level="high",
         if_fail="أراجع `encoding.py`: هل يُحفظ بالترميز المكتشف نفسه؟"),
    dict(n=12, group="d", title="تعديل خارجي أثناء الفتح",
         shape="conflict",
         cmd="عدّل plan.md من محرّر آخر ثم Ctrl+S هنا",
         do="افتح ملفًا، غيّره من خارج التطبيق، ثم احفظ من التطبيق.",
         expect="لافتة بأن الملف تغيّر على القرص، ولا كتابة فوق التعديل الخارجي "
                "إلا بموافقتك الصريحة.",
         why="هذا أخطر مسار في أي محرّر: كتابة فوق عمل أُنجز في مكان آخر. كل ما "
             "بنيناه في «سلامة البيانات» يقف على هذا السطر.",
         rec="أتوقع النجاح — ثقة عالية",
         level="high",
         if_fail="أعده فورًا؛ هذا البند وحده يوقف النشر إن فشل."),
    dict(n=13, group="d", title="ملف كبير (٥٠ م.ب)",
         shape="bigfile",
         cmd="افتح ~/g3b/big.txt",
         do="افتح ملفًا نصيًا كبيرًا.",
         expect="شريط تقدّم ثم المستند بلا تجمّد؛ وفوق السقف المضبوط تظهر معاينة "
                "للقراءة فقط مع زر «افتح الملف كاملًا».",
         why="وعد «لا يتجمّد» جزء من وعد المنتج الأساسي؛ ملف واحد كبير يهدم الثقة "
             "أكثر من عشر ميزات ناقصة.",
         rec="أتوقع النجاح — ثقة متوسطة (يعتمد على سرعة قرصك)",
         level="medium",
         if_fail="أطلب رقم السقف المضبوط في إعداداتك وحجم الملف بالضبط."),
    dict(n=14, group="d", title="ترميز قديم (Windows-1256)",
         shape="encoding",
         cmd="افتح legacy.txt",
         do="افتح ملفًا بترميز عربي قديم، عدّل سطرًا، احفظ.",
         expect="العربية تظهر سليمة، وشريحة شريط الحالة تقول `Windows-1256`، "
                "والحفظ بالترميز نفسه لا UTF-8.",
         why="أرشيف عربي كامل على هذا الترميز؛ تحويله الصامت إلى UTF-8 يجعل بقية "
             "برامج المستخدم تقرأ الملف مشوّهًا.",
         rec="أتوقع النجاح — ثقة عالية",
         level="high",
         if_fail="أتحقق من `detect_encoding` على أول 64 KiB فقط."),
    dict(n=15, group="e", title="Markdown حيّ لا يمسّ الملف",
         shape="markdown",
         cmd="Ctrl+Shift+M",
         do="فعّل العرض المنسّق على ملف Markdown، ثم احفظ، ثم أوقفه.",
         expect="يتنسّق العرض، و«معدَّل» لا تظهر عند التبديل، وبعد الإيقاف يعود "
                "النص الخام حرفًا بحرف.",
         why="الوعد الحرفي: «ما تراه هو ما كتبته — لا أكثر ولا أقل». أي تغيير في "
             "الملف بسبب العرض يكسر هذا الوعد ويكسر معه git.",
         rec="أتوقع النجاح — ثقة عالية",
         level="high",
         if_fail="أراجع أن التنسيق طبقة عرض لا تعديل على المخزن."),
    dict(n=16, group="e", title="طباعة عربية إلى PDF",
         shape="pdf",
         cmd="Ctrl+P ▸ Print to File ▸ plan.pdf",
         do="اطبع مستندًا عربيًا إلى ملف PDF ثم افتحه.",
         expect="ملف يُفتح، حروف عربية غير مقطوعة ولا معكوسة، سطور لا تتداخل، "
                "وترقيم مستمر.",
         why="الطبع مسار مُختبر آليًا (عدد الصفحات والخط المضمّن)، لكن **عينك** "
             "وحدها ترى القطع والترتيب؛ والطابعة الورقية تبقى غير مُختبرة.",
         rec="أتوقع النجاح — ثقة عالية في PDF، ولا ثقة في الطابعة الورقية",
         level="medium",
         if_fail="أراجع مقاس الورق والهوامش واتجاه الصفحة في حوار الطابعة."),
    dict(n=17, group="e", title="البحث في السمة الداكنة",
         shape="darksearch",
         cmd="Ctrl+F ▸ تسليم ▸ F3 ▸ Esc",
         do="ابحث في السمة الداكنة ثم تنقّل بين النتائج وأغلق الشريط.",
         expect="أول نتيجة مظلَّلة وواضحة على الخلفية الداكنة، `F3` ينتقل، `Esc` "
                "يعيد التركيز للمستند بلا أثر باقٍ.",
         why="ما يفشل عادة في السمة الداكنة هو التظليل لا البحث: نص أصفر على خلفية "
             "داكنة يختفي، والمستخدم يظن أن البحث لم يجد شيئًا.",
         rec="أتوقع النجاح — ثقة متوسطة (ألوان الشفافية تعتمد على النظام)",
         level="medium",
         if_fail="أراجع ألوان `search` في ملف السمة الداكنة."),
]

CSS = """
:root{
  --brand:#5FC1EA; --ink:#1f2d34; --dim:#607684; --line:#dbe6ec;
  --bg:#f6fafc; --card:#ffffff; --ok:#1e8e52; --bad:#c8382f; --warn:#b1761b;
  --hl:#fff3c4;
}
@media (prefers-color-scheme: dark){
  :root{ --ink:#e8f1f5; --dim:#9fb3bd; --line:#28414c; --bg:#101a1f;
         --card:#16242b; --hl:#4a4326; }
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:"IBM Plex Sans Arabic","Noto Sans Arabic","Segoe UI",Tahoma,sans-serif;
  line-height:1.75;font-size:16px}
header.top{position:sticky;top:0;z-index:5;background:var(--card);
  border-bottom:1px solid var(--line);padding:14px 20px;
  display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between}
h1{font-size:20px;margin:0}
h1 small{font-weight:400;color:var(--dim);font-size:13px;display:block}
.bar{height:8px;background:var(--line);border-radius:6px;overflow:hidden;flex:1;min-width:140px}
.bar>i{display:block;height:100%;width:0;background:var(--brand);transition:width .25s}
.counter{font-variant-numeric:tabular-nums;font-size:14px;color:var(--dim)}
button{font:inherit;cursor:pointer;border:1px solid var(--line);background:var(--card);
  color:var(--ink);border-radius:8px;padding:6px 12px}
button.primary{background:var(--brand);border-color:var(--brand);color:#06222e;font-weight:600}
button:disabled{opacity:.5;cursor:not-allowed}
main{max-width:1180px;margin:0 auto;padding:22px 18px 80px}
.intro{background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:16px 18px;margin-bottom:18px}
.intro p{margin:.4em 0}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:13px;color:var(--dim);margin-top:8px}
.legend b{color:var(--ink)}
.grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(330px,1fr))}
article.item{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:16px 16px 12px;display:flex;flex-direction:column;gap:10px;
  border-inline-start:4px solid var(--line)}
article.item[data-verdict="ok"]{border-inline-start-color:var(--ok)}
article.item[data-verdict="bad"]{border-inline-start-color:var(--bad)}
article.item[data-verdict="later"]{border-inline-start-color:var(--warn)}
.head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.num{font-weight:700;font-variant-numeric:tabular-nums;background:var(--brand);
  color:#06222e;border-radius:8px;padding:1px 9px;font-size:14px}
.title{font-weight:700;font-size:17px}
.group{font-size:12px;color:var(--dim);border:1px solid var(--line);border-radius:999px;
  padding:0 8px}
.shape{width:100%;height:auto;max-height:150px;background:transparent}
.shape text{font-family:"IBM Plex Sans Arabic","Noto Sans Arabic",Tahoma,sans-serif}
.pane{fill:#fff;stroke:var(--line);stroke-width:1}
.pane2{fill:#eef6fa;stroke:var(--line)}
.rule{stroke:var(--line);stroke-width:1}
.rule2{stroke:var(--line);stroke-width:1}
.ink{fill:#1f2d34}
.dim{fill:#7d94a1}
.tiny{fill:#9fb3bd}
.brand{fill:var(--brand)}
.brandink{fill:#1b6f8f}
.ok{fill:#1e8e52}
.bad{fill:#c8382f}
.chip{fill:#eef6fa;stroke:#dbe6ec}
.tab{fill:#eef6fa;stroke:#dbe6ec}
.hl{fill:none;stroke:var(--brand);stroke-width:1.6;stroke-dasharray:4 3}
.hl2{fill:#ffe066;opacity:.45}
.warn{fill:#fdf1d8;stroke:#ecd39a}
.dark{fill:#111b20;stroke:#28414c}
.darkchip{fill:#1b2a31}
.darkink{fill:#dbe9ef}
.darkdim{fill:#8fa6b1}
code{background:#eef6fa;border:1px solid var(--line);border-radius:6px;
  padding:1px 6px;font-size:13px;direction:ltr;display:inline-block;
  font-family:"IBM Plex Mono","DejaVu Sans Mono",monospace}
.run{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.run code{flex:1;min-width:180px;overflow:auto;white-space:nowrap}
.label{font-size:12px;color:var(--dim);text-transform:uppercase;letter-spacing:.04em}
.rec{font-size:13px;border-radius:10px;padding:8px 10px;display:flex;gap:8px;
  align-items:flex-start;background:#eef6fa;border:1px solid var(--line)}
.rec[data-level="medium"]{background:#fdf1d8;border-color:#ecd39a}
.rec b{white-space:nowrap}
.verdicts{display:flex;gap:6px;flex-wrap:wrap;margin-top:2px}
.verdicts label{display:flex;align-items:center;gap:6px;border:1px solid var(--line);
  border-radius:999px;padding:4px 10px;font-size:13px;cursor:pointer}
.verdicts input{accent-color:var(--brand)}
.verdicts label.ok:has(input:checked){border-color:var(--ok);background:#e8f6ee}
.verdicts label.bad:has(input:checked){border-color:var(--bad);background:#fbeceb}
.verdicts label.later:has(input:checked){border-color:var(--warn);background:#fdf1d8}
textarea{width:100%;min-height:56px;resize:vertical;font:inherit;font-size:13px;
  border:1px solid var(--line);border-radius:8px;padding:8px;background:var(--bg);
  color:var(--ink)}
footer.summary{position:fixed;inset-inline:0;bottom:0;background:var(--card);
  border-top:1px solid var(--line);padding:8px 18px;display:flex;gap:12px;
  align-items:center;flex-wrap:wrap;font-size:14px;z-index:6}
.fail-list{color:var(--bad);font-size:13px}
@media print{
  header.top{position:static}.grid{grid-template-columns:1fr 1fr}
  footer.summary{display:none}article.item{break-inside:avoid}
  .verdicts label:has(input:checked){outline:2px solid var(--ink)}
}
"""

JS = """
const KEY = 'mishkah-g3b-v1';
// file:// and private windows can refuse localStorage; the page must still work,
// it just stops remembering between visits.
const memory = {};
const state = () => {
  try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch { return memory.state || {}; }
};
const save = (s) => {
  memory.state = s;
  try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* read-only visit */ }
};

function refresh(){
  const s = state();
  let done = 0, bad = [], later = [];
  document.querySelectorAll('article.item').forEach(card => {
    const n = card.dataset.item;
    const verdict = s[n]?.verdict || '';
    card.dataset.verdict = verdict;
    if (verdict) done++;
    if (verdict === 'bad') bad.push(n);
    if (verdict === 'later') later.push(n);
  });
  const total = document.querySelectorAll('article.item').length;
  document.querySelector('.bar > i').style.width = (100 * done / total) + '%';
  document.querySelector('.counter').textContent = `${done}/${total}`;
  document.getElementById('fails').textContent =
    bad.length ? `فشل: ${bad.map(n => '#' + n).join(' ')}` : '';
  document.getElementById('later').textContent =
    later.length ? `لم يُجرَّب: ${later.length}` : '';
}

document.addEventListener('change', (e) => {
  const card = e.target.closest('article.item');
  if (!card || !e.target.matches('input[type=radio]')) return;
  const s = state();
  s[card.dataset.item] = {...(s[card.dataset.item] || {}), verdict: e.target.value};
  save(s); refresh();
});

document.addEventListener('input', (e) => {
  const card = e.target.closest('article.item');
  if (!card || !e.target.matches('textarea')) return;
  const s = state();
  s[card.dataset.item] = {...(s[card.dataset.item] || {}), note: e.target.value};
  save(s);
});

document.addEventListener('click', async (e) => {
  const copy = e.target.closest('[data-copy]');
  if (copy){
    try { await navigator.clipboard.writeText(copy.dataset.copy); }
    catch { const t = document.createElement('textarea'); t.value = copy.dataset.copy;
            document.body.appendChild(t); t.select(); document.execCommand('copy'); t.remove(); }
    const was = copy.textContent; copy.textContent = 'نُسخ';
    setTimeout(() => copy.textContent = was, 1200);
    return;
  }
  if (e.target.id === 'export'){
    const s = state();
    const lines = ['| # | البند | النتيجة | ملاحظة |', '|---|---|---|---|'];
    document.querySelectorAll('article.item').forEach(card => {
      const n = card.dataset.item;
      const title = card.querySelector('.title').textContent.trim();
      const v = s[n]?.verdict || '';
      const mark = v === 'ok' ? '✅' : v === 'bad' ? '❌' : v === 'later' ? '⏳' : '';
      const note = (s[n]?.note || '').replace(/\\n/g, ' ').replace(/\\|/g, '\\\\|');
      lines.push(`| ${n} | ${title} | ${mark} | ${note} |`);
    });
    const text = lines.join('\\n');
    try { await navigator.clipboard.writeText(text); alert('نُسخ الجدول — الصقه في المحادثة.'); }
    catch { window.prompt('انسخ الجدول:', text); }
    return;
  }
  if (e.target.id === 'clear'){
    if (!confirm('مسح كل ما أجبت به؟')) return;
    try { localStorage.removeItem(KEY); } catch { /* nothing stored */ }
    location.reload();
  }
});

document.addEventListener('DOMContentLoaded', () => {
  const s = state();
  document.querySelectorAll('article.item').forEach(card => {
    const entry = s[card.dataset.item] || {};
    if (entry.verdict){
      const radio = card.querySelector(`input[value="${entry.verdict}"]`);
      if (radio) radio.checked = true;
    }
    if (entry.note){
      const area = card.querySelector('textarea');
      if (area) area.value = entry.note;
    }
  });
  refresh();
});
"""

VERDICTS = (("ok", "✅ نجح"), ("bad", "❌ فشل"), ("later", "⏳ لم أجرّبه"))


def card(item: dict) -> str:
    shape = SHAPES[item["shape"]]()
    rec_level = item["level"]
    rec_icon = {"high": "✅", "medium": "🟡"}[rec_level]
    radios = "\n".join(
        f'<label class="{value}"><input type="radio" name="v{item["n"]}" '
        f'value="{value}"> {text}</label>'
        for value, text in VERDICTS)
    cmd = item.get("cmd", "")
    cmd_html = ""
    if cmd:
        cmd_html = (f'<div class="run"><code>{escape(cmd)}</code>'
                    f'<button data-copy="{escape(cmd, quote=True)}">نسخ</button></div>')
    return f"""
<article class="item" data-item="{item['n']}">
  <div class="head">
    <span class="num">{item['n']}</span>
    <span class="title">{escape(item['title'])}</span>
    <span class="group">{escape(GROUPS[item['group']])}</span>
  </div>
  {cmd_html}
  <div>
    <div class="label">ما تفعله · do</div>
    <div>{_md(item['do'])}</div>
  </div>
  <div>
    <div class="label">ما تتوقعه · expect</div>
    <div>{_md(item['expect'])}</div>
  </div>
  <figure>
    <div class="label">شكل مبسط · what it looks like</div>
    {shape}
  </figure>
  <div>
    <div class="label">التأثير إن فشل · why it matters</div>
    <div>{escape(item['why'])}</div>
  </div>
  <div class="rec" data-level="{rec_level}">
    <b>{rec_icon} توصيتي:</b>
    <span>{escape(item['rec'])}<br><span class="dim">إن فشل، أبدأ بـ: {escape(item['if_fail'])}</span></span>
  </div>
  <div>
    <div class="label">نتيجتك · your verdict</div>
    <div class="verdicts">{radios}</div>
  </div>
  <label>
    <span class="label">ملاحظة / ما ظهر (اختياري)</span>
    <textarea placeholder="مثال: ظهرت اللافتة، لكن الزر لم يستجب…"></textarea>
  </label>
</article>"""


def _md(text: str) -> str:
    """Turn the two marks used in ``expect`` into tags: **bold** and `code`."""
    out, bold, code = [], False, False
    i = 0
    while i < len(text):
        if text.startswith("**", i):
            out.append("<b>" if not bold else "</b>")
            bold = not bold
            i += 2
        elif text[i] == "`":
            out.append("<code>" if not code else "</code>")
            code = not code
            i += 1
        else:
            out.append(escape(text[i]))
            i += 1
    return "".join(out)


def build() -> str:
    cards = "\n".join(card(item) for item in ITEMS)
    groups = " · ".join(GROUPS[key] for key in GROUPS)
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>بوابة G3b — قائمة الفحص اليدوي · Mishkah Note 1.0.02</title>
<style>{CSS}</style>
</head>
<body>
<header class="top">
  <h1>بوابة G3b — 17 بندًا يدويًا
    <small>Mishkah Note 1.0.02 · اختر نتيجة لكل بند · لا شيء يُرسل من هذه الصفحة</small></h1>
  <div class="bar" role="progressbar" aria-label="التقدّم"><i></i></div>
  <span class="counter">0/17</span>
  <button class="primary" id="export">تصدير الجدول</button>
  <button id="clear">مسح</button>
</header>
<main>
  <section class="intro">
    <p><b>كيف تستخدم الصفحة:</b> لكل بند ثلاثة أزرار — <b>نجح</b> · <b>فشل</b> ·
      <b>لم أجرّبه</b> — وحقل ملاحظة حر. تُحفظ إجاباتك في متصفحك حتى لو أغلقت
      الصفحة، و«تصدير الجدول» ينسخ جدولًا جاهزًا للصقه في المحادثة.</p>
    <p><b>التوصية</b> هي ما أتوقعه وما أنصح بمراقبته، ومعها <b>إن فشل، أبدأ بـ</b>
      حتى يصلني البلاغ بنقطة انطلاق لا بلغز. الفحص كله نحو <b>20 دقيقة</b>.</p>
    <div class="legend">
      <span><b>المجموعات:</b> {groups}</span>
      <span><b>✅ ثقة عالية</b> — يغطيه اختبار آلي أو أثبتُّه بنفسي</span>
      <span><b>🟡 ثقة متوسطة</b> — يعتمد على جهازك أو إعدادك</span>
    </div>
    <p class="dim">الشرح الكامل والأوامر في
      <code>docs/G3B_WALKTHROUGH.ar.md</code>.</p>
  </section>
  <div class="grid">{cards}
  </div>
</main>
<footer class="summary">
  <span>تقدّمك: محفوظ في هذا المتصفح</span>
  <span class="fail-list" id="fails"></span>
  <span class="fail-list" id="later"></span>
  <span class="dim">لا وسم ولا نشر قبل أن تعود النتيجة.</span>
</footer>
<script>{JS}</script>
</body>
</html>
"""


def main(argv: list | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    html = build()
    if "--check" in args:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != html:
            print(f"{OUT.relative_to(ROOT)} is stale: run "
                  f"{Path(sys.argv[0]).name} to rebuild it", file=sys.stderr)
            return 1
        print(f"{OUT.relative_to(ROOT)} is up to date ({len(ITEMS)} items)")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(ITEMS)} items, "
          f"{len(html) // 1024} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
