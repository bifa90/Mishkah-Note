# Contributing to Notepad-Linux

Thanks for taking the time to help. This project aims to stay small, readable
and dependable: a text editor that opens in a blink, handles a 200 MB log file
without freezing, and gets Arabic right.

## Getting set up

```bash
git clone https://github.com/bifa90/Notepad-Linux.git
cd Notepad-Linux
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
python -m mufakkira          # run the app
pytest                       # run the suite
```

On a headless machine:

```bash
QT_QPA_PLATFORM=offscreen pytest
```

## Ground rules

1. **`core/` and `models/` must stay Qt-free.** They are the testable heart of
   the app; importing PySide6 there breaks the fast unit tests and the CLI.
2. **No global layout direction.** Never call
   `QApplication.setLayoutDirection()`. Direction is per document (see
   `EditorView.apply_direction`) or per window, derived from the UI language.
3. **Long work goes to a worker thread.** File I/O happens in
   `services/file_service.py`; the UI thread only reacts to signals.
4. **Every behavioural change comes with a test**, including a regression test
   for the bug you just fixed.
5. **Translations ship with the change.** `core/i18n_data.py` must contain the
   new key in all ten languages; `tests/test_widgets.py` enforces this.

## Coding style

* Python ≥ 3.9, `from __future__ import annotations` in every module.
* Type hints on public functions; short docstrings that explain *why*.
* Line length 96, linted by ruff (`ruff check src tests`).
* Qt naming is kept for overrides (`resizeEvent`, `keyPressEvent`) with
  `# noqa: N802`.

## Adding a language

1. Append a `Language(...)` entry to `_LANGUAGES` in `core/languages.py` —
   include the native name, the script, an RTL flag and a font stack whose first
   entries exist on the target distros.
2. Add the code to every table in `core/i18n_data.py`.
3. Extend the table in `README.md` and `docs/FONTS.md`.
4. Run `pytest`; the completeness test will point at anything missing.

## Adding a UI string

Use `tr("section.key")` in the widget and add the key to `core/i18n_data.py`.
Fallback order is the active language, then English.

## Commit messages

```
area: short imperative summary

Why the change was needed, and anything a reviewer should watch for.
```

`area` is one of `core`, `views`, `widgets`, `services`, `packaging`, `docs`,
`tests`.

## Reporting bugs

Please include the distribution, Qt/PySide6 version, the file size and encoding
if the problem involves a specific document, and whether it reproduces with
`notepad --safe-mode` (which skips session restore and starts with defaults).
