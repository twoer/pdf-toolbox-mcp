"""pdf_info：元数据与页数（pdfinfo，L1）。"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .pages import _page_count
from .probe import require
from .sandbox import assert_readable, ensure_pdf
from .text import extract_text


def pdf_info(path: str | Path) -> dict:
    """返回 pdfinfo 的键值 dict + 派生字段（searchable 预判留给 P2 的 is_searchable）。"""
    pdf = ensure_pdf(Path(path))
    require("pdfinfo")
    proc = subprocess.run(
        ["pdfinfo", str(pdf)], capture_output=True, text=True, timeout=60
    )
    if proc.returncode != 0:
        # 加密文件 pdfinfo 无密码会失败——但 info 是智能路由入口，必须能识别加密状态
        blob = (proc.stdout + proc.stderr).lower()
        if "password" in blob or "encrypted" in blob:
            import pikepdf

            try:
                with pikepdf.open(pdf):
                    pass
                raise RuntimeError(  # 能无密码打开却让 pdfinfo 失败，属未知情况
                    f"pdfinfo 失败但文件可打开: {proc.stderr.strip()[:200]}"
                )
            except pikepdf.PasswordError:
                return {
                    "path": str(pdf),
                    "pages": None,
                    "encrypted": True,
                    "file_size_bytes": pdf.stat().st_size,
                    "note": "文件已加密，需要密码才能读取（unlock_pdf 计划中）",
                }
        raise RuntimeError(f"pdfinfo 失败: {proc.stderr.strip()[:300]}")

    info: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            info[k.strip()] = v.strip()

    encrypted = "yes" in info.get("Encrypted", "no").lower()
    pages = int(info.get("Pages", "0") or 0)
    return {
        "path": str(pdf),
        "pages": pages,
        "encrypted": encrypted,
        "page_size": info.get("Page size"),
        "pdf_version": info.get("PDF version"),
        "title": info.get("Title"),
        "author": info.get("Author"),
        "producer": info.get("Producer"),
        "file_size_bytes": pdf.stat().st_size,
        "raw": info,
    }


def is_searchable(path: str | Path, sample_pages: int = 5) -> dict:
    """智能路由入口：抽样页文本密度判断是否可直接提取。

    平均字符/页 ≥ 50 判为可搜索；否则建议先 ocr_pdf 写回文本层。
    """
    pdf = assert_readable(ensure_pdf(Path(path)))
    require("pdftotext")

    total = _page_count(pdf)
    sampled = min(max(1, int(sample_pages)), total)
    result = extract_text(pdf, pages=f"1-{sampled}", per_page=True)
    chars_per_page = sum(len(v) for v in result["per_page"].values()) / max(1, sampled)
    searchable = chars_per_page >= 50
    return {
        "path": str(pdf),
        "pages": total,
        "sampled_pages": sampled,
        "chars_per_page": round(chars_per_page, 1),
        "searchable": searchable,
        "recommendation": "extract_text" if searchable else "ocr_pdf",
    }


def list_fonts(path: str | Path) -> dict:
    """字体体检（pdffonts）：未嵌入字体在别人的机器/打印店可能缺字。"""
    pdf = assert_readable(ensure_pdf(Path(path)))
    require("pdffonts")

    proc = subprocess.run(
        ["pdffonts", str(pdf)], capture_output=True, text=True, timeout=60
    )
    if proc.returncode != 0:
        raise RuntimeError(f"pdffonts 失败: {proc.stderr.strip()[:300]}")

    fonts: list[dict] = []
    for line in proc.stdout.splitlines():
        tokens = line.split()
        # 列：name type encoding emb sub uni object ID（name 可能含空格，从右侧取 7 列）
        if len(tokens) < 9 or tokens[1] in ("type", "[type]"):
            continue
        if set(line.strip()) <= {"-", " "}:
            continue
        *name_parts, ftype, enc, emb, sub, _uni, _obj, _fid = tokens
        fonts.append(
            {
                "name": " ".join(name_parts),
                "type": ftype,
                "encoding": enc,
                "embedded": emb.lower() == "yes",
                "subset": sub.lower() == "yes",
            }
        )

    non_embedded = [f for f in fonts if not f["embedded"]]
    return {
        "path": str(pdf),
        "fonts": fonts,
        "count": len(fonts),
        "non_embedded_count": len(non_embedded),
        "warning": (
            f"{len(non_embedded)} 个字体未嵌入，跨设备查看/打印可能缺字"
            if non_embedded
            else None
        ),
    }
