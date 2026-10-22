# دليل خاص لصاحب المستودع: بناء ورفع Mishkah Note 1.0.01

هذا دليل تشغيل شخصي يمكنك حذفه بعد إتمام العمل. ليس إعلانًا بأن الحزم مبنية
أو منشورة. لا تحتاج إلى إرسال كلمة مرور أو token لأي شخص.

## 1. ما الذي تفعله الأتمتة الآن؟

ملفات GitHub Actions الفعلية في `.github/workflows/`، ونسخها المرجعية في
`docs/ci/`. سير CI يفحص التطبيق، وسير Release يبني كل الصيغ بعد نجاح اختبارات
المصدر. دفعات فرع الجلسة تبني مرشح إصدار **دون نشره**؛ النشر مخصص لتشغيل الوسم
أو التشغيل اليدوي. يمكنك متابعة حالة كل وظيفة من تبويب Actions.

التشغيل اليدوي عبر API يحتاج صلاحية **Actions: write**، وهي مختلفة عن صلاحية
**Workflows: write** اللازمة لإضافة ملفات YAML. إذا لم يظهر زر Run workflow،
قد يحتاج الملف إلى الوجود على الفرع الافتراضي أو إلى مراجعة إعدادات Actions.
لا تدمج PR قبل أن تقرر أنت اعتماده.

## 2. المسار الأسهل: تنزيل مخرجات Actions

1. افتح https://github.com/bifa90/Mishkah-Note/actions.
2. اختر تشغيل Release الخاص بالـcommit المطلوب، وليس تشغيلًا لمصدر مختلف.
3. تأكد من نجاح الاختبارات وكل وظائف البناء، لا من نجاح وظيفة واحدة فقط.
4. نزّل Artifacts المسماة `packages-python`, `packages-deb`, `packages-rpm`,
   `packages-arch`, `packages-appimage`, `packages-flatpak`, `packages-msi`.
5. فك ZIP لكل أثر. لا ترفع ملفات ZIP الخاصة بالآثار بدل الحزم نفسها.
6. أثر `screenshots` منفصل: افحص صوره بصريًا، ثم استخدم الصور المعتمدة في
   `docs/screenshots/`. لا ترفعه كحزمة تثبيت.
7. اجمع ملفات الحزم الثمانية فقط في مجلد مثل `release-bundle/` خارج المصدر.

إذا فشل بناء: افتح الوظيفة والخطوة الحمراء واقرأ الخطأ. لا تغيّر امتداد ملف
ولا تنشئ ملفًا فارغًا لتعويض حزمة مفقودة.

## 3. سكربت Python الموحّد

من جذر المستودع:

```bash
python scripts/build_release.py --help
python scripts/build_release.py --formats all --dry-run
```

السكربت يشغّل وصفات البناء الحقيقية الموجودة في المستودع؛ لا يصنع أغلفة
وهمية، ولا يحوّل Linux إلى Windows. الأهداف:

| الهدف | الناتج | بيئة البناء |
|---|---|---|
| `python` | wheel + sdist | Python مع أدوات البناء |
| `deb` | Debian/Ubuntu `.deb` | Linux مع `dpkg-deb` |
| `rpm` | Fedora/openSUSE `.rpm` | Linux مع `rpmbuild` |
| `arch` | `.pkg.tar.zst` | Arch/Manjaro مع `makepkg` ومستخدم غير root |
| `appimage` | `.AppImage` | Linux x86_64 مع `appimagetool` |
| `flatpak` | `.flatpak` | Linux مع Flatpak وKDE SDK/runtime |
| `msi` | Windows `.msi` | Windows x64 مع Python و.NET وPowerShell |

`--formats linux` يطلب كل أهداف Linux بما فيها حزم Python؛ لن ينجح إذا كانت
الأدوات ناقصة. `--formats all` يشمل MSI أيضًا، فلا تتوقع بناء الجميع على نظام
واحد. استخدم الأهداف المناسبة لكل جهاز.

```bash
python scripts/build_release.py --formats python,deb --check
python scripts/build_release.py --formats python,deb
python scripts/build_release.py --formats rpm --output ./dist
```

- `--check`: فحص أولي للأدوات؛ لا يغني عن نجاح البناء أو اختبار الحزمة.
- `--dry-run`: يعرض الأوامر فقط، ولا ينتج ملفات.
- `--keep-going`: يحاول بقية الأهداف عند الفشل؛ يبقى رمز الخروج غير صفر
  إذا غاب أي هدف مطلوب أو فشل، ولا يُعتبر ذلك إصدارًا مكتملًا.
