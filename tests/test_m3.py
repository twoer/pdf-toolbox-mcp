"""check_repair / linearize + batch_ocr：M3 新能力测试。"""

from __future__ import annotations

import subprocess

import pikepdf
import pytest

from conftest import MARKER, requires_poppler, requires_qpdf, requires_tesseract
from pdf_toolbox.engine import batch_ocr, check_repair, linearize


@requires_qpdf
class TestCheckRepair:
    def test_healthy(self, text_pdf):
        result = check_repair(text_pdf)
        assert result["status"] == "ok"
        assert result["recommendation"] is None

    def test_corrupted_detected(self, corrupted_pdf):
        result = check_repair(corrupted_pdf)
        assert result["status"] in ("errors", "warnings")
        assert result["recommendation"] is not None

    def test_repair_rebuilds(self, corrupted_pdf, tmp_path):
        result = check_repair(corrupted_pdf, repair=True, output=tmp_path / "fixed.pdf")
        assert "repaired_output" in result
        with pikepdf.open(result["repaired_output"]) as doc:
            assert len(doc.pages) == 3  # 截断在 60%，三页对象应仍可恢复

    def test_repair_healthy_raises(self, text_pdf):
        with pytest.raises(ValueError):
            check_repair(text_pdf, repair=True)


@requires_qpdf
class TestLinearize:
    def test_linearized(self, text_pdf, tmp_path):
        result = linearize(text_pdf, output=tmp_path / "fast.pdf")
        assert result["linearized"] is True


@requires_poppler
@requires_tesseract
class TestBatchOcr:
    def test_mixed_batch(self, text_pdf, scanned_pdf, tmp_path):
        result = batch_ocr(
            [text_pdf, scanned_pdf], lang="eng", out_dir=tmp_path, overwrite=True
        )
        assert result["total"] == 2
        assert result["succeeded"] == 2
        for entry in result["results"]:
            assert entry["ok"] is True
            assert entry["attempts"] == 1
        # 写回闭环：批量产物之一可搜索
        out = tmp_path / "scanned_ocr.pdf"
        text = subprocess.run(
            ["pdftotext", str(out), "-"],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout
        assert MARKER in text

    def test_failure_isolation(self, text_pdf, tmp_path):
        missing = tmp_path / "missing.pdf"
        result = batch_ocr([text_pdf, missing], lang="eng", overwrite=True)
        assert result["total"] == 2
        assert result["succeeded"] == 1
        assert result["failed"] == 1
        failed_entry = next(r for r in result["results"] if not r["ok"])
        assert failed_entry["error"] == "FileNotFoundError"

    def test_directory_input(self, text_pdf, scanned_pdf, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        import shutil

        shutil.copy(text_pdf, src / "a.pdf")
        shutil.copy(scanned_pdf, src / "b.pdf")
        out = tmp_path / "out"
        result = batch_ocr(src, lang="eng", out_dir=out, overwrite=True)
        assert result["total"] == 2
        assert result["succeeded"] == 2
        assert (out / "a_ocr.pdf").exists()

    def test_empty_input(self, tmp_path):
        with pytest.raises(ValueError):
            batch_ocr([])
