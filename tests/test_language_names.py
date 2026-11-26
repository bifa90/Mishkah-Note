"""The fifteen highlighting languages must speak the interface's language.

S3: the language menu and the status bar used to say "Plain text", "Shell",
"Markdown" in an otherwise fully Arabic window.  The names now come from one
table, and Arabic interface users read Arabic.
"""

from __future__ import annotations

import re

from mishkah.core import syntax

ARABIC = re.compile(r"[\u0600-\u06FF]")


def test_every_language_has_an_arabic_name():
    missing = [spec.code for spec in syntax.LANGUAGES
               if not syntax.ARABIC_NAMES.get(spec.code, "").strip()]
    assert missing == [], f"languages with no Arabic name: {missing}"


def test_the_table_has_no_orphan_entries():
    known = {spec.code for spec in syntax.LANGUAGES}
    assert set(syntax.ARABIC_NAMES) == known


def test_plain_text_and_the_word_like_names_are_arabic():
    """Words get translated; ``C``, ``JSON`` and ``SQL`` stay as they are."""
    word_like = ["plain", "python", "javascript", "typescript", "rust", "go",
                 "java", "shell", "markdown"]
    for code in word_like:
        assert ARABIC.search(syntax.ARABIC_NAMES[code]), code
    for code in ["json", "html", "css", "c", "cpp", "sql", "yaml"]:
        assert syntax.ARABIC_NAMES[code] == syntax.get_language(code).name, code


def test_display_name_switches_on_the_interface_language():
    assert syntax.display_name("python", "ar") == "بايثون"
    assert syntax.display_name("python", "en") == "Python"
    # A regional tag must not defeat the table.
    assert syntax.display_name("markdown", "ar-EG") == "ماركداون"


def test_display_name_never_returns_an_empty_label():
    for code in [spec.code for spec in syntax.LANGUAGES] + ["", None, "unknown"]:
        for language in ("ar", "en", "ru", ""):
            assert syntax.display_name(code, language).strip()


def test_unknown_language_degrades_to_plain_text():
    assert syntax.display_name("nonsense", "ar") == syntax.ARABIC_NAMES["plain"]


def test_menu_choices_follow_the_language():
    arabic = dict(syntax.language_choices("ar"))
    english = dict(syntax.language_choices("en"))
    assert arabic["python"] == "بايثون"
    assert english["python"] == "Python"
    assert set(arabic) == set(english) == {spec.code for spec in syntax.LANGUAGES}
    # Sixteen rows: fifteen grammars plus plain text.
    assert len(arabic) == 16


# --------------------------------------------------------------------------
# the two places the user actually reads the name
# --------------------------------------------------------------------------
def test_the_status_bar_shows_the_arabic_name(qapp, tmp_path):
    from mishkah.controllers.main_controller import MainController
    from mishkah.core.settings import Settings
    from mishkah.services.file_service import FileService
    from mishkah.views.main_window import MainWindow

    settings = Settings(path=tmp_path / "settings.json", restore_session=False,
                        ui_language="ar")
    window = MainWindow()
    controller = MainController(window, settings, FileService())
    try:
        editor = controller.new_document()
        editor.setPlainText("def main():\n    return 1\n")
        # Detection is what sets the content language; calling the controller
        # hook alone would only see "plain" and hide the segment.
        editor.detect_language()
        assert window.status.language_text() == "بايثون"
    finally:
        window.close()


def test_the_override_menu_is_rebuilt_in_arabic(qapp):
    from mishkah.core import i18n
    from mishkah.views.main_window import MainWindow

    previous = i18n.current_language()
    window = MainWindow()
    try:
        i18n.set_language("ar")
        window.retranslate()
        labels = [action.text()
                  for action in window._language_override_actions.values()]
        assert "بايثون" in labels
        assert "نص عادي" in labels
        assert "Python" not in labels
    finally:
        i18n.set_language(previous)
        window.close()
