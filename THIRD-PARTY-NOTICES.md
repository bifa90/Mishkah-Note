# إشعارات الأطراف الثالثة · Third-Party Notices

**مفكرة مشكاة · Mishkah Note** — الإصدار 1.0.02
هذا الملف يوضّح رخصة البرنامج نفسه، ورخص كل ما يُوزَّع معه داخل الحزم، وكيف يمكنك استبدال
المكوّنات التي تفرض رخصتها ذلك. وهو مُضمَّن في **كل** حزمة نُصدرها:

| الحزمة | موضع الملف داخلها |
|---|---|
| `.deb` | `/usr/share/doc/mishkah-note/THIRD-PARTY-NOTICES.md` |
| `.rpm` | `/usr/share/doc/mishkah-note/THIRD-PARTY-NOTICES.md` |
| Arch (`pkg.tar.zst`) | `/usr/share/licenses/mishkah-note/THIRD-PARTY-NOTICES.md` |
| AppImage | `usr/share/doc/mishkah-note/THIRD-PARTY-NOTICES.md` داخل الصورة |
| Flatpak | `/app/share/doc/mishkah-note/THIRD-PARTY-NOTICES.md` |
| MSI (Windows) | `%ProgramFiles%\Mishkah Note\THIRD-PARTY-NOTICES.md` |

---

## 1 · البرنامج نفسه

**Mishkah Note** — رخصة MIT، نصها الكامل في `LICENSE`. لا ضمان من أي نوع.

---

## 2 · المكتبات التي تعتمد عليها النسخ المصدريّة والحزم النظامية

هذه الحزم **لا تحتوي** مكتبات Qt؛ بل تطلبها من نظامك (اعتمادًا) أو من زمن تشغيل Flatpak.
وحيث تُحمَّل المكتبات ديناميكيًا في وقت التشغيل، تبقى قابلة للاستبدال بحزمة النظام.

| المكوّن | الرخصة | ملاحظة |
|---|---|---|
| **Qt 6** (Core · Gui · Widgets · PrintSupport · Svg · Network · DBus) | **LGPL v3** (أو GPL v3 أو تجارية) | تُحمَّل ديناميكيًا من حزمة النظام |
| **PySide6** و **Shiboken6** | **LGPL v3** (أو GPL v3 أو تجارية) | غلاف بايثون لـ Qt؛ ديناميكي |
| **charset-normalizer** | MIT | كشف الترميز |
| **IBM Plex Sans Arabic** (الخطوط المضمّنة) | **SIL Open Font License 1.1** | النص في `src/mishkah/resources/fonts/OFL.txt` |
| **Python 3** (المفسّر) | PSF License Agreement | يوفّره نظامك |
| خطوط النظام (Noto، Liberation…) | رخصها الخاصة | غير محزومة |

---

## 3 · ما يُحزَم داخل AppImage و MSI (مهم)

حزمة **AppImage** و**حزمة Windows (MSI)** تحزمان معهما **مكتبات Qt وPySide6** ومفسّر
**CPython** لتشغيل البرنامج بلا تثبيت مسبق. وهذا يجعل الإفصاح التالي إلزاميًا:

| المكوّن | الرخصة | أين يوجد |
|---|---|---|
| Qt 6 / PySide6 / Shiboken6 | LGPL v3 | `usr/lib/python-packages/PySide6/Qt/lib` (AppImage) · `_internal\PySide6\Qt6` (MSI) |
| CPython 3.11 (مفسّر محمول) | PSF License Agreement | `usr/python` (AppImage) · `_internal\python3*.dll` (MSI) |
| PyInstaller bootloader | GPL v2 مع استثناء المُقلِّع | MSI فقط |
| charset-normalizer | MIT | حزم بايثون المحزومة |
| pip · setuptools | MIT | داخل مفسّر AppImage المحمول |

### كيف تستبدل مكتبات Qt (حق تكفله LGPL v3)

- **AppImage:** فُكّ الصورة (`Mishkah_Note-*.AppImage --appimage-extract`)، استبدل الملفات داخل
  `squashfs-root/usr/lib/python-packages/PySide6/Qt/lib` بنسخة متوافقة من عندك، وأعد التشغيل
  عبر `squashfs-root/AppRun`. ويمكنك أيضًا حزم نسخة معدَّلة من الصورة وإعادة توزيعها وفق LGPL v3.
- **MSI:** استبدل الملفات داخل `%ProgramFiles%\Mishkah Note\_internal\PySide6\Qt6\bin`
  و`...\plugins` بنسخة متوافقة تحمل الاسم نفسه.
- **deb / rpm / Arch / Flatpak:** لا شيء محزوم؛ حدّث `python3-pyside6` (أو `pyside6`) من مدير
  حزم توزيعتك، أو زمن تشغيل Flatpak، وسيستخدم البرنامج النسخة الجديدة.

### مصدر الشيفرة المقابلة

- Qt: <https://download.qt.io/official_releases/qt/>
- PySide6: <https://pypi.org/project/PySide6/> · <https://code.qt.io/cgit/pyside/pyside-setup.git/>
- CPython: <https://www.python.org/downloads/source/>
- pyenv-style المحمول المستخدم في AppImage: <https://github.com/astral-sh/python-build-standalone>
- charset-normalizer: <https://pypi.org/project/charset-normalizer/>
- IBM Plex: <https://github.com/IBM/plex>

---

## 4 · أدوات البناء (لا تُوزَّع مع البرنامج)

| الأداة | الرخصة | الاستخدام |
|---|---|---|
| PyInstaller | GPL v2 + استثناء | تجميد نسخة ويندوز |
| WiX Toolset | MS-RL | بناء MSI |
| appimagetool | MIT | بناء AppImage |
| flatpak-builder | LGPL v2+ | بناء Flatpak |
| dpkg / rpmbuild / makepkg | GPL وغيرها | بناء الحزم |

---

## 5 · لا ضمان

البرنامج والمكوّنات أعلاه تُقدَّم «كما هي»، بلا ضمان صريح أو ضمني، إلى الحد الذي تسمح به
رخصها. راجع نص كل رخصة للتفاصيل؛ وعند التعارض في أي لغة، يكون النص الإنجليزي للرخصة هو
المرجع.

## English summary

Mishkah Note itself is MIT (see `LICENSE`). It uses **Qt 6 and PySide6** under the **LGPL v3**,
dynamically loaded from the system in the deb, rpm, Arch and Flatpak packages; the **AppImage and
the Windows MSI bundle** those libraries and a **CPython** runtime, and this file states where they
live and how to replace them, as the LGPL requires. `charset-normalizer` is MIT, the bundled
**IBM Plex Sans Arabic** font is under the **SIL OFL 1.1** (`OFL.txt` ships with it), and the
CPython interpreter is covered by the **PSF License Agreement**. No warranty is given.
