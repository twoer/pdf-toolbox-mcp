# Security Policy

## Design principles

- **No network calls.** The server makes no outbound connections; files never leave the machine.
- Subprocess calls use argument lists only — no shell interpolation, no injection surface from page ranges or filenames.
- Passwords are never included in logs or error payloads.
- Outputs never silently overwrite existing files.
- Writes can be confined to a workspace via `PDF_TOOLBOX_WORKSPACE`; system directories are always denied.

## True redaction guarantees (and boundaries)

`redact` / `redact_text` rasterize the affected pages: redacted text is physically absent from the output file (not merely covered). Boundaries to be aware of:

- The *original* file is left untouched — delete it yourself if it contained secrets.
- Rasterized pages lose accessibility text and searchability (by design).
- Metadata and attachments are NOT removed by redaction — run `sanitize` for those.

## Reporting a vulnerability

Please open a private security advisory (GitHub → Security → Advisories) or email the maintainer. Do not open public issues for vulnerabilities.
