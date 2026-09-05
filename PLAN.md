# pdf-toolbox-mcp 实施计划

> 本地、免费、隐私优先的 PDF 处理 MCP server —— OCRmyPDF + Poppler + qpdf 重引擎封装
>
> 状态：**工程完成，待发布**（2026-09-06 终态，见 §13）｜ 历史：v1.2 定位修正（读向拥挤→处理管线）；v1.1 M-1 验证闸门
>
> v1.2 变更：第二轮调研修正定位——读取向已拥挤（Citra 916★ 等），差异化收窄为"处理/输出管线"；卡位表、M-1a 状态同步更新（证据：docs/competitor-matrix.md）
> v1.1 变更：新增 M-1 验证阶段与修正版里程碑；M1 收缩为 P1a 四工具；P1 拆分为 P1a/P1b 两批；M-1 通过标准对齐 RESEARCH.md §6 门槛

---

## 1. 项目定位

**一句话**：给 AI 代理（Claude Desktop / Claude Code / Cursor / ChatGPT 等）提供一套完全本地运行的 PDF 处理能力：扫描件 OCR、版面级文本提取、页面级渲染（喂给视觉模型）、页面手术、加密权限、脱敏发布。

**卡位逻辑**（调研结论，2026-09）：

| 现有方案 | 缺陷 | 本项目 |
|---|---|---|
| 云 SaaS MCP（PSPDFKit / ComPDFKit / KDAN） | 收费、文件必须上传 | 纯本地，文件不出机器 |
| 读取向 MCP（Citra 916★、jztan/pdf-mcp 130★、ODA 153★） | 只解决"AI 看 PDF"：无 OCR 写回可搜索产物、无加密/压缩 | 处理/输出管线：OCRmyPDF 写回 + qpdf 手术 + 加密压缩 |
| pypdf 系轻量 MCP（pdfmux 等） | 无 OCR、文本提取差、无渲染 | 重引擎：Tesseract OCR + pdftotext + pdftoppm |
| 单工具 0-star 封装（ocrmypdf-mcp ×3） | 只有 OCR 单点、无人维护 | 工具箱 + 智能路由 + 分发运营 |

**定位叙事（v1.2 修正，证据见 docs/competitor-matrix.md）**：读 PDF 给模型看已被读向头部做好，本项目做**处理与输出**——OCR 写回可搜索产物、页面手术、加密压缩、脱敏发布。一句话：*别人让 AI 读 PDF，我们让 PDF 被 AI 处理好*。加密 PDF 是比预期更硬的切入点（Claude 原生直接拒绝加密文件、ChatGPT 扫描件报 "No text could be extracted"）。

**核心差异点（必须做对的两件事）**：
1. **分发体验**：uvx 一行接入；启动自检依赖，缺什么给一行安装命令；能力分级降级而不是全有全无。
2. **智能路由**：`is_searchable` 检测 + OCR 建议 + 渲染兜底（文本层差就转图给宿主模型看）——这是 pypdf 系永远给不了的。

**命名**：`pdf-toolbox-mcp`（PyPI 名可用性待 M0 确认，备选 `pdftoolbox-mcp` / `pdfcraft-mcp`）。CLI 命令名 `pdftoolbox`。

---

## 2. 目标用户与场景

**主力**：无 shell 的 MCP 桌面客户端用户（Claude Desktop 等）。
**顺带**：不想记 CLI 参数的开发者（通过 CLI / Claude Code 使用）。

| 场景 | 典型请求 | 用到的工具 |
|---|---|---|
| 扫描件数字化（最高频） | "这份扫描合同里找违约金条款" | is_searchable → ocr_pdf → extract_text |
| 论文/资料工作流 | "把这 3 篇的第 2 章抽出来合并" | extract_text / split / merge |
| 视觉理解 | "第 4 页那个流程图讲了什么" | render_pages（返回图给宿主模型） |
| 对外分发 | "压缩到 5MB 以内发邮件"、"发之前去掉元数据和 JS" | compress / sanitize / protect |
| 真涂黑脱敏 | "把身份证号那几块涂掉再发" | redact（光栅化，底层文字物理删除） |
| 打印体检 | "这文件打印会不会缺字" | list_fonts |
| 个人归档 | "12 个月流水按月拆开" | split (every_n) |

