"""pdf-toolbox-mcp server：FastMCP stdio 薄壳。

工具 = P1a 五件（info / extract_text / ocr_pdf / render_pages / unlock_pdf）
     + P1b 四件（split / merge / rotate / protect）+ dependency_status + doctor。

_guard 约定（PLAN §5）：
- 成功：engine dict 原样返回 + `_deps` 能力摘要（{"level": N, "missing": [...]}）
- 失败：{"ok": False, "error": <code>, "message": ...}——缺依赖带 install 命令，
  加密件带 unlock_pdf 引导，agent 可据此自路由
"""

from __future__ import annotations

from .engine import (
    batch_ocr,
    check_repair,
    compress_pdf,
    edit_metadata,
    extract_attachments,
    extract_images,
    extract_text,
    fill_form,
    is_searchable,
    linearize,
    list_fonts,
    locate_text,
    merge_pdfs,
    ocr_pdf,
    pdf_info,
    protect_pdf,
    redact,
    redact_text,
    render_pages,
    rotate_pages,
    sanitize,
    split_pdf,
    unlock_pdf,
)
from .engine.errors import ToolboxError
from .engine.probe import deps_summary, probe_all
from .engine.sandbox import PageRangeError
from .onboarding import report_checks

try:
    from fastmcp import FastMCP
    from fastmcp.utilities.types import Image
except ImportError as exc:  # 允许 engine 单独使用（CLI 无需 fastmcp）
    raise SystemExit("需要 fastmcp：uv sync 或 pip install fastmcp") from exc


def _guard(fn, /, **kwargs):
    try:
        result = fn(**kwargs)
    except ToolboxError as exc:
        return exc.as_dict()
    except PageRangeError as exc:
        return {"ok": False, "error": "invalid_page_range", "message": str(exc)}
    except FileExistsError as exc:
        return {"ok": False, "error": "output_exists", "message": str(exc)}
    except FileNotFoundError as exc:
        return {"ok": False, "error": "file_not_found", "message": str(exc)}
    except PermissionError as exc:
        return {"ok": False, "error": "permission_denied", "message": str(exc)}
    except ValueError as exc:
        return {"ok": False, "error": "invalid_argument", "message": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": "internal_error",
                "message": f"{type(exc).__name__}: {exc}"}
    if isinstance(result, dict):
        result.setdefault("_deps", deps_summary())
    return result


mcp = FastMCP(
    "pdf-toolbox",
    instructions=(
        "本地 PDF 处理：扫描件先 ocr_pdf 写回可搜索层再 extract_text；"
        "复杂版面/图表用 render_pages(return_images=True) 直接看图；"
        "加密文件先 unlock_pdf（user 密码即可）再走其他工具；"
        "对外分发用 protect_pdf。返回带 ok:false 时按 error 字段自路由："
        "missing_dependency→看 install/unlocks 字段装依赖；encrypted_pdf→先 unlock_pdf。"
    ),
)


@mcp.tool
def tool_pdf_info(path: str) -> dict:
    """获取 PDF 元信息：页数、是否加密、页面尺寸、标题作者等。处理任何 PDF 前先调用此工具。"""
    return _guard(pdf_info, path=path)


@mcp.tool
def tool_extract_text(
    path: str,
    pages: str | None = None,
    layout: bool = False,
    per_page: bool = False,
) -> dict:
    """提取 PDF 文本（pdftotext）。pages 精确页范围如 '1-3,5'；layout 保持版面；per_page 按页返回。"""
    return _guard(extract_text, path=path, pages=pages, layout=layout, per_page=per_page)


@mcp.tool
def tool_ocr_pdf(
    path: str,
    lang: str | None = None,
    deskew: bool = False,
    redo_ocr: bool = False,
    output: str | None = None,
    overwrite: bool = False,
) -> dict:
    """对扫描件 OCR 并把文本层写回，产出可搜索 PDF（输出 <stem>_ocr.pdf）——本工具箱的核心差异化能力。

    默认跳过已有文本层的页；默认语言 chi_sim+eng（缺语言包时自动降级并在结果中说明）。"""
    return _guard(ocr_pdf, path=path, lang=lang, deskew=deskew,
                  redo_ocr=redo_ocr, output=output, overwrite=overwrite)


@mcp.tool
def tool_render_pages(
    path: str,
    pages: str = "1",
    dpi: int = 150,
    out_dir: str | None = None,
    return_images: bool = False,
):
    """渲染指定页为 PNG。return_images=True 时直接返回图像内容块（供视觉查看复杂版面/图表/扫描页）。"""
    result = _guard(render_pages, path=path, pages=pages, dpi=dpi, out_dir=out_dir)
    if not return_images or not isinstance(result, dict) or result.get("ok") is False:
        return result
    return [
        {k: v for k, v in result.items() if k != "images"},
        *[Image(path=img["file"], format="png") for img in result["images"]],
    ]


