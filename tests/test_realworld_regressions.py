"""真实世界回归：扫描件、加密件、坏件、批处理、多页报告。"""

from __future__ import annotations

import shutil
import subprocess

import pikepdf
import pytest

from conftest import MARKER, requires_gs, requires_poppler, requires_qpdf, requires_tesseract
from pdf_toolbox.engine import (
    batch_ocr,
    check_repair,
    compress_pdf,
    fill_form,
    is_searchable,
    ocr_pdf,
    sanitize,
    unlock_pdf,
)

pytestmark = pytest.mark.realworld


def _pdftotext(path) -> str:
    return subprocess.run(
        ["pdftotext", str(path), "-"],
        capture_output=True,
        text=True,
        check=True,
        timeout=90,
    ).stdout


@requires_poppler
@requires_tesseract
class TestScanRoundtrip:
    def test_low_res_scan_becomes_searchable(self, low_res_scanned_pdf, tmp_path):
        before = is_searchable(low_res_scanned_pdf)
        assert before["searchable"] is False
        assert before["recommendation"] == "ocr_pdf"

        result = ocr_pdf(low_res_scanned_pdf, lang="eng", output=tmp_path / "scan_ocr.pdf")
        text = _pdftotext(result["output"])

        assert result["lang"] == "eng"
        assert result["lang_fallback"] is False
        assert "TOOLBOX" in text.upper()
        assert "7734" in text


@requires_qpdf
@requires_poppler
class TestUnlockAndRepair:
    def test_encrypted_contract_unlocks(self, encrypted_pdf, tmp_path):
        result = unlock_pdf(encrypted_pdf, password="pdf-toolbox-test", output=tmp_path / "unlocked.pdf")
        text = _pdftotext(result["output"])

        assert result["decrypted"] is True
        assert result["pages"] == 3
        assert MARKER in text

    def test_corrupted_report_repairs(self, corrupted_pdf, tmp_path):
        result = check_repair(corrupted_pdf, repair=True, output=tmp_path / "fixed.pdf")
        text = _pdftotext(result["repaired_output"])

        assert result["status"] in {"ok", "warnings", "errors"}
        assert MARKER in text


@requires_poppler
@requires_tesseract
class TestBatchWorkflow:
    def test_mixed_directory_ocr(self, report_pdf, report_scanned_pdf, tmp_path):
        src = tmp_path / "src"
        out = tmp_path / "out"
        src.mkdir()
        shutil.copy(report_pdf, src / "report.pdf")
        shutil.copy(report_scanned_pdf, src / "report_scan.pdf")

        result = batch_ocr(src, lang="eng", out_dir=out, overwrite=True)

        assert result["total"] == 2
        assert result["succeeded"] == 2
        assert (out / "report_ocr.pdf").exists()
        assert (out / "report_scan_ocr.pdf").exists()
        assert MARKER in _pdftotext(out / "report_scan_ocr.pdf")
        assert MARKER in _pdftotext(out / "report_ocr.pdf")


@requires_gs
@requires_poppler
class TestCompressionWorkflow:
    def test_large_report_compresses(self, report_scanned_pdf, tmp_path):
        compressed = compress_pdf(report_scanned_pdf, target_mb=1, output=tmp_path / "report.pdf")
        with pikepdf.open(compressed["output"]) as pdf:
            assert len(pdf.pages) == 12
        assert compressed["size_after"] > 0
        assert compressed["quality_used"] in {"printer", "ebook", "screen"}


@requires_poppler
class TestPublishWorkflow:
    def test_sanitize_dirty_packet(self, dirty_pdf, tmp_path):
        clean = sanitize(dirty_pdf, output=tmp_path / "clean.pdf")
        with pikepdf.open(clean["output"]) as pdf:
            assert not list(pdf.docinfo)
            assert not list(pdf.attachments.keys())
            assert "/OpenAction" not in pdf.Root
        assert MARKER in _pdftotext(clean["output"])


class TestForms:
    def test_fill_form_packet(self, form_pdf, tmp_path):
        result = fill_form(
            form_pdf,
            {"fullname": "张三", "email": "zhang@example.com"},
            output=tmp_path / "filled.pdf",
        )
        with pikepdf.open(result["output"]) as pdf:
            values = {str(field.T): str(field.V) for field in pdf.Root.AcroForm.Fields}

        assert result["missing"] == []
        assert values["fullname"] == "张三"
        assert values["email"] == "zhang@example.com"
