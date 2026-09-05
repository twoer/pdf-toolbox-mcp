"""split / merge / rotate：页面手术测试（qpdf，L0）。"""

from __future__ import annotations

import subprocess

import pikepdf
import pytest

from conftest import MARKER, requires_qpdf
from pdf_toolbox.engine import merge_pdfs, rotate_pages, split_pdf


def _pages(path) -> int:
    with pikepdf.open(path) as doc:
        return len(doc.pages)


@requires_qpdf
class TestSplit:
    def test_ranges(self, text_pdf, tmp_path):
        result = split_pdf(text_pdf, ranges="1-2,3", out_dir=tmp_path)
        assert result["count"] == 2
        assert [p["page_count"] for p in result["parts"]] == [2, 1]
        assert _pages(result["parts"][0]["file"]) == 2

    def test_every_n(self, text_pdf, tmp_path):
        result = split_pdf(text_pdf, every_n=2, out_dir=tmp_path)
        assert result["count"] == 2  # 3 页 → [1-2] [3]

    def test_mutually_exclusive(self, text_pdf, tmp_path):
        with pytest.raises(ValueError):
            split_pdf(text_pdf, ranges="1", every_n=1, out_dir=tmp_path)

    def test_overwrite_protection(self, text_pdf, tmp_path):
        split_pdf(text_pdf, ranges="1", out_dir=tmp_path)
        with pytest.raises(FileExistsError):
            split_pdf(text_pdf, ranges="1", out_dir=tmp_path)
        split_pdf(text_pdf, ranges="1", out_dir=tmp_path, overwrite=True)


@requires_qpdf
class TestMerge:
    def test_roundtrip(self, text_pdf, tmp_path):
        parts = split_pdf(text_pdf, ranges="1-2,3", out_dir=tmp_path)
        merged = merge_pdfs(
            [p["file"] for p in parts["parts"]], tmp_path / "merged.pdf"
        )
        assert merged["page_count"] == 3
        text = subprocess.run(
            ["pdftotext", merged["output"], "-"],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout
        assert MARKER in text

    def test_empty_paths(self, tmp_path):
        with pytest.raises(ValueError):
            merge_pdfs([], tmp_path / "x.pdf")


@requires_qpdf
class TestRotate:
    def test_rotation_90(self, text_pdf, tmp_path):
        result = rotate_pages(text_pdf, angle=90, pages="1", output=tmp_path / "r.pdf")
        with pikepdf.open(result["output"]) as doc:
            assert int(doc.pages[0].get("/Rotate", 0)) == 90
            assert int(doc.pages[1].get("/Rotate", 0)) == 0  # 未指定页不动

    def test_bad_angle(self, text_pdf, tmp_path):
        with pytest.raises(ValueError):
            rotate_pages(text_pdf, angle=45, output=tmp_path / "r.pdf")
