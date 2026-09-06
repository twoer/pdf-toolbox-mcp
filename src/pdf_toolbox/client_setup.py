"""各 MCP 客户端的接入片段生成。

目标不是替用户改配置，而是把最常见的本地接入方式一次性吐出来：
- Claude Desktop / 通用 mcpServers JSON
- Claude Code 的 `claude mcp add`
- Zed 的 `context_servers` JSON
- ChatGPT 的远程 connector 说明
"""

from __future__ import annotations

import json
import shlex
from base64 import b64encode
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

DEFAULT_SERVER_NAME = "pdf-toolbox"
DEFAULT_COMMAND = (
    "uvx",
    "--from",
    "git+https://github.com/twoer/pdf-toolbox-mcp",
    "pdf-toolbox-mcp",
)


@dataclass(frozen=True)
class ClientSetup:
    name: str
    display_name: str
    mode: str
    summary: str
    export_filename: str
    snippet_title: str | None
    snippet: str | None
    install_link: str | None = None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "mode": self.mode,
            "summary": self.summary,
            "export_filename": self.export_filename,
            "snippet_title": self.snippet_title,
            "snippet": self.snippet,
            "install_link": self.install_link,
            "notes": list(self.notes),
        }

    def render_text(self) -> str:
        lines = [self.display_name, "", self.summary]
        if self.snippet_title and self.snippet:
            lines.extend(["", f"{self.snippet_title}:", self.snippet])
        elif self.snippet:
            lines.extend(["", self.snippet])
        if self.install_link:
            lines.extend(["", f"Install link: {self.install_link}"])
        if self.notes:
            lines.extend(["", "Notes:"])
            lines.extend(f"- {note}" for note in self.notes)
        return "\n".join(lines)


def _server_entry() -> dict[str, list[str] | str]:
    return {
        "command": DEFAULT_COMMAND[0],
        "args": list(DEFAULT_COMMAND[1:]),
    }


