# pdf-toolbox-mcp Launch Kit

## Positioning

`pdf-toolbox-mcp` is a local-first PDF processing MCP server for AI agents.
It OCRs scans back into searchable PDFs, unlocks encrypted files, splits/merges/rotates pages, renders pages for vision, and compresses PDFs, all on the user's machine.

## 定位

`pdf-toolbox-mcp` 是一个面向 AI 代理的本地优先 PDF 处理 MCP 服务。
它可以把扫描件 OCR 写回可搜索 PDF、解锁加密文件、拆分/合并/旋转页面、渲染页面给视觉模型，并本地压缩 PDF，全部在用户机器上完成。

## One-line pitch

Local-first PDF processing for AI agents: OCR write-back, unlock, render, split/merge, redact, compress.

## 一句话介绍

面向 AI 代理的本地优先 PDF 处理：OCR 写回、解锁、渲染、拆分/合并、涂黑、压缩。

## Short description

Use `pdf-toolbox-mcp` when you want ChatGPT, Claude Desktop, Claude Code, or Cursor to actually process PDFs instead of only reading them.
It keeps files local, returns structured errors, and gives AI agents a clean tool surface for OCR, unlock, render, and page surgery.

## 简短介绍

当你希望 ChatGPT、Claude Desktop、Claude Code 或 Cursor 不只是“读 PDF”，而是真的处理 PDF 时，就用 `pdf-toolbox-mcp`。
它会把文件保留在本地，返回结构化错误，并给 AI 代理一套清晰的 OCR、解锁、渲染和页面处理工具。

## Install commands

MCP JSON:

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

CLI:

```bash
uvx --from pdf-toolbox-mcp pdftoolbox doctor
```

Project page:

https://pypi.org/project/pdf-toolbox-mcp/

## 安装命令

MCP JSON：

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

CLI：

```bash
uvx --from pdf-toolbox-mcp pdftoolbox doctor
```

项目页：

https://pypi.org/project/pdf-toolbox-mcp/

## Feature bullets

- OCR scans into searchable PDFs
- Unlock encrypted PDFs with the user password
- Split, merge, rotate, and linearize PDFs
- Render pages for vision models
- Redact text and protect shared files
- Compress PDFs locally
- Structured error output with exact next steps

## 功能要点

- 把扫描件 OCR 成可搜索 PDF
- 用用户密码解锁加密 PDF
- 拆分、合并、旋转、线性化 PDF
- 把页面渲染给视觉模型
- 涂黑文本并保护共享文件
- 本地压缩 PDF
- 返回结构化错误和明确下一步

## Suggested directory copy

## 建议投稿文案

### mcp.so

Title: `pdf-toolbox-mcp`

Description: `Local-first PDF processing MCP server for AI agents. OCR write-back, unlock, split/merge, render, redact, and compress PDFs on your machine.`

标题：`pdf-toolbox-mcp`

简介：`面向 AI 代理的本地优先 PDF 处理 MCP 服务。支持 OCR 写回、解锁、拆分/合并、渲染、涂黑和压缩，全部在本地完成。`

### MCP Registry

Title: `pdf-toolbox-mcp`

Summary: `A local-first PDF processing MCP server that helps AI agents OCR, unlock, render, redact, and compress PDFs without uploading files.`

标题：`pdf-toolbox-mcp`

摘要：`一个本地优先的 PDF 处理 MCP 服务，帮助 AI 代理在不上传文件的情况下完成 OCR、解锁、渲染、涂黑和压缩。`

### mcpservers.org

Title: `pdf-toolbox-mcp`

Tagline: `Local-first PDF processing for AI agents`

标题：`pdf-toolbox-mcp`

标语：`面向 AI 代理的本地优先 PDF 处理`

## Screenshot request

Not required for the first directory submissions.

If we later do Product Hunt, Show HN, or a social post, the best single screenshot is:

1. A terminal/CLI shot showing `uvx --from pdf-toolbox-mcp pdftoolbox doctor`
2. Or a before/after PDF example showing scan -> searchable output

## 截图需求

第一轮目录提交不需要截图。

如果后面做 Product Hunt、Show HN 或社媒帖，最合适的一张图是：

1. 终端/CLI 截图，展示 `uvx --from pdf-toolbox-mcp pdftoolbox doctor`
2. 或者扫描件前后对比图，展示从扫描件到可搜索 PDF 的结果

## Next submission order

1. mcp.so
2. MCP Registry
3. mcpservers.org
4. Smithery only if we package a compatible HTTP/bundle path later
5. Product Hunt / Show HN

## 下一步提交顺序

1. mcp.so
2. MCP Registry
3. mcpservers.org
4. 只有在后续补出兼容的 HTTP / bundle 形态时再考虑 Smithery
5. Product Hunt / Show HN
