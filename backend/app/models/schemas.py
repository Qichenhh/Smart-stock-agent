"""股票分析数据模型"""

import re
from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, field_validator


# ============ 请求模型 ============

class StockAnalysisRequest(BaseModel):
    """股票分析请求"""
    symbol: str = Field(..., description="股票代码", example="000001")
    market: str = Field(default="A", description="市场: A(A股)/HK(港股)/US(美股)", example="A")
    analysis_type: str = Field(
        default="comprehensive",
        description="分析类型: technical(技术面)/fundamental(基本面)/sentiment(情绪面)/comprehensive(综合)"
    )
    date_range: str = Field(default="3m", description="分析时间范围: 1m/3m/6m/1y", example="3m")
    free_text_input: Optional[str] = Field(default="", description="额外分析要求", example="重点关注北向资金流向")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "000001",
                "market": "A",
                "analysis_type": "comprehensive",
                "date_range": "3m",
                "free_text_input": "重点关注近期走势和资金流向"
            }
        }


# ============ 数据模型 ============

class StockQuote(BaseModel):
    """实时行情"""
    symbol: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    price: float = Field(..., description="最新价")
    change: float = Field(..., description="涨跌额")
    change_percent: float = Field(..., description="涨跌幅(%)")
    volume: float = Field(..., description="成交量(手)")
    amount: float = Field(..., description="成交额(元)")
    high: float = Field(..., description="最高价")
    low: float = Field(..., description="最低价")
    open: float = Field(..., description="开盘价")
    prev_close: float = Field(..., description="前收盘价")
    turnover_rate: Optional[float] = Field(default=None, description="换手率(%)")
    market_cap: Optional[float] = Field(default=None, description="总市值")


class TechnicalIndicator(BaseModel):
    """技术指标"""
    name: str = Field(..., description="指标名称", example="MACD")
    value: str = Field(..., description="指标值", example="DIF上穿DEA")
    signal: str = Field(..., description="信号: buy(买入)/sell(卖出)/neutral(中性)", example="buy")
    description: str = Field(..., description="指标解读", example="MACD金叉，短期看涨信号")


class FundamentalData(BaseModel):
    """基本面数据"""
    pe_ratio: Optional[float] = Field(default=None, description="市盈率")
    pb_ratio: Optional[float] = Field(default=None, description="市净率")
    ps_ratio: Optional[float] = Field(default=None, description="市销率")
    market_cap: Optional[float] = Field(default=None, description="总市值(亿)")
    revenue: Optional[float] = Field(default=None, description="营业收入(亿)")
    net_profit: Optional[float] = Field(default=None, description="净利润(亿)")
    eps: Optional[float] = Field(default=None, description="每股收益")
    roe: Optional[float] = Field(default=None, description="净资产收益率(%)")
    roa: Optional[float] = Field(default=None, description="总资产收益率(%)")
    gross_margin: Optional[float] = Field(default=None, description="毛利率(%)")
    net_margin: Optional[float] = Field(default=None, description="净利率(%)")
    debt_ratio: Optional[float] = Field(default=None, description="资产负债率(%)")
    current_ratio: Optional[float] = Field(default=None, description="流动比率")
    revenue_growth: Optional[float] = Field(default=None, description="营收同比增长(%)")
    profit_growth: Optional[float] = Field(default=None, description="利润同比增长(%)")

    @field_validator('market_cap', 'revenue', 'net_profit', mode='before')
    @classmethod
    def parse_financial_value(cls, v):
        """解析LLM返回的各种数值格式: '2423亿元', '1.2万亿', 'N/A', None"""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            v = v.strip()
            if not v or v.upper() in ('N/A', 'NULL', 'NONE', '-'):
                return None
            # 提取数字部分
            match = re.search(r'[\d,.]+', v)
            if match:
                num_str = match.group().replace(',', '')
                try:
                    num = float(num_str)
                except ValueError:
                    return None
                # 处理单位: 万亿、亿、万
                if '万亿' in v:
                    return num * 10000  # 转为亿
                if '万' in v and '亿' not in v:
                    return num / 10000  # 转为亿
                return num  # 默认视为亿
            return None
        return None


class SentimentItem(BaseModel):
    """市场情绪条目"""
    source: str = Field(default="市场数据", description="信息来源")
    title: str = Field(default="市场情绪", description="标题")
    summary: str = Field(default="", description="摘要")
    sentiment: str = Field(default="neutral", description="情绪: positive(正面)/negative(负面)/neutral(中性)")
    timestamp: Optional[str] = Field(default=None, description="发布时间")


class KLineData(BaseModel):
    """K线数据点"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    open: float = Field(..., description="开盘价")
    close: float = Field(..., description="收盘价")
    high: float = Field(..., description="最高价")
    low: float = Field(..., description="最低价")
    volume: float = Field(..., description="成交量")
    amount: Optional[float] = Field(default=None, description="成交额")


# ============ 分析报告模型 ============

class TechnicalSection(BaseModel):
    """技术面分析部分"""
    score: int = Field(..., description="技术面评分 0-100", ge=0, le=100)
    summary: str = Field(..., description="技术面分析总结")
    indicators: List[TechnicalIndicator] = Field(default=[], description="技术指标列表")


class FundamentalSection(BaseModel):
    """基本面分析部分"""
    score: int = Field(..., description="基本面评分 0-100", ge=0, le=100)
    summary: str = Field(..., description="基本面分析总结")
    data: FundamentalData = Field(default_factory=FundamentalData, description="基本面数据")


class SentimentSection(BaseModel):
    """情绪面分析部分"""
    score: int = Field(..., description="情绪面评分 0-100", ge=0, le=100)
    summary: str = Field(..., description="情绪面分析总结")
    items: List[SentimentItem] = Field(default=[], description="情绪/新闻列表")


class AnalysisReport(BaseModel):
    """综合分析报告"""
    symbol: str = Field(..., description="股票代码")
    company_name: str = Field(..., description="公司名称")
    market: str = Field(..., description="市场")
    generated_at: str = Field(default="", description="报告生成时间")
    summary: str = Field(..., description="综合摘要")
    technical_analysis: TechnicalSection = Field(..., description="技术面分析")
    fundamental_analysis: FundamentalSection = Field(..., description="基本面分析")
    sentiment_analysis: SentimentSection = Field(..., description="情绪面分析")
    overall_rating: str = Field(
        ...,
        description="综合评级: 强烈买入/买入/持有/卖出/强烈卖出"
    )
    risks: List[str] = Field(default=[], description="风险提示")
    suggestions: str = Field(..., description="操作建议")


# ============ 响应模型 ============

class AnalysisResponse(BaseModel):
    """分析报告响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: Optional[AnalysisReport] = Field(default=None, description="分析报告数据")


class StockQuoteResponse(BaseModel):
    """行情响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: Optional[StockQuote] = Field(default=None, description="行情数据")


class KLineResponse(BaseModel):
    """K线数据响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: List[KLineData] = Field(default=[], description="K线数据列表")


class StockSearchResult(BaseModel):
    """股票搜索结果"""
    symbol: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    market: str = Field(..., description="市场")
    industry: Optional[str] = Field(default=None, description="所属行业")


class StockSearchResponse(BaseModel):
    """股票搜索响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: List[StockSearchResult] = Field(default=[], description="搜索结果列表")


# ============ 错误响应 ============

class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = Field(default=False, description="是否成功")
    message: str = Field(..., description="错误消息")
    error_code: Optional[str] = Field(default=None, description="错误代码")
