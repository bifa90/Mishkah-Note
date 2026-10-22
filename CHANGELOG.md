# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] — 2026-10-22

First public release of the rewrite, numbered 1.0.1. The editor was rebuilt from
a single generated script into a layered, tested application, and this release
adds the writing aids and tab features that turn it into a working editor.

### Added

#### The rewrite

* **Windows 11 visual language** — rounded tab strip with a modified-document
  dot, flat menu bar, generous padding, light and dark themes that follow the
  system colour scheme, and a compact status bar (`Ln, Col` · zoom · encoding ·
  line endings · text direction).
* **Ten most-spoken languages** with a script-appropriate font stack each, and
  a fully translated interface (140 strings × 10 languages) that switches
  without a restart.
* **Bundled Arabic typeface** (IBM Plex Sans Arabic Light, SIL OFL 1.1) so Arabic
  renders correctly on distributions with no Arabic fonts installed.
* **Large-file pipeline**: encoding sniffing on the first 64 KiB, chunked decode
  in 1 MiB blocks with progress and cancellation, read-only preview mode above
  8 MiB, an explicit confirmation above 512 MiB, and atomic saves through a
  temporary file plus `os.replace`.
* **Settings dialog** (`Ctrl+,`) covering language, theme, typeface, size, tab
  width, word wrap, gutter, default text direction, large-file thresholds and
  session restore.
* **Progress dialog** with a cancel signal wired to the I/O workers.
* **Direction control in three places**: the Ctrl+Shift chord, the Format menu
  (`Ctrl+Shift+A/R/L`), and a clickable status-bar chip.
* **Open-source project scaffold**: `pyproject.toml`, pytest suite,
  `CONTRIBUTING.md`, `docs/SWOT.md`, and packaging for Debian, RPM, Arch,
  AppImage and Flatpak.
* **Application icon pipeline**: `tools/make_icon.py` renders every size from
  one vector master (16–512 px, `.ico`, and an SVG master). The koi mark
  described below is what that master now holds.

#### Writing aids, tabs and branding

* **Automatic completion while typing.**
  * Brackets and quotes close themselves (`(`, `[`, `{`, `"`, `'`, `` ` ``,
    `«`, `‹`, `“`, `‘`), the caret lands inside the pair, and typing the
    closing character steps over it instead of duplicating it.
  * Typing over a selection wraps it in the pair.
  * Backspace between an empty pair removes both halves.
  * Quote pairing never fires inside a word, so `don't` and `it's` stay intact.
* **Smart indentation.** Enter keeps the current indent, adds one level after
  a block opener (`(`, `[`, `{`, `:`), dedents when a closing bracket is
  typed, and follows the file's own style (tabs, two or four spaces).
  `Tab`/`Shift+Tab` indent and outdent whole selections.
* **Word completion** (`Ctrl+Space`): suggests words already present in the
  document, ranked by frequency and recency, with Arabic support.
* **Syntax highlighting, off by default.** Fourteen languages (Python,
  JavaScript, TypeScript, JSON, HTML, CSS, C, C++, Rust, Go, Java, shell,
  SQL, YAML, Markdown) detected from the file name; `Ctrl+Shift+H` toggles it,
  and View ▸ Highlight language overrides the guess per tab. Light and dark
  palettes follow the theme.
* **Coloured and pinned tabs.** A Tab menu and a tab context menu offer six
  sticky-note colours, and a pin keeps the active tab's window above every
  other application (`Ctrl+T`, or `Ctrl+P` to pin the tab itself).
* **New logo** — the koi illustration is now the application icon, rendered
  from the supplied vector (`resources/branding/logo.svg`) at every size, with
  a tighter framing for 16–32 px so it stays legible in a taskbar.

### Changed

* The About box shows the vector logo instead of the previous generated mark.
* Settings ▸ Typing groups the three writing aids with a note explaining that
  highlighting is opt-in.
* Note colours have a dark variant: the tab keeps its hue but drops to a deep
  shade in the dark theme, where labels are painted in the theme's light text
  colour and a pastel fill would be unreadable.
* Untitled tabs and window titles now follow the interface language
  («بدون عنوان» in Arabic) instead of always saying "Untitled".
* Word wrap and line-number choices are remembered between sessions.
* Package renamed to `notepad-linux`, console entry points `notepad` and
  `mufakkira`.
* Project restructured into `core` / `models` / `services` / `views` / `widgets`
  / `controllers`; `core` and `models` are Qt-free and covered by fast tests.
* Line numbers are **off** by default, matching Windows 11 Notepad.

### Fixed

* Packaging metadata: the RPM spec was ignored by the `*.spec` rule in
  `.gitignore`, so it never reached a release archive; it is written and
  tracked now.
* The status bar's size segment kept its old width and clipped the unit
  ("207" instead of "207 B") until the window was resized.
* Editing a file left the size segment showing the size it had when opened.
* `theme = system` always produced the light highlighting palette, so a dark
  desktop got dark-on-dark colours; the palette now follows the actual
  application palette.
* Closing a pinned tab left the window floating above other applications.
* The View and Tab menus did not reflect switching tabs (pin/colour state).
* **Text direction no longer defaults to RTL.** The application used to call
  `QApplication.setLayoutDirection(Qt.RightToLeft)`, flipping the whole UI and
  every document. Direction is now resolved per document, and the default mode
  is *automatic*, inferred from the first strong character of the buffer.
* **Ctrl+Shift direction switching actually works.** The old handler relied on
  `nativeScanCode()` alone, which is ambiguous (scan code 62 is Right Shift on
  X11/evdev but Right Control on macOS). The key identity now comes from
  `event.key()` and only the *side* from the scan code; the chord fires only
  when Ctrl+Shift are pressed and released without a third key, and a 1.5 s
  timeout stops stale state from flipping the document later.
* **`dominant_direction()` follows the Unicode bidi rule** — the first strong
  character of the first non-empty line decides, instead of an early
  "more than 24 Latin characters" heuristic that flipped genuine Arabic
  paragraphs with a long English tail.
* **Large-file previews no longer cut words in half** and report the real
  preview size instead of "the first 0 MiB".
* **Saving is atomic** — a crash or power loss can no longer leave a truncated
  file behind.
* **Window title no longer shows the developer's name**; it reads
  `file.txt - Notepad`, as on Windows 11.

### Removed

* The 1,672-line generator script and the pre-built 1.0.0 Debian package.
* All occurrences of the developer's name outside the About box.

## [1.0.0] — 2026-09-30

First public package: a single-window Arabic-first editor with tab support,
find/replace and a Debian package.