- سجل النتائج في `build/manual-release-report.json`، والمخرجات افتراضيًا في
  `dist/`. كلاهما خارج Git.
- لا تشغّل السكربت بصلاحية root؛ استخدم sudo لتثبيت المتطلبات فقط.

## 4. الحصول على المصدر نفسه على كل جهاز

إلى أن تعتمد PR، يمكنك تنزيل فرع الجلسة للاختبار:

```bash
git clone --branch arena/71ffd864-mishkah-note https://github.com/bifa90/Mishkah-Note.git
cd Mishkah-Note
git rev-parse HEAD
```

سجّل SHA الناتج واستعمل **نفس commit** في كل بيئات البناء. بعد اعتماد المصدر
يمكن استعمال commit المعتمد أو الوسم الذي يشير إليه. لا تجمع حزمًا من commits
مختلفة تحت الإصدار نفسه. بناء RPM وArch يؤرشف HEAD، لذا احفظ تغييرات المصدر
في commit قبل بنائهما؛ لا تعتمد على تعديلات محلية غير محفوظة.

## 5. Debian / Ubuntu

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip dpkg-dev \
  libgl1 libegl1 libxkbcommon0 libdbus-1-3 fonts-noto-core fonts-noto-cjk
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]' wheel 'setuptools>=68'
QT_QPA_PLATFORM=offscreen MISHKAH_CLEAN_EXIT=1 python -m pytest tests/ -q
python -m ruff check src tests tools
python scripts/build_release.py --formats python,deb
```

المتوقع: `dist/mishkah-note_1.0.01_all.deb` مع wheel وsdist. Debian هنا
`all` لأن كود التطبيق Python مستقل عن المعمارية؛ لا تغيّر الاسم إلى amd64.
اختبر التثبيت على جهاز/آلة افتراضية منفصلة:

```bash
sudo apt install ./dist/mishkah-note_1.0.01_all.deb
mishkah --version
mishkah
```

## 6. Fedora / RPM

داخل Fedora، بحساب مستخدم عادي:

```bash
sudo dnf install -y git rpm-build python3 python3-pip python3-build \
  python3-setuptools python3-wheel
