"""RAG 服务 — Qdrant 本地文件 + embedding 语义检索 + TF-IDF 兜底"""

import os
import json
from typing import List, Optional
from datetime import datetime

KB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "knowledge_base")
KB_DIR = os.path.abspath(KB_DIR)
QDRANT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "qdrant_data")
QDRANT_PATH = os.path.abspath(QDRANT_PATH)

_client = None      # QdrantClient
_embedder = None    # SentenceTransformer
_ready = False
_collection = "stock_knowledge"     # RAG 知识库
_mem_collection = "stock_memory"    # 语义记忆
_vector_size = 384


def _ensure_qdrant():
    """延迟初始化 Qdrant + embedding"""
    global _client, _embedder, _ready
    if _ready:
        return

    # 1. Qdrant 本地文件模式
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        os.makedirs(QDRANT_PATH, exist_ok=True)
        _client = QdrantClient(path=QDRANT_PATH)

        # 创建知识库集合
        if not _client.collection_exists(_collection):
            _client.create_collection(
                collection_name=_collection,
                vectors_config=VectorParams(size=_vector_size, distance=Distance.COSINE),
            )
        # 创建语义记忆集合
        if not _client.collection_exists(_mem_collection):
            _client.create_collection(
                collection_name=_mem_collection,
                vectors_config=VectorParams(size=_vector_size, distance=Distance.COSINE),
            )
            print(f"[RAG] Qdrant 集合已就绪: knowledge + memory")
    except Exception as e:
        print(f"[RAG] Qdrant 初始化失败: {e}")
        _client = None

    # 2. Embedding 模型
    try:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer('all-MiniLM-L6-v2')
        print(f"[RAG] embedding 模型就绪: {_vector_size}维")
    except Exception as e:
        print(f"[RAG] embedding 初始化失败: {e}")
        _embedder = None

    # 3. 加载知识文件入库
    if _client and _embedder:
        _load_knowledge()
    elif not _client:
        print("[RAG] Qdrant 不可用，回退到 TF-IDF")
        _init_tfidf()

    _ready = True


def _load_knowledge():
    """加载知识文件 → 分块 → embedding → Qdrant"""
    info = _client.get_collection(_collection)
    if info.points_count > 0:
        print(f"[RAG] 知识库已有 {info.points_count} 个向量，跳过加载")
        return

    if not os.path.isdir(KB_DIR):
        return

    all_chunks = []
    for fname in os.listdir(KB_DIR):
        if not (fname.endswith('.txt') or fname.endswith('.md')):
            continue
        fpath = os.path.join(KB_DIR, fname)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                text = f.read().strip()
            if not text:
                continue
            ns = _namespace(fname)
            chunks = _split_chunks(text, max_chars=400)
            for i, chunk in enumerate(chunks):
                all_chunks.append({
                    "text": chunk,
                    "source": f"{fname}#{i}",
                    "namespace": ns,
                })
        except Exception as e:
            print(f"[RAG] 加载失败 {fname}: {e}")

    if not all_chunks:
        return

    # 批量 embedding + upsert
    texts = [c["text"] for c in all_chunks]
    print(f"[RAG] 正在向量化 {len(texts)} 个文本块...")

    try:
        from qdrant_client.models import PointStruct
        embeddings = _embedder.encode(texts, show_progress_bar=False)

        points = []
        for idx, chunk in enumerate(all_chunks):
            points.append(PointStruct(
                id=idx,
                vector=embeddings[idx].tolist(),
                payload={
                    "text": chunk["text"],
                    "source": chunk["source"],
                    "namespace": chunk["namespace"],
                }
            ))

        _client.upsert(collection_name=_collection, points=points, wait=True)
        print(f"[RAG] 知识库初始化完成: {len(points)} 个向量")

    except Exception as e:
        print(f"[RAG] 向量化失败: {e}")
        _init_tfidf()  # 回退


# ──────────── TF-IDF 回退 ────────────

_tfidf_vectorizer = None
_tfidf_matrix = None
_tfidf_docs = []


def _init_tfidf():
    """构建 TF-IDF 索引（Qdrant 不可用时的兜底）"""
    global _tfidf_vectorizer, _tfidf_matrix, _tfidf_docs
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        texts = []
        _tfidf_docs = []
        for fname in os.listdir(KB_DIR):
            if fname.endswith('.txt') or fname.endswith('.md'):
                with open(os.path.join(KB_DIR, fname), 'r', encoding='utf-8') as f:
                    text = f.read().strip()
                if text:
                    for chunk in _split_chunks(text, 400):
                        _tfidf_docs.append({"text": chunk, "source": fname})
                        texts.append(chunk)
        if texts:
            _tfidf_vectorizer = TfidfVectorizer(max_features=500)
            _tfidf_matrix = _tfidf_vectorizer.fit_transform(texts)
            print(f"[RAG] TF-IDF 回退就绪: {len(texts)} 个文本块")
    except Exception as e:
        print(f"[RAG] TF-IDF 初始化失败: {e}")


# ──────────── 工具函数 ────────────

def _split_chunks(text: str, max_chars: int = 400) -> List[str]:
    paragraphs = text.split('\n\n')
    chunks, current = [], ""
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if p.startswith('#') and len(p) < 80:
            current += p + " "
            continue
        if len(current) + len(p) > max_chars:
            if current:
                chunks.append(current.strip())
            current = p
        else:
            current += " " + p
    if current:
        chunks.append(current.strip())
    return chunks if chunks else [text[:max_chars]]


