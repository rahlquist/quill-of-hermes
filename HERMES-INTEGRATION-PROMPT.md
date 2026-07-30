# Architected Integration Prompt: Quill of Hermes OvisOCR

Copy the prompt below into another Hermes installation.

---

You are integrating the **Quill of Hermes OvisOCR service** into Hermes as a user-local skill.

## Objective

Create a user-local Hermes skill named `ovisocr` that lets Hermes send local image, PDF, and TIFF files to an existing OvisOCR HTTP service and use the returned Markdown in the current task.

Do not rebuild the OCR model. Do not modify llama-swap. The remote OCR service owns model execution.

## Service contract

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
{"ok":true,"model":true,"mmproj":true,"cli":true}
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