python3 -m venv .venv
. .venv/bin/activate
python -m pip install build wheel 'setuptools>=68'
python scripts/build_release.py --formats rpm
```

الناتج: `dist/mishkah-note-1.0.01-*.noarch.rpm`.
الفحص: `rpm -qip dist/*.rpm` و`rpm -qlp dist/*.rpm`؛ ثم التثبيت والتشغيل
في آلة افتراضية. ملفات `.src.rpm` ليست حزمة التثبيت المطلوب إرفاقها.

## 7. Arch / Manjaro

داخل Arch/Manjaro، ليس بحساب root:

```bash
sudo pacman -Syu --needed base-devel git python pyside6 python-charset-normalizer \
  python-build python-installer python-wheel python-setuptools
python scripts/build_release.py --formats arch
```

الناتج: `dist/mishkah-note-1.0.01-1-any.pkg.tar.zst`.
اختبره باستخدام `sudo pacman -U dist/*.pkg.tar.zst` داخل آلة افتراضية.

## 8. AppImage

على Linux x86_64، داخل venv معدة كما في قسم Ubuntu:

1. نزّل `appimagetool-x86_64.AppImage` من المصدر الرسمي:
   https://github.com/AppImage/appimagetool/releases.
2. تحقّق من المصدر وchecksum المتاح، واحفظ الأداة خارج ملفات Git.
3. نفّذ:

```bash
chmod +x /path/to/appimagetool-x86_64.AppImage
export APPIMAGETOOL=/path/to/appimagetool-x86_64.AppImage
# عند غياب FUSE داخل حاوية يمكن استخدام وضع الاستخراج الخاص بالأداة:
export APPIMAGE_EXTRACT_AND_RUN=1
python scripts/build_release.py --formats appimage
```

الناتج: `dist/Mishkah_Note-1.0.01-x86_64.AppImage`. يحتاج هذا التغليف Python3
على جهاز المستخدم ومكتبات النظام المتوافقة؛ ليس ضمانًا للعمل على كل توزيعة.
اختبره على توزيعة الهدف، لا بأمر `--version` وحده.

## 9. Flatpak

```bash
sudo apt install flatpak flatpak-builder
flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub org.kde.Platform//6.7 org.kde.Sdk//6.7
python scripts/build_release.py --formats flatpak
flatpak install --user ./dist/org.mishkahnote.Mishkah.flatpak
flatpak run org.mishkahnote.Mishkah
```

هذا بناء عبر KDE runtime المحدد في manifest؛ تنزيل SDK والحزم يحتاج إنترنت
ومساحة كافية. افحص توفر runtime، ولا تستبدل رقمه عشوائيًا إذا لم يعد متاحًا.

## 10. Windows MSI

استخدم Windows x64. ثبّت Git وPython 3.11 و.NET SDK 8 وPowerShell 7 من المصادر
الرسمية. أمثلة اختيارية عبر winget:

```powershell
winget install -e --id Git.Git
winget install -e --id Python.Python.3.11
winget install -e --id Microsoft.DotNet.SDK.8
winget install -e --id Microsoft.PowerShell
```

افتح نافذة PowerShell جديدة لتحديث PATH، ثم من جذر نفس مصدر المشروع:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe scripts/build_release.py --formats msi --check
.\.venv\Scripts\python.exe scripts/build_release.py --formats msi
```

السكربت الفرعي يثبّت متطلبات PyInstaller وWiX المحددة ويبني التطبيق ثم MSI.
الناتج: `dist/Mishkah_Note_1.0.01_x64.msi`.

اختبر التثبيت والإزالة في Windows Sandbox/آلة افتراضية نظيفة لا تحتوي Python:

```powershell
msiexec /i .\dist\Mishkah_Note_1.0.01_x64.msi
```

افتح البرنامج من Start، واختبر العربية والخط المضمّن والفتح والحفظ والتبويبات
وMarkdown الاختياري، ثم أزل التثبيت من Settings. تحذير SmartScreen ممكن لأن
الحزمة غير موقّعة بشهادة ناشر تجارية؛ لا تدّع أنها موقّعة.

## 11. جمع الحزم والتحقق ثم الرفع يدويًا

اجمع الحزم الثماني فقط، دون ZIP أو ملفات سجل أو مجلدات بناء، في مجلد فارغ
مثل `/path/to/release-bundle` أو `C:\release-bundle`. ثم:

```bash
python scripts/build_release.py --verify-bundle /path/to/release-bundle
```

الفحص يتحقق من الأسماء والاكتمال وكون الملفات غير فارغة؛ لا يثبت سلامة تشغيلها
ولا يفحصها أمنيًا. يُنشئ checksum في `build/SHA256SUMS.txt`، خارج مجلد الحزم
لكي تستطيع تكرار فحص المجلد دون تعارض. ارفع ملف checksum أيضًا بعد نجاح الفحص.

1. افتح https://github.com/bifa90/Mishkah-Note/releases.
2. اختر تحرير Release الخاص بـ`v1.0.01` (ولا تنشئ إصدارًا برقم مختلف).
3. تأكد أن الوسم يشير إلى **نفس commit الذي بنيت منه**. لا ترفق حزمًا لا تطابق
   المصدر الموجود تحت الوسم. نقل الوسم قرار نشر مستقل، وليس موافقة أو دمجًا
   تلقائيًا للـPR؛ افحص SHA قبل تنفيذ القرار.
4. اجعل العنوان `Mishkah Note 1.0.01`، وانسخ الملاحظات من `docs/RELEASE_NOTES.md`.
5. اسحب ملفات الحزم الثمانية الفعلية و`SHA256SUMS.txt` إلى منطقة Attach binaries.
6. انتظر اكتمال الرفع، ثم احفظ الإصدار وافتح الصفحة للتحقق من كل الأسماء.
7. لا ترفع الحزم إلى شجرة ملفات المستودع ولا تستخدم `git add dist/`.
8. أبقِ `v1.0.01` والإصدار المرتبط به فقط وفق سياسة المشروع، بعد التأكد من
   اكتمال النشر. لا تحذف الوسم الصحيح أو أصولًا صالحة أثناء المحاولة.

## 12. قبل أن تعتبر العمل منتهيًا

- [ ] الاختبارات الكاملة وruff ناجحة على مصدر البناء نفسه.
- [ ] الصور السبع مولّدة من التطبيق الحقيقي ومراجعة بصريًا بالهوية الحالية.
- [ ] العربية تستخدم IBM Plex Sans Arabic Regular تلقائيًا، وتغيير الخط متاح.
- [ ] الحزم الثماني موجودة واجتازت الفحوص وتجارب التثبيت المناسبة.
- [ ] ملفات GitHub Release تطابق أسماء الحزم وchecksums ومصدر الوسم.
- [ ] لا dist أو build أو venv أو مفاتيح توقيع داخل Git.
- [ ] موافقتك على PR قرارك أنت؛ سكربت البناء لا يدمج شيئًا ولا يرفع شيئًا.

بعد الانتهاء يمكنك حذف هذا الدليل الشخصي؛ ليس جزءًا يحتاجه التطبيق للتشغيل.
