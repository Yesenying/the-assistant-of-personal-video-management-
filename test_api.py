"""
API 测试脚本
用于测试后端各项功能
"""

import requests
import json
import time

API_BASE = "http://localhost:5000/api"

def test_health():
    """测试健康检查"""
    print("\n" + "="*60)
    print("测试 1: 健康检查")
    print("="*60)
    
    response = requests.get(f"{API_BASE}/health")
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    
    return response.status_code == 200

def test_import_video(video_path):
    """测试导入视频"""
    print("\n" + "="*60)
    print("测试 2: 导入视频")
    print("="*60)
    print(f"视频路径: {video_path}")
    
    response = requests.post(
        f"{API_BASE}/videos/import",
        json={"path": video_path}
    )
    
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get('success'):
        return result.get('video_id')
    return None

def test_list_videos():
    """测试获取视频列表"""
    print("\n" + "="*60)
    print("测试 3: 获取视频列表")
    print("="*60)
    
    response = requests.get(f"{API_BASE}/videos")
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(f"视频数量: {len(result.get('videos', []))}")
    
    if result.get('videos'):
        print("\n视频列表:")
        for video in result['videos']:
            print(f"  - {video['file_name']} ({video['duration']:.1f}s)")
    
    return result.get('success')

def test_search(query):
    """测试搜索功能"""
    print("\n" + "="*60)
    print("测试 4: 搜索片段")
    print("="*60)
    print(f"搜索关键词: {query}")
    
    response = requests.post(
        f"{API_BASE}/search",
        json={"query": query, "top_k": 5}
    )
    
    print(f"状态码: {response.status_code}")
    result = response.json()
    
    if result.get('success'):
        results = result.get('results', [])
        print(f"找到 {len(results)} 个结果:")
        
        for idx, clip in enumerate(results, 1):
            print(f"\n  {idx}. 相似度: {clip['similarity']*100:.1f}%")
            print(f"     时间: {clip['start_time']:.1f}s - {clip['end_time']:.1f}s")
            print(f"     缩略图: {clip['thumbnail_path']}")
    else:
        print(f"搜索失败: {result.get('error')}")
    
    return result.get('success')

def test_stats():
    """测试统计信息"""
    print("\n" + "="*60)
    print("测试 5: 获取统计信息")
    print("="*60)
    
    response = requests.get(f"{API_BASE}/stats")
    result = response.json()
    
    if result.get('success'):
        stats = result['stats']
        print(f"总视频数: {stats['total_videos']}")
        print(f"总片段数: {stats['total_clips']}")
        print(f"存储空间: {stats['storage_used']}")
    
    return result.get('success')

def main():
    """主测试流程"""
    print("🧪 开始 API 测试")
    
    # 1. 健康检查
    if not test_health():
        print("\n❌ 后端服务未启动，请先运行 python backend/app.py")
        return
    
    print("\n✅ 后端服务正常")
    
    # 2. 获取统计
    test_stats()
    
    # 3. 获取视频列表
    test_list_videos()
    
    # 4. 导入视频（可选）
    video_path = input("\n输入要测试的视频路径（留空跳过）: ").strip()
    if video_path:
        video_id = test_import_video(video_path)
        if video_id:
            print(f"\n✅ 视频导入成功，ID: {video_id}")
            print("⏳ 等待索引完成...")
            time.sleep(5)
    
    # 5. 测试搜索
    query = input("\n输入搜索关键词（留空跳过）: ").strip()
    if query:
        test_search(query)
    
    print("\n" + "="*60)
    print("🎉 测试完成")
    print("="*60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  测试中断")
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