def _json_snippet(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _cursor_install_link(name: str, payload: dict) -> str:
    encoded = b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
    return f"cursor://anysphere.cursor-deeplink/mcp/install?name={quote(name)}&config={quote(encoded)}"


def _claude_desktop_setup() -> ClientSetup:
    payload = {
        "mcpServers": {
            DEFAULT_SERVER_NAME: _server_entry(),
        }
    }
    return ClientSetup(
        name="claude-desktop",
        display_name="Claude Desktop",
        mode="json",
        summary="Paste into claude_desktop_config.json or import with Claude Code.",
        export_filename="claude_desktop_config.json",
        snippet_title="claude_desktop_config.json",
        snippet=_json_snippet(payload),
        notes=(
            "Restart Claude Desktop after saving the file.",
            "Claude Code can import the same mcpServers object with `claude mcp add-json`.",
        ),
    )


def _claude_code_setup() -> ClientSetup:
    command = shlex.join(("claude", "mcp", "add", DEFAULT_SERVER_NAME, "--scope", "user", "--", *DEFAULT_COMMAND))
    return ClientSetup(
        name="claude-code",
        display_name="Claude Code",
        mode="command",
        summary="Use the built-in `claude mcp add` flow.",
        export_filename="claude_code_add.txt",
        snippet_title="Command",
        snippet=command,
        notes=(
            "This writes to your user scope by default.",
            (
                "If you already have a Claude Desktop JSON block, use `claude mcp add-json` "
                "with its inner `mcpServers` object."
            ),
        ),
    )


def _zed_setup() -> ClientSetup:
    payload = {
        "context_servers": {
            DEFAULT_SERVER_NAME: {
                "command": DEFAULT_COMMAND[0],
                "args": list(DEFAULT_COMMAND[1:]),
                "env": {},
            }
        }
    }
    return ClientSetup(
        name="zed",
        display_name="Zed",
        mode="json",
        summary="Paste into Zed Settings → AI → MCP Servers.",
        export_filename="zed_settings.json",
        snippet_title="settings.json",
        snippet=_json_snippet(payload),
        notes=(
            "In Zed, add a Local Server and paste the JSON into the generated settings entry.",
            "Zed exposes the server in Agent Panel once the indicator dot turns green.",
        ),
    )


def _cursor_setup() -> ClientSetup:
    server_config = _server_entry()
    payload = {
        "mcpServers": {
            DEFAULT_SERVER_NAME: server_config,
        }
    }
    return ClientSetup(
        name="cursor",
        display_name="Cursor",
        mode="json",
        summary="Use `mcp.json` or the Cursor MCP deeplink installer.",
        export_filename="cursor_mcp.json",
        snippet_title="mcp.json",
        snippet=_json_snippet(payload),
        install_link=_cursor_install_link(DEFAULT_SERVER_NAME, server_config),
        notes=(
            "Cursor can load the same stdio block from `~/.cursor/mcp.json`.",
            "Cursor also supports `cursor://.../mcp/install` deeplinks for one-click install.",
        ),
    )


def _universal_setup() -> ClientSetup:
    payload = {
        "mcpServers": {
            DEFAULT_SERVER_NAME: _server_entry(),
        }
    }
    return ClientSetup(
        name="universal",
        display_name="Universal Project MCP",
        mode="json",
        summary="Write a project-level `.mcp.json` for Claude Code project sessions and repo/workspace use.",
        export_filename=".mcp.json",
        snippet_title=".mcp.json",
        snippet=_json_snippet(payload),
        notes=(
            "This is the simplest drop-in for a repo or workspace.",
            "Claude Code project sessions can use `.mcp.json` directly.",
        ),
    )


def _generic_json_setup() -> ClientSetup:
    payload = {
        "mcpServers": {
            DEFAULT_SERVER_NAME: _server_entry(),
        }
    }
    return ClientSetup(
        name="generic-json",
        display_name="Generic MCP JSON",
        mode="json",
        summary="Reusable `mcpServers` block for clients that import Claude Desktop-style config.",
        export_filename="mcpServers.json",
        snippet_title="mcpServers",
        snippet=_json_snippet(payload),
        notes=("This is the portable stdio block used by Claude Desktop-style imports.",),
    )


def _chatgpt_setup() -> ClientSetup:
    return ClientSetup(
        name="chatgpt",
        display_name="ChatGPT",
        mode="manual",
        summary="ChatGPT uses the remote MCP / connector flow, not a local stdio drop-in.",
        export_filename="chatgpt_connect.txt",
        snippet_title=None,
        snippet=None,
        notes=(
            "Use the remote connector / workspace flow from the OpenAI docs.",
            "This repo currently targets local clients such as Claude Desktop, Claude Code, and Zed.",
        ),
    )


_BUILDERS: dict[str, Callable[[], ClientSetup]] = {
    "claude-desktop": _claude_desktop_setup,
    "claude": _claude_desktop_setup,
    "desktop": _claude_desktop_setup,
    "claude-code": _claude_code_setup,
    "code": _claude_code_setup,
    "zed": _zed_setup,
    "cursor": _cursor_setup,
    "universal": _universal_setup,
    "generic-json": _generic_json_setup,
    "chatgpt": _chatgpt_setup,
}

LIST_ORDER = (
    "universal",
    "claude-desktop",
    "claude-code",
    "zed",
    "cursor",
    "generic-json",
    "chatgpt",
)


def list_client_setups() -> list[ClientSetup]:
    return [build_client_setup(name) for name in LIST_ORDER]


def supported_client_names() -> tuple[str, ...]:
    return LIST_ORDER


def build_client_setup(name: str) -> ClientSetup:
    key = name.strip().lower()
    try:
        return _BUILDERS[key]()
    except KeyError as exc:
        supported = ", ".join(LIST_ORDER)
        raise KeyError(f"Unknown client '{name}'. Supported clients: {supported}") from exc


def render_client_list() -> list[str]:
    lines: list[str] = []
    for setup in list_client_setups():
        lines.append(f"{setup.name:14s} {setup.summary}")
    return lines


def export_client_bundle(
    out_dir: Path,
    *,
    clients: list[str] | None = None,
    overwrite: bool = False,
) -> list[Path]:
    selected = list_client_setups() if clients is None else [build_client_setup(name) for name in clients]
    written: list[Path] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for setup in selected:
        client_dir = out_dir / setup.name
        client_dir.mkdir(parents=True, exist_ok=True)
        target = client_dir / setup.export_filename
        if target.exists() and not overwrite:
            raise FileExistsError(target)
        content = setup.snippet if setup.mode == "json" and setup.snippet else setup.render_text()
        target.write_text(content, encoding="utf-8")
        written.append(target)
        if setup.install_link:
            link_file = client_dir / "install-link.txt"
            if link_file.exists() and not overwrite:
                raise FileExistsError(link_file)
            link_file.write_text(setup.install_link + "\n", encoding="utf-8")
            written.append(link_file)
    return written
