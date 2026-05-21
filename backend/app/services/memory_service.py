"""记忆服务 — 轻量文件存储，不依赖 Qdrant/嵌入模型"""

import json
import os
import threading
from typing import List, Optional
from datetime import datetime


MEMORY_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "memory_data")
MEMORY_FILE = os.path.join(MEMORY_DIR, "analysis_history.json")
_lock = threading.Lock()


def _ensure_dir():
    os.makedirs(MEMORY_DIR, exist_ok=True)


def _read_all() -> List[dict]:
    _ensure_dir()
    if not os.path.exists(MEMORY_FILE):
        return []
    try:
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _write_all(records: List[dict]):
    _ensure_dir()
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def record_analysis(symbol: str, company_name: str, summary: str,
                    tech_score: int, fund_score: int, senti_score: int,
                    rating: str):
    """记录一次分析到本地 JSON 文件"""
    with _lock:
        records = _read_all()
        records.append({
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "company_name": company_name,
            "summary": summary[:200],
            "tech_score": tech_score,
            "fund_score": fund_score,
            "senti_score": senti_score,
            "rating": rating,
        })
        # 只保留最近 50 条
        if len(records) > 50:
            records = records[-50:]
        _write_all(records)


def get_context(symbol: str, limit: int = 3) -> str:
    """检索该股票的历史分析记录"""
    records = _read_all()
    if not records:
        return ""

    # 筛选该股票 + 最近的记录
    matching = [r for r in records if r.get("symbol") == symbol]
    recent = matching[-limit:]

    if not recent:
        return ""

    lines = [f"历史分析记录 ({symbol}):"]
    for r in recent:
        lines.append(
            f"- {r['timestamp'][:10]}: 技术面{r['tech_score']}, "
            f"基本面{r['fund_score']}, 情绪面{r['senti_score']}, "
            f"评级={r['rating']}. {r['summary'][:80]}"
        )
    return "\n".join(lines)


def get_recent_analyses(limit: int = 10) -> List[dict]:
    """获取最近的分析列表（供前端展示）"""
    records = _read_all()
    return records[-limit:][::-1]  # 最新的在前
