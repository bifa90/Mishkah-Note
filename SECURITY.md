# Security policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 1.0.x (latest patch) | ✅ |
| < 1.0 | ❌ |

Only the newest published release receives fixes. Older 1.0.x builds are kept
on the releases page for reference, not for support; see the "always use the
latest release" note in the README.

## Reporting a vulnerability

Please **do not** open a public issue for a security problem. Send a private
report through GitHub's *Security ▸ Report a vulnerability* form on
<https://github.com/bifa90/Mishkah-Note>, including:

* the affected version (`mishkah --version`) and how it was installed
  (deb, rpm, Arch, AppImage, Flatpak, MSI, wheel);
* a minimal reproduction — the file that triggers it, or the exact steps;
* what you expected instead, and what you observed;
* whether the report may be published, and under which name.

**What to expect:** an acknowledgement within **7 days**, a first assessment
within **30 days**, and a coordinated disclosure once a fixed release is
available. If a report is out of scope you will still get a reply explaining
why.

## Scope and threat model

Mishkah Note is a local desktop editor. It has no network code, no telemetry,
no plugin system and no auto-update mechanism, so the interesting surface is
small:

* **Opening a file.** Content is decoded with `charset-normalizer` from a
  bounded sample, rejected when it looks binary, and opened read-only above the
  configured preview threshold. A crafted file can at worst produce a wrong
  encoding guess — never code execution. Files whose encoding cannot be
  determined prompt for an explicit choice instead of being decoded silently.
* **Saving a file.** Writes go to a temporary file in the same directory and
  are moved into place with `os.replace`, so an interrupted save cannot
  truncate the original. A pre-save check compares the on-disk modification
  time and size, so an editor running elsewhere cannot be silently overwritten.
* **Settings.** `~/.config/Mishkah/settings.json` is parsed as JSON against a
  typed allow-list; unknown keys, wrong types and out-of-range values are
  dropped and replaced by defaults, and a structurally corrupt file is backed
  up as `settings.json.bak` before defaults are used.
* **Bundled assets.** Fonts and icons are static files; the only bundled
  typeface is IBM Plex Sans Arabic (SIL OFL 1.1).

### Known limitations

* The Flatpak build currently requests `--filesystem=home` so that autosave,
  recent files and session restore keep working through the document portal.
  The reason and the plan to narrow it are documented in
  `docs/PACKAGING.md`; treat the sandbox permission as broad until that lands.
* Document content is never executed, but a document can still be confusing:
  bidirectional control characters are legal text. The editor can display them
  on request; it does not strip them from files.

Out of scope: vulnerabilities in Qt/PySide6 itself (report them upstream),
problems that require an already-compromised local account, and social
engineering of the maintainer.
