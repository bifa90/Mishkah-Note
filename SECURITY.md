# Security policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 2.0.x   | ✅ |
| 1.0.x   | ❌ (single-script release, superseded) |

## Reporting a vulnerability

Please **do not** open a public issue for a security problem. Send a private
report through GitHub's *Security ▸ Report a vulnerability* form on
<https://github.com/bifa90/Mishkah-Note>, including:

* the affected version and distribution,
* a minimal reproduction (the file that triggers it, or the exact steps),
* what you expected instead.

You will get an acknowledgement within a few days. Once a fix is ready the
advisory is published together with the release notes.

## Scope and threat model

Mishkah Note is a local desktop editor. It has no network code, no telemetry, no
plugins and no auto-update mechanism, so the interesting surface is small:

* **Opening a file.** Content is decoded with `charset-normalizer`, capped at
  512 MiB with an explicit confirmation, and previewed read-only above 8 MiB.
  A crafted file can at worst produce a wrong encoding guess, never code
  execution.
* **Saving a file.** Writes go to a temporary file in the same directory and
  are moved into place with `os.replace`, so an interrupted save cannot
  truncate the original.
* **Settings.** `~/.config/Mishkah/settings.json` is parsed as JSON with a
  whitelist of known keys; unknown keys are dropped.
* **Bundled assets.** Fonts and icons are static files; the only bundled
  typeface is IBM Plex Sans Arabic (SIL OFL 1.1).

Out of scope: vulnerabilities in Qt/PySide6 itself (report them upstream) and
problems that require an already-compromised local account.
