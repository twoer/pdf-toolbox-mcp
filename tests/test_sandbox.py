"""sandbox 单元测试：页范围解析 / 路径校验（无外部依赖）。"""

from __future__ import annotations

import pytest

from pdf_toolbox.engine.sandbox import (
    PageRangeError,
    ensure_pdf,
    flatten_pages,
    merge_overlapping_ranges,
    parse_pages,
)


class TestParsePages:
    def test_single(self):
        assert parse_pages("5") == [(5, 5)]

    def test_range(self):
        assert parse_pages("1-3") == [(1, 3)]

    def test_mixed(self):
        assert parse_pages("1-3,5,7-9") == [(1, 3), (5, 5), (7, 9)]

    def test_spaces(self):
        assert parse_pages(" 1-3 , 5 ") == [(1, 3), (5, 5)]

    def test_open_range_with_max(self):
        assert parse_pages("6-", max_pages=10) == [(6, 10)]

    def test_open_range_without_max_raises(self):
        with pytest.raises(PageRangeError):
            parse_pages("8-")

    def test_zero_raises(self):
        with pytest.raises(PageRangeError):
            parse_pages("0-2")

    def test_descending_raises(self):
        with pytest.raises(PageRangeError):
            parse_pages("5-2")

    def test_out_of_range_raises(self):
        with pytest.raises(PageRangeError):
            parse_pages("1-99", max_pages=3)

    def test_empty_raises(self):
        with pytest.raises(PageRangeError):
            parse_pages(",,,")

    def test_flatten(self):
        assert flatten_pages([(1, 3), (5, 5), (2, 2)]) == [1, 2, 3, 5]

    def test_merge_overlapping_ranges(self):
        assert merge_overlapping_ranges([(1, 2), (2, 3)]) == [(1, 3)]
        assert merge_overlapping_ranges([(1, 2), (3, 3)]) == [(1, 2), (3, 3)]


class TestEnsurePdf:
    def test_ok(self, tmp_path):
        f = tmp_path / "a.pdf"
        f.write_bytes(b"%PDF-1.4")
        assert ensure_pdf(f) == f

    def test_missing_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ensure_pdf(tmp_path / "nope.pdf")

    def test_not_pdf_raises(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("x")
        with pytest.raises(ValueError):
            ensure_pdf(f)
