# المفكرة — Notepad for Linux

نصّ بسيط وسريع لسطح مكتب لينكس، بواجهة تحاكي **Notepad في Windows 11**، مع دعم
حقيقي للعربية واللغات ذات الاتجاه من اليمين إلى اليسار. حرّ ومفتوح المصدر تحت
رخصة MIT.

A fast, minimal text editor for the Linux desktop, styled after **Windows 11
Notepad**, with first-class support for Arabic and other right-to-left scripts.
Free and open source under the MIT license.

![Notepad in light theme](docs/screenshots/light.png)

| الوضع الداكن مع العربية | الإعدادات |
|---|---|
| ![dark](docs/screenshots/dark-arabic.png) | ![settings](docs/screenshots/settings.png) |

---

![الشعار · the logo](src/mufakkira/resources/icons/app-256.png)

## المزايا · Features

### واجهة Windows 11 · Windows 11 look
* شريط تبويبات بزوايا مستديرة ونقطة تعديل، مثل Notepad 11.
* شريط قوائم مسطّح وخفيف، وشريط حالة يعرض `السطر، العمود` وحجم النص والترميز ونهاية السطر.
* سمتان فاتحة وداكنة تتبعان إعداد النظام تلقائيًا (`system` / `light` / `dark`).

### الكتابة الذكية · Smart typing
* **إكمال تلقائي للأقواس والعلامات**: اكتب `(` فيظهر `()` والمؤشر بالداخل، واكتب
  `)` فيتخطى القوس الموجود بدل تكراره. يشمل `[] {} "" '' `` «» ‹› “” ‘’`،
  ويلفّ التحديد المظلّل عند الضغط على أي منها.
* **مسافة تراجع ذكية**: `Backspace` بين قوسين فارغين يحذفهما معًا.
* **إزاحة تلقائية**: `Enter` يحافظ على الإزاحة ويضيف مستوى بعد فتح كتلة
  (`(`، `[`، `{`، `:`) ويتراجع عند كتابة قوس إغلاق. ويتبع أسلوب الملف نفسه
  (Tab أو مسافتان أو أربع).
* **`Tab` / `Shift+Tab`** يزيح/يرجع كتلة كاملة.
* **إكمال الكلمات** بـ`Ctrl+Space`: يقترح كلمات موجودة في مستندك مرتّبة
  بالتكرار والحداثة، ويدعم العربية.

### تبويبات ملوّنة ومثبّتة · Coloured and pinned tabs
* ستة ألوان على نمط أوراق الملاحظات اللاصقة تُطبَّق على التبويب من قائمة
  **Tab** أو من قائمة السياق بالزر الأيمن، و`Ctrl+Shift+K` يدوّر الألوان.
* **التثبيت فوق التطبيقات**: `Ctrl+P` (أو دبّوس التبويب) يجعل التبويب النشط
  يرفع النافذة فوق كل البرامج، ويظهر دبّوس على التبويب بلون النص المناسب.
  تبويب واحد مثبّت في الوقت نفسه، ويُرفع القيد تلقائيًا عند تبديل التبويب
  أو إغلاقه. `Ctrl+T` يفعل الشيء نفسه من القائمة.

### تلوين الشيفرة (اختياري) · Syntax highlighting (opt-in)
* **معطّل افتراضيًا** كما طُلب: مفكرة عادية لا يجب أن تلوّن شيئًا من تلقاء نفسها.
* عند تشغيله (`Ctrl+Shift+H` أو View ▸ Syntax highlighting) يتعرّف على اللغة من
  اسم الملف: Python، JavaScript، TypeScript، JSON، HTML، CSS، C، C++، Rust،
  Go، Java، shell، SQL، YAML، Markdown.
* `View ▸ Highlight language` يتجاوز التخمين لكل تبويب، والألوان تتبع
  السمة الفاتحة أو الداكنة.

### الاتجاه (RTL) — الإصلاح الجذري
كان الخلل في النسخة السابقة أنّ التطبيق يفرض `RightToLeft` على مستوى
`QApplication`، فينقلب كل شيء — القوائم والنوافذ وحتى الملفات الإنجليزية.

الآن:

