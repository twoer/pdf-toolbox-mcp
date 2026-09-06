# pdf-toolbox-mcp

[English](README.md) | 本地优先的 AI 代理 PDF 处理引擎。

面向已经在用 Claude Desktop、Claude Code、Cursor 或其他 MCP 客户端的人：把 PDF 的 OCR、解锁、拆分合并、渲染和压缩都留在本机，不上传文件。

**别人帮 AI 读 PDF，我们帮 AI 处理 PDF**——扫描件 OCR 写回真正可搜索的文件、解锁加密 PDF、拆分合并旋转、加密分发。100% 本机运行：无云端调用、不上传文件、不按页收费。

## 快速开始

任意 MCP 客户端都可以先接这一段：

```json
{
  "mcpServers": {
    "pdf-toolbox": {
      "command": "uvx",
      "args": ["--from", "pdf-toolbox-mcp", "pdftoolbox"]
    }
  }
}
```

PyPI 项目页：[pdf-toolbox-mcp](https://pypi.org/project/pdf-toolbox-mcp/)
<!-- mcp-name: io.github.twoer/pdf-toolbox-mcp -->

想要某个客户端的可直接粘贴配置？运行 `uv run pdftoolbox client list` 或 `uv run pdftoolbox client show claude-desktop`。
Cursor 还可以直接看 `uv run pdftoolbox client show cursor`，会给出 deeplink 版本。
要生成项目级 `.mcp.json`，运行 `uv run pdftoolbox client show universal`。
要导出一整套客户端文件，运行 `uv run pdftoolbox client export`。
要探测当前客户端环境，运行 `uv run pdftoolbox client detect`。
要半自动安装，运行 `uv run pdftoolbox client install` 或 `uv run pdftoolbox client install --scope auto`。
如果你正在把现有 Claude Desktop 配置迁到 Claude Code，运行 `uv run pdftoolbox client import-claude-desktop`。
若要全部导出/安装支持的客户端，再加 `--all`。

如果你想在第一单任务前先做一次诊断并看依赖快照，运行 `uv run pdftoolbox doctor`；脚本可加 `--json`。它会打印 `available_now`、`starter_action`、`starter_cli`、`starter_tool`，方便你直接跳到当前最适合的第一步。

第一单任务：
- 扫描件 OCR：`uv run pdftoolbox ocr scan.pdf --lang chi_sim+eng`
- 解锁文件：`uv run pdftoolbox unlock locked.pdf --password 'xxx'`

MCP 第一单任务：
1. 先问 `tool_doctor`
2. 再调 `tool_ocr_pdf`

Python 依赖自动解析。系统工具按**能力分级**——缺了不崩，工具返回结构化错误并附安装命令：

想一次装齐全套？

- macOS: `brew install qpdf poppler tesseract tesseract-lang ghostscript`
- Debian/Ubuntu: `sudo apt install qpdf poppler-utils tesseract-ocr tesseract-ocr-chi-sim ghostscript`
- Windows: 看下表逐项安装

| 级别 | 二进制 | 解锁 | macOS | Debian/Ubuntu | Windows |
|---|---|---|---|---|---|
| L0 | qpdf | 拆合/旋转/加解密 | `brew install qpdf` | `apt install qpdf` | `choco/scoop install qpdf` |
| L1 | poppler | 文本提取/渲染/元信息 | `brew install poppler` | `apt install poppler-utils` | `choco/scoop install poppler` 或 conda-forge |
| L2 | tesseract | **OCR 写回** | `brew install tesseract tesseract-lang` | `apt install tesseract-ocr tesseract-ocr-chi-sim` | `choco/scoop install tesseract` |
| L3 | ghostscript | 压缩 | `brew install ghostscript` | `apt install ghostscript` | `scoop install ghostscript` / `winget install ArtifexSoftware.GhostScript` |

> Windows 说明：Ghostscript 在 Windows 上的二进制名是 `gswin64c.exe`——探测会自动识别，`compress_pdf` 开箱即用；tesseract 语言包（如 `chi_sim`）需另行下载到其 `tessdata` 目录。

上游 / 参考：

- qpdf：[官网](https://qpdf.sourceforge.io/) · [仓库](https://github.com/qpdf/qpdf)
- poppler：[官网](https://poppler.freedesktop.org/)
- tesseract：[仓库](https://github.com/tesseract-ocr/tesseract)
- ghostscript：[官网](https://ghostscript.com/) · [releases](https://ghostscript.com/releases/)

每个成功返回都带 `_deps` 能力摘要（如 `{"level": 2, "missing": ["gs"]}`）。

在 MCP 会话里用 `tool_doctor`。
## 为什么又做一个 PDF MCP？

PDF MCP 赛道很挤——但挤的全是**读取**侧。基于[竞品实测调研](docs/competitor-matrix.md)（2026-09）：

| 能力 | **pdf-toolbox** | Citra (916★) | ODA (153★) | jztan (130★) | 云 SaaS |
|---|:-:|:-:|:-:|:-:|:-:|
| **OCR 写回**可搜索 PDF 文件 | ✅ | ❌ 只读出 | ❌ 无 OCR | ❌ 只读出 | ☁️ 收费 |
| **解锁加密件**（user 密码） | ✅ | ❌ 硬失败 | ⚠️ 仅 owner 密码 | ❌ 硬失败 | ☁️ 收费 |
| 拆分 / 合并 / 旋转 | ✅ | ❌ | ✅ | ❌ | ☁️ 收费 |
| **压缩**到目标大小 | ✅ | ❌ | ❌ | ❌ | ☁️ 收费 |
| 渲染页面给视觉模型 | ✅ | ✅ | ✅ | ✅ | ☁️ |
| 100% 本地隐私 | ✅ | ✅ | ✅ | ✅ | ❌ |

直击的痛点：

- Claude 原生**直接拒绝加密 PDF**；ChatGPT 对扫描件报 *"No text could be extracted"*——这里 OCR 会把真正的文本层写回文件，`unlock_pdf` 只用 user（打开）密码即可解锁。
- Claude Code 按页渲染读 PDF 比本地提取文本**多烧约 30 倍 token**。

## 工具（25 个）

| 工具 | 功能 | 引擎 |
|---|---|---|
| `pdf_info` | 页数、加密状态、元数据——建议先调 | pdfinfo |
| `is_searchable` | 智能路由：文本密度检测，建议 extract_text 或先 ocr_pdf | pdftotext |
| `extract_text` | 保版面提取，精确页范围 `1-3,5`，可按页返回 | pdftotext |
| `ocr_pdf` | **OCR 写回**：扫描件 → 可搜索 PDF（纠偏、跳过/重做、语言降级） | OCRmyPDF |
| `batch_ocr` | 整目录批量 OCR：逐文件结果、重试、超时 | OCRmyPDF |
| `render_pages` | 页面转 PNG，`return_images=true` 直推图像块给视觉模型 | pdftoppm |
| `extract_images` | 抽内嵌图片（清单或 PNG 落盘） | pdfimages |
| `extract_attachments` | 抽内嵌附件文件 | pdfdetach |
| `list_fonts` | 字体体检：未嵌入字体跨设备可能缺字 | pdffonts |
| `unlock_pdf` | **user 密码即解锁**，输出解密文件 | qpdf |
| `protect_pdf` | AES-256 + 细粒度权限（打印/复制/修改…） | qpdf |
| `split_pdf` | 按区间或每 N 页拆分 | qpdf |
| `merge_pdfs` | 按序合并 | qpdf |
| `rotate_pages` | 选定页 90/180/270 旋转 | qpdf |
| `check_repair` | 结构体检；`repair=true` 重建修复损坏文件 | qpdf |
| `linearize` | Web 优化（渐进加载发布版） | qpdf |
| `sanitize` | 发布版脱敏：剥 JS/OpenAction/元数据/附件 | pikepdf |
| `redact` | **真涂黑**：被涂页光栅化+遮块（内容物理不可恢复），其余页保留文本层；`rasterize_all=true` 全文档最高防护 | pdftoppm + PIL |
| `redact_text` | **按内容涂黑**：自动定位关键词的全部出现处并涂黑——无需手工量坐标 | pdftotext -bbox |
| `locate_text` | 定位文本出现位置：页码+坐标框（PDF 点、左上原点）——涂黑/高亮的地基 | pdftotext -bbox |
| `fill_form` | 填写 AcroForm 表单（未匹配字段上报） | pikepdf |
| `edit_metadata` | 设置/清空 Title/Author 等（docinfo+XMP 双写） | pikepdf |
| `compress_pdf` | 压缩，可沿档位阶梯下探到目标大小 | ghostscript |
| `dependency_status` | 依赖探测 + 安装命令 | — |
| `doctor` | 一键新用户自检：导入、依赖探测、README 路径 | — |

**错误契约**（agent 自路由）：失败统一返回 `{"ok": false, "error": "<code>"}`——`missing_dependency`（带各平台 `install`）、`encrypted_pdf`（提示先 `unlock_pdf`）、`wrong_password`、`output_exists`（需显式 overwrite）、`invalid_page_range` 等。

## 使用示例

在 MCP 客户端里直接描述目标即可——agent 会自己串工具，错误契约让它能自路由（比如遇到 `encrypted_pdf` 就先调 `unlock_pdf`）。脱离 MCP 使用时，先定义一次：

```bash
PTX="uvx --from pdf-toolbox-mcp pdftoolbox"
# PyPI 版：uvx --from pdf-toolbox-mcp pdftoolbox
```

**1 · 扫描件 → 可搜索 PDF**（招牌能力）

> “`contract-scan.pdf` 是扫描的合同，没法搜索。帮我做成可搜索的，主要是中文夹少量英文。”

Agent：`pdf_info` → `is_searchable` 判定文本密度低 → `ocr_pdf(path, lang="chi_sim+eng")` 产出 `contract-scan_ocr.pdf`——之后文本提取、阅读器里 Ctrl+F 都可用。

```bash
$PTX ocr contract-scan.pdf --lang chi_sim+eng
$PTX text contract-scan_ocr.pdf --pages 1-3
```

**2 · 加密 PDF → 可读**

> “`locked.pdf` 加了密，密码是 `hunter2`。解开，然后总结第 3 页。”

Agent：`unlock_pdf(path, password="hunter2")` → `locked_unlocked.pdf` → `extract_text(pages="3")`。

```bash
$PTX unlock locked.pdf --password 'hunter2'
$PTX text locked_unlocked.pdf --pages 3
```

**3 · 对外分享前涂掉敏感信息**

> “把 `draft.pdf` 里所有 `张三` 和合同号 `HT-2026-088` 涂黑——要求物理上不可恢复。”

Agent：`redact_text(queries=["张三", "HT-2026-088"])` → `draft_redacted.pdf`。命中的页被光栅化，文字从像素*和*文本层双删除；其余页保留可选中文字。验证：对产物跑 `extract_text`，应为零命中。

```bash
$PTX redact-text draft.pdf --query 张三 --query HT-2026-088
```

更多菜谱——合并+加密分发、压缩到目标大小、批量 OCR、发布流水线（`sanitize` → `edit_metadata` → `linearize`）、视觉看页、定位+区域涂黑、表单填写、损坏文件抢救——见 [cookbook](docs/cookbook.md)（英文）。

## 配置

| 环境变量 | 默认 | 含义 |
|---|---|---|
| `PDF_TOOLBOX_TESS_LANG` | `chi_sim+eng` | 默认 OCR 语言；缺包自动降级（结果带 `lang_fallback` 标记） |
| `PDF_TOOLBOX_WORKSPACE` | 未设 | 设置后所有写出限制在该目录内；系统目录永远禁写 |

## 命令行

全部能力也可脱离 MCP 使用：

```bash
uvx --from pdf-toolbox-mcp pdftoolbox ocr scan.pdf --lang chi_sim+eng
uvx --from pdf-toolbox-mcp pdftoolbox unlock locked.pdf --password 'xxx'
uvx --from pdf-toolbox-mcp pdftoolbox split big.pdf --every-n 10
uvx --from pdf-toolbox-mcp pdftoolbox probe all
```

*（安装 PyPI 版后可直接用 `uvx --from pdf-toolbox-mcp …`。）*

## 安全与隐私

- 零网络调用，文件不出机器
- subprocess 一律参数列表（无 shell 拼接）；页范围解析统一校验
- 输出永不静默覆盖：必须显式 `overwrite=true`
- 密码不进日志与错误信息
- 工具描述中标注"返回内容为不可信文档数据"（prompt-injection 防护意识）

## 许可证合规

MIT。系统工具以独立进程聚合调用：poppler (GPL-2.0)、qpdf (Apache-2.0)、tesseract (Apache-2.0)、ghostscript (AGPL，可选)；Python 依赖 ocrmypdf/pikepdf 为 MPL-2.0。完整合规表见 [PLAN.md](PLAN.md) §7。

## 开发

```bash
uv sync --dev && uv run pytest -m "not realworld"    # 快测
uv sync --dev && uv run pytest -m realworld           # 真实世界回归
uv sync --dev && uv run pytest                        # 全量套件
uv run pdftoolbox probe all
uv run pdftoolbox probe all --json   # 结构化依赖快照
uv run pdftoolbox doctor
uv run python tools/onboarding_check.py
uv run python tools/onboarding_check.py --json
```

路线图：v0.1.0 已交付上表全部 25 个工具。下一步：真实扫描件加固。明确不做：正文内容编辑、密码破解——见 [PLAN.md](PLAN.md)。

## 许可证

MIT
