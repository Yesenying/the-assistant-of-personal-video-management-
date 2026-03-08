# 视频知识库后端 - CloudBase CloudRun 部署
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 预下载模型（避免启动时下载）
RUN python -c "from transformers import AutoProcessor, ChineseCLIPModel; \
    AutoProcessor.from_pretrained('OFA-Sys/chinese-clip-vit-large-patch14'); \
    ChineseCLIPModel.from_pretrained('OFA-Sys/chinese-clip-vit-large-patch14')"

# 复制代码
COPY backend/ ./backend/
COPY reindex.py .
COPY frontend/ ./frontend/

# 创建数据目录
RUN mkdir -p /app/data /app/clips

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=backend.app

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["python", "-m", "backend.app"]
