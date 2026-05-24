"""Memory 服务 — SQLite 结构化存储 + 重要性打分 + 衰减 + 去重"""

import sqlite3
import os
import re
import json
import threading
from typing import List, Dict, Optional
from datetime import datetime, timedelta


MEMORY_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "memory_data")
DB_PATH = os.path.join(MEMORY_DIR, "memory.db")
_lock = threading.Lock()
_MAX_ANALYSIS = 50
_PREFERENCE_PATTERNS = [
    (r'北向|外资|北上', '关注北向/外资资金'),
    (r'主力|资金流向|大单', '关注主力资金流向'),
    (r'分红|股息', '关注分红/股息'),
    (r'估值|PE|PB|破净', '关注估值指标'),
    (r'ROE|盈利|利润', '关注盈利能力'),
    (r'技术|MACD|均线|KDJ|RSI', '关注技术指标'),
    (r'短线|日内|T\+0', '短线交易风格'),
    (r'长线|长期|持有', '长线投资风格'),
    (r'银行|金融', '偏好金融板块'),
    (r'消费|白酒|食品', '偏好消费板块'),
    (r'科技|芯片|AI|半导体', '偏好科技板块'),
    (r'对比|比较|哪个', '偏好对比分析'),
    (r'风险|止损|仓位', '重视风险管理'),
]


