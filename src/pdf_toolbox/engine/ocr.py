"""ocr_pdf：OCR 写回可搜索 PDF（ocrmypdf 库调用，L2）——本项目差异化核心。"""

from __future__ import annotations

import os
from pathlib import Path

import ocrmypdf
from ocrmypdf.exceptions import (
    EncryptedPdfError as _OcrEncryptedError,
)
from ocrmypdf.exceptions import (
    MissingDependencyError as _OcrMissingDepError,
)
from ocrmypdf.exceptions import (
    PriorOcrFoundError as _OcrPriorFound,
)
from ocrmypdf.exceptions import (
    TaggedPDFError as _OcrTaggedPdf,
)

from .errors import EncryptedPdfError, ToolboxError
from .probe import require, tess_langs
from .sandbox import check_write, ensure_pdf

DEFAULT_LANG = os.environ.get("PDF_TOOLBOX_TESS_LANG", "chi_sim+eng")
_LANG_INSTALL_HINT = {
    "darwin": "brew install tesseract-lang（全部语言）或下载 chi_sim.traineddata 到 tessdata",
    "linux": "apt install tesseract-ocr-chi-sim（按语言替换后缀）",
    "win32": "从 https://github.com/UB-Mannheim/tesseract/wiki 下载语言包",
}


def resolve_lang(lang: str | None) -> tuple[str, bool]:
    """解析实际使用的语言串。

    - 显式传入的语言缺包 → ValueError（附安装命令）
    - 默认语言缺包 → 自动降级到已有语言（eng 优先），返回 fallback=True
    """
    requested = lang or DEFAULT_LANG
    avail = tess_langs()
    if not avail:  # tesseract 不在——交给 ocrmypdf/上层报 missing dependency
        return requested, False

    wanted = [code for code in requested.split("+") if code]
    missing = [code for code in wanted if code not in avail]
    if not missing:
        return requested, False

    if lang is not None:
        import platform

        hint = _LANG_INSTALL_HINT.get(platform.sys.platform, _LANG_INSTALL_HINT["linux"])
        raise ValueError(
            f"缺少 tesseract 语言包: {missing}。{hint}；"
            f"可用语言: {sorted(avail)[:10]}"
        )

    kept = [code for code in wanted if code in avail]
    if not kept and "eng" in avail:
        kept = ["eng"]
    if not kept:
        return requested, False
    return "+".join(kept), True


def ocr_pdf(
    path: str | Path,
    lang: str | None = None,
    deskew: bool = False,
    skip_text: bool = True,
    redo_ocr: bool = False,
    output: str | Path | None = None,
    overwrite: bool = False,
    timeout: float | None = None,
) -> dict:
    """对扫描件 OCR 并把文本层写回，产出可搜索 PDF。

    skip_text=True 跳过已有文本层的页；redo_ocr 重做旧 OCR 层（与 skip_text 互斥）。
    默认语言（chi_sim+eng）缺包时自动降级并在结果中说明；timeout 为单文件秒数上限。
    """
    pdf = ensure_pdf(Path(path))
    require("tesseract")
    out = Path(output) if output else pdf.with_name(f"{pdf.stem}_ocr.pdf")
    out = check_write(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not overwrite:
        raise FileExistsError(f"输出已存在（overwrite=True 才覆盖）: {out}")

    lang_effective, fell_back = resolve_lang(lang)

    try:
        result = ocrmypdf.ocr(
            str(pdf),
            str(out),
            language=lang_effective,
            deskew=deskew,
            skip_text=skip_text and not redo_ocr,
            redo_ocr=redo_ocr,
            progress_bar=False,
            timeout=timeout,
        )
    except _OcrPriorFound as exc:
        raise RuntimeError("已有 OCR 层：用 redo_ocr=True 重做，或 skip_text=True 跳过") from exc
    except _OcrTaggedPdf as exc:
        raise RuntimeError("Tagged PDF 不适合 skip_text，尝试 redo_ocr=True") from exc
    except _OcrEncryptedError:
        raise EncryptedPdfError(str(pdf)) from None
    except _OcrMissingDepError as exc:
        raise ToolboxError(f"ocrmypdf 依赖缺失: {exc}") from exc

    return {
        "input": str(pdf),
        "output": str(out),
        "lang": lang_effective,
        "lang_fallback": fell_back,
        "requested_lang": lang or DEFAULT_LANG,
        "sidecar_none": result == "skipped" if isinstance(result, str) else False,
        "size_bytes": out.stat().st_size if out.exists() else 0,
    }
