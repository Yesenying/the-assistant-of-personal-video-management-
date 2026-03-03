# 🎬 个人视频素材知识库 V1

> 用关键词搜索视频片段，1分钟找到你要的画面

## 📋 功能特性

✅ **自动片段化** - 视频自动切割为4秒片段，步长2秒  
✅ **语义搜索** - 用自然语言描述查找画面  
✅ **缩略图预览** - 每个片段生成代表帧  
✅ **本地运行** - 数据完全存储在本地，保护隐私  
✅ **开源模型** - 使用 CLIP 模型，无需 API 费用  

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- FFmpeg (用于视频处理)
- 8GB+ RAM (推荐)
- Mac / Linux / Windows

### 2. 安装依赖

```bash
# 克隆或下载项目后
cd video_knowledge_base

# 安装 Python 依赖
pip install -r requirements.txt

# Mac 安装 FFmpeg (如果还没装)
brew install ffmpeg

# 安装 CLIP 模型
pip install git+https://github.com/openai/CLIP.git
```

### 3. 启动后端服务

```bash
cd backend
python app.py
```

看到以下输出表示启动成功：
```
============================================================
🎬 个人视频素材知识库 - 后端服务
============================================================
📂 数据目录: /path/to/data
📂 片段目录: /path/to/clips
🗄️  数据库: /path/to/video_library.db
============================================================
 * Running on http://0.0.0.0:5000
```

### 4. 打开前端页面

在浏览器中打开：
```
file:///path/to/video_knowledge_base/frontend/index.html
```

或者直接双击 `frontend/index.html` 文件。

## 📖 使用说明

### 导入视频

1. 在前端页面顶部输入框中输入视频文件路径
2. 点击"导入视频"按钮
3. 等待处理完成（24分钟视频约需5分钟）

示例路径：
```
/Users/yesenying/Documents/videos/紫罗兰永恒花园/mp4/第七集.mp4
```

### 搜索片段

1. 在搜索框中输入关键词描述
2. 点击"搜索"或按回车
3. 浏览搜索结果，点击查看缩略图

搜索示例：
- "雨夜屋顶拔刀"
- "情绪爆发的场景"
- "两个人对视的镜头"
- "夕阳下的剪影"

## 🏗️ 项目结构

```
video_knowledge_base/
├── backend/               # 后端服务
│   ├── app.py            # Flask API
│   ├── database.py       # 数据库管理
│   ├── video_processor.py # 视频处理
│   └── search_engine.py  # 搜索引擎
├── frontend/             # 前端页面
│   └── index.html        # Web UI
├── data/                 # 数据存储
│   ├── video_library.db  # SQLite 数据库
│   └── chroma_db/        # 向量数据库
├── clips/                # 片段和缩略图
│   └── [video_id]/
│       ├── clip_0000.jpg
│       └── ...
└── requirements.txt      # Python 依赖
```

## ⚙️ 配置说明

### 修改片段切割参数

编辑 `backend/video_processor.py`:

```python
def __init__(self, clips_dir: str, clip_duration: float = 4.0, stride: float = 2.0):
    # clip_duration: 片段时长（秒）
    # stride: 步长（秒）
```

### 修改搜索模型

编辑 `backend/search_engine.py`:

```python
def __init__(self, db, model_name: str = "ViT-B/32"):
    # 可选模型：
    # - "ViT-B/32" (默认，快速)
    # - "ViT-B/16" (更准确，更慢)
    # - "ViT-L/14" (最准确，需要更多内存)
```

## 🔧 故障排查

### 问题 1：CLIP 模型下载失败

**解决方案**：手动安装
```bash
pip install git+https://github.com/openai/CLIP.git
```

### 问题 2：视频导入失败

**检查项**：
1. 确认 FFmpeg 已安装：`ffmpeg -version`
2. 确认视频文件路径正确
3. 确认视频格式支持（mp4, mkv, avi, mov）

### 问题 3：搜索没有结果

**可能原因**：
1. 还没有导入视频
2. 向量索引未建立（查看后端日志）
3. 关键词描述太具体

### 问题 4：内存不足

**解决方案**：
1. 使用更小的 CLIP 模型 (ViT-B/32)
2. 减少片段数量（增大 stride）
3. 分批导入视频

## 📊 性能指标

**单集 24 分钟动漫视频**：
- 片段数量：约 720 个
- 处理时间：约 5 分钟
- 存储空间：约 150 MB
- 搜索响应：< 2 秒

## 🎯 V1 验收标准

✅ 能成功导入一集动漫  
✅ 能生成可浏览的片段列表  
✅ 能通过关键词命中用户预期片段（Top-10 内）  

## 🔜 后续计划 (V2)

- [ ] 更细粒度标签
- [ ] 连续片段合并
- [ ] 视频播放器集成
- [ ] 批量导入文件夹
- [ ] 搜索历史记录
- [ ] 收藏夹管理

## 📝 技术栈

- **后端**: Flask + Python
- **视频处理**: OpenCV + FFmpeg
- **AI 模型**: CLIP (OpenAI)
- **向量数据库**: ChromaDB
- **元数据库**: SQLite
- **前端**: 原生 HTML/CSS/JS

## 🤝 反馈与贡献

遇到问题或有建议？欢迎：
- 提交 Issue
- 发起 Pull Request
- 分享使用体验

## 📄 许可证

MIT License

---

**让视频素材像文档一样可搜索！** 🚀
