from pathlib import Path
import asyncio, os, subprocess, tempfile, time
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
ROOT=Path(__file__).resolve().parent; STATIC=ROOT/'static'
MODEL=Path(os.getenv('OVISOCR_MODEL','/home/rahlquist/.cache/llama.cpp/OvisOCR2-F16.gguf'))
MMPROJ=Path(os.getenv('OVISOCR_MMPROJ','/home/rahlquist/.cache/llama.cpp/mmproj-F16.gguf'))
CLI=os.getenv('OVISOCR_CLI','/opt/llama-cuda/bin/llama-mtmd-cli')
PROMPT='Extract all readable content from this image in natural reading order. Output only the transcription as Markdown. Preserve wording, punctuation, paragraph breaks, and mathematical notation. Do not translate or paraphrase.'
app=FastAPI(title='OvisOCR'); app.mount('/static',StaticFiles(directory=STATIC),name='static'); lock=asyncio.Semaphore(1)
@app.get('/',response_class=HTMLResponse)
def index(): return FileResponse(STATIC/'index.html')
@app.get('/health')
def health(): return {'ok':True,'model':MODEL.exists(),'mmproj':MMPROJ.exists(),'cli':Path(CLI).exists()}
@app.post('/api/ocr')
async def ocr(file:UploadFile=File(...)):
    suffix=Path(file.filename or '').suffix.lower()
    if suffix not in {'.png','.jpg','.jpeg','.webp'}: raise HTTPException(400,'Upload a PNG, JPEG, or WebP image.')
    if not (MODEL.is_file() and MMPROJ.is_file() and Path(CLI).is_file()): raise HTTPException(503,'OCR runtime is not configured.')
    data=await file.read(25*1024*1024+1)
    if len(data)>25*1024*1024: raise HTTPException(413,'Image exceeds the 25 MB limit.')
    async with lock:
        with tempfile.TemporaryDirectory(prefix='ovisocr-') as td:
            image=Path(td)/('input'+suffix); image.write_bytes(data)
            cmd=[CLI,'-m',str(MODEL),'--mmproj',str(MMPROJ),'--image',str(image),'-p',PROMPT,'-n','4096','--temp','0']
            started=time.perf_counter()
            try: proc=await asyncio.to_thread(subprocess.run,cmd,capture_output=True,text=True,timeout=300,cwd=td)
            except subprocess.TimeoutExpired: raise HTTPException(504,'OCR timed out after 5 minutes.')
            elapsed=time.perf_counter()-started
            if proc.returncode: raise HTTPException(502,'OCR process failed. Check the service log.')
            if not proc.stdout.strip(): raise HTTPException(502,'OCR returned no text.')
            return {'markdown':proc.stdout.strip(),'elapsed_seconds':round(elapsed,3)}
if __name__=='__main__':
    import uvicorn; uvicorn.run(app,host='0.0.0.0',port=int(os.getenv('OVISOCR_PORT','7860')))
# end
