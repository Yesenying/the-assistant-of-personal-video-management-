"""
个人视频素材知识库 - 后端 API
提供视频处理、片段索引、语义搜索功能
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
from pathlib import Path
import json
from datetime import datetime

from video_processor import VideoProcessor
from search_engine import SearchEngine
from database import Database
import subprocess
import re


app = Flask(__name__)
CORS(app)

# 配置（支持环境变量覆盖）
BASE_DIR = Path(os.environ.get("APP_BASE_DIR", Path(__file__).parent.parent))
DATA_DIR = Path(os.environ.get("APP_DATA_DIR", BASE_DIR / "data"))
CLIPS_DIR = Path(os.environ.get("APP_CLIPS_DIR", BASE_DIR / "clips"))
DB_PATH = DATA_DIR / "video_library.db"

# 确保目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

# 打印配置（调试用）
print(f"📂 BASE_DIR: {BASE_DIR}")
print(f"📂 DATA_DIR: {DATA_DIR}")
print(f"📂 CLIPS_DIR: {CLIPS_DIR}")

# 初始化组件
db = Database(str(DB_PATH))
video_processor = VideoProcessor(str(CLIPS_DIR))
search_engine = SearchEngine(db)
 

def _safe_filename(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9._-]+', '_', name)

@app.route('/api/clips/<clip_id>/download', methods=['GET'])
def download_clip(clip_id):
    clip = db.get_clip(clip_id)
    if not clip:
        return jsonify({"success": False, "error": "Clip not found"}), 404

    video = db.get_video(clip["video_id"])
    if not video:
        return jsonify({"success": False, "error": "Video not found"}), 404

    video_path = video.get("path") or video.get("video_path") or video.get("file_path")
    if not video_path or not os.path.exists(video_path):
        return jsonify({"success": False, "error": "Video file not found"}), 404

    start = float(clip["start_time"])
    end = float(clip["end_time"])
    duration = max(0.01, end - start)

    # ✅ 用项目根目录，避免 CWD 不同导致路径错乱
    ROOT = Path(__file__).resolve().parent.parent  # .../video_knowledge_base
    out_dir = ROOT / "data" / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = _safe_filename(f"{clip['video_id']}_{clip_id}_{start:.2f}-{end:.2f}.mp4")
    out_path = out_dir / filename

    def run_ffmpeg(cmd):
        try:
            r = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return r.returncode, (r.stderr or b"").decode("utf-8", errors="ignore")
        except FileNotFoundError:
            return -1, "ffmpeg not found. Please install ffmpeg."

    # 1) 先尝试极速裁剪（不重编码）
    if not out_path.exists():
        cmd_copy = [
            "ffmpeg", "-y",
            "-ss", f"{start}",
            "-i", video_path,
            "-t", f"{duration}",
            "-c", "copy",
            str(out_path)
        ]
        code, err = run_ffmpeg(cmd_copy)

        # ✅ 如果没生成文件 / 或文件大小异常小，走重编码兜底
        if (code != 0) or (not out_path.exists()) or (out_path.stat().st_size < 1024):
            # 清理可能的坏文件
            if out_path.exists():
                try:
                    out_path.unlink()
                except:
                    pass

            cmd_reencode = [
                "ffmpeg", "-y",
                "-ss", f"{start}",
                "-i", video_path,
                "-t", f"{duration}",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                str(out_path)
            ]
            code2, err2 = run_ffmpeg(cmd_reencode)

            if (code2 != 0) or (not out_path.exists()):
                # 返回更可读的错误
                detail = (err2 or err)[-1500:]
                return jsonify({
                    "success": False,
                    "error": "ffmpeg failed to generate clip",
                    "detail": detail
                }), 500

    # 2) 最终再校验一次（避免 send_file 再 500）
    if not out_path.exists():
        return jsonify({"success": False, "error": "Output clip not found after ffmpeg"}), 500

    return send_file(
        str(out_path),
        as_attachment=True,
        download_name=filename,
        mimetype="video/mp4"
    )


@app.route('/api/videos/import_batch', methods=['POST'])
def import_videos_batch():
    """
    批量导入视频：
    - 支持传入 paths: ["/a.mp4", "/b.mp4"]
    - 或传入 dir: "/path/to/folder" 让后端扫描目录（递归）
    """
    data = request.json or {}
    paths = data.get('paths', [])
    dir_path = data.get('dir')
    exts = set([e.lower() for e in data.get('exts', ['.mp4', '.mkv', '.mov', '.webm'])])

    # 1) 收集待导入文件列表
    file_list = []

    if dir_path:
        if not os.path.exists(dir_path):
            return jsonify({"success": False, "error": f"Invalid dir: {dir_path}"}), 400

        for root, _, files in os.walk(dir_path):
            for fn in files:
                p = os.path.join(root, fn)
                if os.path.splitext(p)[1].lower() in exts:
                    file_list.append(p)

    if paths:
        file_list.extend(paths)

    # 去重 + 过滤不存在
    seen = set()
    uniq = []
    for p in file_list:
        if not p or p in seen:
            continue
        seen.add(p)
        if os.path.exists(p):
            uniq.append(p)

    if not uniq:
        return jsonify({"success": False, "error": "No valid video files found"}), 400

    # 2) 逐个导入（切割 + 入库 + 同步索引）
    results = []
    ok = 0
    fail = 0

    for p in uniq:
        try:
            # ✅ 关键：你现在的 process_video 已经支持 search_engine 同步 index（你刚改过）
            video_id = video_processor.process_video(p, db, search_engine)
            results.append({"path": p, "success": True, "video_id": video_id})
            ok += 1
        except Exception as e:
            results.append({"path": p, "success": False, "error": str(e)})
            fail += 1

    return jsonify({
        "success": True,
        "total": len(uniq),
        "ok": ok,
        "fail": fail,
        "results": results
    })


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/api/videos', methods=['GET'])
def list_videos():
    """获取所有视频列表"""
    videos = db.get_all_videos()
    return jsonify({
        "success": True,
        "videos": videos
    })


@app.route('/api/videos/<video_id>', methods=['GET'])
def get_video_details(video_id):
    """获取视频详情"""
    video = db.get_video(video_id)
    if not video:
        return jsonify({"success": False, "error": "Video not found"}), 404
    
    clips = db.get_clips_by_video(video_id)
    return jsonify({
        "success": True,
        "video": video,
        "clips": clips
    })


@app.route('/api/videos/import', methods=['POST'])
def import_video():
    """导入视频文件"""
    data = request.json
    video_path = data.get('path')
    
    if not video_path or not os.path.exists(video_path):
        return jsonify({
            "success": False,
            "error": "Invalid video path"
        }), 400
    
    try:
        # 处理视频
        video_id = video_processor.process_video(video_path, db, search_engine)

        # search_engine.index_video_clips(video_id)
        
        return jsonify({
            "success": True,
            "video_id": video_id,
            "message": "Video imported successfully"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# @app.route('/api/search', methods=['POST'])
# def search_clips():
#     """搜索视频片段"""
#     data = request.json
#     query = data.get('query', '')
#     top_k = data.get('top_k', 10)
    
#     if not query:
#         return jsonify({
#             "success": False,
#             "error": "Query cannot be empty"
#         }), 400
    
#     try:
#         results = search_engine.search(query, top_k)
#         return jsonify({
#             "success": True,
#             "query": query,
#             "results": results
#         })
#     except Exception as e:
#         return jsonify({
#             "success": False,
#             "error": str(e)
#         }), 500

@app.route('/api/search', methods=['POST'])
def search_clips():
    data = request.json or {}
    query = data.get('query', '')
    top_k = int(data.get('top_k', 10))

    # ✅ 新增可选参数（不传也有默认值）
    fetch_k = int(data.get('fetch_k', max(300, top_k * 30)))
    use_mmr = bool(data.get('use_mmr', True))
    mmr_lambda = float(data.get('mmr_lambda', 0.78))

    if not query:
        return jsonify({"success": False, "error": "Query cannot be empty"}), 400

    try:
        results = search_engine.search(
            query=query,
            top_k=top_k,
            fetch_k=fetch_k,
            use_mmr=use_mmr,
            mmr_lambda=mmr_lambda
        )
        return jsonify({"success": True, "query": query, "results": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



@app.route('/api/clips/<clip_id>/thumbnail', methods=['GET'])
def get_thumbnail(clip_id):
    """获取片段缩略图"""
    clip = db.get_clip(clip_id)
    if not clip or not clip['thumbnail_path']:
        return jsonify({"error": "Thumbnail not found"}), 404
    
    thumbnail_path = Path(clip['thumbnail_path'])
    if not thumbnail_path.exists():
        return jsonify({"error": "Thumbnail file not found"}), 404
    
    return send_file(thumbnail_path, mimetype='image/jpeg')


@app.route('/api/clips/<clip_id>/favorite', methods=['POST'])
def toggle_favorite(clip_id):
    """收藏/取消收藏片段"""
    data = request.json
    is_favorite = data.get('favorite', True)
    
    success = db.update_clip_favorite(clip_id, is_favorite)
    return jsonify({
        "success": success,
        "clip_id": clip_id,
        "favorite": is_favorite
    })


@app.route('/api/clips/<clip_id>/tags', methods=['POST'])
def update_tags(clip_id):
    """更新片段标签"""
    data = request.json
    tags = data.get('tags', [])
    
    success = db.update_clip_tags(clip_id, tags)
    return jsonify({
        "success": success,
        "clip_id": clip_id,
        "tags": tags
    })


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    stats = {
        "total_videos": db.count_videos(),
        "total_clips": db.count_clips(),
        "storage_used": "0 MB"  # TODO: 计算实际存储
    }
    return jsonify({
        "success": True,
        "stats": stats
    })

@app.route('/api/clips/<clip_id>', methods=['GET'])
def get_clip_details(clip_id):
    """获取片段详情（用于播放定位）"""
    clip = db.get_clip(clip_id)
    if not clip:
        return jsonify({"success": False, "error": "Clip not found"}), 404
    return jsonify({"success": True, "clip": clip})

@app.route('/api/videos/<video_id>/file', methods=['GET'])
@app.route('/api/videos/<video_id>/stream', methods=['GET'])  # ✅ 兼容前端现有 /stream
def get_video_file(video_id):
    """输出原视频文件（给浏览器 video 标签播放）"""
    video = db.get_video(video_id)
    if not video:
        return jsonify({"success": False, "error": "Video not found"}), 404

    video_path = video.get("path") or video.get("video_path") or video.get("file_path")
    if not video_path or not os.path.exists(video_path):
        return jsonify({"success": False, "error": "Video file not found"}), 404

    # ✅ conditional=True 对 <video> 的 Range/断点请求更友好
    return send_file(video_path, mimetype="video/mp4", conditional=True)

if __name__ == '__main__':
    print("=" * 60)
    print("🎬 个人视频素材知识库 - 后端服务")
    print("=" * 60)
    print(f"📂 数据目录: {DATA_DIR}")
    print(f"📂 片段目录: {CLIPS_DIR}")
    print(f"🗄️  数据库: {DB_PATH}")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
