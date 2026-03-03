#!/usr/bin/env python3
"""
reset_clips_and_chroma.py

清空：
1) SQLite 里的 clips 表（可选：同时清空 videos 表）
2) Chroma 向量库目录 data/chroma_db
3) 可选：删除缩略图目录 clips/

用法（在项目根目录）：
  ./.venv/bin/python reset_clips_and_chroma.py
  ./.venv/bin/python reset_clips_and_chroma.py --delete-thumbnails
  ./.venv/bin/python reset_clips_and_chroma.py --reset-videos --delete-thumbnails
"""

import argparse
import os
import shutil
import sqlite3
from pathlib import Path


DEFAULT_DB = "data/video_library.db"
DEFAULT_CHROMA_DIR = "data/chroma_db"
DEFAULT_THUMBS_DIR = "clips"


def reset_sqlite(db_path: str, reset_videos: bool) -> None:
    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"SQLite DB not found: {db_file.resolve()}")

    conn = sqlite3.connect(str(db_file))
    try:
        cur = conn.cursor()

        # 清表（在事务里执行）
        cur.execute("DELETE FROM clips;")
        if reset_videos:
            cur.execute("DELETE FROM videos;")

        conn.commit()  # ✅ 先提交事务

        # ✅ VACUUM 必须在事务外执行（最好用 autocommit）
        conn.isolation_level = None
        conn.execute("VACUUM;")

    finally:
        conn.close()



def reset_chroma(chroma_dir: str) -> None:
    p = Path(chroma_dir)
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True, exist_ok=True)


def delete_thumbnails(thumbnails_dir: str) -> None:
    p = Path(thumbnails_dir)
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Reset clips table + chroma db (optional thumbnails/videos).")
    parser.add_argument("--db", default=DEFAULT_DB, help=f"SQLite DB path (default: {DEFAULT_DB})")
    parser.add_argument("--chroma", default=DEFAULT_CHROMA_DIR, help=f"Chroma directory (default: {DEFAULT_CHROMA_DIR})")
    parser.add_argument("--thumbs", default=DEFAULT_THUMBS_DIR, help=f"Thumbnails directory (default: {DEFAULT_THUMBS_DIR})")

    parser.add_argument("--reset-videos", action="store_true", help="Also delete rows in videos table")
    parser.add_argument("--delete-thumbnails", action="store_true", help="Also delete thumbnails directory (clips/)")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()

    print("=== RESET PLAN ===")
    print(f"- SQLite DB: {Path(args.db).resolve()}")
    print(f"  * clear table: clips")
    print(f"  * clear table: videos  -> {args.reset_videos}")
    print(f"- Chroma dir: {Path(args.chroma).resolve()} (will be deleted and recreated)")
    print(f"- Thumbnails dir: {Path(args.thumbs).resolve()} (delete -> {args.delete_thumbnails})")
    print("==================")

    if not args.yes:
        confirm = input("Type YES to proceed: ").strip()
        if confirm != "YES":
            print("Cancelled.")
            return

    # 1) SQLite
    reset_sqlite(args.db, reset_videos=args.reset_videos)
    print("✅ SQLite reset done.")

    # 2) Chroma
    reset_chroma(args.chroma)
    print("✅ Chroma directory reset done.")

    # 3) Thumbnails
    if args.delete_thumbnails:
        delete_thumbnails(args.thumbs)
        print("✅ Thumbnails directory reset done.")

    print("\n✅ All done. Next steps:")
    print("1) 重新导入视频（会按‘镜头切割’生成新的 clips 和缩略图）")
    print("2) 运行 reindex.py（把新 clips 重新向量化写入 Chroma）")


if __name__ == "__main__":
    main()
