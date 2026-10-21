# دليل التطوير · Development guide

## تشغيل البيئة · Setting up

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

تشغيل التطبيق:

```bash
python -m mufakkira            # أو: notepad
python -m mufakkira README.md  # فتح ملف مباشرة
notepad --safe-mode            # بلا جلسة سابقة وبإعدادات افتراضية
```

## الاختبارات · Tests

```bash
pytest                        # كل الاختبارات
pytest -m "not gui"           # المنطق الخالص فقط (بلا Qt)
pytest tests/test_editor_direction.py -v
```

### بلا شاشة · Headless

```bash
QT_QPA_PLATFORM=offscreen pytest
```

### ملاحظة عن إنهاء العمليات · Known teardown note

على بعض الأنظمة (PySide6 6.12 مع Python 3.11) يُنهي المفسّر نفسه بـ:

```
Fatal Python error: bool_dealloc: deallocating True or False
```

بعد أن تنجح **كل** الاختبارات. السبب خلل في تفكيك كائنات الربط أثناء التجميع
النهائي للذاكرة (final GC)، وليس في التطبيق: كل assertions مرّت، والمخرج قبل
الإنهاء سليم، ولا يظهر الخلل عند تعريف أصناف إضافية في السكربت، ولا مع عدد
أقل من الودجات.

للحصول على رمز خروج حتمي في CI:

```bash
MUFAKKIRA_CLEAN_EXIT=1 QT_QPA_PLATFORM=offscreen pytest
```

هذا المتغيّر يجعل `tests/conftest.py` يُفرِّغ المخازن المؤقتة ثم يخرج عبر
`os._exit(status)` بعد انتهاء الجلسة، فلا يدخل CPython مرحلة التفكيك التي
تُسبّب الانهيار. لا يُفعَّل تلقائيًا كي لا يخفي أخطاء حقيقية في بيئات أخرى.

## البنية · Layout

| المسار | المسؤولية | يستورد Qt؟ |
|--------|-----------|-------------|
| `core/` | اتجاه النص، الترميز، الملفات الكبيرة، اللغات، الترجمة، الإعدادات | لا |
| `models/` | حالة المستند | لا |
| `services/` | إدخال/إخراج في خيوط خلفية | نعم (QThread/Signal) |
| `views/` | النافذة، المحرّر، شريط الحالة | نعم |
| `widgets/` | الحوارات | نعم |
| `controllers/` | الربط بين الطبقات | نعم |

## إضافة ترجمة · Adding a translation

1. أضف رمز اللغة إلى `_LANGUAGES` في `core/languages.py` (مع حزمة الخطوط
   واتجاه الكتابة).
2. أضف الرمز إلى كل جدول في `core/i18n_data.py`.
3. `pytest tests/test_widgets.py::test_every_string_exists_in_every_language`
   سيكشف أي مفتاح ناقص.

## الأيقونة · The icon

الأيقونة مرسومة برمجيًا، لا صورة مولّدة، لتكون قابلة للمراجعة وإعادة التوليد:

```bash
python tools/make_icon.py
```

يُخرج `app.svg` و`app-16…512.png` و`app.ico` في
`src/mufakkira/resources/icons/`.

## التغليف · Packaging

راجع [PACKAGING.md](PACKAGING.md). البناء الكامل:

```bash
scripts/build-all.sh          # deb + wheel + sdist
scripts/build-deb.sh          # .deb فقط
```
