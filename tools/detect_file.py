#!/usr/bin/env python3
"""Say what the application will *think* a file is, before you open it.

G3b item 14 was reported as "it opens normally, but only after I change the
encoding by hand" — and there is no way to act on that sentence: the file is not
here, and "wrong" needs a number.  This prints what the detector decides today,
with the evidence it decided from, so a report can carry the file's identity
without the file itself.

    python tools/detect_file.py ~/g3b/legacy.txt
    python tools/detect_file.py ~/g3b/legacy.txt --json > report.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

SAMPLE = 64 * 1024


def inspect(path: Path) -> dict:
    from mishkah.core.encoding import detect_format, looks_binary

    data = path.read_bytes()[:SAMPLE]
    fmt = detect_format(data)
    high = Counter(byte for byte in data if byte >= 0x80)
    return {
        "path": str(path),
        "size": path.stat().st_size,
        "sampled": len(data),
        "binary": looks_binary(data),
        "encoding": fmt.encoding,
        "confident": fmt.confident,
        "has_bom": fmt.has_bom,
        "line_ending": fmt.line_ending.replace("\r", "CR").replace("\n", "LF"),
        "high_bytes": len(high),
        "top_high_bytes": [f"0x{b:02X}×{n}" for b, n in high.most_common(6)],
        "head_hex": data[:32].hex(" "),
        "decodes_as_detected": None,
    }


def main(argv: list | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    paths = [a for a in args if not a.startswith("--")]
    if not paths:
        print(f"usage: {Path(sys.argv[0]).name} FILE [--json]", file=sys.stderr)
        return 2

    reports = []
    for raw in paths:
        path = Path(raw).expanduser()
        if not path.is_file():
            print(f"not a file: {path}", file=sys.stderr)
            continue
        report = inspect(path)
        try:
            path.read_bytes()[:SAMPLE].decode(report["encoding"])
            report["decodes_as_detected"] = True
        except (UnicodeDecodeError, LookupError):
            report["decodes_as_detected"] = False
        reports.append(report)

    if "--json" in args:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
        return 0

    for report in reports:
        print(f"{report['path']}  ({report['size']:,} bytes)")
        print(f"  detected     : {report['encoding']} "
              f"({'confident' if report['confident'] else 'GUESS — check this one'})")
        print(f"  BOM          : {'yes' if report['has_bom'] else 'no'}")
        print(f"  line endings : {report['line_ending']}")
        print(f"  binary       : {'yes' if report['binary'] else 'no'}")
        print(f"  high bytes   : {report['high_bytes']} "
              f"({', '.join(report['top_high_bytes']) or 'none'})")
        print(f"  head (hex)   : {report['head_hex']}")
        print(f"  decodes ok   : {report['decodes_as_detected']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
