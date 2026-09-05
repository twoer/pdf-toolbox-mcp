# pdf-toolbox-mcp

[中文文档](README.zh-CN.md) | Local-first PDF processing for AI agents.

**Others help AI *read* PDFs. This one helps AI *process* them** — OCR a scan into a truly searchable file, unlock encrypted PDFs, split/merge/rotate, re-encrypt for sharing. 100% on your machine: no cloud calls, no file uploads, no per-page fees.

## Why another PDF MCP?

The PDF MCP space is crowded — but only on the *reading* side. Based on a [hands-on survey of the ecosystem](docs/competitor-matrix.md) (2026-09):

| Capability | **pdf-toolbox** | Citra (916★) | ODA PDF-Tools (153★) | jztan/pdf-mcp (130★) | Cloud SaaS MCPs |
|---|:-:|:-:|:-:|:-:|:-:|
| **OCR write-back** → searchable PDF file | ✅ | ❌ read-out only | ❌ (no OCR) | ❌ read-out only | ☁️ paid |
| **Unlock encrypted** (user password) | ✅ | ❌ hard fail | ⚠️ owner-pw only | ❌ hard fail | ☁️ paid |
| Split / merge / rotate | ✅ | ❌ | ✅ | ❌ | ☁️ paid |
| **Compress** to target size | ✅ | ❌ | ❌ | ❌ | ☁️ paid |
| Render pages for vision | ✅ | ✅ | ✅ | ✅ | ☁️ |
| 100% local & private | ✅ | ✅ | ✅ | ✅ | ❌ |

Pain points this addresses directly:

- Claude natively **refuses encrypted PDFs**; ChatGPT reports *"No text could be extracted"* on scans — here, OCR writes a real text layer back into the file, and `unlock_pdf` decrypts with just the user password.
- Claude Code burns **~30× more tokens** reading a PDF page-as-image than extracting text locally.

## Quick start

Add to any MCP client (Claude Desktop / Claude Code / Cursor / …):

```json
{
  "mcpServers": {
    "pdf-toolbox": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/twoer/pdf-toolbox-mcp", "pdf-toolbox-mcp"]
    }
  }
}
```

*(PyPI package `pdf-toolbox-mcp` is coming; the git install above works today.)*

Python dependencies resolve automatically. System tools are **capability-leveled** — missing ones never crash the server; the tool returns a structured error with the exact install command:

| Level | Binary | Unlocks | macOS | Debian/Ubuntu | Windows |
|---|---|---|---|---|---|
| L0 | qpdf | split / merge / rotate / protect / unlock | `brew install qpdf` | `apt install qpdf` | `choco/scoop install qpdf` |
| L1 | poppler | extract_text / render / info | `brew install poppler` | `apt install poppler-utils` | `choco/scoop install poppler` or conda-forge |
| L2 | tesseract | **ocr_pdf (write-back)** | `brew install tesseract tesseract-lang` | `apt install tesseract-ocr tesseract-ocr-chi-sim` | `choco/scoop install tesseract` |
| L3 | ghostscript | compress | `brew install ghostscript` | `apt install ghostscript` | `scoop install ghostscript` / `winget install ArtifexSoftware.GhostScript` |

> Windows note: Ghostscript's binary is `gswin64c.exe` there — the probe detects it automatically, so `compress_pdf` works out of the box. Tesseract language packs (e.g. `chi_sim`) must be downloaded to its `tessdata` folder separately.

Every successful response carries a `_deps` summary (`{"level": 2, "missing": ["gs"]}`) so the agent always knows what's available.

## Tools (24)

