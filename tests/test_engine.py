"""engine 功能测试：按依赖分级 skip（poppler=L1，tesseract=L2）。"""

from __future__ import annotations

import subprocess

import pytest

from conftest import MARKER, requires_poppler, requires_tesseract
from pdf_toolbox.engine import extract_text, ocr_pdf, pdf_info, render_pages


@requires_poppler
class TestPdfInfo:
    def test_text_pdf(self, text_pdf):
        info = pdf_info(text_pdf)
        assert info["pages"] == 3
        assert info["encrypted"] is False
        assert info["file_size_bytes"] > 0

    def test_encrypted_pdf(self, encrypted_pdf):
        # info 是智能路由入口：加密件应返回 encrypted=True 而不是抛错
        info = pdf_info(encrypted_pdf)
        assert info["encrypted"] is True
        assert info["pages"] is None
        assert "密码" in info["note"]


@requires_poppler
class TestExtractText:
    def test_marker(self, text_pdf):
        result = extract_text(text_pdf)
        assert MARKER in result["text"]
        assert result["total_chars"] > 100

    def test_page_range(self, text_pdf):
        result = extract_text(text_pdf, pages="1")
        assert "page 1" in result["text"]
        assert "page 2" not in result["text"]

    def test_multi_range_exact(self, text_pdf):
        # 多区间精确提取：1,3 不得包含第 2 页内容（还债验证）
        result = extract_text(text_pdf, pages="1,3")
        assert "page 1" in result["text"]
        assert "page 3" in result["text"]
        assert "page 2" not in result["text"]

    def test_range_overlap_dedup(self, text_pdf):
        result = extract_text(text_pdf, pages="1-2,2-3")
        assert result["text"].count("Sample Page 2") == 1

    def test_per_page(self, text_pdf):
        result = extract_text(text_pdf, per_page=True)
        assert set(result["per_page"]) == {1, 2, 3}
        assert "page 3" in result["per_page"][3]

    def test_scanned_has_no_text(self, scanned_pdf):
        result = extract_text(scanned_pdf)
        assert len(result["text"].strip()) == 0  # 智能路由的判断依据

    def test_encrypted_raises(self, encrypted_pdf):
        from pdf_toolbox.engine.errors import EncryptedPdfError

        with pytest.raises(EncryptedPdfError):
            extract_text(encrypted_pdf)


@requires_poppler
class TestRender:
    def test_multi_range(self, text_pdf, tmp_path):
        result = render_pages(text_pdf, pages="1,3", dpi=100, out_dir=tmp_path)
        assert result["count"] == 2
        assert [img["page"] for img in result["images"]] == [1, 3]  # 页号（还债验证）
        for img in result["images"]:
            assert img["size_bytes"] > 0

    def test_dpi_clamped(self, text_pdf, tmp_path):
        result = render_pages(text_pdf, pages="1", dpi=9999, out_dir=tmp_path)
        assert result["dpi"] == 300

    def test_out_of_range(self, text_pdf, tmp_path):
        from pdf_toolbox.engine.sandbox import PageRangeError

        with pytest.raises(PageRangeError):
            render_pages(text_pdf, pages="1-99", out_dir=tmp_path)


@requires_poppler
@requires_tesseract
class TestOcrWriteBack:
    """差异化核心：OCR 写回后产物必须有可搜索文本层。"""

    def test_write_back_roundtrip(self, scanned_pdf):
        result = ocr_pdf(scanned_pdf, lang="eng", overwrite=True)
        text = subprocess.run(
            ["pdftotext", result["output"], "-"],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout
        assert MARKER in text

    def test_skip_text_on_text_pdf(self, text_pdf):
        # 已有文本层的输入：skip_text 默认跳过，产物仍可提取
        result = ocr_pdf(text_pdf, lang="eng")
        text = subprocess.run(
            ["pdftotext", result["output"], "-"],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout
        assert MARKER in text

    def test_overwrite_protection(self, scanned_pdf, tmp_path):
        out = tmp_path / "dup.pdf"
        out.write_bytes(b"x")
        with pytest.raises(FileExistsError):
            ocr_pdf(scanned_pdf, lang="eng", output=out)

    def test_missing_input(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ocr_pdf(tmp_path / "nope.pdf")


class TestLangResolution:
    """默认语言缺包自动降级、显式语言缺包报错（还债验证）。"""

    def test_explicit_missing_lang_raises(self):
        from pdf_toolbox.engine.ocr import resolve_lang
        from pdf_toolbox.engine.probe import tess_langs

        if not tess_langs():
            pytest.skip("无 tesseract")
        with pytest.raises(ValueError, match="语言包"):
            resolve_lang("klingon_lat")

    def test_default_falls_back(self):
        from pdf_toolbox.engine.ocr import DEFAULT_LANG, resolve_lang
        from pdf_toolbox.engine.probe import tess_langs

        avail = tess_langs()
        if not avail:
            pytest.skip("无 tesseract")
        if all(code in avail for code in DEFAULT_LANG.split("+")):
            pytest.skip(f"本机语言齐备（{sorted(avail)}），无降级路径")
        lang, fell_back = resolve_lang(None)
        assert fell_back is True
        assert all(code in avail for code in lang.split("+"))
