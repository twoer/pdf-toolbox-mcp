# MCP 空白调研：主流 CLI 工具的 MCP 覆盖情况

> 调研时间：2026-09-05
> 目的：为"选一个主流但还没有像样 MCP 的 CLI 工具，自己写对应 MCP"提供选题依据
> 结论：选定 **本地 PDF 工具箱**（OCRmyPDF + Poppler + qpdf），详见 PLAN.md

---

## 1. 调研方法

- **awesome 清单全文比对**：punkpeye/awesome-mcp-servers（3939 行，最大收录）+ appcypher/awesome-mcp-servers（532 行），对 40+ 个候选工具逐一 grep
- **GitHub Search API**：`«工具名»+mcp` 按 star 排序，取 top 结果核对 star 数与最近推送时间
- **MCP 目录站交叉验证**：glama.ai、mcp.so、mcpservers.org、pulsemcp.com
- **判档标准**：
  - **NONE** — 未找到任何实现
  - **WEAK** — 存在但 <100★ / 停更 / 功能极窄
  - **STRONG** — 官方出品或 200★+ 且活跃

## 2. 覆盖情况总表

### 2.1 已饱和（不要碰）

| 工具 | 证据 |
|---|---|
| ffmpeg | 218★ / 146★ / 138★ / 119★ 至少四个活跃实现（hyepartners-gmail/vibevideo-mcp 等） |
| yt-dlp | kevinwatt/yt-dlp-mcp 278★，另有多个衍生 |
| homebrew | **官方内置** `brew mcp-server`（docs.brew.sh/MCP-Server） |
| ansible | **Red Hat 官方** AAP MCP Server + VS Code 扩展内置 |
| nmap | 生态极丰富，且被 cyproxio/mcp-for-security（631★）、FuzzingLabs/mcp-security-hub（779★）两大合集收录 |
| wireshark/tshark | bx33661/Wireshark-MCP 227★ 活跃 |
| inkscape | 三个 50★+ 活跃实现（inkmcp 67★ 等） |
| duckdb / pandoc / calibre / taskfile / graphviz 生态 | 均有像样覆盖（pandoc：vivekVells/mcp-pandoc；calibre：trieloff/calibre-mcp 49★；taskfile：mcp-taskfile-server 13★） |

### 2.2 存在空白（按"值得做"排序）

| 工具 | 自身热度 | 现有最好 MCP | 备注 |
|---|---|---|---|
| **本地 PDF 工具箱（ocrmypdf+poppler+qpdf）** | PDF 事实标准 | pypdf 系轻量实现若干，**重引擎路线零覆盖** | ✅ 最终选题 |
| aria2 | ★41.9k | kinmeic/aria2-mcp 1★ | 自带 JSON-RPC daemon，MCP 是薄适配层；下载是长时有状态操作 |
| OCRmyPDF（单独） | ★34.7k | 3 个 0★ 仓库 | 并入 PDF 工具箱选题 |
| jujutsu (jj) | ★31.4k | kmarxican/jj-mcp 1★（2026-09 刚建） | 受众全是 CLI 重度玩家，自带 shell，MCP 增量存疑 |
| rclone | ★70k+ | rclone-ui/rclone-mcp 10★ | `rclone rc` 是现成 API；云盘管理是无 shell 用户真实需求 |
| hyperfine | ★28.8k | 零结果 | 受众窄（开发者自带 shell） |
| exiftool | 极常用 | vgribok/exiftool-mcp-server 3★ | 照片整理场景真实但受众窄 |
| sox / handbrake / mkvtoolnix | 主流 | 0–6★ 或没有 | 与 ffmpeg MCP 场景重叠 |
| restic / borg | 主流 | 2★ / 0★ | 备份领域不适合 AI 即兴发挥 |
| sops / age | 主流 | 0★（2026-06 新建） | AI agent 管 secrets 是热点，但安全敏感 |
| certbot / vagrant / tcpdump / newsboat / csvkit / qpdf(单) / ghostscript(单) | — | 无专属实现 | 工具偏窄或场景已被邻近工具覆盖 |

