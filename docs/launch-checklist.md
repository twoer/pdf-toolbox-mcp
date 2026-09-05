# M2 发布清单（launch checklist）

> 需要仓库所有者（zhangkun）操作的步骤已标注 👤；其余为材料就绪状态。

## 1. GitHub 远程 👤

```bash
# 方式一：gh CLI（推荐）
gh repo create pdf-toolbox-mcp --public --source . --push
# 方式二：网页建仓后
git remote add origin git@github.com:<你>/pdf-toolbox-mcp.git
git push -u origin main
```

- [x] 建仓完成（2026-09-05）：https://github.com/twoer/pdf-toolbox-mcp（公开）
- [x] `pyproject.toml` 的 `[project.urls]` 已回填
- [x] 确认 Actions 三平台 CI 全绿（2026-09-05 run 33975818609：ubuntu 26s / macos 32s / windows 27s）

## 2. PyPI 发版 👤（token 一次性录入）

```bash
uv build                       # 产出 dist/*.whl + .tar.gz（本地已验证 ✅）
uv publish                     # 需要 PyPI API token：pypi.org → Account settings → API tokens
```

- [ ] 提前在 pypi.org 注册并验证 `pdf-toolbox-mcp` 名称归属（2026-09-05 查询：可用）
- [ ] 发布后验证 `uvx pdf-toolbox-mcp` 全新环境可跑
- [ ] 打 tag：`git tag v0.1.0 && git push --tags`

## 3. 目录站提交（材料已备，逐个粘贴）

### awesome-mcp-servers（punkpeye，提 PR）

插入位置：File Processing 区块，格式对齐现有条目：

```markdown
- [twoer/pdf-toolbox-mcp](https://github.com/twoer/pdf-toolbox-mcp) 🐍 🏠 🍎 🪟 🐧 - Local-first PDF processing for AI agents: OCR write-back to searchable PDFs (OCRmyPDF), layout-aware text extraction (Poppler), page rendering for vision models, page surgery and AES-256 encryption/unlock (qpdf). Capability-leveled dependencies with structured missing-dependency errors and install hints.
```

- [ ] PR：https://github.com/punkpeye/awesome-mcp-servers/edit/main/README.md

### 其他目录（表单提交）

| 站点 | 入口 | 一句话（英文） |
|---|---|---|
| glama.ai | https://glama.ai/mcp/servers/submit | Local-first PDF processing: OCR write-back, unlock, page surgery (OCRmyPDF+Poppler+qpdf) |
| mcp.so | https://mcp.so/submit | 同上 |
| pulsemcp.com | https://www.pulsemcp.com/submit | 同上 |
| mcpservers.org | GitHub 提交（读其 README） | 同上 |
| appcypher/awesome-mcp-servers | PR | 同上 |

> glama 排序权重：adoption 40% + maintenance 24%——**发布后前 4 周保持每周 commit 与 issue 响应**比什么都重要。

## 4. 中文教程

- 草稿就绪：[tutorial.zh-CN.md](tutorial.zh-CN.md)（含配图清单与投放变体）
- [ ] 补截图（4 张）
- [ ] 投放：少数派（完整版）/ V2EX（干货版）/ 即刻（链接+一段话）

## 5. 发版前自检（已通过 ✅ 2026-09-05）

- [x] `uv build` 成功，whl 含全部 13 个模块文件
- [x] wheel 在隔离环境经 uvx 启动，10 工具注册正常
- [x] CLI 入口 `pdftoolbox` 可用（隔离环境 probe 正常）
- [x] 60 测试双平台全绿
- [x] README 双语 + 对比表 + 安装矩阵
