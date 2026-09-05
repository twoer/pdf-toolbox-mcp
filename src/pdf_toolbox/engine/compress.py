"""compress_pdf：ghostscript 压缩（L3 可选依赖），支持压到目标大小。"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .probe import find_binary, require
from .sandbox import assert_readable, check_write, ensure_pdf

# 从高质量到低质量依次尝试（gs PDFSETTINGS 档位）
_QUALITY_LADDER = ["prepress", "printer", "ebook", "screen"]


def _gs(input: Path, output: Path, quality: str) -> None:
    gs_bin = find_binary("gs")  # Windows 上是 gswin64c
    assert gs_bin is not None  # require() 已在上游把关
    proc = subprocess.run(
        [
            gs_bin,
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.5",
            f"-dPDFSETTINGS=/{quality}",
            "-dNOPAUSE", "-dBATCH", "-dQUIET",
            f"-sOutputFile={output}",  # gs 需要等号形式，空格分隔在其后接输入文件时不可靠
            str(input),
        ],
        capture_output=True, text=True, timeout=600,
    )
    if proc.returncode != 0 or not output.exists():
        raise RuntimeError(f"ghostscript 失败: {(proc.stderr or proc.stdout).strip()[:300]}")


def compress_pdf(
    path: str | Path,
    target_mb: float | None = None,
    quality: str = "ebook",
    output: str | Path | None = None,
    overwrite: bool = False,
) -> dict:
    """压缩 PDF。给定 target_mb 时沿档位阶梯（ebook→screen）下探直到达标（尽力而为）。

    注意：gs 压缩有损（图像重采样/重编码）；文本向量通常不受影响。
    """
    pdf = assert_readable(ensure_pdf(Path(path)))
    require("gs")

    out = Path(output) if output else pdf.with_name(f"{pdf.stem}_compressed.pdf")
    out = check_write(out)
    if out.exists() and not overwrite:
        raise FileExistsError(f"输出已存在（overwrite=True 才覆盖）: {out}")

    size_before = pdf.stat().st_size
    target_bytes = int(target_mb * 1024 * 1024) if target_mb else None

    if target_bytes:
        ladder = [q for q in _QUALITY_LADDER if q != "prepress"]  # 目标压缩不试印刷级
    else:
        if quality not in _QUALITY_LADDER:
            raise ValueError(f"quality 只能是 {'/'.join(_QUALITY_LADDER)}")
        ladder = [quality]

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        attempts: list[dict] = []
        best: tuple[int, Path, str] | None = None
        for q in ladder:
            candidate = Path(tmp) / f"try_{q}.pdf"
            _gs(pdf, candidate, q)
            size = candidate.stat().st_size
            attempts.append({"quality": q, "size_bytes": size})
            if best is None or size < best[0]:
                best = (size, candidate, q)
            if target_bytes and size <= target_bytes:
                break
        assert best is not None
        import shutil

        shutil.copyfile(best[1], out)
        quality_used = best[2]

    size_after = out.stat().st_size
    target_met = (size_after <= target_bytes) if target_bytes else None
    return {
        "input": str(pdf),
        "output": str(out),
        "size_before": size_before,
        "size_after": size_after,
        "ratio": round(size_after / max(1, size_before), 3),
        "quality_used": quality_used,
        "target_mb": target_mb,
        "target_met": target_met,
        "note": "ghostscript 有损压缩（图像重采样）；矢量文本通常无损",
    }
