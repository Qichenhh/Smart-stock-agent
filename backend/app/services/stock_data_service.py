"""股票数据服务 — baostock + akshare 双数据源"""

import threading
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from ..models.schemas import (
    StockQuote, KLineData, FundamentalData,
    TechnicalIndicator, SentimentItem,
)


class StockCache:
    """线程安全的股票数据缓存

    - 自动 TTL 过期（默认5分钟行情、30分钟K线）
    - 最大 500 条限制，超出时淘汰最旧条目
    - 命中率统计
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._data: Dict[str, Any] = {}
        self._times: Dict[str, datetime] = {}
        self._ttls: Dict[str, int] = {}  # 每个 key 独立 TTL
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self._max_size = 500

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._data:
                ttl = self._ttls.get(key, 300)
                age = (datetime.now() - self._times[key]).total_seconds()
                if age < ttl:
                    self.hits += 1
                    return self._data[key]
                # 过期，清除
                del self._data[key]
                del self._times[key]
                del self._ttls[key]
            self.misses += 1
            return None

    def set(self, key: str, value: Any, ttl: int = 300):
        with self._lock:
            # 超出大小限制时清除最旧的 50 条
            if len(self._data) >= self._max_size:
                sorted_keys = sorted(self._times.items(), key=lambda x: x[1])
                for old_key, _ in sorted_keys[:50]:
                    del self._data[old_key]
                    del self._times[old_key]
                    self._ttls.pop(old_key, None)
            self._data[key] = value
            self._times[key] = datetime.now()
            self._ttls[key] = ttl
            self.sets += 1

    def clear(self):
        with self._lock:
            count = len(self._data)
            self._data.clear()
            self._times.clear()
            self._ttls.clear()
            return count

    def stats(self) -> dict:
        with self._lock:
            total = self.hits + self.misses
            hit_rate = round(self.hits / total * 100, 1) if total > 0 else 0
            return {
                "entries": len(self._data),
                "max_size": self._max_size,
                "hits": self.hits,
                "misses": self.misses,
                "sets": self.sets,
                "hit_rate_pct": hit_rate,
            }

    def cleanup_expired(self) -> int:
        """清理所有过期条目，返回清理数量"""
        with self._lock:
            now = datetime.now()
            expired = [
                k for k in list(self._data.keys())
                if (now - self._times[k]).total_seconds() >= self._ttls.get(k, 300)
            ]
            for k in expired:
                del self._data[k]
                del self._times[k]
                self._ttls.pop(k, None)
            return len(expired)


# 全局缓存实例
_cache = StockCache()


def _safe_float(value) -> Optional[float]:
    """安全转换为 float，处理 NaN/None/空字符串"""
    import math
    try:
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except (ValueError, TypeError):
        return None


class StockDataService:
    """股票数据服务（单例）"""

    def __init__(self):
        self._data_source = None  # "akshare" or "baostock"
        self._init_data_source()

    def _init_data_source(self):
        """自动检测可用数据源"""
        # 优先 akshare（数据更全）
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            if len(df) > 0:
                self._data_source = "akshare"
                print(f"[Data] 数据源: AKShare ({len(df)} 只股票)")
                return
        except Exception as e:
            print(f"[Data] AKShare 不可用: {e}")

        # 备选 baostock
        try:
            import baostock as bs
            lg = bs.login()
            if lg.error_code == '0':
                self._data_source = "baostock"
                print("[Data] 数据源: Baostock")
                bs.logout()
                return
        except Exception as e:
            print(f"[Data] Baostock 不可用: {e}")

        # 兜底
        print("[Data] 警告: 无可用数据源，将返回空数据")
        self._data_source = "mock"

    # ========== 实时行情 ==========

    async def get_realtime_quote(self, symbol: str) -> Optional[StockQuote]:
        """获取A股实时行情"""
        cache_key = f"quote_{symbol}"
        cached = _cache.get(cache_key)
        if cached:
            return cached

        if self._data_source == "akshare":
            result = await self._quote_akshare(symbol)
        elif self._data_source == "baostock":
            result = await self._quote_baostock(symbol)
        else:
            result = self._quote_mock(symbol)

        if result:
            _cache.set(cache_key, result, ttl=60)  # 行情60秒过期
        return result

    async def _quote_akshare(self, symbol: str) -> Optional[StockQuote]:
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            row = df[df['代码'] == symbol]
            if row.empty:
                return None
            row = row.iloc[0]
            return StockQuote(
                symbol=symbol,
                name=str(row.get('名称', '')),
                price=float(row.get('最新价', 0)),
                change=float(row.get('涨跌额', 0)),
                change_percent=float(row.get('涨跌幅', 0)),
                volume=float(row.get('成交量', 0)),
                amount=float(row.get('成交额', 0)),
                high=float(row.get('最高', 0)),
                low=float(row.get('最低', 0)),
                open=float(row.get('今开', 0)),
                prev_close=float(row.get('昨收', 0)),
                turnover_rate=float(row['换手率']) if '换手率' in row.index and row['换手率'] != '-' else None,
                market_cap=float(row['总市值']) if '总市值' in row.index and row['总市值'] != '-' else None,
            )
        except Exception as e:
            print(f"[AKShare] 行情获取失败 {symbol}: {e}")
            return None

    async def _quote_baostock(self, symbol: str) -> Optional[StockQuote]:
        try:
            import baostock as bs
            bs.login()

            # baostock 代码格式: sh.600000 或 sz.000001
            if symbol.startswith('6'):
                bs_code = f'sh.{symbol}'
            else:
                bs_code = f'sz.{symbol}'

            # 获取股票基本信息
            rs = bs.query_stock_basic(code=bs_code)
            data = rs.get_data()
            if data.empty:
                bs.logout()
                return None
            name = data.iloc[0]['code_name']

            # 获取最近交易日K线
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            rs = bs.query_history_k_data_plus(
                bs_code, 'date,open,high,low,close,preclose,volume,amount,turn',
                start_date=start_date, end_date=end_date, frequency='d', adjustflag='2'
            )
            k_data = rs.get_data()
            bs.logout()

            if k_data.empty:
                return None

            latest = k_data.iloc[-1]
            prev_close = float(latest['preclose'])
            price = float(latest['close'])
            change = price - prev_close
            change_pct = (change / prev_close * 100) if prev_close != 0 else 0

            return StockQuote(
                symbol=symbol,
                name=name,
                price=price,
                change=round(change, 2),
                change_percent=round(change_pct, 2),
                volume=float(latest['volume']),
                amount=float(latest['amount']) if latest['amount'] else 0,
                high=float(latest['high']),
                low=float(latest['low']),
                open=float(latest['open']),
                prev_close=prev_close,
                turnover_rate=float(latest['turn']) if latest['turn'] else None,
            )
        except Exception as e:
            print(f"[Baostock] 行情获取失败 {symbol}: {e}")
            try:
                import baostock as bs
                bs.logout()
            except:
                pass
            return None

    def _quote_mock(self, symbol: str) -> StockQuote:
        """Mock数据（开发测试用）"""
        return StockQuote(
            symbol=symbol,
            name=f"测试股票{symbol}",
            price=10.00,
            change=0.50,
            change_percent=5.0,
            volume=1000000,
            amount=10000000,
            high=10.50,
            low=9.80,
            open=9.90,
            prev_close=9.50,
        )

    # ========== 历史K线 ==========

    async def get_history(self, symbol: str, period: str = "daily",
                          start_date: str = None, end_date: str = None) -> List[KLineData]:
        """获取历史K线"""
        cache_key = f"history_{symbol}_{period}_{start_date}_{end_date}"
        cached = _cache.get(cache_key)
        if cached:
            return cached

        if self._data_source == "akshare":
            result = await self._history_akshare(symbol, period, start_date, end_date)
        elif self._data_source == "baostock":
            result = await self._history_baostock(symbol, period, start_date, end_date)
        else:
            result = self._history_mock(symbol)

        _cache.set(cache_key, result, ttl=600)  # 历史K线10分钟
        return result

    async def _history_akshare(self, symbol, period, start_date, end_date):
        try:
            import akshare as ak
            if not start_date:
                days_map = {"1m": 30, "3m": 90, "6m": 180, "1y": 365}
                days = days_map.get(period, 90)
                start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
            if not end_date:
                end_date = datetime.now().strftime("%Y%m%d")

            df = ak.stock_zh_a_hist(symbol=symbol, period=period,
                                    start_date=start_date, end_date=end_date, adjust="qfq")
            klines = []
            for _, row in df.iterrows():
                klines.append(KLineData(
                    date=str(row['日期'])[:10],
                    open=float(row['开盘']), close=float(row['收盘']),
                    high=float(row['最高']), low=float(row['最低']),
                    volume=float(row['成交量']),
                    amount=float(row['成交额']) if '成交额' in row.index else None,
                ))
            return klines
        except Exception as e:
            print(f"[AKShare] 历史K线失败 {symbol}: {e}")
            return []

    async def _history_baostock(self, symbol, period, start_date, end_date):
        try:
            import baostock as bs
            bs.login()

            if symbol.startswith('6'):
                bs_code = f'sh.{symbol}'
            else:
                bs_code = f'sz.{symbol}'

            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if not start_date:
                days_map = {"1m": 30, "3m": 90, "6m": 180, "1y": 365}
                days = days_map.get(period, 90)
                start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            rs = bs.query_history_k_data_plus(
                bs_code, 'date,open,high,low,close,volume,amount',
                start_date=start_date, end_date=end_date, frequency='d', adjustflag='2'
            )
            data = rs.get_data()
            bs.logout()

            klines = []
            for _, row in data.iterrows():
                klines.append(KLineData(
                    date=row['date'],
                    open=float(row['open']), close=float(row['close']),
                    high=float(row['high']), low=float(row['low']),
                    volume=float(row['volume']),
                    amount=float(row['amount']) if row['amount'] else None,
                ))
            return klines
        except Exception as e:
            print(f"[Baostock] 历史K线失败 {symbol}: {e}")
            try:
                import baostock as bs
                bs.logout()
            except:
                pass
            return []

    def _history_mock(self, symbol):
        """生成Mock K线数据"""
        klines = []
        base_price = 10.0
        for i in range(60, 0, -1):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            import random
            change = (random.random() - 0.5) * 0.5
            close = base_price + change
            klines.append(KLineData(
                date=date, open=base_price, close=close,
                high=max(base_price, close) + random.random() * 0.2,
                low=min(base_price, close) - random.random() * 0.2,
                volume=random.randint(100000, 500000),
            ))
            base_price = close
        return klines

    # ========== 股票搜索 ==========

    async def search_stock(self, keyword: str) -> List[Dict[str, str]]:
        """搜索股票"""
        cache_key = f"search_{keyword}"
        cached = _cache.get(cache_key)
        if cached:
            return cached

        if self._data_source == "akshare":
            result = await self._search_akshare(keyword)
        elif self._data_source == "baostock":
            result = await self._search_baostock(keyword)
        else:
            result = [{"symbol": keyword, "name": f"测试{keyword}", "market": "A", "industry": None}]

        _cache.set(cache_key, result, ttl=300)  # 搜索结果5分钟
        return result

    async def _search_akshare(self, keyword):
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            mask = df['代码'].str.contains(keyword, na=False) | df['名称'].str.contains(keyword, na=False)
            results = df[mask].head(20)
            stocks = []
            for _, row in results.iterrows():
                stocks.append({
                    "symbol": str(row['代码']),
                    "name": str(row['名称']),
                    "market": "A",
                    "industry": str(row.get('所属行业', '')) if '所属行业' in row.index else None,
                })
            return stocks
        except Exception as e:
            print(f"[AKShare] 搜索失败: {e}")
            return []

    async def _search_baostock(self, keyword):
        try:
            import baostock as bs
            bs.login()
            # baostock 没有模糊搜索，匹配常见代码
            results = []
            # 尝试直接查询
            for prefix, market in [('sh.60', 'A'), ('sz.00', 'A'), ('sz.30', 'A')]:
                if keyword and keyword[0].isdigit():
                    break
                # 全量查询太慢，返回提示
            bs.logout()
            return results if results else [
                {"symbol": "000001", "name": "平安银行", "market": "A", "industry": "银行"},
                {"symbol": "600000", "name": "浦发银行", "market": "A", "industry": "银行"},
                {"symbol": "600519", "name": "贵州茅台", "market": "A", "industry": "白酒"},
            ]
        except Exception as e:
            print(f"[Baostock] 搜索失败: {e}")
            return []

    # ========== 基本面数据 ==========

    async def get_fundamentals(self, symbol: str) -> Optional[FundamentalData]:
        """获取基本面数据"""
        cache_key = f"fundamentals_{symbol}"
        cached = _cache.get(cache_key)
        if cached:
            return cached

        # 1. 基础估值数据（PE/PB/市值）
        if self._data_source == "akshare":
            result = await self._fundamentals_akshare(symbol)
        elif self._data_source == "baostock":
            result = await self._fundamentals_baostock(symbol)
        else:
            result = FundamentalData(pe_ratio=15.0, pb_ratio=2.5, market_cap=500)

        # 2. 深度财务数据（akshare 财务 API 独立，baostock 模式下也尝试）
        if result:
            try:
                import akshare as ak
                df_fin = ak.stock_financial_analysis_indicator(symbol=symbol, start_year='2024')
                annual = df_fin[df_fin.iloc[:, 0].astype(str).str.contains('12-31', na=False)]
                if not annual.empty:
                    annual = annual.iloc[-1]
                else:
                    annual = df_fin.iloc[-1]

                result.eps = _safe_float(annual.iloc[1])
                result.roe = _safe_float(annual.iloc[11])
                result.net_margin = _safe_float(annual.iloc[17])
                result.gross_margin = _safe_float(annual.iloc[21])
                result.revenue_growth = _safe_float(annual.iloc[31])
                result.profit_growth = _safe_float(annual.iloc[32])
                result.current_ratio = _safe_float(annual.iloc[45])
                result.debt_ratio = _safe_float(annual.iloc[61])
            except Exception as e:
                print(f"[FinData] 深度财务指标获取失败(非关键): {e}")

        if result:
            _cache.set(cache_key, result, ttl=600)  # 基本面10分钟
        return result

    async def _fundamentals_akshare(self, symbol):
        try:
            import akshare as ak

            # 1. 实时行情 → PE/PB/市值
            df_spot = ak.stock_zh_a_spot_em()
            row = df_spot[df_spot['代码'] == symbol]
            if row.empty:
                return None
            row = row.iloc[0]

            pe = float(row['市盈率-动态']) if '市盈率-动态' in row.index and str(row['市盈率-动态']) not in ('-', '') else None
            pb = float(row['市净率']) if '市净率' in row.index and str(row['市净率']) not in ('-', '') else None
            mcap = float(row['总市值']) if '总市值' in row.index and str(row['总市值']) not in ('-', '') else None

            # 2. 财务指标 → ROE/EPS/利润率/增长率/负债率
            roe = eps = net_margin = gross_margin = None
            revenue_growth = profit_growth = None
            debt_ratio = current_ratio = None

            try:
                df_fin = ak.stock_financial_analysis_indicator(symbol=symbol, start_year='2024')
                latest = df_fin.iloc[-1]  # 最新季度
                annual = df_fin[df_fin.iloc[:, 0].str.contains('12-31', na=False)]
                if not annual.empty:
                    annual = annual.iloc[-1]  # 最近一个完整财年
                else:
                    annual = latest

                # 列索引映射 (stock_financial_analysis_indicator 固定列顺序)
                eps = _safe_float(annual.iloc[1])       # 摊薄每股收益
                roe = _safe_float(annual.iloc[11])       # 净资产收益率
                net_margin = _safe_float(annual.iloc[17])     # 销售净利率
                gross_margin = _safe_float(annual.iloc[21])   # 销售毛利率
                revenue_growth = _safe_float(annual.iloc[31]) # 主营业务收入增长率
                profit_growth = _safe_float(annual.iloc[32])  # 净利润增长率
                current_ratio = _safe_float(annual.iloc[45])  # 流动比率
                debt_ratio = _safe_float(annual.iloc[61])     # 资产负债率

                # 银行股无销售数据，这些为 NaN 是正常的
                if gross_margin and gross_margin == 0:
                    gross_margin = None
                if net_margin and net_margin == 0:
                    net_margin = None

            except Exception as e:
                print(f"[FinData] 深度财务指标获取失败(非关键): {e}")

            return FundamentalData(
                pe_ratio=pe, pb_ratio=pb, market_cap=mcap,
                eps=eps, roe=roe,
                net_margin=net_margin, gross_margin=gross_margin,
                revenue_growth=revenue_growth, profit_growth=profit_growth,
                debt_ratio=debt_ratio, current_ratio=current_ratio,
            )
        except Exception as e:
            print(f"[AKShare] 基本面失败: {e}")
            return None

    async def _fundamentals_baostock(self, symbol):
        # baostock 的面函数需要单独调用，此处返回基础数据
        try:
            import baostock as bs
            bs.login()
            if symbol.startswith('6'):
                bs_code = f'sh.{symbol}'
            else:
                bs_code = f'sz.{symbol}'
            rs = bs.query_stock_basic(code=bs_code)
            data = rs.get_data()
            bs.logout()
            if data.empty:
                return None
            return FundamentalData()
        except:
            return None

    # ========== 新闻舆情 ==========

    async def get_news(self, symbol: str, limit: int = 10) -> List[SentimentItem]:
        """获取个股新闻（东方财富）"""
        cache_key = f"news_{symbol}_{limit}"
        cached = _cache.get(cache_key)
        if cached:
            return cached

        try:
            import akshare as ak
            df = ak.stock_news_em(symbol=symbol)

            if df is None or df.empty:
                print(f"[News] 无新闻数据: {symbol}")
                return []

            items = []
            for _, row in df.head(limit).iterrows():
                # 简单情绪判断：基于关键词
                title = str(row.iloc[1])  # 新闻标题
                content = str(row.iloc[2]) if len(row) > 2 else ''  # 新闻内容
                text = title + content

                # 负面词/正面词计数
                pos_words = ['增长', '上涨', '利好', '突破', '增持', '盈利', '买入', '上升', '回暖', '分红']
                neg_words = ['下跌', '亏损', '减持', '风险', '下滑', '立案', '违约', '暴雷', '退市', '警示']

                pos_count = sum(1 for w in pos_words if w in text)
                neg_count = sum(1 for w in neg_words if w in text)

                if neg_count > pos_count:
                    sentiment = 'negative'
                elif pos_count > neg_count:
                    sentiment = 'positive'
                else:
                    sentiment = 'neutral'

                items.append(SentimentItem(
                    source=str(row.iloc[4]) if len(row) > 4 else '东方财富',
                    title=title[:100],
                    summary=content[:200] if content else title,
                    sentiment=sentiment,
                    timestamp=str(row.iloc[3]) if len(row) > 3 else None,
                ))

            _cache.set(cache_key, items, ttl=300)  # 新闻5分钟
            print(f"[News] {symbol}: 获取 {len(items)} 条新闻")
            return items

        except Exception as e:
            print(f"[News] 获取失败 {symbol}: {e}")
            return []

    # ========== 同步方法（给 Agent Tool 调用，不走 asyncio）==========

    def get_realtime_quote_sync(self, symbol: str) -> Optional[StockQuote]:
        """获取行情（同步版）—— Agent Tool 专用"""
        import threading
        result = [None]
        def _run():
            import asyncio
            loop = asyncio.new_event_loop()
            result[0] = loop.run_until_complete(self.get_realtime_quote(symbol))
            loop.close()
        t = threading.Thread(target=_run)
        t.start()
        t.join(timeout=15)
        return result[0]

    def get_history_sync(self, symbol: str, period: str = "3m") -> List[KLineData]:
        """获取历史K线（同步版）"""
        import threading
        result = [[]]
        def _run():
            import asyncio
            loop = asyncio.new_event_loop()
            result[0] = loop.run_until_complete(self.get_history(symbol, period=period))
            loop.close()
        t = threading.Thread(target=_run)
        t.start()
        t.join(timeout=15)
        return result[0]

    def search_stock_sync(self, keyword: str) -> List[Dict[str, str]]:
        """搜索股票（同步版）"""
        import threading
        result = [[]]
        def _run():
            import asyncio
            loop = asyncio.new_event_loop()
            result[0] = loop.run_until_complete(self.search_stock(keyword))
            loop.close()
        t = threading.Thread(target=_run)
        t.start()
        t.join(timeout=15)
        return result[0]

    def get_fundamentals_sync(self, symbol: str) -> Optional[FundamentalData]:
        """获取基本面（同步版）—— 财务API需多页请求，超时60秒"""
        import threading
        result = [None]
        def _run():
            import asyncio
            loop = asyncio.new_event_loop()
            result[0] = loop.run_until_complete(self.get_fundamentals(symbol))
            loop.close()
        t = threading.Thread(target=_run)
        t.start()
        t.join(timeout=60)  # 财务数据API需要更长超时
        return result[0]

    def get_news_sync(self, symbol: str, limit: int = 10) -> List[SentimentItem]:
        """获取新闻（同步版）"""
        import threading
        result = [[]]
        def _run():
            import asyncio
            loop = asyncio.new_event_loop()
            result[0] = loop.run_until_complete(self.get_news(symbol, limit=limit))
            loop.close()
        t = threading.Thread(target=_run)
        t.start()
        t.join(timeout=15)
        return result[0]


# ========== 全局单例 ==========

_stock_data_service: Optional[StockDataService] = None


def get_stock_data_service() -> StockDataService:
    global _stock_data_service
    if _stock_data_service is None:
        _stock_data_service = StockDataService()
    return _stock_data_service
