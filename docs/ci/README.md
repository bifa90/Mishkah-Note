# سير عمل GitHub Actions · GitHub Actions

الملفات المفعّلة موجودة في `.github/workflows/`، وهذه النسخ المرجعية في
`docs/ci/`. عند تعديلها انسخ القوالب لتبقى النسختان متطابقتين:

```bash
mkdir -p .github/workflows
cp docs/ci/ci.yml docs/ci/release.yml .github/workflows/
git add .github/workflows
git commit -m "ci: enable the test and release workflows"
git push
```

| الملف | متى يعمل | ماذا يفعل |
|-------|-----------|-----------|
| `ci.yml` | كل دفعة إلى `main` أو `arena/**`، وكل PR، ويدويًا | `ruff` + `pytest` على Python 3.9/3.11/3.13، ثم فحص التغليف: بناء `.deb` و`sdist` و`wheel`، والتثبيت في بيئة نظيفة، والتحقق من الأيقونات والـAppStream |
| `release.yml` | عند دفع وسم `v*` أو يدويًا | يبني **كل** الصيغ: `.deb`، `.rpm`، `.pkg.tar.zst`، `.AppImage`، `.flatpak`، `.msi` (على `windows-latest`)، ثم يرفقها بالإصدار مع `SHA256SUMS.txt` |

## ما يحتاجه السير

* لا أسرار إضافية: يُستخدم `GITHUB_TOKEN` المدمج (صلاحية `contents: write`).
* الأصول تُرفع عبر `gh release upload` من GitHub Actions؛ الرفع يحتاج الوصول إلى
  `uploads.github.com`، وهو محجوب في بيئة هذه الجلسة.
* وظيفة Flatpak هي الأبطأ (تنزيل `org.kde.Sdk//6.7` من Flathub، نحو 1.5 GB).

## البناء يدويًا على جهازك

```bash
bash scripts/verify-packaging.sh     # كل ما يمكن التحقق منه محليًا
bash scripts/build-deb.sh            # dist/mishkah-note_<version>_all.deb
bash scripts/build-rpm.sh            # يحتاج rpmbuild
bash scripts/build-arch.sh           # يحتاج makepkg (Arch)
bash packaging/appimage/build-appimage.sh   # يحتاج appimagetool
flatpak-builder --user --install-deps-from=flathub build/flatpak-build \
    packaging/flatpak/org.mishkahnote.Mishkah.json
pwsh scripts/build-msi.ps1 -Version <version>   # على Windows فقط
```

## شروط نشر 1.0.01

- يُبنى المصدر الذي يشير إليه `v1.0.01` في جميع وظائف البناء، حتى عند التشغيل اليدوي.
- يجب أن يشير الوسم إلى commit الهوية الحالية المقصود نشره، لا إلى مصدر مختلف.
- تمر الاختبارات وفحوص التغليف قبل بدء بناء الحزم.
- تُرفق ثماني حزم: wheel وsdist وDebian وRPM وArch وAppImage وFlatpak وMSI.
- يتحقق `tools/check_release_assets.py` من اكتمال الأسماء ووجود ملفات غير فارغة؛
  هذا فحص اكتمال، وليس بديلًا عن اختبار تشغيل كل حزمة.
- صور التطبيق الفعلية تُحفظ كأثر Actions باسم `screenshots` للمراجعة البصرية،
  ولا تدخل ضمن ملفات الحزم المنشورة.
- لا تُعدّل ملفات التوثيق في `docs/ci/` إعدادات GitHub تلقائيًا؛ يجب نسخها
  إلى `.github/workflows/` باستخدام صلاحية مناسبة.

بعد تفعيل السير وتثبيت الوسم على المصدر المعتمد:

```bash
gh workflow run release.yml --repo bifa90/Mishkah-Note --ref main -f tag=v1.0.01
gh run list --repo bifa90/Mishkah-Note --workflow release.yml
gh release view v1.0.01 --repo bifa90/Mishkah-Note --json name,assets
```
