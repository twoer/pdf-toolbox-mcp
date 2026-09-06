#!/usr/bin/env python3
"""本地 onboarding 检查：只读，不修改文件。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main(argv: list[str] | None = None) -> int:
    from pdf_toolbox.onboarding import format_report, parse_args, report_checks

    args = parse_args(sys.argv[1:] if argv is None else argv)
    report = report_checks(ROOT)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0 if report["ok"] else 1
    for line in format_report(report, success_mark="OK  ", failure_mark="FAIL"):
        print(line)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
