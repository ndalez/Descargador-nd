import os
import logging
import imageio_ffmpeg
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
    return {"status": "ok", "message": "Backend funcionando correctamente"}

@app.post("/download")
async def download_media(request: DownloadRequest, background_tasks: BackgroundTasks):
    url = request.url
    is_audio = request.format.lower() == "mp3"

    # Obtener la ruta ejecutable de FFmpeg provista por imageio-ffmpeg
    ffmpeg_exe_path = imageio_ffmpeg.get_ffmpeg_exe()
    logger.info(f"Ruta de FFmpeg detectada: {ffmpeg_exe_path}")

    # Configuración de formatos con fallback automático
    if is_audio:
        format_spec = 'bestaudio/best'
    else:
        format_spec = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

    ydl_opts = {
        'format': format_spec,
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'noplaylist': True,
        'quiet': False,
        'no_warnings': False,
        'ffmpeg_location': ffmpeg_exe_path,  # Le indicamos a yt-dlp dónde está FFmpeg
        'cookiefile': 'cookies.txt',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web']
            }
        }
    }

    # Si se pide MP3, usamos FFmpeg para convertir a audio limpio MP3
    if is_audio:
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info("Extrayendo e iniciando descarga...")
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            if is_audio:
                base_name, _ = os.path.splitext(filename)
                potential_mp3 = f"{base_name}.mp3"
                if os.path.exists(potential_mp3):
                    filename = potential_mp3

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
