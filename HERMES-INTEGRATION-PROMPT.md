# Architected Integration Prompt: Quill of Hermes OvisOCR

Copy the prompt below into another Hermes installation.

---

You are integrating the **Quill of Hermes OvisOCR service** into Hermes as a user-local skill.

## Objective

Create a user-local Hermes skill named `ovisocr` that lets Hermes send local image, PDF, and TIFF files to an existing OvisOCR HTTP service and use the returned Markdown in the current task.

Do not rebuild the OCR model. Do not modify llama-swap. The remote OCR service owns model execution.

## Current WIMPY deployment notes

- OCR inference runs on the RTX 5060 Ti (`CUDA0`) via the Ovis-local `llama-mtmd-cli-patched` executable.
- OvisOCR2 uses CUDA0 for both its model and mmproj.
- TeleOCR (NaviDC-OCR) uses CUDA0 for its OCR model but keeps its 1.3 GiB mmproj on CPU because it fails CUDA allocation in the current build.
- The service sets `CUDA_VISIBLE_DEVICES=0` and uses four CPU threads. Do not add CPU-only `LLAMA_ARG_DEVICE=none`, `LLAMA_ARG_N_GPU_LAYERS=0`, or `MTMD_BACKEND_DEVICE=none` overrides.
- The OCR process is separate from Llama Hugs/llama-swap, but shares the physical GPU and therefore can contend for GPU resources. This is process separation, not GPU resource isolation.
- After deploying on WIMPY, run `python3 ~/wimpy-setup/tools/verify_ovisocr_llama_isolation.py`. It runs the smoke fixture against both OCR models and verifies Llama Hugs remains active with unchanged process ID and model inventory.

## Service contract

The service runs OCR inference on the RTX 5060 Ti (`CUDA0`) through the Ovis-local `llama-mtmd-cli-patched` executable. OvisOCR2 uses CUDA0 for both model and mmproj. TeleOCR (NaviDC-OCR) uses CUDA0 for its model, while its 1.3 GiB mmproj stays on CPU because it fails CUDA allocation in the current build. The OCR service runs in a separate process from Llama Hugs/llama-swap and shares the GPU, so it can contend for GPU resources.

Default endpoint:

```text
http://wimpy:7860
```

Allow override through:

```text
OVISOCR_URL
```

Health endpoint:

```http
GET /health
```

Expected health response:

```json
{"ok":true,"models":{"ovisocr2":true,"teleocr":true},"cli":true}
```

OCR endpoint:

```http
POST /api/ocr
Content-Type: multipart/form-data
Field: file
```

Accepted formats:

- PNG
- JPEG/JPG
- WebP
- PDF
- TIFF/TIF, including multi-page TIFF

Current service limits:

- 100 MB per upload
- 50 pages per document
- One OCR job at a time
- Five-minute timeout per page

Successful response:

```json
{
  "markdown": "...",
  "model": "ovisocr2",
  "elapsed_seconds": 12.731,
  "page_count": 2
}
```

For multi-page documents, page results are joined with a Markdown horizontal rule:

```markdown
---
```

## Required skill behavior

1. Trigger when the user asks to read, transcribe, extract, or OCR an image, PDF, or TIFF.
2. Verify the source file exists before sending it.
3. Use the configured `OVISOCR_URL`, defaulting to `http://wimpy:7860`.
4. Check `/health` when the service is unavailable or before the first request in a troubleshooting flow.
5. POST the file as multipart field `file` to `/api/ocr`.
6. Enforce a client timeout of at least 330 seconds.
7. Read `markdown`, `elapsed_seconds`, and `page_count` from the response.
8. Return or use the Markdown result without silently paraphrasing it.
9. Visually verify ambiguous handwriting, mathematical symbols, names, dates, numbers, and punctuation before presenting an exact transcription.
10. Never claim OCR succeeded if the response is an error, empty, or missing required fields.
11. Do not send secrets or unrelated files to the service.
12. Report page count and OCR duration when useful.

## Suggested implementation

Create:

```text
${HERMES_HOME:-$HOME/.hermes}/skills/ovisocr/SKILL.md
```

Use valid Hermes skill frontmatter. Keep the endpoint configurable and do not hard-code Wimpy filesystem paths.

The skill may use `curl` or an equivalent HTTP client. A shell request looks like:

```bash
OVISOCR_URL="${OVISOCR_URL:-http://wimpy:7860}"
curl --fail-with-body --max-time 330 \
  -X POST \
  -F "file=@/absolute/path/to/input.pdf" \
  "$OVISOCR_URL/api/ocr"
```

## Verification requirements

Before concluding that the deployed OCR service is healthy, inspect `GET /health`: require `ok: true`, the selected model set to true under `models`, and `cli: true`. The health schema is `{"ok":true,"models":{"ovisocr2":true,"teleocr":true},"cli":true}`.

After creating the skill:

1. Validate its frontmatter and name.
2. Check the service health endpoint.
3. Submit one small image and confirm non-empty Markdown.
4. Submit a multi-page PDF or TIFF if available and confirm `page_count > 1`.
5. Confirm the skill does not expose or persist credentials.
6. Explain that the current session may need to be restarted before Hermes's skill index notices a newly created skill.

## Non-goals

- Do not install packages on the OCR host unless explicitly requested.
- Do not modify llama-swap configuration.
- Do not expose the OCR service to the public Internet.
- Do not treat OCR output as authoritative for ambiguous characters or equations.

## Deliverable

Return:

- The absolute path of the created skill.
- The configured endpoint.
- Verification results.
- Any limitations or missing prerequisites.

---

This prompt is intentionally explicit: it separates the Hermes skill from the OCR server, defines the HTTP contract, and gives the integrating agent testable completion criteria.