FROM python:3.11-slim

# Instalar FFmpeg
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

# Copiar requirements
COPY requirements.txt .

# Instalar Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY main.py .

# Crear carpeta temporal
RUN mkdir -p temp_downloads

# Puerto de Render
EXPOSE 10000

# Ejecutar FastAPI
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]
