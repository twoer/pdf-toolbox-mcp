"""CLI 三档覆盖：代表性命令的薄壳回归。"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pdf_toolbox.cli import app
from pdf_toolbox.client_install import InstallResult

runner = CliRunner()


class TestCliCoverage:
    def test_version_low(self):
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "0.1.2" in result.stdout

    def test_info_medium(self, text_pdf):
        result = runner.invoke(app, ["info", str(text_pdf)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["pages"] == 3

    def test_split_high(self, text_pdf, tmp_path):
        out_dir = tmp_path / "parts"
        result = runner.invoke(
            app,
            [
                "split",
                str(text_pdf),
                "--ranges",
                "1-2,2-3",
                "--out-dir",
                str(out_dir),
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["count"] == 1
        assert (out_dir / "text_p1-3.pdf").exists()

    def test_client_list(self):
        result = runner.invoke(app, ["client", "list"])
        assert result.exit_code == 0
        assert "universal" in result.output
        assert "claude-desktop" in result.output
        assert "claude-code" in result.output
        assert "zed" in result.output
        assert "cursor" in result.output

    def test_client_show_json(self):
        result = runner.invoke(app, ["client", "show", "claude-desktop", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "claude-desktop"
        assert data["mode"] == "json"
        assert "mcpServers" in data["snippet"]

    def test_client_export(self, tmp_path):
        out_dir = tmp_path / "bundle"
        result = runner.invoke(app, ["client", "export", "--out-dir", str(out_dir), "--client", "cursor"])
        assert result.exit_code == 0
        assert (out_dir / "cursor" / "cursor_mcp.json").exists()
        assert (out_dir / "cursor" / "install-link.txt").exists()
        assert "cursor_mcp.json" in result.output

    def test_client_install(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = runner.invoke(app, ["client", "install", "--client", "cursor", "--scope", "user"])
        assert result.exit_code == 0
        assert "cursor [user] written" in result.output
        assert (tmp_path / ".cursor" / "mcp.json").exists()

    def test_client_install_default(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setattr("pdf_toolbox.client_install._git_toplevel", lambda start=None: tmp_path)
        result = runner.invoke(app, ["client", "install", "--scope", "auto"])
        assert result.exit_code == 0
        assert "universal [project] written" in result.output
        assert (tmp_path / ".mcp.json").exists()

    def test_client_import_claude_desktop(self, monkeypatch):
        result_value = InstallResult(
            client="claude-desktop",
            scope="user",
            status="installed",
            detail="imported",
        )
        monkeypatch.setattr("pdf_toolbox.cli.import_from_claude_desktop", lambda: result_value)
        result = runner.invoke(app, ["client", "import-claude-desktop"])
        assert result.exit_code == 0
        assert "claude-desktop [user] installed" in result.output

    def test_client_import_claude_desktop_failure(self, monkeypatch):
        result_value = InstallResult(
            client="claude-desktop",
            scope="user",
            status="failed",
            detail="boom",
        )
        monkeypatch.setattr("pdf_toolbox.cli.import_from_claude_desktop", lambda: result_value)
        result = runner.invoke(app, ["client", "import-claude-desktop"])
        assert result.exit_code == 1
        assert "claude-desktop [user] failed" in result.output

    def test_client_detect(self):
        result = runner.invoke(app, ["client", "detect", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "clients" in data
        assert "recommended" in data