def _namespace(filename: str) -> str:
    n = filename.lower()
    if any(k in n for k in ['valuation', 'industry', 'bank']):
        return 'industry'
    if any(k in n for k in ['technical', 'indicator', 'rule']):
        return 'rules'
    return 'principles'


# ──────────── 公共 API ────────────

def search(query: str, top_k: int = 3, max_chars: int = 800, namespace: str = None) -> str:
    """语义搜索知识库 → 格式化文本"""
    _ensure_qdrant()

    results = []
    # 1. Qdrant 语义搜索
    if _client and _embedder:
        try:
            query_vec = _embedder.encode(query).tolist()
            search_result = _client.query_points(
                collection_name=_collection,
                query=query_vec,
                limit=top_k,
            )
            for r in search_result.points:
                ns = r.payload.get("namespace", "")
                if namespace and ns != namespace:
                    continue
                results.append({
                    "text": r.payload["text"],
                    "source": r.payload.get("source", ""),
                    "namespace": ns,
                    "score": round(r.score, 3),
                })
        except Exception as e:
            print(f"[RAG] Qdrant 搜索失败: {e}")

    # 2. TF-IDF 兜底
    if not results and _tfidf_vectorizer is not None:
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            qv = _tfidf_vectorizer.transform([query])
            scores = cosine_similarity(qv, _tfidf_matrix).flatten()
            indices = scores.argsort()[-top_k:][::-1]
            for idx in indices:
                if scores[idx] > 0.01:
                    results.append({
                        "text": _tfidf_docs[idx]["text"][:300],
                        "source": _tfidf_docs[idx]["source"],
                        "namespace": "",
                        "score": round(float(scores[idx]), 3),
                    })
        except Exception:
            pass

    if not results:
        return ""

    lines = ["相关知识库内容："]
    for r in results[:top_k]:
        text = r["text"]
        if len(text) > max_chars // top_k:
            text = text[:max_chars // top_k] + "..."
        lines.append(f"[{r['namespace']}] {text}")
    return "\n".join(lines)


def is_ready() -> bool:
    _ensure_qdrant()
    return _client is not None or _tfidf_vectorizer is not None


def add_knowledge(text: str, namespace: str = "api"):
    """动态添加知识（需要 Qdrant）"""
    _ensure_qdrant()
    if not _client or not _embedder:
        return

    try:
        from qdrant_client.models import PointStruct
        vec = _embedder.encode(text).tolist()
        pid = _client.count(_collection).count
        _client.upsert(_collection, points=[PointStruct(
            id=pid, vector=vec,
            payload={"text": text[:1000], "source": f"api@{datetime.now().isoformat()}", "namespace": namespace}
        )], wait=True)
        print(f"[RAG] 已添加知识: {namespace}")
    except Exception as e:
        print(f"[RAG] 添加失败: {e}")


def get_stats() -> dict:
    _ensure_qdrant()
    stats = {"ready": is_ready(), "kb_path": KB_DIR}
    if _client:
        info = _client.get_collection(_collection)
        mem_info = _client.get_collection(_mem_collection)
        stats["backend"] = "Qdrant"
        stats["kb_vectors"] = info.points_count
        stats["mem_vectors"] = mem_info.points_count
        stats["storage"] = QDRANT_PATH
    elif _tfidf_vectorizer:
        stats["backend"] = "TF-IDF"
        stats["chunks"] = len(_tfidf_docs)
    return stats


# ──────────── 语义记忆 ────────────

def memory_store(symbol: str, title: str, content: str, summary: str = "",
                 rating: str = "", tags: str = "", importance: float = 0.5):
    """将分析报告全文存入语义记忆"""
    _ensure_qdrant()
    if not _client or not _embedder:
        print("[RAG] 语义记忆不可用（Qdrant 或 embedding 未就绪）")
        return

    try:
        from qdrant_client.models import PointStruct
        vec = _embedder.encode(content[:2000]).tolist()
        pid = _client.count(_mem_collection).count
        _client.upsert(_mem_collection, points=[PointStruct(
            id=pid,
            vector=vec,
            payload={
                "type": "report",
                "symbol": symbol,
                "title": title,
                "content": content[:3000],
                "summary": summary[:200],
                "rating": rating,
                "tags": tags,
                "importance": importance,
                "stored_at": datetime.now().isoformat(),
            }
        )], wait=True)
    except Exception as e:
        print(f"[RAG] 语义记忆存储失败: {e}")


def memory_search(symbol: str, query: str = "", top_k: int = 3,
                  max_chars: int = 600) -> str:
    """语义检索历史分析报告"""
    _ensure_qdrant()
    if not _client or not _embedder:
        return ""

    try:
        search_text = f"{symbol} {query}"
        vec = _embedder.encode(search_text).tolist()
        results = _client.query_points(
            collection_name=_mem_collection,
            query=vec,
            limit=top_k,
        )

        if not results.points:
            return ""

        lines = ["历史分析洞察（语义检索）:"]
        for r in results.points:
            p = r.payload
            sym = p.get("symbol", "")
            title = p.get("title", "")
            summary = p.get("summary", "")[:150]
            rating = p.get("rating", "")
            lines.append(f"- [{sym}] {title} | 评级={rating} | {summary}")

        return "\n".join(lines)

    except Exception as e:
        print(f"[RAG] 语义记忆搜索失败: {e}")
        return ""
