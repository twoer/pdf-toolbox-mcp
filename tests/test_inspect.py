"""is_searchable / list_fonts：智能路由与字体体检。"""

from __future__ import annotations

from conftest import requires_poppler
from pdf_toolbox.engine import is_searchable, list_fonts


@requires_poppler
class TestIsSearchable:
    def test_text_pdf(self, text_pdf):
        result = is_searchable(text_pdf)
        assert result["searchable"] is True
        assert result["recommendation"] == "extract_text"
        assert result["chars_per_page"] > 50

    def test_scanned_pdf(self, scanned_pdf):
        result = is_searchable(scanned_pdf)
        assert result["searchable"] is False
        assert result["recommendation"] == "ocr_pdf"


@requires_poppler
class TestListFonts:
    def test_non_embedded_warning(self, text_pdf):
        # fpdf2 的 Helvetica 属标准 14 字体，不嵌入——正好验证体检逻辑
        result = list_fonts(text_pdf)
        assert result["count"] >= 1
        assert result["non_embedded_count"] >= 1
        assert "未嵌入" in result["warning"]

    def test_font_fields(self, text_pdf):
        font = list_fonts(text_pdf)["fonts"][0]
        assert {"name", "type", "encoding", "embedded", "subset"} <= set(font)