---

## 3. 总体架构

```
┌─────────────────────── engine（纯 Python 库）───────────────────────┐
│  每个操作 = 一个纯函数：输入 dict → 输出 dict（JSON 可序列化）        │
│  内部通过 subprocess 调 qpdf/poppler/gs；ocrmypdf/pikepdf 走库调用   │
└─────────────────────────────────────────────────────────────────────┘
        │                        │                        │
  server.py（FastMCP        cli.py                  （未来可选）
  stdio，薄壳）             typer 薄壳               本地 Web UI / remote MCP
```

**原则**：
- engine 不 import 任何 MCP 框架 —— 可独立测试、可复用
- 所有工具返回**结构化 JSON**（路径、页数、耗时、警告）+ 一句话人类可读摘要
- 长任务（OCR/压缩）返回进度提示；批处理返回逐文件结果数组

---

## 4. 工具清单

### P1 — MVP（8 个工具，分两批交付）

**P1a 核心 4 工具**（M1 交付——直接验证"OCR + 提取 + 渲染"核心假设）：

| 工具 | 底层 | 关键入参 | 所需依赖 |
|---|---|---|---|
| `pdf_info` | pdfinfo + pikepdf | path | poppler |
| `extract_text` | pdftotext | path, pages?, layout?, per_page? | poppler |
| `ocr_pdf` | ocrmypdf (库调用) | path, lang?(默认 chi_sim+eng), deskew?, skip_text?, redo_ocr? | tesseract |
| `render_pages` | pdftoppm → PNG 图像块 | path, pages, dpi?(150), max_pages? | poppler |

> ✅ 决定（2026-09-05，依据竞品实测 §8.2）：`unlock_pdf` **正式进入 P1a**（user 密码即解锁、输出解密文件）。P1a 实际交付五件套。

**P1b 页面手术 4 工具**（M2 发布前补齐——同质 qpdf 封装，晚做零风险）：

| 工具 | 底层 | 关键入参 | 所需依赖 |
|---|---|---|---|
| `split_pdf` | qpdf | path, ranges \| every_n | qpdf |
| `merge_pdfs` | qpdf | paths[], outline? | qpdf |
| `rotate_pages` | qpdf | path, angle, pages | qpdf |
| `protect_pdf` / `unlock_pdf` | qpdf | path, password, permissions? | qpdf |

### P2 — 深化（+6）

| 工具 | 底层 | 说明 |
|---|---|---|
| `is_searchable` | pdftotext 文本密度 | 智能路由入口：返回建议动作 |
| `list_fonts` | pdffonts | 打印缺字体检 |
| `extract_images` | pdfimages | 抽内嵌图 |
| `extract_attachments` | pdfdetach | 抽附件 |
| `check_repair` | qpdf --check | 结构体检与修复建议 |
| `linearize` | qpdf --linearize | Web 快速加载 |
| 批量模式 | 以上工具支持目录入参 | 整目录 OCR/拆分 |

### P3 — 高级（+4）

| 工具 | 底层 | 说明 |
|---|---|---|
| `sanitize` | pikepdf + qpdf | 剥 JS/OpenAction/元数据/附件，发布版 |
| `redact` | pdftoppm 光栅化 + 遮块 | **真涂黑**：底层文字物理删除，防复制泄密 |
| `fill_form` | pikepdf | AcroForm 字段填写 |
| `compress_pdf` | ghostscript 循环试档位 | 压到目标大小（`target_mb`），打印质量可选 |
| `edit_metadata` | pikepdf | Title/Author 等 |

### 明确不做（非目标）

- ❌ 修改已有文字内容（PDF 编辑器领域）
- ❌ 破解密码（有密码才解锁）
- ❌ XFA 动态表单
- ❌ 云端 remote MCP 部署（自废"本地隐私"卖点；最多文档化内网穿透用法）
- ❌ 自建聊天客户端（平台正在免费做分发；等真实需求信号再说）

---

## 5. 依赖管理与启动自检（核心体验设计）

**Python 层**（uvx 自动装）：`fastmcp`、`ocrmypdf`、`pikepdf`、`typer`

**系统工具层**（按能力分级，缺了不崩、给出安装命令）：

