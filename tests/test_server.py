"""MCP server 契约测试：FastMCP in-memory client（M1 起持续扩展为全工具契约）。"""

from __future__ import annotations

import asyncio
import json

from conftest import requires_poppler
from pdf_toolbox.server import mcp

EXPECTED_TOOLS = {
    "tool_pdf_info",
    "tool_extract_text",
    "tool_ocr_pdf",
    "tool_render_pages",
    "tool_unlock_pdf",
    "tool_split_pdf",
    "tool_merge_pdfs",
    "tool_rotate_pages",
    "tool_protect_pdf",
    "tool_is_searchable",
    "tool_list_fonts",
    "tool_extract_images",
    "tool_extract_attachments",
    "tool_check_repair",
    "tool_linearize",
    "tool_batch_ocr",
    "tool_sanitize",
    "tool_redact",
    "tool_redact_text",
    "tool_locate_text",
    "tool_fill_form",
    "tool_edit_metadata",
    "tool_compress_pdf",
    "tool_dependency_status",
}


def _run(coro):
    return asyncio.run(coro)


class TestContract:
    def test_tool_registry(self):
        async def scenario():
            async with __import__("fastmcp").Client(mcp) as client:
                tools = await client.list_tools()
                return {t.name for t in tools}

        assert _run(scenario()) >= EXPECTED_TOOLS

    @requires_poppler
    def test_pdf_info_call(self, text_pdf):
        async def scenario():
            async with __import__("fastmcp").Client(mcp) as client:
                result = await client.call_tool("tool_pdf_info", {"path": str(text_pdf)})
                return json.loads(result.content[0].text)

        data = _run(scenario())
        assert data["pages"] == 3
        assert data["encrypted"] is False

    @requires_poppler
    def test_extract_text_call(self, text_pdf):
        async def scenario():
            async with __import__("fastmcp").Client(mcp) as client:
                result = await client.call_tool(
                    "tool_extract_text", {"path": str(text_pdf), "pages": "1"}
                )
                return json.loads(result.content[0].text)

        data = _run(scenario())
        assert "Sample Page 1" in data["text"]

    def test_dependency_status_call(self):
        async def scenario():
            async with __import__("fastmcp").Client(mcp) as client:
                result = await client.call_tool("tool_dependency_status", {})
                return json.loads(result.content[0].text)

        deps = _run(scenario())
        names = {d["name"] for d in deps}
        assert names == {"qpdf", "pdfinfo", "tesseract", "gs"}
