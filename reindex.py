# reindex.py（放项目根目录）
from backend.database import Database
from backend.search_engine import SearchEngine

db = Database("data/video_library.db")
se = SearchEngine(db)
se.reindex_all()
print("DONE")
