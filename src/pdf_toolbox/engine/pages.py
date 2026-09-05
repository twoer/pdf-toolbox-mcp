"""split / merge / rotate：页面手术（qpdf，L0——不依赖 poppler）。

页数读取用 pikepdf（Python 依赖），保证 L0 纯净：只装 qpdf 也能用全套。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .errors import EncryptedPdfError
from .probe import require
from .sandbox import assert_readable, check_write, ensure_pdf, parse_pages


def _qpdf(args: list[str]) -> None:
    proc = subprocess.run(
        ["qpdf", *args], capture_output=True, text=True, timeout=300
    )
    if proc.returncode != 0:
        raise RuntimeError(f"qpdf 失败: {(proc.stderr or proc.stdout).strip()[:300]}")


def _page_count(pdf: Path) -> int:
    import pikepdf

    try:
        with pikepdf.open(pdf) as doc:
            return len(doc.pages)
    except pikepdf.PasswordError:
        raise EncryptedPdfError(str(pdf)) from None


def _prep_output(out: Path, overwrite: bool) -> Path:
    out = check_write(out)
    if out.exists() and not overwrite:
        raise FileExistsError(f"输出已存在（overwrite=True 才覆盖）: {out}")
    return out


def split_pdf(
    path: str | Path,
    ranges: str | None = None,
    every_n: int | None = None,
    out_dir: str | Path | None = None,
    overwrite: bool = False,
) -> dict:
    """拆分：ranges='1-3,5' 按区间出文件；every_n=N 每 N 页一段。二者二选一。"""
    pdf = assert_readable(ensure_pdf(Path(path)))
    require("qpdf")
    if bool(ranges) == bool(every_n):
        raise ValueError("ranges 与 every_n 必须二选一")

    total = _page_count(pdf)
    if every_n:
        n = int(every_n)
        if n < 1:
            raise ValueError("every_n 至少为 1")
        spec = ",".join(
            f"{a}-{min(a + n - 1, total)}" for a in range(1, total + 1, n)
        )
    else:
        spec = ranges  # type: ignore[assignment]

    target_dir = Path(out_dir).expanduser().resolve() if out_dir else pdf.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    outputs: list[dict] = []
    for a, b in parse_pages(spec, max_pages=total):
        name = f"{pdf.stem}_p{a}.pdf" if a == b else f"{pdf.stem}_p{a}-{b}.pdf"
        out = _prep_output(target_dir / name, overwrite)
        _qpdf([str(pdf), "--pages", ".", f"{a}-{b}", "--", str(out)])
        outputs.append(
            {"file": str(out), "pages": f"{a}-{b}", "page_count": b - a + 1}
        )

    return {"input": str(pdf), "parts": outputs, "count": len(outputs)}


def merge_pdfs(
    paths: list[str | Path],
    output: str | Path,
    overwrite: bool = False,
) -> dict:
    """合并多个 PDF（按传入顺序）。书签保留自首个文件（qpdf 默认行为）。"""
    if not paths:
        raise ValueError("paths 为空")
    docs = [assert_readable(ensure_pdf(Path(p))) for p in paths]
    require("qpdf")
    out = _prep_output(Path(output), overwrite)
    _qpdf(["--empty", "--pages", *[str(d) for d in docs], "--", str(out)])
    return {
        "inputs": [str(d) for d in docs],
        "output": str(out),
        "page_count": _page_count(out),
    }


def rotate_pages(
    path: str | Path,
    angle: int,
    pages: str | None = None,
    output: str | Path | None = None,
    overwrite: bool = False,
) -> dict:
    """旋转页面 90/180/270 度。pages 缺省旋转全部页。"""
    if angle not in (90, 180, 270):
        raise ValueError("angle 只能是 90/180/270")
    pdf = assert_readable(ensure_pdf(Path(path)))
    require("qpdf")
    total = _page_count(pdf)
    spec = pages or f"1-{total}"
    ranges = parse_pages(spec, max_pages=total)
    page_spec = ",".join(f"{a}-{b}" if a != b else str(a) for a, b in ranges)

    out = Path(output) if output else pdf.with_name(f"{pdf.stem}_rot{angle}.pdf")
    out = _prep_output(out, overwrite)
    _qpdf([str(pdf), f"--rotate=+{angle}:{page_spec}", "--", str(out)])
    return {
        "input": str(pdf),
        "output": str(out),
        "angle": angle,
        "pages": page_spec,
    }


def check_repair(
    path: str | Path,
    repair: bool = False,
    output: str | Path | None = None,
    overwrite: bool = False,
) -> dict:
    """结构体检（qpdf --check）：语法/流编码错误与警告清单；repair=True 尝试重建修复。"""
    pdf = ensure_pdf(Path(path))
    require("qpdf")

    proc = subprocess.run(
        ["qpdf", "--check", str(pdf)], capture_output=True, text=True, timeout=120
    )
    blob = (proc.stdout + "\n" + proc.stderr)
    warnings = [ln.strip() for ln in blob.splitlines() if ln.strip().startswith("WARNING")]
    errors = [ln.strip() for ln in blob.splitlines() if ln.strip().startswith("ERROR")]
    status = "errors" if errors or proc.returncode not in (0, 3) else ("warnings" if warnings else "ok")
    # qpdf 退出码：0 正常；3 = 有 warning

    result: dict = {
        "path": str(pdf),
        "status": status,
        "warnings": warnings,
        "errors": errors,
        "recommendation": (
            "repair=True 尝试重建" if status != "ok" else None
        ),
    }

    if repair:
        if status == "ok":
            raise ValueError("文件健康，无需修复")
        out = Path(output) if output else pdf.with_name(f"{pdf.stem}_repaired.pdf")
        out = _prep_output(out, overwrite)
        # 修复读入：不同 qpdf 版本对"警告级恢复"的退出码不一致，
        # 以产物有效性为准（能被 pikepdf 打开即恢复成功），退出信息作为警告保留
        proc = subprocess.run(
            ["qpdf", str(pdf), "--", str(out)], capture_output=True, text=True, timeout=300
        )
        if not out.exists():
            raise RuntimeError(f"修复失败（无产物）: {(proc.stderr or proc.stdout).strip()[:300]}")
        try:
            result["repair_page_count"] = _page_count(out)
        except Exception as exc:
            raise RuntimeError(
                f"修复失败（产物不可读）: {(proc.stderr or proc.stdout).strip()[:200]} / {exc}"
            ) from exc
        result["repaired_output"] = str(out)
        result["repair_warnings"] = [
            ln.strip()
            for ln in (proc.stdout + "\n" + proc.stderr).splitlines()
            if ln.strip().startswith("WARNING")
        ][:10]
    return result


def linearize(
    path: str | Path,
    output: str | Path | None = None,
    overwrite: bool = False,
) -> dict:
    """Web 优化（qpdf --linearize）：首屏渐进加载，适合在线浏览的发布版。"""
    pdf = assert_readable(ensure_pdf(Path(path)))
    require("qpdf")
    out = Path(output) if output else pdf.with_name(f"{pdf.stem}_fast.pdf")
    out = _prep_output(out, overwrite)
    _qpdf(["--linearize", str(pdf), "--", str(out)])
    proc = subprocess.run(
        ["qpdf", "--check", str(out)], capture_output=True, text=True, timeout=120
    )
    return {
        "input": str(pdf),
        "output": str(out),
        "linearized": "linearized" in (proc.stdout + proc.stderr).lower(),
    }
