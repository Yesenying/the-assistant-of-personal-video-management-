#!/usr/bin/env python3
"""
rebuild_collection.py

用途：
- 删除并重建 Chroma collection（默认: video_clips）
- 从 SQLite 读取所有 videos -> clips
- 对每个 clip 的缩略图（多帧）重新计算 embedding 并 upsert 回 Chroma

等价于：只“重建向量索引/collection”，不动切片结果（clips 表不清空）。
"""


import argparse
from pathlib import Path

from backend.database import Database
from backend.search_engine import SearchEngine


def main():
    parser = argparse.ArgumentParser(description="Rebuild Chroma collection for video clip search.")
    parser.add_argument("--db", default="data/video_library.db", help="SQLite DB path (default: data/video_library.db)")
    parser.add_argument("--chroma", default="data/chroma_db", help="Chroma persist dir (default: data/chroma_db)")
    parser.add_argument("--collection", default="video_clips", help="Chroma collection name (default: video_clips)")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    db_path = Path(args.db)
    chroma_path = Path(args.chroma)

    if not db_path.exists():
        raise FileNotFoundError(f"DB not found: {db_path.resolve()}")

    chroma_path.mkdir(parents=True, exist_ok=True)

    print("=== REBUILD PLAN ===")
    print(f"- SQLite DB:     {db_path.resolve()}")
    print(f"- Chroma dir:    {chroma_path.resolve()}")
    print(f"- Collection:    {args.collection}")
    print("Action: delete collection -> recreate (cosine) -> re-embed all clips")
    print("====================")

    if not args.yes:
        confirm = input("Type YES to proceed: ").strip()
        if confirm != "YES":
            print("Cancelled.")
            return

    db = Database(str(db_path))
    se = SearchEngine(db)

    # ✅ 关键：把 SearchEngine 的 client/path、collection name 对齐到脚本参数
    # 如果你不想改 SearchEngine 的构造函数，就在这里强制覆盖
    se.chroma_client = __import__("chromadb").PersistentClient(path=str(chroma_path))
    try:
        se.chroma_client.delete_collection(args.collection)
        print(f"🗑️ Deleted collection: {args.collection}")
    except Exception as e:
        print(f"ℹ️ delete_collection skipped (maybe not exist): {e}")

    se.collection = se.chroma_client.get_or_create_collection(
        name=args.collection,
        metadata={"hnsw:space": "cosine", "description": "Video clip embeddings"},
    )
    print(f"✅ Created collection: {args.collection} (cosine)")

    videos = db.get_all_videos()
    print(f"📼 videos: {len(videos)}")

    total = 0
    for v in videos:
        video_id = v["video_id"]
        clips = db.get_clips_by_video(video_id)
        print(f"\n🔍 video {video_id} clips: {len(clips)}")

        for i, c in enumerate(clips, start=1):
            se.index_clip(c["clip_id"], c["thumbnail_path"])
            total += 1

            if i % 50 == 0:
                print(f"  ... {i}/{len(clips)}")

    print("\n====================")
    print(f"✅ Done. Total indexed clips: {total}")
    print("Tip: 重启后端服务再测 /api/search")


if __name__ == "__main__":
    main()
