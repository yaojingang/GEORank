"""
向量数据库服务 — Qdrant
负责公司知识库的语义检索
支持连接失败时降级（本地开发无 Qdrant 时不崩溃）
"""
from typing import Optional
from app.core.config import settings

COLLECTION = settings.QDRANT_COLLECTION
DIM = settings.EMBEDDING_DIMENSIONS


class VectorStore:
    """Qdrant 向量存储封装，连接懒初始化"""

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            from qdrant_client import QdrantClient
            self._client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT, timeout=5)
        return self._client

    def ensure_collection(self):
        """启动时确保 Collection 存在"""
        from qdrant_client.models import Distance, VectorParams
        from qdrant_client.http.exceptions import UnexpectedResponse
        client = self._get_client()
        collections = [c.name for c in client.get_collections().collections]
        if COLLECTION not in collections:
            try:
                client.create_collection(
                    collection_name=COLLECTION,
                    vectors_config=VectorParams(size=DIM, distance=Distance.COSINE),
                )
            except UnexpectedResponse as exc:
                # 并发初始化时可能会出现 409，说明另一任务已经创建成功。
                if "already exists" not in str(exc):
                    raise

    def upsert_company_vectors(self, company_id: str, chunks: list[dict]):
        """
        将公司知识库的文本块写入向量库
        chunks: [{"id": int, "text": "...", "vector": [...], "metadata": {...}}]
        """
        from qdrant_client.models import PointStruct
        client = self._get_client()
        points = [
            PointStruct(
                id=chunk["id"],
                vector=chunk["vector"],
                payload={
                    "company_id": company_id,
                    "text": chunk["text"],
                    **chunk.get("metadata", {}),
                },
            )
            for chunk in chunks
        ]
        client.upsert(collection_name=COLLECTION, points=points)

    def search_companies(self, query_vector: list[float], top_k: int = 5, category: Optional[str] = None) -> list[dict]:
        """
        语义检索 — 在公司知识库中查找最相关的内容块
        用于方案生成器的 RAG 检索阶段
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        client = self._get_client()
        filters = None
        if category:
            filters = Filter(must=[FieldCondition(key="category", match=MatchValue(value=category))])

        results = client.search(
            collection_name=COLLECTION,
            query_vector=query_vector,
            limit=top_k,
            query_filter=filters,
        )
        return [
            {
                "company_id": r.payload.get("company_id"),
                "text": r.payload.get("text"),
                "score": r.score,
                "metadata": {k: v for k, v in r.payload.items() if k not in ("company_id", "text")},
            }
            for r in results
        ]

    async def get_similar_company_ids(self, company_id: str, top_k: int = 3) -> list[str]:
        """
        查找与指定公司最相似的其他公司 ID（用于 similar 接口）
        通过该公司的所有向量块取均值作为查询向量
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        client = self._get_client()

        # 先获取该公司的所有向量点
        scroll_result, _ = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(must=[FieldCondition(key="company_id", match=MatchValue(value=company_id))]),
            with_vectors=True,
            limit=20,
        )
        if not scroll_result:
            return []

        # 计算向量均值
        import numpy as np
        vectors = [p.vector for p in scroll_result if p.vector]
        if not vectors:
            return []
        centroid = np.mean(vectors, axis=0).tolist()

        # 按均值向量查找最近邻
        results = client.search(
            collection_name=COLLECTION,
            query_vector=centroid,
            limit=top_k + 5,
        )
        # 去重：按 company_id 聚合，排除自身
        seen = set()
        similar = []
        for r in results:
            cid = r.payload.get("company_id")
            if cid and cid != company_id and cid not in seen:
                seen.add(cid)
                similar.append(cid)
                if len(similar) >= top_k:
                    break
        return similar

    def delete_company_vectors(self, company_id: str):
        """删除某公司的所有向量"""
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        client = self._get_client()
        client.delete(
            collection_name=COLLECTION,
            points_selector=Filter(
                must=[FieldCondition(key="company_id", match=MatchValue(value=company_id))]
            ),
        )


# 全局单例
vector_store = VectorStore()
