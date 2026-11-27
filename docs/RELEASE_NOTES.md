# ملاحظات إصدار مفكرة مشكاة 1.0.02 · Mishkah Note 1.0.02

إصدار تصحيحات وسلامة بيانات، لا إصدار ميزات جديدة. أكبر ما فيه ليس ما أُضيف بل
ما أُعلن: قيود كانت مخفيّة صارت مكتوبة، وحزمة كانت تفشل صامتة صارت تعمل أو تقول
لماذا لا تعمل.

> **اقرأ «القيود المعروفة» قبل أن تُثبّت.** كل بند فيها اختُبر فعلًا أو لم يُختبر
> أصلًا، ونقول أيّهما.

---

## ما الجديد

**المحرّر والأداء**
- إقران الأقواس و`Backspace` يقرآن الحرفين حول المؤشر فقط: **9.4 ms ← 0.02 ms** على
  مستند 1.2 م.ب.
- الإحصاءات وجهة المستند تُحسب بعد توقف الكتابة 150 ms، لا مع كل مفتاح.
- Markdown بنافذة 400 سطر: تفعيله على 8000 كتلة **1862 ms ← 76 ms**.

**الملفات الكبيرة والبحث**
- سقف المستخدم يصل فعلًا إلى القارئ؛ ما فوقه يُفتح معاينة للقراءة فقط مع زر
  «افتح الملف كاملًا».
- بحث متدرّج (180 ms) يبدأ من موضع فتح الشريط، ويُعلَّم الحقل بالأحمر عند عدم وجود نتيجة.

**التبويبات والنوافذ**
- أيقونة لكل تبويب مع نقطة للمعدَّل ودبوس للتثبيت · `Ctrl+T` تبويب · `Alt+T` فوق
  التطبيقات · عدّاد كلمات · إفلات ذكي (محتوى في المحرّر، تبويب جديد على الشريط).
- صفحة بداية عند إغلاق آخر تبويب وعند بدء تشغيل بلا جلسة، وإعدادات بسبع فئات.
- نافذة جديدة بـ`Ctrl+Shift+N` بتبويباتها المستقلة.

**الترخيص والتغليف (جديد في هذا الإصدار)**
- `THIRD-PARTY-NOTICES.md`: MIT للبرنامج · **LGPL v3** لـ Qt/PySide6 · **OFL-1.1**
  لخط IBM Plex Sans Arabic · MIT لـ charset-normalizer · **PSF** لمفسّر CPython —
  مع موضع كل مكوّن داخل كل حزمة وكيفية استبدال مكتبات Qt. الملف داخل الحزم الست
  كلها، و`verify-packaging.sh` يفشل إن غاب.
- **AppImage يحمل مفسّره**: CPython 3.11.18 محمولًا، فلا يحتاج `python3` على جهازك.
- `scripts/smoke-test.sh`: يفتح الحزمة المبنية ويشغّلها من داخلها — `--version`،
  دورة كتابة/قراءة عربية، ثم Qt والخطوط ونافذة بلا شاشة.
- اللغة الحالية للتلوين تُعرض بالعربية في شريط الحالة وفي قائمة اللغة
  (بايثون · جافاسكربت · ماركداون …)، و`C`/`JSON`/`SQL` تبقى كما هي عن قصد.
- **الطباعة مُختبرة**: مستند عربي يُخرج PDF متعدّد الصفحات بخط مضمَّن (عبر حوار
  الطابعة، وليست تصديرًا). طابعة حقيقية لم تُجرَّب بعد.
- **قياس الأداء والإقلاع في CI**: زمن الإقلاع يُسجَّل في كل تشغيل، وإدراج 100 KiB
  له بوابة 100 ms — فيظهر الانحدار قبل أن يشتكي مستخدم.
- الحدّ الأدنى من الوصولية: أسماء للعناصر التي لا نص لها، وشرائح شريط الحالة
  تُبلَغ بالمفتاح `Tab`، وسلسلة تنقّل واحدة صريحة.

