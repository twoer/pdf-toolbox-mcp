"""locate_text / redact_text：文本→坐标定位与按内容涂黑。"""

from __future__ import annotations

import subprocess

import pytest

from conftest import MARKER, requires_poppler
from pdf_toolbox.engine import locate_text, redact_text


@requires_poppler
class TestLocateText:
    def test_all_pages(self, text_pdf):
        result = locate_text(text_pdf, MARKER)
        assert result["count"] == 3
        assert [m["page"] for m in result["matches"]] == [1, 2, 3]
        for m in result["matches"]:
            assert m["x"] >= 0 and m["w"] > 0 and m["h"] > 0

    def test_sparse_page_range(self, text_pdf):
        result = locate_text(text_pdf, MARKER, pages="1,3")
        assert result["count"] == 2
        assert [m["page"] for m in result["matches"]] == [1, 3]

    def test_overlap_page_range_dedup(self, text_pdf):
        result = locate_text(text_pdf, MARKER, pages="1-2,2-3")
        assert result["count"] == 3
        assert [m["page"] for m in result["matches"]] == [1, 2, 3]

    def test_cross_word_match(self, text_pdf):
        result = locate_text(text_pdf, "quick brown")
        assert result["count"] == 3
        assert all(m["w"] > 30 for m in result["matches"])  # 跨词联合框更宽

    def test_page_filter(self, text_pdf):
        result = locate_text(text_pdf, "page 2", pages="2")
        assert result["count"] >= 1
        assert all(m["page"] == 2 for m in result["matches"])

    def test_no_match(self, text_pdf):
        assert locate_text(text_pdf, "完全不存在的内容XYZ")["count"] == 0

    def test_empty_query_raises(self, text_pdf):
        with pytest.raises(ValueError):
            locate_text(text_pdf, "   ")

    def test_scanned_needs_ocr_first(self, scanned_pdf):
        # 扫描件无文本层——定位结果为 0（上游应先 is_searchable → ocr_pdf）
        assert locate_text(scanned_pdf, MARKER)["count"] == 0


@requires_poppler
class TestRedactText:
    def test_only_affected_pages_rasterized(self, text_pdf, tmp_path):
        result = redact_text(text_pdf, queries=["page 2"], output=tmp_path / "r.pdf")
        assert result["queries"] == {"page 2": 1}
        assert result["rasterized_pages"] == [2]  # 只有第 2 页被栅格化
        per_page = subprocess.run(
            ["pdftotext", str(result["output"]), "-"],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout.split("\f")
        assert "page 2" not in per_page[1]  # 被涂内容消失
        assert per_page[1].strip() == ""  # 被涂页无文本层
        assert MARKER in per_page[0]  # 第 1 页原样保留
        assert "page 3" in per_page[2]  # 第 3 页原样保留

    def test_multi_query_all_occurrences(self, text_pdf, tmp_path):
        result = redact_text(
            text_pdf, queries=[MARKER, "quick brown"], output=tmp_path / "r.pdf"
        )
        assert result["queries"] == {MARKER: 3, "quick brown": 3}
        assert result["rasterized_pages"] == [1, 2, 3]  # 每页都有命中
        text = subprocess.run(
            ["pdftotext", str(result["output"]), "-"],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout
        assert text.strip() == ""

    def test_no_match_raises(self, text_pdf, tmp_path):
        with pytest.raises(ValueError, match="未找到"):
            redact_text(text_pdf, queries=["不存在XYZ"], output=tmp_path / "r.pdf")

    def test_empty_queries(self, text_pdf, tmp_path):
        with pytest.raises(ValueError):
            redact_text(text_pdf, queries=[], output=tmp_path / "r.pdf")
