"""extract_images / extract_attachments：素材抽取。"""

from __future__ import annotations

from PIL import Image, ImageDraw

from conftest import make_dirty_pdf, requires_poppler
from pdf_toolbox.engine import extract_attachments, extract_images


def _make_image_pdf(out):
    from fpdf import FPDF

    canvas = Image.new("RGB", (160, 96), "white")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((16, 16, 144, 80), fill="navy")
    draw.text((32, 36), "img", fill="white")

    png = out.with_suffix(".png")
    canvas.save(png)

    pdf = FPDF()
    for _ in range(3):
        pdf.add_page()
        pdf.image(str(png), x=20, y=24, w=50)
    pdf.output(str(out))
    png.unlink()


@requires_poppler
class TestExtractImages:
    def test_inventory(self, scanned_pdf):
        # scanned.pdf 是整页图片 PDF → 每页一张内嵌图
        result = extract_images(scanned_pdf, list_only=True)
        assert result["count"] == 2
        assert all(i["page"] in (1, 2) for i in result["inventory"])

    def test_extraction(self, scanned_pdf, tmp_path):
        result = extract_images(scanned_pdf, out_dir=tmp_path)
        assert result["count"] == 2
        for img in result["images"]:
            assert img["size_bytes"] > 0
            assert img["page"] in (1, 2)

    def test_sparse_page_range(self, tmp_path):
        pdf = tmp_path / "sparse.pdf"
        _make_image_pdf(pdf)

        inventory = extract_images(pdf, pages="1,3", list_only=True)
        assert inventory["count"] == 2
        assert [item["page"] for item in inventory["inventory"]] == [1, 3]

        result = extract_images(pdf, pages="1,3", out_dir=tmp_path)
        assert result["count"] == 2
        assert [img["page"] for img in result["images"]] == [1, 3]

    def test_overlap_page_range_dedup(self, tmp_path):
        pdf = tmp_path / "overlap.pdf"
        _make_image_pdf(pdf)

        result = extract_images(pdf, pages="1-2,2-3", out_dir=tmp_path)
        assert result["count"] == 3
        assert [img["page"] for img in result["images"]] == [1, 2, 3]


@requires_poppler
class TestExtractAttachments:
    def test_roundtrip(self, attached_pdf, tmp_path):
        result = extract_attachments(attached_pdf, out_dir=tmp_path)
        assert result["count"] == 1
        assert result["attachments"][0]["name"] == "note.txt"
        saved = tmp_path / "note.txt"
        assert saved.read_bytes() == b"PDF-TOOLBOX-ATTACH-TEST"

    def test_no_attachments(self, text_pdf):
        result = extract_attachments(text_pdf)
        assert result["count"] == 0
        assert result["saved"] == []

    def test_multiple_attachments(self, text_pdf, tmp_path):
        dirty = make_dirty_pdf(
            text_pdf,
            tmp_path / "multi_attach.pdf",
            with_annotation=False,
            attachment_count=2,
        )
        result = extract_attachments(dirty, out_dir=tmp_path)
        assert result["count"] == 2
        assert {att["name"] for att in result["attachments"]} == {
            "hidden-0.txt",
            "hidden-1.txt",
        }
