# PDF MCP 竞品矩阵（M-1a 桌面轮）

> 日期：2026-09-05（第二轮调研）
> 方法：GitHub Search API 10 组查询（pdf+mcp / pdf-mcp / topic:mcp+pdf / ocr+mcp / ocrmypdf / poppler+mcp / qpdf+mcp 等，sort=stars）+ 5 个目录站盘点（glama.ai / mcp.so / pulsemcp / mcpservers.org / mcpcursor）+ 需求侧证据（Reddit / HN Algolia / 高星仓库 Issues）+ 官方文档核对原生能力
> 状态：**桌面轮完成**；实测轮（安装并运行 top 3–5）待做
> 关键负面结果：GitHub 上不存在 OCRmyPDF 封装 MCP、不存在 qpdf 封装 MCP（Sohaib-2 间接用 qpdf）；poppler 封装仅 2 个 0★ 项目

---

## 1. 核心结论：假设修正

**原假设"本地 + OCR + 渲染零覆盖"——被证伪（读取方向）**。至少 3 家满足：Citra（916★）、jztan/pdf-mcp（130★）、pdf-decompiler-mcp（17★）。

**修正后的空白（仍然成立）**：把"渲染"定义为"给 vision model 看的 PNG"后，读取向已拥挤；但——

> **整个检索结果中，"本地 + OCR 写回可搜索 PDF + 拆分合并 + 加密 + 压缩"的组合为零。**

各竞品只占一角：Citra/jztan 占"读向三件套"（无输出管线）；Open-Document-Alliance 占"本地编辑/拆合/渲染"（无 OCR，依赖 pdf.js 文本层）；Sohaib-2 占"qpdf 加密压缩"（无 OCR/渲染，15★ 停更）；ComPDFKit/PSPDFKit/KDAN 占"全能力"（但全云端收费）。

**定位修正**：从"PDF 工具箱零覆盖" → **"读取向已拥挤（头部近千星），本地重引擎处理/输出管线仍是空白"**。

## 2. A 类矩阵：本地处理向项目（按 star 排序）

