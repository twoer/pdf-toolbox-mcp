"""extract_images / extract_attachments：素材抽取。"""

from __future__ import annotations

from conftest import requires_poppler
from pdf_toolbox.engine import extract_attachments, extract_images


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
