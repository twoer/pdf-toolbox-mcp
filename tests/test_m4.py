"""M4（P3 高级）测试：sanitize / redact / fill_form / edit_metadata / compress_pdf。

redact 安全标准（PLAN M4 完成标准）：涂黑后不可提取被涂内容。
"""

from __future__ import annotations

import shutil
import subprocess
from typing import ClassVar

import pikepdf
import pytest

from conftest import MARKER, requires_gs, requires_poppler
from pdf_toolbox.engine import (
    compress_pdf,
    edit_metadata,
    fill_form,
    redact,
    sanitize,
)


class TestSanitize:
    def test_strips_everything(self, dirty_pdf, tmp_path):
        result = sanitize(dirty_pdf, output=tmp_path / "clean.pdf")
        with pikepdf.open(result["output"]) as pdf:
            assert not list(pdf.docinfo)  # 元数据清空
            assert "/OpenAction" not in pdf.Root  # 动作移除
            assert not list(pdf.attachments.keys())  # 附件移除
        removed = set(result["removed"])
        assert {"open_action", "docinfo", "attachments"} <= removed

    def test_content_intact(self, dirty_pdf, tmp_path):
        # 脱敏不动正文——标记串仍可提取
        sanitize(dirty_pdf, output=tmp_path / "clean.pdf")
        text = subprocess.run(
            ["pdftotext", str(tmp_path / "clean.pdf"), "-"],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout
        assert MARKER in text

    def test_selective(self, dirty_pdf, tmp_path):
        result = sanitize(
            dirty_pdf, strip_metadata=False, strip_attachments=False,
            output=tmp_path / "partial.pdf",
        )
        with pikepdf.open(result["output"]) as pdf:
            assert str(pdf.docinfo.get("/Title", "")) == "Secret Project Title"
            assert list(pdf.attachments.keys())
        assert "docinfo" not in result["removed"]


@requires_poppler
class TestRedact:
    """真涂黑（选择性光栅化）：被涂页无任何文本，其余页文本层保留。"""

    REGIONS: ClassVar = [{"page": 1, "x": 40, "y": 60, "w": 480, "h": 40}]

    def test_marker_unrecoverable_others_intact(self, text_pdf, tmp_path):
        result = redact(text_pdf, regions=self.REGIONS, output=tmp_path / "r.pdf")
        assert result["regions_applied"] == 1
        assert result["rasterized_pages"] == [1]
        per_page = subprocess.run(
            ["pdftotext", str(result["output"]), "-"],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout.split("\f")
        # 标记串每页都有：第 1 页必须被涂掉，第 2/3 页按设计保留
        assert MARKER not in per_page[0]
        assert per_page[0].strip() == ""  # 被涂页无文本层
        assert MARKER in per_page[1]  # 其余页原样保留
        assert "page 3" in per_page[2]

    def test_rasterize_all(self, text_pdf, tmp_path):
        result = redact(text_pdf, regions=self.REGIONS, rasterize_all=True,
                        output=tmp_path / "r.pdf")
        assert result["rasterized_pages"] == [1, 2, 3]
        text = subprocess.run(
            ["pdftotext", str(result["output"]), "-"],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout
        assert text.strip() == ""

    def test_black_box_rendered(self, text_pdf, tmp_path):
        out = tmp_path / "r.pdf"
        redact(text_pdf, regions=self.REGIONS, output=out)
        png = tmp_path / "check"
        subprocess.run(
            ["pdftoppm", "-png", "-r", "72", "-f", "1", "-l", "1", str(out), str(png)],
            check=True, capture_output=True, timeout=60,
        )
        from PIL import Image

        img = Image.open(next(tmp_path.glob("check-*.png")))
        # 区域中心（x=40+480/2=280, y=60+40/2=80 pt → 72dpi 即像素值）必须是黑色
        r, g, b = img.getpixel((280, 80))[:3]
        assert r + g + b < 60

    def test_invalid_page(self, text_pdf, tmp_path):
        with pytest.raises(ValueError):
            redact(text_pdf, regions=[{"page": 99, "x": 0, "y": 0, "w": 10, "h": 10}],
                   output=tmp_path / "r.pdf")

    def test_invalid_geometry(self, text_pdf, tmp_path):
        with pytest.raises(ValueError):
            redact(text_pdf, regions=[{"page": 1, "x": 0, "y": 0, "w": -5, "h": 10}],
                   output=tmp_path / "r.pdf")


class TestFillForm:
    def test_fill_flat_fields(self, form_pdf, tmp_path):
        result = fill_form(
            form_pdf,
            {"fullname": "张三", "email": "zhang@example.com"},
            output=tmp_path / "filled.pdf",
        )
        assert sorted(result["filled"]) == ["email", "fullname"]
        assert result["missing"] == []
        with pikepdf.open(result["output"]) as pdf:
            values = {
                str(f.T): str(f.V)
                for f in pdf.Root.AcroForm.Fields
            }
        assert values["fullname"] == "张三"
        assert values["email"] == "zhang@example.com"

    def test_missing_field_reported(self, form_pdf, tmp_path):
        result = fill_form(form_pdf, {"notexist": "x"}, output=tmp_path / "f.pdf")
        assert result["filled"] == []
        assert result["missing"] == ["notexist"]

    def test_no_form_raises(self, text_pdf, tmp_path):
        with pytest.raises(ValueError, match="AcroForm"):
            fill_form(text_pdf, {"a": "b"}, output=tmp_path / "f.pdf")


class TestEditMetadata:
    def test_set_and_read(self, text_pdf, tmp_path):
        edit_metadata(text_pdf, title="公开标题", author="作者甲",
                      output=tmp_path / "m.pdf")
        # 用 pikepdf 断言而非 pdfinfo 文本输出——Windows 控制台码页会把 UTF-8 标题打成乱码
        with pikepdf.open(tmp_path / "m.pdf") as pdf:
            assert str(pdf.docinfo.get("/Title", "")) == "公开标题"
            assert str(pdf.docinfo.get("/Author", "")) == "作者甲"

    def test_clear(self, dirty_pdf, tmp_path):
        edit_metadata(dirty_pdf, clear=True, output=tmp_path / "c.pdf")
        with pikepdf.open(tmp_path / "c.pdf") as pdf:
            keys = [str(k) for k in pdf.docinfo]
        # pikepdf 保存时会自动补 /Producer（标识写入库，非敏感）——敏感字段必须已清
        assert "/Title" not in keys
        assert "/Author" not in keys


@requires_gs
@requires_poppler
class TestCompress:
    """gs 语义测试（不硬性断言压缩率，跨版本图像行为不稳）。"""

    def test_basic(self, scanned_pdf, tmp_path):
        shutil.copy(scanned_pdf, tmp_path / "s.pdf")
        result = compress_pdf(tmp_path / "s.pdf", output=tmp_path / "c.pdf")
        assert result["quality_used"] == "ebook"
        assert result["size_after"] > 0
        assert result["target_met"] is None
        # 产物完整可读
        with pikepdf.open(result["output"]) as pdf:
            assert len(pdf.pages) == 2

    def test_target_met_generous(self, scanned_pdf, tmp_path):
        shutil.copy(scanned_pdf, tmp_path / "s.pdf")
        result = compress_pdf(tmp_path / "s.pdf", target_mb=5, output=tmp_path / "c.pdf")
        assert result["target_met"] is True

    def test_bad_quality(self, scanned_pdf, tmp_path):
        with pytest.raises(ValueError):
            compress_pdf(scanned_pdf, quality="ultra", output=tmp_path / "c.pdf")