**الواجهة والخطوط**
- صفحة البداية بعمودين متقابلين: الشعار، ثم **مفكرة مشكاة**، ثم **Mishkah Note**،
  ثم **الإصدار 1.0.02** في جهة القراءة (يمينًا في العربية والأردية، يسارًا في
  غيرها)، وقائمة «آخر الملفات» في بطاقة بالجهة المعاكسة.
- ضبط أحجام الخطوط والهوامش في القوائم المنسدلة لكل لغة، وتعميم نص المساعدة
  بالذكاء الاصطناعي في نافذة «حول البرنامج» عبر اللغات العشر.
- نصوص الصفحة تعيد ترجمة نفسها حين تُبدَّل اللغة من داخل التشغيل.
- **خط الواجهة غير خط الكتابة**: القوائم والأزرار في الأردية بخط
  `Noto Sans Arabic` المضمَّن (النستعليق يبقى للمحرّر)، والعربية بخط
  `IBM Plex Sans Arabic`؛ فلا تعتمد الواجهة على خطوط النظام.
- **تحصين الإقلاع عبر كل الصيغ**: سقوط لطيف عند غياب `PySide6.QtNetwork`،
  واعتماديات `.deb` صريحة (`python3-pyside6.qtwidgets` + `python3-pyside6.qtnetwork`)
  مع اجتياز `lintian --fail-on error`، وتضمين `Qt6Network.dll` و`Qt6Svg.dll`
  و`Qt6PrintSupport.dll` في `.msi`، وعزل `PYTHONNOUSERSITE=1` في `AppImage`.

---

## القيود المعروفة · Known limitations

### ما لم يُختبر أصلًا
| البند | الحال |
|---|---|
| **الوصولية** | الحدّ الأدنى فقط: أسماء للعناصر و`Tab` يصل إليها. **لم يُجرَّب مع Orca** ولا مع قارئ شاشة، ولا توجد مراجعة وصولية كاملة (ترتيب قراءة RTL، إعلان التغييرات، تكبير عالٍ). |
| **إدخال العربية على Wayland/IBus** | لم يُجرَّب على جلسة Wayland حقيقية بمدخل عربي. |
| **الطباعة** | لم تُجرَّب على طابعة حقيقية؛ أُنتج PDF فقط. |
| **الخطوط على macOS/Windows** | الخطوط العربية والأردية مضمَّنة داخل الحزمة، لكن شكلها على هذين النظامين (وبدائل النظام عندهما) لم يُجرَّب في هذا الإصدار. |
| **التثبيت على توزيعات حقيقية** | الحزم تُبنى وتُفحص آليًا، لكن التثبيت بـ`apt`/`dnf`/`pacman` على جهاز مستخدم لم يُجرَّب في هذا الإصدار. |

### الترجمات
- العربية والإنجليزية مكتوبتان يدويًا. **الثماني الأخرى (الصينية · الهندية ·
  الإسبانية · الفرنسية · البنغالية · البرتغالية · الروسية · الأردية) آلية لم
  يراجعها متحدّث أصلي.** الأخطاء اللغوية فيها واردة، والترجمة الكاملة شرط لأي
  إصدار يعلنها.

### الميزات الغائبة (بقصد، لا سهوًا)
- **لا تصدير**: `Markdown` عرض حيّ فقط — لا تصدير إلى HTML أو PDF أو Markdown.
  (الطباعة إلى PDF عبر حوار الطابعة موجودة ومُختبرة، لكنها ليست «تصديرًا»: لا
  خيارات تنسيق ولا ملفّ ناتج بأمر واحد.)
- **الجلسة لنافذة واحدة**: النافذة الأولى وحدها تحفظ قائمة التبويبات؛ التبويبات
  المفتوحة في نوافذ إضافية لا تعود بعد إعادة التشغيل.
- **لا استرداد لمستند بلا مسار**: الملفات المحفوظة محميّة، أما تبويب لم يُحفظ بعد
  فيُفقد إن أُغلق البرنامج بانهيار.
