"""protect / unlock：加密与解锁（qpdf，L0）。

unlock 是差异化刚需（竞品实测 §8.2：三家硬失败、一家过严）——
本实现与 qpdf 默认一致：user 密码即可解锁，产物为解密文件。
"""

from __future__ import annotations

from pathlib import Path

from .errors import WrongPasswordError
from .pages import _page_count, _prep_output, _qpdf
from .probe import require
from .sandbox import assert_readable, ensure_pdf


def protect_pdf(
    path: str | Path,
    user_password: str = "",
    owner_password: str | None = None,
    *,
    allow_print: bool = True,
    allow_extract: bool = True,
    allow_modify: bool = False,
    allow_annotate: bool = False,
    allow_form: bool = False,
    allow_assembly: bool = False,
    output: str | Path | None = None,
    overwrite: bool = False,
) -> dict:
    """AES-256 加密。user_password 为空 = 仅权限限制（打开无密码）。

    权限默认"可打印可复制、不可改"——对外分发的常见形态。
    """
    pdf = assert_readable(ensure_pdf(Path(path)))
    require("qpdf")
    out = Path(output) if output else pdf.with_name(f"{pdf.stem}_locked.pdf")
    out = _prep_output(out, overwrite)

    owner = owner_password if owner_password is not None else user_password
    args = [
        str(pdf),
        "--encrypt", user_password, owner, "256",
        f"--print={'full' if allow_print else 'none'}",
        f"--extract={'y' if allow_extract else 'n'}",
        f"--modify-other={'y' if allow_modify else 'n'}",
        f"--annotate={'y' if allow_annotate else 'n'}",
        f"--form={'y' if allow_form else 'n'}",
        f"--assemble={'y' if allow_assembly else 'n'}",
        "--",
        str(out),
    ]
    _qpdf(args)
    return {
        "input": str(pdf),
        "output": str(out),
        "algorithm": "AES-256",
        "permissions": {
            "print": allow_print,
            "extract": allow_extract,
            "modify": allow_modify,
            "annotate": allow_annotate,
            "form": allow_form,
            "assembly": allow_assembly,
        },
    }


def unlock_pdf(
    path: str | Path,
    password: str,
    output: str | Path | None = None,
    overwrite: bool = False,
) -> dict:
    """用密码解锁并输出解密文件。user（打开）密码即可，无需 owner 密码。"""
    pdf = ensure_pdf(Path(path))
    require("qpdf")
    out = Path(output) if output else pdf.with_name(f"{pdf.stem}_unlocked.pdf")
    out = _prep_output(out, overwrite)

    try:
        _qpdf([f"--password={password}", "--decrypt", str(pdf), "--", str(out)])
    except RuntimeError as exc:
        if "password" in str(exc).lower():
            raise WrongPasswordError(f"密码错误或权限不足: {str(exc)[:180]}") from exc
        raise

    try:
        pages = _page_count(out)
    except Exception:
        pages = None
    return {"input": str(pdf), "output": str(out), "decrypted": True, "pages": pages}


def sanitize(
    path: str | Path,
    strip_javascript: bool = True,
    strip_metadata: bool = True,
    strip_attachments: bool = True,
    strip_annotations: bool = False,
    output: str | Path | None = None,
    overwrite: bool = False,
) -> dict:
    """发布版脱敏：剥离 JS/OpenAction/元数据/附件（可选注释）。

    只移除敏感结构，不动页面内容——正文文本保持可提取。
    """
    pdf_path = assert_readable(ensure_pdf(Path(path)))
    import pikepdf

    out = Path(output) if output else pdf_path.with_name(f"{pdf_path.stem}_sanitized.pdf")
    out = _prep_output(out, overwrite)

    removed: list[str] = []
    with pikepdf.open(pdf_path) as pdf:
        if strip_javascript:
            if "/OpenAction" in pdf.Root:
                del pdf.Root["/OpenAction"]
                removed.append("open_action")
            if "/Names" in pdf.Root and "/JavaScript" in pdf.Root.Names:
                del pdf.Root.Names["/JavaScript"]
                removed.append("javascript_names")
                if not dict(pdf.Root.Names):
                    del pdf.Root["/Names"]
            for page in pdf.pages:
                if "/AA" in page:
                    del page["/AA"]
                    removed.append("page_actions")
        if strip_metadata:
            for key in list(pdf.docinfo.keys()):
                del pdf.docinfo[key]
            removed.append("docinfo")
            if "/Metadata" in pdf.Root:
                del pdf.Root["/Metadata"]
                removed.append("xmp_metadata")
        if strip_attachments:
            if pdf.attachments:
                for name in list(pdf.attachments.keys()):
                    del pdf.attachments[name]
                removed.append("attachments")
            if "/AF" in pdf.Root:
                del pdf.Root["/AF"]
        if strip_annotations:
            for page in pdf.pages:
                if "/Annots" in page:
                    del page["/Annots"]
            removed.append("annotations")
        pdf.save(out)

    return {
        "input": str(pdf_path),
        "output": str(out),
        "removed": sorted(set(removed)),
        "note": "结构脱敏完成；正文文本未改动" if not strip_annotations
        else "结构脱敏完成（含注释移除）；正文文本未改动",
    }


