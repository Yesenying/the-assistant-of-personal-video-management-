"""
搜索引擎模块
使用 Chinese-CLIP 实现图文语义搜索
- 支持：对每个 clip 读取多帧缩略图 clip_XXXX_f*.jpg，做 embedding 聚合（mean / GeM）
"""

from PIL import Image
import numpy as np
from pathlib import Path
from typing import List, Dict
import chromadb
import torch
from transformers import AutoProcessor, ChineseCLIPModel

import math

def gem_pooling(embs: np.ndarray, p: float = 3.0, eps: float = 1e-6) -> np.ndarray:
    """
    GeM pooling: (mean(x^p))^(1/p)
    embs: (n, d) 已归一化也没问题
    """
    x = np.clip(embs, eps, None)
    x = np.power(x, p).mean(axis=0)
    x = np.power(x, 1.0 / p)
    # 再归一化
    return x / (np.linalg.norm(x) + 1e-12)

def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


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

        # 多模态模型（图文同空间）
        # self.model = SentenceTransformer(model_name)
        # 模型选择：
        # - "OFA-Sys/chinese-clip-vit-base-patch16" (基础版，快速)
        # - "OFA-Sys/chinese-clip-vit-large-patch14" (推荐，效果更好)
        self.model_name = "OFA-Sys/chinese-clip-vit-large-patch14"
        print(f"[INFO] Chinese-CLIP: {self.model_name}")

        self.device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
        print(f"[INFO] device: {self.device}")

        self.processor = AutoProcessor.from_pretrained(self.model_name)
        self.model = ChineseCLIPModel.from_pretrained(self.model_name).to(self.device)
        self.model.eval()

        # Chroma 持久化（使用绝对路径，避免从不同目录运行时路径混乱）
        from pathlib import Path as _Path
        _project_root = _Path(__file__).resolve().parent.parent
        _chroma_path = str(_project_root / "data" / "chroma_db")
        self.chroma_client = chromadb.PersistentClient(path=_chroma_path)

        # collection
        self.collection = self.chroma_client.get_or_create_collection(
        name="video_clips",
        metadata={"hnsw:space": "cosine", "description": "Video clip embeddings"}
    )


        print("✅ 搜索引擎初始化完成")

    # ---------- encoding helpers ----------

    def encode_text(self, text: str) -> np.ndarray:
        """文本 -> embedding（归一化）"""
        with torch.no_grad():
            inputs = self.processor(
                text=[text],
                return_tensors="pt",
                padding=True,
                truncation=True
            )
            input_ids = inputs["input_ids"].to(self.device)
            attention_mask = inputs.get("attention_mask")
            if attention_mask is not None:
                attention_mask = attention_mask.to(self.device)

            text_outputs = self.model.text_model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                return_dict=True
            )

            # pooled 输出（不同版本字段可能不同）
            pooled = getattr(text_outputs, "pooler_output", None)
            if pooled is None:
                pooled = text_outputs.last_hidden_state[:, 0, :]  # 兜底：取 CLS

            text_feat = self.model.text_projection(pooled)  # (1, d)
            text_feat = text_feat / (text_feat.norm(dim=-1, keepdim=True) + 1e-12)

            return text_feat[0].detach().cpu().numpy().astype(np.float32)


    def encode_images(self, image_paths: list[str], batch_size: int = 8) -> np.ndarray:
        """多图 -> embeddings（归一化），返回 shape (n, d)"""
        imgs = [Image.open(p).convert("RGB") for p in image_paths]

        feats = []
        with torch.no_grad():
            for i in range(0, len(imgs), batch_size):
                batch = imgs[i:i + batch_size]
                inputs = self.processor(images=batch, return_tensors="pt")
                pixel_values = inputs["pixel_values"].to(self.device)

                vision_outputs = self.model.vision_model(
                    pixel_values=pixel_values,
                    return_dict=True
                )

                pooled = getattr(vision_outputs, "pooler_output", None)
                if pooled is None:
                    pooled = vision_outputs.last_hidden_state[:, 0, :]  # 兜底：取 CLS

                img_feat = self.model.visual_projection(pooled)  # (b, d)
                img_feat = img_feat / (img_feat.norm(dim=-1, keepdim=True) + 1e-12)

                feats.append(img_feat.detach().cpu())

        return torch.cat(feats, dim=0).numpy().astype(np.float32)



    def _get_multi_frame_paths(self, thumbnail_path: str, max_frames: int = 5) -> List[str]:
        """
        根据主缩略图路径 clip_0003.jpg，查找同目录下 clip_0003_f*.jpg
        若不存在多帧，则回退为单帧 thumbnail_path
        """
        p = Path(thumbnail_path)
        if not p.exists():
            return []

        # clip_0003.jpg -> clip_0003_f*.jpg
        stem = p.stem  # clip_0003
        candidates = sorted(p.parent.glob(f"{stem}_f*.jpg"))

        # 只取前 max_frames 张（你现在默认就是 5 张）
        candidates = candidates[:max_frames]

        if candidates:
            return [str(x) for x in candidates]

        return [str(p)]

    # ---------- indexing ----------

    # def index_clip(self, clip_id: str, thumbnail_path: str):
    #     """索引单个片段：多帧聚合 -> 一个 clip_id 向量（mean + 再归一化）"""
    #     clip_id = str(clip_id)

    #     paths = self._get_multi_frame_paths(thumbnail_path, max_frames=5)
    #     if not paths:
    #         print(f"⚠️  缩略图不存在: {thumbnail_path}")
    #         return

    #     # 批量编码（每帧已归一化：normalize_embeddings=True）
    #     embs = self.encode_images(paths)  # (n, d)  已归一化
    #     if embs is None or len(embs) == 0:
    #         print(f"⚠️  无法编码图片: {paths}")
    #         return

    #     # mean 聚合
    #     clip_emb = embs.mean(axis=0)

    #     # ✅ 关键：聚合后再归一化（否则向量长度会漂，检索容易“全都差不多”）
    #     denom = np.linalg.norm(clip_emb) + 1e-12
    #     clip_emb = clip_emb / denom

    #     self.collection.upsert(
    #         embeddings=[clip_emb.astype(np.float32).tolist()],
    #         ids=[clip_id],
    #         metadatas=[{
    #             "thumbnail_path": thumbnail_path,
    #             "frames_used": len(paths)
    #         }]
    #     )
    def index_clip(self, clip_id: str, thumbnail_path: str, extra_meta: Dict[str, object] | None = None):
        """
        索引单个片段：多帧 -> clip/video 级 embedding（GeM pooling）-> 写入 Chroma
        """
        clip_id = str(clip_id)
        extra_meta = extra_meta or {}

        paths = self._get_multi_frame_paths(thumbnail_path, max_frames=5)
        if not paths:
            print(f"⚠️  缩略图不存在: {thumbnail_path}")
            return

        embs = self.encode_images(paths)  # (n, d) 已归一化
        if embs is None or len(embs) == 0:
            print(f"⚠️  无法编码图片: {paths}")
            return

        # ✅ 更强的聚合：GeM（也可选 max pooling）
        clip_emb = gem_pooling(embs, p=3.0)

        # ChromaDB metadata 只支持 str/int/float/bool/None，列表需要转 JSON
        import json as _json
        meta = {
            "thumbnail_path": thumbnail_path,
            "frames_used": len(paths),
            "frame_paths": _json.dumps(paths),  # 列表转字符串
            **extra_meta
        }

        self.collection.upsert(
            embeddings=[clip_emb.astype(np.float32).tolist()],
            ids=[clip_id],
            metadatas=[meta]
        )


    def index_video_clips(self, video_id: str):
        """索引视频的所有片段"""
        print(f"\n🔍 开始索引视频片段: {video_id}")
        clips = self.db.get_clips_by_video(video_id)

        for idx, clip in enumerate(clips):
            self.index_clip(
                clip["clip_id"],
                clip["thumbnail_path"],
                extra_meta={"video_id": clip.get("video_id")}
            )


        print(f"✅ 索引完成! 共 {len(clips)} 个片段")

    # ---------- search ----------

    def search(self, query: str, top_k: int = 10, fetch_k: int = 300, use_mmr: bool = True, mmr_lambda: float = 0.78) -> List[Dict[str, object]]:
        """
        顶配 Step1：
        - 先 fetch_k 大召回
        - 再用 MMR 做多样性重排（减少重复/扎堆）
        - 返回解释性字段：frames_used / frame_paths
        """
        print(f"\n🔎 搜索: '{query}'")

        q = self.encode_text(query)

        results = self.collection.query(
            query_embeddings=[q.tolist()],
            n_results=fetch_k,
            include=["metadatas", "distances", "embeddings"]
        )

        ids = results.get("ids", [[]])[0]
        dists = results.get("distances", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        embs = results.get("embeddings", [[]])[0]

        if not ids:
            return []

        # 组装候选
        candidates = []
        for cid, dist, meta, emb in zip(ids, dists, metas, embs):
            clip = self.db.get_clip(cid)
            if not clip:
                continue
            sim = 1.0 - float(dist)  # cosine distance -> similarity
            clip["_sim"] = sim
            clip["_emb"] = np.array(emb, dtype=np.float32)
            clip["_meta"] = meta or {}
            candidates.append(clip)

        if not candidates:
            return []

        # ---------- 去重（轻量版）：同一视频 + 时间太近的结果折叠 ----------
        # 你不计成本，可以后面再上更强的 near-duplicate（pHash/聚类）
        def too_close(a, b, sec=2.0):
            if a.get("video_id") != b.get("video_id"):
                return False
            try:
                return abs(float(a.get("start_time", 0)) - float(b.get("start_time", 0))) < sec
            except:
                return False

        # ---------- MMR 多样性重排 ----------
        picked = []
        if use_mmr:
            remaining = candidates[:]
            while remaining and len(picked) < top_k:
                best = None
                best_score = -1e9

                for c in remaining:
                    rel = c["_sim"]
                    div = 0.0
                    if picked:
                        div = max(cosine(c["_emb"], p["_emb"]) for p in picked)
                    mmr = mmr_lambda * rel - (1 - mmr_lambda) * div
                    if mmr > best_score:
                        best_score = mmr
                        best = c

                # 去掉时间近似重复
                if best is not None:
                    if any(too_close(best, p, sec=2.0) for p in picked):
                        remaining.remove(best)
                        continue
                    picked.append(best)
                    remaining.remove(best)
        else:
            # 不用 MMR 就直接取 sim 最高的，并做轻去重
            candidates.sort(key=lambda x: x["_sim"], reverse=True)
            for c in candidates:
                if any(too_close(c, p, sec=2.0) for p in picked):
                    continue
                picked.append(c)
                if len(picked) >= top_k:
                    break

        # ---------- 返回结果（带解释性字段） ----------
        out = []
        for c in picked:
            meta = c.get("_meta") or {}
            c["similarity"] = round(float(c["_sim"]), 4)
            c["frames_used"] = meta.get("frames_used")
            c["frame_paths"] = meta.get("frame_paths")
            # 清理内部字段
            c.pop("_sim", None)
            c.pop("_emb", None)
            c.pop("_meta", None)
            out.append(c)

        print(f"✅ 返回 {len(out)} 个结果")
        return out


    # def search(self, query: str, top_k: int = 10) -> List[Dict]:
    #     """搜索相关片段"""
    #     print(f"\n🔎 搜索: '{query}'")

    #     query_embedding = self.encode_text(query)

    #     results = self.collection.query(
    #         query_embeddings=[query_embedding.tolist()],
    #         n_results=top_k
    #     )

    #     search_results = []
    #     if results.get("ids") and len(results["ids"][0]) > 0:
    #         for clip_id, distance in zip(results["ids"][0], results["distances"][0]):
    #             clip = self.db.get_clip(clip_id)
    #             if clip:
    #                 # 你原来的逻辑保留：distance 基于 L2，归一化后距离范围更可控
    #                 similarity = 1 - distance 
    #                 clip["similarity"] = round(float(similarity), 4)
    #                 search_results.append(clip)

    #     print(f"✅ 找到 {len(search_results)} 个结果")
    #     return search_results

    def reindex_all(self):
        """重新索引所有片段"""
        print("\n🔄 重新索引所有片段...")

        self.chroma_client.delete_collection("video_clips")
        self.collection = self.chroma_client.get_or_create_collection(
            name="video_clips",
            # metadata={"description": "Video clip embeddings"}.  
            metadata = {"hnsw:space": "cosine", "description": "Video clip embeddings"}
        )

        videos = self.db.get_all_videos()
        for video in videos:
            self.index_video_clips(video["video_id"])

        print("✅ 重新索引完成")
