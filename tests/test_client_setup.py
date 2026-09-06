"""客户端接入片段测试。"""

from __future__ import annotations

import json

from pdf_toolbox.client_setup import (
    build_client_setup,
    export_client_bundle,
    list_client_setups,
    supported_client_names,
)


class TestClientSetup:
    def test_supported_clients(self):
        assert supported_client_names() == (
            "universal",
            "claude-desktop",
            "claude-code",
            "zed",
            "cursor",
            "generic-json",
            "chatgpt",
        )

    def test_list_client_setups(self):
        setups = list_client_setups()
        names = [setup.name for setup in setups]
        assert names == list(supported_client_names())

    def test_claude_desktop_json(self):
        setup = build_client_setup("claude-desktop")
        payload = json.loads(setup.snippet)
        assert setup.display_name == "Claude Desktop"
        assert payload["mcpServers"]["pdf-toolbox"]["command"] == "uvx"
        assert payload["mcpServers"]["pdf-toolbox"]["args"] == [
            "--from",
            "git+https://github.com/twoer/pdf-toolbox-mcp",
            "pdf-toolbox-mcp",
        ]

    def test_universal_json(self):
        setup = build_client_setup("universal")
        payload = json.loads(setup.snippet)
        assert setup.export_filename == ".mcp.json"
        assert payload["mcpServers"]["pdf-toolbox"]["command"] == "uvx"

    def test_claude_code_command(self):
        setup = build_client_setup("claude-code")
        assert setup.mode == "command"
        assert setup.snippet.startswith("claude mcp add pdf-toolbox")
        assert "uvx --from git+https://github.com/twoer/pdf-toolbox-mcp pdf-toolbox-mcp" in setup.snippet

    def test_zed_json(self):
        setup = build_client_setup("zed")
        payload = json.loads(setup.snippet)
        assert payload["context_servers"]["pdf-toolbox"]["command"] == "uvx"
        assert payload["context_servers"]["pdf-toolbox"]["env"] == {}

    def test_cursor_json_and_link(self):
        setup = build_client_setup("cursor")
        payload = json.loads(setup.snippet)
        assert payload["mcpServers"]["pdf-toolbox"]["command"] == "uvx"
        assert setup.install_link.startswith("cursor://anysphere.cursor-deeplink/mcp/install?")
        assert "name=pdf-toolbox" in setup.install_link
        assert "config=" in setup.install_link

    def test_chatgpt_is_manual(self):
        setup = build_client_setup("chatgpt")
        assert setup.mode == "manual"
        assert setup.snippet is None
        assert "remote MCP" in setup.summary

    def test_export_client_bundle(self, tmp_path):
        written = export_client_bundle(tmp_path, clients=["claude-desktop", "cursor"], overwrite=False)
        assert (tmp_path / "claude-desktop" / "claude_desktop_config.json").exists()
        assert (tmp_path / "cursor" / "cursor_mcp.json").exists()
        assert (tmp_path / "cursor" / "install-link.txt").exists()
        assert len(written) == 3