| 级别 | 依赖 | 解锁的能力 | 缺失时行为 |
|---|---|---|---|
| L0（最低可用） | qpdf | split/merge/rotate/protect | 只剩 pikepdf 兜底版 info |
| L1 | poppler | extract_text/render/fonts/info | 对应工具返回安装提示 |
| L2 | tesseract + 语言包 | OCR 全家 | 同上 |
| L3（可选） | ghostscript | compress_pdf | 同上 |

- `probe.py` 启动时探测全部二进制 + tesseract 语言包，结果缓存；`server.py` 把探测结果注入每个工具的返回（`_deps` 字段）与工具描述
- 缺依赖时工具返回结构化错误：`{"error": "missing_dependency", "binary": "tesseract", "install": {"darwin": "brew install tesseract tesseract-lang", "linux": "apt install tesseract-ocr tesseract-ocr-chi-sim", "win32": "scoop install tesseract"}}`
- 配置（环境变量）：`PDF_TOOLBOX_TESS_LANG`（默认 `chi_sim+eng`）、`PDF_TOOLBOX_WORKSPACE`（沙箱根）、`PDF_TOOLBOX_GS_PATH`

---

## 6. 安全设计

1. **路径沙箱**：所有读写限制在 workspace（默认 `~/PDF-Toolbox` + 客户端传入的绝对路径白名单机制：首次访问新根目录时返回确认请求）。拒绝系统目录。
2. **覆盖保护**：任何输出会覆盖已存在文件时，需 `overwrite: true` 显式确认。
3. **危险操作清单**（qpdf decrypt、sanitize、redact、compress 有损档位）在工具描述里标注，交由宿主客户端的确认机制把关。
4. **密码不落日志**：protect/unlock 的 password 参数标记 sensitive，日志与错误信息中脱敏。
5. 页范围解析器统一实现（`1-3,5,8-`），全部工具复用，杜绝注入到 shell —— **所有 subprocess 调用一律 list 参数，禁止 shell=True**。

---

## 7. 许可证合规

| 组件 | 许可证 | 使用方式 | 合规结论 |
|---|---|---|---|
| 本项目代码 | MIT | — | — |
| ocrmypdf / pikepdf | MPL-2.0 | 库依赖 | 文件级 copyleft，不传染 MIT 项目 ✅ |
| qpdf | Apache-2.0 | subprocess | ✅ |
| tesseract | Apache-2.0 | subprocess | ✅ |
| poppler (GPL-2.0) | subprocess 独立进程聚合 | 不传染 ✅（ffmpeg MCP 同款模式） |
| ghostscript (AGPL) | subprocess，可选 | 独立进程调用、不修改其源码 ✅；README 注明 |

> 修正早前讨论：ocrmypdf 现为 MPL-2.0（早年才是 GPLv3），可放心作库依赖。

---

## 8. 项目结构

```
pdf-toolbox-mcp/
├── pyproject.toml          # uv/hatch；console_scripts: pdftoolbox, pdf-toolbox-mcp
├── README.md               # 双语；安装矩阵；uvx 快速开始
├── LICENSE                 # MIT
├── src/pdf_toolbox/
│   ├── engine/
│   │   ├── probe.py        # 依赖探测 + 平台安装命令表
│   │   ├── sandbox.py      # 路径沙箱 + 页范围解析 + 覆盖检查
│   │   ├── meta.py         # pdf_info / is_searchable / list_fonts
│   │   ├── text.py         # extract_text
│   │   ├── ocr.py          # ocr_pdf（ocrmypypdf 库调用）
│   │   ├── pages.py        # split / merge / rotate / linearize / check
│   │   ├── render.py       # render_pages（返回 base64 图像块）
│   │   ├── secure.py       # protect / unlock / sanitize / redact
│   │   └── compress.py     # compress_pdf（gs 循环）
│   ├── server.py           # FastMCP 入口（stdio）
│   └── cli.py              # typer CLI，子命令与工具一一对应
└── tests/
    ├── fixtures/           # 生成式 fixture：pytest + reportlab 造样本
    │                       # （多页文本 PDF / 空文本扫描状 PDF / 加密 PDF / 带表单 PDF）
    ├── test_engine_*.py    # engine 纯函数单测（不依赖 MCP）
    ├── test_server.py      # MCP 工具契约测试（in-memory client）
    └── test_e2e.py         # 真实二进制端到端（按依赖分级 skipif）
```

