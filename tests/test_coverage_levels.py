"""低 / 中 / 高 三档覆盖：核心场景矩阵。"""

from __future__ import annotations

import shutil
import subprocess

import pikepdf
import pytest
from PIL import Image, ImageDraw

from conftest import (
    MARKER,
    make_dirty_pdf,
    make_form_pdf,
    make_scanned_pdf,
    make_text_pdf,
    requires_gs,
    requires_poppler,
    requires_qpdf,
    requires_tesseract,
)
from pdf_toolbox.engine import (
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


def _short_text_pdf(tmp_path):
    from fpdf import FPDF

    out = tmp_path / "short.pdf"
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    pdf.cell(text="Hi", new_x="LMARGIN", new_y="NEXT")
    pdf.output(out)
    return out


def _dense_text_pdf(tmp_path):
    return make_text_pdf(
        tmp_path / "dense.pdf",
        pages=8,
        paragraphs_per_page=4,
        marker_repeats=2,
    )


def _multi_font_pdf(tmp_path, name, fonts):
    from fpdf import FPDF

    out = tmp_path / name
    pdf = FPDF()
    for i, font in enumerate(fonts, 1):
        family, style = font if isinstance(font, tuple) else (font, "")
        pdf.add_page()
        pdf.set_font(family, style=style, size=14)
        label = family if not style else f"{family} {style}"
        pdf.cell(text=f"{label} page {i}", new_x="LMARGIN", new_y="NEXT")
    pdf.output(out)
    return out


def _image_pdf(tmp_path, name, *, pages=3):
    from fpdf import FPDF

    out = tmp_path / name
    canvas = Image.new("RGB", (160, 96), "white")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((16, 16, 144, 80), fill="navy")
    draw.text((32, 36), "img", fill="white")

    png = out.with_suffix(".png")
    canvas.save(png)

    pdf = FPDF()
    for _ in range(pages):
        pdf.add_page()
        pdf.image(str(png), x=20, y=24, w=50)
    pdf.output(str(out))
    png.unlink()
    return out


def _scan_pdf(tmp_path, source, name, *, first_page=1, last_page=None, dpi=150):
    return make_scanned_pdf(
        source,
        tmp_path / name,
        first_page=first_page,
        last_page=last_page,
        dpi=dpi,
    )


def _field_values(pdf_path):
    def walk(field):
        yield field
        for kid in field.get("/Kids", []):
            yield from walk(kid)

    def full_name(field):
        parts = [str(field.get("/T", ""))] if "/T" in field else []
        parent = field.get("/Parent")
        depth = 0
        while parent is not None and depth < 8:
            parts.append(str(parent.get("/T", "")))
            parent = parent.get("/Parent")
            depth += 1
        return ".".join(reversed([p for p in parts if p]))

    with pikepdf.open(pdf_path) as pdf:
        fields = {}
        for root in pdf.Root.AcroForm.Fields:
            for field in walk(root):
                fields[full_name(field)] = {
                    "V": str(field.V) if "/V" in field else "",
                    "AS": str(field.AS) if "/AS" in field else "",
                }
        return fields


def _page_count(path):
    with pikepdf.open(path) as pdf:
        return len(pdf.pages)


@requires_poppler
class TestInfoAndTextCoverage:
    def test_pdf_info_low(self, tmp_path):
        pdf = _short_text_pdf(tmp_path)
        info = pdf_info(pdf)
        assert info["pages"] == 1
        assert info["encrypted"] is False

    def test_pdf_info_medium(self, dirty_pdf):
        info = pdf_info(dirty_pdf)
        assert info["pages"] == 3
        assert info["encrypted"] is False
        assert info["title"] == "Secret Project Title"

    def test_pdf_info_high(self, encrypted_pdf):
        info = pdf_info(encrypted_pdf)
        assert info["encrypted"] is True
        assert info["pages"] is None

    def test_searchability_low(self, tmp_path):
        pdf = _short_text_pdf(tmp_path)
        result = is_searchable(pdf)
        assert result["searchable"] is False
        assert result["recommendation"] == "ocr_pdf"

    def test_searchability_medium(self, text_pdf):
        result = is_searchable(text_pdf)
        assert result["searchable"] is True
        assert result["recommendation"] == "extract_text"

    def test_searchability_high(self, tmp_path):
        pdf = _dense_text_pdf(tmp_path)
        result = is_searchable(pdf, sample_pages=8)
        assert result["searchable"] is True
        assert result["chars_per_page"] > 150

    def test_extract_text_low(self, tmp_path):
        pdf = make_text_pdf(tmp_path / "text_low.pdf", pages=1, paragraphs_per_page=1)
        result = extract_text(pdf, pages="1", per_page=True)
        assert list(result["per_page"]) == [1]
        assert MARKER in result["per_page"][1]

    def test_extract_text_medium(self, text_pdf):
        result = extract_text(text_pdf, pages="1,3")
        assert result["text"].count(MARKER) == 2

    def test_extract_text_high(self, tmp_path):
        pdf = _dense_text_pdf(tmp_path)
        result = extract_text(pdf, layout=True, per_page=True)
        assert len(result["per_page"]) == 8
        assert result["total_chars"] > 500

    def test_render_pages_low(self, text_pdf, tmp_path):
        result = render_pages(text_pdf, pages="1", dpi=72, out_dir=tmp_path)
        assert result["count"] == 1
        assert result["images"][0]["page"] == 1

    def test_render_pages_medium(self, text_pdf, tmp_path):
        result = render_pages(text_pdf, pages="1,3", dpi=100, out_dir=tmp_path)
        assert result["count"] == 2
        assert [img["page"] for img in result["images"]] == [1, 3]

    def test_render_pages_high(self, tmp_path):
        pdf = _dense_text_pdf(tmp_path)
        result = render_pages(pdf, pages="1-8", dpi=300, out_dir=tmp_path)
        assert result["count"] == 8
        assert result["dpi"] == 300


@requires_poppler
class TestFontsAndAssetsCoverage:
    def test_list_fonts_low(self, tmp_path):
        pdf = _multi_font_pdf(tmp_path, "fonts_low.pdf", ["Helvetica"])
        result = list_fonts(pdf)
        assert result["count"] == 1
        assert result["non_embedded_count"] == 1

    def test_list_fonts_medium(self, tmp_path):
        pdf = _multi_font_pdf(tmp_path, "fonts_med.pdf", ["Helvetica", "Courier", "Times"])
        result = list_fonts(pdf)
        assert result["count"] == 3
        assert result["non_embedded_count"] == 3

    def test_list_fonts_high(self, tmp_path):
        pdf = _multi_font_pdf(
            tmp_path,
            "fonts_high.pdf",
            [
                ("Helvetica", ""),
                ("Helvetica", "B"),
                ("Helvetica", "I"),
                ("Helvetica", "BI"),
            ],
        )
        result = list_fonts(pdf)
        assert result["count"] == 4
        assert result["non_embedded_count"] == 4
        assert result["warning"]

    def test_extract_images_low(self, tmp_path):
        pdf = _image_pdf(tmp_path, "images_low.pdf")
        result = extract_images(pdf, pages="1", list_only=True)
        assert result["count"] == 1
        assert [item["page"] for item in result["inventory"]] == [1]

    def test_extract_images_medium(self, tmp_path):
        pdf = _image_pdf(tmp_path, "images_medium.pdf")
        result = extract_images(pdf, pages="1,3", out_dir=tmp_path)
        assert result["count"] == 2
        assert [img["page"] for img in result["images"]] == [1, 3]

    def test_extract_images_high(self, tmp_path):
        pdf = _image_pdf(tmp_path, "images_high.pdf")
        result = extract_images(pdf, pages="1-2,2-3", out_dir=tmp_path)
        assert result["count"] == 3
        assert [img["page"] for img in result["images"]] == [1, 2, 3]

    def test_extract_attachments_low(self, attached_pdf, tmp_path):
        result = extract_attachments(attached_pdf, out_dir=tmp_path)
        assert result["count"] == 1
        assert result["attachments"][0]["name"] == "note.txt"

    def test_extract_attachments_medium(self, text_pdf):
        result = extract_attachments(text_pdf)
        assert result["count"] == 0
        assert result["saved"] == []

    def test_extract_attachments_high(self, text_pdf, tmp_path):
        dirty = make_dirty_pdf(
            text_pdf,
            tmp_path / "multi_attach.pdf",
            with_annotation=False,
            attachment_count=2,
        )
        result = extract_attachments(dirty, out_dir=tmp_path)
        assert result["count"] == 2
        assert {att["name"] for att in result["attachments"]} == {"hidden-0.txt", "hidden-1.txt"}


@requires_poppler
@requires_tesseract
class TestOcrCoverage:
    def test_ocr_low(self, tmp_path):
        base = _short_text_pdf(tmp_path)
        scanned = _scan_pdf(tmp_path, base, "ocr_low.pdf", last_page=1)
        result = ocr_pdf(scanned, lang="eng", overwrite=True)
        text = subprocess.run(
            ["pdftotext", result["output"], "-"],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout
        assert len(text.strip()) > 0

    def test_ocr_medium(self, scanned_pdf):
        result = ocr_pdf(scanned_pdf, lang="eng", overwrite=True)
        text = subprocess.run(
            ["pdftotext", result["output"], "-"],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout
        assert MARKER in text

    def test_ocr_high(self, tmp_path):
        base = _dense_text_pdf(tmp_path)
        scanned = _scan_pdf(tmp_path, base, "ocr_high.pdf", last_page=3, dpi=100)
        result = ocr_pdf(scanned, lang="eng", deskew=True, overwrite=True)
        text = subprocess.run(
            ["pdftotext", result["output"], "-"],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout
        assert MARKER in text


@requires_poppler
class TestLocateAndRedactCoverage:
    def test_locate_low(self, text_pdf):
        result = locate_text(text_pdf, MARKER, pages="2")
        assert result["count"] == 1
        assert [m["page"] for m in result["matches"]] == [2]

    def test_locate_medium(self, text_pdf):
        result = locate_text(text_pdf, MARKER, pages="1,3")
        assert result["count"] == 2
        assert [m["page"] for m in result["matches"]] == [1, 3]

    def test_locate_high(self, text_pdf):
        result = locate_text(text_pdf, MARKER, pages="1-2,2-3")
        assert result["count"] == 3
        assert [m["page"] for m in result["matches"]] == [1, 2, 3]

    def test_redact_text_low(self, text_pdf, tmp_path):
        result = redact_text(text_pdf, queries=["page 2"], output=tmp_path / "r_low.pdf")
        assert result["queries"] == {"page 2": 1}
        assert result["rasterized_pages"] == [2]

    def test_redact_text_medium(self, text_pdf, tmp_path):
        result = redact_text(
            text_pdf,
            queries=["page 1", "page 3"],
            output=tmp_path / "r_med.pdf",
        )
        assert result["queries"] == {"page 1": 1, "page 3": 1}
        assert result["rasterized_pages"] == [1, 3]

    def test_redact_text_high(self, text_pdf, tmp_path):
        result = redact_text(
            text_pdf,
            queries=[MARKER],
            output=tmp_path / "r_high.pdf",
            rasterize_all=True,
        )
        assert result["queries"] == {MARKER: 3}
        assert result["rasterized_pages"] == [1, 2, 3]
        text = subprocess.run(
            ["pdftotext", result["output"], "-"],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout
        assert text.strip() == ""


@requires_poppler
class TestSanitizeCoverage:
    def test_sanitize_low(self, text_pdf, tmp_path):
        dirty = make_dirty_pdf(text_pdf, tmp_path / "dirty_low.pdf", with_annotation=False)
        result = sanitize(dirty, output=tmp_path / "clean_low.pdf")
        with pikepdf.open(result["output"]) as pdf:
            assert "/OpenAction" not in pdf.Root
            assert not list(pdf.docinfo)
            assert not list(pdf.attachments.keys())
        assert {"open_action", "docinfo", "attachments"} <= set(result["removed"])

    def test_sanitize_medium(self, text_pdf, tmp_path):
        dirty = make_dirty_pdf(text_pdf, tmp_path / "dirty_medium.pdf", with_annotation=False)
        result = sanitize(
            dirty,
            strip_metadata=False,
            strip_attachments=False,
            output=tmp_path / "clean_medium.pdf",
        )
        with pikepdf.open(result["output"]) as pdf:
            assert str(pdf.docinfo.get("/Title", "")) == "Secret Project Title"
            assert list(pdf.attachments.keys())
        assert "docinfo" not in result["removed"]

    def test_sanitize_high(self, text_pdf, tmp_path):
        dirty = make_dirty_pdf(
            text_pdf,
            tmp_path / "dirty_high.pdf",
            with_annotation=True,
            attachment_count=2,
        )
        result = sanitize(dirty, strip_annotations=True, output=tmp_path / "clean_high.pdf")
        with pikepdf.open(result["output"]) as pdf:
            assert "/Annots" not in pdf.pages[0]
            assert not list(pdf.attachments.keys())
        assert "annotations" in result["removed"]


@requires_poppler
class TestRedactCoverage:
    def test_redact_low(self, text_pdf, tmp_path):
        result = redact(
            text_pdf,
            regions=[{"page": 1, "x": 40, "y": 60, "w": 480, "h": 40}],
            output=tmp_path / "redact_low.pdf",
        )
        assert result["rasterized_pages"] == [1]
        assert result["regions_applied"] == 1

    def test_redact_medium(self, text_pdf, tmp_path):
        result = redact(
            text_pdf,
            regions=[{"page": 1, "x": 40, "y": 60, "w": 480, "h": 40}],
            rasterize_all=True,
            output=tmp_path / "redact_medium.pdf",
        )
        assert result["rasterized_pages"] == [1, 2, 3]
        assert result["regions_applied"] == 1

    def test_redact_high(self, text_pdf, tmp_path):
        result = redact(
            text_pdf,
            regions=[
                {"page": 1, "x": 40, "y": 60, "w": 480, "h": 40},
                {"page": 3, "x": 40, "y": 60, "w": 480, "h": 40},
            ],
            output=tmp_path / "redact_high.pdf",
        )
        assert result["rasterized_pages"] == [1, 3]
        assert result["regions_applied"] == 2
        assert result["warning"]


@requires_poppler
class TestMetadataAndFormsCoverage:
    def test_edit_metadata_low(self, text_pdf, tmp_path):
        edit_metadata(text_pdf, title="公开标题", author="作者甲", output=tmp_path / "m_low.pdf")
        with pikepdf.open(tmp_path / "m_low.pdf") as pdf:
            assert str(pdf.docinfo.get("/Title", "")) == "公开标题"
            assert str(pdf.docinfo.get("/Author", "")) == "作者甲"

    def test_edit_metadata_medium(self, text_pdf, tmp_path):
        edit_metadata(
            text_pdf,
            subject="主题",
            keywords="a,b,c",
            creator="codex",
            output=tmp_path / "m_medium.pdf",
        )
        with pikepdf.open(tmp_path / "m_medium.pdf") as pdf:
            assert str(pdf.docinfo.get("/Subject", "")) == "主题"
            assert str(pdf.docinfo.get("/Keywords", "")) == "a,b,c"
            with pdf.open_metadata() as meta:
                assert meta["dc:description"] == "主题"
                assert meta["xmp:CreatorTool"] == "codex"

    def test_edit_metadata_high(self, dirty_pdf, tmp_path):
        edit_metadata(dirty_pdf, clear=True, output=tmp_path / "m_high.pdf")
        with pikepdf.open(tmp_path / "m_high.pdf") as pdf:
            assert "/Title" not in pdf.docinfo
            assert "/Author" not in pdf.docinfo
            with pdf.open_metadata() as meta:
                assert "dc:title" not in meta
                assert "dc:creator" not in meta

    def test_fill_form_low(self, form_pdf, tmp_path):
        result = fill_form(
            form_pdf,
            {"fullname": "张三", "email": "zhang@example.com"},
            output=tmp_path / "f_low.pdf",
        )
        assert sorted(result["filled"]) == ["email", "fullname"]
        assert result["missing"] == []

    def test_fill_form_medium(self, text_pdf, tmp_path):
        nested = make_form_pdf(text_pdf, tmp_path / "f_medium.pdf", nested=True)
        result = fill_form(
            nested,
            {"employee.name": "李四", "employee.department": "研发"},
            output=tmp_path / "f_medium_filled.pdf",
        )
        assert sorted(result["filled"]) == ["employee.department", "employee.name"]
        fields = _field_values(result["output"])
        assert fields["employee.name"]["V"] == "李四"
        assert fields["employee.department"]["V"] == "研发"

    def test_fill_form_high(self, text_pdf, tmp_path):
        form = make_form_pdf(text_pdf, tmp_path / "f_high.pdf", checkbox=True)
        result = fill_form(
            form,
            {"agree": True, "notexist": "x"},
            output=tmp_path / "f_high_filled.pdf",
        )
        assert result["filled"] == ["agree"]
        assert result["missing"] == ["notexist"]
        fields = _field_values(result["output"])
        assert fields["agree"]["V"] != "/Off"
        assert fields["agree"]["AS"] != "/Off"


@requires_gs
@requires_poppler
class TestCompressionCoverage:
    def test_compress_low(self, scanned_pdf, tmp_path):
        result = compress_pdf(scanned_pdf, output=tmp_path / "c_low.pdf")
        assert result["quality_used"] == "ebook"
        assert result["target_met"] is None

    def test_compress_medium(self, scanned_pdf, tmp_path):
        result = compress_pdf(scanned_pdf, target_mb=5, output=tmp_path / "c_medium.pdf")
        assert result["target_met"] is True
        assert result["size_after"] > 0

    def test_compress_high(self, scanned_pdf, tmp_path):
        result = compress_pdf(scanned_pdf, target_mb=0.001, output=tmp_path / "c_high.pdf")
        assert result["target_met"] is False
        assert result["quality_used"] in {"ebook", "screen"}


@requires_poppler
@requires_tesseract
class TestBatchOcrCoverage:
    def test_batch_low(self, scanned_pdf, tmp_path):
        result = batch_ocr([scanned_pdf], lang="eng", out_dir=tmp_path, overwrite=True)
        assert result["total"] == 1
        assert result["succeeded"] == 1

    def test_batch_medium(self, text_pdf, scanned_pdf, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        shutil.copy(text_pdf, src / "a.pdf")
        shutil.copy(scanned_pdf, src / "b.pdf")
        out = tmp_path / "out"
        result = batch_ocr(src, lang="eng", out_dir=out, overwrite=True)
        assert result["total"] == 2
        assert result["succeeded"] == 2
        assert (out / "a_ocr.pdf").exists()

    def test_batch_high(self, scanned_pdf, tmp_path, monkeypatch):
        import pdf_toolbox.engine.batch as batch_mod

        calls = {"count": 0}
        real_ocr = batch_mod.ocr_pdf

        def flaky(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("transient")
            return real_ocr(*args, **kwargs)

        monkeypatch.setattr(batch_mod, "ocr_pdf", flaky)
        result = batch_ocr(
            [scanned_pdf],
            lang="eng",
            out_dir=tmp_path,
            overwrite=True,
            max_retries=1,
        )
        assert result["total"] == 1
        assert result["succeeded"] == 1
        assert result["results"][0]["attempts"] == 2


@requires_qpdf
class TestPageOpsCoverage:
    def test_split_low(self, text_pdf, tmp_path):
        result = split_pdf(text_pdf, ranges="1", out_dir=tmp_path)
        assert result["count"] == 1
        assert result["parts"][0]["page_count"] == 1

    def test_split_medium(self, text_pdf, tmp_path):
        result = split_pdf(text_pdf, every_n=2, out_dir=tmp_path)
        assert result["count"] == 2
        assert [part["page_count"] for part in result["parts"]] == [2, 1]

    def test_split_high(self, text_pdf, tmp_path):
        result = split_pdf(text_pdf, ranges="1-2,2-3", out_dir=tmp_path)
        assert result["count"] == 1
        assert result["parts"][0]["page_count"] == 3

    def test_merge_low(self, text_pdf, tmp_path):
        parts = split_pdf(text_pdf, ranges="1,2", out_dir=tmp_path)
        merged = merge_pdfs([p["file"] for p in parts["parts"]], tmp_path / "m_low.pdf")
        assert merged["page_count"] == 2

    def test_merge_medium(self, text_pdf, tmp_path):
        parts = split_pdf(text_pdf, ranges="1-2,3", out_dir=tmp_path)
        merged = merge_pdfs([p["file"] for p in parts["parts"]], tmp_path / "m_medium.pdf")
        assert merged["page_count"] == 3
        assert MARKER in subprocess.run(
            ["pdftotext", merged["output"], "-"],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout

    def test_merge_high(self, text_pdf, tmp_path):
        parts = split_pdf(text_pdf, ranges="1", out_dir=tmp_path)
        out = tmp_path / "exists.pdf"
        out.write_text("x")
        with pytest.raises(FileExistsError):
            merge_pdfs([parts["parts"][0]["file"]], out)

    def test_rotate_low(self, text_pdf, tmp_path):
        result = rotate_pages(text_pdf, angle=90, pages="1", output=tmp_path / "r_low.pdf")
        with pikepdf.open(result["output"]) as pdf:
            assert int(pdf.pages[0].get("/Rotate", 0)) == 90

    def test_rotate_medium(self, text_pdf, tmp_path):
        result = rotate_pages(text_pdf, angle=180, pages="1,3", output=tmp_path / "r_med.pdf")
        with pikepdf.open(result["output"]) as pdf:
            assert int(pdf.pages[0].get("/Rotate", 0)) == 180
            assert int(pdf.pages[1].get("/Rotate", 0)) == 0
            assert int(pdf.pages[2].get("/Rotate", 0)) == 180

    def test_rotate_high(self, text_pdf, tmp_path):
        result = rotate_pages(text_pdf, angle=270, output=tmp_path / "r_high.pdf")
        with pikepdf.open(result["output"]) as pdf:
            assert all(int(page.get("/Rotate", 0)) == 270 for page in pdf.pages)

    def test_rotate_overlap_dedup(self, text_pdf, tmp_path):
        result = rotate_pages(text_pdf, angle=90, pages="1-2,2-3", output=tmp_path / "r_overlap.pdf")
        with pikepdf.open(result["output"]) as pdf:
            assert all(int(page.get("/Rotate", 0)) == 90 for page in pdf.pages)


@requires_qpdf
class TestSecurityCoverage:
    def test_protect_low(self, text_pdf, tmp_path):
        result = protect_pdf(text_pdf, output=tmp_path / "p_low.pdf")
        with pikepdf.open(result["output"]):
            pass

    def test_protect_medium(self, text_pdf, tmp_path):
        result = protect_pdf(
            text_pdf,
            user_password="pw",
            allow_print=False,
            allow_extract=False,
            output=tmp_path / "p_med.pdf",
        )
        assert result["permissions"]["print"] is False
        assert result["permissions"]["extract"] is False
        unlocked = unlock_pdf(result["output"], password="pw", output=tmp_path / "u_med.pdf")
        assert unlocked["decrypted"] is True

    def test_protect_high_wrong_password(self, text_pdf, tmp_path):
        from pdf_toolbox.engine.errors import WrongPasswordError

        result = protect_pdf(text_pdf, user_password="right", output=tmp_path / "p_high.pdf")
        with pytest.raises(WrongPasswordError):
            unlock_pdf(result["output"], password="wrong", output=tmp_path / "u_high.pdf")


@requires_qpdf
class TestRepairAndLinearizeCoverage:
    def test_check_repair_low(self, text_pdf):
        result = check_repair(text_pdf)
        assert result["status"] == "ok"

    def test_check_repair_medium(self, corrupted_pdf, tmp_path):
        result = check_repair(corrupted_pdf, repair=True, output=tmp_path / "fixed.pdf")
        assert "repaired_output" in result
        assert _page_count(result["repaired_output"]) == 3

    def test_check_repair_high(self, text_pdf):
        with pytest.raises(ValueError):
            check_repair(text_pdf, repair=True)

    def test_linearize_low(self, text_pdf, tmp_path):
        result = linearize(text_pdf, output=tmp_path / "lin_low.pdf")
        assert result["linearized"] is True

    def test_linearize_medium(self, scanned_pdf, tmp_path):
        result = linearize(scanned_pdf, output=tmp_path / "lin_med.pdf")
        assert result["linearized"] is True
        assert result["output"].endswith("lin_med.pdf")

    def test_linearize_high(self, text_pdf, tmp_path):
        out = tmp_path / "lin_high.pdf"
        out.write_text("x")
        with pytest.raises(FileExistsError):
            linearize(text_pdf, output=out)
