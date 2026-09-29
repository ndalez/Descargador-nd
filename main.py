@app.post("/download")
async def download_media(request: DownloadRequest, background_tasks: BackgroundTasks):
    url = request.url
    is_audio = request.format.lower() == "mp3"

    ffmpeg_exe_path = imageio_ffmpeg.get_ffmpeg_exe()

    # Formatos más flexibles y compatibles
    if is_audio:
        format_spec = 'bestaudio/best'
    else:
        # Pide el mejor video + mejor audio y permite que FFmpeg los unifique a MP4
        format_spec = 'bestvideo+bestaudio/best'

    ydl_opts = {
        'format': format_spec,
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'noplaylist': True,
        'quiet': False,
        'no_warnings': False,
        'ffmpeg_location': ffmpeg_exe_path,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept-Language': 'es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7',
        },
        # Se elimina 'skip': ['hls', 'dash'] para permitir obtener todos los formatos
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web']
            }
        }
    }

    # Cargar cookies solo si existe el archivo
    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'

    if is_audio:
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        # Asegura que el contenedor final del video sea MP4
        ydl_opts['merge_output_format'] = 'mp4'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info("Extrayendo e iniciando descarga...")
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            # Ajuste de extensión si cambió tras el postprocesamiento
            if is_audio:
                base_name, _ = os.path.splitext(filename)
                potential_mp3 = f"{base_name}.mp3"
                if os.path.exists(potential_mp3):
                    filename = potential_mp3
            else:
                base_name, _ = os.path.splitext(filename)
                potential_mp4 = f"{base_name}.mp4"
                if os.path.exists(potential_mp4):
                    filename = potential_mp4

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
            detail=f"Error en la descarga: {str(de)}"
        )
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Ocurrió un error en el servidor: {str(e)}"
        )
