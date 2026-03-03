#!/bin/bash

echo "🔧 修复脚本 - 替换为兼容版本"
echo "================================"

# 检查是否在项目目录
if [ ! -d "backend" ]; then
    echo "❌ 请在 video_knowledge_base 目录下运行此脚本"
    exit 1
fi

# 备份原文件
echo "📦 备份原文件..."
if [ -f "backend/search_engine.py" ]; then
    cp backend/search_engine.py backend/search_engine.py.bak
    echo "✅ 已备份: backend/search_engine.py.bak"
fi

# 创建新的 search_engine.py
echo "📝 创建新的搜索引擎文件..."
cat > backend/search_engine.py << 'EOF'
"""
搜索引擎模块
使用 sentence-transformers 实现图文语义搜索
"""

from sentence_transformers import SentenceTransformer
from PIL import Image
import numpy as np
from pathlib import Path
from typing import List, Dict
import chromadb
from chromadb.config import Settings


class SearchEngine:
    """语义搜索引擎"""
    
    def __init__(self, db, model_name: str = "clip-ViT-B-32"):
        """
        Args:
            db: 数据库实例
            model_name: 模型名称
        """
        self.db = db
        
        print("🔧 初始化搜索引擎...")
        print(f"   模型: {model_name}")
        
        # 加载多模态模型
        self.model = SentenceTransformer(model_name)
        
        # 初始化向量数据库
        self.chroma_client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory="./data/chroma_db"
        ))
        
        # 创建或获取 collection
        self.collection = self.chroma_client.get_or_create_collection(
            name="video_clips",
            metadata={"description": "Video clip embeddings"}
        )
        
        print("✅ 搜索引擎初始化完成")
    
    def encode_image(self, image_path: str) -> np.ndarray:
        """将图像编码为向量"""
        image = Image.open(image_path).convert('RGB')
        embedding = self.model.encode(image)
        return embedding
    
    def encode_text(self, text: str) -> np.ndarray:
        """将文本编码为向量"""
        embedding = self.model.encode(text)
        return embedding
    
    def index_clip(self, clip_id: str, thumbnail_path: str):
        """索引单个片段"""
        if not Path(thumbnail_path).exists():
            print(f"⚠️  缩略图不存在: {thumbnail_path}")
            return
        
        embedding = self.encode_image(thumbnail_path)
        self.collection.add(
            embeddings=[embedding.tolist()],
            ids=[clip_id]
        )
    
    def index_video_clips(self, video_id: str):
        """索引视频的所有片段"""
        print(f"\n🔍 开始索引视频片段...")
        clips = self.db.get_clips_by_video(video_id)
        
        for idx, clip in enumerate(clips):
            self.index_clip(clip['clip_id'], clip['thumbnail_path'])
            
            if (idx + 1) % 10 == 0:
                print(f"   进度: {idx + 1}/{len(clips)}")
        
        print(f"✅ 索引完成! 共 {len(clips)} 个片段")
    
    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """搜索相关片段"""
        print(f"\n🔎 搜索: '{query}'")
        
        query_embedding = self.encode_text(query)
        
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k
        )
        
        search_results = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for clip_id, distance in zip(results['ids'][0], results['distances'][0]):
                clip = self.db.get_clip(clip_id)
                if clip:
                    similarity = 1 - (distance / 2)
                    clip['similarity'] = round(similarity, 4)
                    search_results.append(clip)
        
        print(f"✅ 找到 {len(search_results)} 个结果")
        return search_results
    
    def reindex_all(self):
        """重新索引所有片段"""
        print("\n🔄 重新索引所有片段...")
        
        self.chroma_client.delete_collection("video_clips")
        self.collection = self.chroma_client.get_or_create_collection(
            name="video_clips",
            metadata={"description": "Video clip embeddings"}
        )
        
        videos = self.db.get_all_videos()
        for video in videos:
            self.index_video_clips(video['video_id'])
        
        print("✅ 重新索引完成")
EOF

echo "✅ 文件已更新"

# 安装 sentence-transformers
echo ""
echo "📦 安装 sentence-transformers..."
pip3 install sentence-transformers

echo ""
echo "================================"
echo "✅ 修复完成！"
echo ""
echo "现在可以启动项目了："
echo "  cd backend"
echo "  python3 app.py"
echo "================================"
