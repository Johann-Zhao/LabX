"""Chroma 向量检索：知识卡片灌库与查询。

为什么用本地字符 n-gram 向量而不是在线 embedding：
- 演示要求断网可跑（NFR2），在线 embedding 和 Chroma 默认的英文模型都要联网下载，且对中文差
- 中文按字二元（bigram）切分天然适配本场景；33 张卡片规模下精度足够
- 后续要换更强的 embedding，只需替换 LocalEmbedding 一个类
"""
import hashlib
import math
import os

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

CHROMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".chroma")
COLLECTION_NAME = "knowledge_cards"
DIM = 1024  # 哈希向量维度


class LocalEmbedding(EmbeddingFunction[Documents]):
    """确定性中文友好向量：字符二元组 + 词，哈希到固定维度后归一化。"""

    def __call__(self, input: Documents) -> Embeddings:
        return [self._embed(t) for t in input]

    @staticmethod
    def name() -> str:
        return "labx-local-ngram"

    def get_config(self) -> dict:
        return {"dim": DIM}

    @classmethod
    def build_from_config(cls, config: dict) -> "LocalEmbedding":
        return cls()

    def is_legacy(self) -> bool:
        return False

    @staticmethod
    def _stable_hash(feat: str) -> int:
        return int(hashlib.md5(feat.encode("utf-8")).hexdigest(), 16)

    def _embed(self, text: str) -> list[float]:
        v = [0.0] * DIM
        t = (text or "").lower()
        feats = [t[i : i + 2] for i in range(len(t) - 1)] + t.split()
        for f in feats:
            v[self._stable_hash(f) % DIM] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]


_client = chromadb.PersistentClient(path=CHROMA_DIR)
_ef = LocalEmbedding()


def _collection():
    return _client.get_or_create_collection(COLLECTION_NAME, embedding_function=_ef)


def rebuild_from_db(cards) -> int:
    """全量重建索引。init_db.py 灌完知识卡片后调用。"""
    try:
        _client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass  # 集合不存在时删除会报错，忽略
    coll = _collection()
    ids, docs, metas = [], [], []
    for c in cards:
        ids.append(c.id)
        docs.append(f"{c.title}\n{c.points}\n{c.content or ''}"[:2000])
        metas.append({"material_id": c.material_id, "card_type": c.card_type})
    if ids:
        coll.add(ids=ids, documents=docs, metadatas=metas)
    return len(ids)


def query(question: str, material_id: str | None = None, top_k: int = 3) -> list[dict]:
    """向量检索 top_k 张卡片；material_id 非空时先按物料精确过滤。"""
    coll = _collection()
    if coll.count() == 0:
        return []
    kwargs = {"where": {"material_id": material_id}} if material_id else {}
    res = coll.query(query_texts=[question], n_results=top_k, **kwargs)
    hits = []
    for cid, doc, meta, dist in zip(
        res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]
    ):
        title = (doc or "").split("\n", 1)[0]
        hits.append({"card_id": cid, "title": title, "text": doc, "score": 1 - dist})
    return hits