def _connect() -> sqlite3.Connection:
    os.makedirs(MEMORY_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    schema = os.path.join(os.path.dirname(__file__), "memory_schema.sql")
    if os.path.exists(schema):
        with open(schema, 'r', encoding='utf-8') as f:
            sql = f.read()
        conn = _connect()
        conn.executescript(sql)
        conn.commit()
        conn.close()


# 启动时自动建表
_init_db()


# ──────────── 分析历史 ────────────

def record_analysis(symbol: str, company_name: str, summary: str,
                    tech_score: int, fund_score: int, senti_score: int,
                    rating: str, free_text: str = "", report_json: str = ""):
    """记录一次分析 → analysis_history 表"""
    total = round(tech_score * 0.4 + fund_score * 0.35 + senti_score * 0.25)
    importance = _calculate_importance(tech_score, fund_score, senti_score, rating, summary)

    with _lock:
        conn = _connect()
        now = datetime.now().isoformat()

        # 24h 去重：同股票同天覆盖
        today = datetime.now().strftime("%Y-%m-%d")
        existing = conn.execute(
            "SELECT id, merged_count FROM analysis_history WHERE symbol=? AND analyzed_at LIKE ? ORDER BY analyzed_at DESC LIMIT 1",
            (symbol, today + "%")
        ).fetchone()

        if existing:
            new_count = existing["merged_count"] + 1
            conn.execute(
                """UPDATE analysis_history SET
                    name=?, analyzed_at=?, rating=?, tech_score=?, fund_score=?,
                    senti_score=?, total_score=?, summary=?, importance=?, merged_count=?
                    WHERE id=?""",
                (company_name, now, rating, tech_score, fund_score, senti_score,
                 total, summary[:200], importance, new_count, existing["id"])
            )
        else:
            conn.execute(
                """INSERT INTO analysis_history
                    (symbol, name, analyzed_at, rating, tech_score, fund_score,
                     senti_score, total_score, summary, importance)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (symbol, company_name, now, rating, tech_score, fund_score,
                 senti_score, total, summary[:200], importance)
            )

        # 清理：总量控制 + 衰减删除
        _prune_old(conn)
        conn.commit()
        conn.close()

    # 提取偏好
    if free_text:
        _extract_preferences(free_text)


def _calculate_importance(tech: int, fund: int, senti: int, rating: str, summary: str) -> float:
    score = 0.5
    # 三维一致性
    variance = max(tech, fund, senti) - min(tech, fund, senti)
    if variance < 15:
        score += 0.2
    elif variance > 40:
        score -= 0.2
    # 摘要完整
    if len(summary) > 80:
        score += 0.15
    # 非兜底
    if "兜底" in summary or "数据获取失败" in summary:
        score -= 0.3
    # 结论明确
    if rating in ("买入", "卖出"):
        score += 0.1
    return max(0.05, min(1.0, round(score, 2)))


def _prune_old(conn: sqlite3.Connection):
    """删除低重要性 + 超出数量上限的记录"""
    # 衰减标记：30天前重要性打折
    cutoff_30 = (datetime.now() - timedelta(days=30)).isoformat()
    conn.execute(
        "UPDATE analysis_history SET importance = importance * 0.3 WHERE analyzed_at < ?",
        (cutoff_30,)
    )
    cutoff_7 = (datetime.now() - timedelta(days=7)).isoformat()
    conn.execute(
        "UPDATE analysis_history SET importance = importance * 0.7 WHERE analyzed_at < ? AND importance >= 0.4",
        (cutoff_7,)
    )
    # 删除低于阈值
    conn.execute("DELETE FROM analysis_history WHERE importance < 0.2")
    # 超出上限时删最旧
    count = conn.execute("SELECT COUNT(*) as cnt FROM analysis_history").fetchone()["cnt"]
    if count > _MAX_ANALYSIS:
        excess = count - _MAX_ANALYSIS
        conn.execute(
            "DELETE FROM analysis_history WHERE id IN (SELECT id FROM analysis_history ORDER BY importance ASC, analyzed_at ASC LIMIT ?)",
            (excess,)
        )


def get_context(symbol: str, limit: int = 3) -> str:
    """召回历史分析摘要"""
    conn = _connect()
    rows = conn.execute(
        """SELECT * FROM analysis_history WHERE symbol=?
           ORDER BY importance DESC, analyzed_at DESC LIMIT ?""",
        (symbol, limit)
    ).fetchall()
    conn.close()

    if not rows:
        return ""

    lines = [f"分析历史 ({symbol}):"]
    for r in rows:
        imp = r["importance"]
        quality = "高" if imp > 0.7 else "中" if imp > 0.4 else "低"
        merged = f" (合并{r['merged_count']}次)" if r["merged_count"] > 1 else ""
        try:
            ts = datetime.fromisoformat(r["analyzed_at"])
            age = (datetime.now() - ts).days
        except (ValueError, TypeError):
            age = 99
        lines.append(
            f"- [{quality}|{age}d前{merged}] 技术面{r['tech_score']} "
            f"基本面{r['fund_score']} 情绪面{r['senti_score']} 评级={r['rating']}"
        )
    return "\n".join(lines)


def get_history(symbol: str = None) -> List[dict]:
    conn = _connect()
    if symbol:
        rows = conn.execute(
            "SELECT * FROM analysis_history WHERE symbol=? ORDER BY analyzed_at DESC LIMIT 20",
            (symbol,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM analysis_history ORDER BY analyzed_at DESC LIMIT 20"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_trend(symbol: str) -> dict:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM analysis_history WHERE symbol=? ORDER BY analyzed_at DESC LIMIT 5",
        (symbol,)
    ).fetchall()
    conn.close()
    if len(rows) < 2:
        return {"count": len(rows), "trend": "insufficient_data"}

    scores = [(r["tech_score"] + r["fund_score"] + r["senti_score"]) / 3 for r in rows[::-1]]
    trend = "up" if scores[-1] > scores[0] + 3 else "down" if scores[-1] < scores[0] - 3 else "stable"
    return {
        "count": len(rows),
        "trend": trend,
        "avg_tech": round(sum(r["tech_score"] for r in rows) / len(rows), 1),
        "avg_fund": round(sum(r["fund_score"] for r in rows) / len(rows), 1),
        "avg_senti": round(sum(r["senti_score"] for r in rows) / len(rows), 1),
    }


# ──────────── 用户偏好 ────────────

def _extract_preferences(free_text: str):
    conn = _connect()
    now = datetime.now().isoformat()
    for pattern, label in _PREFERENCE_PATTERNS:
        if re.search(pattern, free_text):
            existing = conn.execute(
                "SELECT id, weight, confidence FROM user_preferences WHERE category='interest' AND value=?",
                (label,)
            ).fetchone()
            if existing:
                new_weight = min(1.0, existing["weight"] + 0.15)
                new_conf = min(0.95, existing["confidence"] + 0.1)
                conn.execute(
                    "UPDATE user_preferences SET weight=?, confidence=?, last_updated=? WHERE id=?",
                    (new_weight, new_conf, now, existing["id"])
                )
            else:
                conn.execute(
                    "INSERT INTO user_preferences (category, value, weight, confidence, last_updated) VALUES (?,?,?,?,?)",
                    ("interest", label, 0.3, 0.4, now)
                )
    conn.commit()
    conn.close()


def get_user_preferences() -> Dict[str, float]:
    conn = _connect()
    rows = conn.execute(
        "SELECT value, weight FROM user_preferences WHERE category='interest' AND confidence > 0.3 ORDER BY weight DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return {r["value"]: round(r["weight"], 2) for r in rows}


def get_preferences_text() -> str:
    prefs = get_user_preferences()
    if not prefs:
        return ""
    top = list(prefs.items())[:5]
    return "用户偏好: " + ", ".join(f"{k}({v:.1f})" for k, v in top)


# ──────────── 自选股 ────────────

def add_watch(symbol: str, name: str = "", reason: str = "", tags: str = "", notes: str = ""):
    conn = _connect()
    now = datetime.now().isoformat()
    existing = conn.execute("SELECT id FROM watchlist WHERE symbol=?", (symbol,)).fetchone()
    if existing:
        conn.execute(
            "UPDATE watchlist SET name=?, reason=?, tags=?, notes=?, last_viewed_at=? WHERE symbol=?",
            (name, reason, tags, notes, now, symbol)
        )
    else:
        conn.execute(
            "INSERT INTO watchlist (symbol, name, reason, tags, notes, added_at) VALUES (?,?,?,?,?,?)",
            (symbol, name, reason, tags, notes, now)
        )
    conn.commit()
    conn.close()


def remove_watch(symbol: str):
    conn = _connect()
    conn.execute("DELETE FROM watchlist WHERE symbol=?", (symbol,))
    conn.commit()
    conn.close()


def get_watchlist() -> List[dict]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM watchlist ORDER BY added_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]
