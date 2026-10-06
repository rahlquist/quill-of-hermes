---
name: ovisocr
description: Use when OCR is needed from an image via OvisOCR.
version: 1.1.0
author: Richard Ahlquist
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ocr, vision, handwriting, markdown, ovisocr]
    related_skills: [hermes-agent]
---

# OvisOCR

Use the Quill of Hermes OvisOCR HTTP service for image OCR when a local image contains handwriting, printed text, tables, formulas, or document layout that should be converted to Markdown.

The WIMPY deployment runs OCR inference on the RTX 5060 Ti (`CUDA0`). OvisOCR2 uses CUDA for both model and projector; TeleOCR (NaviDC-OCR) uses CUDA for its model and CPU for its large projector because the projector fails CUDA allocation in the current build. This service is separate from Llama Hugs/llama-swap, but shares the physical GPU and can contend for GPU resources. Do not describe the OCR service as CPU-only or GPU-isolated.

For PDF/TIFF inputs, the server checks the rendered page count against the source count and rejects documents over 50 pages before doing full page conversion.

## Endpoint

Default endpoint:

```text
http://wimpy:7860
```

Override with `OVISOCR_URL` when the service is hosted elsewhere. The service must be reachable from the Hermes runtime.

## Workflow

1. Confirm the source image is available as a local file path.
2. POST it as multipart field `file` to `${OVISOCR_URL:-http://wimpy:7860}/api/ocr`.
3. Accept PNG, JPEG, WebP, PDF, or TIFF. The service limits uploads to 100 MB and 50 pages, and serializes OCR jobs.
4. Read JSON fields `markdown`, `elapsed_seconds`, and `page_count`.
5. Use the Markdown in the current task, preserving model structure unless cleanup is requested.
6. Report OCR time when relevant.
7. Verify uncertain handwriting, mathematical symbols, names, numbers, and punctuation against the source image. OCR output is not ground truth.

## Shell recipe

```bash
OVISOCR_URL="${OVISOCR_URL:-http://wimpy:7860}"
curl --fail-with-body --max-time 330 \
  -X POST -F "file=@/absolute/path/to/image.png" \
  "$OVISOCR_URL/api/ocr"
```

Response shape:

```json
{"markdown":"...","model":"ovisocr2","elapsed_seconds":3.039,"page_count":1}
```

Markdown-only extraction:

```bash
curl --fail-with-body --max-time 330 \
  -X POST -F "file=@/absolute/path/to/image.png" \
  "$OVISOCR_URL/api/ocr" | python3 -c 'import json,sys; print(json.load(sys.stdin)["markdown"])'
```

## Health check

```bash
curl --fail --max-time 5 "$OVISOCR_URL/health"
```

Expected fields:

```json
{"ok":true,"models":{"ovisocr2":true,"teleocr":true},"cli":true}
```

If `ok` is false or either selected model reports false under `models`, do not claim OCR succeeded. The health response also reports whether the executable exists under `cli`, for example: `{"ok":true,"models":{"ovisocr2":true,"teleocr":true},"cli":true}`. If a request returns 502, inspect `journalctl --user -u ovisocr.service` on the OCR host.

## Limitations

- Supports PNG, JPEG, WebP, PDF, and single/multi-page TIFF through the same endpoint. PDFs and TIFFs are processed page by page and joined with `---`.
- Backend is an Ovis-local `llama-mtmd-cli-patched` executable with a fixed allowlist: OvisOCR2 (default) and TeleOCR (NaviDC-OCR).
- Handwriting and mathematical notation can contain recognition errors.
- Do not silently correct text based on expectation. Preserve the result and mark uncertain corrections.
- Do not send secrets or unrelated files to the endpoint.

## Verification checklist

- [ ] Source image exists and has an accepted extension.
- [ ] Health check is available or the API request succeeds.
- [ ] Response contains non-empty Markdown.
- [ ] OCR timing is captured when reporting performance.
- [ ] Symbols, equations, names, dates, and ambiguous characters are visually checked before presenting exact transcription.
