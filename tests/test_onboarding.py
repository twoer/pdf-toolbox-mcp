"""onboarding 入口测试：CLI doctor + 共享检查结果。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

import pdf_toolbox.onboarding as onboarding
from pdf_toolbox.cli import app
from pdf_toolbox.onboarding import all_ok, collect_checks


class TestOnboarding:
    def test_parse_args(self):
        assert onboarding.parse_args(["--json"]).json is True

    def test_collect_checks(self):
        items = collect_checks()
        names = {item.name for item in items}
        assert {"server", "cli", "probe", "README.md", "README.zh-CN.md", "docs/cookbook.md"} <= names
        assert any(item.detail == "documents doctor" for item in items)
        assert any(item.detail == "documents ocr_pdf" for item in items)
        assert any(item.detail == "documents starter_action" for item in items)
        assert any(item.detail == "documents starter_cli" for item in items)
        assert any(item.detail == "documents starter_tool" for item in items)
        assert any(item.detail == "documents client list" for item in items)
        assert any(item.detail == "documents client show" for item in items)
        assert any(item.detail == "documents client export" for item in items)
        assert any(item.detail == "documents client detect" for item in items)
        assert any(item.detail == "documents client install" for item in items)
        assert any(item.detail == "documents client import-claude-desktop" for item in items)
        assert any(item.detail == "documents universal" for item in items)
        assert any(item.detail == "documents cursor" for item in items)
        assert any(item.detail == "documents onboarding_check.py --json" for item in items)
        assert any(item.detail == "documents pdftoolbox doctor" for item in items)
        assert any(item.detail == "documents tool_doctor" for item in items)
        assert all_ok(items)

    def test_doctor_command(self):
        runner = CliRunner()
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "PASS onboarding check" in result.output
        assert "server" in result.output
        assert "capability_level" in result.output
        assert "available_now" in result.output
        assert "starter_action" in result.output
        assert "starter_cli" in result.output
        assert "starter_tool" in result.output
        assert "Run `pdftoolbox doctor --json`" in result.output

    def test_doctor_json(self):
        runner = CliRunner()
        result = runner.invoke(app, ["doctor", "--json"])
        assert result.exit_code == 0
        report = json.loads(result.output)
        assert report["ok"] is True
        assert report["summary"] == "PASS onboarding check"
        assert "dependencies" in report
        assert "available_actions" in report
        assert "starter_action" in report
        assert "starter_cli" in report
        assert "starter_tool" in report
        assert "next_step" in report
        assert "tool_ocr_pdf" in report["next_step"] or "tool_doctor" in report["next_step"]

    def test_onboarding_script(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, str(root / "tools" / "onboarding_check.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert "available_now" in result.stdout
        assert "starter_action" in result.stdout
        assert "starter_cli" in result.stdout
        assert "starter_tool" in result.stdout

    def test_onboarding_script_json(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, str(root / "tools" / "onboarding_check.py"), "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        report = json.loads(result.stdout)
        assert report["ok"] is True
        assert "available_actions" in report
        assert "starter_cli" in report
        assert "starter_tool" in report

    def test_report_checks_uses_single_probe(self, monkeypatch):
        calls = 0
        original = onboarding.probe_all

        def wrapped():
            nonlocal calls
            calls += 1
            return original()

        monkeypatch.setattr(onboarding, "probe_all", wrapped)
        report = onboarding.report_checks()
        assert report["ok"] is True
        assert calls == 1
