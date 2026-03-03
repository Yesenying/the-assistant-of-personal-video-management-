#!/bin/bash

echo "============================================================"
echo "🎬 个人视频素材知识库 - 启动脚本"
echo "============================================================"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python3，请先安装"
    exit 1
fi

echo "✅ Python: $(python3 --version)"

# 检查 FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ 未找到 FFmpeg"
    echo "请运行: brew install ffmpeg (Mac) 或 apt install ffmpeg (Linux)"
    exit 1
fi

echo "✅ FFmpeg: $(ffmpeg -version | head -n 1)"

# 检查依赖
echo ""
echo "📦 检查依赖..."
pip3 show flask &> /dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  未安装依赖，正在安装..."
    pip3 install -r requirements.txt
    pip3 install git+https://github.com/openai/CLIP.git
fi

echo "✅ 依赖检查完成"

# 启动后端
echo ""
echo "🚀 启动后端服务..."
echo "============================================================"
cd backend
python3 app.py
