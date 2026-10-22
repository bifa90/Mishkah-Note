# جاهزية Mishkah Note 1.0.01

## ضمانات المصدر والتغليف

| المجال | الضمان | الاختبارات |
|---|---|---|
| الهوية والإصدار | حزمة ووحدة وأمر موحّدة، ومدخل إصدار واحد | `tests/test_project_meta.py` |
| سطر الأوامر | `mishkah --version` و`python -m mishkah --version` يعرضان `1.0.01` دون تحميل Qt | `tests/test_cli.py` |
| الخطوط | IBM Plex Sans Arabic Regular مضمّن، واختيار المستخدم مقدّم لكل لغة | `tests/test_fonts.py` |
| السمات | `QWidget` لا يفرض عائلة الخط أو حجمه | `tests/test_packaging_static.py` |
| Unicode | BOM واحد، وقراءة UTF-16/32، وترميز تدفقي على حدود الدفعات | `tests/test_large_file.py` |
| الحفظ | لقطة نص وترميز عند الطلب؛ اكتمال الحفظ لا يمحو علامة تعديل أحدث | `tests/test_save_revision.py` و`tests/test_controller.py` |
| الإغلاق | اختيار الحفظ يؤجل إغلاق التبويب حتى نجاح العملية | `tests/test_controller.py` |
| المصدر | sdist يتضمن أدوات Windows؛ Arch يستخدم أرشيف checkout البناء | `tests/test_packaging_static.py` |
| النشر | اكتمال الحزم الثماني وأسمائها قبل الرفع | `tests/test_release_assets.py` |

## التحقق المتاح في بيئة الجلسة

- 195 اختبارًا ناجحًا في المجموعة القابلة للتشغيل بلا Qt، مع 11 تخطيًا
  لواجهات الخطوط واستبعاد اختباري نافذة «حول» من هذه المجموعة.
- `ruff check src tests tools` نظيف.
- بناء wheel وsdist وDebian ناجح؛ الخط والترخيص وملفات branding موجودة في wheel.
- تثبيت wheel في venv نظيف ناجح، وأمر الإصدار يعرض `1.0.01`.
- `scripts/verify-packaging.sh`: 37 فحصًا ناجحًا، صفر فشل، 8 تخطيات.
- Shell وJSON وXML وYAML اجتازت الفحوص البنيوية المتاحة.

## التحقق على GitHub والحزم

- صلاحية دفع workflows متاحة؛ ملفات CI وRelease الفعلية موجودة في
  `.github/workflows/` ونسخها المرجعية في `docs/ci/`.
- نجحت الاختبارات الكاملة على Python 3.9 و3.11 و3.13 وفحص التغليف:
  [CI](https://github.com/bifa90/Mishkah-Note/actions/runs/39775427299).
- ولّد GitHub الصور السبع من التطبيق الحقيقي، وأُدرجت في الفرع وفُحصت بصريًا؛
  تظهر هوية Mishkah Note والرابط الحالي والخط العربي.
- أصلحت وصفة MSI ربط ملفات التطبيق بميزة WiX، وأضيف فحص نجاح الأدوات
  وجمع الموارد. اجتاز Windows البناء وتشغيل الملف المجمّد والتثبيت الفعلي
  وفحص الملف التنفيذي والخط العربي ثم إزالة التثبيت:
  [فحص المثبّت](https://github.com/bifa90/Mishkah-Note/actions/runs/39784251803).
- تتضمن بيئة Flatpak أدوات `elfutils` ومحرّك SVG `librsvg2-common`،
  مع فحص AppStream دون تعطيله وفحص تشغيل Qt والخط العربي داخل الحزمة.
  اجتاز البناء وفحص التشغيل في
  [فحص الحزم الأصلية](https://github.com/bifa90/Mishkah-Note/actions/runs/39785367720).
- تستخدم وظائف Linux بيئة Ubuntu 24.04 LTS مثبتة بدل الصورة المتحركة.
- حالة الحزم النهائية والنشر متاحة في
  [سير Release](https://github.com/bifa90/Mishkah-Note/actions/workflows/release.yml).
  نجاح البناء وفحص التشغيل وحدهما لا يعني اكتمال تصدير الحزم أو رفعها.
- بعد تفويض صاحب المشروع، تسمح علامة `[publish 1.0.01]` في رسالة دفعة
  فرع الجلسة بالنشر؛ لا ترفع الحزم إلا بعد نجاح اختبار المصدر وكل وظائف
  التغليف والتحقق من وجود المخرجات الثمانية ثم توليد `SHA256SUMS.txt`.
- يشير الوسم إلى مصدر البناء نفسه. الدمج منفصل عن النشر، ولا ينفّذ إلا
  بعد التحقق من اكتمال الملفات التسعة في صفحة الإصدار وموافقة صاحب المشروع.

للتفعيل والتشغيل: [docs/ci/README.md](ci/README.md).
الدليل الشخصي للبناء والرفع اليدوي: [PRIVATE_BUILD_GUIDE.ar.md](PRIVATE_BUILD_GUIDE.ar.md).
