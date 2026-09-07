#!/usr/bin/env python3
"""Generate the synthetic PDF corpus used by the M-1d benchmark.

The content is fictional and intentionally contains no real personal data.
Generated PDFs are image-only scans so the OCR write-back path is exercised.

Example:
  uv run python tools/generate_m1d_samples.py --output-dir output/pdf
"""

from __future__ import annotations

import argparse
from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "output" / "pdf"
FONT_CANDIDATES = (
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)


def _font_path() -> Path:
    for candidate in FONT_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            return path
    raise SystemExit(f"No CJK font found; tried: {', '.join(FONT_CANDIDATES)}")


def _font(path: Path, size: int):
    return ImageFont.truetype(str(path), size=size)


def _page(title: str, subtitle: str, blocks: list[str], kind: str, page_no: int, total: int, dpi: int, font_path: Path):
    image = Image.new("RGB", (int(8.27 * dpi), int(11.69 * dpi)), "white")
    draw = ImageDraw.Draw(image)
    margin = int(dpi * 0.72)
    navy, gray, light = (27, 55, 88), (90, 100, 112), (232, 238, 245)
    draw.rectangle((0, 0, image.width, int(dpi * 0.56)), fill=navy)
    draw.text((margin, int(dpi * 0.78)), title, fill=navy, font=_font(font_path, int(dpi * 0.25)))
    draw.text((margin, int(dpi * 1.15)), subtitle, fill=gray, font=_font(font_path, int(dpi * 0.105)))
    body, small = _font(font_path, int(dpi * 0.125)), _font(font_path, int(dpi * 0.10))
    y, max_chars = int(dpi * 1.55), 35 if dpi >= 200 else 30
    for block in blocks:
        if block.startswith("HEADING:"):
            draw.text((margin, y), block[8:], fill=navy, font=_font(font_path, int(dpi * 0.16)))
            y += int(dpi * 0.34)
            continue
        if block.startswith("TABLE:"):
            rows = [row.split("|") for row in block[6:].split("\\n")]
            widths, row_h = (int(dpi * 1.5), int(dpi * 2.4), int(dpi * 1.3)), int(dpi * 0.30)
            for row_index, row in enumerate(rows):
                x = margin
                draw.rectangle(
                    (margin, y, margin + sum(widths), y + row_h),
                    fill=light if row_index == 0 else "white",
                    outline=(180, 190, 200),
                )
                for col, cell in enumerate(row):
                    draw.rectangle((x, y, x + widths[col], y + row_h), outline=(180, 190, 200))
                    draw.text(
                        (x + int(dpi * 0.08), y + int(dpi * 0.07)), cell,
                        fill=navy if row_index == 0 else (35, 40, 45), font=small,
                    )
                    x += widths[col]
                y += row_h
            y += int(dpi * 0.20)
            continue
        for line in wrap(block, width=max_chars):
            draw.text((margin, y), line, fill=(35, 40, 45), font=body)
            y += int(dpi * 0.23)
        y += int(dpi * 0.10)
    footer_y = image.height - int(dpi * 0.62)
    draw.line((margin, footer_y, image.width - margin, footer_y), fill=(200, 208, 216), width=2)
    draw.text(
        (margin, image.height - int(dpi * 0.48)),
        f"SYNTHETIC M-1d SAMPLE | {kind} | 第 {page_no}/{total} 页",
        fill=gray, font=small,
    )
    return image


def _save(path: Path, pages: list[Image.Image], dpi: int) -> None:
    first, rest = pages[0].convert("RGB"), [page.convert("RGB") for page in pages[1:]]
    first.save(path, "PDF", resolution=dpi, save_all=True, append_images=rest)


def _contract(font_path: Path, dpi: int = 220):
    return [
        _page("房屋租赁合同", "示例编号：SYN-LEASE-2026-014 | 签署日期：2026年09月07日", [
            "甲方（出租方）：星河物业管理有限公司", "乙方（承租方）：李文华（虚构样本）",
            "HEADING:第一条 房屋基本情况",
            "房屋坐落于上海市浦东新区云杉路88号，建筑面积为八十九平方米，仅用于办公及研发用途。",
            "HEADING:第二条 租赁期限与租金",
            "租赁期限自2026年10月1日起至2028年9月30日止。月租金为人民币12,500元，乙方应于每月5日前支付。",
            "HEADING:第三条 双方权利义务",
            "甲方负责主体结构维护；乙方应合理使用房屋，不得擅自转租、改变用途或存放危险物品。",
        ], "contract-clean", 1, 2, dpi, font_path),
        _page("房屋租赁合同（续）", "示例编号：SYN-LEASE-2026-014", [
            "HEADING:第四条 违约责任", "若乙方逾期支付超过15日，甲方有权解除合同并要求支付违约金25,000元。",
            "HEADING:第五条 争议解决",
            "因本合同产生的争议，双方应先友好协商；协商不成的，提交合同签署地人民法院处理。",
            "本合同一式两份，甲乙双方各执一份，双方签字或盖章后生效。",
            "甲方代表：周明远（虚构） 乙方代表：李文华（虚构）",
            "签署地点：上海市 联系编号：TEST-ONLY-7734",
        ], "contract-clean", 2, 2, dpi, font_path),
    ]


