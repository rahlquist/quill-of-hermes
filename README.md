# Quill of Hermes — OvisOCR

LAN OCR web page and API for OvisOCR2 and TeleOCR. The page lists only these OCR models; Holo is not configured or served here.

## Isolation from Llama Hugs / llama.cpp

OvisOCR runs as its own `ovisocr.service` user unit on port 7860. It invokes the Ovis-local `llama-mtmd-cli-patched` with CPU-only settings (`--device none`, `--mmproj-device none`, `-ngl 0`, four threads). It does not change, restart, or share GPU allocation with the Llama Hugs service. Keep these settings service-local; do not export them in the user manager or shell globally.

The HTML page is served with `Cache-Control: no-store` so stale model choices cannot persist in a browser cache.

## Models

- `ovisocr2` — OvisOCR2-F16; default selection.
- `teleocr` — NaviDC-OCR Q4_K_M.

The model selector is a fixed allowlist in `app.py`. Do not populate it from `/v1/models`; that is Llama Hugs' inventory, not OvisOCR's.

## Requirements

- Linux and a systemd user manager.
- Python 3.10+, FastAPI, Uvicorn, and `python-multipart`.
- OvisOCR2 GGUF and its matching mmproj; optional NaviDC-OCR GGUF and mmproj under `~/.cache/llama.cpp/`.
- The Ovis-local `llama-mtmd-cli-patched` executable at `~/ovisocr/llama-mtmd-cli-patched`.
- `pdfinfo`/`pdftoppm` for PDF input and ImageMagick `magick` for TIFF input.

## Install and run

```bash
mkdir -p ~/ovisocr/static
uv venv ~/ovisocr/.venv
uv pip install --python ~/ovisocr/.venv/bin/python -r requirements.txt
```

Install the user unit from `ovisocr.service` at `~/.config/systemd/user/ovisocr.service`. Ensure its `OVISOCR_CLI` points to the Ovis-local patched executable and its CPU-only environment remains present. Then:

```bash
systemctl --user daemon-reload
systemctl --user enable --now ovisocr.service
```

After deploying app or model changes, restart only OvisOCR and run the cross-service check from `wimpy-setup`:

```bash
systemctl --user restart ovisocr.service
cd ~/wimpy-setup && python3 tools/verify_ovisocr_llama_isolation.py
```

The check exercises OCR and verifies that Llama Hugs remains active with the same API model inventory and process identity.

## API and page

- Page: `http://wimpy:7860/`
- Health: `GET /health`
- OCR: `POST /api/ocr`, multipart fields `file` and optional `model` (`ovisocr2` by default; `teleocr` is the other allowed value).
- Supported files: PNG, JPEG, WebP, PDF, TIFF; 100 MB maximum and 50 pages maximum.

Example:

```bash
curl --fail-with-body --max-time 330 \
  -F 'file=@document.pdf' -F 'model=ovisocr2' \
  http://wimpy:7860/api/ocr
```

The JSON response contains `markdown`, `elapsed_seconds`, `page_count`, and `model`.

## Tests

```bash
python -m unittest discover -s tests -v
```

The unit tests check the Ovis-only model allowlist, CPU-only CLI arguments, and page cache/model labels. GitHub Actions runs the same suite. The WIMPY cross-service smoke test is run after deployment; it uses a synthetic fixture and does not send a model-generation request to Llama Hugs.
