# import os
# print("CWD =", os.getcwd())
# print("CHROMA_PATH =", os.path.abspath("./data/chroma_db"))


# import chromadb

# client = chromadb.PersistentClient(path="./data/chroma_db")

# # 看看有哪些 collections
# print("collections =", [c.name for c in client.list_collections()])

# # 你的 collection 名字如果是 "clips"
# col = client.get_or_create_collection("clips")
# print("clips count =", col.count())

# q1 = model.encode("雨夜 屋顶", normalize_embeddings=True)
# q2 = model.encode("教室 争吵", normalize_embeddings=True)
# print(q1[:8], q2[:8])
# print("cosine(q1,q2)=", float((q1 @ q2)))

# 查看存入的embedding相关参数以及元数据
import chromadb

client = chromadb.PersistentClient(path="./data/chroma_db")
col = client.get_collection("video_clips")

res = col.get(limit=5, include=["embeddings", "metadatas"])

print("sample ids:", res["ids"])

emb = res.get("embeddings", None)
if emb is None:
    print("embeddings: None (可能没取到)")
else:
    print("embeddings type:", type(emb))
    print("embeddings shape:", getattr(emb, "shape", None))
    print("embedding dim:", len(emb[0]) if len(emb) > 0 else None)

meta = res.get("metadatas", None)
print("sample meta:", meta[0] if meta and len(meta) > 0 else None)
print("collection metadata:", col.metadata)

