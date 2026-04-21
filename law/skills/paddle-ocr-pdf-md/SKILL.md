---
name: paddle-ocr-pdf-md
description: Convert image-based PDF files into Markdown by calling a Paddle OCR HTTP API. Use when users in OpenClaw ask to OCR scanned/image PDFs, extract text from non-selectable PDF pages, or produce `.md` from picture-heavy contracts, letters, and legal files.
---

# Paddle OCR PDF MD

## Overview

Use this skill to turn scanned PDFs into markdown text via Paddle OCR API endpoints. Produce both a readable markdown file and a raw JSON artifact for traceability.

## Required Inputs

- Input PDF/image path
- Output markdown path
- Paddle layout-parsing API URL
- API token

Set API values by args or environment variables:

```bash
export PADDLE_OCR_API_URL="https://<your-host>/layout-parsing"
export PADDLE_OCR_API_KEY="<your-token>"
```

## Workflow

1. Confirm source file is an image/scanned PDF or text cannot be selected.
2. Run OCR conversion script.
3. Review markdown and downloaded image artifacts.
4. Return absolute paths of generated `.md` and `.json`.

## Run Commands

Recommended (your provided layout-parsing API):

```bash
python3 scripts/pdf_to_md_via_paddle_api.py \
  --mode layout-parsing-json \
  --auth-scheme token \
  --input-file /absolute/path/input.pdf \
  --output-md /absolute/path/output.md
```

If input is an image, set `--file-type 1` explicitly:

```bash
python3 scripts/pdf_to_md_via_paddle_api.py \
  --mode layout-parsing-json \
  --auth-scheme token \
  --file-type 1 \
  --input-file /absolute/path/input.png \
  --output-md /absolute/path/output.md
```

Control optional payload flags:

```bash
python3 scripts/pdf_to_md_via_paddle_api.py \
  --mode layout-parsing-json \
  --auth-scheme token \
  --input-file /absolute/path/input.pdf \
  --output-md /absolute/path/output.md \
  --use-doc-orientation-classify \
  --use-doc-unwarping \
  --no-use-chart-recognition
```

Generic fallback modes are still available:

```bash
python3 scripts/pdf_to_md_via_paddle_api.py \
  --mode multipart-pdf \
  --input-file /absolute/path/input.pdf \
  --output-md /absolute/path/output.md
```

## Output Rules

- Always generate markdown as final OCR text artifact.
- Always persist raw OCR JSON for auditability.
- For layout parsing responses, keep per-document sections (`## Document N`).
- Save split markdown docs under `<output-stem>_split/doc_{i}.md`.
- Download markdown/output images to `<output-stem>_assets/` by default.

## Integration In OpenClaw

- For legal workflows, run this OCR skill first to create `.md` from scanned PDF.
- Then hand markdown to downstream analysis/report skills (for example legal-counsel).
- If downstream output must be `.docx`, keep OCR `.md` as intermediate artifact and generate `.docx` in the next step.

## References

- API contract details: [`references/paddle-api-contract.md`](references/paddle-api-contract.md)
- Output structure details: [`references/output-spec.md`](references/output-spec.md)
