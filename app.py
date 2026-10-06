from pathlib import Path
import asyncio, os, subprocess, tempfile, time
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
ROOT=Path(__file__).resolve().parent; STATIC=ROOT/'static'
CLI=os.getenv('OVISOCR_CLI',str(ROOT/'llama-mtmd-cli-patched'))
PROMPT='Extract all readable content from this image in natural reading order. Output only the transcription as Markdown. Preserve wording, punctuation, paragraph breaks, and mathematical notation. Do not translate or paraphrase.'
IMAGE_EXT={'.png','.jpg','.jpeg','.webp','.tif','.tiff'}; MAX_BYTES=100*1024*1024

# Run OCR on the RTX 5060 Ti (CUDA0). NaviDC's 1.3 GiB projector
# currently fails CUDA allocation, so keep only that projector on CPU.
CUDA_ARGS = ['--device', 'CUDA0', '--mmproj-device', 'CUDA0', '-ngl', '99', '-t', '4']
CUDA_MODEL_CPU_MMPROJ_ARGS = ['--device', 'CUDA0', '--mmproj-device', 'none', '-ngl', '99', '-t', '4']

MODELS = {
    'ovisocr2': {
        'model': os.getenv('OVISOCR_MODEL', str(Path.home()/'.cache/llama.cpp/OvisOCR2-F16.gguf')),
        'mmproj': os.getenv('OVISOCR_MMPROJ', str(Path.home()/'.cache/llama.cpp/OvisOCR2-F16.mmproj.gguf')),
        'cli': CLI,
        'cli_args': CUDA_ARGS.copy(),
    },
    'teleocr': {
        'model': str(Path.home()/'.cache/llama.cpp/NaviDC-OCR-Q4_K_M.gguf'),
        'mmproj': str(Path.home()/'.cache/llama.cpp/NaviDC-OCR-mmproj-f16.gguf'),
        'cli': CLI,
        'cli_args': CUDA_MODEL_CPU_MMPROJ_ARGS.copy(),
    },
}

app=FastAPI(title='OvisOCR'); app.mount('/static',StaticFiles(directory=STATIC),name='static'); lock=asyncio.Semaphore(1)

@app.get('/',response_class=HTMLResponse)
def index():
    return FileResponse(
        STATIC/'index.html',
        headers={'Cache-Control':'no-store, no-cache, must-revalidate, max-age=0'},
    )

@app.get('/health')
def health():
    return {
        'ok': True,
        'models': {
            name: Path(m['model']).is_file() and Path(m['mmproj']).is_file() and Path(m.get('cli', CLI)).is_file()
            for name, m in MODELS.items()
        },
        'cli': Path(CLI).exists(),
    }

MAX_PAGES = 50