def _invoice(font_path: Path, dpi: int = 220):
    return [_page("增值税普通发票（测试样本）", "票据编号：SYN-INV-2026-0912 | 开票日期：2026年09月07日", [
        "购买方：云杉数据实验室（虚构） 纳税识别号：TEST-91310000",
        "销售方：星河信息技术有限公司（虚构） 地址：上海市示例区创新路18号",
        "TABLE:项目|规格/服务内容|金额（元）\\n"
        "文档处理服务|PDF OCR 与批量归档|4800.00\\n"
        "技术支持|季度维护与咨询|1200.00\\n合计|价税合计|6000.00",
        "价税合计（大写）：人民币陆仟元整",
        "备注：本票据仅用于 OCR 回归测试，不具备任何财务效力。",
        "校验串：INVOICE-SAMPLE-2026-0912",
    ], "invoice-clean", 1, 1, dpi, font_path)]


def _paper(font_path: Path, dpi: int = 220):
    pages = [
        ("中文文档处理性能评估", [
            "HEADING:摘要",
            "本文评估本地 PDF 处理管线在文本提取、页面渲染和 OCR 写回任务中的表现。"
            "所有数据均为合成数据，实验不包含真实个人信息。",
            "HEADING:1 实验设计",
            "我们构造三类输入：可搜索文本 PDF、整页图像扫描 PDF，以及带有倾斜和噪点的退化扫描 PDF。"
            "每类样本重复运行三次并记录中位耗时。",
            "HEADING:2 评价指标",
            "主要指标包括字符错误率（CER）、任务成功率、单页平均处理时间和输出文件完整性。"
            "结果通过 pdftotext、pdfinfo 及像素抽样复核。",
        ]),
        ("中文文档处理性能评估（续）", [
            "HEADING:3 结果摘要",
            "在干净印刷体样本上，OCR 字符准确率达到99%左右；在轻度倾斜样本上，deskew 能明显降低错误；"
            "重度噪点会造成识别边界下降。",
            "TABLE:样本|准确率|平均耗时（秒）\\n干净印刷体|99.03%|1.60\\n"
            "倾斜 2.5 度|93.69%|2.20\\n噪点扫描|81.07%|1.30",
            "HEADING:4 讨论",
            "输出采用临时文件或临时目录生成，成功后才发布；已有目标默认不会被覆盖。该行为用于降低批处理失败时的部分产物风险。",
        ]),
        ("中文文档处理性能评估（结论）", [
            "HEADING:5 结论与限制",
            "本报告仅用于 M-1d 方法学演练。合成字体、版面和噪声分布不能替代真实扫描材料；"
            "正式验收仍需经用户脱敏后的合同、票据和论文样本复核。",
            "复现实验：使用 chi_sim+eng 语言包，记录输入摘要、工具调用顺序、输出页数、CER、耗时和失败原因。",
            "结束标记：SYNTHETIC-REPORT-END-2026",
        ]),
    ]
    return [
        _page(title, "技术报告编号：SYN-PAPER-2026-03", blocks, "paper-clean", i, 3, dpi, font_path)
        for i, (title, blocks) in enumerate(pages, 1)
    ]


def _degrade(pages: list[Image.Image], mode: str):
    result = []
    for page in pages:
        if mode == "lowres":
            small = page.resize((page.width // 3, page.height // 3), Image.Resampling.BOX)
            result.append(small.resize(page.size, Image.Resampling.BILINEAR))
        elif mode == "skew":
            result.append(page.rotate(2.5, resample=Image.Resampling.BICUBIC, expand=False, fillcolor="white"))
        else:
            noise = Image.effect_noise(page.size, 34).convert("L")
            noisy = Image.blend(page, ImageOps.colorize(noise, (170, 170, 170), (255, 255, 255)), 0.20)
            result.append(ImageEnhance.Contrast(noisy).enhance(1.12).filter(ImageFilter.GaussianBlur(radius=0.25)))
    return result


def generate(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    font_path = _font_path()
    contract, invoice, paper = _contract(font_path), _invoice(font_path), _paper(font_path)
    jobs = [
        ("m1d_contract_clean.pdf", contract, 220),
        ("m1d_invoice_clean.pdf", invoice, 220),
        ("m1d_paper_clean.pdf", paper, 220),
        ("m1d_contract_lowres.pdf", _degrade(contract, "lowres"), 150),
        ("m1d_invoice_skewed.pdf", _degrade(invoice, "skew"), 220),
        ("m1d_paper_noisy.pdf", _degrade(paper, "noise"), 220),
        ("m1d_mixed_clean_noisy.pdf", [contract[0], _degrade(invoice, "noise")[0]], 220),
        ("m1d_mixed_lowres_skew_clean.pdf", [_degrade(paper, "lowres")[0], _degrade(paper, "skew")[1], paper[2]], 150),
    ]
    paths = []
    for name, pages, dpi in jobs:
        path = output_dir / name
        _save(path, pages, dpi)
        paths.append(path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    for path in generate(args.output_dir):
        print(path)


if __name__ == "__main__":
    main()