| Tool | What it does | Engine |
|---|---|---|
| `pdf_info` | Pages, encryption status, metadata — always call first | pdfinfo |
| `is_searchable` | Smart routing: text density check → recommends `extract_text` or `ocr_pdf` | pdftotext |
| `extract_text` | Layout-aware text, exact page ranges `1-3,5`, per-page mode | pdftotext |
| `ocr_pdf` | **OCR write-back**: scan → searchable PDF (deskew, skip/redo, lang fallback) | OCRmyPDF |
| `batch_ocr` | Whole-directory OCR with per-file results, retries, timeouts | OCRmyPDF |
| `render_pages` | PNG per page, `return_images=true` streams image blocks to the vision model | pdftoppm |
| `extract_images` | Pull embedded images (inventory or PNG files) | pdfimages |
| `extract_attachments` | Pull embedded attachment files | pdfdetach |
| `list_fonts` | Font audit — non-embedded fonts risk missing glyphs on other machines | pdffonts |
| `unlock_pdf` | Decrypt with **user password**, output a clean decrypted file | qpdf |
| `protect_pdf` | AES-256 + granular permissions (print/extract/modify/…) | qpdf |
| `split_pdf` | By ranges or every N pages | qpdf |
| `merge_pdfs` | Ordered merge | qpdf |
| `rotate_pages` | 90/180/270 on selected pages | qpdf |
| `check_repair` | Structural check; `repair=true` rebuilds damaged files | qpdf |
| `linearize` | Web-optimized progressive-loading output | qpdf |
| `sanitize` | Publishing hygiene: strip JS/OpenAction/metadata/attachments | pikepdf |
| `redact` | **True redaction**: affected pages rasterized + opaque boxes — redacted text physically unrecoverable, other pages keep their text layer (`rasterize_all=true` for max protection) | pdftoppm + PIL |
| `redact_text` | Redact **by content**: locate every occurrence of the given keywords and black them out — no manual coordinates needed | pdftotext -bbox |
| `locate_text` | Find where text occurs: page + bounding boxes (PDF points, top-left origin) — the foundation for redaction & highlighting | pdftotext -bbox |
| `fill_form` | Fill AcroForm fields (missing fields reported) | pikepdf |
| `edit_metadata` | Set/clear Title/Author/… (docinfo + XMP) | pikepdf |
| `compress_pdf` | Compress, optionally down a quality ladder until hitting `target_mb` | ghostscript |
| `dependency_status` | Probe system tools + install commands | — |

**Error contract** (agents self-route): failures return `{"ok": false, "error": "<code>"}` — `missing_dependency` (with `install` per platform), `encrypted_pdf` (hint: call `unlock_pdf` first), `wrong_password`, `output_exists` (explicit overwrite required), `invalid_page_range`, …

## Examples

In an MCP client, just describe the outcome — the agent chains the tools itself, and the error contract makes it self-routing (an `encrypted_pdf` error tells it to call `unlock_pdf` first, and so on). For headless use, define once:

```bash
PTX="uvx --from git+https://github.com/twoer/pdf-toolbox-mcp pdftoolbox"
# shortens to "uvx --from pdf-toolbox-mcp pdftoolbox" once the PyPI package lands
```

**1 · Scan → searchable PDF** (the flagship)

> “`contract-scan.pdf` is a scanned contract I can't search. Make it searchable — mostly Chinese with some English.”

Agent: `pdf_info` → `is_searchable` reports low text density → `ocr_pdf(path, lang="chi_sim+eng")` writes `contract-scan_ocr.pdf`. Text extraction and Ctrl+F now work on the output.

```bash
$PTX ocr contract-scan.pdf --lang chi_sim+eng
$PTX text contract-scan_ocr.pdf --pages 1-3
```

**2 · Encrypted PDF → readable**

> “`locked.pdf` is password-protected; the password is `hunter2`. Unlock it and summarize page 3.”

Agent: `unlock_pdf(path, password="hunter2")` → `locked_unlocked.pdf` → `extract_text(pages="3")`.

```bash
$PTX unlock locked.pdf --password 'hunter2'
$PTX text locked_unlocked.pdf --pages 3
```

**3 · Redact secrets before sharing**

> “Black out every occurrence of `张三` and `HT-2026-088` in `draft.pdf` — it must be physically unrecoverable.”

