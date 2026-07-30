# OvisOCR LAN Service

A small LAN web wrapper around OvisOCR2 GGUF and llama.cpp `llama-mtmd-cli`. It accepts PNG, JPEG, and WebP images and returns Markdown plus measured OCR runtime.

## Requirements

- Linux host; systemd user service instructions assume systemd
- Python 3.10+
- `uv` or Python virtualenv/pip
- FastAPI, Uvicorn, python-multipart
- llama.cpp build containing `llama-mtmd-cli` with `--model`, `--mmproj`, and `--image`
- OvisOCR2 main GGUF plus matching `mmproj-*.gguf`
- Enough RAM/VRAM for the model

Tested pair:

```text
OvisOCR2-F16.gguf
mmproj-F16.gguf
```

## API

```bash
curl -X POST -F file=@document.png http://HOST:7860/api/ocr
```

Response:

```json
{"markdown":"...","elapsed_seconds":3.039}
```

`elapsed_seconds` measures the llama.cpp subprocess from launch through completion. It includes model loading, image encoding, and generation; it does not include browser upload time.

## Configuration

```text
OVISOCR_MODEL=/path/to/OvisOCR2-F16.gguf
OVISOCR_MMPROJ=/path/to/mmproj-F16.gguf
OVISOCR_CLI=/path/to/llama-mtmd-cli
OVISOCR_PORT=7860
```

The service accepts only PNG/JPEG/WebP, limits uploads to 25 MB, permits one OCR process at a time, applies a five-minute timeout, and cleans temporary files after each request. Keep it LAN-only unless authentication and a reverse proxy are added.

## Install

```bash
mkdir -p ~/ovisocr/static
uv venv ~/ovisocr/.venv
uv pip install --python ~/ovisocr/.venv/bin/python fastapi 'uvicorn[standard]' python-multipart
```

Run manually:

```bash
~/ovisocr/.venv/bin/python ~/ovisocr/app.py
```

Health check:

```bash
curl http://127.0.0.1:7860/health
```

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

## Hermes integration

Hermes has no built-in OvisOCR-specific skill. A local skill can call this HTTP API, provided it can access the image path and reach Wimpy. The skill should POST the image to `/api/ocr`, consume `markdown` and `elapsed_seconds`, and tell Hermes to verify handwriting and mathematical symbols. A reusable skill should make the endpoint configurable rather than hard-code Wimpy.

## Troubleshooting

```bash
systemctl --user status ovisocr.service
journalctl --user -u ovisocr.service
curl http://127.0.0.1:7860/health
```

The service intentionally remains separate from llama-swap because multimodal `llama-server` support has not been proven for this model.
