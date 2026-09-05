"""pdf-toolbox engine：本地 PDF 处理核心（不依赖任何 MCP 框架）。

分层（PLAN.md §3）：
- engine.*  纯函数核心，subprocess 调 qpdf/poppler/gs，ocrmypdf/pikepdf 走库调用
- cli       typer 薄壳
- server    FastMCP 薄壳（stdio）
"""

__version__ = "0.1.0"