**测试策略**：三层——engine 单测（mock subprocess）→ MCP 契约测试（FastMCP in-memory）→ e2e（本机装齐依赖后跑，CI 用 GitHub Actions matrix: macos/ubuntu-windows + apt/brew/scoop 装 L1，tesseract 可选 job）。

---

## 9. 发布与分发

1. **PyPI + uvx**：`uvx pdf-toolbox-mcp` 一行接入；GitHub Release 附安装脚本。
2. **README 安装矩阵**：三平台 × 依赖级别一张表；"最低可用 60 秒"路径（只装 qpdf 也能跑）。
3. **目录站提交清单**（逐个提 PR/表单）：
   - punkpeye/awesome-mcp-servers（PR，带 glama badge）
   - appcypher/awesome-mcp-servers
   - glama.ai、mcp.so、pulsemcp.com、mcpservers.org、mcpcursor.com
4. **内容营销一篇**：《为什么所有 PDF MCP 都做错了——本地重引擎的胜利》角度写 README 顶部对比表（云收费 / pypdf 无 OCR / 本项目）。
5. 中文渠道：少数派/V2EX/即刻 发"扫描件变可搜索"教程（目标用户在桌面端，教程是主要获客路径）。

---

## 10. 验证阶段（M-1，新增）

完整 MVP 之前先做小范围 PoC，避免把未经验证的市场假设直接变成跨平台工程。

| 阶段 | 内容 | 工作量 | 通过标准 |
|---|---|---:|---|
| M-1a 竞品复核 | 实测 15 个 PDF/MCP 项目，补齐功能和安装矩阵，快照落盘 `docs/competitor-matrix.md`（✅ 桌面轮 + 实测轮均已完成 2026-09-05：桌面覆盖 20+ 项目、实测 Citra / jztan / go-docs / ODA 四家，结论见矩阵 §8） | 0.5–1 天 | 每个项目有 URL、版本、实测结论 |
| M-1b 引擎 PoC | 四个核心操作在 macOS/Linux/Windows 验证 | 1 天 | 至少两平台安装成功并完成样本任务 |
| M-1c 客户端 PoC | 目标 MCP 客户端调用 OCR、文本和图片返回 | 0.5 天 | 三个真实场景端到端完成 |
| M-1d 样本评估 | 5–10 份脱敏中文 PDF，记录质量、耗时和失败原因 | 0.5 天 | 按 RESEARCH.md §6 四条继续门槛判定（两平台 10 分钟安装 / OCR 准确率达标 / 核心任务成功率 ≥80% / 无高危缺陷），数据写入验收记录并给出继续/终止结论 |

> **进度（2026-09-05，详见 [docs/m1-record.md](docs/m1-record.md)）**：M-1b ✅（macOS 本机 + Linux docker 两平台，OCR 写回闭环成立）；M-1c ✅ 协议层（mcp_probe 对自家 server 全通），真实客户端验收待配置；M-1d ⏳ 待中文样本与 chi_sim 语言包，不阻塞 M0。

M-1 未通过时，不扩展 P2/P3；优先解决依赖分发、协议返回类型和 OCR 质量问题。

## 11. 修正版里程碑

| 里程碑 | 内容 | 工作量（单人业余） | 完成标准 |
|---|---|---|---|
| **M0 骨架** | repo、pyproject、probe.py、sandbox.py、CI 骨架、PyPI 名确认 | 0.5–1 天 | 探测器在三平台返回正确安装命令 |
| **M1 MVP** | 先做 `pdf_info`、`extract_text`、`ocr_pdf`、`render_pages`，加 CLI 和 MCP 契约测试 | 5–8 天 | 至少两平台 e2e 通过；目标客户端完成三个真实场景 |
| **M2 发布** | 补齐 P1b 四个 qpdf 工具 ✅；README 打磨 ✅（双语+对比表）、PyPI 发布、6 个目录站提交、教程一篇（草稿 ✅） | 1–2 天 | 8 个 P1 工具全部可用 ✅（实际 9+探测）；uvx 可用（wheel 隔离验证 ✅，PyPI 待发）；awesome PR 被合并 |

