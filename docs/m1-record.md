# M-1 验证记录

> 目的：按 PLAN §10 门槛验证"本地重引擎"假设，决定是否进入 M0/M1。

## M-1b 引擎 PoC —— ✅ 通过（2026-09-05）

**平台**：macOS arm64（本机，qpdf 12.4.1 / poppler 26.03 / tesseract 5.5.3(eng) / gs 10.07.1）+ Linux docker（python:3.12-slim + apt 系，qpdf 12.2 / poppler 25.03 / tesseract 5.5.0 / gs 10.05）。门槛要求"至少两平台"，已达成；Windows 未测。

**同套代码**（`src/pdf_toolbox/engine/`，CLI 入口 `uv run pdftoolbox`）：

| 操作 | macOS | Linux | 验证方式 |
|---|---|---|---|
| `pdf_info` | ✅ | ✅ | 3 页/未加密/尺寸正确 |
| `extract_text` | ✅ | ✅ | 标记串命中 |
| `ocr_pdf`（写回） | ✅ | ✅ | **产物再跑 pdftotext，标记串 2 页命中——写回闭环成立** |
| `render_pages` | ✅ | ✅ | 多区间 "1,3" 出 2 张 1241×1754 PNG（A4@150dpi） |
| 依赖探测 L0–L3 | ✅ 全绿 | ✅ 全绿 | probe all 两平台输出正确 |

**过程中发现并修复的问题**：
1. `render.py` Path+str 拼接 TypeError——已修
2. 覆盖保护在 Linux 验证时被意外触发（旧产物随目录拷入），行为正确——无需修
3. pikepdf 仅设 user 密码生成弱加密样本的坑（记录于竞品矩阵 §8）

**已知债务（转 M1 待办）**：
- ~~`extract_text` 多区间目前取外包络~~ → ✅ 2026-09-05 已还：精确页集合去重 + 连续区间分组逐段提取
- ~~`render_pages` 输出的 `page` 字段为 null~~ → ✅ 已还：从 pdftoppm 文件名解析页号
- ~~默认语言 `chi_sim+eng` 缺包直接报错~~ → ✅ 已还：默认语言缺包自动降级（结果中 `lang_fallback=True`）；显式语言缺包给安装命令
- ~~路径沙箱未实现~~ → ✅ 基础版已还：`PDF_TOOLBOX_WORKSPACE` 写出限制 + 系统目录禁写；读路径与"首次新根目录确认"机制留 M2（对齐 ODA 白名单设计）
- 新增债务：`extract_text`/`render_pages` 每连续区间一次子进程调用——百页级文档可接受，千页级需改单次调用后切分（M2 观察性能再定）

## M-1c 客户端 PoC —— ✅ 协议层通过（2026-09-05）；🟡 真实客户端验收被环境阻断（2026-09-06 尝试）

用 `tools/mcp_probe.py` 对自家 server（`uv run pdf-toolbox-mcp`，FastMCP 4.0.3 / protocol 2025-06-18）：

- `list`：5 工具（info / extract_text / ocr_pdf / render_pages / dependency_status）✅
- `call tool_extract_text`：返回结构化 JSON + 标记串 ✅

无头 Claude Code 方案已就绪并注册验证（`✔ Connected`），但本机对外的 HTTPS 链路异常（TCP 可达、TLS 握手被复位）——用户侧网络环境问题，非本项目代码问题。**网络恢复后重跑**：

```bash
cd <path/to/pdf-toolbox-mcp>
claude mcp add --scope local pdf-toolbox -- uv run --directory $PWD pdf-toolbox-mcp
# 场景1：扫描件智能路由→OCR 写回→定位标记串
claude -p "用 pdf-toolbox 工具处理 .fixtures/scanned.pdf：先判断是否可搜索，不可搜索则 OCR 写回（覆盖输出），在产物中找到 PDF-TOOLBOX-TEST-7734 并报告页码，最后报告调用的工具与顺序" --allowedTools "mcp__pdf-toolbox__*"
# 场景2：加密件解锁（密码 pdf-toolbox-test）→提取第 1 页文字
# 场景3：render_pages(return_images=true) 渲染第 1 页并读出标题
```

