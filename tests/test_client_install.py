"""客户端半自动安装测试。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pdf_toolbox.client_install import (
    default_install_target,
    detect_client_environment,
    import_from_claude_desktop,
    install_client,
)


class TestClientInstall:
    def test_install_cursor_user(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = install_client("cursor", scope="user", overwrite=False)
        path = tmp_path / ".cursor" / "mcp.json"
        assert result.status == "written"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["mcpServers"]["pdf-toolbox"]["command"] == "uvx"

    def test_install_zed_user(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = install_client("zed", scope="user", overwrite=False)
        path = tmp_path / ".config" / "zed" / "settings.json"
        assert result.status == "written"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["context_servers"]["pdf-toolbox"]["command"] == "uvx"

    def test_install_universal_project(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = install_client("universal", scope="project", overwrite=False, project_root=tmp_path)
        path = tmp_path / ".mcp.json"
        assert result.scope == "project"
        assert result.status == "written"
        assert path.exists()

    def test_install_universal_conflict_without_overwrite(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        path = tmp_path / ".mcp.json"
        path.write_text('{"mcpServers":{"pdf-toolbox":{"command":"old","args":[]}}}', encoding="utf-8")
        result = install_client("universal", scope="project", overwrite=False, project_root=tmp_path)
        assert result.status == "conflict"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["mcpServers"]["pdf-toolbox"]["command"] == "old"

    def test_install_universal_conflict_with_overwrite(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        path = tmp_path / ".mcp.json"
        path.write_text('{"mcpServers":{"pdf-toolbox":{"command":"old","args":[]}}}', encoding="utf-8")
        result = install_client("universal", scope="project", overwrite=True, project_root=tmp_path)
        assert result.status == "written"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["mcpServers"]["pdf-toolbox"]["command"] == "uvx"

    def test_install_claude_desktop_is_manual(self):
        result = install_client("claude-desktop", scope="user", overwrite=False)
        assert result.status == "manual"
        assert result.command is not None

    def test_import_from_claude_desktop_unsupported_platform(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        result = import_from_claude_desktop()
        assert result.status == "manual"
        assert "only supported" in result.detail

    def test_import_from_claude_desktop_needs_cli(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr("pdf_toolbox.client_install.shutil.which", lambda name: None)
        result = import_from_claude_desktop()
        assert result.status == "needs_cli"
        assert "not found on PATH" in result.detail

    def test_import_from_claude_desktop_installed(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr("pdf_toolbox.client_install.shutil.which", lambda name: "/usr/bin/claude")

        class RunResult:
            returncode = 0
            stdout = "imported"
            stderr = ""

        def fake_run(command, capture_output, text, check):
            assert command[:4] == ["claude", "mcp", "add-from-claude-desktop", "--scope"]
            assert command[-1] == "user"
            return RunResult()

        monkeypatch.setattr("pdf_toolbox.client_install.subprocess.run", fake_run)
        result = import_from_claude_desktop()
        assert result.status == "installed"
        assert result.detail == "imported"

    def test_import_from_claude_desktop_installed_on_wsl(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
        monkeypatch.setattr("pdf_toolbox.client_install.shutil.which", lambda name: "/usr/bin/claude")

        class RunResult:
            returncode = 0
            stdout = "imported on wsl"
            stderr = ""

        monkeypatch.setattr(
            "pdf_toolbox.client_install.subprocess.run",
            lambda *args, **kwargs: RunResult(),
        )
        result = import_from_claude_desktop()
        assert result.status == "installed"
        assert result.detail == "imported on wsl"

    def test_import_from_claude_desktop_failure(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr("pdf_toolbox.client_install.shutil.which", lambda name: "/usr/bin/claude")

        class RunResult:
            returncode = 1
            stdout = ""
            stderr = "nope"

        monkeypatch.setattr(
            "pdf_toolbox.client_install.subprocess.run",
            lambda *args, **kwargs: RunResult(),
        )
        result = import_from_claude_desktop()
        assert result.status == "failed"
        assert result.detail == "nope"

    def test_detect_client_environment(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        report = detect_client_environment(project_root=tmp_path)
        assert report["scope"] == "project"
        assert report["project_root"] == str(tmp_path)
        assert any(client["name"] == "universal" for client in report["clients"])
        assert report["recommended"] == "universal"

    def test_default_install_target_prefers_project_universal(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        report = detect_client_environment(project_root=tmp_path)
        assert default_install_target(report) == "universal"
