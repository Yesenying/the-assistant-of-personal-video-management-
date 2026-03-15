FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libgomp1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --timeout 300 -r /app/requirements.txt \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com

COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY reindex.py /app/reindex.py

RUN mkdir -p /app/data /app/clips /app/data/downloads

ENV PYTHONUNBUFFERED=1
ENV APP_BASE_DIR=/app
ENV APP_DATA_DIR=/app/data
ENV APP_CLIPS_DIR=/app/clips
ENV PORT=5000

EXPOSE 5000

CMD ["python", "backend/app.py"]