- **لا بحث عبر التبويبات**: البحث داخل التبويب الحالي فقط.
- **Flatpak بصلاحية `home`** وليس بـportals، ولم يُقدَّم إلى Flathub.
- **Windows/MSI تجريبي**: يُبنى ويُثبَّت آليًا، لكنه ليس مسارًا مدعومًا بالكامل بعد.

---

## متطلبات كل حزمة

| الحزمة | نظام التشغيل | ما تحتاجه على جهازك | الحجم التقريبي |
|---|---|---|---|
| `Mishkah_Note-1.0.02-x86_64.AppImage` | لينكس x86_64 | لا شيء (يحمل Python وPySide6-Essentials)؛ يحتاج glibc متوافقة وX11/Wayland | ~77 م.ب |
| `mishkah-note_1.0.02_all.deb` | Debian/Ubuntu | `python3` و`python3-pyside6.qtwidgets` و`python3-pyside6.qtnetwork` (تُثبَّت تلقائيًا عبر `apt install ./…deb`) | ~1.7 م.ب |
| `mishkah-note-1.0.02-1.*.noarch.rpm` | Fedora/RHEL/openSUSE | `python3` و`python3-pyside6` | ~1.7 م.ب |
| `mishkah-note-1.0.02-1-any.pkg.tar.zst` | Arch/Manjaro | `python3` و`pyside6` | ~3.3 م.ب |
| `org.mishkahnote.Mishkah.flatpak` | أي توزيعة فيها Flatpak | زمن تشغيل `org.kde.Platform//6.7` | ~32 م.ب |
| `Mishkah_Note_1.0.02_x64.msi` | Windows 10/11 x64 | لا شيء (يحمل Python وPySide6) | ~39 م.ب |
| `mishkah_note-1.0.2-py3-none-any.whl` + `.tar.gz` | أي | `pip install` مع PySide6 | ~2.4 / 3.2 م.ب |  <!-- version-gate: allow: PEP 440 normalises the file name -->

الخط العربي **مضمَّن** في كل الصيغ؛ لا تحتاج تثبيت خط.

---

## التحقق في هذا الإصدار

- الاختبارات: **670 ناجحًا، صفر فشل** (Qt يعمل، بلا شاشة) على Python 3.9 و3.11 و3.13.
- `scripts/verify-packaging.sh`: 54 فحصًا ناجحًا · صفر فشل · 8 تخطيات (أدوات
  غير مثبّتة على الجهاز).
- `scripts/smoke-test.sh --build`: 6 ناجحة · صفر فشل · تخطّيان (MSI وFlatpak).
- `tools/check_version.py`: `1.0.02` في كل مكان مشتق، صفر اختلاف.
- CI على GitHub أخضر للفروع الثلاثة من Python، ولـ`Packaging sanity` بما فيه
  اختبار الدخان داخل `.deb`.

---

## English summary

A correctness and data-safety release. Highlights: a faster editing path (paste of
100 KiB ≈ 7.5 ms, neighbour reads 9.4 → 0.02 ms on a 1.2 MB buffer), a large-file
preview with an explicit "open the whole file" button, incremental search, coloured
and pinnable tabs, a welcome page, seven-category settings, real extra windows, and
the 1.0.02 packaging work — third-party notices shipped in every package, an
AppImage that carries its own CPython, and a smoke test that runs a built package
from the inside.

**Known limitations, stated plainly:** accessibility is a *minimum* (names and Tab
reachability) and has **not** been tested with Orca or any screen reader; the eight
non-Arabic/non-English interface translations are **machine-made and unreviewed**; Markdown is
a view only, with **no export**; the session belongs to the first window, so tabs in
extra windows are not restored; untitled buffers are not recovered after a crash;
Flatpak uses `--filesystem=home` rather than portals and is not on Flathub; the
Windows MSI is **experimental**; Wayland/IBus Arabic input and real printers are
untested.
