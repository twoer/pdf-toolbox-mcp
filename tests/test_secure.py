"""protect / unlock：加密解锁往返测试（qpdf，L0）——差异化刚需的回归保障。"""

from __future__ import annotations

import subprocess

import pikepdf
import pytest

from conftest import MARKER, requires_qpdf
from pdf_toolbox.engine import protect_pdf, unlock_pdf


@requires_qpdf
class TestProtectUnlock:
    def test_roundtrip(self, text_pdf, tmp_path):
        locked = protect_pdf(
            text_pdf,
            user_password="secret123",
            output=tmp_path / "locked.pdf",
        )
        assert locked["algorithm"] == "AES-256"

        # 空密码打不开
        with pytest.raises(pikepdf.PasswordError):
            pikepdf.open(locked["output"])

        # user 密码即可解锁（与 ODA 的过严策略形成差异）
        unlocked = unlock_pdf(locked["output"], password="secret123")
        assert unlocked["decrypted"] is True
        assert unlocked["pages"] == 3

        with pikepdf.open(unlocked["output"]) as doc:  # 产物已解密
            assert len(doc.pages) == 3
        text = subprocess.run(
            ["pdftotext", unlocked["output"], "-"],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout
        assert MARKER in text

    def test_wrong_password(self, text_pdf, tmp_path):
        from pdf_toolbox.engine.errors import WrongPasswordError

        locked = protect_pdf(text_pdf, user_password="right", output=tmp_path / "l.pdf")
        with pytest.raises(WrongPasswordError):
            unlock_pdf(locked["output"], password="wrong", output=tmp_path / "u.pdf")

    def test_permissions_flags(self, text_pdf, tmp_path):
        locked = protect_pdf(
            text_pdf,
            user_password="pw",
            allow_print=False,
            allow_extract=False,
            output=tmp_path / "perm.pdf",
        )
        assert locked["permissions"]["print"] is False
        out = subprocess.run(
            ["pdfinfo", "-upw", "pw", locked["output"]],
            capture_output=True, text=True, timeout=30,
        ).stdout
        assert "print:no" in out.replace(" ", "")
        assert "copy:no" in out.replace(" ", "")

    def test_empty_user_password_is_restrictions_only(self, text_pdf, tmp_path):
        # user 密码为空 = 打开无需密码（仅权限限制）——分发场景
        locked = protect_pdf(text_pdf, output=tmp_path / "ro.pdf")
        with pikepdf.open(locked["output"]):  # 无密码可开
            pass

    def test_unlock_fixture(self, encrypted_pdf, tmp_path):
        # conftest 的强加密样本（user+owner 双密码）——user 密码即解锁
        result = unlock_pdf(encrypted_pdf, password="pdf-toolbox-test", output=tmp_path / "u.pdf")
        assert result["pages"] == 3
