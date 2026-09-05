# Contributing

Thanks for your interest in improving pdf-toolbox-mcp!

## Development setup

```bash
git clone https://github.com/twoer/pdf-toolbox-mcp
cd pdf-toolbox-mcp
uv sync --dev
uv run pdftoolbox probe all   # 检查系统依赖级别（见 README 安装矩阵）
```

System tools are capability-leveled — you can develop and run most tests with just one of them installed; engine tests auto-skip when a binary is missing.

## Before submitting

```bash
uv run ruff check src tests tools   # lint 必须全绿
uv run pytest                       # 全量测试（按本机依赖自动跳过）
```

Both must pass. CI runs the full matrix (ubuntu / macos / windows) on every PR.

## Adding a tool

1. Implement the engine function in `src/pdf_toolbox/engine/` — pure function, `dict` in / `dict` out, no MCP imports; call `require()` for binaries and `assert_readable()`/`check_write()` for path safety.
2. Wrap it in `server.py` via `_guard()` (structured errors + `_deps` injection) and add a `cli.py` command.
3. Tests in `tests/` with the right capability marker (`requires_poppler` / `requires_qpdf` / `requires_tesseract` / `requires_gs`).
4. Update both READMEs' tool table and `CHANGELOG.md`.

## Conventions

- Errors raise typed exceptions from `engine/errors.py`; the MCP layer converts them to `{"ok": false, "error": <code>, ...}`.
- Outputs never overwrite silently — `overwrite=true` must be explicit.
- All subprocess calls use argument lists (no shell interpolation).
- Docs and user-facing messages are bilingual (English README + `README.zh-CN.md`); code comments in Chinese are fine.

## Reporting issues

Please include `uv run pdftoolbox probe all` output and the structured error JSON you got.
