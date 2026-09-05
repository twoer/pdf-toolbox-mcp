"""batch_ocr：整批 OCR 写回（逐文件结果 / 失败重试 / 单文件超时）——M3 完成标准的落点。"""

from __future__ import annotations

from pathlib import Path

from .ocr import ocr_pdf


def _resolve_inputs(inputs) -> list[Path]:
    if isinstance(inputs, (str, Path)):
        inputs = [inputs]
    files: list[Path] = []
    for item in inputs:
        p = Path(item).expanduser()
        if p.is_dir():
            files.extend(sorted(p.glob("*.pdf")))
        else:
            files.append(p)
    if not files:
        raise ValueError("输入为空（目录中没有 PDF，或未传入路径）")
    return files


def batch_ocr(
    inputs,
    lang: str | None = None,
    deskew: bool = False,
    redo_ocr: bool = False,
    out_dir: str | Path | None = None,
    overwrite: bool = False,
    per_file_timeout: float | None = None,
    max_retries: int = 0,
) -> dict:
    """批量 OCR：inputs 为文件列表或目录（取目录下全部 *.pdf）。

    单文件失败不中断整批；max_retries 次内重试；结果逐文件结构化返回。
    """
    files = _resolve_inputs(inputs)
    out = Path(out_dir).expanduser().resolve() if out_dir else None

    results: list[dict] = []
    succeeded = failed = 0
    for f in files:
        entry: dict = {"input": str(f), "ok": False}
        attempts = max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                r = ocr_pdf(
                    f,
                    lang=lang,
                    deskew=deskew,
                    redo_ocr=redo_ocr,
                    output=(out / f"{f.stem}_ocr.pdf") if out else None,
                    overwrite=overwrite,
                    timeout=per_file_timeout,
                )
                entry.update(
                    ok=True,
                    output=r["output"],
                    lang=r["lang"],
                    lang_fallback=r["lang_fallback"],
                    size_bytes=r["size_bytes"],
                    attempts=attempt,
                )
                break
            except FileExistsError as exc:
                entry.update(error="output_exists", message=str(exc), attempts=attempt)
                break  # 已存在不是瞬时故障，不重试
            except Exception as exc:
                entry.update(
                    error=type(exc).__name__,
                    message=str(exc)[:300],
                    attempts=attempt,
                )
        results.append(entry)
        if entry["ok"]:
            succeeded += 1
        else:
            failed += 1

    return {
        "total": len(files),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }
