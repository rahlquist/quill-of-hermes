# Quill of Hermes — OvisOCR

LAN OCR page and API for OvisOCR2 (default) and TeleOCR, using an Ovis-local `llama-mtmd-cli-patched`. The page uses a fixed OCR model allowlist; it does not expose Llama Hugs models such as Holo.

## Requirements

- Linux host; systemd user service instructions assume systemd
- Python 3.10+, `uv`, FastAPI, Uvicorn, python-multipart
- Ovis-local `llama-mtmd-cli-patched` executable with `--model`, `--mmproj`, and `--image`
- OvisOCR2 main GGUF plus its matching OvisOCR2 mmproj; optionally NaviDC-OCR plus its matching mmproj
- The deployed service runs the OCR model on CUDA0 (the RTX 5060 Ti); OvisOCR2 also runs its matching projector on CUDA0
- TeleOCR (NaviDC-OCR) runs its model on CUDA0 but keeps its 1.3 GiB projector on CPU because that projector fails CUDA allocation in the current build
- OCR uses its own `llama-mtmd-cli-patched` process, separate from Llama Hugs and llama-swap; it still consumes resources on the same physical GPU
- The service sets `CUDA_VISIBLE_DEVICES=0` and uses four CPU threads for CPU-side work
- `pdftoppm` and `pdfinfo` for PDF input
- ImageMagick `magick` for TIFF input

## Supported input

- PNG, JPEG, WebP: single page
- PDF: page count is checked before rendering; rendered at 150 DPI, up to 50 pages
- TIFF/TIF: page count is checked before rendering; single or multi-page up to 50 pages, rendered by ImageMagick
- Upload limit: 100 MB

Each page is sent independently to the selected OCR model (`ovisocr2` or `teleocr`). Results are joined with a Markdown horizontal rule (`---`). The API returns `markdown`, `model`, `page_count`, and total `elapsed_seconds`.

## API

```bash
curl -X POST -F file=@document.pdf -F model=ovisocr2 http://HOST:7860/api/ocr
```

Response:

```json
{"markdown":"page one...\n\n---\n\npage two...","model":"ovisocr2","elapsed_seconds":12.731,"page_count":2}
```

Timing includes rendering plus all page OCR subprocesses, not browser upload time.

## Configuration

```text
OVISOCR_MODEL=~/.cache/llama.cpp/OvisOCR2-F16.gguf
OVISOCR_MMPROJ=~/.cache/llama.cpp/OvisOCR2-F16.mmproj.gguf
OVISOCR_CLI=~/ovisocr/llama-mtmd-cli-patched
OVISOCR_PORT=7860
# The service uses CUDA0; these settings are service-local:
CUDA_VISIBLE_DEVICES=0
LLAMA_ARG_THREADS=4
```

## Install

```bash
mkdir -p ~/ovisocr/static
uv venv ~/ovisocr/.venv
uv pip install --python ~/ovisocr/.venv/bin/python fastapi 'uvicorn[standard]' python-multipart
```

Run manually with `~/ovisocr/.venv/bin/python ~/ovisocr/app.py`. Health is `/health`.

## systemd user service

Create `~/.config/systemd/user/ovisocr.service`:

```ini
[Unit]
Description=OvisOCR LAN web service
After=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/ovisocr
ExecStart=%h/ovisocr/.venv/bin/python %h/ovisocr/app.py
Restart=on-failure
RestartSec=5
Environment=OVISOCR_PORT=7860
Environment=OVISOCR_CLI=%h/ovisocr/llama-mtmd-cli-patched
Environment=CUDA_VISIBLE_DEVICES=0
Environment=LLAMA_ARG_THREADS=4

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now ovisocr.service
```

The service serializes jobs, limits documents to 50 pages and 100 MB, applies a five-minute timeout per page, and cleans temporary files. Keep it LAN-only unless authentication and a reverse proxy are added.

## Tests and post-deploy isolation check

Run the OvisOCR unit tests with:

```bash
python -m unittest discover -s tests -v
```

The smoke test fixture, `tests/fixtures/ocr-smoke.png`, contains the expected text `OVIS OCR SMOKE TEST` and `ORANGE 42`.

### Cross-service smoke test

After deploying either OvisOCR or Llama Hugs on WIMPY, run the cross-service smoke test from `wimpy-setup`:

```bash
python3 tools/verify_ovisocr_llama_isolation.py
```

The check is read-only with respect to Llama Hugs. It submits a synthetic OCR page to both OvisOCR2 and TeleOCR, confirms both models recognize the expected text, checks CUDA0 service configuration and the model-specific projector placement, and verifies Llama Hugs remains active with the same process identity and model inventory. It does not call a Llama Hugs model, restart either service, or modify Llama Hugs.

## Hermes integration

The companion Hermes skill calls `/api/ocr`, consumes `markdown`, `elapsed_seconds`, and `page_count`, and requires visual verification of uncertain handwriting, symbols, equations, names, and numbers. PDF and TIFF are supported through the same endpoint.

## Troubleshooting

```bash
systemctl --user status ovisocr.service
journalctl --user -u ovisocr.service
curl http://127.0.0.1:7860/health
```

For PDFs, verify `pdfinfo` and `pdftoppm`. For TIFFs, verify `magick identify` and `magick`.

The service remains separate from llama-swap because multimodal `llama-server` support has not been proven for this model.
