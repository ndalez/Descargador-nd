import os
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yt_dlp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("yt_downloader")

app = FastAPI(title="YouTube Downloader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOAD_DIR = "temp_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

class DownloadRequest(BaseModel):
    url: str
    format: str  # "mp3" o "mp4"

def cleanup_file(filepath: str):
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            logger.info(f"Archivo eliminado correctamente: {filepath}")
        except Exception as e:
            logger.error(f"Error al eliminar archivo {filepath}: {e}")

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Backend funcionando"}

@app.post("/download")
async def download_media(request: DownloadRequest, background_tasks: BackgroundTasks):
    url = request.url
    is_audio = request.format.lower() == "mp3"

    logger.info(f"Petición recibida - URL: {url} | Formato: {request.format}")

    # Criterio de selección de formato 100% compatible sin requerir FFmpeg
    if is_audio:
        # Descarga el audio nativo directamente (usualmente m4a o webm)
        format_spec = 'bestaudio/best'
    else:
        # Descarga el mejor archivo pre-combinado de vídeo y audio directo
        format_spec = 'best[ext=mp4]/best'

    ydl_opts = {
        'format': format_spec,
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'cookiefile': 'cookies.txt',  # Lee las cookies subidas
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web']
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info("Iniciando descarga con yt-dlp...")
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        if not os.path.exists(filename):
            raise HTTPException(status_code=500, detail="El archivo no se pudo encontrar tras la descarga.")

        download_name = os.path.basename(filename)
        background_tasks.add_task(cleanup_file, filename)

        return FileResponse(
            path=filename,
            filename=download_name,
            media_type="application/octet-stream"
        )

    except yt_dlp.utils.DownloadError as de:
        logger.error(f"Error en yt-dlp: {str(de)}")
        raise HTTPException(
            status_code=400,
            detail=f"Error en el formato del video: {str(de)}"
        )
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Ocurrió un error en el servidor: {str(e)}"
        )
