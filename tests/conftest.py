"""pytest 共享 fixture：样本生成 + 依赖分级 skip 标记。

样本策略（跨平台，无字体依赖）：
- text.pdf     fpdf2 直接生成 3 页
- scanned.pdf  先用 pdftoppm 把 text.pdf 前两页渲染成 PNG，再用 PIL 拼回 PDF
               （天然无文本层；复用渲染管线，绕开跨平台字体路径问题）
- encrypted.pdf pikepdf 强加密（user+owner 都显式设置，避免弱加密坑）
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

MARKER = "PDF-TOOLBOX-TEST-7734"


def _have(*bins: str) -> bool:
    return all(shutil.which(b) for b in bins)


requires_poppler = pytest.mark.skipif(
    not _have("pdfinfo", "pdftotext", "pdftoppm"), reason="需要 poppler (L1)"
)
requires_qpdf = pytest.mark.skipif(
    not _have("qpdf"), reason="需要 qpdf (L0)"
)
requires_tesseract = pytest.mark.skipif(
    not _have("tesseract"), reason="需要 tesseract (L2)"
)
requires_gs = pytest.mark.skipif(
    not _have("gs"), reason="需要 ghostscript (L3)"
)


def _make_text_pdf(out: Path) -> None:
    from fpdf import FPDF

    pdf = FPDF()
    for i in range(1, 4):
        pdf.add_page()
        pdf.set_font("Helvetica", size=16)
        pdf.cell(text=f"Sample Page {i}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=11)
        pdf.multi_cell(
            w=0,
            text=(
                f"This is page {i} of the pdf-toolbox-mcp test fixture.\n"
                f"Marker string: {MARKER}\n"
                "The quick brown fox jumps over the lazy dog."
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )
    pdf.output(out)


def _make_scanned_pdf(text_pdf: Path, out: Path) -> None:
    from PIL import Image

    subprocess.run(
        ["pdftoppm", "-png", "-r", "150", "-f", "1", "-l", "2", str(text_pdf), str(out.with_suffix(""))],
        check=True,
        capture_output=True,
        timeout=120,
    )
    pngs = sorted(out.with_suffix("").parent.glob(f"{out.with_suffix('').name}-*.png"))
    assert len(pngs) == 2, f"pdftoppm 产物数量异常: {pngs}"
    imgs = [Image.open(p).convert("RGB") for p in pngs]
    imgs[0].save(out, save_all=True, append_images=imgs[1:], resolution=150)
    for p in pngs:
        p.unlink()


def _make_encrypted_pdf(text_pdf: Path, out: Path) -> None:
    import pikepdf

    with pikepdf.open(text_pdf) as pdf:
        pdf.save(
            out,
            encryption=pikepdf.Encryption(
                user="pdf-toolbox-test", owner="pdf-toolbox-owner", R=6
            ),
        )


@pytest.fixture(scope="session")
def _fixdir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("fixtures")


@pytest.fixture(scope="session")
def text_pdf(_fixdir: Path) -> Path:
    out = _fixdir / "text.pdf"
    if not out.exists():
        _make_text_pdf(out)
    return out


@pytest.fixture(scope="session")
def scanned_pdf(_fixdir: Path, text_pdf: Path) -> Path:
    if not _have("pdftoppm"):
        pytest.skip("生成扫描件样本需要 poppler")
    out = _fixdir / "scanned.pdf"
    if not out.exists():
        _make_scanned_pdf(text_pdf, out)
    return out


@pytest.fixture(scope="session")
def encrypted_pdf(_fixdir: Path, text_pdf: Path) -> Path:
    out = _fixdir / "encrypted.pdf"
    if not out.exists():
        _make_encrypted_pdf(text_pdf, out)
    return out


@pytest.fixture(scope="session")
def attached_pdf(_fixdir: Path, text_pdf: Path) -> Path:
    import pikepdf

    out = _fixdir / "attached.pdf"
    if not out.exists():
        payload = _fixdir / "note.txt"
        payload.write_bytes(b"PDF-TOOLBOX-ATTACH-TEST")
        with pikepdf.open(text_pdf) as pdf:
            pdf.attachments["note.txt"] = pikepdf.AttachedFileSpec.from_filepath(
                pdf, payload, description="test attachment"
            )
            pdf.save(out)
    return out


@pytest.fixture(scope="session")
def corrupted_pdf(_fixdir: Path, text_pdf: Path) -> Path:
    out = _fixdir / "corrupted.pdf"
    if not out.exists():
        data = bytearray(text_pdf.read_bytes())
        # 中段置零破坏流数据、保留 xref/trailer：qpdf --check 稳定检出，
        # 且修复（重建）跨 qpdf 版本确定性成功——截断式损坏在旧版 qpdf 上不可恢复
        lo = len(data) // 3
        data[lo : lo + 48] = b"\x00" * 48
        out.write_bytes(bytes(data))
    return out


@pytest.fixture(scope="session")
def dirty_pdf(_fixdir: Path, text_pdf: Path) -> Path:
    """带敏感信息的样本：元数据 + 附件 + OpenAction 动作——sanitize 的靶子。"""
    import pikepdf

    out = _fixdir / "dirty.pdf"
    if not out.exists():
        payload = _fixdir / "hidden.txt"
        payload.write_bytes(b"SECRET-ATTACHMENT")
        with pikepdf.open(text_pdf) as pdf:
            pdf.docinfo["/Title"] = "Secret Project Title"
            pdf.docinfo["/Author"] = "Secret Author"
            pdf.Root.OpenAction = pikepdf.Array(
                [pdf.pages[0].obj, pikepdf.Name.XYZ, 0, 792, None]
            )
            pdf.attachments["hidden.txt"] = pikepdf.AttachedFileSpec.from_filepath(
                pdf, payload, description="secret"
            )
            pdf.save(out)
    return out


@pytest.fixture(scope="session")
def form_pdf(_fixdir: Path, text_pdf: Path) -> Path:
    """带 AcroForm 文本字段（fullname / email）的样本——fill_form 的靶子。"""
    import pikepdf

    out = _fixdir / "form.pdf"
    if not out.exists():
        with pikepdf.open(text_pdf) as pdf:
            page = pdf.pages[0]
            fields = []
            for name, y in (("fullname", 740), ("email", 700)):
                widget = pikepdf.Dictionary(
                    Type=pikepdf.Name.Annot,
                    Subtype=pikepdf.Name.Widget,
                    FT=pikepdf.Name.Tx,
                    T=name,
                    V="",
                    Rect=[72, y, 320, y + 24],
                    DA="/Helv 12 Tf 0 g",
                    P=page.obj,
                )
                ref = pdf.make_indirect(widget)
                page.Annots = [ref] if "/Annots" not in page else [*page.Annots, ref]
                fields.append(ref)
            pdf.Root.AcroForm = pikepdf.Dictionary(
                Fields=fields, NeedAppearances=True
            )
            pdf.save(out)
    return out


def make_text_pdf(
    out: Path,
    *,
    pages: int = 3,
    paragraphs_per_page: int = 2,
    marker_repeats: int = 1,
    include_marker: bool = True,
    title: str | None = None,
) -> Path:
    """生成可控密度的文本 PDF。"""
    from fpdf import FPDF

    pdf = FPDF()
    if title:
        pdf.set_title(title)
    for i in range(1, pages + 1):
        pdf.add_page()
        pdf.set_font("Helvetica", size=16)
        pdf.cell(text=f"Scenario Page {i}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=11)
        blocks = []
        for _ in range(paragraphs_per_page):
            marker_text = f"{MARKER} " if include_marker else ""
            blocks.append(
                (
                    f"This is page {i} of a generated PDF for scenario coverage. "
                    f"{marker_text}"
                    + "The quick brown fox jumps over the lazy dog. " * marker_repeats
                ).strip()
            )
        pdf.multi_cell(w=0, text="\n\n".join(blocks), new_x="LMARGIN", new_y="NEXT")
    pdf.output(out)
    return out


def make_scanned_pdf(
    text_pdf: Path,
    out: Path,
    *,
    first_page: int = 1,
    last_page: int | None = None,
    dpi: int = 150,
) -> Path:
    """把文本 PDF 渲染回图像 PDF，作为扫描件样本。"""
    from PIL import Image

    prefix = out.with_suffix("")
    end = last_page if last_page is not None else first_page
    subprocess.run(
        [
            "pdftoppm",
            "-png",
            "-r",
            str(dpi),
            "-f",
            str(first_page),
            "-l",
            str(end),
            str(text_pdf),
            str(prefix),
        ],
        check=True,
        capture_output=True,
        timeout=120,
    )
    pngs = sorted(prefix.parent.glob(f"{prefix.name}-*.png"))
    imgs = [Image.open(p).convert("RGB") for p in pngs]
    imgs[0].save(out, save_all=True, append_images=imgs[1:], resolution=dpi)
    for p in pngs:
        p.unlink()
    return out


def make_dirty_pdf(
    base_pdf: Path,
    out: Path,
    *,
    with_attachment: bool = True,
    with_open_action: bool = True,
    with_annotation: bool = False,
    attachment_count: int = 1,
) -> Path:
    """生成带元数据/附件/动作/注释的脏样本。"""
    import pikepdf

    with pikepdf.open(base_pdf) as pdf:
        pdf.docinfo["/Title"] = "Secret Project Title"
        pdf.docinfo["/Author"] = "Secret Author"
        if with_open_action:
            pdf.Root.OpenAction = pikepdf.Array(
                [pdf.pages[0].obj, pikepdf.Name.XYZ, 0, 792, None]
            )
        if with_annotation:
            annot = pikepdf.Dictionary(
                Type=pikepdf.Name.Annot,
                Subtype=pikepdf.Name.Text,
                Rect=[72, 720, 120, 760],
                Contents="hidden annotation",
                Name=pikepdf.Name.Comment,
            )
            ref = pdf.make_indirect(annot)
            page = pdf.pages[0]
            page.Annots = [ref] if "/Annots" not in page else [*page.Annots, ref]
        if with_attachment:
            for idx in range(attachment_count):
                payload = out.with_name(f"hidden-{idx}.txt")
                payload.write_bytes(f"SECRET-ATTACHMENT-{idx}".encode())
                pdf.attachments[payload.name] = pikepdf.AttachedFileSpec.from_filepath(
                    pdf, payload, description=f"secret-{idx}"
                )
        pdf.save(out)
    return out


def make_form_pdf(
    base_pdf: Path,
    out: Path,
    *,
    nested: bool = False,
    checkbox: bool = False,
) -> Path:
    """生成简单/嵌套/复选框表单样本。"""
    import pikepdf

    with pikepdf.open(base_pdf) as pdf:
        page = pdf.pages[0]
        fields = []

        def add_text_field(name: str, y: int, parent=None):
            widget = pikepdf.Dictionary(
                Type=pikepdf.Name.Annot,
                Subtype=pikepdf.Name.Widget,
                FT=pikepdf.Name.Tx,
                T=name,
                V="",
                Rect=[72, y, 320, y + 24],
                DA="/Helv 12 Tf 0 g",
                P=page.obj,
            )
            if parent is not None:
                widget.Parent = parent
            ref = pdf.make_indirect(widget)
            page.Annots = [ref] if "/Annots" not in page else [*page.Annots, ref]
            if parent is None:
                fields.append(ref)
            else:
                parent.Kids = [ref] if "/Kids" not in parent else [*parent.Kids, ref]
            return ref

        add_text_field("fullname", 740)
        add_text_field("email", 700)

        if nested:
            parent = pikepdf.Dictionary(T="employee")
            parent_ref = pdf.make_indirect(parent)
            fields.append(parent_ref)
            add_text_field("name", 660, parent=parent_ref)
            add_text_field("department", 620, parent=parent_ref)

        if checkbox:
            agree = pikepdf.Dictionary(
                Type=pikepdf.Name.Annot,
                Subtype=pikepdf.Name.Widget,
                FT=pikepdf.Name.Btn,
                T="agree",
                V=pikepdf.Name.Off,
                AS=pikepdf.Name.Off,
                Rect=[72, 580, 92, 600],
                DA="/Helv 12 Tf 0 g",
                P=page.obj,
            )
            agree_ref = pdf.make_indirect(agree)
            page.Annots = [*page.Annots, agree_ref]
            fields.append(agree_ref)

        pdf.Root.AcroForm = pikepdf.Dictionary(Fields=fields, NeedAppearances=True)
        pdf.save(out)
    return out
