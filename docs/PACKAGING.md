# التغليف · Packaging

كل ما يلزم لبناء حزم التوزيعات موجود في `packaging/`، والبناء الفعلي في
`scripts/`.

| الصيغة | الأمر | المخرَج | يحتاج |
|--------|-------|---------|-------|
| sdist + wheel | `python -m build` | `dist/*.tar.gz`, `dist/*.whl` | `build` |
| Debian/Ubuntu | `scripts/build-deb.sh` | `dist/notepad-linux_2.0.0_all.deb` | `dpkg-deb` |
| Fedora/RHEL/SUSE | `rpmbuild -ba packaging/rpm/notepad-linux.spec` | `~/rpmbuild/RPMS/noarch/*.rpm` | `rpm-build` |
| Arch/Manjaro | `cd packaging/arch && makepkg -si` | `*.pkg.tar.zst` | `base-devel` |
| Flatpak | `flatpak-builder --install --user build packaging/flatpak/org.notepadlinux.Notepad.json` | تطبيق معزول | `flatpak-builder`, `org.kde.Sdk` |
| AppImage | `packaging/appimage/build-appimage.sh` | `dist/Notepad-2.0.0-x86_64.AppImage` | `appimagetool` |
| الكل مرة واحدة | `scripts/build-all.sh` | `dist/` | ما توفّر منها |

`scripts/build-all.sh` يتخطّى أي صيغة أداتها غير مثبّتة مع رسالة صريحة،
ولا يفشل بسببها.

## ما تفعله الحزمة عند التثبيت

* تضع الشيفرة في `/usr/lib/notepad-linux` (DEB) أو `_libexecdir` (RPM)
  أو `site-packages` (wheel/PKGBUILD).
* تُنشئ المُشغّل `/usr/bin/notepad` الذي يضبط `PYTHONPATH` ثم يشغّل
  `python3 -m mufakkira`.
* تثبّت `notepad-linux.desktop` بأسماء عربية وبأسماء لغات أخرى.
* تثبّت الأيقونة بثمانية أحجام (16…512) + SVG في `hicolor`، لتظهر حادّة في
  القوائم وشريط المهام ومراكز البرامج.
* تثبّت صفحة الدليل `man 1 notepad`.

## التحقق قبل النشر

```bash
# محتوى الحزمة
dpkg-deb -c dist/notepad-linux_2.0.0_all.deb | less
dpkg-deb -I dist/notepad-linux_2.0.0_all.deb
lintian dist/notepad-linux_2.0.0_all.deb      # إن كان مثبتًا

# تثبيت تجريبي بلا صلاحيات جذر
dpkg-deb -x dist/notepad-linux_2.0.0_all.deb /tmp/install-test
PYTHONPATH=/tmp/install-test/usr/lib/notepad-linux \
    QT_QPA_PLATFORM=offscreen python3 -m mufakkira --version

# الحزمة البرمجية
python -m venv /tmp/venv-test
/tmp/venv-test/bin/pip install dist/notepad_linux-2.0.0-py3-none-any.whl
/tmp/venv-test/bin/notepad --version
```

## الاعتماديات

* `PySide6 >= 6.5` — الواجهة.
* `charset-normalizer >= 3.0` — كشف الترميز.
* خطوط النظام (اختياري لكنه موصى به): `fonts-noto-core`, `fonts-noto-cjk`,
  `fonts-liberation`. الخط العربي **مضمَّن** ولا يحتاج تثبيتًا.

## Windows

حزمة MSI خارج نطاق هذا المستودع بطلب من صاحب المشروع؛ عند الحاجة يكفي
`python -m pip install .` ثم `cx_Freeze` أو `pynsist` مع
`src/mufakkira/resources/icons/app.ico` الموجود أصلًا هنا.

## الإصدار

غيّر `version` في `pyproject.toml` و`__version__` في
`src/mufakkira/__init__.py`، وأضف قسمًا في `CHANGELOG.md`، ثم أعد البناء.
سكربتات الحزم تقرأ الرقم من `pyproject.toml` تلقائيًا.
