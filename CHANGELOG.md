# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); versioning is [SemVer](https://semver.org/).

## [0.1.4] — 2026-09-06

Docs-only release. README client setup section was reformatted into a compact, copy-friendly list.

### Changed
- README client setup instructions now render as bullets instead of a dense paragraph

## [0.1.3] — 2026-09-06

Release 0.1.3. Local-first PDF processing MCP server (OCRmyPDF + Poppler + qpdf + ghostscript).

### Added
- Real-world regression suite with manifest-driven cases for low-res OCR, encrypted unlock, repair, batch OCR, sanitize, forms, and compression
- CI split so normal runs skip slower realworld fixtures, plus a scheduled `realworld` workflow
- Registry metadata, launch kit docs, and the launcher mockup asset
- README dependency matrix now includes one-shot install commands and upstream links
- **Content redaction**: `locate_text` (text → page + bounding boxes via `pdftotext -bbox`, CJK-safe normalized matching) and `redact_text` (redact by keyword — auto-locates every occurrence, no manual coordinates)
- **P1a core**: `pdf_info`, `is_searchable` (smart routing), `extract_text` (exact page ranges), `ocr_pdf` (**OCR write-back** to searchable PDF, language fallback), `render_pages` (PNG, optional inline image blocks), `unlock_pdf` (user-password decrypt — competitors hard-fail here)
- **P1b page surgery** (L0-pure qpdf): `split_pdf`, `merge_pdfs`, `rotate_pages`, `protect_pdf` (AES-256 + granular permissions)
- **P2 inspection & batch**: `list_fonts`, `extract_images`, `extract_attachments`, `check_repair` (+ rebuild repair), `linearize`, `batch_ocr` (per-file results / retries / timeouts)
- **P3 advanced**: `sanitize` (strip JS/metadata/attachments), `redact` (**true redaction** — affected pages rasterized, redacted text physically unrecoverable, other pages keep their text layer; `rasterize_all=true` for whole-doc protection), `fill_form`, `edit_metadata` (docinfo+XMP), `compress_pdf` (quality ladder to target size)
- Capability-leveled dependencies (L0–L3) with structured `missing_dependency` errors carrying per-platform install commands; `_deps` summary injected into every successful response
- CLI: `pdftoolbox` with all operations + `probe all`
- Windows: `gswin64c` binary alias, UTF-8 console output; CI runs the full suite on windows-latest via choco
- Research & plan docs (`RESEARCH.md`, `PLAN.md`, `docs/competitor-matrix.md` incl. hands-on survey of Citra / ODA / jztan / go-docs-mcp)

### Verified
- OCR write-back roundtrip (scan → searchable, marker asserted) on macOS + Linux + Windows
- Redaction security: output text layer empty + black-box pixel assertion
- Chinese OCR benchmark (synthetic): 99.03% clean / 93.69% deskewed / 81.07% heavy-noise
- 50-file batch: 50/50 success, ~1.6 s/file

[Unreleased]: https://github.com/twoer/pdf-toolbox-mcp/commits/main
[0.1.4]: https://github.com/twoer/pdf-toolbox-mcp/releases/tag/v0.1.4
[0.1.3]: https://github.com/twoer/pdf-toolbox-mcp/releases/tag/v0.1.3
