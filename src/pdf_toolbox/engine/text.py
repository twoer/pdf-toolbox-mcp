"""extract_text：版面级文本提取（pdftotext，L1）。多区间精确提取（逐区间调用后拼接）。"""

from __future__ import annotations

import html as _html
import re as _re
import subprocess
import unicodedata as _unicodedata
from pathlib import Path

from .pages import _page_count
from .probe import require
from .sandbox import (
    assert_readable,
    ensure_pdf,
    flatten_pages,
    group_consecutive,
    parse_pages,
)


def _pdftotext(args: list[str]) -> str:
    proc = subprocess.run(
        ["pdftotext", "-enc", "UTF-8", *args],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"pdftotext 失败: {proc.stderr.strip()[:300]}")
    return proc.stdout


def extract_text(
    path: str | Path,
    pages: str | None = None,
    layout: bool = False,
    per_page: bool = False,
) -> dict:
    """提取文本。pages 形如 '1-3,5'（精确页，重叠自动去重）；layout 保版面；per_page 返回 {页号: 文本}。

    换页符 \\f 是 pdftotext 的天然页分隔符，per_page 借助它切分。
    """
    pdf = assert_readable(ensure_pdf(Path(path)))
    require("pdftotext")
    style = ["-layout"] if layout else []

    if not pages:
        text = _pdftotext([*style, str(pdf), "-"])
        if per_page:
            page_map = {i + 1: c.strip() for i, c in enumerate(text.split("\f")) if c.strip()}
            return {"path": str(pdf), "per_page": page_map, "total_chars": len(text)}
        return {"path": str(pdf), "text": text.strip(), "total_chars": len(text)}

    ranges = parse_pages(pages)
    # 精确页集合 → 连续区间分组，每区间一次调用（页数多时平衡精度与调用次数）
    unique = flatten_pages(ranges)
    page_map: dict[int, str] = {}
    for a, b in group_consecutive(unique):
        out = _pdftotext([*style, "-f", str(a), "-l", str(b), str(pdf), "-"])
        for i, chunk in enumerate(out.split("\f")):
            if chunk.strip():
                page_map[a + i] = chunk.strip()

    if per_page:
        return {"path": str(pdf), "per_page": page_map, "total_chars": sum(len(v) for v in page_map.values())}

    text = "\n".join(page_map[p] for p in sorted(page_map))
    return {"path": str(pdf), "text": text, "total_chars": len(text)}


# ---------------------------------------------------------------------------
# locate_text：文本 → 坐标（pdftotext -bbox），redact_text 的地基
# ---------------------------------------------------------------------------

# 单遍扫描：<page> 开新页；<word ...>text</word> 收词（坐标 PDF 点、左上原点）
_TOKEN_RE = _re.compile(
    r'(?P<page><page\b[^>]*>)'
    r'|<word xMin="(?P<xm>[\d.]+)" yMin="(?P<ym>[\d.]+)" '
    r'xMax="(?P<xM>[\d.]+)" yMax="(?P<yM>[\d.]+)">(.*?)</word>'
)


def _norm_for_match(s: str) -> str:
    """匹配归一化：NFKC + 去所有空白——CJK 无分词、英文跨词匹配统一处理。"""
    return "".join(_unicodedata.normalize("NFKC", s).split())


def _bbox_words(pdf: Path, pages: list[tuple[int, int]] | None) -> list[dict]:
    """运行 pdftotext -bbox，返回按页分组的词列表（坐标为 PDF 点、左上原点）。"""
    cmd = ["pdftotext", "-bbox", "-enc", "UTF-8"]
    if pages:
        first = min(a for a, _ in pages)
        last = max(b for _, b in pages)
        cmd += ["-f", str(first), "-l", str(last)]
    cmd += [str(pdf), "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        raise RuntimeError(f"pdftotext -bbox 失败: {proc.stderr.strip()[:300]}")

    result: list[dict] = []
    current: dict | None = None
    for m in _TOKEN_RE.finditer(proc.stdout):
        if m.group("page"):
            if current is not None:
                result.append(current)
            current = {"words": []}
        elif current is not None:
            current["words"].append(
                {
                    "text": _html.unescape(m.group(6)),
                    "x": float(m.group("xm")), "y": float(m.group("ym")),
                    "x2": float(m.group("xM")), "y2": float(m.group("yM")),
                }
            )
    if current is not None:
        result.append(current)
    return result


def locate_text(
    path: str | Path,
    query: str,
    pages: str | None = None,
    max_results: int = 50,
) -> dict:
    """定位文本出现的页面与坐标框（PDF 点、左上原点）——redact/高亮的地基。

    匹配按 NFKC 归一化去空白进行：中文无分词、英文跨词（'quick brown'）均可命中。
    """
    pdf = assert_readable(ensure_pdf(Path(path)))
    require("pdftotext")

    total = _page_count(pdf)
    ranges = parse_pages(pages, max_pages=total) if pages else [(1, total)]
    page_offset = min(a for a, _ in ranges)

    needle = _norm_for_match(query)
    if not needle:
        raise ValueError("query 归一化后为空")

    pages_data = _bbox_words(pdf, ranges)
    matches: list[dict] = []
    for pi, page in enumerate(pages_data):
        page_no = page_offset + pi
        # 按行聚类（yMin 相近 ±2pt），匹配只发生在行内——避免跨行的错误联合框
        lines: list[list[dict]] = []
        for w in page["words"]:
            if lines and abs(w["y"] - lines[-1][0]["y"]) <= 2.0:
                lines[-1].append(w)
            else:
                lines.append([w])
        for line in lines:
            hay = ""
            char_map: list[int] = []  # hay 中每个字符 → line 中的词下标
            for wi, w in enumerate(line):
                norm = _norm_for_match(w["text"])
                hay += norm
                char_map.extend([wi] * len(norm))
            start = 0
            while True:
                idx = hay.find(needle, start)
                if idx < 0:
                    break
                w_lo, w_hi = char_map[idx], char_map[idx + len(needle) - 1]
                span = line[w_lo : w_hi + 1]
                x = min(s["x"] for s in span)
                y = min(s["y"] for s in span)
                x2 = max(s["x2"] for s in span)
                y2 = max(s["y2"] for s in span)
                snippet = "".join(_norm_for_match(s["text"]) for s in line)[
                    max(0, idx - 10) : idx + len(needle) + 10
                ]
                matches.append(
                    {
                        "page": page_no,
                        "text": query,
                        "x": round(x, 2), "y": round(y, 2),
                        "w": round(x2 - x, 2), "h": round(y2 - y, 2),
                        "context": snippet,
                    }
                )
                if len(matches) >= max_results:
                    return {"path": str(pdf), "query": query, "count": len(matches), "matches": matches}
                start = idx + len(needle)
    return {"path": str(pdf), "query": query, "count": len(matches), "matches": matches}
