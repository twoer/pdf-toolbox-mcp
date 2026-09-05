"""pdftoolbox CLI：子命令与 MCP 工具一一对应（typer 薄壳）。"""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path

import typer

from . import __version__
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
from .engine.probe import probe_all


def _ensure_utf8_stdio() -> None:
    """Windows 控制台默认码页（cp1252/GBK）编码不了 ✅ 与中文——统一按 UTF-8 输出。"""
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(Exception):
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]


_ensure_utf8_stdio()

app = typer.Typer(
    name="pdftoolbox",
    help="本地 PDF 处理引擎（OCR 写回 / 文本提取 / 页面渲染 / 元数据）",
    no_args_is_help=True,
)
probe_app = typer.Typer(help="依赖探测")
app.add_typer(probe_app, name="probe")


def _echo(result: dict) -> None:
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2, default=str))


@app.command()
def info(path: Path) -> None:
    """PDF 元信息（pdfinfo）"""
    _echo(pdf_info(path))


@app.command()
def text(
    path: Path,
    pages: str | None = typer.Option(None, help="页范围，如 1-3,5"),
    layout: bool = typer.Option(False, help="保持版面"),
    per_page: bool = typer.Option(False, help="按页返回"),
) -> None:
    """提取文本（pdftotext）"""
    _echo(extract_text(path, pages=pages, layout=layout, per_page=per_page))


@app.command()
def ocr(
    path: Path,
    lang: str = typer.Option(None, help="tesseract 语言，默认 chi_sim+eng"),
    output: Path | None = typer.Option(None, help="输出路径，默认 <stem>_ocr.pdf"),
    deskew: bool = typer.Option(False, help="自动纠偏"),
    redo: bool = typer.Option(False, help="重做已有 OCR 层"),
    overwrite: bool = typer.Option(False, help="覆盖已存在输出"),
) -> None:
    """OCR 写回可搜索 PDF（ocrmypdf）"""
    _echo(
        ocr_pdf(
            path, lang=lang, output=output, deskew=deskew,
            redo_ocr=redo, overwrite=overwrite,
        )
    )


@app.command()
def render(
    path: Path,
    pages: str = typer.Option("1", help="页范围，如 1-3,5"),
    dpi: int = typer.Option(150, help="72–300"),
    out_dir: Path | None = typer.Option(None),
) -> None:
    """渲染页面为 PNG（pdftoppm）"""
    _echo(render_pages(path, pages=pages, dpi=dpi, out_dir=out_dir))


@app.command()
def split(
    path: Path,
    ranges: str = typer.Option(None, help="如 '1-3,5'"),
    every_n: int = typer.Option(None, help="每 N 页一段（与 ranges 二选一）"),
    out_dir: Path | None = typer.Option(None),
    overwrite: bool = typer.Option(False),
) -> None:
    """拆分 PDF（qpdf）"""
    _echo(split_pdf(path, ranges=ranges, every_n=every_n, out_dir=out_dir, overwrite=overwrite))


@app.command()
def merge(
    paths: list[Path] = typer.Argument(..., help="按顺序合并的多个 PDF"),
    output: Path = typer.Option(..., help="输出文件"),
    overwrite: bool = typer.Option(False),
) -> None:
    """合并 PDF（qpdf）"""
    _echo(merge_pdfs(paths, output=output, overwrite=overwrite))


@app.command()
def rotate(
    path: Path,
    angle: int = typer.Option(..., help="90/180/270"),
    pages: str = typer.Option(None, help="缺省全部页"),
    output: Path | None = typer.Option(None),
    overwrite: bool = typer.Option(False),
) -> None:
    """旋转页面（qpdf）"""
    _echo(rotate_pages(path, angle=angle, pages=pages, output=output, overwrite=overwrite))


@app.command()
def protect(
    path: Path,
    user_password: str = typer.Option("", help="打开密码；留空=仅权限限制"),
    owner_password: str = typer.Option(None),
    output: Path | None = typer.Option(None),
    overwrite: bool = typer.Option(False),
) -> None:
    """AES-256 加密（默认可打印可复制、不可修改）"""
    _echo(protect_pdf(path, user_password=user_password, owner_password=owner_password,
                      output=output, overwrite=overwrite))


@app.command()
def unlock(
    path: Path,
    password: str = typer.Option(..., help="user（打开）密码即可"),
    output: Path | None = typer.Option(None),
    overwrite: bool = typer.Option(False),
) -> None:
    """解锁加密 PDF，输出解密文件"""
    _echo(unlock_pdf(path, password=password, output=output, overwrite=overwrite))


@app.command()
def searchable(path: Path, sample: int = typer.Option(5)) -> None:
    """判断是否可搜索并给出建议动作"""
    _echo(is_searchable(path, sample_pages=sample))


@app.command()
def fonts(path: Path) -> None:
    """字体体检（嵌入状态）"""
    _echo(list_fonts(path))


@app.command()
def images(
    path: Path,
    pages: str | None = typer.Option(None),
    list_only: bool = typer.Option(False, "--list-only", help="只列清单不落盘"),
    out_dir: Path | None = typer.Option(None),
) -> None:
    """抽取内嵌图片"""
    _echo(extract_images(path, pages=pages, list_only=list_only, out_dir=out_dir))


