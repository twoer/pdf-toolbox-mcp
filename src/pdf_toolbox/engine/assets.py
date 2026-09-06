"""extract_images / extract_attachments：素材抽取（pdfimages / pdfdetach，L1）。"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .probe import require
from .sandbox import assert_readable, check_write, ensure_pdf, flatten_pages, group_consecutive


def extract_images(
    path: str | Path,
    pages: str | None = None,
    list_only: bool = False,
    out_dir: str | Path | None = None,
) -> dict:
    """抽取内嵌图片。list_only=True 只返回清单（pdfimages -list）不落盘。"""
    pdf = assert_readable(ensure_pdf(Path(path)))
    require("pdfimages")

    target_dir = Path(out_dir).expanduser().resolve() if out_dir else pdf.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    ranges: list[tuple[int, int]] | None = None
    if pages:
        from .sandbox import parse_pages

        ranges = parse_pages(pages)
        unique = flatten_pages(ranges)
        ranges = group_consecutive(unique)

    if list_only:
        inventory: list[dict] = []
        if ranges is None:
            cmd = ["pdfimages", "-list", str(pdf)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if proc.returncode != 0:
                raise RuntimeError(f"pdfimages 失败: {proc.stderr.strip()[:300]}")
            for line in proc.stdout.splitlines():
                tokens = line.split()
                # 列：page num type width height color comp bpc enc interp object ID ...
                if len(tokens) >= 6 and tokens[0].isdigit() and tokens[1].isdigit():
                    inventory.append(
                        {
                            "page": int(tokens[0]),
                            "num": int(tokens[1]),
                            "type": tokens[2],
                            "width": int(tokens[4]) if tokens[4].isdigit() else None,
                            "height": int(tokens[5]) if tokens[5].isdigit() else None,
                        }
                    )
        else:
            for a, b in ranges:
                cmd = ["pdfimages", "-list", "-f", str(a), "-l", str(b), str(pdf)]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if proc.returncode != 0:
                    raise RuntimeError(f"pdfimages 失败: {proc.stderr.strip()[:300]}")
                for line in proc.stdout.splitlines():
                    tokens = line.split()
                    # 列：page num type width height color comp bpc enc interp object ID ...
                    if len(tokens) >= 6 and tokens[0].isdigit() and tokens[1].isdigit():
                        inventory.append(
                            {
                                "page": int(tokens[0]),
                                "num": int(tokens[1]),
                                "type": tokens[2],
                                "width": int(tokens[4]) if tokens[4].isdigit() else None,
                                "height": int(tokens[5]) if tokens[5].isdigit() else None,
                            }
                        )
        return {"path": str(pdf), "inventory": inventory, "count": len(inventory)}

    outputs: list[dict] = []
    if ranges is None:
        prefix = check_write(target_dir / f"{pdf.stem}_img")
        cmd = ["pdfimages", "-png", "-p", str(pdf), str(prefix)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            raise RuntimeError(f"pdfimages 失败: {proc.stderr.strip()[:300]}")

        for png in sorted(target_dir.glob(f"{prefix.name}-*.png")):
            m = re.search(r"-(\d+)-(\d+)\.png$", png.name)
            outputs.append(
                {
                    "file": str(png),
                    "page": int(m.group(1)) if m else None,
                    "size_bytes": png.stat().st_size,
                }
            )
    else:
        for a, b in ranges:
            suffix = f"p{a}" if a == b else f"p{a}-{b}"
            prefix = check_write(target_dir / f"{pdf.stem}_img_{suffix}")
            cmd = ["pdfimages", "-png", "-p", "-f", str(a), "-l", str(b), str(pdf), str(prefix)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if proc.returncode != 0:
                raise RuntimeError(f"pdfimages 失败: {proc.stderr.strip()[:300]}")

            for png in sorted(target_dir.glob(f"{prefix.name}-*.png")):
                m = re.search(r"-(\d+)-(\d+)\.png$", png.name)
                outputs.append(
                    {
                        "file": str(png),
                        "page": int(m.group(1)) if m else None,
                        "size_bytes": png.stat().st_size,
                    }
                )
    outputs.sort(key=lambda x: (x["page"] is None, x["page"], x["file"]))
    return {"path": str(pdf), "images": outputs, "count": len(outputs)}


def extract_attachments(path: str | Path, out_dir: str | Path | None = None) -> dict:
    """抽取 PDF 内嵌附件（pdfdetach）。返回清单与落盘文件。"""
    pdf = assert_readable(ensure_pdf(Path(path)))
    require("pdfdetach")

    proc = subprocess.run(
        ["pdfdetach", "-list", str(pdf)], capture_output=True, text=True, timeout=60
    )
    if proc.returncode != 0:
        raise RuntimeError(f"pdfdetach 失败: {proc.stderr.strip()[:300]}")

    attachments: list[dict] = []
    for line in proc.stdout.splitlines():
        # 格式：首行 "N embedded files"，其后 "<index>: <filename>"
        m = re.match(r"^(\d+):\s+(.+)$", line.strip())
        if m:
            attachments.append(
                {"index": int(m.group(1)), "name": m.group(2).strip()}
            )

    saved: list[str] = []
    if attachments:
        target_dir = Path(out_dir).expanduser().resolve() if out_dir else pdf.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        check_write(target_dir / ".pdfdetach-write-check")
        (target_dir / ".pdfdetach-write-check").unlink(missing_ok=True)
        proc = subprocess.run(
            ["pdfdetach", "-saveall", "-o", str(target_dir), str(pdf)],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"pdfdetach 保存失败: {proc.stderr.strip()[:300]}")
        for att in attachments:
            f = target_dir / att["name"]
            if f.exists():
                saved.append(str(f))

    return {
        "path": str(pdf),
        "attachments": attachments,
        "count": len(attachments),
        "saved": saved,
    }
