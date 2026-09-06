# Cookbook

Start with `pdftoolbox doctor` / `tool_doctor`, then use the [README](../README.md) for the first three moves (OCR write-back, unlock, redact-by-keyword). This cookbook walks the rest — same conventions: in an MCP client you just describe the goal and the agent picks the tool; headless, define once:

```bash
PTX="uvx --from git+https://github.com/twoer/pdf-toolbox-mcp pdftoolbox"
```

## Batch-OCR a folder of scans

> “OCR everything in `./scans/` — Chinese + English, retry failures once.”

`batch_ocr(inputs=["./scans"], lang="chi_sim+eng", max_retries=1, per_file_timeout=180)` processes every PDF in the directory; one bad file never aborts the run — you get per-file results at the end. Outputs land next to the sources (or in `out_dir`) as `<stem>_ocr.pdf`.

```bash
$PTX batch ocr scans/ --lang chi_sim+eng --retries 1 --timeout 180
```

## Publish a clean external copy

Before sending a PDF outside, strip everything that isn't content, set proper metadata, and optimize for web viewing:

1. `sanitize(path)` — removes JavaScript, OpenAction, metadata, attachments → `<stem>_sanitized.pdf`. (MCP keeps annotations by default; the CLI strips them unless you pass `--keep-annotations`.)
2. `edit_metadata(title="Q3 Report", author="Acme")` → `<stem>_meta.pdf`; `clear=true` wipes all fields instead.
3. `linearize(path)` — progressive-loading output for browsers → `<stem>_fast.pdf`.

```bash
$PTX sanitize report.pdf
$PTX meta report_sanitized.pdf --title "Q3 Report" --author "Acme"
$PTX linearize report_meta.pdf
```

## Merge and protect

> “Merge `cover.pdf` + `report.pdf` into `annual.pdf`, then protect it: opens with password `k3y`, printing allowed, modification not.”

`merge_pdfs(paths=["cover.pdf", "report.pdf"], output="annual.pdf")` joins files in order; `protect_pdf(user_password="k3y")` writes an AES-256 encrypted copy with permissions you choose. For the common case, keep printing/extraction on and modification off.

```bash
$PTX merge cover.pdf report.pdf --output annual.pdf
$PTX protect annual.pdf --user-password 'k3y'
```

## Compress to target

> “`big.pdf` is 38 MB and the mail cap is 10 MB. Shrink it.”

`compress_pdf(path, target_mb=10)` walks the quality ladder until the output drops under the target. It is lossy, so use it for sharing or email, not archival masters.

```bash
$PTX compress big.pdf --target-mb 10
```

## Let the model *see* a complex page

Text extraction fails on dense tables and diagrams. Render the page and hand it to the vision model directly:

> “Page 4 is a big table — look at it and tell me the totals.”

`render_pages(path, pages="4", dpi=200, return_images=True)` returns the PNG as an image block inside the MCP response, so the model reads it without touching disk. `dpi` can go up to 300 for small print; `pages` accepts ranges like `"1-3,5"`.

```bash
$PTX render manual.pdf --pages 4 --dpi 200 --out-dir ./png
```

## Locate text, then redact surgically

`redact_text` blacks out every occurrence of a keyword — but when you need *this* mention kept and *that* one removed, locate first and redact by coordinates:

```bash
$PTX locate manual.pdf --query '违约金'          # → page + bbox per hit (PDF points, top-left origin)
$PTX redact manual.pdf --regions '[{"page":3,"x":60,"y":100,"w":300,"h":30}]'
```

`redact` rasterizes only the pages it touches: the redacted strings are physically gone (pixels *and* text layer), untouched pages keep selectable text. `rasterize_all=true` takes the whole document down to images for maximum protection.

## Rescue a damaged PDF

> “`old.pdf` won't open in anything. Try to save it.”

`check_repair(path, repair=True)` rebuilds the file structure via qpdf → `<stem>_repaired.pdf`. Run it with `repair=false` first (the default) to see what's actually wrong.

```bash
$PTX check old.pdf            # diagnose only
$PTX check old.pdf --repair   # write old_repaired.pdf
```

## Fill a PDF form

> “Fill `application.pdf`: name 张三, email zk@example.com.”

`fill_form(fields={"name": "张三", "email": "zk@example.com"})` → `<stem>_filled.pdf`. Field names that didn't match any AcroForm field come back in `missing` so you can correct them; the classic gotcha is `Name` vs `name` — run once, read `missing`, adjust.

```bash
$PTX fill application.pdf --fields '{"name":"张三","email":"zk@example.com"}'
```

## Pull embedded images and attachments

```bash
$PTX images report.pdf --list-only     # inventory only, nothing written
$PTX images report.pdf --pages 1-3     # extract PNGs
$PTX attachments contract.pdf          # extract embedded files (out_dir optional)
```

MCP equivalents: `extract_images(list_only=true)` / `extract_attachments(out_dir=…)`.

## Audit fonts before printing

`list_fonts(path)` shows every font and whether it's embedded. Non-embedded fonts render with substitutes (or missing glyphs) on machines that don't have them — worth checking before a print run or external delivery.

```bash
$PTX fonts deck.pdf
```

## Split & rotate

```bash
$PTX split big.pdf --ranges '1-3,4-6,7-12'   # one output file per range
$PTX split big.pdf --every-n 10              # fixed-size chunks
$PTX rotate scan.pdf --angle 90 --pages 2,5  # → scan_rot90.pdf
```

## Know your environment

```bash
$PTX probe all        # which engines are installed, capability level, install commands
```

In an MCP session, `dependency_status` does the same, and every successful tool response carries a `_deps` summary. To confine all writes to one directory, set `PDF_TOOLBOX_WORKSPACE=/path/to/dir` in the server's environment — outputs then never land outside it.