* **لا يوجد أي فرض عالمي للاتجاه.** واجهة التطبيق تتبع لغة الواجهة فقط، أما
  اتجاه *النص* فيُضبط لكل مستند على حدة عبر
  `QTextBlockFormat.setLayoutDirection()` على كل فقرة (هذا هو المفتاح الحقيقي في
  Qt؛ `setTextBlockDirection` غير موجود أصلًا).
* **الاتجاه الافتراضي = تلقائي**: يُستنتج من أول حرف قوي في أول سطر غير فارغ
  (عربي/عبري ← من اليمين، غير ذلك ← من اليسار)، مع إمكانية التجاوز من القائمة.
* **Ctrl+Shift يعمل بثبات**: يمين = RTL، يسار = LTR. يُنفَّذ فقط عند اكتمال
  الإيعاز (Ctrl+Shift وحدهما دون أي مفتاح ثالث) وعند رفع المفتاح، فلا يتعارض مع
  تبديل لوحة المفاتيح في النظام ولا مع `Ctrl+Shift+N` وأخواتها.
  مسجّل أيضًا في القائمة (`Ctrl+Shift+A/R/L`) وكشريحة قابلة للنقر في شريط الحالة.

### ملفات كبيرة — Large files
* فحص الترميز على أول 64 كيلوبايت، ثم فكّ ترميز على دفعات 1 ميجابايت مع شريط تقدّم
  وإمكانية إلغاء.
* الملفات فوق 8 ميجابايت تُفتح في **وضع معاينة للقراءة فقط** اختياري، وفوق 512
  ميجابايت يُطلب تأكيد صريح.
* الحفظ ذرّي: كتابة إلى ملف مؤقت ثم `os.replace` — لا يبقى ملف نصف مكتوب عند
  انقطاع الكهرباء.
* تنبيه عند تجاوز مليوني سطر، مع إمكانية تعطيل الالتفاف وسجل التراجع
  (وضع الأداء) تلقائيًا.

### اللغات — Languages
أكثر عشر لغات استخدامًا في العالم، ولكل لغة **حزمة خطوط مناسبة لنظام كتابتها**
(يُختار أول خط متاح على النظام، ثم البديل التالي):

| # | اللغة | الرمز | الخط المفضّل | الاتجاه |
|---|-------|-------|--------------|---------|
| 1 | English | `en` | Segoe UI → Roboto → Liberation Sans | LTR |
| 2 | 简体中文 | `zh-Hans` | Microsoft YaHei → Noto Sans CJK SC | LTR |
| 3 | हिन्दी | `hi` | Nirmala UI → Noto Sans Devanagari | LTR |
| 4 | Español | `es` | Segoe UI → Roboto → Liberation Sans | LTR |
| 5 | Français | `fr` | Segoe UI → Roboto → Liberation Sans | LTR |
| 6 | العربية | `ar` | **IBM Plex Sans Arabic** (مضمَّن) → Noto Naskh Arabic | RTL |
| 7 | বাংলা | `bn` | Nirmala UI → Noto Sans Bengali | LTR |
| 8 | Português | `pt` | Segoe UI → Roboto → Liberation Sans | LTR |
| 9 | Русский | `ru` | Segoe UI → Roboto → DejaVu Sans | LTR |
| 10 | اردو | `ur` | Noto Nastaliq Urdu → Jameel Noori Nastaleeq | RTL |

خط `IBM Plex Sans Arabic Light` مضمَّن مع التطبيق (SIL OFL 1.1)، لذا تظهر العربية
بشكل صحيح حتى على توزيعة بلا خطوط عربية. بقية الخطوط تُستعار من النظام عند
توفرها؛ راجع [docs/FONTS.md](docs/FONTS.md) لطريقة تثبيتها.

واجهة التطبيق نفسها مترجمة إلى اللغات العشر، وتتبدّل مباشرة من
`الإعدادات ← لغة الواجهة` دون إعادة تشغيل.

### الترميز — Encodings
UTF-8، UTF-8 مع BOM، UTF-16 LE/BE، UTF-32، Windows-1256، Windows-1252،
ISO-8859-6، ISO-8859-1، CP720، ASCII — مع كشف تلقائي عبر `charset-normalizer`
وإمكانية إعادة الفتح بترميز آخر.

---

## التثبيت · Installation