> **M2 进度（2026-09-05）**：材料侧全部就绪——双语 README（含竞品对比表与安装矩阵）、教程草稿、目录站提交文案、打包验证（uv build + 隔离环境 uvx + CLI）——发版清单与教程草稿存于本地 `notes/`（未入库）。剩余三项需仓库所有者：建 GitHub 远程、`uv publish`（需 PyPI token）、目录站提交与教程投放。
| **M3 深化** | P2 分批实现 ✅（2026-09-05：is_searchable / list_fonts / extract_images / extract_attachments / check_repair+repair / linearize / batch_ocr 逐文件结果+重试+超时，17 工具，77 测试双平台） | 4–7 天 | 50 文件批处理有超时、失败重试和逐文件结果 ✅（2026-09-06 压测：50/50 成功，1.56s/文件，见 m1-record） |
| **M4 高级** | P3 实现 ✅（2026-09-06：sanitize / redact 真涂黑 / fill_form / edit_metadata / compress_pdf 档位阶梯，22 工具，92 测试双平台） | 5–10 天 | redact 后无法提取被涂内容 ✅（产物纯图像，pdftotext 全空 + 遮块像素级验证），文档明确质量损失和边界 ✅（工具描述与 README 注明"全文档光栅化、无文本层"） |

**成功信号**（前 3 个月）：awesome 收录 + 100★ + uvx 周下载 >500；用户反馈里"扫描件 OCR"占比 >50% 即验证定位。

---

## 12. 风险与对策

| 风险 | 概率 | 对策 |
|---|---|---|
| Windows poppler 安装摩擦大（无官方包） | ~~高~~ **已缓解** | ✅ 2026-09-06：CI Windows job 经 choco 装齐四依赖跑全量 94 测试通过；gs 的 gswin64c 别名、控制台码页等平台坑已修；README 安装矩阵提供 choco/scoop/winget/conda 四路 |
| 大文件 OCR 阻塞 MCP 会话超时 | 中 | ocrmypdf 走库调用 + 分批（每次 ≤N 页）；工具描述引导宿主分页调用 |
| 平台官方下场（如 Claude 出内置 PDF 工具） | 低 | 差异点在 OCR + 渲染 + 重引擎，官方内置通常只做浅层提取 |
| PyPI 名被抢 | 低 | M0 第一件事确认；备选名已列 |
| GPL 认知劝退贡献者 | 低 | README 许可证合规表直接回应 |

---

## 13. 状态收尾（2026-09-06 终态）

工程侧全部完成，项目进入发布运营阶段：

- ✅ **全部里程碑**：M-1a（竞品桌面+实测）/ M-1b（引擎两平台）/ M-1c（协议层；真实客户端验收等 API 代理恢复，命令留档 m1-record）/ M-1d（合成样本预演：干净 99%/倾斜 94%/噪点 81%）/ M0（骨架+CI+LICENSE）/ M1（P1a+P1b+结构化错误）/ M2（材料+建仓+CI 三平台）/ M3（P2 七工具）/ M4（P3 五工具+真涂黑）
- ✅ **超额项**：Windows 全量 CI（choco 真装四依赖）、redact 选择性光栅化升级、locate_text/redact_text 按内容涂黑、ruff 门禁、PyPI trusted publishing 流水线、git 直装路径实测、中文 OCR 基准与 50 文件压测
- **终态规模**：24 工具 / 105 测试 / 三平台 CI 全绿 / 双语 README / CHANGELOG / CONTRIBUTING / SECURITY / issue 模板
- **风险表**：唯一"高风险"项（Windows 安装摩擦）已降级为已缓解

**剩余事项（全部需仓库所有者操作，清单存于本地 `notes/launch-checklist.md`，未入库）**：
1. PyPI：pypi.org 注册 pending publisher（owner=twoer, repo=pdf-toolbox-mcp, workflow=release.yml）→ `git tag v0.1.0 && git push --tags`
2. M-1c 真实客户端验收：API 代理恢复后跑 m1-record 留档命令
3. M-1d 正式版：5–10 份真实脱敏中文样本复核
4. 目录站提交（六站文案已备）+ 教程投放（草稿+配图清单已备）
5. 发布后前 4 周：保持 commit 节奏与 issue 响应（glama 排序 40% 权重是 adoption）