@mcp.tool
def tool_unlock_pdf(
    path: str,
    password: str,
    output: str | None = None,
    overwrite: bool = False,
) -> dict:
    """用密码解锁加密 PDF，输出解密文件。user（打开）密码即可，无需 owner 密码。解锁后再走其他工具。"""
    return _guard(unlock_pdf, path=path, password=password, output=output, overwrite=overwrite)


@mcp.tool
def tool_split_pdf(
    path: str,
    ranges: str | None = None,
    every_n: int | None = None,
    out_dir: str | None = None,
    overwrite: bool = False,
) -> dict:
    """拆分 PDF：ranges='1-3,5' 按区间出文件，或 every_n=N 每 N 页一段。二者二选一。"""
    return _guard(split_pdf, path=path, ranges=ranges, every_n=every_n,
                  out_dir=out_dir, overwrite=overwrite)


@mcp.tool
def tool_merge_pdfs(
    paths: list[str],
    output: str,
    overwrite: bool = False,
) -> dict:
    """按传入顺序合并多个 PDF 为一个文件。"""
    return _guard(merge_pdfs, paths=paths, output=output, overwrite=overwrite)


@mcp.tool
def tool_rotate_pages(
    path: str,
    angle: int,
    pages: str | None = None,
    output: str | None = None,
    overwrite: bool = False,
) -> dict:
    """旋转页面 90/180/270 度。pages 缺省旋转全部页。"""
    return _guard(rotate_pages, path=path, angle=angle, pages=pages,
                  output=output, overwrite=overwrite)


@mcp.tool
def tool_protect_pdf(
    path: str,
    user_password: str = "",
    owner_password: str | None = None,
    allow_print: bool = True,
    allow_extract: bool = True,
    allow_modify: bool = False,
    allow_annotate: bool = False,
    allow_form: bool = False,
    allow_assembly: bool = False,
    output: str | None = None,
    overwrite: bool = False,
) -> dict:
    """AES-256 加密（对外分发）。user_password 留空 = 打开无密码、仅权限限制；权限默认可打印可复制、不可修改。"""
    return _guard(protect_pdf, path=path, user_password=user_password,
                  owner_password=owner_password, allow_print=allow_print,
                  allow_extract=allow_extract, allow_modify=allow_modify,
                  allow_annotate=allow_annotate, allow_form=allow_form,
                  allow_assembly=allow_assembly, output=output, overwrite=overwrite)


@mcp.tool
def tool_is_searchable(path: str, sample_pages: int = 5) -> dict:
    """智能路由入口：判断 PDF 是否已有可提取文本层，返回建议动作（extract_text 或先 ocr_pdf）。不确定时先调这个。"""
    return _guard(is_searchable, path=path, sample_pages=sample_pages)


@mcp.tool
def tool_list_fonts(path: str) -> dict:
    """字体体检：列出字体与嵌入状态，未嵌入字体跨设备查看/打印可能缺字。"""
    return _guard(list_fonts, path=path)


@mcp.tool
def tool_extract_images(
    path: str,
    pages: str | None = None,
    list_only: bool = False,
    out_dir: str | None = None,
) -> dict:
    """抽取 PDF 内嵌图片为 PNG；list_only=true 只返回图片清单不落盘。"""
    return _guard(extract_images, path=path, pages=pages, list_only=list_only, out_dir=out_dir)


@mcp.tool
def tool_extract_attachments(path: str, out_dir: str | None = None) -> dict:
    """抽取 PDF 内嵌附件文件到指定目录。"""
    return _guard(extract_attachments, path=path, out_dir=out_dir)


@mcp.tool
def tool_check_repair(
    path: str,
    repair: bool = False,
    output: str | None = None,
    overwrite: bool = False,
) -> dict:
    """结构体检（语法/流编码）；repair=true 尝试重建输出修复版文件。"""
    return _guard(check_repair, path=path, repair=repair, output=output, overwrite=overwrite)


@mcp.tool
def tool_linearize(
    path: str,
    output: str | None = None,
    overwrite: bool = False,
) -> dict:
    """Web 优化：输出渐进加载版，适合在线浏览的发布文件。"""
    return _guard(linearize, path=path, output=output, overwrite=overwrite)


