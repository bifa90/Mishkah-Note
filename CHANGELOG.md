# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] — 2026-10-21

The rewrite. The editor was rebuilt from a single generated script into a
layered, tested, open-source application.

### Added

* **Windows 11 visual language** — rounded tab strip with a modified-document
  dot, flat menu bar, generous padding, light and dark themes that follow the
  system colour scheme, and a compact status bar (`Ln, Col` · zoom · encoding ·
  line endings · text direction).
* **Ten most-spoken languages** with a script-appropriate font stack each, and
  a fully translated interface (118 strings × 10 languages) that switches
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
* **New application icon**: a geometric black-and-white fish on a light sky-blue
  rounded square, rendered deterministically by `tools/make_icon.py` at every
  required size (16–512 px, `.ico`, and an SVG master).

### Fixed

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

### Changed

* Package renamed to `notepad-linux`, version bumped to 2.0.0, console entry
  points `notepad` and `mufakkira`.
* Project restructured into `core` / `models` / `services` / `views` / `widgets`
  / `controllers`; `core` and `models` are Qt-free and covered by fast tests.
* Line numbers are **off** by default, matching Windows 11 Notepad.

### Removed

* The 1,672-line generator script and the pre-built 1.0.0 Debian package.
* All occurrences of the developer's name outside the About box.

## [1.0.0] — 2026-09-30

First public package: a single-window Arabic-first editor with tab support,
find/replace and a Debian package.