### من الحزم الجاهزة · Packages
```bash
# Debian / Ubuntu
sudo apt install ./notepad-linux_1.0.1_all.deb

# Fedora / RHEL / openSUSE  (بناء محلي)
rpmbuild -ba packaging/rpm/notepad-linux.spec

# Arch / Manjaro
cd packaging/arch && makepkg -si

# AppImage (محمول — portable)
./packaging/appimage/build-appimage.sh

# Flatpak
flatpak-builder --install --user build packaging/flatpak/org.notepadlinux.Notepad.json
```

### من المصدر · From source
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install .
notepad            # أو: mufakkira
```

يتطلب Python ≥ 3.9، وPySide6 ≥ 6.5، و`charset-normalizer`.

### التشغيل للتطوير · Development run
```bash
pip install -e ".[dev]"
python -m mufakkira            # مع PYTHONPATH=src أو بعد pip install -e
```

---

## لوحة المفاتيح · Keyboard shortcuts

| الاختصار | الوظيفة |
|-----------|----------|
| `Ctrl+N` / `Ctrl+O` / `Ctrl+S` | جديد / فتح / حفظ |
| `Ctrl+Shift+S` | حفظ باسم |
| `Ctrl+W` / `Ctrl+Tab` | إغلاق التبويب / التنقل بين التبويبات |
| `Ctrl+F` / `Ctrl+H` / `F3` | بحث / استبدال / التالي |
| `Ctrl+G` | الانتقال إلى سطر |
| `Ctrl+Plus` / `Ctrl+Minus` / `Ctrl+0` | تكبير / تصغير / إعادة ضبط |
| `F5` / `Ctrl+Shift+D` | التاريخ والوقت |
| `Ctrl+,` | الإعدادات |
| `Ctrl+Space` | إكمال الكلمة |
| `Ctrl+Shift+H` | تشغيل/إيقاف تلوين الشيفرة |
| `Ctrl+P` / `Ctrl+T` | تثبيت التبويب / النافذة فوق التطبيقات |
| `Ctrl+Shift+K` | تدوير لون التبويب |
| **`Ctrl+Shift+→` / `Ctrl+Shift+←`** | **اتجاه النص: من اليمين / من اليسار** |
| `Ctrl+Shift+A` | اتجاه تلقائي (حسب المحتوى) |

---

## البنية · Architecture

```
src/mufakkira/
├── core/            منطق خالص بلا Qt — قابل للاختبار وحده
│   ├── languages.py       سجل اللغات وحزم الخطوط
│   ├── autocomplete.py    إقران الأقواس، الإزاحة، إكمال الكلمات
│   ├── syntax.py          تعريف 16 لغة للتلوين
│   ├── tab_style.py       ألوان الملاحظات للتبويبات
│   ├── text_direction.py  كشف الاتجاه بقواعد bidi
│   ├── encoding.py        كشف الترميز ونهايات الأسطر
│   ├── large_file.py      القراءة/الكتابة المجزّأة والذرّية
│   ├── i18n.py            الترجمة (140 مفتاحًا × 10 لغات)
│   └── settings.py        الإعدادات في ~/.config/Mufakkira
├── models/document.py     حالة المستند (مسار، ترميز، تعديل…)
├── services/file_service.py  عمليات الإدخال/الإخراج في خيوط خلفية
├── views/           النافذة والمحرّر وشريط الحالة
├── widgets/         الحوارات + الملوّن النحوي
└── controllers/main_controller.py  الربط بين الواجهة والخدمات
```

القاعدة: `core/` و`models/` لا تستوردان PySide6 مطلقًا، لذا تُختبر بسرعة وبدون
شاشة. الطبقات الأخرى رقيقة وتُختبر بـ`pytest-qt`.

---

## الاختبارات · Tests

```bash
pytest                       # 216 اختبارًا
pytest -m "not gui"          # اختبارات المنطق فقط
```

على الخوادم بلا شاشة:
```bash
QT_QPA_PLATFORM=offscreen pytest
```

تفاصيل بيئة الاختبار والملاحظة المعروفة عن إنهاء العمليات في
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

---

## المساهمة · Contributing

نرحّب بكل مساهمة — راجع [CONTRIBUTING.md](CONTRIBUTING.md). المهام المقترحة
والتحليل الكامل في [docs/SWOT.md](docs/SWOT.md).

## الرخصة · License

MIT — راجع [LICENSE](LICENSE). الخطوط المضمّنة لها رخصتها الخاصة
(SIL OFL 1.1)، مذكورة في [docs/FONTS.md](docs/FONTS.md).
