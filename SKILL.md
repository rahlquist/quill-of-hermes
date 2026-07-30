---
name: ovisocr
description: Use when OCR is needed from an image via OvisOCR.
version: 1.0.0
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

## Endpoint

Default endpoint:

```text
http://wimpy:7860
```

Override with `OVISOCR_URL` when the service is hosted elsewhere. The service must be reachable from the Hermes runtime.

## Workflow

1. Confirm the source image is available as a local file path.
2. POST it as multipart field `file` to `${OVISOCR_URL:-http://wimpy:7860}/api/ocr`.
3. Accept PNG, JPEG, or WebP only. The service limits uploads to 25 MB and serializes OCR jobs.
4. Read JSON fields `markdown` and `elapsed_seconds`.
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
{"markdown":"...","elapsed_seconds":3.039}
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
{"ok":true,"model":true,"mmproj":true,"cli":true}
```

If a runtime field is false, do not claim OCR was performed. If the request returns 502, inspect `journalctl --user -u ovisocr.service` on the host.

## Limitations

- Image OCR only; PDF support is not exposed yet.
- Backend is OvisOCR2 GGUF through `llama-mtmd-cli`.
- Handwriting and mathematical notation can contain recognition errors.
- Do not silently correct text based on expectation. Preserve the result and mark uncertain corrections.
- Do not send secrets or unrelated files to the endpoint.

## Verification checklist

- [ ] Source image exists and has an accepted extension.
- [ ] Health check is available or the API request succeeds.
- [ ] Response contains non-empty Markdown.
- [ ] OCR timing is captured when reporting performance.
- [ ] Symbols, equations, names, dates, and ambiguous characters are visually checked before presenting exact transcription.
