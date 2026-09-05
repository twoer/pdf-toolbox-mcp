#!/usr/bin/env python3
"""MCP stdio 探测客户端（M-1a 竞品实测用，M1 阶段复用为契约测试工具）。

用法：
  python3 tools/mcp_probe.py list -- <server-command...>
  python3 tools/mcp_probe.py call <tool> '<json-args>' -- <server-command...>

只依赖标准库。按换行分隔的 JSON-RPC 2.0 与 server 通信，
对 stdout 上的非 JSON 行（劣质 server 的日志）单独收集为 noise 并提示。
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
from typing import Any

PROTOCOL_VERSION = "2025-06-18"
# 调试用：PROBE_TEXT_LIMIT=2000 可放宽文本截断
TEXT_LIMIT = int(os.environ.get("PROBE_TEXT_LIMIT", "400"))


class McpStdioClient:
    def __init__(self, command: list[str], timeout: float = 60.0) -> None:
        self.timeout = timeout
        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.responses: dict[int, queue.Queue] = {}
        self.noise: list[str] = []
        self.notifications: list[dict] = []
        self._id = 0
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()
        self._stderr = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stderr.start()

    def _read_stdout(self) -> None:
        assert self.proc.stdout is not None
        for raw in self.proc.stdout:
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                self.noise.append(line[:300])
                continue
            if "id" in msg and isinstance(msg.get("id"), int):
                self.responses.setdefault(msg["id"], queue.Queue()).put(msg)
            else:
                self.notifications.append(msg)

    def _drain_stderr(self) -> None:
        assert self.proc.stderr is not None
        for _ in self.proc.stderr:
            pass  # 丢弃，防止 pipe 涨死；调试时可改为收集

    def _send(self, obj: dict) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write((json.dumps(obj) + "\n").encode())
        self.proc.stdin.flush()

    def request(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        rid = self._id
        q: queue.Queue = queue.Queue()
        self.responses[rid] = q
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}})
        try:
            msg = q.get(timeout=self.timeout)
        except queue.Empty as exc:
            raise TimeoutError(f"{method} 超时（{self.timeout}s）") from exc
        finally:
            self.responses.pop(rid, None)
        if "error" in msg:
            raise RuntimeError(f"{method} 返回错误: {msg['error']}")
        return msg.get("result", {})

    def initialize(self) -> dict:
        result = self.request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "pdf-toolbox-probe", "version": "0.1.0"},
            },
        )
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return result

    def list_tools(self) -> list[dict]:
        result = self.request("tools/list")
        return result.get("tools", [])

    def call_tool(self, name: str, args: dict) -> Any:
        return self.request("tools/call", {"name": name, "arguments": args})

    def close(self) -> None:
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def summarize_content(content: Any) -> str:
    """把工具返回的 content 数组压成人话摘要。"""
    if not isinstance(content, list):
        return str(content)[:400]
    parts = []
    for block in content:
        btype = block.get("type")
        if btype == "text":
            parts.append(block.get("text", "")[:TEXT_LIMIT])
        elif btype == "image":
            data = block.get("data", "")
            parts.append(f"[image {block.get('mimeType', '?')} base64≈{len(data)} chars]")
        elif btype == "resource":
            parts.append(f"[resource {block.get('resource', {}).get('uri', '?')}]")
        else:
            parts.append(f"[{btype}]")
    return " | ".join(parts)[: TEXT_LIMIT * 2 + 200]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["list", "call", "schema"])
    parser.add_argument("tool", nargs="?", help="call/schema 模式下的工具名")
    parser.add_argument("args", nargs="?", default="{}", help="call 模式下的 JSON 参数")
    parser.add_argument("--timeout", type=float, default=60.0)
    # 手动在第一个 -- 处切开：-- 之后的全部原样视为 server 命令（可能含 -y 之类参数）
    argv = sys.argv[1:]
    if "--" in argv:
        idx = argv.index("--")
        command = argv[idx + 1 :]
        argv = argv[:idx]
    else:
        command = []
    ns = parser.parse_args(argv)
    if not command:
        parser.error("缺少 server 命令（用 -- 分隔）")

    client = McpStdioClient(command, timeout=ns.timeout)
    try:
        info = client.initialize()
        server_info = info.get("serverInfo", {})
        print(
            f"server: {server_info.get('name', '?')} {server_info.get('version', '?')}"
            f"  protocol={info.get('protocolVersion', '?')}"
        )
        if client.noise:
            print(f"⚠️ stdout 噪声 {len(client.noise)} 行（server 日志打进了协议通道）")
        if ns.action == "list":
            tools = client.list_tools()
            print(f"tools: {len(tools)}")
            for t in tools:
                desc = (t.get("description") or "").strip().replace("\n", " ")
                print(f"  - {t['name']}: {desc[:120]}")
        elif ns.action == "schema":
            if not ns.tool:
                parser.error("schema 模式需要工具名")
            tools = {t["name"]: t for t in client.list_tools()}
            if ns.tool not in tools:
                parser.error(f"工具不存在，可选: {', '.join(tools)}")
            print(json.dumps(tools[ns.tool].get("inputSchema", {}), indent=2, ensure_ascii=False))
        else:
            if not ns.tool:
                parser.error("call 模式需要工具名")
            result = client.call_tool(ns.tool, json.loads(ns.args))
            status = "error" if result.get("isError") else "ok"
            print(f"call {ns.tool} -> {status}")
            print(summarize_content(result.get("content")))
    except (TimeoutError, RuntimeError) as exc:
        print(f"❌ {exc}")
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
