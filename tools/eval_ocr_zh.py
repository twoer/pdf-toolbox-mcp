#!/usr/bin/env python3
"""M-1d 预演：中文 OCR 质量基准（合成样本）+ 50 文件批量压测。

真实脱敏样本到位前的评估方法学预演：
1. 用系统 CJK 字体渲染已知ground truth 的"扫描式"中文 PDF（三档：干净/噪点/倾斜）
2. ocr_pdf 写回（chi_sim+eng）→ pdftotext 提取 → 计算字符错误率 CER
3. 50 文件批量压测（M3 完成标准补漏）

用法：
  mkdir -p .tessdata
  curl -L -o .tessdata/chi_sim.traineddata https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_sim.traineddata
  curl -L -o .tessdata/eng.traineddata    https://github.com/tesseract-ocr/tessdata_fast/raw/main/eng.traineddata
  TESSDATA_PREFIX=$PWD/.tessdata uv run --python 3.12 python tools/eval_ocr_zh.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

FIXTURES = ROOT / ".fixtures" / "zh"
OUT = FIXTURES / "ocr_out"

FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",          # macOS
    "/System/Library/Fonts/STHeiti Light.ttc",      # macOS 旧
    "/System/Library/Fonts/Hiragino Sans GB.ttc",   # macOS 备选
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Linux
]

GROUND_TRUTH = """房屋租赁合同
甲方（出租方）：张三明
乙方（承租方）：李文华
第一条 房屋坐落于上海市浦东新区世纪大道100号，建筑面积为八十九平方米。
第二条 租金为每月人民币12,500元，乙方应于每月5日前支付。
第三条 若乙方逾期支付超过15日，甲方有权解除合同并要求支付违约金25,000元。
第四条 租赁期限自2026年10月1日起至2028年9月30日止。
本合同一式两份，双方签字后生效。
Contract No: SH-2026-0912"""


def _font(size: int):
    from PIL import ImageFont

    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise SystemExit(f"未找到 CJK 字体，尝试过: {FONT_CANDIDATES}")


def render_sample(out: Path, dpi: int, noise: float = 0.0, rotate: float = 0.0) -> None:
    from PIL import Image, ImageChops, ImageDraw

    W, H = int(8.27 * dpi), int(11.69 * dpi)  # A4
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    title_font = _font(int(dpi * 0.16))
    body_font = _font(int(dpi * 0.105))
    lines = GROUND_TRUTH.splitlines()
    y = int(dpi * 0.9)
    for i, line in enumerate(lines):
        font = title_font if i == 0 else body_font
        draw.text((int(dpi * 0.9), y), line, fill="black", font=font)
        y += int(dpi * (0.28 if i == 0 else 0.21))
    if noise > 0:
        noise_img = Image.effect_noise((W, H), sigma=int(255 * noise)).convert("RGB")
        img = ImageChops.overlay(img, noise_img.point(lambda p: 128 + (p - 128) // 3))
    if rotate:
        img = img.rotate(rotate, expand=False, fillcolor="white", resample=Image.BICUBIC)
    img.save(out, resolution=dpi)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return "".join(text.split())  # 去所有空白


def cer(ref: str, hyp: str) -> float:
    """字符错误率 = 编辑距离 / 参考长度。"""
    ref, hyp = normalize(ref), normalize(hyp)
    if not ref:
        return 0.0
    prev = list(range(len(hyp) + 1))
    for i, rc in enumerate(ref, 1):
        cur = [i]
        for j, hc in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rc != hc)))
        prev = cur
    return prev[-1] / len(ref)


def make_samples() -> dict[str, Path]:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    samples = {
        "v1_clean_300dpi": {"dpi": 300},
        "v2_noise_200dpi": {"dpi": 200, "noise": 0.10},
        "v3_skew_2.5deg": {"dpi": 300, "rotate": 2.5},
    }
    paths = {}
    for name, kw in samples.items():
        p = FIXTURES / f"{name}.pdf"
        if not p.exists():
            render_sample(p, **kw)
        paths[name] = p
    return paths


def run_quality() -> list[dict]:
    from pdf_toolbox.engine import ocr_pdf

    rows = []
    for name, path in make_samples().items():
        t0 = time.time()
        result = ocr_pdf(path, lang="chi_sim+eng", deskew="skew" in name,
                         output=OUT / f"{name}_ocr.pdf", overwrite=True)
        elapsed = round(time.time() - t0, 2)
        text = subprocess.run(
            ["pdftotext", result["output"], "-"],
            capture_output=True, text=True, check=True, timeout=120,
        ).stdout
        rows.append({
            "sample": name, "cer": round(cer(GROUND_TRUTH, text), 4),
            "accuracy%": round((1 - cer(GROUND_TRUTH, text)) * 100, 2),
            "seconds": elapsed,
            "lang": result["lang"], "fallback": result["lang_fallback"],
        })
    return rows


def run_batch_stress(n: int = 50) -> dict:
    from pdf_toolbox.engine import batch_ocr

    src = FIXTURES / "batch_src"
    if src.exists():
        shutil.rmtree(src)
    src.mkdir(parents=True)
    sample = make_samples()["v2_noise_200dpi"]
    for i in range(n):
        shutil.copy(sample, src / f"doc_{i:02d}.pdf")
    out = FIXTURES / "batch_out"
    t0 = time.time()
    result = batch_ocr(src, lang="chi_sim+eng", out_dir=out, overwrite=True,
                       max_retries=1)
    return {
        "files": n, "succeeded": result["succeeded"], "failed": result["failed"],
        "total_seconds": round(time.time() - t0, 1),
        "per_file_avg_s": round((time.time() - t0) / n, 2),
    }


def main() -> None:
    if not os.environ.get("TESSDATA_PREFIX"):
        raise SystemExit("请先设置 TESSDATA_PREFIX=$PWD/.tessdata（见文件头用法）")
    OUT.mkdir(parents=True, exist_ok=True)

    print("== 中文 OCR 质量基准（合成样本，ground truth 已知）==")
    print(f"{'样本':<20} {'CER':>8} {'准确率':>8} {'耗时':>7} 语言")
    for r in run_quality():
        fb = "（降级!）" if r["fallback"] else ""
        print(f"{r['sample']:<20} {r['cer']:>8.2%} {r['accuracy%']:>7.2f}% {r['seconds']:>6}s {r['lang']}{fb}")

    print("\n== 50 文件批量压测 ==")
    stats = run_batch_stress()
    print(stats)


if __name__ == "__main__":
    main()
