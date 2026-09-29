import os
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yt_dlp

# Configuración de logs para depuración en Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("yt_downloader")

app = FastAPI(title="YouTube Downloader API")

# Habilitar CORS para peticiones desde GitHub Pages o cualquier dispositivo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Carpeta donde se guardarán temporalmente los videos descargados
DOWNLOAD_DIR = "temp_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


class DownloadRequest(BaseModel):
    url: str
    format: str  # "mp3" o "mp4"


def cleanup_file(filepath: str):
    """Elimina el archivo del servidor de Render después de haberlo enviado al usuario"""
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            logger.info(f"Archivo eliminado correctamente: {filepath}")
        except Exception as e:
            logger.error(f"Error al eliminar el archivo {filepath}: {e}")


@app.get("/")
def read_root():
    return {"status": "ok", "message": "Backend del descargador de YouTube funcionando correctamente"}


@app.post("/download")
async def download_media(request: DownloadRequest, background_tasks: BackgroundTasks):
    url = request.url
    is_audio = request.format.lower() == "mp3"

    logger.info(f"Procesando solicitud de descarga. URL: {url} | Formato: {request.format}")

    # Definir el formato con alternativas flexibles para evitar errores de formato no disponible
    if is_audio:
        # Intenta descargar el mejor audio disponible
        format_selection = 'bestaudio/best'
    else:
        # Intenta descargar video + audio en MP4; si no es posible, descarga el mejor MP4 directo
        format_selection = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

    ydl_opts = {
        'format': format_selection,
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'noplaylist': True,
        'quiet': False,
        'no_warnings': False,
        'cookiefile': 'cookies.txt',  # Autenticación con cookies subidas a la raíz
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

    # Si solicita MP3 y existe ffmpeg instalado, aplica el postprocesador de extracción
    if is_audio:
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info("Extrayendo información del video...")
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            # Si se convirtió a MP3, ajustar el nombre de la extensión generada
            if is_audio:
                base_name, _ = os.path.splitext(filename)
                potential_mp3 = f"{base_name}.mp3"
                if os.path.exists(potential_mp3):
                    filename = potential_mp3

        if not os.path.exists(filename):
            logger.error("El proceso de descarga finalizó pero el archivo no existe en disco.")
            raise HTTPException(status_code=500, detail="El archivo descargado no se pudo encontrar en el servidor.")

        download_name = os.path.basename(filename)

        # Programar la limpieza del archivo en segundo plano tras ser entregado
        background_tasks.add_task(cleanup_file, filename)

        logger.info(f"Enviando archivo al cliente: {download_name}")
        return FileResponse(
            path=filename,
            filename=download_name,
            media_type="application/octet-stream"
        )

    except yt_dlp.utils.DownloadError as de:
        logger.error(f"Error de yt-dlp: {str(de)}")
        raise HTTPException(
            status_code=400,
            detail=f"No se pudo descargar el video. YouTube bloqueó el formato o la URL es inválida. Detalle: {str(de)}"
        )
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Ocurrió un error en el servidor: {str(e)}"
        )
