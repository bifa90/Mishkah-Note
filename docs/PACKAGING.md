# التغليف · Packaging

كل صيغ لينكس الخمس موجودة في `packaging/`، وبناءها في `scripts/`، وملف واحد
يتحقق منها: `scripts/verify-packaging.sh`.

| الصيغة | الأمر | المخرَج | يحتاج |
|--------|-------|---------|-------|
| sdist + wheel | `python -m build` | `dist/*.tar.gz`, `dist/*.whl` | `build` |
| Debian / Ubuntu | `bash scripts/build-deb.sh` | `dist/mishkah-note_1.0.02_all.deb` | `dpkg-deb` |
| Fedora / RHEL / openSUSE | `bash scripts/build-rpm.sh` | `dist/mishkah-note-1.0.02-1.*.noarch.rpm` | `rpm-build` |
| Arch / Manjaro | `bash scripts/build-arch.sh` | `dist/mishkah-note-1.0.02-1-any.pkg.tar.zst` | `base-devel` |
| AppImage | `bash packaging/appimage/build-appimage.sh` | `dist/Mishkah_Note-1.0.02-x86_64.AppImage` | `appimagetool` + شبكة |
| Flatpak | `flatpak-builder --user --install-deps-from=flathub build/flatpak-build packaging/flatpak/org.mishkahnote.Mishkah.json` | تطبيق معزول أو `.flatpak` | `flatpak-builder` + `org.kde.Sdk//6.7` |
| Windows MSI | `pwsh scripts/build-msi.ps1 -Version 1.0.02` | `dist/Mishkah_Note_1.0.02_x64.msi` | Windows + WiX v5 + PyInstaller |
| الكل مرة واحدة | `bash scripts/build-all.sh` | `dist/` | ما توفّر منها |

`build-all.sh` يتخطّى أي صيغة أداتها غير مثبّتة مع رسالة صريحة، ولا يفشل بسببها.

**AppImage يحمل مفسّره**: تُنزّل `build-appimage.sh` نسخة CPython مثبَّتة
(`python-build-standalone`، الإصدار `20261124`، بايثون 3.11.18) وتضعها في
`usr/python`، ثم يحزم PySide6 و`charset-normalizer` في `usr/lib/python-packages`.
فيعمل الملف على جهاز لم يرَ بايثون قط، بحجم أكبر بنحو 40 م.ب. البدائل:

```bash
MISHKAH_PYTHON_STANDALONE_ARCHIVE=/path/to/cpython-...-install_only.tar.gz \
    bash packaging/appimage/build-appimage.sh      # بناء بلا شبكة
MISHKAH_APPIMAGE_SYSTEM_PYTHON=1 \
    bash packaging/appimage/build-appimage.sh      # بلا مفسّر (للتطوير فقط)
```

في الحالة الثانية يقول `AppRun` بالعربية والإنجليزية إن الصورة تحتاج `python3`
على النظام، بدل أن يفشل بصمت.
`build-rpm.sh` يبني شجرة `_topdir` خاصة به من `git archive`، فلا يلوّث
`~/rpmbuild` ولا يحتاج شبكة.

## ما تفعله الحزمة عند التثبيت

* تضع الشيفرة في `/usr/lib/mishkah-note` (DEB) أو `_libexecdir` (RPM) أو
  `site-packages` (wheel / PKGBUILD / Flatpak).
* تُنشئ المُشغّل `/usr/bin/mishkah` الذي يضبط `PYTHONPATH` ثم يشغّل
  `python3 -m mishkah`. (متغيّر `NOTEPAD_PYTHON` يتيح اختيار مفسّر آخر.)
* تثبّت `mishkah-note.desktop` بأسماء عشر لغات.
* تثبّت الأيقونة بثمانية أحجام (16…512) + SVG في `hicolor`.
* تثبّت `man 1 mishkah` وبيانات AppStream في `/usr/share/metainfo`، فتظهر
  التطبيق في مراكز البرامج مع لقطات وترجمة عربية.
* تحدّث `update-desktop-database` و`gtk-update-icon-cache` بعد التثبيت
  والإزالة (سكربتات `postinst` / `postrm`).