@mcp.tool
def tool_batch_ocr(
    inputs: list[str],
    lang: str | None = None,
    deskew: bool = False,
    redo_ocr: bool = False,
    out_dir: str | None = None,
    overwrite: bool = False,
    per_file_timeout: float | None = None,
    max_retries: int = 0,
) -> dict:
    """批量 OCR 写回：inputs 为文件路径或目录（取全部 PDF）。单文件失败不中断，逐文件返回结果。"""
    return _guard(batch_ocr, inputs=inputs, lang=lang, deskew=deskew,
                  redo_ocr=redo_ocr, out_dir=out_dir, overwrite=overwrite,
                  per_file_timeout=per_file_timeout, max_retries=max_retries)


@mcp.tool
def tool_sanitize(
    path: str,
    strip_javascript: bool = True,
    strip_metadata: bool = True,
    strip_attachments: bool = True,
    strip_annotations: bool = False,
    output: str | None = None,
    overwrite: bool = False,
) -> dict:
    """发布版脱敏：剥离 JS/OpenAction/元数据/附件（可选注释）。正文文本不动——防元数据与隐藏对象泄密。"""
    return _guard(sanitize, path=path, strip_javascript=strip_javascript,
                  strip_metadata=strip_metadata, strip_attachments=strip_attachments,
                  strip_annotations=strip_annotations, output=output, overwrite=overwrite)


@mcp.tool
def tool_redact(
    path: str,
    regions: list[dict],
    dpi: int = 150,
    output: str | None = None,
    overwrite: bool = False,
    rasterize_all: bool = False,
) -> dict:
    """真涂黑（安全级）：regions=[{page,x,y,w,h}]（PDF 点、左上原点）。含涂黑区域的页被光栅化——
    被涂文字物理删除，复制/提取/文本层均无法恢复；其余页保留原文本层。
    rasterize_all=true 全文档光栅化（最高防护档）。"""
    return _guard(redact, path=path, regions=regions, dpi=dpi,
                  output=output, overwrite=overwrite, rasterize_all=rasterize_all)


@mcp.tool
def tool_locate_text(
    path: str,
    query: str,
    pages: str | None = None,
    max_results: int = 50,
) -> dict:
    """定位文本出现的页面与坐标框（PDF 点、左上原点）——找内容在哪、给 redact 量坐标的地基。

    中文无分词、英文跨词均可命中（NFKC 归一化去空白匹配）。"""
    return _guard(locate_text, path=path, query=query, pages=pages, max_results=max_results)


@mcp.tool
def tool_redact_text(
    path: str,
    queries: list[str],
    dpi: int = 150,
    output: str | None = None,
    overwrite: bool = False,
    rasterize_all: bool = False,
) -> dict:
    """按内容真涂黑：自动定位每个关键词的全部出现处并涂黑（无需手工量坐标）。
    如"把所有合同编号涂掉"。被涂页光栅化、文字物理删除；其余页保留文本层。"""
    return _guard(redact_text, path=path, queries=queries, dpi=dpi,
                  output=output, overwrite=overwrite, rasterize_all=rasterize_all)


@mcp.tool
def tool_fill_form(
    path: str,
    fields: dict,
    output: str | None = None,
    overwrite: bool = False,
) -> dict:
    """填写 AcroForm 表单（字段名→字符串/布尔）。未匹配字段在 missing 中返回。"""
    return _guard(fill_form, path=path, fields=fields, output=output, overwrite=overwrite)


@mcp.tool
def tool_edit_metadata(
    path: str,
    title: str | None = None,
    author: str | None = None,
    subject: str | None = None,
    keywords: str | None = None,
    creator: str | None = None,
    clear: bool = False,
    output: str | None = None,
    overwrite: bool = False,
) -> dict:
    """编辑元数据（docinfo+XMP 双写）；clear=true 清空全部——对外发布前配合 sanitize 使用。"""
    return _guard(edit_metadata, path=path, title=title, author=author,
                  subject=subject, keywords=keywords, creator=creator,
                  clear=clear, output=output, overwrite=overwrite)


@mcp.tool
def tool_compress_pdf(
    path: str,
    target_mb: float | None = None,
    quality: str = "ebook",
    output: str | None = None,
    overwrite: bool = False,
) -> dict:
    """压缩 PDF（ghostscript，有损：图像重采样）。target_mb 给定时沿 ebook→screen 下探直到达标（尽力而为）。"""
    return _guard(compress_pdf, path=path, target_mb=target_mb, quality=quality,
                  output=output, overwrite=overwrite)


@mcp.tool
def tool_dependency_status() -> list[dict]:
    """探测系统依赖（qpdf/poppler/tesseract/ghostscript）、安装命令与可解锁工具。工具报 missing_dependency 时先看这里。"""
    return [d.as_dict() for d in probe_all()]


@mcp.tool
def tool_doctor() -> dict:
    """一键诊断：导入、依赖快照、README 关键路径。"""
    return report_checks()


def main() -> None:
    mcp.run()  # stdio


if __name__ == "__main__":
    main()