@app.command()
def attachments(path: Path, out_dir: Path | None = typer.Option(None)) -> None:
    """抽取内嵌附件"""
    _echo(extract_attachments(path, out_dir=out_dir))


@app.command()
def check(
    path: Path,
    repair: bool = typer.Option(False),
    output: Path | None = typer.Option(None),
    overwrite: bool = typer.Option(False),
) -> None:
    """结构体检，可尝试修复"""
    _echo(check_repair(path, repair=repair, output=output, overwrite=overwrite))


@app.command()
def linearize_cmd(
    path: Path,
    output: Path | None = typer.Option(None),
    overwrite: bool = typer.Option(False),
) -> None:
    """Web 优化（渐进加载）"""
    _echo(linearize(path, output=output, overwrite=overwrite))


batch_app = typer.Typer(help="批处理")
app.add_typer(batch_app, name="batch")


@batch_app.command("ocr")
def batch_ocr_cmd(
    inputs: list[Path] = typer.Argument(..., help="PDF 文件或目录"),
    lang: str = typer.Option(None),
    out_dir: Path | None = typer.Option(None),
    overwrite: bool = typer.Option(False),
    retries: int = typer.Option(0, help="单文件失败重试次数"),
    timeout: float | None = typer.Option(None, help="单文件秒数上限"),
) -> None:
    """批量 OCR 写回（逐文件结果）"""
    _echo(
        batch_ocr(
            inputs, lang=lang, out_dir=out_dir, overwrite=overwrite,
            max_retries=retries, per_file_timeout=timeout,
        )
    )


@app.command()
def locate(
    path: Path,
    query: str = typer.Option(...),
    pages: str | None = typer.Option(None),
) -> None:
    """定位文本出现的页面与坐标（PDF 点、左上原点）"""
    _echo(locate_text(path, query=query, pages=pages))


@app.command()
def redact_text_cmd(
    path: Path,
    queries: list[str] = typer.Option(..., "--query", help="可多次传入"),
    dpi: int = typer.Option(150),
    output: Path | None = typer.Option(None),
    overwrite: bool = typer.Option(False),
) -> None:
    """按内容真涂黑（自动定位全部出现处）"""
    _echo(redact_text(path, queries=queries, dpi=dpi, output=output, overwrite=overwrite))


@app.command()
def sanitize_cmd(
    path: Path,
    output: Path | None = typer.Option(None),
    keep_annotations: bool = typer.Option(False, help="保留注释（默认剥离）"),
    overwrite: bool = typer.Option(False),
) -> None:
    """发布版脱敏：剥 JS/元数据/附件"""
    _echo(sanitize(path, strip_annotations=not keep_annotations,
                   output=output, overwrite=overwrite))


@app.command()
def redact_cmd(
    path: Path,
    regions: str = typer.Option(..., help='JSON 数组，如 \'[{"page":1,"x":60,"y":100,"w":300,"h":30}]\''),
    dpi: int = typer.Option(150),
    output: Path | None = typer.Option(None),
    overwrite: bool = typer.Option(False),
) -> None:
    """真涂黑（全文档光栅化，被涂内容物理删除）"""
    import json as _json

    _echo(redact(path, regions=_json.loads(regions), dpi=dpi,
                 output=output, overwrite=overwrite))


@app.command()
def fill(
    path: Path,
    fields: str = typer.Option(..., help='JSON 对象，如 \'{"fullname":"张三","email":"a@b.c"}\''),
    output: Path | None = typer.Option(None),
    overwrite: bool = typer.Option(False),
) -> None:
    """填写 AcroForm 表单"""
    import json as _json

    _echo(fill_form(path, fields=_json.loads(fields), output=output, overwrite=overwrite))


@app.command()
def meta(
    path: Path,
    title: str = typer.Option(None),
    author: str = typer.Option(None),
    subject: str = typer.Option(None),
    clear: bool = typer.Option(False),
    output: Path | None = typer.Option(None),
    overwrite: bool = typer.Option(False),
) -> None:
    """编辑元数据"""
    _echo(edit_metadata(path, title=title, author=author, subject=subject,
                        clear=clear, output=output, overwrite=overwrite))


@app.command()
def compress(
    path: Path,
    target_mb: float = typer.Option(None, help="目标大小（MB），尽力而为"),
    quality: str = typer.Option("ebook", help="prepress/printer/ebook/screen"),
    output: Path | None = typer.Option(None),
    overwrite: bool = typer.Option(False),
) -> None:
    """压缩 PDF（ghostscript 有损）"""
    _echo(compress_pdf(path, target_mb=target_mb, quality=quality,
                       output=output, overwrite=overwrite))


@probe_app.command("all")
def probe() -> None:
    """探测系统依赖与能力级别"""
    for dep in probe_all():
        mark = "✅" if dep.found else "❌"
        typer.echo(f"{mark} L{dep.level} {dep.name:10s} {dep.version or ''}")
        if not dep.found:
            typer.echo(f"      install: {dep.install}")


@app.command()
def version() -> None:
    typer.echo(__version__)


if __name__ == "__main__":
    sys.exit(app())