## M1 完成情况（2026-09-05 追加）

- **PLAN §5 缺依赖结构化错误 ✅**：engine 层类型化异常（`errors.py`：Missing/Encrypted/WrongPassword）+ `require()` 前置检查；MCP 层 `_guard` 统一转 `{"ok": false, "error": <code>, ...}`（缺依赖带 install 命令、加密件带 unlock_pdf 引导、未知异常兜底 internal_error）；成功返回注入 `_deps` 能力摘要（协议层实测 `{'level': 3, 'missing': []}`）
- P1a 五件套（info / extract_text / ocr_pdf / render_pages / **unlock_pdf**）+ P1b 四件（split / merge / rotate / protect）全部就位；render 支持 return_images 直返 MCP 图像块
- 测试 60/60（macOS + docker Linux）
- render 的 Path 拼接 bug 曾在重写时复发、fastmcp 4.x Image 导出路径变化——均已修复（测试拦截）

## M-1d 样本评估 —— ⏳ 待办

前置条件：
1. 本机装中文语言包（`brew install tesseract-lang`，或仅下载 `chi_sim.traineddata` 到 tessdata）
2. 5–10 份脱敏中文扫描件（合同/票据/论文，需用户提供）

通过标准（RESEARCH §6 四条门槛）：两平台 10 分钟安装 ✅（实测 docker 约 2–3 分钟装齐 L0–L2）/ OCR 字符准确率达标（待样本）/ 核心任务成功率 ≥80%（待样本）/ 无高危缺陷（当前无）。

## M-1d 样本评估 —— 🟡 预演完成（2026-09-06），真实样本待用户提供

**方法学预演**（`tools/eval_ocr_zh.py`，可复现）：系统 CJK 字体渲染已知 ground truth 的"扫描式"中文合同（含中英混排、金额、日期），三档退化；OCR 写回（chi_sim+eng）后 pdftotext 提取，NFKC 归一化去空白算 CER。

环境：tessdata 本地化（`cp -RL /opt/homebrew/share/tessdata .tessdata` + 下载 `chi_sim.traineddata` from tessdata_fast；坑：homebrew 的 tessdata 是指向 Cellar 的软链，`cp -R` 会复制出悬空相对链接，必须 `-L` 解引用）+ `TESSDATA_PREFIX=$PWD/.tessdata`。

| 样本 | CER | 准确率 | 耗时 |
|---|---:|---:|---:|
| v1 干净 300dpi | 0.97% | **99.03%** | 1.6s |
| v2 噪点 200dpi（10% 高斯） | 18.93% | 81.07% | 1.3s |
| v3 倾斜 2.5°（deskew 开） | 6.31% | 93.69% | 2.2s |

**对照 RESEARCH §6 门槛**：两平台 10 分钟安装 ✅；OCR 准确率——干净印刷体 99% 远超可用线 ✅，重度噪点 81% 属边界（真实扫描件通常介于 v1–v2 之间，deskew 对倾斜有效）；核心任务成功率——待真实样本；无高危缺陷 ✅。

**50 文件批量压测**（同脚本）：50/50 成功，总 77.8s，平均 1.56s/文件——M3 完成标准的"50 文件批处理"补漏 ✅。

**结论**：管线质量达标，预演通过；正式 M-1d 仍需 5–10 份真实脱敏样本复核（尤其噪点档表现）。

## 结论

M-1b/M-1c 通过，M-1d 因样本依赖暂挂。**建议：M0 骨架（CI/测试补齐）与 M-1d 并行推进，M-1d 结果不阻塞 M0，但阻塞 M2 发布。**
