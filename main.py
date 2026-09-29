from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import yt_dlp
import os
import uuid
import re
from urllib.parse import quote

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOAD_DIR = "temp_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def limpiar_nombre(nombre: str) -> str:
    # Quitar caracteres no permitidos en nombres de archivos
    return re.sub(r'[\\/*?:"<>|]', "", nombre)

# Función para eliminar archivos temporales del servidor tras ser entregados
def borrar_archivo(file_path: str):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"Error al eliminar archivo temporal: {e}")

@app.post("/api/download")
async def download_media(data: dict):
    url = data.get("url")
    format_type = data.get("format")  # 'mp3' o 'mp4'
    quality = data.get("quality", "720")

    if not url:
        raise HTTPException(status_code=400, detail="URL no proporcionada")

    # Usar ID único corto para evitar colisiones
    file_id = str(uuid.uuid4())[:8]
    output_template = f"{DOWNLOAD_DIR}/{file_id}_%(title)s.%(ext)s"

    base_opts = {
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'noplaylist': True,
    }

    if format_type == "mp3":
        ydl_opts = {
            **base_opts,
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
    else:
        ydl_opts = {
            **base_opts,
            'format': f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            titulo_original = info.get("title", "cancion")
            titulo_limpio = limpiar_nombre(titulo_original)

            # Buscar el archivo generado en la carpeta temporal
            ext = "mp3" if format_type == "mp3" else "mp4"
            archivo_generado = None
            
            for file in os.listdir(DOWNLOAD_DIR):
                if file.startswith(file_id) and file.endswith(f".{ext}"):
                    archivo_generado = file
                    break

            if not archivo_generado:
                raise HTTPException(status_code=500, detail="No se pudo localizar el archivo descargado.")

            return {
                "status": "success",
                "title": titulo_limpio,
                "file_name_server": archivo_generado,
                "download_url": f"/api/get-file/{archivo_generado}?title={quote(titulo_limpio)}&ext={ext}"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/get-file/{file_name_server}")
async def get_file(file_name_server: str, title: str, ext: str, background_tasks: BackgroundTasks):
    file_path = os.path.join(DOWNLOAD_DIR, file_name_server)
    
    if os.path.exists(file_path):
        nombre_descarga = f"{title}.{ext}"
        
        # Se programa la eliminación automática del archivo en el servidor después de enviarlo
        background_tasks.add_task(borrar_archivo, file_path)
        
        return FileResponse(
            file_path, 
            filename=nombre_descarga,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{quote(nombre_descarga)}"'}
        )
    
    raise HTTPException(status_code=404, detail="Archivo no encontrado")