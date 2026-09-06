"""依赖探测：L0–L3 能力分级 + 各平台安装命令（PLAN.md §5）。

usage:
    python -m pdf_toolbox.engine.probe
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass

# 二进制名 → (能力级别, version flag, {sys.platform: 安装命令})
SPEC: dict[str, tuple[int, str, dict[str, str]]] = {
    "qpdf": (
        0,
        "--version",
        {
            "darwin": "brew install qpdf",
            "linux": "apt install qpdf  # 或 dnf install qpdf",
            "win32": "scoop install qpdf  # 或 choco install qpdf",
        },
    ),
    "pdfinfo": (
        1,
        "-v",
        {
            "darwin": "brew install poppler",
            "linux": "apt install poppler-utils",
            "win32": "scoop install poppler  # 或 conda install -c conda-forge poppler",
        },
    ),
    "tesseract": (
        2,
        "--version",
        {
            "darwin": "brew install tesseract tesseract-lang",
            "linux": "apt install tesseract-ocr tesseract-ocr-chi-sim",
            "win32": "scoop install tesseract  # 语言包需另行下载 tessdata",
        },
    ),
    "gs": (
        3,
        "--version",
        {
            "darwin": "brew install ghostscript",
            "linux": "apt install ghostscript",
            "win32": "scoop install ghostscript  # 或 winget install ArtifexSoftware.GhostScript",
        },
    ),
}

# 二进制安装后可解锁的主要工具（给缺依赖报错 / probe 输出用）
UNLOCKS: dict[str, tuple[str, ...]] = {
    "qpdf": ("split_pdf", "merge_pdfs", "rotate_pages", "protect_pdf", "unlock_pdf", "check_repair", "linearize"),
    "pdfinfo": ("pdf_info", "extract_text", "render_pages", "list_fonts", "is_searchable"),
    "tesseract": ("ocr_pdf", "batch_ocr"),
    "gs": ("compress_pdf",),
}


@dataclass
class Dependency:
    name: str
    level: int
    found: bool
    version: str | None
    install: str | None
    unlocks: tuple[str, ...]
    error: str | None = None

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload["unlocks"] = list(self.unlocks)
        return payload


def probe_one(name: str) -> Dependency:
    level, flag, hints = SPEC[name]
    hint = hints.get(platform.sys.platform, hints.get("linux", ""))
    unlocks = UNLOCKS.get(name, ())
    path = find_binary(name)
    if not path:
        return Dependency(name, level, False, None, hint, unlocks)
    try:
        out = subprocess.run(
            [path, flag], capture_output=True, text=True, timeout=10
        )
        first = (out.stdout or out.stderr).strip().splitlines()
        version = first[0][:120] if first else None
        return Dependency(name, level, True, version, hint, unlocks)
    except Exception as exc:
        return Dependency(name, level, True, None, hint, unlocks, error=str(exc))


def probe_all() -> list[Dependency]:
    return [probe_one(name) for name in SPEC]


def tess_langs() -> set[str]:
    """tesseract 已安装的语言包（无 tesseract 时返回空集）。"""
    path = find_binary("tesseract")
    if not path:
        return set()
    try:
        out = subprocess.run(
            [path, "--list-langs"], capture_output=True, text=True, timeout=10
        )
        lines = (out.stdout or out.stderr).strip().splitlines()[1:]  # 首行是标题
        return {ln.strip() for ln in lines if ln.strip()}
    except Exception:
        return set()


# 同一工具在不同平台的二进制名候选（按序探测）
BINARY_CANDIDATES: dict[str, list[str]] = {
    "gs": ["gs", "gswin64c", "gswin32c"],  # Windows 上 Ghostscript 是 gswin64c
}


def find_binary(name: str) -> str | None:
    """返回可执行文件路径：按平台候选名依次探测（Windows gs → gswin64c）。"""
    for candidate in BINARY_CANDIDATES.get(name, [name]):
        path = shutil.which(candidate)
        if path:
            return path
    return None


# poppler 家族 / 其他随包工具 → 归并到 SPEC 条目（安装提示一致）
_ALIASES: dict[str, str] = {
    "pdftotext": "pdfinfo",
    "pdftoppm": "pdfinfo",
    "pdffonts": "pdfinfo",
    "pdfimages": "pdfinfo",
    "pdfdetach": "pdfinfo",
}


def require(*binaries: str) -> None:
    """确保系统二进制可用，否则抛 MissingDependencyError（含各平台安装命令）。"""
    from .errors import MissingDependencyError

    for name in binaries:
        root = _ALIASES.get(name, name)
        spec = SPEC.get(root)
        level, _, hints = spec if spec else (9, "", {})
        unlocks = UNLOCKS.get(root, ())
        if find_binary(name) is None:
            raise MissingDependencyError(name, level, hints, unlocks=unlocks)


_deps_cache: dict | None = None


def deps_summary() -> dict:
    """能力摘要（进程内缓存一次）：注入每个成功返回的 _deps 字段。"""
    global _deps_cache
    if _deps_cache is None:
        deps = probe_all()
        _deps_cache = {
            "level": _capability_level_from_deps(deps),
            "missing": [d.name for d in deps if not d.found],
        }
    return dict(_deps_cache)


def probe_snapshot() -> dict:
    """依赖快照（给 CLI/脚本 JSON 输出用）。"""
    deps = probe_all()
    return {
        "capability_level": _capability_level_from_deps(deps),
        "missing": [d.name for d in deps if not d.found],
        "dependencies": [d.as_dict() for d in deps],
    }


def capability_level() -> int:
    """当前可用能力级别：所有 ≤N 级依赖齐备时的最大 N。"""
    deps = probe_all()
    return _capability_level_from_deps(deps)


def _capability_level_from_deps(deps: list[Dependency]) -> int:
    level = -1
    for lv in range(max(d.level for d in deps) + 1):
        if all(d.found for d in deps if d.level <= lv):
            level = lv
    return level


if __name__ == "__main__":
    import contextlib
    import sys

    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(Exception):
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    for dep in probe_all():
        mark = "✅" if dep.found else "❌"
        ver = dep.version or dep.error or ""
        print(f"{mark} L{dep.level} {dep.name:10s} {ver}")
        if dep.unlocks:
            print(f"      unlocks: {', '.join(dep.unlocks)}")
        if not dep.found:
            print(f"      install: {dep.install}")
    print(f"\n当前能力级别: L{capability_level()}")
