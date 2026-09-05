#!/usr/bin/env python3
"""生成 M-1a 竞品实测用的 PDF 样本（M1 阶段复用为测试 fixture）。

产物（输出到 .fixtures/）：
- text.pdf       3 页文本 PDF，含可搜索标记串
- scanned.pdf    图像式"扫描件"（无文本层），同一标记串画在图上
- encrypted.pdf  text.pdf 的 AES-256 加密版（密码 pdf-toolbox-test）

用法：uv run --python 3.12 --with fpdf2 --with pillow --with pikepdf tools/make_fixtures.py
"""

from pathlib import Path

MARKER = "PDF-TOOLBOX-TEST-7734"
OUT = Path(__file__).resolve().parent.parent / ".fixtures"


def make_text_pdf() -> Path:
    from fpdf import FPDF

    pdf = FPDF()
    for i in range(1, 4):
        pdf.add_page()
        pdf.set_font("Helvetica", size=16)
        pdf.cell(text=f"Sample Page {i}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=11)
        pdf.multi_cell(
            w=0,
            text=(
                f"This is page {i} of the pdf-toolbox-mcp competitor test fixture.\n"
                f"Marker string: {MARKER}\n"
                "The quick brown fox jumps over the lazy dog."
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )
    path = OUT / "text.pdf"
    pdf.output(path)
    return path


def make_scanned_pdf() -> Path:
    from PIL import Image, ImageDraw, ImageFont

    font_big = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 28)
    font_small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 18)
    pages = []
    for i in range(1, 3):
        img = Image.new("RGB", (1240, 1754), "white")  # A4 @150dpi
        d = ImageDraw.Draw(img)
        d.text((80, 80), f"Scanned Page {i}", fill="black", font=font_big)
        d.text((80, 160), f"Marker string: {MARKER}", fill="black", font=font_small)
        d.text((80, 200), "The quick brown fox jumps over the lazy dog.", fill="black", font=font_small)
        pages.append(img)
    path = OUT / "scanned.pdf"
    pages[0].save(path, save_all=True, append_images=pages[1:], resolution=150)
    return path


def make_encrypted_pdf(src: Path) -> Path:
    import pikepdf

    path = OUT / "encrypted.pdf"
    # user 和 owner 必须都显式设置：只设 user 会生成"仅限制型"加密（空密码可开），测不出真加密行为
    with pikepdf.open(src) as pdf:
        pdf.save(
            path,
            encryption=pikepdf.Encryption(
                user="pdf-toolbox-test", owner="pdf-toolbox-owner", R=6
            ),
        )
    return path


def main() -> None:
    OUT.mkdir(exist_ok=True)
    t = make_text_pdf()
    s = make_scanned_pdf()
    e = make_encrypted_pdf(t)
    for p in (t, s, e):
        print(f"OK  {p}  {p.stat().st_size} bytes")


if __name__ == "__main__":
    main()
