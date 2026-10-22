# التغليف · Packaging

كل صيغ لينكس الخمس موجودة في `packaging/`، وبناءها في `scripts/`، وملف واحد
يتحقق منها: `scripts/verify-packaging.sh`.

| الصيغة | الأمر | المخرَج | يحتاج |
|--------|-------|---------|-------|
| sdist + wheel | `python -m build` | `dist/*.tar.gz`, `dist/*.whl` | `build` |
| Debian / Ubuntu | `bash scripts/build-deb.sh` | `dist/notepad-linux_1.0.01_all.deb` | `dpkg-deb` |
| Fedora / RHEL / openSUSE | `bash scripts/build-rpm.sh` | `dist/notepad-linux-1.0.01-1.*.noarch.rpm` | `rpm-build` |
| Arch / Manjaro | `bash scripts/build-arch.sh` | `dist/notepad-linux-1.0.01-1-any.pkg.tar.zst` | `base-devel` |
| AppImage | `bash packaging/appimage/build-appimage.sh` | `dist/Notepad-1.0.01-x86_64.AppImage` | `appimagetool` |
| Flatpak | `flatpak-builder --user --install-deps-from=flathub build/flatpak-build packaging/flatpak/org.notepadlinux.Notepad.json` | تطبيق معزول أو `.flatpak` | `flatpak-builder` + `org.kde.Sdk//6.7` |
| Windows MSI | `pwsh scripts/build-msi.ps1 -Version 1.0.01` | `dist/Notepad-1.0.01-x64.msi` | Windows + WiX v5 + PyInstaller |
| الكل مرة واحدة | `bash scripts/build-all.sh` | `dist/` | ما توفّر منها |

`build-all.sh` يتخطّى أي صيغة أداتها غير مثبّتة مع رسالة صريحة، ولا يفشل بسببها.
`build-rpm.sh` يبني شجرة `_topdir` خاصة به من `git archive`، فلا يلوّث
`~/rpmbuild` ولا يحتاج شبكة.

## ما تفعله الحزمة عند التثبيت

* تضع الشيفرة في `/usr/lib/notepad-linux` (DEB) أو `_libexecdir` (RPM) أو
  `site-packages` (wheel / PKGBUILD / Flatpak).
* تُنشئ المُشغّل `/usr/bin/notepad` الذي يضبط `PYTHONPATH` ثم يشغّل
  `python3 -m mufakkira`. (متغيّر `NOTEPAD_PYTHON` يتيح اختيار مفسّر آخر.)
* تثبّت `notepad-linux.desktop` بأسماء عشر لغات.
* تثبّت الأيقونة بثمانية أحجام (16…512) + SVG في `hicolor`.
* تثبّت `man 1 notepad` وبيانات AppStream في `/usr/share/metainfo`، فتظهر
  التطبيق في مراكز البرامج مع لقطات وترجمة عربية.
* تحدّث `update-desktop-database` و`gtk-update-icon-cache` بعد التثبيت
  والإزالة (سكربتات `postinst` / `postrm`).

## التحقق

```bash
bash scripts/verify-packaging.sh          # بناء + فحص كل ما هو متاح
bash scripts/verify-packaging.sh --quick  # فحوص ثابتة فقط
```

يفحص السكربت:

1. أن الشيفرة تُترجم، وأن `core/` و`models/` لا تستورد Qt على مستوى الوحدة.
2. `bash -n` على كل السكربتات.
3. `.deb`: الترويسة والإصدار والمحتوى، ثم فكّ الحزمة وتشغيلها فعليًا
   (`python -m mufakkira --version`) من داخل شجرة الحزمة.
4. `sdist` و`wheel`، ثم تثبيتهما مع الاعتماديات في **بيئة venv نظيفة**
   وتشغيل `notepad --version` منها.
5. `rpmspec` / `makepkg` إن وُجدا، و`desktop-file-validate` و`appstreamcli`
   و`groff` عند توفّرها، وإلا تُعلَن "متخطّاة" لا "فاشلة".
6. `.wxs` و`AppStream` و`Flatpak JSON`: صحة XML/JSON والمفاتيح الإلزامية.

النتيجة المتوقعة على Debian بلا أدوات RPM/Arch/Flatpak:

```
36 passed, 0 failed, 8 skipped
```

## الاعتماديات

* `PySide6 >= 6.5` — الواجهة.
* `charset-normalizer >= 3.0` — كشف الترميز.
* خطوط النظام (مستحسنة لا إلزامية): `fonts-noto-core`, `fonts-noto-cjk`,
  `fonts-liberation`. الخط العربي **مضمَّن** ولا يحتاج تثبيتًا.

## Windows

`packaging/windows/notepad.wxs` (WiX v4/v5) و`scripts/build-msi.ps1`:

1. يثبّت `pyinstaller` و`PySide6` و`charset-normalizer`، ومن ثم WiX CLI
   (`dotnet tool install --global wix`).
2. يجمّد التطبيق من `packaging/windows/notepad.spec` (onedir، بلا console،
   بأيقونة `app.ico` والأيقونة العربية المضمّنة).
3. يحوّل `LICENSE` إلى RTF لصفحة الترخيص في المثبّت.
4. يبني `Notepad-<version>-x64.msi`: تثبيت في `Program Files`، اختصارات في
   Start Menu وسطح المكتب، ومدخل «Open with» لملفات `.txt`، مع
   `MajorUpgrade` يمنع الرجوع إلى إصدار أقدم.

لا يحتاج الجهاز الهدف إلى Python ولا PySide6. لا يمكن بناء MSI على لينكس؛
سير العمل يبنيه على `windows-latest`.

> ملاحظة: لم يُضمَّن اسم المطوّر في أي بيانات حزمة (Manufacturer =
> `Notepad-Linux contributors`)، ليبقى ذكره في نافذة «حول» فقط.

## الإصدار والنشر

```bash
# 1) رقم الإصدار في مكان واحد يُغذّي البقية
$EDITOR pyproject.toml            # version = "1.0.01"
#    ثم: src/mufakkira/__init__.py، packaging/arch/PKGBUILD، man، CHANGELOG

# 2) بناء محلي والتحقق
bash scripts/verify-packaging.sh

# 3) وسم وإصدار
git tag -a v1.0.01 -m "Notepad 1.0.01"
git push origin v1.0.01
```

`docs/ci/release.yml` يبني الصيغ السبع على GitHub ويرفقها بالإصدار مع
`SHA256SUMS.txt`. راجع [docs/ci/README.md](ci/README.md) لتفعيل السير.
