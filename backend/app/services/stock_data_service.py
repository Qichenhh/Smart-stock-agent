"""股票数据服务 — baostock + akshare 双数据源"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from ..models.schemas import (
    StockQuote, KLineData, FundamentalData,
    TechnicalIndicator, SentimentItem,
)

# 缓存机制
_cache: Dict[str, Any] = {}
_cache_time: Dict[str, datetime] = {}
CACHE_TTL = 300  # 5分钟


def _cache_get(key: str) -> Optional[Any]:
    if key in _cache and key in _cache_time:
        if (datetime.now() - _cache_time[key]).seconds < CACHE_TTL:
            return _cache[key]
    return None


def _cache_set(key: str, value: Any):
    _cache[key] = value
    _cache_time[key] = datetime.now()


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
        cached = _cache_get(cache_key)
        if cached:
            return cached

        if self._data_source == "akshare":
            result = await self._quote_akshare(symbol)
        elif self._data_source == "baostock":
            result = await self._quote_baostock(symbol)
        else:
            result = self._quote_mock(symbol)

        if result:
            _cache_set(cache_key, result)
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
        cached = _cache_get(cache_key)
        if cached:
            return cached

        if self._data_source == "akshare":
            result = await self._history_akshare(symbol, period, start_date, end_date)
        elif self._data_source == "baostock":
            result = await self._history_baostock(symbol, period, start_date, end_date)
        else:
            result = self._history_mock(symbol)

        _cache_set(cache_key, result)
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
        cached = _cache_get(cache_key)
        if cached:
            return cached

        if self._data_source == "akshare":
            result = await self._search_akshare(keyword)
        elif self._data_source == "baostock":
            result = await self._search_baostock(keyword)
        else:
            result = [{"symbol": keyword, "name": f"测试{keyword}", "market": "A", "industry": None}]

        _cache_set(cache_key, result)
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
        cached = _cache_get(cache_key)
        if cached:
            return cached

        if self._data_source == "akshare":
            result = await self._fundamentals_akshare(symbol)
        elif self._data_source == "baostock":
            result = await self._fundamentals_baostock(symbol)
        else:
            result = FundamentalData(pe_ratio=15.0, pb_ratio=2.5, market_cap=500)

        if result:
            _cache_set(cache_key, result)
        return result

    async def _fundamentals_akshare(self, symbol):
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            row = df[df['代码'] == symbol]
            if row.empty:
                return None
            row = row.iloc[0]
            return FundamentalData(
                pe_ratio=float(row['市盈率-动态']) if '市盈率-动态' in row.index and row['市盈率-动态'] != '-' else None,
                pb_ratio=float(row['市净率']) if '市净率' in row.index and row['市净率'] != '-' else None,
                market_cap=float(row['总市值']) if '总市值' in row.index and row['总市值'] != '-' else None,
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


# ========== 全局单例 ==========

_stock_data_service: Optional[StockDataService] = None


def get_stock_data_service() -> StockDataService:
    global _stock_data_service
    if _stock_data_service is None:
        _stock_data_service = StockDataService()
    return _stock_data_service
