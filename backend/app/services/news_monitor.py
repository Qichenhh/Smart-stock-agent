"""新闻监控服务 — 定时轮询 + 新新闻检测 + 影响判断"""

import asyncio
import threading
import time
from typing import List, Dict, Set
from datetime import datetime


class NewsMonitor:
    """个股新闻监控（后台轮询）

    工作流程：
    1. 用户通过 WebSocket 订阅股票
    2. 后台每 60 秒轮询一次 akshare.stock_news_em()
    3. 对比历史，检测新出现的新闻
    4. 关键词分析影响（利好/利空/中性）
    5. 重要新闻推送给所有 WebSocket 客户端
    """

    # 利好/利空关键词
    POSITIVE_WORDS = [
        '增长', '上涨', '利好', '突破', '增持', '买入', '上升', '回暖',
        '分红', '回购', '中标', '签约', '获批', '扭亏', '预增', '超预期',
        '创新高', '新高', '盈利', '扩张', '升级', '加码', '投资',
        '收购', '重组', '合并', '涨停', '大涨', '走强', '翻红', '翻倍',
    ]
    NEGATIVE_WORDS = [
        '下跌', '亏损', '减持', '下滑', '立案', '违约', '暴雷', '退市',
        '警示', '处罚', '诉讼', '冻结', '爆仓', '预亏', '低于预期',
        '创新低', '新低', '停产', '裁员', '关闭', '计提', '减值', '担保',
        '违规', '调查', '处分', '问询', '监管', '限制',
        '跌停', '大跌', '走弱', '踩雷', '逾期', '失信', '被执行',
    ]
    HIGH_IMPACT = [
        '立案', '退市', '暴雷', '处罚', '预增', '超预期', '重大', '重组',
        '收购', '合并', '分红', '回购', '中标', '获批', '扭亏',
        '涨停', '跌停', '违约', '爆雷', '调查', '停牌', '退市',
    ]

    def __init__(self):
        self._subscribers: Dict[str, Set] = {}  # symbol -> set of ws connections
        self._seen_news: Dict[str, Set] = {}    # symbol -> set of seen titles
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._interval = 60  # 轮询间隔（秒）

    def subscribe(self, symbol: str, ws) -> bool:
        """订阅一只股票的新闻推送"""
        with self._lock:
            if symbol not in self._subscribers:
                self._subscribers[symbol] = set()
                self._seen_news[symbol] = set()
            self._subscribers[symbol].add(ws)
        self._ensure_running()
        print(f"[NewsMonitor] 订阅 {symbol} (共 {len(self._subscribers)} 只)")
        return True

    def unsubscribe(self, symbol: str, ws):
        """取消订阅"""
        with self._lock:
            if symbol in self._subscribers:
                self._subscribers[symbol].discard(ws)
                if not self._subscribers[symbol]:
                    del self._subscribers[symbol]
                    self._seen_news.pop(symbol, None)

    def _ensure_running(self):
        """确保监控线程在运行"""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._thread.start()
            print("[NewsMonitor] 监控线程已启动")

    def _poll_loop(self):
        """后台轮询循环"""
        while self._running:
            with self._lock:
                symbols = list(self._subscribers.keys())
            for sym in symbols:
                try:
                    self._check_news(sym)
                except Exception as e:
                    print(f"[NewsMonitor] {sym} 检查失败: {e}")
            time.sleep(self._interval)

    def _check_news(self, symbol: str):
        """检查某只股票的新新闻"""
        try:
            import akshare as ak
            df = ak.stock_news_em(symbol=symbol)
        except Exception:
            return

        if df is None or df.empty:
            return

        with self._lock:
            seen = self._seen_news.get(symbol, set())

        new_alerts = []
        for _, row in df.head(8).iterrows():
            title = str(row.iloc[1]) if len(row) > 1 else ""
            if not title or title in seen:
                continue

            seen.add(title)
            content = str(row.iloc[2]) if len(row) > 2 else ""
            source = str(row.iloc[4]) if len(row) > 4 else "未知来源"

            # 影响分析
            impact = self._analyze_impact(title + content)
            if impact["level"] == "low":
                continue  # 低影响不推送

            alert = {
                "symbol": symbol,
                "title": title[:100],
                "summary": content[:150] if content else title[:150],
                "source": source,
                "impact": impact["direction"],  # positive/negative/neutral
                "level": impact["level"],        # high/medium/low
                "keywords": impact["keywords"][:5],
                "time": datetime.now().strftime("%H:%M:%S"),
            }
            new_alerts.append(alert)

        with self._lock:
            self._seen_news[symbol] = seen

        # 推送给所有订阅者
        if new_alerts:
            for alert in new_alerts:
                self._broadcast(symbol, alert)

    def _analyze_impact(self, text: str) -> dict:
        """分析新闻影响（关键词匹配）"""
        pos_count = 0
        neg_count = 0
        matched = []
        weight = 1

        for w in self.POSITIVE_WORDS:
            if w in text:
                pos_count += 1
                matched.append(f"+{w}")
                if w in self.HIGH_IMPACT:
                    pos_count += 1  # 加权

        for w in self.NEGATIVE_WORDS:
            if w in text:
                neg_count += 1
                matched.append(f"-{w}")
                if w in self.HIGH_IMPACT:
                    neg_count += 1  # 加权

        if neg_count > pos_count:
            direction = "negative"
            score = neg_count
        elif pos_count > neg_count:
            direction = "positive"
            score = pos_count
        else:
            direction = "neutral"
            score = 0

        if score >= 3:
            level = "high"
        elif score >= 1:
            level = "medium"
        else:
            level = "low"

        return {
            "direction": direction,
            "level": level,
            "keywords": matched,
            "score": score,
        }

    def _broadcast(self, symbol: str, alert: dict):
        """推送预警给所有订阅该股的 WebSocket"""
        with self._lock:
            subs = list(self._subscribers.get(symbol, set()))
        dead = []
        for ws in subs:
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                loop.run_until_complete(ws.send_json({"type": "alert", **alert}))
                loop.close()
            except Exception:
                dead.append(ws)
        # 清理断开的连接
        if dead:
            for ws in dead:
                self.unsubscribe(symbol, ws)


# 全局单例
_monitor: NewsMonitor = None


def get_news_monitor() -> NewsMonitor:
    global _monitor
    if _monitor is None:
        _monitor = NewsMonitor()
    return _monitor
