# سير عمل GitHub Actions · GitHub Actions

السيران موجودان هنا (في `docs/ci/`) لا في `.github/workflows/` لأن صلاحية
الـGitHub App المستخدمة في هذا الفرع لا تستطيع كتابة ملفات سير العمل. نسخهما
مكانهما كافٍ لتفعيلهما.

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
