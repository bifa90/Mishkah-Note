"""Language registry: the 10 most spoken languages in the world.

Each entry carries the typographic stack that renders that script best, so the
mishkah always looks native no matter which UI language is active.

Ordering follows total speakers (L1 + L2), Ethnologue 2024/2025:
English, Mandarin Chinese, Hindi, Spanish, French, Standard Arabic,
Bengali, Portuguese, Russian, Urdu.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

# Optional monospaced alternatives for users who prefer code-oriented faces.
MONO_STACK: Tuple[str, ...] = (
    "Cascadia Mono",       # Windows 11 Notepad default
    "Cascadia Code",
    "Consolas",
    "JetBrains Mono",
    "IBM Plex Mono",
    "DejaVu Sans Mono",
)

# Generic UI faces (menus, tabs, status bar) — Fluent-first so the app matches
# Windows 11 Notepad when Segoe is present, and falls back cleanly on Linux.
UI_STACK: Tuple[str, ...] = (
    "Segoe UI Variable Text",
    "Segoe UI",
    "Cantarell",
    "Noto Sans",
    "DejaVu Sans",
)


@dataclass(frozen=True)
class Language:
    code: str                      # BCP-47 tag used in the UI/Qt
    english_name: str
    native_name: str
    rtl: bool
    script: str
    fonts: Tuple[str, ...]         # script-specific reading faces, best first
    sample: str                    # string used to preview the language

    @property
    def editor_fonts(self) -> Tuple[str, ...]:
        """Reading face first; keep Arabic available in mixed-script text."""
        return tuple(dict.fromkeys(self.fonts + ("IBM Plex Sans Arabic",) + UI_STACK))

    @property
    def mono_fonts(self) -> Tuple[str, ...]:
        """Editor stack: monospace first, then this language's script faces."""
        return MONO_STACK + self.fonts

    @property
    def ui_fonts(self) -> Tuple[str, ...]:
        return tuple(list(self.fonts) + list(UI_STACK))


_LANGUAGES: Tuple[Language, ...] = (
    Language(
        code="en",
        english_name="English",
        native_name="English",
        rtl=False,
        script="Latin",
        fonts=("Noto Sans", "Segoe UI", "Liberation Sans", "DejaVu Sans"),
        sample="The quick brown fox jumps over the lazy dog.",
    ),
    Language(
        code="zh-Hans",
        english_name="Chinese (Simplified)",
        native_name="简体中文",
        rtl=False,
        script="Han",
        fonts=(
            "Noto Sans CJK SC",
            "Microsoft YaHei",
            "Source Han Sans SC",
            "WenQuanYi Micro Hei",
        ),
        sample="敏捷的棕色狐狸跳过懒狗。",
    ),
    Language(
        code="hi",
        english_name="Hindi",
        native_name="हिन्दी",
        rtl=False,
        script="Devanagari",
        fonts=("Noto Sans Devanagari", "Nirmala UI", "Mangal", "Lohit Devanagari"),
        sample="तेज़ भूरा लोमड़ी आलसी कुत्ते पर कूदता है।",
    ),
    Language(
        code="es",
        english_name="Spanish",
        native_name="Español",
        rtl=False,
        script="Latin",
        fonts=("Noto Sans", "Segoe UI", "Liberation Sans", "DejaVu Sans"),
        sample="El rápido zorro marrón salta sobre el perro perezoso.",
    ),
    Language(
        code="fr",
        english_name="French",
        native_name="Français",
        rtl=False,
        script="Latin",
        fonts=("Noto Sans", "Segoe UI", "Liberation Sans", "DejaVu Sans"),
        sample="Le rapide renard brun saute par-dessus le chien paresseux.",
    ),
    Language(
        code="ar",
        english_name="Arabic",
        native_name="العربية",
        rtl=True,
        script="Arabic",
        fonts=(
            "IBM Plex Sans Arabic",      # bundled with the application
            "Noto Naskh Arabic",
            "Amiri",
            "Noto Sans Arabic",
            "Tahoma",
        ),
        sample="نص عربي تجريبي: الثعلب البني السريع يقفز فوق الكلب الكسول.",
    ),
    Language(
        code="bn",
        english_name="Bengali",
        native_name="বাংলা",
        rtl=False,
        script="Bengali",
        fonts=("Noto Sans Bengali", "Nirmala UI", "Lohit Bengali", "Bangla MN"),
        sample="দ্রুত বাদামি শেয়াল অলস কুকুরের উপর লাফ দেয়।",
    ),
    Language(
        code="pt",
        english_name="Portuguese",
        native_name="Português",
        rtl=False,
        script="Latin",
        fonts=("Noto Sans", "Segoe UI", "Liberation Sans", "DejaVu Sans"),
        sample="A rápida raposa marrom salta sobre o cão preguiçoso.",
    ),
    Language(
        code="ru",
        english_name="Russian",
        native_name="Русский",
        rtl=False,
        script="Cyrillic",
        fonts=("Noto Sans", "PT Sans", "Segoe UI", "Liberation Sans"),
        sample="Быстрая коричневая лиса прыгает через ленивую собаку.",
    ),
    Language(
        code="ur",
        english_name="Urdu",
        native_name="اردو",
        rtl=True,
        script="Arabic (Nastaliq)",
        fonts=(
            "Noto Nastaliq Urdu",
            "Jameel Noori Nastaleeq",
            "Urdu Typesetting",
            "Noto Naskh Arabic",
            "IBM Plex Sans Arabic",
        ),
        sample="تیز بھوری لومڑی سست کتے پر چھلانگ لگاتی ہے۔",
    ),
)

BY_CODE: Dict[str, Language] = {lang.code: lang for lang in _LANGUAGES}

DEFAULT_LANGUAGE_CODE = "en"

# UI language is remembered per user; text direction is decided per document.
UI_LANGUAGE_FALLBACKS: Tuple[str, ...] = ("en",)


def all_languages() -> Tuple[Language, ...]:
    return _LANGUAGES


def get_language(code: str | None) -> Language:
    """Resolve a language tag, tolerating region subtags (``ar-EG`` → ``ar``)."""
    if not code:
        return BY_CODE[DEFAULT_LANGUAGE_CODE]
    code = code.strip()
    if code in BY_CODE:
        return BY_CODE[code]
    base = code.split("-")[0].split("_")[0].lower()
    for known, lang in BY_CODE.items():
        if known.split("-")[0].lower() == base:
            return lang
    return BY_CODE[DEFAULT_LANGUAGE_CODE]


def language_choices() -> List[Tuple[str, str]]:
    """(code, "Native — English") pairs for the language picker."""
    return [
        (lang.code, f"{lang.native_name} — {lang.english_name}")
        for lang in _LANGUAGES
    ]


def font_families_for(code: str | None, mono: bool = False) -> List[str]:
    lang = get_language(code)
    return list(lang.mono_fonts if mono else lang.editor_fonts)


def editor_font_families(code: str | None, custom_family: str = "") -> List[str]:
    """Automatic language stack, or the user's choice with script fallbacks.

    The active interface language selects the reading face. This is not content
    detection: mixed-script glyphs are resolved by Qt's font fallback engine.
    """
    families = get_language(code).editor_fonts
    custom_family = custom_family.strip()
    if custom_family:
        families = (custom_family,) + families
    return list(dict.fromkeys(families))