### 2.3 PDF MCP 现有格局（选题直接依据）

awesome 清单 PDF 相关约 90 处提及，独立 server 14 个，路线只有三种：

1. **云 SaaS 封装**：PSPDFKit 两个商业 server、pdfspark —— 收费 + 文件必须上传
2. **生成型**：md-to-pdf、filetopdf —— 把别的格式转成 PDF，不处理已有 PDF
3. **pypdf 系轻量**：pdfmux、pdf-toolkit 等 —— 无 OCR、文本提取差、无页面渲染

**第一轮结论**（仅 awesome 清单视野）：没有任何一个走"本地重引擎"路线（OCR + 版面级提取 + 渲染给视觉模型）。

> **⚠️ 第二轮修正（同日，GitHub 系统检索 10 组查询 + 5 个目录站，详见 [docs/competitor-matrix.md](docs/competitor-matrix.md)）**：上述结论在读取向被证伪——Citra（SylphxAI/pdf-reader-mcp，916★）、jztan/pdf-mcp（130★）等已做到"本地 + OCR + 页面渲染给模型看"，读取向拥挤且头部近千星。**修正后的空白口径："本地 + OCR 写回可搜索 PDF + 拆分合并 + 加密 + 压缩"的组合在全部检索结果中为零**——处理/输出管线仍是空白，本选题按此收窄定位（不做读取/证据向功能，避免与头部正面竞争）。

## 3. 分析结论

### 3.1 为什么有空白

1. **供需错位**：写 MCP 的是程序员（不碰扫描合同），被扫描件折磨的用户不会写 MCP；生态第一批全是开发者工具
2. **路径依赖**：Python 开发者本能 `pip install pypdf`（零外部依赖），而 poppler/qpdf/tesseract 是外部二进制，跨平台分发劝退（Windows 无官方 poppler 包）
3. **分发经济学**：MCP 目录按安装摩擦排序，纯 Python/JS 封装永远排在"要装三个系统依赖"前面 → 劣币驱逐良币 → 后人一搜"PDF MCP 一大堆"就不做了
4. **生态年轻**：MCP 协议 2024-11 才发布，重组合品类最晚被覆盖
5. **GPL 顾虑**（认知误区）：poppler GPL-2.0 让人绕道，实际 subprocess 聚合不传染；ocrmypdf 现为 MPL-2.0 更无问题

### 3.2 选题过滤器：目标客户端有没有 shell

- **Claude Code / Cursor 等编码代理自带 shell** → 一次性命令类工具（hyperfine、jj、mise、jq 类）做 MCP 是重复建设
- **Claude Desktop / ChatGPT 桌面端无 shell** → 普通用户的本地文件需求只有 MCP 一条路，这才是增量市场
- 适合 MCP 的 CLI 特征：**有状态、长时运行、输出结构化**（aria2 满分）或**面向无 shell 人群的日常刚需**（PDF 满分）

### 3.3 最终决策

**本地 PDF 工具箱（处理/输出管线口径）** > aria2 > rclone。理由：需求频率最高（扫描件数字化是对普通用户最高频的本地文件需求）、处理/输出管线零覆盖（读向已有 Citra/jztan 强竞品，但"OCR 写回 + 拆合 + 加密 + 压缩"的本地组合为零，见 §2.3 第二轮修正）、隐私卖点最纯粹（零云依赖，且 Claude 原生拒绝加密 PDF、ChatGPT 扫描件直接报错、Claude Code 读 PDF 多烧 30 倍 token——原生短板即刚需）。aria2 作为备选保留（工程最顺：JSON-RPC 现成）。

PSPDFKit 专门为 MCP 出两个商业 server，证明"AI 代理处理 PDF"需求已被商业验证——赢法不是"再写一个 PDF MCP"，而是把**分发**（uvx + 启动自检 + 分级降级）和**智能路由**（is_searchable → OCR → 渲染兜底）做对。

