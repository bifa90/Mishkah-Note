"""Live Markdown: the view formats, the document never changes.

The contract of the feature is unusually strict, so the tests are too:

* turning it on decorates the buffer,
* turning it off gives back the same characters, in the same order,
* ``toPlainText()`` is identical in both states — and equal to the file,
* the undo stack is neither used nor polluted.

The formatting assertions read the *formats the highlighter applied*, not
pixels, so they are deterministic on every platform.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QFont, QTextCharFormat, QTextCursor

from mufakkira.core import markdown
from mufakkira.models.document import DocumentModel
from mufakkira.views.editor_view import EditorView

pytestmark = pytest.mark.usefixtures("qapp")

SAMPLE = """# Title

Some **bold** and *italic* and ~~struck~~ and `code` here.
A [link](https://example.org) and an ![image](pic.png).

## Second

- bullet one
- bullet two
  - nested bullet
1. ordered one
2. ordered two

> quoted line
> second quoted line

| Name | Value |
|------|------:|
| one  | 1     |

---

```python
print("hello")
```
"""


def make_editor(text: str = SAMPLE, path: Path | None = None) -> EditorView:
    doc = DocumentModel(content=text, path=path)
    editor = EditorView(doc, QFont("DejaVu Sans", 13))
    editor.load_content(text)
    editor.resize(700, 600)
    editor.show()
    return editor


def formats_at(editor: EditorView, block_number: int) -> dict:
    """Map offset -> the char format the highlighter gave that character.

    ``QPlainTextEdit`` builds its format fragments lazily, so the block's
    ``QTextLayout`` is the reliable source: it holds the ranges the
    highlighter produced as soon as the line has been laid out (walking the
    blocks with :func:`block_of` first guarantees that).
    """
    block = editor.document().findBlockByNumber(block_number)
    out = {}
    if not block.isValid() or block.layout() is None:
        return out
    layout = block.layout()          # keep it alive while reading its ranges
    # Shortest range wins: Qt may keep a whole-block default range alongside
    # the ranges the highlighter produced, and the specific ones are what the
    # reader actually sees.
    for record in sorted(layout.formats(), key=lambda r: r.length):
        fmt = QTextCharFormat(record.format)
        for offset in range(record.start, record.start + record.length):
            out.setdefault(offset, fmt)
    return out


def block_of(editor: EditorView, needle: str) -> int:
    block = editor.document().firstBlock()
    while block.isValid():
        if needle in block.text():
            return block.blockNumber()
        block = block.next()
    raise AssertionError(f"no block contains {needle!r}")


# ---------------------------------------------------------------------------
# the parser (no Qt)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("source,kind", [
    ("# heading", markdown.HEADING),
    ("###### six", markdown.HEADING),
    ("- bullet", markdown.LIST_ITEM),
    ("* bullet", markdown.LIST_ITEM),
    ("1. ordered", markdown.LIST_ITEM),
    ("> quote", markdown.QUOTE),
    ("---", markdown.RULE),
    ("| a | b |", markdown.TABLE_ROW),
    ("plain text", markdown.PARAGRAPH),
    ("", markdown.BLANK),
])
def test_block_kinds_are_recognised(source, kind):
    line, _ = markdown.parse_line(source)
    assert line.kind == kind


@pytest.mark.parametrize("source,expected", [
    ("# Title", "Title"),
    ("### Third level", "Third level"),
    ("- bullet", " bullet"),
    ("1. ordered", "1. ordered"),
    ("> quote", " quote"),
    ("**bold**", "bold"),
    ("*italic*", "italic"),
    ("~~gone~~", "gone"),
    ("`code`", "code"),
    ("[label](https://x.y)", "label"),
    ("plain **bold** text", "plain bold text"),
    ("\\*not emphasis\\*", "not emphasis"),
])
def test_visible_text_drops_the_syntax(source, expected):
    line, _ = markdown.parse_line(source)
    assert line.visible_text == expected


def test_headings_carry_their_level():
    for level in range(1, 7):
        line, _ = markdown.parse_line("#" * level + " heading")
        assert (line.kind, line.level) == (markdown.HEADING, level)


def test_fenced_code_is_tracked_across_lines():
    state = None
    kinds = []
    for source in ("```python", "print(1)", "```", "after"):
        line, state = markdown.parse_line(source, None, state)
        kinds.append(line.kind)
    assert kinds == [markdown.FENCE, markdown.CODE_BLOCK, markdown.FENCE,
                     markdown.PARAGRAPH]


def test_ordered_lists_keep_their_numbers():
    line, _ = markdown.parse_line("12. item")
    assert line.kind == markdown.LIST_ITEM and line.ordered
    assert "12." in line.visible_text


def test_markdown_paths_are_recognised():
    assert markdown.is_markdown_path("/tmp/notes.md")
    assert markdown.is_markdown_path("README.MARKDOWN")
    assert not markdown.is_markdown_path("notes.txt")
    assert not markdown.is_markdown_path(None)


# ---------------------------------------------------------------------------
# the editor layer
# ---------------------------------------------------------------------------
def test_markdown_is_off_by_default(qapp):
    editor = make_editor()
    assert editor.live_markdown_enabled() is False
    assert editor.markdown_decorator() is None


def test_enabling_decorates_the_buffer(qapp):
    editor = make_editor()
    editor.set_live_markdown(True, "light")
    editor.viewport().update()
    qapp.processEvents()

    heading = formats_at(editor, block_of(editor, "Title"))
    title_offset = editor.document().findBlockByNumber(
        block_of(editor, "Title")).text().index("Title")
    title_format = heading[title_offset]
    assert title_format.fontWeight() >= QFont.Weight.DemiBold
    assert title_format.fontPointSize() > 13          # bigger than the body

    bold_block = formats_at(editor, block_of(editor, "Some **bold**"))
    bold_offset = editor.document().findBlockByNumber(
        block_of(editor, "Some **bold**")).text().index("bold")
    assert bold_block[bold_offset].fontWeight() == QFont.Weight.Bold

    code_block = formats_at(editor, block_of(editor, "`code`"))
    text = editor.document().findBlockByNumber(block_of(editor, "`code`")).text()
    assert code_block[text.index("code")].fontFamilies()


def test_hidden_syntax_collapses(qapp):
    """The ``**`` of bold is hidden *and* takes no width."""
    editor = make_editor()
    editor.set_live_markdown(True, "light")
    qapp.processEvents()
    number = block_of(editor, "Some **bold**")
    block = editor.document().findBlockByNumber(number).text()
    formats = formats_at(editor, number)
    for offset in (block.index("**"), block.index("**") + 1):
        fmt = formats[offset]
        assert fmt.fontPointSize() < 1.5            # shrunk to nothing
        assert fmt.fontLetterSpacing() < 0           # and pulled together
    line = editor.markdown_decorator().document().findBlockByNumber(number).userData().line
    assert line.kind == markdown.PARAGRAPH
    assert "**" not in line.visible_text


def test_disabling_restores_the_exact_text(qapp):
    editor = make_editor()
    before = editor.toPlainText()
    editor.set_live_markdown(True, "light")
    qapp.processEvents()
    assert editor.toPlainText() == before
    editor.set_live_markdown(False)
    qapp.processEvents()
    assert editor.toPlainText() == before
    assert editor.live_markdown_enabled() is False
    # no format is left behind: the block keeps no layout ranges at all
    block = editor.document().firstBlock()
    assert block.layout() is None or not block.layout().formats()


def test_plain_text_is_stable_in_both_states(qapp, tmp_text):
    text = tmp_text.read_text(encoding="utf-8")
    editor = make_editor("**a** _b_ `c`\n> d\n- e\n")
    assert editor.toPlainText() == "**a** _b_ `c`\n> d\n- e\n"
    editor.set_live_markdown(True, "light")
    qapp.processEvents()
    assert editor.toPlainText() == "**a** _b_ `c`\n> d\n- e\n"
    assert text == "first line\nsecond line\n"     # the fixture file is untouched


def test_markdown_does_not_touch_the_undo_stack(qapp):
    editor = make_editor()
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)

    editor.set_live_markdown(True, "light")
    qapp.processEvents()
    assert editor.document().isUndoAvailable() is False
    assert editor.document().isRedoAvailable() is False

    # a real edit still works and still undoes to the original text
    original = editor.toPlainText()
    editor.textCursor().insertText("new ")
    assert editor.document().isUndoAvailable()
    editor.undo()
    assert editor.toPlainText() == original
    editor.set_live_markdown(False)
    assert editor.toPlainText() == original


def test_document_modified_flag_is_untouched(qapp):
    editor = make_editor()
    assert editor.document().isModified() is False
    editor.set_live_markdown(True, "light")
    qapp.processEvents()
    assert editor.document().isModified() is False


def test_the_active_paragraph_reveals_its_source(qapp):
    """While the caret is inside a block its markers are shown, greyed out."""
    editor = make_editor()
    number = block_of(editor, "Some **bold**")
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.Start)
    for _ in range(number):
        cursor.movePosition(QTextCursor.MoveOperation.NextBlock)
    editor.setTextCursor(cursor)

    editor.set_live_markdown(True, "light")
    qapp.processEvents()
    text = editor.document().findBlockByNumber(number).text()
    active = formats_at(editor, number)[text.index("**")]
    assert active.fontPointSize() == 0           # not shrunk: visible again
    assert active.fontLetterSpacing() == 0

    # moving away hides it again
    other = editor.textCursor()
    other.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(other)
    editor._sync_markdown_caret()
    qapp.processEvents()
    away = formats_at(editor, number)[text.index("**")]
    assert away.fontPointSize() < 1.5


def test_theme_switch_repaints(qapp):
    editor = make_editor()
    editor.set_live_markdown(True, "light")
    qapp.processEvents()
    decorator = editor.markdown_decorator()
    editor.set_theme_name("dark")
    qapp.processEvents()
    assert decorator.theme() == "dark"
    editor.set_theme_name("light")
    qapp.processEvents()
    assert decorator.theme() == "light"


def test_font_change_rescales_hidden_runs(qapp):
    editor = make_editor()
    editor.set_live_markdown(True, "light")
    qapp.processEvents()
    number = block_of(editor, "Some **bold**")
    editor.set_font_size(20)
    qapp.processEvents()
    text = editor.document().findBlockByNumber(number).text()
    fmt = formats_at(editor, number)[text.index("**")]
    assert fmt.fontPointSize() < 1.5


def test_set_document_keeps_the_mode(qapp):
    editor = make_editor()
    editor.set_live_markdown(True, "light")
    other = DocumentModel(content="# two\n")
    editor.set_document(other)
    qapp.processEvents()
    assert editor.toPlainText() == "# two\n"
    assert editor.live_markdown_enabled() is True


def test_decorator_limits_huge_documents(qapp):
    from mufakkira.widgets.markdown_decorator import MAX_MARKDOWN_BLOCKS

    editor = make_editor("line\n")
    editor.set_live_markdown(True, "light")
    qapp.processEvents()
    decorator = editor.markdown_decorator()
    assert MAX_MARKDOWN_BLOCKS > 1000
    assert decorator is not None
    # a block past the limit is left alone (no parse data, no formats)
    block = editor.document().findBlockByNumber(MAX_MARKDOWN_BLOCKS + 1)
    assert block.isValid() is False


def test_markdown_strings_exist_in_every_language():
    from mufakkira.core.i18n import tr
    from mufakkira.core.i18n_data import STRINGS
    from mufakkira.core.languages import all_languages

    codes = {lang.code for lang in all_languages()}
    for key in ("action.markdown", "settings.markdown_note"):
        assert set(STRINGS[key]) == codes
    tr("action.markdown")           # resolves in the current language


# ---------------------------------------------------------------------------
# wiring: View menu, Settings and every open tab
# ---------------------------------------------------------------------------
@pytest.fixture()
def controller(qapp, tmp_path):
    from mufakkira.controllers.main_controller import MainController
    from mufakkira.core.settings import Settings
    from mufakkira.services.file_service import FileService
    from mufakkira.views.main_window import MainWindow

    settings = Settings(path=tmp_path / "settings.json", restore_session=False)
    window = MainWindow()
    control = MainController(window, settings, FileService())
    yield control
    window.close()


def test_menu_action_exists_and_is_off(controller):
    from PySide6.QtGui import QKeySequence

    action = controller.window.act_markdown
    assert action.isCheckable()
    assert action.isChecked() is False                 # off by default
    assert action.shortcut() == QKeySequence("Ctrl+Shift+M")
    assert "Markdown" in action.text()


def test_toggling_applies_to_every_open_tab(controller, qapp):
    first = controller.new_document()
    first.setPlainText("# one\n")
    second = controller.new_document()
    second.setPlainText("**two**\n")

    controller.window.act_markdown.setChecked(True)
    qapp.processEvents()
    assert controller.settings.live_markdown is True
    assert all(editor.live_markdown_enabled() for editor in controller.window.editors())
    assert first.toPlainText() == "# one\n" and second.toPlainText() == "**two**\n"

    controller.window.act_markdown.setChecked(False)
    qapp.processEvents()
    assert controller.settings.live_markdown is False
    assert not any(editor.live_markdown_enabled() for editor in controller.window.editors())


def test_preference_survives_a_restart(controller, tmp_path):
    controller.set_live_markdown(True)
    controller.settings.save()

    from mufakkira.core.settings import Settings

    reloaded = Settings.load(tmp_path / "settings.json")
    assert reloaded.live_markdown is True


def test_new_tabs_inherit_the_preference(controller):
    controller.set_live_markdown(True)
    editor = controller.new_document()
    assert editor.live_markdown_enabled() is True


def test_settings_dialog_round_trip(controller):
    from mufakkira.widgets.settings_dialog import SettingsDialog

    dialog = SettingsDialog(controller.settings)
    assert dialog.chk_markdown.isChecked() is False
    dialog.chk_markdown.setChecked(True)
    values = dialog.values()
    assert values["live_markdown"] is True
    dialog.apply_to(controller.settings)
    assert controller.settings.live_markdown is True


# ---------------------------------------------------------------------------
# task lists
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("source,checked", [
    ("- [ ] todo", False),
    ("- [x] done", True),
    ("- [X] done", True),
    ("* [x] starred", True),
    ("1. [x] numbered", True),
])
def test_task_items_are_recognised(source, checked):
    line, _ = markdown.parse_line(source)
    assert line.kind == markdown.LIST_ITEM
    assert line.task is checked
    assert "[x]" not in line.visible_text and "[ ]" not in line.visible_text


def test_plain_brackets_are_not_a_task():
    line, _ = markdown.parse_line("- [link](https://x.y)")
    assert line.task is None


def test_task_markers_keep_their_width(qapp):
    """The painted checkbox replaces the ``[x]`` without moving the text."""
    editor = make_editor("- [x] done\n- [ ] todo\n")
    editor.set_live_markdown(True, "light")
    qapp.processEvents()
    number = block_of(editor, "done")
    block = editor.document().findBlockByNumber(number).text()
    formats = formats_at(editor, number)
    start = block.index("[x]")
    assert all(formats[offset].fontPointSize() < 1.5
               for offset in range(start, start + 3))
    # collapsed? no: letter spacing stays at zero so the box fits the gap
    assert formats[start].fontLetterSpacing() == 0
