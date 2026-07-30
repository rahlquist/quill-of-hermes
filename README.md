# OvisOCR LAN Service

LAN web wrapper around OvisOCR2 GGUF and llama.cpp `llama-mtmd-cli`. Accepts single images, PDFs, and multi-page TIFFs and returns Markdown.

## Requirements

- Linux host; systemd user service instructions assume systemd
- Python 3.10+, `uv`, FastAPI, Uvicorn, python-multipart
- llama.cpp build containing `llama-mtmd-cli` with `--model`, `--mmproj`, and `--image`
- OvisOCR2 main GGUF plus matching `mmproj-*.gguf`
- `pdftoppm` and `pdfinfo` for PDF input
- ImageMagick `magick` for TIFF input

## Supported input

- PNG, JPEG, WebP: single page
- PDF: rendered at 150 DPI, up to 50 pages
- TIFF/TIF: single or multi-page, up to 50 pages; ImageMagick renders each page
- Upload limit: 100 MB

Each page is sent independently to OvisOCR2. Results are joined with a Markdown horizontal rule (`---`). The API also returns `page_count` and total `elapsed_seconds`.

## API

```bash
curl -X POST -F file=@document.pdf http://HOST:7860/api/ocr
```

Response:

```json
{"markdown":"page one...\n\n---\n\npage two...","elapsed_seconds":12.731,"page_count":2}
```

Timing includes rendering plus all page OCR subprocesses, not browser upload time.

## Configuration

```text
OVISOCR_MODEL=/path/to/OvisOCR2-F16.gguf
OVISOCR_MMPROJ=/path/to/mmproj-F16.gguf
OVISOCR_CLI=/path/to/llama-mtmd-cli
OVISOCR_PORT=7860
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

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now ovisocr.service
```

The service serializes jobs, limits documents to 50 pages and 100 MB, applies a five-minute timeout per page, and cleans temporary files. Keep it LAN-only unless authentication and a reverse proxy are added.

## Hermes integration

The companion Hermes skill calls `/api/ocr`, consumes `markdown`, `elapsed_seconds`, and `page_count`, and requires visual verification of uncertain handwriting, symbols, equations, names, and numbers. PDF and TIFF are now supported through the same endpoint.

## Troubleshooting

```bash
systemctl --user status ovisocr.service
journalctl --user -u ovisocr.service
curl http://127.0.0.1:7860/health
```

For PDFs, verify `pdfinfo` and `pdftoppm`. For TIFFs, verify `magick identify` and `magick`.

The service remains separate from llama-swap because multimodal `llama-server` support has not been proven for this model.
