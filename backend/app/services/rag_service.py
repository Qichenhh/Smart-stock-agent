"""RAG 服务 — 金融知识库检索增强生成（RAGTool 单例）"""

import os
from typing import Optional
from hello_agents.tools import RAGTool


_rag_tool: Optional[RAGTool] = None
_rag_ready: bool = False


def get_rag_tool() -> Optional[RAGTool]:
    """获取 RAG 工具单例（首次调用时初始化并加载知识库）"""
    global _rag_tool, _rag_ready
    if _rag_tool is None:
        try:
            # 知识库路径（相对于 run.py 的工作目录，即 backend/）
            kb_path = os.path.join(os.path.dirname(__file__), "..", "..", "knowledge_base")
            kb_path = os.path.abspath(kb_path)

            _rag_tool = RAGTool(
                knowledge_base_path=kb_path,
                rag_namespace="stock",
                expandable=True  # 展开为 rag_search/rag_add_text 等子工具
            )

            # 初始化完成后自动加载预置知识
            _load_knowledge(_rag_tool)
            _rag_ready = True
            print(f"[RAG] 知识库初始化成功: {kb_path}")

        except Exception as e:
            print(f"[RAG] 初始化失败(非关键): {e}")
            _rag_tool = None
            _rag_ready = False
    return _rag_tool


def _load_knowledge(rag: RAGTool):
    """加载预置金融知识到知识库"""
    kb_dir = rag.knowledge_base_path
    if not os.path.isdir(kb_dir):
        return

    loaded = 0
    for fname in os.listdir(kb_dir):
        if fname.endswith('.txt') or fname.endswith('.md'):
            fpath = os.path.join(kb_dir, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    text = f.read().strip()
                if text:
                    ns = _get_namespace(fname)
                    rag.add_text(text, namespace=ns)
                    loaded += 1
                    print(f"  [RAG] 已加载: {fname} → namespace={ns}")
            except Exception as e:
                print(f"  [RAG] 加载失败 {fname}: {e}")

    if loaded:
        print(f"[RAG] 共加载 {loaded} 个知识文件")


def _get_namespace(filename: str) -> str:
    """根据文件名自动分配命名空间"""
    name = filename.lower()
    if 'bank' in name or 'valuation' in name or 'industry' in name:
        return 'industry'
    if 'technical' in name or 'indicator' in name or 'rule' in name:
        return 'rules'
    if 'market' in name or 'news' in name or 'review' in name:
        return 'market'
    return 'default'


def search_knowledge(query: str, namespace: str = "industry",
                     limit: int = 3, max_chars: int = 800) -> str:
    """检索金融知识库"""
    tool = get_rag_tool()
    if not tool:
        return ""
    try:
        return tool.get_relevant_context(
            query=query, limit=limit,
            max_chars=max_chars, namespace=namespace
        )
    except Exception:
        return ""


def is_ready() -> bool:
    """RAG 服务是否就绪"""
    return _rag_ready