def render_pages(path, suffix, td):
    if suffix == '.pdf':
        out = Path(td) / 'page'
        info = subprocess.run(['pdfinfo', str(path)], capture_output=True, text=True, timeout=20)
        if info.returncode:
            raise HTTPException(400, 'Invalid PDF.')
        try:
            page_count = next(
                (int(line.split(':', 1)[1]) for line in info.stdout.splitlines() if line.startswith('Pages:')),
                0,
            )
        except ValueError as exc:
            raise HTTPException(400, 'Could not determine PDF page count.') from exc
        if page_count < 1:
            raise HTTPException(400, 'PDF must contain at least 1 page.')
        if page_count > MAX_PAGES:
            raise HTTPException(413, 'Document exceeds the 50-page limit.')
        rendered = subprocess.run(
            ['pdftoppm', '-r', '150', '-jpeg', str(path), str(out)],
            capture_output=True, text=True, timeout=120,
        )
        if rendered.returncode:
            raise HTTPException(400, 'PDF rendering failed.')
        pages = sorted(Path(td).glob('page-*.jpg'))
        if len(pages) != page_count:
            raise HTTPException(400, 'PDF rendering produced an unexpected page count.')
        return pages
    if suffix in {'.tif', '.tiff'}:
        identify = subprocess.run(
            ['magick', 'identify', '-format', '%n' + chr(10), str(path)],
            capture_output=True, text=True, timeout=30,
        )
        if identify.returncode:
            raise HTTPException(400, 'TIFF decoding failed; ImageMagick is required.')
        try:
            frame_counts = [int(line) for line in identify.stdout.splitlines() if line]
        except ValueError as exc:
            raise HTTPException(400, 'Could not determine TIFF page count.') from exc
        if not frame_counts:
            raise HTTPException(400, 'Could not determine TIFF page count.')
        if len(set(frame_counts)) != 1 or frame_counts[0] != len(frame_counts):
            raise HTTPException(400, 'Could not verify TIFF page count.')
        page_count = len(frame_counts)
        if page_count > MAX_PAGES:
            raise HTTPException(413, 'Document exceeds the 50-page limit.')
        if page_count < 1:
            raise HTTPException(400, 'TIFF must contain at least 1 page.')
        out = Path(td) / 'page-%04d.png'
        converted = subprocess.run(
            ['magick', str(path), '-alpha', 'off', str(out)],
            capture_output=True, text=True, timeout=120,
        )
        if converted.returncode:
            raise HTTPException(400, 'TIFF page rendering failed.')
        pages = sorted(Path(td).glob('page-*.png'))
        if len(pages) != page_count:
            raise HTTPException(400, 'TIFF rendering produced an unexpected page count.')
        return pages
    raise HTTPException(400, 'Unsupported document format.')

async def run_one(image, model_path, mmproj_path, cli_path=None, cli_args=None):
    cli = cli_path or CLI
    cmd=[cli,'-m',str(model_path),'--mmproj',str(mmproj_path),'--image',str(image),'-p',PROMPT,'-n','4096','--temp','0']
    cmd.extend(cli_args or [])
    p=await asyncio.to_thread(subprocess.run,cmd,capture_output=True,text=True,timeout=300)
    if p.returncode or not p.stdout.strip(): raise RuntimeError(p.stderr[-1000:] or 'OCR returned no text')
    return p.stdout.strip()

@app.post('/api/ocr')
async def ocr(file:UploadFile=File(...), model:str=Form('ovisocr2')):
    suffix=Path(file.filename or '').suffix.lower()
    if suffix not in IMAGE_EXT and suffix!='.pdf': raise HTTPException(400,'Upload PNG, JPEG, WebP, PDF, or TIFF.')
    if model not in MODELS: raise HTTPException(400,f'Unknown model: {model}.')
    m = MODELS[model]
    if not (Path(m['model']).is_file() and Path(m['mmproj']).is_file() and Path(CLI).is_file()):
        raise HTTPException(503,'OCR runtime is not configured.')
    data=await file.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES: raise HTTPException(413,'Document exceeds the 100 MB limit.')
    async with lock:
        with tempfile.TemporaryDirectory(prefix='ovisocr-') as td:
            src=Path(td)/('input'+suffix); src.write_bytes(data); started=time.perf_counter()
            pages=render_pages(src,suffix,td) if suffix in {'.pdf','.tif','.tiff'} else [src]
            results=[]
            for n,page in enumerate(pages,1):
                try: results.append(await run_one(page, m['model'], m['mmproj'], m.get('cli'), m.get('cli_args')))
                except asyncio.TimeoutError: raise HTTPException(504,f'OCR timed out on page {n}.')
                except subprocess.TimeoutExpired: raise HTTPException(504,f'OCR timed out on page {n}.')
                except Exception as e: raise HTTPException(502,f'OCR failed on page {n}: {e}')
            sep='\n\n---\n\n'; return {'markdown':sep.join(results),'elapsed_seconds':round(time.perf_counter()-started,3),'page_count':len(results),'model':model}

if __name__=='__main__':
    import uvicorn; uvicorn.run(app,host='0.0.0.0',port=int(os.getenv('OVISOCR_PORT','7860')))
# end