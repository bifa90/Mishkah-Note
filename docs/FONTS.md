# الخطوط · Fonts

## خط الكتابة التلقائي

اختيار «تلقائي» في **الإعدادات ← الخط** يضع خط القراءة المناسب للغة الواجهة
أولًا، دون تقديم الخطوط أحادية العرض عليه. هذه ترشيحات للوضوح والاتساق؛
لا يوجد خط رسمي إلزامي لكل لغة ولا حكم جمالي يناسب جميع المستخدمين.

| لغة الواجهة | خط الكتابة المفضّل | البدائل عند عدم توفره |
|---|---|---|
| العربية `ar` | **IBM Plex Sans Arabic — Regular (مضمّن)** | Noto Naskh Arabic، Amiri، Noto Sans Arabic، Tahoma |
| الإنجليزية `en` | Noto Sans | Segoe UI، Liberation Sans، DejaVu Sans |
| الإسبانية `es` | Noto Sans | Segoe UI، Liberation Sans، DejaVu Sans |
| الفرنسية `fr` | Noto Sans | Segoe UI، Liberation Sans، DejaVu Sans |
| البرتغالية `pt` | Noto Sans | Segoe UI، Liberation Sans، DejaVu Sans |
| الروسية `ru` | Noto Sans | PT Sans، Segoe UI، Liberation Sans |
| الصينية المبسطة `zh-Hans` | Noto Sans CJK SC | Microsoft YaHei، Source Han Sans SC، WenQuanYi Micro Hei |
| الهندية `hi` | Noto Sans Devanagari | Nirmala UI، Mangal، Lohit Devanagari |
| البنغالية `bn` | Noto Sans Bengali | Nirmala UI، Lohit Bengali، Bangla MN |
| الأردية `ur` | Noto Nastaliq Urdu | Jameel Noori Nastaleeq، Urdu Typesetting، Noto Naskh Arabic، IBM Plex Sans Arabic |

IBM Plex Sans Arabic مضمّن ويُسجّل عند بدء التطبيق. الخطوط الأخرى ترشيحات
لخطوط النظام، وليست مضمّنة أو منزّلة تلقائيًا؛ يختار Qt البديل المتاح عند
غيابها. يبقى IBM Plex Sans Arabic ضمن بدائل المحرّر لكل اللغات للنصوص المختلطة.
اختيار العائلة مرتبط بلغة الواجهة، وليس كشفًا تلقائيًا للغة كل مستند؛
يتولى Qt بدائل المحارف عند مزج أنظمة الكتابة.

## أساس الترشيح · Sources

- [IBM Plex — المصدر الرسمي والترخيص](https://github.com/IBM/plex): عائلة مفتوحة
  تدعم العربية، مع وزن Regular مضمّن للكتابة اليومية.
- [توصيات Noto للاستخدام](https://notofonts.github.io/noto-docs/website/use/):
  Noto Sans للاتينية والسيريلية، ونسخ نظام الكتابة للمستندات الهندية والبنغالية.
- [Noto CJK](https://github.com/notofonts/noto-cjk): خطوط الصينية واليابانية والكورية.
- [Noto Nastaliq](https://github.com/notofonts/nastaliq): عائلة متخصصة للكتابة بالنستعليق.

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

`src/mishkah/resources/fonts/IBMPlexSansArabic-Regular.ttf`

وتتوفر أيضًا نسخة Light داخل الموارد.

* **IBM Plex Sans Arabic Regular**
* الرخصة: SIL Open Font License 1.1، ونصها في `src/mishkah/resources/fonts/OFL.txt`
* المصدر: <https://github.com/IBM/plex>
* يُسجَّل عند بدء التشغيل عبر `QFontDatabase.addApplicationFont()`، لذا تظهر
  العربية بشكل صحيح حتى على نظام بلا أي خط عربي.

## تجاوز يدوي · Manual override

`الإعدادات ← الخط` متاح لكل المستخدمين في اللغات العشر، ويتيح اختيار أي خط
مثبّت على النظام، بما فيه الخطوط أحادية العرض. يُحفظ اختيار المستخدم ويظل
مقدّمًا على الترشيحات عند تبديل لغة الواجهة؛ اختيار «تلقائي» يعيد ترشيح اللغة. عند تركه على
«تلقائي» تُستخدم حزمة اللغة الحالية، وهو الخيار الموصى به لأنه يتبع نظام
الكتابة تلقائيًا عند تبديل لغة الواجهة.