## 4. 命名验证（2026-09-05）

- PyPI：`pdf-toolbox-mcp` ✅ 可用（`pdf-toolbox` 被占用；pdftoolbox / pdfcraft-mcp / pdfsmith-mcp / pdf-lab-mcp / pdfpress-mcp 均可用作备选）
- GitHub：`pdf-toolbox-mcp` 精确同名仓库 0 个

## 5. 证据边界与待验证假设

本报告是选题筛选，不是完整市场规模或竞争情报报告。以下判断目前只能视为假设：

- “本地重引擎路线零覆盖”需要对候选仓库逐个实测后才能成立；awesome 清单未收录不等于不存在。
- “扫描件数字化是普通用户最高频需求”尚无用户访谈、搜索量、下载量或任务日志支撑。
- GitHub star、目录站收录和最后提交时间只能作为代理指标，不能直接代表活跃用户数或产品质量。
- “PDF 事实标准”“隐私卖点最纯粹”等表述应在对比矩阵和用户反馈后再定稿。

正式决策前应保存一份可复核的竞品快照：查询日期、搜索语句、仓库 URL、star、最近提交、支持的操作、安装步骤、OCR/渲染实测结果和排除理由。对 `ocrmypdf-mcp`、`pdfmux`、`pdf-toolkit` 等项目应优先做实测，而不是只依据 README 或目录收录。

## 6. 选题验证阶段（新增）

在投入完整 MVP 前，先完成一个 1–2 天的验证包：

1. 建立至少 15 个实际 PDF/MCP 项目的竞品矩阵，并复核本报告的“零覆盖”结论。
2. 在 macOS、Linux、Windows 各跑通 `pdf_info`、`extract_text`、`ocr_pdf`、`render_pages` 的最小 PoC。
3. 使用 5–10 份脱敏的中文扫描合同、票据和论文测试 OCR 准确率、耗时、文件大小和失败原因。
4. 在至少一个目标客户端中真实调用 MCP，确认图片内容块、错误返回和长任务超时行为。
5. 记录安装成功率、首个任务完成率和用户愿意重复使用的场景；未达到门槛时收缩范围或更换选题。

建议的继续开发门槛：三平台至少两平台可在 10 分钟内完成安装；核心样本 OCR 字符准确率达到可接受水平（先定义样本和算法）；核心任务成功率达到 80% 以上；不存在会泄露文件或密码的高危缺陷。

## 7. 主要来源

- [punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) / [appcypher/awesome-mcp-servers](https://github.com/appcypher/awesome-mcp-servers)
- [kinmeic/aria2-mcp](https://github.com/kinmeic/aria2-mcp) · [rclone-ui/rclone-mcp](https://github.com/rclone-ui/rclone-mcp) · [kmarxican/jj-mcp](https://github.com/kmarxican/jj-mcp) · [wuzhuoyan/ocrmypdf-mcp](https://github.com/wuzhuoyan/ocrmypdf-mcp)（各空白的最好现有实现）
- [hyepartners-gmail/vibevideo-mcp](https://github.com/hyepartners-gmail/vibevideo-mcp)（ffmpeg 生态饱和证据）
- [Homebrew MCP 官方文档](https://docs.brew.sh/MCP-Server) · [Red Hat AAP MCP 公告](https://www.redhat.com/en/blog/it-automation-agentic-ai-introducing-mcp-server-red-hat-automation-platform)（官方下场证据）
- [cyproxio/mcp-for-security](https://github.com/cyproxio/mcp-for-security) · [FuzzingLabs/mcp-security-hub](https://github.com/FuzzingLabs/mcp-security-hub)（安全合集收录证据）
- PSPDFKit MCP servers（云商业路线证据，见 awesome 清单）
- GitHub Search API（各仓库 star 数与推送时间，2026-09-05 快照）
