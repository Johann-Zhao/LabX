"""Chroma 向量检索 + IDF 重排：知识卡片灌库与查询。

设计（为什么离线、为什么是 n-gram + IDF）：
- 演示要求断网可跑（NFR2），在线 embedding 和 Chroma 默认英文模型都要联网下载，且对中文差
- Chroma 负责存储与粗召回；纯 Python IDF 重排解决"哈希向量相关度区分度差"的问题
  （45 张卡片规模，暴力重排零成本；特征按文档频率加权，稀有特征才是相关性强信号）
- 后续要换更强的 embedding，只需替换 LocalEmbedding 一个类
"""
import hashlib
import math
import os

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

CHROMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".chroma")
COLLECTION_NAME = "knowledge_cards"
DIM = 1024  # 哈希向量维度（粗召回用）


class LocalEmbedding(EmbeddingFunction[Documents]):
    """确定性中文友好向量：字符二元组 + 词，哈希到固定维度后归一化。"""

    def __call__(self, input: Documents) -> Embeddings:
        return [self._embed(t) for t in input]

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

# IDF 重排用的文档频率表（特征 → 含该特征的文档数），懒加载
_DF: dict[str, float] | None = None
_DF_NDOCS = 0


def _collection():
    return _client.get_or_create_collection(COLLECTION_NAME, embedding_function=_ef)


def _features(text: str) -> list[str]:
    t = (text or "").lower()
    return [t[i : i + 2] for i in range(len(t) - 1)] + t.split()


def _doc_text(card) -> str:
    return f"{card.title}\n{card.points}\n{card.content or ''}"[:2000]


def _compute_df(docs: list[str]) -> None:
    global _DF, _DF_NDOCS
    df: dict[str, float] = {}
    for doc in docs:
        for feat in set(_features(doc)):
            df[feat] = df.get(feat, 0) + 1
    _DF = df
    _DF_NDOCS = len(docs)


def _ensure_df() -> None:
    """_DF 为空时从 Chroma 里重建（服务重启不跑 init_db 也能用）。"""
    global _DF
    if _DF is not None:
        return
    coll = _collection()
    got = coll.get()
    _compute_df(got["documents"] or [])


def rebuild_from_db(cards) -> int:
    """全量重建索引（Chroma 向量 + IDF 词表）。init_db.py 灌完知识卡片后调用。"""
    try:
        _client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass  # 集合不存在时删除会报错，忽略
    coll = _collection()
    ids, docs, metas = [], [], []
    for c in cards:
        ids.append(c.id)
        docs.append(_doc_text(c))
        metas.append({"material_id": c.material_id, "card_type": c.card_type})
    if ids:
        coll.add(ids=ids, documents=docs, metadatas=metas)
    _compute_df(docs)
    return len(ids)


def add_card(card) -> None:
    """增量索引一张卡片（社区经验入库后调用），并更新 IDF 词表。"""
    global _DF
    text = _doc_text(card)
    coll = _collection()
    coll.add(
        ids=[card.id],
        documents=[text],
        metadatas=[{"material_id": card.material_id, "card_type": card.card_type}],
    )
    _ensure_df()
    for feat in set(_features(text)):
        _DF[feat] = _DF.get(feat, 0) + 1
    global _DF_NDOCS
    _DF_NDOCS += 1


def _idf_score(query_feats: list[str], doc_text: str) -> float:
    """查询与文档的 IDF 加权重合度：共享特征越稀有得分越高。"""
    if not _DF_NDOCS:
        return 0.0
    doc_feats = set(_features(doc_text))
    score = 0.0
    for f in set(query_feats) & doc_feats:
        df = _DF.get(f, 0.5)
        score += math.log((_DF_NDOCS + 1) / (df + 0.5))
    return score


def query(question: str, material_id: str | None = None, top_k: int = 3) -> list[dict]:
    """Chroma 粗召回 top_k*2 → IDF 重排取 top_k。score 为 IDF 重合度（越大越相关）。"""
    coll = _collection()
    if coll.count() == 0:
        return []
    _ensure_df()
    kwargs = {"where": {"material_id": material_id}} if material_id else {}
    res = coll.query(query_texts=[question], n_results=min(top_k * 2, coll.count()), **kwargs)
    hits = []
    q_feats = _features(question)
    for cid, doc, meta in zip(res["ids"][0], res["documents"][0], res["metadatas"][0]):
        hits.append({
            "card_id": cid,
            "title": (doc or "").split("\n", 1)[0],
            "text": doc,
            "material_id": meta.get("material_id"),
            "card_type": meta.get("card_type"),
            "score": _idf_score(q_feats, doc or ""),
        })
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:top_k]