## الإشعارات القانونية · Third-party notices

البرنامج MIT، لكنه يعتمد على **Qt/PySide6 تحت LGPL v3**، وخط **IBM Plex Sans
Arabic تحت OFL-1.1**، و**charset-normalizer تحت MIT**، ومفسّر **CPython تحت
رخصة PSF**. النص الكامل ومواضع المكوّنات وكيفية استبدال مكتبات Qt في
[`THIRD-PARTY-NOTICES.md`](../THIRD-PARTY-NOTICES.md)، وهو **مضمَّن في كل حزمة**:

| الحزمة | الموضع |
|---|---|
| `.deb` / `.rpm` | `/usr/share/doc/mishkah-note/THIRD-PARTY-NOTICES.md` |
| Arch | `/usr/share/licenses/mishkah-note/THIRD-PARTY-NOTICES.md` |
| AppImage | `usr/share/doc/mishkah-note/THIRD-PARTY-NOTICES.md` داخل الصورة |
| Flatpak | `/app/share/doc/mishkah-note/THIRD-PARTY-NOTICES.md` |
| MSI | `%ProgramFiles%\Mishkah Note\THIRD-PARTY-NOTICES.md` |
| sdist | جذر الأرشيف |

`verify-packaging.sh` يفشل — لا يحذّر — إذا غاب الملف من الشيفرة أو من أي وصفة
بناء، أو إذا لم يشرح كيفية استبدال Qt: الامتثال لـ LGPL ليس زينة.

## التحقق

```bash
bash scripts/verify-packaging.sh          # بناء + فحص كل ما هو متاح
bash scripts/verify-packaging.sh --quick  # فحوص ثابتة فقط
```

يفحص السكربت:

1. أن الشيفرة تُترجم، وأن `core/` و`models/` لا تستورد Qt على مستوى الوحدة.
2. `bash -n` على كل السكربتات.
3. `.deb`: الترويسة والإصدار والمحتوى، ثم فكّ الحزمة وتشغيلها فعليًا
   (`python -m mishkah --version`) من داخل شجرة الحزمة.
4. `sdist` و`wheel`، ثم تثبيتهما مع الاعتماديات في **بيئة venv نظيفة**
   وتشغيل `mishkah --version` منها.
5. `rpmspec` / `makepkg` إن وُجدا، و`desktop-file-validate` و`appstreamcli`
   و`groff` عند توفّرها، وإلا تُعلَن "متخطّاة" لا "فاشلة".
6. `.wxs` و`AppStream` و`Flatpak JSON`: صحة XML/JSON والمفاتيح الإلزامية.
7. **الإشعارات**: وجود `THIRD-PARTY-NOTICES.md`، وذكره للرخص الأربع، وشرحه
   لاستبدال Qt، ووصولُه إلى كل وصفة بناء وإلى `.deb` و`sdist` فعليًا، وأن
   AppImage لم يعد يعتمد على مفسّر النظام.

### اختبار الدخان للحزم · Smoke test

`verify-packaging.sh` يتأكد أن الحزمة **تُبنى** وتحتوي ما يجب. أما
`scripts/smoke-test.sh` فيتأكد أنها **تعمل**، من داخلها لا من الشجرة:

```bash
bash scripts/smoke-test.sh --build                    # يبني .deb ثم يفحصه
bash scripts/smoke-test.sh --deb dist/*.deb           # حزمة موجودة
bash scripts/smoke-test.sh --appimage dist/*.AppImage # يفكّ الصورة ويشغّل AppRun
```

في كل مرة: `--version` من داخل الحزمة، ثم دورة كتابة/قراءة عربية عبر
`write_text_atomic` و`load_file` في الشيفرة المحزومة، ثم استيراد Qt وتسجيل
الخطوط وبناء نافذة بلا شاشة (`offscreen`). أدوات غائبة أو صيغة لا تُبنى هنا
تُعلَن «متخطّاة» لا «فاشلة». السكربت يعمل في CI على `.deb` المبنية.

النتيجة المتوقعة على Debian بلا أدوات RPM/Arch/Flatpak:

