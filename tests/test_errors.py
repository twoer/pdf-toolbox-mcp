"""结构化错误契约：PLAN §5 的缺依赖/加密路由/未知异常兜底 + _deps 注入。"""

from __future__ import annotations

import json

import pytest

from conftest import encrypted_pdf, requires_poppler, requires_qpdf, text_pdf  # noqa: F401
from pdf_toolbox.engine.errors import (
    EncryptedPdfError,
    MissingDependencyError,
    WrongPasswordError,
)
from pdf_toolbox.engine.probe import require
from pdf_toolbox.server import mcp


def _call(tool: str, args: dict):
    import asyncio

    from fastmcp import Client

    async def scenario():
        async with Client(mcp) as client:
            result = await client.call_tool(tool, args)
            return json.loads(result.content[0].text)

    return asyncio.run(scenario())


class TestRequire:
    def test_missing_binary(self):
        with pytest.raises(MissingDependencyError) as ei:
            require("definitely_not_a_binary_xyz")
        payload = ei.value.as_dict()
        assert payload["error"] == "missing_dependency"
        assert payload["binary"] == "definitely_not_a_binary_xyz"


class TestGuardContract:
    @requires_poppler
    def test_success_injects_deps(self, text_pdf):  # noqa: F811
        data = _call("tool_pdf_info", {"path": str(text_pdf)})
        assert data["pages"] == 3
        assert "_deps" in data
        assert isinstance(data["_deps"]["level"], int)
        assert isinstance(data["_deps"]["missing"], list)

    def test_file_not_found(self, tmp_path):
        data = _call("tool_pdf_info", {"path": str(tmp_path / "nope.pdf")})
        assert data == {
            "ok": False,
            "error": "file_not_found",
            "message": data["message"],
        } or (data["ok"] is False and data["error"] == "file_not_found")

    def test_encrypted_routes_to_unlock(self, encrypted_pdf):  # noqa: F811
        data = _call("tool_extract_text", {"path": str(encrypted_pdf)})
        assert data["ok"] is False
        assert data["error"] == "encrypted_pdf"
        assert "unlock_pdf" in data["message"]

    @requires_qpdf
    def test_wrong_password_structured(self, encrypted_pdf, tmp_path):  # noqa: F811
        data = _call(
            "tool_unlock_pdf",
            {"path": str(encrypted_pdf), "password": "bad",
             "output": str(tmp_path / "u.pdf")},
        )
        assert data["ok"] is False
        assert data["error"] == "wrong_password"

    def test_missing_dependency_structured(self, text_pdf, tmp_path, monkeypatch):  # noqa: F811
        import pdf_toolbox.engine.pages as pages_mod

        def _boom(*a, **k):
            raise MissingDependencyError(
                "qpdf",
                0,
                {"darwin": "brew install qpdf"},
                unlocks=("split_pdf", "merge_pdfs"),
            )

        monkeypatch.setattr(pages_mod, "require", _boom)
        data = _call(
            "tool_split_pdf",
            {"path": str(text_pdf), "ranges": "1", "out_dir": str(tmp_path)},
        )
        assert data["ok"] is False
        assert data["error"] == "missing_dependency"
        assert data["binary"] == "qpdf"
        assert "brew install qpdf" in data["install"]["darwin"]
        assert data["unlocks"] == ["split_pdf", "merge_pdfs"]

    def test_unknown_exception_still_structured(self, text_pdf, monkeypatch):  # noqa: F811
        import pdf_toolbox.engine.meta as meta_mod

        def _boom(*a, **k):
            raise KeyError("surprise")

        monkeypatch.setattr(meta_mod, "require", _boom)
        data = _call("tool_pdf_info", {"path": str(text_pdf)})
        assert data["ok"] is False
        assert data["error"] == "internal_error"
        assert "KeyError" in data["message"]


class TestErrorCodes:
    def test_distinct_codes(self):
        assert EncryptedPdfError("x").error_code == "encrypted_pdf"
        assert WrongPasswordError("x").error_code == "wrong_password"
