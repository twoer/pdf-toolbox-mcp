"""新用户入口检查：只读，不修改文件。"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from importlib import import_module
from pathlib import Path

from .engine.probe import capability_level, probe_all

REQUIRED_TERMS = (
    "unlock_pdf",
    "ocr_pdf",
    "render_pages",
    "doctor",
    "client list",
    "client show",
    "client export",
    "client detect",
    "client install",
    "client import-claude-desktop",
    "universal",
    "cursor",
    "starter_action",
    "starter_cli",
    "starter_tool",
    "onboarding_check.py --json",
)


@dataclass(frozen=True)
class CheckItem:
    name: str
    ok: bool
    detail: str


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="本地 onboarding 检查")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出诊断结果")
    return parser.parse_args(argv)


def collect_checks(root: Path | None = None, deps: list | None = None) -> list[CheckItem]:
    root = root or project_root()
    items: list[CheckItem] = []

    try:
        server = import_module("pdf_toolbox.server")
        cli = import_module("pdf_toolbox.cli")
        probe = import_module("pdf_toolbox.engine.probe")
    except Exception as exc:
        return [CheckItem("import", False, f"{type(exc).__name__}: {exc}")]

    items.append(
        CheckItem(
            "server",
            hasattr(server, "mcp") and hasattr(server, "main"),
            "FastMCP entrypoint is present",
        )
    )
    items.append(
        CheckItem(
            "cli",
            hasattr(cli, "app"),
            "Typer app is present",
        )
    )

    try:
        deps = deps if deps is not None else probe.probe_all()
        items.append(
            CheckItem(
                "probe",
                isinstance(deps, list) and len(deps) == 4,
                "default dependency probe runs",
            )
        )
        items.append(
            CheckItem(
                "probe",
                all(hasattr(dep, "unlocks") for dep in deps),
                "dependencies expose unlock targets",
            )
        )
    except Exception as exc:
        items.append(CheckItem("probe", False, f"{type(exc).__name__}: {exc}"))
        return items

    for rel in ("README.md", "README.zh-CN.md"):
        text = (root / rel).read_text(encoding="utf-8")
        for term in REQUIRED_TERMS:
            items.append(
                CheckItem(
                    rel,
                    term in text,
                    f"documents {term}",
                )
            )

    cookbook = (root / "docs/cookbook.md").read_text(encoding="utf-8")
    for term in ("pdftoolbox doctor", "tool_doctor"):
        items.append(
            CheckItem(
                "docs/cookbook.md",
                term in cookbook,
                f"documents {term}",
            )
        )

    return items


def all_ok(items: list[CheckItem]) -> bool:
    return all(item.ok for item in items)


def available_actions(dependencies: list) -> list[str]:
    actions: list[str] = []
    for dep in dependencies:
        if getattr(dep, "found", False):
            actions.extend(getattr(dep, "unlocks", ()))
    return list(dict.fromkeys(actions))


def recommended_action(actions: list[str]) -> str | None:
    priority = (
        "ocr_pdf",
        "unlock_pdf",
        "render_pages",
        "extract_text",
        "pdf_info",
        "is_searchable",
        "split_pdf",
        "merge_pdfs",
        "rotate_pages",
        "protect_pdf",
        "check_repair",
        "linearize",
        "batch_ocr",
        "compress_pdf",
        "list_fonts",
    )
    for item in priority:
        if item in actions:
            return item
    return actions[0] if actions else None


def starter_commands(action: str | None) -> tuple[str | None, str | None]:
    mapping = {
        "ocr_pdf": (
            "pdftoolbox ocr scan.pdf --lang chi_sim+eng",
            "tool_ocr_pdf",
        ),
        "unlock_pdf": (
            "pdftoolbox unlock locked.pdf --password 'xxx'",
            "tool_unlock_pdf",
        ),
        "render_pages": (
            "pdftoolbox render scan.pdf --pages 1 --dpi 150",
            "tool_render_pages",
        ),
        "extract_text": (
            "pdftoolbox text scan.pdf --pages 1",
            "tool_extract_text",
        ),
        "pdf_info": (
            "pdftoolbox info scan.pdf",
            "tool_pdf_info",
        ),
        "is_searchable": (
            "pdftoolbox searchable scan.pdf",
            "tool_is_searchable",
        ),
        "split_pdf": (
            "pdftoolbox split input.pdf --ranges '1-3,5'",
            "tool_split_pdf",
        ),
        "merge_pdfs": (
            "pdftoolbox merge a.pdf b.pdf --output merged.pdf",
            "tool_merge_pdfs",
        ),
        "rotate_pages": (
            "pdftoolbox rotate scan.pdf --angle 90",
            "tool_rotate_pages",
        ),
        "protect_pdf": (
            "pdftoolbox protect file.pdf --user-password 'xxx'",
            "tool_protect_pdf",
        ),
        "check_repair": (
            "pdftoolbox check broken.pdf",
            "tool_check_repair",
        ),
        "linearize": (
            "pdftoolbox linearize file.pdf",
            "tool_linearize",
        ),
        "batch_ocr": (
            "pdftoolbox batch ocr scans/ --lang chi_sim+eng",
            "tool_batch_ocr",
        ),
        "compress_pdf": (
            "pdftoolbox compress big.pdf --target-mb 10",
            "tool_compress_pdf",
        ),
        "list_fonts": (
            "pdftoolbox fonts deck.pdf",
            "tool_list_fonts",
        ),
    }
    return mapping.get(action, (None, None))


def format_report(
    report: dict,
    *,
    success_mark: str = "✅",
    failure_mark: str = "❌",
) -> list[str]:
    lines: list[str] = []
    for dep in report["dependencies"]:
        mark = success_mark if dep["found"] else failure_mark
        lines.append(f"{mark} L{dep['level']} {dep['name']:10s} {dep['version'] or ''}")
        if dep["unlocks"]:
            lines.append(f"      unlocks: {', '.join(dep['unlocks'])}")
        if not dep["found"]:
            lines.append(f"      install: {dep['install']}")
    lines.append(f"capability_level: L{report['capability_level']}")
    if report.get("available_actions"):
        lines.append(f"available_now: {', '.join(report['available_actions'])}")
    if report.get("starter_action"):
        lines.append(f"starter_action: {report['starter_action']}")
    if report.get("starter_cli"):
        lines.append(f"starter_cli: {report['starter_cli']}")
    if report.get("starter_tool"):
        lines.append(f"starter_tool: {report['starter_tool']}")
    for item in report["checks"]:
        mark = success_mark if item["ok"] else failure_mark
        lines.append(f"{mark} {item['name']:10s} {item['detail']}")
    lines.append(report["next_step"])
    lines.append(report["summary"])
    return lines


def report_checks(root: Path | None = None) -> dict:
    deps = probe_all()
    items = collect_checks(root, deps=deps)
    missing = [dep for dep in deps if not dep.found]
    actions = available_actions(deps)
    starter = recommended_action(actions)
    starter_cli, starter_tool = starter_commands(starter)
    if missing:
        if starter_cli and starter_tool:
            next_step = (
                f"You can already start with `{starter_cli}` or `{starter_tool}`; "
                "install the missing binaries below, then rerun `pdftoolbox doctor` or `tool_doctor`."
            )
        else:
            next_step = "Install the missing binaries below, then rerun `pdftoolbox doctor` or `tool_doctor`."
    else:
        if starter_cli and starter_tool:
            next_step = (
                "Run `pdftoolbox doctor --json` or `tool_doctor`, then start with "
                f"`{starter_cli}` or `{starter_tool}`."
            )
        else:
            next_step = "Run `pdftoolbox doctor --json` or `tool_doctor`."
    return {
        "ok": all_ok(items),
        "summary": "PASS onboarding check" if all_ok(items) else "FAIL onboarding check",
        "capability_level": capability_level(),
        "available_actions": actions,
        "starter_action": starter,
        "starter_cli": starter_cli,
        "starter_tool": starter_tool,
        "next_step": next_step,
        "dependencies": [dep.as_dict() for dep in deps],
        "checks": [asdict(item) for item in items],
    }
