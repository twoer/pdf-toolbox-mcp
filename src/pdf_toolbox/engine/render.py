"""render_pages：页面渲染成 PNG（pdftoppm，L1）——喂给宿主视觉模型的兜底通道。"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .errors import EncryptedPdfError
from .meta import pdf_info
from .probe import require
from .sandbox import ensure_pdf, flatten_pages, group_consecutive, parse_pages

# pdftoppm 输出文件名形如 prefix-3.png / prefix-03.png，数字即绝对页号
_PAGE_NUM_RE = re.compile(r"-(\d+)\.png$")


def render_pages(
    path: str | Path,
    pages: str = "1",
    dpi: int = 150,
    out_dir: str | Path | None = None,
) -> dict:
    """渲染指定页为 PNG，返回文件路径与页号（MCP 层按需读成 base64 图像块）。

    dpi 钳制在 72–300；pages 支持多区间（重叠去重后按连续区间分组调用）。
    """
    pdf = ensure_pdf(Path(path))
    require("pdftoppm")
    dpi = max(72, min(int(dpi), 300))
    target_dir = Path(out_dir).expanduser().resolve() if out_dir else pdf.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    info = pdf_info(pdf)
    if info.get("encrypted"):
        raise EncryptedPdfError(str(pdf), hint="渲染前需先 unlock_pdf 解锁")

    unique = flatten_pages(parse_pages(pages, max_pages=info["pages"]))
    outputs: list[dict] = []
    for a, b in group_consecutive(unique):
        span = f"-{b}" if b != a else ""
        prefix = target_dir / f"{pdf.stem}_p{a}{span}"
        proc = subprocess.run(
            [
                "pdftoppm", "-png", "-r", str(dpi),
                "-f", str(a), "-l", str(b),
                str(pdf), str(prefix),
            ],
            capture_output=True, text=True, timeout=180,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"pdftoppm 失败: {proc.stderr.strip()[:300]}")
        for png in sorted(target_dir.glob(f"{prefix.name}-*.png")):
            m = _PAGE_NUM_RE.search(png.name)
            page_no = int(m.group(1)) if m else None
            outputs.append(
                {"file": str(png), "page": page_no, "size_bytes": png.stat().st_size}
            )

    outputs.sort(key=lambda x: (x["page"] is None, x["page"]))
    return {"path": str(pdf), "dpi": dpi, "images": outputs, "count": len(outputs)}