Agent: `redact_text(queries=["张三", "HT-2026-088"])` → `draft_redacted.pdf`. Pages containing hits are rasterized, so the strings vanish from the pixels *and* the text layer; other pages keep their selectable text. Verify by running `extract_text` on the output: zero hits expected.

```bash
$PTX redact-text draft.pdf --query 张三 --query HT-2026-088
```

**4 · Assemble & encrypt for sending**

> “Merge `cover.pdf` + `report.pdf` into `annual.pdf`, then protect it: opens with password `k3y`, printing allowed, modification not.”

Agent: `merge_pdfs(paths=["cover.pdf", "report.pdf"], output="annual.pdf")` → `protect_pdf(user_password="k3y")` (print/extract allowed, modify denied by default) → `annual_locked.pdf`.

```bash
$PTX merge cover.pdf report.pdf --output annual.pdf
$PTX protect annual.pdf --user-password 'k3y'
```

**5 · Fit an email size limit**

> “`big.pdf` is 38 MB and the mail cap is 10 MB. Shrink it.”

Agent: `compress_pdf(path, target_mb=10)` walks the quality ladder (ebook → screen) until under target → `big_compressed.pdf`.

```bash
$PTX compress big.pdf --target-mb 10
```

More recipes — batch OCR, the publish-hygiene chain (`sanitize` → `edit_metadata` → `linearize`), vision rendering, locate-and-redact, form filling, damaged-file rescue — in the [cookbook](docs/cookbook.md).

## Configuration

| Env | Default | Meaning |
|---|---|---|
| `PDF_TOOLBOX_TESS_LANG` | `chi_sim+eng` | Default OCR languages; missing packs auto-fallback (flagged via `lang_fallback`) |
| `PDF_TOOLBOX_WORKSPACE` | unset | If set, all writes are confined to this directory; system dirs are always denied |

## CLI

Everything is also available headless (great for scripts and CI):

```bash
uvx --from git+https://github.com/twoer/pdf-toolbox-mcp pdftoolbox ocr scan.pdf --lang chi_sim+eng
uvx --from git+https://github.com/twoer/pdf-toolbox-mcp pdftoolbox unlock locked.pdf --password 'xxx'
uvx --from git+https://github.com/twoer/pdf-toolbox-mcp pdftoolbox split big.pdf --every-n 10
uvx --from git+https://github.com/twoer/pdf-toolbox-mcp pdftoolbox probe all
```

*(Shortens to `uvx --from pdf-toolbox-mcp …` once the PyPI package is published — see the note in Quick start.)*

## Security & privacy

- No network calls. Files never leave the machine.
- All subprocess calls use argument lists (no shell interpolation); page-range parsing is shared and validated.
- Outputs never silently overwrite: `overwrite=true` must be passed explicitly.
- Passwords are never logged in error payloads.
- Untrusted PDF content is flagged in tool descriptions (prompt-injection awareness).

## License compliance

MIT. System tools are invoked as independent processes (aggregation): poppler (GPL-2.0), qpdf (Apache-2.0), tesseract (Apache-2.0), ghostscript (AGPL, optional); Python deps ocrmypdf/pikepdf are MPL-2.0. See [PLAN.md](PLAN.md) §7 for the full table.

## Development

```bash
uv sync --dev          # install
uv run pytest          # 105 tests; auto-skip by capability level
uv run pdftoolbox probe all
```

Cross-platform check without leaving macOS:

```bash
docker run --rm -v "$PWD":/src:ro python:3.12-slim bash -c \
  'apt-get update -qq >/dev/null && apt-get install -y -qq poppler-utils tesseract-ocr qpdf ghostscript >/dev/null &&
   pip install -q uv && cp -r /src /work && cd /work && uv sync --dev --quiet && uv run pytest -q'
```

Roadmap: v0.1.0 ships all 24 tools above. Next up: the PyPI package (drops the git prefix from every command) and hardening against real-world scanned documents. Explicit non-goals: editing existing text, password cracking — see [PLAN.md](PLAN.md).

## License

MIT