```
54 passed, 0 failed, 8 skipped      # verify-packaging.sh (كامل)
36 passed, 0 failed, 10 skipped     # verify-packaging.sh --quick
6 passed, 0 failed, 2 skipped       # smoke-test.sh --build بلا Qt على الجهاز
```

فحوص Qt في `smoke-test.sh` تحتاج `PySide6` **ومكتبات Qt** (`libgl1`،
`libxkbcommon0`، `libdbus-1-3`)؛ فإن غابت أُعلنت متخطّاة. في CI يُضبط
`MISHKAH_REQUIRE_QT=1`، فيصير **غياب Qt فشلًا** لا تخطيًا صامتًا: لا نريد شهادة
خضراء لم تُجرَّب فيها الحزمة مع Qt أصلًا.

## الاعتماديات

* `PySide6 >= 6.5` — الواجهة.
* `charset-normalizer >= 3.0` — كشف الترميز.
* خطوط النظام (مستحسنة لا إلزامية): `fonts-noto-core`, `fonts-noto-cjk`,
  `fonts-liberation`. الخط العربي **مضمَّن** ولا يحتاج تثبيتًا.

## Windows

`packaging/windows/mishkah.wxs` (WiX v4/v5) و`scripts/build-msi.ps1`:

1. يثبّت `pyinstaller` و`PySide6` و`charset-normalizer`، ومن ثم WiX CLI
   (`dotnet tool install --global wix`).
2. يجمّد التطبيق من `packaging/windows/mishkah.spec` (onedir، بلا console،
   بأيقونة `app.ico` والأيقونة العربية المضمّنة).
3. يحوّل `LICENSE` إلى RTF لصفحة الترخيص في المثبّت.
4. ينسخ `THIRD-PARTY-NOTICES.md` و`LICENSE.txt` إلى مجلد الحِزمة، فيصلان مع
   البرنامج إلى `Program Files` (لأن `mishkah.wxs` يشحن كل ملفات المصدر).
5. يبني `Mishkah_Note-<version>-x64.msi`: تثبيت في `Program Files`، اختصارات في
   Start Menu وسطح المكتب، ومدخل «Open with» لملفات `.txt`، مع
   `MajorUpgrade` يمنع الرجوع إلى إصدار أقدم.

لا يحتاج الجهاز الهدف إلى Python ولا PySide6. لا يمكن بناء MSI على لينكس؛
سير العمل يبنيه على `windows-latest`.

> ملاحظة: لم يُضمَّن اسم المطوّر في أي بيانات حزمة (Manufacturer =
> `Mishkah-Note contributors`)، ليبقى ذكره في نافذة «حول» فقط.

## الإصدار والنشر

```bash
# 1) رقم الإصدار: يُكتب في pyproject.toml وحده، والأداة تنشره وتتحقق منه
python3 tools/bump_version.py 1.0.02
#    يحدّث: _version.txt، PKGBUILD، spec (‏version_override + changelog)،
#    .wxs، man، metainfo (+<release>)، السير، README، والوثائق
python3 tools/check_version.py            # البوابة: كل مكان مشتق يوافق

# 2) بناء محلي والتحقق
bash scripts/verify-packaging.sh
bash scripts/smoke-test.sh --build

# 3) النشر
git tag -a v1.0.02 -m "Mishkah Note 1.0.02"
git push origin v1.0.02
```

البوابة صارمة عن قصد: أي `1.0.0x` قديم في ملف يتتبّعه git يُفشلها — بما في ذلك
التوثيق والاختبارات. الاستثناءات ثلاثة فقط: ملفات **التاريخ** التي تحتفظ بإصدارات
سابقة (`CHANGELOG.md`، إدخالات `<release>` في metainfo، و`%changelog` في spec)،
وأرقام **الأطراف الثالثة** (`5.0.2` لـ WiX، `3.11.18` لبايثون المحمول)، وسطر
يعلن نفسه صراحةً `<!-- version-gate: allow -->` حين يتحدث عن إصدار آخر عن قصد.

`docs/ci/release.yml` يبني الصيغ السبع على GitHub ويرفقها بالإصدار مع
`SHA256SUMS.txt`. راجع [docs/ci/README.md](ci/README.md) لتفعيل السير.
