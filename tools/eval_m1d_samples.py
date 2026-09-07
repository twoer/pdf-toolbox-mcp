#!/usr/bin/env python3
"""Run the reproducible synthetic M-1d sample benchmark.

The suite measures OCR write-back success, marker recall, page count, and
elapsed time. Marker matching reports both exact hits and a conservative
normalized hit (whitespace and punctuation removed) to distinguish OCR
formatting drift from a missing recognition.

Example:
  TESSDATA_PREFIX=$PWD/.tessdata uv run python tools/eval_m1d_samples.py
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

from pdf_toolbox.engine import ocr_pdf

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "output" / "pdf"
DEFAULT_OUTPUT = ROOT / "tmp" / "pdfs" / "m1d-eval"
SAMPLE_MANIFEST = Path(__file__).with_name("m1d_samples.json")


def _normalized(value: str) -> str:
    """Remove whitespace and punctuation while preserving letters and digits."""
    return re.sub(r"[^\w\u3400-\u9fff]", "", value, flags=re.UNICODE).casefold()


def _page_count(path: Path) -> int | None:
    try:
        output = subprocess.run(
            ["pdfinfo", str(path)], capture_output=True, text=True, check=True, timeout=30
        ).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    for line in output.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    return None


def _load_manifest(path: Path = SAMPLE_MANIFEST) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def evaluate(input_dir: Path, output_dir: Path, manifest: list[dict]) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for sample in manifest:
        source = input_dir / sample["file"]
        target = output_dir / f"{source.stem}_ocr.pdf"
        started = time.perf_counter()
        row = {
            "file": sample["file"],
            "kind": sample["kind"],
            "degradation": sample["degradation"],
            "pages": _page_count(source) if source.exists() else None,
        }
        try:
            result = ocr_pdf(
                source,
                lang="chi_sim+eng",
                deskew=sample["deskew"],
                output=target,
                overwrite=True,
            )
            text = subprocess.run(
                ["pdftotext", str(target), "-"],
                capture_output=True,
                text=True,
                check=True,
                timeout=180,
            ).stdout
            exact = [marker for marker in sample["markers"] if marker in text]
            normalized_text = _normalized(text)
            normalized = [
                marker for marker in sample["markers"] if _normalized(marker) in normalized_text
            ]
            row.update(
                {
                    "ok": True,
                    "seconds": round(time.perf_counter() - started, 2),
                    "exact_markers": exact,
                    "normalized_markers": normalized,
                    "marker_count": f"{len(exact)}/{len(sample['markers'])}",
                    "normalized_marker_count": f"{len(normalized)}/{len(sample['markers'])}",
                    "lang": result.get("lang"),
                    "lang_fallback": result.get("lang_fallback", False),
                }
            )
        except Exception as exc:
            row.update(
                {
                    "ok": False,
                    "seconds": round(time.perf_counter() - started, 2),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        rows.append(row)

    successful = [row for row in rows if row["ok"]]
    return {
        "suite": "synthetic-m1d",
        "files": len(rows),
        "succeeded": len(successful),
        "exact_marker_hits": sum(
            len(row.get("exact_markers", [])) for row in successful
        ),
        "normalized_marker_hits": sum(
            len(row.get("normalized_markers", [])) for row in successful
        ),
        "marker_targets": sum(len(sample["markers"]) for sample in manifest),
        "total_seconds": round(sum(row["seconds"] for row in rows), 2),
        "results": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    report = evaluate(args.input_dir, args.output_dir, _load_manifest())
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
