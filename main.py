from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yt_dlp
import os

app = FastAPI()

# Permitir peticiones desde cualquier origen (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Crear la carpeta de descargas temporales si no existe
DOWNLOAD_DIR = "temp_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

class DownloadRequest(BaseModel):
    url: str
    format: str  # "mp3" o "mp4"

def cleanup_file(filepath: str):
    """Elimina el archivo del servidor después de enviarlo al usuario"""
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception as e:
            print(f"Error limpiando archivo {filepath}: {e}")

@app.post("/download")
async def download_media(request: DownloadRequest, background_tasks: BackgroundTasks):
    url = request.url
    is_audio = request.format.lower() == "mp3"

    # Selección de formato compatible sin requerir FFmpeg obligatorio
    if is_audio:
        format_spec = 'ba/b'  # Descarga el mejor audio disponible (bestaudio)
    else:
        format_spec = 'b/best' # Descarga el mejor formato unificado de video+audio

    ydl_opts = {
        'format': format_spec,
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'cookiefile': 'cookies.txt',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web']
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        if not os.path.exists(filename):
            raise HTTPException(status_code=500, detail="El archivo no se pudo generar.")

        download_name = os.path.basename(filename)

        # Borrar el archivo temporal tras enviar la respuesta
        background_tasks.add_task(cleanup_file, filename)

        return FileResponse(
            path=filename,
            filename=download_name,
            media_type="application/octet-stream"
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
