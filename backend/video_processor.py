"""
视频处理模块
负责视频切片、缩略图生成、特征提取
"""

import cv2
import subprocess
from pathlib import Path
from typing import Tuple, List
import numpy as np
from PIL import Image


class VideoProcessor:
    """视频处理器"""
    
    def __init__(self, clips_dir: str, clip_duration: float = 4.0, stride: float = 2.0):
        """
        Args:
            clips_dir: 片段存储目录
            clip_duration: 片段时长（秒）
            stride: 步长（秒）
        """
        self.clips_dir = Path(clips_dir)
        self.clip_duration = clip_duration
        self.stride = stride
        self.clips_dir.mkdir(parents=True, exist_ok=True)
    
    def get_video_info(self, video_path: str) -> Tuple[float, str, float]:
        """
        获取视频基本信息
        
        Returns:
            (duration, resolution, fps)
        """
        cap = cv2.VideoCapture(video_path)
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration = frame_count / fps if fps > 0 else 0
        
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        resolution = f"{width}x{height}"
        
        cap.release()
        
        return duration, resolution, fps
    
    def generate_clips(self, video_path: str, duration: float) -> List[Tuple[float, float]]:
        """
        生成片段时间戳列表
        
        Returns:
            [(start_time, end_time), ...]
        """
        clips = []
        current_time = 0.0
        
        while current_time < duration:
            end_time = min(current_time + self.clip_duration, duration)
            clips.append((current_time, end_time))
            current_time += self.stride
        
        return clips
    
    def extract_thumbnail(self, video_path: str, timestamp: float, output_path: str) -> bool:
        """
        提取视频帧作为缩略图
        
        Args:
            video_path: 视频路径
            timestamp: 时间戳（秒）
            output_path: 输出路径
        
        Returns:
            是否成功
        """
        cap = cv2.VideoCapture(video_path)
        
        # 定位到指定时间
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_number = int(timestamp * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            return False
        
        # 保存缩略图
        cv2.imwrite(output_path, frame)
        return True
    
    def extract_middle_frame(self, video_path: str, start_time: float, end_time: float, output_path: str) -> bool:
        """
        提取片段中间帧作为缩略图
        
        Args:
            video_path: 视频路径
            start_time: 开始时间
            end_time: 结束时间
            output_path: 输出路径
        
        Returns:
            是否成功
        """
        middle_time = (start_time + end_time) / 2
        return self.extract_thumbnail(video_path, middle_time, output_path)
    
    def extract_frame_at_time(self, video_path: str, time_sec: float, output_path: str, target_width: int = 480) -> bool:
        """
        在指定时间点抽一帧保存为 jpg
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return False

        # 定位到毫秒
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, time_sec) * 1000.0)
        ok, frame = cap.read()
        cap.release()

        if not ok or frame is None:
            return False

        # 缩放（可选，但强烈推荐：更快、embedding 更稳定）
        h, w = frame.shape[:2]
        if target_width and w > target_width:
            new_h = int(h * (target_width / w))
            frame = cv2.resize(frame, (target_width, new_h), interpolation=cv2.INTER_AREA)

        return bool(cv2.imwrite(output_path, frame))

    def extract_clip_frames(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        base_output_path: str,
        num_frames: int = 5,
        target_width: int = 480,
    ) -> tuple[bool, str]:
        """
        为一个 clip 抽 num_frames 帧，保存为：
          base_output_path 作为主缩略图（中间帧）
          同时保存 base_output_path 去掉 .jpg 后追加 _f{i}.jpg 的多帧文件
        返回：(success, main_thumbnail_path)
        """
        # 计算采样时间点：10%, 30%, 50%, 70%, 90%
        duration = max(0.001, end_time - start_time)
        ratios = [(i + 1) / (num_frames + 1) for i in range(num_frames)]
        sample_times = [start_time + duration * r for r in ratios]

        base = str(base_output_path)
        if base.lower().endswith(".jpg"):
            base_no_ext = base[:-4]
        else:
            base_no_ext = base

        saved_paths = []
        for i, t in enumerate(sample_times):
            out_path = f"{base_no_ext}_f{i}.jpg"
            ok = self.extract_frame_at_time(video_path, t, out_path, target_width=target_width)
            if ok:
                saved_paths.append(out_path)

        if not saved_paths:
            return False, base

        # 选中间帧作为主缩略图（用于 UI 和 DB）
        mid_index = len(saved_paths) // 2
        main_path = saved_paths[mid_index]

        # 把 main_path 复制/另存为 base_output_path（保持你原本的命名 clip_0000.jpg）
        # 这样数据库里 thumbnail_path 仍然是 clip_0000.jpg，不用改任何 DB/前端逻辑
        img = cv2.imread(main_path)
        if img is None:
            return False, base
        ok_main = bool(cv2.imwrite(base, img))
        return ok_main, base
    
    def process_video(self, video_path: str, db, search_engine=None) -> str:
        """
        处理视频：按镜头切割 + 生成多帧缩略图 + 存入数据库
        如果传入 search_engine，则在导入过程中同步写入向量库（Chroma），从此不必手动 reindex。
        """
        print(f"\n{'='*60}")
        print(f"📹 处理视频: {Path(video_path).name}")
        print(f"{'='*60}")

        # 1. 获取视频信息
        print("⏱️  获取视频信息...")
        duration, resolution, fps = self.get_video_info(video_path)
        print(f"   时长: {duration:.2f}秒 | 分辨率: {resolution} | FPS: {fps:.2f}")

        # 2. 添加视频到数据库
        video_id = db.add_video(video_path, duration, resolution, fps)
        print(f"✅ 视频ID: {video_id}")

        # 3. 生成片段列表（按镜头）
        print("🔪 生成片段（按镜头切割）...")
        clips = self.generate_clips_by_scene(video_path)
        print(f"   共 {len(clips)} 个片段")

        # 4. 为每个片段创建目录
        video_clips_dir = self.clips_dir / video_id
        video_clips_dir.mkdir(parents=True, exist_ok=True)

        print("📸 生成缩略图（每段抽 5 帧，用中间帧做主缩略图）...")

        saved = 0
        indexed = 0

        for idx, (start_time, end_time) in enumerate(clips):
            # 主缩略图命名仍保持不变（兼容你现有 DB/前端）
            thumbnail_name = f"clip_{idx:04d}.jpg"
            thumbnail_path = video_clips_dir / thumbnail_name

            success, main_thumb = self.extract_clip_frames(
                video_path=video_path,
                start_time=start_time,
                end_time=end_time,
                base_output_path=str(thumbnail_path),
                num_frames=5,
                target_width=480,
            )

            if not success:
                continue

            # ✅ 写入 SQLite，并拿到 clip_id
            clip_id = db.add_clip(video_id, start_time, end_time, str(main_thumb))
            saved += 1

            # ✅ 同步写入向量库（可选）
            if search_engine is not None:
                try:
                    search_engine.index_clip(clip_id, str(main_thumb))
                    indexed += 1
                except Exception as e:
                    # 不因为单个片段索引失败而中断导入
                    print(f"⚠️  索引失败 clip_id={clip_id}: {e}")

            if (idx + 1) % 10 == 0:
                if search_engine is None:
                    print(f"   进度: {idx + 1}/{len(clips)} | 已保存: {saved}")
                else:
                    print(f"   进度: {idx + 1}/{len(clips)} | 已保存: {saved} | 已索引: {indexed}")

        print(f"✅ 完成! 共保存 {saved} 个片段 | 共索引 {indexed} 个片段")
        print(f"{'='*60}\n")

        return video_id


    
    def generate_clips_by_scene(self, video_path: str):
        """
        使用 PySceneDetect 按镜头切割，返回 [(start_sec, end_sec), ...]
        并做三步处理：
        1) 镜头检测（ContentDetector + min_scene_len 防碎）
        2) 过滤极短镜头 + 超长镜头二次细分（你原来的两道防护）
        3) 合并短镜头：把很多短镜头合成“可检索片段”（推荐 2~8s）
        """
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import ContentDetector

        # ===== 可调参数（建议先用默认） =====
        THRESHOLD = 30.0          # 动漫建议 25~40 之间试
        MIN_SCENE_LEN_FRAMES = 15 # 30fps 下约 0.5s，可明显减少碎镜头/闪白
        MIN_LEN = 0.6             # 过滤小于 0.6s 的镜头（太碎）
        MAX_LEN = 12.0            # 大于 12s 的镜头太长，先二次细分
        DROP_BELOW = 0.2          # 小于 0.2s 的直接丢弃（通常是闪白/噪声）
        MERGE_MIN_TARGET = 2.0    # 合并后片段至少 2s（更像“语义片段”）
        MERGE_MAX_TARGET = 8.0    # 合并后片段最多 8s（避免太长）
        # ==================================

        # 1) 镜头检测
        video = open_video(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(
            ContentDetector(threshold=THRESHOLD, min_scene_len=MIN_SCENE_LEN_FRAMES)
        )
        scene_manager.detect_scenes(video)
        scene_list = scene_manager.get_scene_list()

        raw_clips = []
        for start_tc, end_tc in scene_list:
            s = float(start_tc.get_seconds())
            e = float(end_tc.get_seconds())
            if e > s:
                raw_clips.append((s, e))

        # 2) 你原来的两道防护（过滤极短 + 超长细分）
        protected = []
        for s, e in raw_clips:
            length = e - s

            if length <= DROP_BELOW:
                continue

            if length < MIN_LEN:
                continue

            if length > MAX_LEN:
                sub = s
                while sub < e:
                    sub_end = min(sub + self.clip_duration, e)
                    if sub_end - sub >= MIN_LEN:
                        protected.append((sub, sub_end))
                    sub += self.stride
            else:
                protected.append((s, e))

        # 3) 合并短镜头：把碎镜头合成“可检索片段”
        def merge_short_scenes(scenes, min_target=MERGE_MIN_TARGET, max_target=MERGE_MAX_TARGET, drop_below=DROP_BELOW):
            merged = []
            cur_start, cur_end = None, None

            for s, e in scenes:
                if (e - s) <= drop_below:
                    continue

                if cur_start is None:
                    cur_start, cur_end = s, e
                    continue

                # 尝试并入当前片段
                new_len = e - cur_start

                # 如果并入会超过 max_target，就先落地当前片段，再开新片段
                if new_len > max_target:
                    merged.append((cur_start, cur_end))
                    cur_start, cur_end = s, e
                else:
                    cur_end = e

                # 达到最小目标长度就落地（避免无限合并）
                if (cur_end - cur_start) >= min_target:
                    merged.append((cur_start, cur_end))
                    cur_start, cur_end = None, None

            if cur_start is not None:
                merged.append((cur_start, cur_end))

            return merged

        out = merge_short_scenes(protected)

        return out

        
        