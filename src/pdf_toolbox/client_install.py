"""MCP 客户端半自动安装。"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .client_setup import DEFAULT_SERVER_NAME, ClientSetup, build_client_setup


@dataclass(frozen=True)
class InstallResult:
    client: str
    scope: str
    status: str
    detail: str
    paths: tuple[Path, ...] = ()
    command: str | None = None

    def to_dict(self) -> dict:
        return {
            "client": self.client,
            "scope": self.scope,
            "status": self.status,
            "detail": self.detail,
            "paths": [str(path) for path in self.paths],
            "command": self.command,
        }

    def render_text(self) -> str:
        lines = [f"{self.client} [{self.scope}] {self.status}", self.detail]
        if self.paths:
            lines.append("")
            lines.extend(str(path) for path in self.paths)
        if self.command:
            lines.append("")
            lines.append(self.command)
        return "\n".join(lines)


def _server_entry() -> dict[str, list[str] | str]:
    return {
        "command": "uvx",
        "args": [
            "--from",
            "git+https://github.com/twoer/pdf-toolbox-mcp",
            "pdf-toolbox-mcp",
        ],
    }


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} 不是 JSON 对象")
    return data


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _git_toplevel(start: Path | None = None) -> Path | None:
    run = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start or Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )
    if run.returncode != 0:
        return None
    text = (run.stdout or "").strip()
    return Path(text) if text else None


def resolve_scope(scope: str, project_root: Path | None = None) -> tuple[str, Path | None]:
    if scope != "auto":
        return scope, project_root
    resolved_root = project_root or _git_toplevel()
    if resolved_root is not None:
        return "project", resolved_root
    return "user", None


def _merge_named_entry(
    path: Path,
    *,
    wrapper_key: str,
    name: str,
    entry: dict,
    overwrite: bool = False,
) -> str:
    data = _load_json(path)
    wrapper = data.get(wrapper_key)
    if wrapper is None:
        wrapper = {}
        data[wrapper_key] = wrapper
    if not isinstance(wrapper, dict):
        raise ValueError(f"{path} 中的 {wrapper_key} 不是对象")
    if wrapper.get(name) == entry:
        return "unchanged"
    if name in wrapper and not overwrite:
        return "conflict"
    wrapper[name] = entry
    _write_json(path, data)
    return "written"


def _cursor_path(scope: str, project_root: Path | None) -> Path:
    if scope == "project":
        base = project_root or Path.cwd()
        return base / ".cursor" / "mcp.json"
    return Path.home() / ".cursor" / "mcp.json"


def _universal_path(scope: str, project_root: Path | None) -> Path:
    if scope == "project":
        base = project_root or Path.cwd()
        return base / ".mcp.json"
    return Path.home() / ".mcp.json"


def _zed_path(scope: str, project_root: Path | None) -> Path:
    if scope == "project":
        base = project_root or Path.cwd()
        return base / ".zed" / "settings.json"
    return Path.home() / ".config" / "zed" / "settings.json"


def install_client(
    name: str,
    *,
    scope: str = "user",
    overwrite: bool = False,
    project_root: Path | None = None,
) -> InstallResult:
    scope, project_root = resolve_scope(scope, project_root)
    setup = build_client_setup(name)
    if setup.name == "claude-code":
        return _install_claude_code(setup, scope=scope, overwrite=overwrite, project_root=project_root)
    if setup.name == "cursor":
        return _install_cursor(setup, scope=scope, overwrite=overwrite, project_root=project_root)
    if setup.name == "universal":
        return _install_universal(setup, scope=scope, overwrite=overwrite, project_root=project_root)
    if setup.name == "zed":
        return _install_zed(setup, scope=scope, overwrite=overwrite, project_root=project_root)
    if setup.name == "claude-desktop":
        return InstallResult(
            client=setup.name,
            scope=scope,
            status="manual",
            detail="Claude Desktop 目前先用 `client export` 或在 Desktop 里手动导入。",
            command="uv run pdftoolbox client export --client claude-desktop",
        )
    return InstallResult(
        client=setup.name,
        scope=scope,
        status="manual",
        detail="This client currently uses exported files instead of direct installation.",
        command=f"uv run pdftoolbox client export --client {setup.name}",
    )


def import_from_claude_desktop() -> InstallResult:
    command = ["claude", "mcp", "add-from-claude-desktop", "--scope", "user"]
    if not _claude_desktop_import_supported():
        return InstallResult(
            client="claude-desktop",
            scope="user",
            status="manual",
            detail="Claude Desktop import is only supported on macOS and WSL.",
            command=shlex.join(command),
        )
    if shutil.which("claude") is None:
        return InstallResult(
            client="claude-desktop",
            scope="user",
            status="needs_cli",
            detail="Claude Code CLI was not found on PATH.",
            command=shlex.join(command),
        )
    run = subprocess.run(command, capture_output=True, text=True, check=False)
    if run.returncode != 0:
        detail = (run.stderr or run.stdout or "").strip() or "claude mcp add-from-claude-desktop failed"
        return InstallResult(
            client="claude-desktop",
            scope="user",
            status="failed",
            detail=detail,
            command=shlex.join(command),
        )
    detail = (run.stdout or run.stderr or "").strip() or "Claude Code imported servers from Claude Desktop"
    return InstallResult(
        client="claude-desktop",
        scope="user",
        status="installed",
        detail=detail,
        command=shlex.join(command),
    )


def detect_client_environment(project_root: Path | None = None) -> dict:
    resolved_root = project_root or _git_toplevel()
    scope = "project" if resolved_root is not None else "user"
    universal_path = (resolved_root / ".mcp.json") if resolved_root is not None else None
    universal_present = universal_path is not None and universal_path.exists()
    cursor_user = Path.home() / ".cursor" / "mcp.json"
    cursor_project = (resolved_root / ".cursor" / "mcp.json") if resolved_root is not None else None
    zed_user = Path.home() / ".config" / "zed" / "settings.json"
    zed_project = (resolved_root / ".zed" / "settings.json") if resolved_root is not None else None
    cursor_present = cursor_user.exists() or (cursor_project is not None and cursor_project.exists())
    zed_present = zed_user.exists() or (zed_project is not None and zed_project.exists())
    clients = [
        {
            "name": "universal",
            "display_name": "Universal Project MCP",
            "kind": "project",
            "present": universal_present,
            "scope": scope,
            "paths": [str(universal_path)] if universal_path is not None else [],
            "detail": "Project `.mcp.json` detected"
            if universal_present
            else "Project `.mcp.json` will be created on install",
        },
        {
            "name": "claude-code",
            "display_name": "Claude Code",
            "kind": "cli",
            "present": shutil.which("claude") is not None,
            "scope": "user",
            "paths": [],
            "detail": "claude CLI on PATH" if shutil.which("claude") else "claude CLI missing",
        },
        {
            "name": "cursor",
            "display_name": "Cursor",
            "kind": "config",
            "present": cursor_present,
            "scope": scope,
            "paths": [str(path) for path in (cursor_project, cursor_user) if path is not None],
            "detail": "Cursor config file detected"
            if cursor_present
            else "Cursor config will be created on install",
        },
        {
            "name": "zed",
            "display_name": "Zed",
            "kind": "config",
            "present": zed_present,
            "scope": scope,
            "paths": [str(path) for path in (zed_project, zed_user) if path is not None],
            "detail": "Zed config file detected"
            if zed_present
            else "Zed config will be created on install",
        },
        {
            "name": "claude-desktop",
            "display_name": "Claude Desktop",
            "kind": "manual",
            "present": False,
            "scope": "manual",
            "paths": [],
            "detail": "Use client export or manual import",
        },
        {
            "name": "chatgpt",
            "display_name": "ChatGPT",
            "kind": "remote",
            "present": False,
            "scope": "remote",
            "paths": [],
            "detail": "Use the remote connector/workspace flow",
        },
    ]
    return {
        "project_root": str(resolved_root) if resolved_root is not None else None,
        "scope": scope,
        "clients": clients,
        "recommended": "universal"
        if resolved_root is not None
        else next(
            (
                name
                for name in ("claude-code", "cursor", "zed", "claude-desktop", "chatgpt")
                if any(client["name"] == name and client["present"] for client in clients)
            ),
            "claude-code",
        ),
    }


def default_install_target(report: dict) -> str:
    clients = {client["name"]: client for client in report["clients"]}
    if report.get("scope") == "project":
        return "universal"
    for name in ("claude-code", "cursor", "zed"):
        client = clients.get(name)
        if client and client.get("present"):
            return name
    if shutil.which("claude") is not None:
        return "claude-code"
    return "cursor"


def _claude_desktop_import_supported() -> bool:
    if sys.platform == "darwin":
        return True
    if sys.platform != "linux":
        return False
    return bool(os.environ.get("WSL_DISTRO_NAME"))


def _install_universal(
    setup: ClientSetup,
    *,
    scope: str,
    overwrite: bool,
    project_root: Path | None,
) -> InstallResult:
    if scope != "project":
        return InstallResult(
            client=setup.name,
            scope=scope,
            status="manual",
            detail="Universal `.mcp.json` is meant for project scope; use `--scope auto` or `--scope project`.",
            command="uv run pdftoolbox client install --client universal --scope project",
        )
    path = _universal_path(scope, project_root)
    status = _merge_named_entry(
        path,
        wrapper_key="mcpServers",
        name=DEFAULT_SERVER_NAME,
        entry=_server_entry(),
        overwrite=overwrite,
    )
    return InstallResult(
        client=setup.name,
        scope=scope,
        status=status,
        detail=f"Wrote project MCP config at {path}",
        paths=(path,),
    )


def _install_cursor(
    setup: ClientSetup,
    *,
    scope: str,
    overwrite: bool,
    project_root: Path | None,
) -> InstallResult:
    path = _cursor_path(scope, project_root)
    status = _merge_named_entry(
        path,
        wrapper_key="mcpServers",
        name=DEFAULT_SERVER_NAME,
        entry=_server_entry(),
        overwrite=overwrite,
    )
    return InstallResult(
        client=setup.name,
        scope=scope,
        status=status,
        detail=f"Wrote Cursor config at {path}",
        paths=(path,),
    )


def _install_zed(
    setup: ClientSetup,
    *,
    scope: str,
    overwrite: bool,
    project_root: Path | None,
) -> InstallResult:
    path = _zed_path(scope, project_root)
    status = _merge_named_entry(
        path,
        wrapper_key="context_servers",
        name=DEFAULT_SERVER_NAME,
        entry={
            "command": "uvx",
            "args": [
                "--from",
                "git+https://github.com/twoer/pdf-toolbox-mcp",
                "pdf-toolbox-mcp",
            ],
            "env": {},
        },
        overwrite=overwrite,
    )
    return InstallResult(
        client=setup.name,
        scope=scope,
        status=status,
        detail=f"Wrote Zed config at {path}",
        paths=(path,),
    )


def _install_claude_code(
    setup: ClientSetup,
    *,
    scope: str,
    overwrite: bool,
    project_root: Path | None,
) -> InstallResult:
    server_entry = {
        "command": "uvx",
        "args": [
            "--from",
            "git+https://github.com/twoer/pdf-toolbox-mcp",
            "pdf-toolbox-mcp",
        ],
    }
    command = [
        "claude",
        "mcp",
        "add-json",
        DEFAULT_SERVER_NAME,
        json.dumps(server_entry, ensure_ascii=False),
        "--scope",
        "project" if scope == "project" else "user",
    ]
    if overwrite:
        command.append("--force")
    if shutil.which("claude") is None:
        return InstallResult(
            client=setup.name,
            scope=scope,
            status="needs_cli",
            detail="Claude Code CLI was not found on PATH.",
            command=shlex.join(command),
        )
    run = subprocess.run(
        command,
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if run.returncode != 0:
        detail = (run.stderr or run.stdout or "").strip() or "claude mcp add-json failed"
        return InstallResult(
            client=setup.name,
            scope=scope,
            status="failed",
            detail=detail,
            command=shlex.join(command),
        )
    detail = (run.stdout or run.stderr or "").strip() or "Claude Code accepted the server"
    return InstallResult(
        client=setup.name,
        scope=scope,
        status="installed",
        detail=detail,
        command=shlex.join(command),
    )
