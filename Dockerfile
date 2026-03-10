# 视频知识库后端 - CloudBase CloudRun 部署
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（使用国内源，添加错误处理）
RUN apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
        libgomp1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖（使用清华源，添加超时重试）
RUN pip install --no-cache-dir --timeout 300 -r requirements.txt \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com

# 预下载模型（避免启动时下载，如果失败不影响构建）
RUN python -c "from transformers import AutoProcessor, ChineseCLIPModel; \
    AutoProcessor.from_pretrained('OFA-Sys/chinese-clip-vit-large-patch14'); \
    ChineseCLIPModel.from_pretrained('OFA-Sys/chinese-clip-vit-large-patch14')" || \
    echo "模型预下载失败，将在启动时下载"

# 复制代码
COPY backend/ ./backend/
COPY reindex.py .
COPY frontend/ ./frontend/

# 创建数据目录
RUN mkdir -p /app/data /app/clips /app/data/downloads

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=backend.app
ENV APP_BASE_DIR=/app
ENV APP_DATA_DIR=/app/data
ENV APP_CLIPS_DIR=/app/clips

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["python", "backend/app.py"]
