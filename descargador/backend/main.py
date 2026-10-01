from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import yt_dlp
import os
import uuid
import re
from urllib.parse import quote

app = FastAPI()

# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# CARPETA TEMPORAL
# =========================================================

DOWNLOAD_DIR = "temp_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# =========================================================
# LIMPIAR NOMBRE DEL ARCHIVO
# =========================================================

def limpiar_nombre(nombre: str) -> str:
    """
    Elimina caracteres que pueden causar problemas
    en los nombres de archivos.
    """
    nombre = re.sub(r'[\\/*?:"<>|]', "", nombre)
    nombre = nombre.strip()

    if not nombre:
        nombre = "descarga"

    return nombre


# =========================================================
# ELIMINAR ARCHIVO DESPUÉS DE DESCARGAR
# =========================================================

def borrar_archivo(file_path: str):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Archivo eliminado: {file_path}")
    except Exception as e:
        print(f"Error al eliminar archivo temporal: {e}")


# =========================================================
# DESCARGAR VIDEO / AUDIO
# =========================================================

@app.post("/api/download")
async def download_media(data: dict):

    url = data.get("url")
    format_type = data.get("format")
    quality = data.get("quality", "720")

    # -----------------------------------------------------
    # VALIDAR URL
    # -----------------------------------------------------

    if not url:
        raise HTTPException(
            status_code=400,
            detail="URL de YouTube no proporcionada"
        )

    # -----------------------------------------------------
    # VALIDAR FORMATO
    # -----------------------------------------------------

    if format_type not in ["mp3", "mp4"]:
        raise HTTPException(
            status_code=400,
            detail="Formato no válido. Usa mp3 o mp4."
        )

    # -----------------------------------------------------
    # VALIDAR CALIDAD
    # -----------------------------------------------------

    allowed_quality = ["1080", "720", "480", "360"]

    if quality not in allowed_quality:
        quality = "720"

    # -----------------------------------------------------
    # ID ÚNICO
    # -----------------------------------------------------

    file_id = str(uuid.uuid4())[:8]

    output_template = os.path.join(
        DOWNLOAD_DIR,
        f"{file_id}_%(title)s.%(ext)s"
    )

    # -----------------------------------------------------
    # CONFIGURACIÓN BASE DE YT-DLP
    # -----------------------------------------------------

    base_opts = {
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
    }

    # =====================================================
    # CONFIGURACIÓN MP3
    # =====================================================

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

    # =====================================================
    # CONFIGURACIÓN MP4
    # =====================================================

    else:

        ydl_opts = {
            **base_opts,

            "format": (
                f"bestvideo[height<={quality}][ext=mp4]"
                f"+bestaudio[ext=m4a]/"
                f"best[ext=mp4]/best"
            ),

            "merge_output_format": "mp4",
        }

    # =====================================================
    # DESCARGAR
    # =====================================================

    try:

        print(f"Descargando: {url}")
        print(f"Formato: {format_type}")
        print(f"Calidad: {quality}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(
                url,
                download=True
            )

        # -------------------------------------------------
        # OBTENER TÍTULO
        # -------------------------------------------------

        titulo_original = info.get(
            "title",
            "descarga"
        )

        titulo_limpio = limpiar_nombre(
            titulo_original
        )

        # -------------------------------------------------
        # BUSCAR ARCHIVO GENERADO
        # -------------------------------------------------

        extension = format_type

        archivo_generado = None

        for file in os.listdir(DOWNLOAD_DIR):

            if (
                file.startswith(file_id)
                and file.lower().endswith(
                    f".{extension}"
                )
            ):
                archivo_generado = file
                break

        # -------------------------------------------------
        # VERIFICAR ARCHIVO
        # -------------------------------------------------

        if not archivo_generado:

            raise HTTPException(
                status_code=500,
                detail=(
                    "La descarga terminó, "
                    "pero no se encontró el archivo generado."
                )
            )

        # -------------------------------------------------
        # URL PARA DESCARGAR EL ARCHIVO
        # -------------------------------------------------

        download_url = (
            f"/api/get-file/"
            f"{quote(archivo_generado)}"
            f"?title={quote(titulo_limpio)}"
            f"&ext={extension}"
        )

        print(
            f"Archivo generado: {archivo_generado}"
        )

        # -------------------------------------------------
        # RESPUESTA AL HTML
        # -------------------------------------------------

        return {
            "status": "success",
            "title": titulo_limpio,
            "file_name_server": archivo_generado,
            "download_url": download_url
        }

    # =====================================================
    # ERRORES
    # =====================================================

    except HTTPException:
        raise

    except Exception as e:

        print(
            f"ERROR durante la descarga: {str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================================================
# ENTREGAR ARCHIVO AL USUARIO
# =========================================================

@app.get("/api/get-file/{file_name_server}")
async def get_file(
    file_name_server: str,
    title: str,
    ext: str,
    background_tasks: BackgroundTasks
):

    file_path = os.path.join(
        DOWNLOAD_DIR,
        file_name_server
    )

    # -----------------------------------------------------
    # VERIFICAR QUE EXISTE
    # -----------------------------------------------------

    if not os.path.exists(file_path):

        raise HTTPException(
            status_code=404,
            detail="Archivo no encontrado o ya eliminado."
        )

    # -----------------------------------------------------
    # NOMBRE FINAL
    # -----------------------------------------------------

    nombre_descarga = (
        f"{limpiar_nombre(title)}.{ext}"
    )

    # -----------------------------------------------------
    # ELIMINAR DESPUÉS DE ENVIAR
    # -----------------------------------------------------

    background_tasks.add_task(
        borrar_archivo,
        file_path
    )

    # -----------------------------------------------------
    # ENVIAR ARCHIVO
    # -----------------------------------------------------

    return FileResponse(
        path=file_path,
        filename=nombre_descarga,
        media_type="application/octet-stream"
    )


# =========================================================
# RUTA DE PRUEBA
# =========================================================

@app.get("/")
async def root():

    return {
        "status": "online",
        "message": "Servidor de descarga funcionando correctamente"
    }
