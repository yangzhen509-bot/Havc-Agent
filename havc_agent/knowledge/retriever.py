"""知识检索:scikit-learn TF-IDF 向量化 + chromadb 向量数据库。

- 用 sklearn ``TfidfVectorizer`` 把知识 chunk 与 query 向量化(中文用自定义分词)。
- 把 chunk 向量写入 ``chromadb`` 向量库(余弦空间),query 走向量近邻检索。
中文无空格,采用"ASCII 词 + CJK unigram/bigram"混合分词。
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.config import Settings
from sklearn.feature_extraction.text import TfidfVectorizer

from .loader import KnowledgeChunk, load_chunks

_ASCII = re.compile(r"[a-z0-9]+")
_COLLECTION_SEQ = 0
# Streamlit 热重载会重置模块全局,但 EphemeralClient 按 Settings 缓存复用,
# 旧集合仍在 → 仅用序号 create 会报 already exists。
_EPHEMERAL_CLIENT: Any = None


def _ephemeral_client() -> Any:
    global _EPHEMERAL_CLIENT
    if _EPHEMERAL_CLIENT is None:
        _EPHEMERAL_CLIENT = chromadb.EphemeralClient(
            Settings(anonymized_telemetry=False)
        )
    return _EPHEMERAL_CLIENT


def tokenize(text: str) -> list[str]:
    text = text.lower()
    tokens = _ASCII.findall(text)
    for run in re.findall(r"[一-鿿]+", text):
        tokens.extend(run)                                   # unigram
        tokens.extend(run[i:i + 2] for i in range(len(run) - 1))  # bigram
    return tokens


class TfidfRetriever:
    """sklearn TF-IDF 向量 + chromadb 余弦近邻检索。"""

    def __init__(self, chunks: list[KnowledgeChunk]):
        self._chunks = chunks
        self._by_id = {c.id: c for c in chunks}
        self._vectorizer = TfidfVectorizer(
            tokenizer=tokenize, preprocessor=lambda x: x,
            token_pattern=None, lowercase=False,
        )
        self._col = None
        if not chunks:
            return
        matrix = self._vectorizer.fit_transform(c.searchable() for c in chunks)
        client = _ephemeral_client()
        global _COLLECTION_SEQ
        _COLLECTION_SEQ += 1
        # uuid 后缀避免热重载后与缓存客户端里旧集合重名
        name = f"knowledge_{_COLLECTION_SEQ}_{uuid.uuid4().hex[:8]}"
        self._col = client.create_collection(
            name=name, metadata={"hnsw:space": "cosine"}
        )
        self._col.add(
            ids=[c.id for c in chunks],
            embeddings=matrix.toarray().astype(float).tolist(),
            metadatas=[{"title": c.title} for c in chunks],
        )

    def retrieve(self, query: str, k: int = 3) -> list[tuple[KnowledgeChunk, float]]:
        if self._col is None:
            return []
        qv = self._vectorizer.transform([query]).toarray().astype(float).tolist()
        res = self._col.query(
            query_embeddings=qv, n_results=min(k, len(self._chunks))
        )
        out: list[tuple[KnowledgeChunk, float]] = []
        for cid, dist in zip(res["ids"][0], res["distances"][0]):
            sim = 1.0 - float(dist)  # 余弦距离 → 相似度
            if sim > 1e-6:
                out.append((self._by_id[cid], round(sim, 4)))
        return out


def build_default_retriever(docs_dir: Optional[Path] = None) -> TfidfRetriever:
    return TfidfRetriever(load_chunks(docs_dir))
