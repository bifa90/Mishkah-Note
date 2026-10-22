#!/usr/bin/env python3
"""Expose JUnit failures as GitHub annotations without hiding pytest's exit."""
from __future__ import annotations

import argparse
from pathlib import Path
from xml.etree import ElementTree as ET


def escape(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if not args.report.exists():
        print("JUnit report not produced; inspect the pytest step log.")
        return 0
    for case in ET.parse(args.report).iter("testcase"):
        for child in case:
            if child.tag not in {"error", "failure"}:
                continue
            title = f"{case.get('classname', '')}.{case.get('name', '')}"
            detail = (child.text or child.get("message", ""))[-6000:]
            print(f"::error::{escape(title + ': ' + detail)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
