# الخطوط · Fonts

لكل لغة في التطبيق **حزمة خطوط** مرتبة من الأنسب إلى البديل. يختار Qt أول خط
متاح فعليًا على النظام، لذا لا توجد حاجة لتثبيت كل شيء — لكن التثبيت يحسّن
العرض كثيرًا.

| اللغة | الحزمة (بالترتيب) | حزمة التثبيت المقترحة |
|-------|--------------------|------------------------|
| العربية | IBM Plex Sans Arabic **(مضمَّن)** → Noto Naskh Arabic → Noto Sans Arabic → Amiri | `fonts-noto-core` (Debian/Ubuntu) |
| اردو | Noto Nastaliq Urdu → Jameel Noori Nastaleeq → Noto Naskh Arabic | `fonts-noto-core` |
| 简体中文 | Microsoft YaHei → Noto Sans CJK SC → Source Han Sans SC → WenQuanYi Micro Hei | `fonts-noto-cjk` |
| हिन्दी | Nirmala UI → Noto Sans Devanagari → Mangal → Lohit Devanagari | `fonts-noto-core` |
| বাংলা | Nirmala UI → Noto Sans Bengali → Lohit Bengali | `fonts-noto-core` |
| Русский | Segoe UI → Roboto → DejaVu Sans → Liberation Sans | `fonts-dejavu-core` |
| English / Español / Français / Português | Segoe UI → Roboto → Liberation Sans → Noto Sans | `fonts-liberation` |

## التثبيت السريع · Quick install

```bash
# Debian / Ubuntu
sudo apt install fonts-noto-core fonts-noto-cjk fonts-liberation

# Fedora
sudo dnf install google-noto-sans-fonts google-noto-sans-cjk-fonts liberation-fonts

# Arch
sudo pacman -S noto-fonts noto-fonts-cjk ttf-liberation
```

## الخط المضمَّن · Bundled typeface

`src/mufakkira/resources/fonts/IBMPlexSansArabic-Light.ttf`

* **IBM Plex Sans Arabic Light**
* الرخصة: SIL Open Font License 1.1
* المصدر: <https://github.com/IBM/plex>
* يُسجَّل عند بدء التشغيل عبر `QFontDatabase.addApplicationFont()`، لذا تظهر
  العربية بشكل صحيح حتى على نظام بلا أي خط عربي.

## تجاوز يدوي · Manual override

`الإعدادات ← الخط` يتيح اختيار أي خط مثبّت على النظام. عند تركه على
«تلقائي» تُستخدم حزمة اللغة الحالية، وهو الخيار الموصى به لأنه يتبع نظام
الكتابة تلقائيًا عند تبديل لغة الواجهة.
