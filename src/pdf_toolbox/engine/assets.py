"""extract_images / extract_attachments：素材抽取（pdfimages / pdfdetach，L1）。"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

from .pages import _page_count
from .probe import require
from .sandbox import assert_readable, check_write, ensure_pdf, flatten_pages, group_consecutive


def extract_images(
    path: str | Path,
    pages: str | None = None,
    list_only: bool = False,
    out_dir: str | Path | None = None,
    overwrite: bool = False,
) -> dict:
    """抽取内嵌图片。list_only=True 只返回清单（pdfimages -list）不落盘。"""
    pdf = assert_readable(ensure_pdf(Path(path)))
    require("pdfimages")

    ranges: list[tuple[int, int]] | None = None
    if pages:
        from .sandbox import parse_pages

        ranges = parse_pages(pages, max_pages=_page_count(pdf))
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
    target_dir = Path(out_dir).expanduser().resolve() if out_dir else pdf.parent
    check_write(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    prefixes = (
        [target_dir / f"{pdf.stem}_img"]
        if ranges is None
        else [
            target_dir / f"{pdf.stem}_img_{'p' + str(a) if a == b else f'p{a}-{b}'}"
            for a, b in ranges
        ]
    )
    if not overwrite:
        for prefix in prefixes:
            existing = sorted(target_dir.glob(f"{prefix.name}-*"))
            if existing:
                raise FileExistsError(
                    f"输出已存在（overwrite=True 才覆盖）: {existing[0]}"
                )
    if ranges is None:
        with tempfile.TemporaryDirectory(dir=target_dir, prefix=".pdf-toolbox-images-") as tmp:
            prefix = Path(tmp) / f"{pdf.stem}_img"
            cmd = ["pdfimages", "-png", "-p", str(pdf), str(prefix)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if proc.returncode != 0:
                raise RuntimeError(f"pdfimages 失败: {proc.stderr.strip()[:300]}")

            for png in sorted(Path(tmp).glob(f"{prefix.name}-*.png")):
                destination = target_dir / png.name
                os.replace(png, destination)
                m = re.search(r"-(\d+)-(\d+)\.png$", destination.name)
                outputs.append(
                    {
                        "file": str(destination),
                        "page": int(m.group(1)) if m else None,
                        "size_bytes": destination.stat().st_size,
                    }
                )
    else:
        with tempfile.TemporaryDirectory(dir=target_dir, prefix=".pdf-toolbox-images-") as tmp:
            tmpdir = Path(tmp)
            for a, b in ranges:
                suffix = f"p{a}" if a == b else f"p{a}-{b}"
                prefix = tmpdir / f"{pdf.stem}_img_{suffix}"
                cmd = ["pdfimages", "-png", "-p", "-f", str(a), "-l", str(b), str(pdf), str(prefix)]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if proc.returncode != 0:
                    raise RuntimeError(f"pdfimages 失败: {proc.stderr.strip()[:300]}")

                for png in sorted(tmpdir.glob(f"{prefix.name}-*.png")):
                    destination = target_dir / png.name
                    os.replace(png, destination)
                    m = re.search(r"-(\d+)-(\d+)\.png$", destination.name)
                    outputs.append(
                        {
                            "file": str(destination),
                            "page": int(m.group(1)) if m else None,
                            "size_bytes": destination.stat().st_size,
                        }
                    )
    outputs.sort(key=lambda x: (x["page"] is None, x["page"], x["file"]))
    return {"path": str(pdf), "images": outputs, "count": len(outputs)}


def extract_attachments(
    path: str | Path,
    out_dir: str | Path | None = None,
    overwrite: bool = False,
) -> dict:
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

    # pdfdetach -saveall 落盘是平铺目录：名字带路径会写出目录之外，
    # 字面同名会静默互相覆盖——两种都无法完整抽取，先拒绝
    problems: list[str] = []
    seen: set[str] = set()
    for attachment in attachments:
        raw = attachment["name"]
        name = Path(raw).name
        if name != raw or "\\" in raw:
            problems.append(f"附件名含路径: {raw}")
        elif name in seen:
            problems.append(f"同名附件: {name}")
        else:
            seen.add(name)
    if problems:
        raise ValueError(f"无法完整抽取附件: {'; '.join(problems)}")

    saved: list[str] = []
    if attachments:
        target_dir = Path(out_dir).expanduser().resolve() if out_dir else pdf.parent
        check_write(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        if not overwrite:
            for attachment in attachments:
                target = target_dir / Path(attachment["name"]).name
                if target.exists():
                    raise FileExistsError(
                        f"输出已存在（overwrite=True 才覆盖）: {target}"
                    )
        # Probe writability without touching a user-chosen, fixed filename.
        with tempfile.NamedTemporaryFile(
            prefix=".pdfdetach-write-check-", dir=target_dir
        ):
            pass
        with tempfile.TemporaryDirectory(dir=target_dir, prefix=".pdf-toolbox-attachments-") as tmp:
            proc = subprocess.run(
                ["pdfdetach", "-saveall", "-o", tmp, str(pdf)],
                capture_output=True, text=True, timeout=120,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"pdfdetach 保存失败: {proc.stderr.strip()[:300]}")
            for attachment in attachments:
                source = Path(tmp) / Path(attachment["name"]).name
                if source.exists():
                    os.replace(source, target_dir / source.name)
        for att in attachments:
            f = target_dir / Path(att["name"]).name
            if f.exists():
                saved.append(str(f))

    return {
        "path": str(pdf),
        "attachments": attachments,
        "count": len(attachments),
        "saved": saved,
    }