def redact(
    path: str | Path,
    regions: list[dict],
    dpi: int = 150,
    output: str | Path | None = None,
    overwrite: bool = False,
    rasterize_all: bool = False,
) -> dict:
    """真涂黑（选择性光栅化）：只有含涂黑区域的页被栅格化并覆盖不透明黑块，
    其余页保留原矢量与文本层。

    坐标约定：regions = [{page, x, y, w, h}]，单位 PDF 点（1/72 英寸），
    原点左上、y 向下；页面应无 /Rotate（旋转页先 rotate_pages 归一）。

    安全语义：被涂页的产物为纯图像——被涂文字在文件中物理不存在，
    无法通过复制/提取/文本层恢复。rasterize_all=True 时全文档栅格化
    （最高防护档：连未涂区域的文本也不留）。
    """
    pdf = assert_readable(ensure_pdf(Path(path)))
    require("pdftoppm")

    dpi = max(72, min(int(dpi), 300))
    out = Path(output) if output else pdf.with_name(f"{pdf.stem}_redacted.pdf")
    out = _prep_output(out, overwrite)

    import subprocess as _sp
    import tempfile

    from PIL import Image, ImageDraw

    total = _page_count(pdf)
    by_page: dict[int, list[tuple[float, float, float, float]]] = {}
    for r in regions:
        page_no = int(r["page"])
        if not 1 <= page_no <= total:
            raise ValueError(f"页号超出范围 1–{total}：page={page_no}")
        w, h = float(r["w"]), float(r["h"])
        if w <= 0 or h <= 0:
            raise ValueError(f"区域宽高必须为正：{r}")
        by_page.setdefault(page_no, []).append(
            (float(r["x"]), float(r["y"]), float(r["x"]) + w, float(r["y"]) + h)
        )

    affected = set(range(1, total + 1)) if rasterize_all else set(by_page)

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        raster_pages: dict[int, Image.Image] = {}
        for page_no in sorted(affected):
            prefix = tmpdir / f"p{page_no}"
            proc = _sp.run(
                ["pdftoppm", "-png", "-r", str(dpi),
                 "-f", str(page_no), "-l", str(page_no), str(pdf), str(prefix)],
                capture_output=True, text=True, timeout=300,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"pdftoppm 失败: {proc.stderr.strip()[:300]}")
            png = next(tmpdir.glob(f"{prefix.name}-*.png"))
            img = Image.open(png).convert("RGB")
            if page_no in by_page:  # rasterize_all 时未涂的页不画框
                draw = ImageDraw.Draw(img)
                scale = dpi / 72.0
                for x0, y0, x1, y1 in by_page[page_no]:
                    draw.rectangle(
                        [round(x0 * scale), round(y0 * scale),
                         round(x1 * scale) - 1, round(y1 * scale) - 1],
                        fill="black",
                    )
            raster_pages[page_no] = img

        raster_pdf = tmpdir / "raster.pdf"
        imgs = [raster_pages[p] for p in sorted(raster_pages)]
        if imgs:
            imgs[0].save(
                raster_pdf, save_all=True, append_images=imgs[1:], resolution=dpi
            )

        # 组装：受影响页取自光栅 PDF，其余页原样保留（矢量与文本层不动）
        import pikepdf

        with pikepdf.open(pdf) as src:
            out_doc = pikepdf.new()
            if imgs:
                with pikepdf.open(raster_pdf) as ras:
                    ri = 0
                    for i in range(1, total + 1):
                        if i in raster_pages:
                            out_doc.pages.append(ras.pages[ri])
                            ri += 1
                        else:
                            out_doc.pages.append(src.pages[i - 1])
            else:
                out_doc.pages.extend(src.pages)
            out_doc.save(out)

    return {
        "input": str(pdf),
        "output": str(out),
        "pages": total,
        "rasterized_pages": sorted(affected),
        "regions_applied": sum(len(v) for v in by_page.values()),
        "dpi": dpi,
        "size_bytes": out.stat().st_size,
        "warning": (
            f"第 {sorted(affected)} 页已光栅化：这些页上的一切文字（含被涂区域）均不可再提取；"
            + ("全文档已光栅化" if len(affected) == total else "其余页保留原文本层")
        ),
    }


def redact_text(
    path: str | Path,
    queries: list[str],
    dpi: int = 150,
    pad: float = 2.0,
    output: str | Path | None = None,
    overwrite: bool = False,
    rasterize_all: bool = False,
) -> dict:
    """按内容真涂黑：对每个关键词 locate_text 定位全部出现处，扩充 pad 点后交给 redact。

    典型用法："把文档里所有出现的身份证号/合同编号涂掉"——无需手工量坐标。
    未匹配任何关键词时直接报错（避免产出无意义的副本）。
    """
    from .text import locate_text

    pdf = ensure_pdf(Path(path))
    if not queries:
        raise ValueError("queries 为空")

    regions: list[dict] = []
    located: dict[str, int] = {}
    for query in queries:
        found = locate_text(pdf, query)
        located[query] = found["count"]
        for m in found["matches"]:
            regions.append(
                {
                    "page": m["page"],
                    "x": m["x"] - pad,
                    "y": m["y"] - pad,
                    "w": m["w"] + 2 * pad,
                    "h": m["h"] + 2 * pad,
                }
            )
    if not regions:
        raise ValueError(f"未找到任何匹配：{queries}")

    result = redact(
        pdf, regions=regions, dpi=dpi, output=output,
        overwrite=overwrite, rasterize_all=rasterize_all,
    )
    result["queries"] = located
    result["regions_applied"] = len(regions)
    return result
