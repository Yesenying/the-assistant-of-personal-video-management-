"""
数据库管理模块
使用 SQLite 存储元数据，Chroma 存储向量
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Optional
import uuid
from datetime import datetime


class Database:
    """数据库管理类"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表结构"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        cursor = self.conn.cursor()
        
        # 视频表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                duration REAL,
                resolution TEXT,
                fps REAL,
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        
        # 片段表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clips (
                clip_id TEXT PRIMARY KEY,
                video_id TEXT NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                thumbnail_path TEXT,
                is_favorite INTEGER DEFAULT 0,
                tags TEXT,
                created_at TEXT,
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_clips_video ON clips(video_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_clips_favorite ON clips(is_favorite)')
        
        self.conn.commit()
    
    def add_video(self, file_path: str, duration: float, resolution: str = None, fps: float = None) -> str:
        """添加视频记录"""
        video_id = str(uuid.uuid4())
        file_name = Path(file_path).name
        now = datetime.now().isoformat()
        
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO videos (video_id, file_name, file_path, duration, resolution, fps, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (video_id, file_name, file_path, duration, resolution, fps, now, now))
        
        self.conn.commit()
        return video_id
    
    def add_clip(self, video_id: str, start_time: float, end_time: float, thumbnail_path: str = None) -> str:
        """添加片段记录"""
        clip_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO clips (clip_id, video_id, start_time, end_time, thumbnail_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (clip_id, video_id, start_time, end_time, thumbnail_path, now))
        
        self.conn.commit()
        return clip_id
    
    def get_video(self, video_id: str) -> Optional[Dict]:
        """获取视频信息"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM videos WHERE video_id = ?', (video_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_all_videos(self) -> List[Dict]:
        """获取所有视频"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM videos ORDER BY created_at DESC')
        return [dict(row) for row in cursor.fetchall()]
    
    def get_clip(self, clip_id: str) -> Optional[Dict]:
        """获取片段信息"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM clips WHERE clip_id = ?', (clip_id,))
        row = cursor.fetchone()
        if row:
            result = dict(row)
            result['tags'] = json.loads(result['tags']) if result['tags'] else []
            return result
        return None
    
    def get_clips_by_video(self, video_id: str) -> List[Dict]:
        """获取视频的所有片段"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM clips 
            WHERE video_id = ? 
            ORDER BY start_time ASC
        ''', (video_id,))
        
        clips = []
        for row in cursor.fetchall():
            clip = dict(row)
            clip['tags'] = json.loads(clip['tags']) if clip['tags'] else []
            clips.append(clip)
        return clips
    
    def update_clip_favorite(self, clip_id: str, is_favorite: bool) -> bool:
        """更新片段收藏状态"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE clips SET is_favorite = ? WHERE clip_id = ?
        ''', (1 if is_favorite else 0, clip_id))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def update_clip_tags(self, clip_id: str, tags: List[str]) -> bool:
        """更新片段标签"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE clips SET tags = ? WHERE clip_id = ?
        ''', (json.dumps(tags), clip_id))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def count_videos(self) -> int:
        """统计视频数量"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM videos')
        return cursor.fetchone()[0]
    
    def count_clips(self) -> int:
        """统计片段数量"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM clips')
        return cursor.fetchone()[0]
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