| 项目 | ★ | 推送 | 技术路线 | OCR | 提取 | 渲染 | 拆合 | 加密 | 压缩 | 安装 |
|---|---:|---|---|---|---|---|---|---|---|---|
| [SylphxAI/pdf-reader-mcp](https://github.com/SylphxAI/pdf-reader-mcp)（Citra） | 916 | 2026-09-04 | 自研 Rust 引擎 | ✅ | ✅ | ✅ 裁剪/页级 | — | — | — | npx |
| [Open-Document-Alliance/PDF-Tools](https://github.com/Open-Document-Alliance/PDF-Tools) | 153 | 2026-09-05 | pdf-lib + pdfjs + napi-canvas | — | ✅ | ✅ | ✅ | —（可选云签） | ? | .mcpb/node |
| [jztan/pdf-mcp](https://github.com/jztan/pdf-mcp) | 130 | 2026-09-05 | pypdfium2+pdfplumber+pytesseract+fastembed | ✅ | ✅ | ✅ PNG | — | — | — | pip |
| [Kentucky-ai/opentakeoff](https://github.com/Kentucky-ai/opentakeoff) | 111 | 2026-09-05 | 浏览器 canvas（垂直：建筑图纸测量） | ? | 部分 | ✅ | — | — | — | npx |
| [NameetP/pdfmux](https://github.com/NameetP/pdfmux) | 81 | 2026-09-02 | PyMuPDF/RapidOCR/Docling/Surya 多后端 | ✅ | ✅ | — | — | — | — | pip |
| [I-CAN-hack/pdf-mcp](https://github.com/I-CAN-hack/pdf-mcp) | 77 | 2026-07-30 | PyMuPDF | — | ✅ | ✅ | — | — | — | uvx |
| [hanweg/mcp-pdf-tools](https://github.com/hanweg/mcp-pdf-tools) | 76 | 2024-12-22 ⚠️停更 | PyPDF2 | — | ✅ | — | ✅ | — | — | clone |
| saury1120/pdf-mcp | 49 | 2025-04-07 | PyMuPDF+torch | ? | ✅ | — | — | — | — | clone |
| trafflux/pdf-reader-mcp | 47 | 2025-02-20 | PyPDF2（reader/RAG 向） | — | ✅ | — | — | — | — | docker |
| FutureUnreal/mcp-pdf2md | 35 | 2025-03-25 | PDF→MD | ? | ✅ | — | — | — | — | ? |
| gpetraroli/mcp_pdf_reader | 32 | 2025-07-18 | Node reader | — | ✅ | — | — | — | — | npx |
| danielkennedy1/pdf-tools-mcp | 31 | 2025-05-17 | PyMuPDF | — | ✅ | ✅ | 部分（长图合并） | — | — | uvx |
| m13253/pdflens-mcp | 20 | 2026-06-05 | Rust reader（README 404） | ? | ? | ? | ? | ? | ? | ? |
| [noobieisgod/pdf-decompiler-mcp](https://github.com/noobieisgod/pdf-decompiler-mcp) | 17 | 2026-08-04 | PDF.js + 系统 Tesseract | ✅ | ✅ | ✅ | — | — | — | node |
| **Sohaib-2/pdf-mcp-server** | 15 | 2025-07-05 ⚠️停更 | **CLI：PDFtk + qpdf（唯一 qpdf 路线）** | — | ✅ | — | ✅ | ✅ AES-256 | ✅ | pip |
| vlad-ds/pdf-agent-mcp | 14 | 2025-07-20 | Node | ✅ | ✅ | ✅ | — | — | — | node |
| jpwebb/pdftotext-mcp | 0 | 2025-07-11 | **poppler pdftotext 封装** | — | ✅ | — | — | — | — | npx |

## 3. 云 API 类（对照组）

| 项目 | ★ | 能力 | 模式 |
|---|---:|---|---|
| ComPDFKit/compdf-mcp | 97 | 转换全家桶含 OCR 成可搜索 PDF | 全云，Docker |
| [PSPDFKit/nutrient-dws-mcp-server](https://github.com/PSPDFKit/nutrient-dws-mcp-server) | 69 | 功能最全（OCR/redact/签名/加密） | 全云按 credit 计费 |
| KDAN-PDF-MCP | 57 | 压缩/删页/redact/加密 | remote MCP，全云 |

另：pdfassistant-ai（托管，OCR+脱敏+加密 40 操作，$0.005/页 freemium）——**注意：云方案已覆盖"OCR 写回 + 加密 + 脱敏"全能力，我们的对标物是它的本地免费版**。

## 4. 目录站新发现（不在 GitHub star 视野内的近似竞品）

- **drolosoft/go-docs-mcp**：单 Go 二进制、12 工具、OCR+缓存——**与本项目定位最接近的直接竞品**（待实测确认能力边界）
- **Publicsofttools Mcp**：compress/merge/split/convert/**unlock 解密**
- quillpdf-mcp（Reddit 发布）：merge/split/rotate/watermark/Bates 编号/元数据，MIT 本地
- ReadmeMC/pdf-mcp-advanced（85★）：OCR for scanned PDFs，纯 Python 本地
- mcpdotdirect/pdf-tools-mcp（108★）：12 工具，OCR 14 语言
- 目录站排序逻辑：glama 公开公式 = adoption 40% + maintenance 24% + momentum 14% + 描述质量 13% + trust 9%；mcp.so 用 GitHub star；pulsemcp 用估算下载量。**含义：维护活跃度和采用量权重最高，发布后持续 commit 比功能堆料重要**

## 5. 需求侧信号（来源见链接）

**高星仓库 Issues 点名的功能缺口**：
- jztan/pdf-mcp：加密/带密码 PDF 处理（[#19](https://github.com/jztan/pdf-mcp/issues/19)）、OCR 语言参数是真需求（[#25](https://github.com/jztan/pdf-mcp/issues/25)/[#27](https://github.com/jztan/pdf-mcp/issues/27)）、图表→结构化数据（[#23](https://github.com/jztan/pdf-mcp/issues/23)）
- pdfmux：CJK OCR 质量（[#10](https://github.com/NameetP/pdfmux/issues/10) 韩文乱码）、进度反馈（#15）
- Open-Document-Alliance：Windows 原生二进制缺失（#155）、可配置目录权限（#121）、解压炸弹（#123）——**分发与安全是主战场**
- Citra：真实脏 PDF 的鲁棒性（解析 panic、MCP spec 合规）

**社区讨论（Reddit/HN）**：
- [Claude Code 读 PDF token 实测 73,500 vs 网页版 2,400](https://www.reddit.com/r/ClaudeAI/comments/1qmjpzn/i_tested_pdf_token_usage_claude_code_vs_claudeai/)（30 倍差距 → 本地提取是刚性省钱需求）
- ["Claude Code 读不了 PDF 怎么办"](https://www.reddit.com/r/ClaudeAI/comments/1l42mkd/how_do_you_guys_get_around_claude_code_not_being/)：高赞答案是"先 OCR 再喂"或"转图给模型看"——正是我们的管线
- [律所 OCR 重度工作流求 MCP](https://www.reddit.com/r/ClaudeAI/comments/1vdjxqr/how_to_improve_pdf_reading_skills_and_ocr/)
- [零上传本地 OCR 的隐私诉求](https://www.reddit.com/r/ClaudeAI/comments/1p69t9d/project_share_i_built_a_zerocopy_mcp_server_to/)

## 6. 原生客户端能力边界（差异化参照系）

| 客户端 | 能 | 不能（= 我们的机会） |
|---|---|---|
| Claude 网页/桌面/API | 读无密码 PDF（文本+逐页转图走视觉） | **加密 PDF 直接不支持**；无创建/编辑/拆合/加密；不出可搜索 OCR 文本层；600/100 页上限，密集小字撑爆上下文（[官方文档](https://platform.claude.com/docs/en/build-with-claude/pdf-support)） |
| Claude Code | Read 按"每页渲染成图"计价 | 30 倍 token 成本；feature request [#30546](https://github.com/anthropics/claude-code/issues/30546) 未解决 |
| ChatGPT | 512MB/2M tokens，提取数字文本层 | **扫描件常报 "No text could be extracted"**（无原生 OCR）；无页面级操作 |
| Cursor | 聊天附件文本提取 | 历史上不支持 PDF，OCR/页面操作皆无 |

**五点共同空白**：①扫描件→可搜索 PDF 的真 OCR ②密码/加密 PDF ③拆合/旋转/水印 ④批处理与本地隐私 ⑤CJK 确定性提取——与高星项目 issue 和 Reddit 需求完全吻合。

## 7. 对本项目的影响（建议）

1. **定位话术改为**："读 PDF 给模型看"已经有 Citra/jztan 做得很好（不必再卷）；我们做**"处理与输出"**——OCR 写回可搜索产物、页面手术、加密压缩、脱敏发布。一句话：*别人让 AI 读 PDF，我们让 PDF 被 AI 处理好*。
2. **P1a 工具顺序不变但叙事变了**：`ocr_pdf`（写回可搜索）+ `unlock_pdf`（提前，因为 Claude 原生直接拒绝加密文件，这是比预期更硬的刚需）值得在 P1a 或紧随其后。
3. **竞品威胁排序**（已被 §8.2.3 实测更新：ODA > go-docs > Citra 扩展 > 云厂商出本地版）：drolosoft/go-docs-mcp（定位接近，实测确认纯读向）> Citra 向处理扩展 > 云厂商出本地版。读取向头部项目反而可能是合作/被集成对象（它们没有输出管线）。
4. **运营启示**：glama 排序 40% 权重是 adoption——发布后前 4 周的持续 commit 和 issue 响应决定目录站排名，比功能堆料重要。
5. **M-1a 剩余工作**：实测轮——安装 Citra、jztan/pdf-mcp、drolosoft/go-docs-mcp、Open-Document-Alliance 四家，验证矩阵中标注 ? 的格子。

## 8. 实测轮结果（2026-09-05，本节结论覆盖前文 ? 格子）

**方法**：自研 [tools/mcp_probe.py](../tools/mcp_probe.py)（stdio JSON-RPC 探测客户端）+ 三类样本（3 页文本 PDF / 2 页无文本层扫描式 PDF / AES-256 强加密 PDF，由 [tools/make_fixtures.py](../tools/make_fixtures.py) 生成）。样本含标记串 `PDF-TOOLBOX-TEST-7734` 用于验证 OCR 命中。

> 坑位记录：pikepdf 只设 `user` 密码会生成"仅限制型"加密（空密码可开），必须 user+owner 都显式设置才是强加密样本。第一版弱样本曾让 go-docs"读出"了加密件，属假阳性。

### 8.1 四家逐项实测

| 能力 | Citra 5.0.0（3 工具） | go-docs-mcp 1.2.0（13 工具） | jztan pdf-mcp 3.1.0（13 工具） | ODA PDF-Tools 0.13.0（57 工具） |
|---|---|---|---|---|
| OCR 扫描件（读出） | ✅ 命中标记串 | ✅ 命中标记串（2 页） | ✅ 命中标记串（`ocr`/`ocr_lang` 参数） | ❌ 无 OCR——把页**渲染成 PNG 回给宿主模型看**（借宿主视觉当 OCR） |
| **OCR 写回可搜索 PDF** | ❌ | ❌ | ❌ | ❌（无任何 OCR） |
| 加密 PDF | ❌ 硬失败，schema 无密码参数（报 "invalid key length"） | ❌ 底层 pdftotext 报错，无密码参数 | ❌ PDFium "Incorrect password"，无密码参数 | ⚠️ **四家唯一有 password 概念**：user 密码遇权限位限制会拒绝（坚持要 owner 密码），owner 密码可拆分且输出**保持加密** |
| 页面手术（拆合等） | ❌ | ❌ | ❌ | ✅ split 实测通过（qpdf-wasm 内嵌，无需系统 qpdf） |
| 安装/启动 | npx 秒起 | `go install` 单二进制 | uvx | clone+npm install（较重） |
| 路径访问 | 任意路径 | **只认自家 `~/.docs-mcp/documents` 目录的 filename** | 任意路径（含 URL） | 目录白名单（`~/.pdf-tools/config.json`） |
| 其他实测观察 | 返回 envelope 带 provenance/置信度，工程感强 | 启动自动探测 tesseract+pdftoppm 并报 OCR 可用性 | 返回带 prompt-injection 警告头（`content_warning`），细节讲究 | 报错文案误导：加密件读失败提示"检查路径" |

### 8.2 实测轮结论

1. **核心假设坐实**：四家没有任何一家做"OCR 写回可搜索 PDF"——读出文本 ≠ 产出可搜索文件。处理/输出管线空白经实测确认。
2. **`unlock_pdf` 空间确认且比预期更大**：三家硬失败、一家（ODA）行为过于严格（user 密码不解锁权限限制、输出不脱密）。我们的定位：**user 密码即可解锁、输出为解密文件**（与 qpdf 默认行为一致），对"忘了 owner 密码但有打开密码"的用户是刚需。
3. **ODA 比桌面轮认知更强，威胁上调**：57 工具、内嵌 qpdf-wasm 做页面手术、表单/签名板块完整、目录白名单沙箱。但它没有 OCR、没有压缩、没有脱敏、没有加密输出，且偏重表单签名场景——**与本项目是互补而非正面竞争**，矩阵威胁排序更新为：ODA > go-docs > Citra 扩展。
4. **差异化口径微调**：ODA 占了"本地编辑+表单"，本项目主打 **OCR 写回 + 解锁（宽容策略）+ 压缩 + 脱敏**。README 对比表需把 ODA 列为"最接近的本地竞品"并写清差异，避免被用户当成重复造轮子。
5. **可借鉴的设计**（按来源）：jztan 的 prompt-injection 警告头；ODA 的目录白名单 + 原子写 + "新输出需要 identity 确认"覆盖保护；go-docs 的启动依赖自动探测（与我们 L0-L3 分级同思路）；Citra 的结构化 envelope + provenance。

### 8.3 实测环境备注

- macOS arm64；node 22 / uv 0.11.7 / go（homebrew）；poppler、tesseract(eng) 已装；qpdf、gs 未装（本次未需要）
- tesseract 仅 eng 语言包；CJK OCR 质量留待 M-1d 中文样本评估
- 遗留：`~/.pdf-tools/config.json`（ODA 白名单，指向已删除的 fixtures 目录）、`~/.docs-mcp/documents/`（go-docs 自建）、`~/go/bin/go-docs-mcp` 二进制、`/tmp/oda-pdf-tools` clone——均无害，可 `rm` 清理
