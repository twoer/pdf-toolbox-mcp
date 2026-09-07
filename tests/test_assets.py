"""extract_images / extract_attachments：素材抽取。"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from conftest import make_dirty_pdf, requires_poppler
from pdf_toolbox.engine import extract_attachments, extract_images
from pdf_toolbox.engine.sandbox import PageRangeError


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

    def test_extraction_does_not_overwrite_by_default(self, scanned_pdf, tmp_path):
        extract_images(scanned_pdf, out_dir=tmp_path)
        with pytest.raises(FileExistsError):
            extract_images(scanned_pdf, out_dir=tmp_path)
        result = extract_images(scanned_pdf, out_dir=tmp_path, overwrite=True)
        assert result["count"] == 2

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

    def test_page_range_upper_bound_is_validated(self, tmp_path):
        pdf = tmp_path / "range.pdf"
        _make_image_pdf(pdf)
        with pytest.raises(PageRangeError):
            extract_images(pdf, pages="1-99", list_only=True)


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
        result = extract_attachments(dirty, out_dir=tmp_path, overwrite=True)
        assert result["count"] == 2
        assert {att["name"] for att in result["attachments"]} == {
            "hidden-0.txt",
            "hidden-1.txt",
        }

    def test_write_probe_does_not_delete_existing_file(self, attached_pdf, tmp_path):
        marker = tmp_path / ".pdfdetach-write-check"
        marker.write_text("keep me", encoding="utf-8")
        extract_attachments(attached_pdf, out_dir=tmp_path)
        assert marker.read_text(encoding="utf-8") == "keep me"

    def test_attachment_does_not_overwrite_by_default(self, attached_pdf, tmp_path):
        extract_attachments(attached_pdf, out_dir=tmp_path)
        with pytest.raises(FileExistsError):
            extract_attachments(attached_pdf, out_dir=tmp_path)
        result = extract_attachments(attached_pdf, out_dir=tmp_path, overwrite=True)
        assert result["count"] == 1

    def _attach_with_names(self, base_pdf: Path, out: Path, names: list[str]) -> Path:
        """低层构造附件名完全受控的 PDF（含路径分隔符、重名等非常规形态）。"""
        import pikepdf

        with pikepdf.open(base_pdf) as pdf:
            flat = []
            for idx, name in enumerate(names):
                payload = out.with_name(f"payload-{idx}.txt")
                payload.write_text(f"content-{idx}", encoding="utf-8")
                spec = pikepdf.AttachedFileSpec.from_filepath(pdf, payload)
                spec.obj.F = pikepdf.String(name)
                spec.obj.UF = pikepdf.String(name)
                flat.extend([pikepdf.String(name), spec.obj])
            pdf.Root.Names = pikepdf.Dictionary(
                EmbeddedFiles=pikepdf.Dictionary(Names=pikepdf.Array(flat))
            )
            pdf.save(out)
        return out

    def test_duplicate_names_are_rejected(self, text_pdf, tmp_path):
        dup = self._attach_with_names(
            text_pdf, tmp_path / "dup.pdf", ["readme.txt", "readme.txt"]
        )
        with pytest.raises(ValueError, match=r"同名附件: readme\.txt"):
            extract_attachments(dup, out_dir=tmp_path / "fresh")
        assert not (tmp_path / "fresh").exists()

    def test_attachment_name_with_path_is_rejected(self, text_pdf, tmp_path):
        subpath = self._attach_with_names(
            text_pdf, tmp_path / "subpath.pdf", ["../escape.txt"]
        )
        with pytest.raises(ValueError, match="附件名含路径"):
            extract_attachments(subpath, out_dir=tmp_path / "fresh")
        assert not (tmp_path / "fresh").exists()
