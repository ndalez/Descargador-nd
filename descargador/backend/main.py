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
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOAD_DIR = "temp_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def limpiar_nombre(nombre: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", nombre)


def borrar_archivo(file_path: str):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"Error al eliminar archivo temporal: {e}")


@app.post("/api/download")
async def download_media(data: dict):

    url = data.get("url")
    format_type = data.get("format")
    quality = data.get("quality", "720")

    if not url:
        raise HTTPException(
            status_code=400,
            detail="URL no proporcionada"
        )

    if format_type not in ["mp3", "mp4"]:
        raise HTTPException(
            status_code=400,
            detail="Formato no válido. Usa mp3 o mp4."
        )

    file_id = str(uuid.uuid4())[:8]

    output_template = (
        f"{DOWNLOAD_DIR}/{file_id}_%(title)s.%(ext)s"
    )

    # Configuración base de yt-dlp
    base_opts = {
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "noplaylist": True,

        # Configuración YouTube + PO Token
        "extractor_args": {
            "youtube": {
                "player_client": ["mweb"]
            },
            "youtubepot-bgutilhttp": {
                "base_url": "http://127.0.0.1:4416"
            }
        },
    }

    # =========================
    # MP3
    # =========================
    if format_type == "mp3":

        ydl_opts = {
            **base_opts,

            "format": "bestaudio/best",

            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }

    # =========================
    # MP4
    # =========================
    else:

        ydl_opts = {
            **base_opts,

            "format": (
                f"bestvideo[height<={quality}][ext=mp4]"
                "+bestaudio[ext=m4a]"
                "/best[ext=mp4]"
                "/best"
            ),

            "merge_output_format": "mp4",
        }

    try:

        print(f"Descargando: {url}")
        print(f"Formato: {format_type}")
        print(f"Calidad: {quality}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(
                url,
                download=True
            )

            titulo_original = info.get(
                "title",
                "cancion"
            )

            titulo_limpio = limpiar_nombre(
                titulo_original
            )

            # Extensión final
            ext = (
                "mp3"
                if format_type == "mp3"
                else "mp4"
            )

            archivo_generado = None

            # Buscar archivo generado
            for file in os.listdir(DOWNLOAD_DIR):

                if (
                    file.startswith(file_id)
                    and file.endswith(f".{ext}")
                ):
                    archivo_generado = file
                    break

            if not archivo_generado:

                raise HTTPException(
                    status_code=500,
                    detail=(
                        "No se pudo localizar "
                        "el archivo descargado."
                    )
                )

            return {
                "status": "success",

                "title": titulo_limpio,

                "file_name_server": archivo_generado,

                "download_url": (
                    f"/api/get-file/"
                    f"{archivo_generado}"
                    f"?title={quote(titulo_limpio)}"
                    f"&ext={ext}"
                ),
            }

    except HTTPException:
        raise

    except Exception as e:

        print(
            f"ERROR yt-dlp: {str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail=f"ERROR: {str(e)}"
        )


@app.get("/api/get-file/{file_name_server}")
async def get_file(
    file_name_server: str,
    title: str,
    ext: str,
    background_tasks: BackgroundTasks,
):

    file_path = os.path.join(
        DOWNLOAD_DIR,
        file_name_server
    )

    if os.path.exists(file_path):

        nombre_descarga = (
            f"{title}.{ext}"
        )

        # Eliminar después de enviar
        background_tasks.add_task(
            borrar_archivo,
            file_path
        )

        return FileResponse(
            file_path,

            filename=nombre_descarga,

            media_type="application/octet-stream",

            headers={
                "Content-Disposition": (
                    f'attachment; '
                    f'filename="{quote(nombre_descarga)}"'
                )
            },
        )

    raise HTTPException(
        status_code=404,
        detail="Archivo no encontrado"
    )


@app.get("/")
async def root():

    return {
        "status": "online",
        "message": "Servidor funcionando correctamente"
    }
