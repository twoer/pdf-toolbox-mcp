"""页范围解析、路径校验与写出沙箱（全部工具复用；subprocess 一律 list 参数）。"""

from __future__ import annotations

import os
from pathlib import Path


class PageRangeError(ValueError):
    pass


def parse_pages(spec: str, max_pages: int | None = None) -> list[tuple[int, int]]:
    """解析 '1-3,5,8-' 形式的页范围 → [(start, end), ...]（1-based，闭区间）。

    max_pages 给定时 '8-' 展开到末页，且所有页号做越界校验。
    """
    ranges: list[tuple[int, int]] = []
    for part in spec.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            a, _, b = part.partition("-")
            start = int(a) if a else 1
            if b:
                end = int(b)
            elif max_pages is not None:
                end = max_pages
            else:
                raise PageRangeError(f"开区间 '{part}' 需要 max_pages 才能展开")
        else:
            start = end = int(part)
        if start < 1:
            raise PageRangeError(f"页号从 1 开始：{start}")
        if end < start:
            raise PageRangeError(f"起始页大于结束页：{part}")
        if max_pages is not None and (start > max_pages or end > max_pages):
            raise PageRangeError(f"页号超出范围 1–{max_pages}：{part}")
        ranges.append((start, end))
    if not ranges:
        raise PageRangeError("空页范围")
    return ranges


def flatten_pages(ranges: list[tuple[int, int]]) -> list[int]:
    return sorted({p for a, b in ranges for p in range(a, b + 1)})


def group_consecutive(pages: list[int]) -> list[tuple[int, int]]:
    """[1,2,3,5] → [(1,3),(5,5)]：把去重排序后的页号合并成连续区间。"""
    if not pages:
        return []
    pages = sorted(set(pages))
    groups: list[tuple[int, int]] = []
    start = prev = pages[0]
    for p in pages[1:]:
        if p == prev + 1:
            prev = p
        else:
            groups.append((start, prev))
            start = prev = p
    groups.append((start, prev))
    return groups


# ---------------------------------------------------------------------------
# 路径与写出沙箱（PLAN §6）
# ---------------------------------------------------------------------------

# 明确禁止写出的系统目录（读不限制）。macOS 的 /var/tmp 等临时目录不在禁写之列。
_WRITE_DENY = [
    "/System",
    "/usr",
    "/bin",
    "/sbin",
    "/etc",
    "/private/etc",
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
]


def _resolve(path: str | Path) -> Path:
    p = Path(path).expanduser()
    return (p if p.is_absolute() else Path.cwd() / p).resolve()


def workspace_root() -> Path | None:
    """PDF_TOOLBOX_WORKSPACE 设定时，所有写出必须位于其内；未设定则仅禁写系统目录。"""
    ws = os.environ.get("PDF_TOOLBOX_WORKSPACE")
    return _resolve(ws) if ws else None


def check_write(path: str | Path) -> Path:
    p = _resolve(path)
    root = workspace_root()
    if root is not None and not p.is_relative_to(root):
        raise PermissionError(f"写出沙箱：{p} 不在 workspace {root} 内")
    for denied in _WRITE_DENY:
        if p.is_relative_to(Path(denied)) and str(p) != "/":
            raise PermissionError(f"拒绝写入系统目录: {p}")
    return p


def default_output(path: Path, suffix: str, out_dir: Path | None = None) -> Path:
    """默认输出路径：同目录 <stem><suffix>.pdf；已存在则报错（覆盖需显式确认）。"""
    target = (out_dir or path.parent) / f"{path.stem}{suffix}.pdf"
    return target


def ensure_pdf(path: str | Path) -> Path:
    p = _resolve(path)
    if not p.is_file():
        raise FileNotFoundError(f"文件不存在: {p}")
    if p.suffix.lower() != ".pdf":
        raise ValueError(f"不是 PDF 文件: {p}")
    return p


def assert_readable(pdf: Path) -> Path:
    """用 pikepdf 快速探测可读性——加密文件转 EncryptedPdfError（引导 unlock_pdf）。"""
    import pikepdf

    from .errors import EncryptedPdfError

    try:
        with pikepdf.open(pdf):
            pass
    except pikepdf.PasswordError:
        raise EncryptedPdfError(str(pdf)) from None
    return pdf
