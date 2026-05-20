"""多股票对比API路由"""

from fastapi import APIRouter, HTTPException
from typing import List
from pydantic import BaseModel, Field
from ...services.stock_data_service import get_stock_data_service
from ...services.llm_service import get_llm
from hello_agents import SimpleAgent
import json

router = APIRouter(prefix="/stock", tags=["股票对比"])


class CompareRequest(BaseModel):
    symbols: List[str] = Field(..., description="股票代码列表，2-5只", min_length=2, max_length=5)
    date_range: str = Field(default="3m", description="数据时间范围")


class CompareItem(BaseModel):
    symbol: str
    name: str
    price: float
    change_pct: float
    pe_ratio: float = None
    pb_ratio: float = None
    market_cap: float = None
    eps: float = None
    roe: float = None
    revenue_growth: float = None
    profit_growth: float = None


class CompareResponse(BaseModel):
    success: bool
    message: str
    data: dict = None


# --- 对比 Agent ---

COMPARE_PROMPT = """你是股票对比分析专家。根据多只股票的实时数据和基本面，生成对比分析报告。

**对比维度：**
1. 估值对比 — 哪只最便宜/最贵，PE/PB排名
2. 盈利能力对比 — ROE/EPS 高低排序
3. 成长性对比 — 营收/利润增速排名
4. 市值规模对比 — 大盘/中盘/小盘
5. 综合评分 — 给每只股票打分(0-100)，说明推荐顺序

**返回纯JSON（不要markdown包裹）：**
{
  "summary": "对比总结，100字以内",
  "rankings": [{"rank": 1, "symbol": "...", "name": "...", "score": 85, "reason": "..."}],
  "best_pick": {"symbol": "...", "name": "...", "reason": "..."},
  "comparison_table": {
    "headers": ["指标", "股票A", "股票B"],
    "rows": [["PE", "5.2", "6.8"], ...]
  }
}
"""


@router.post("/compare", response_model=CompareResponse, summary="多股票对比分析")
async def compare_stocks(request: CompareRequest):
    """并排对比多只股票的关键指标"""
    try:
        service = get_stock_data_service()
        llm = get_llm()

        # 收集所有股票数据
        stocks_data = []
        for sym in request.symbols:
            quote = service.get_realtime_quote_sync(sym)
            fund = service.get_fundamentals_sync(sym)
            if quote:
                stocks_data.append({
                    "symbol": sym,
                    "name": quote.name,
                    "price": quote.price,
                    "change_pct": quote.change_percent,
                    "pe_ratio": fund.pe_ratio if fund else None,
                    "pb_ratio": fund.pb_ratio if fund else None,
                    "market_cap": fund.market_cap if fund else None,
                    "eps": fund.eps if fund else None,
                    "roe": fund.roe if fund else None,
                    "revenue_growth": fund.revenue_growth if fund else None,
                    "profit_growth": fund.profit_growth if fund else None,
                })

        if len(stocks_data) < 2:
            return CompareResponse(success=False, message="至少需要2只有效股票", data=None)

        # 构建对比查询
        comparison_text = "请对比以下股票：\n\n"
        for s in stocks_data:
            comparison_text += f"**{s['symbol']} {s['name']}**\n"
            comparison_text += f"  最新价: {s['price']}, 涨跌幅: {s['change_pct']}%\n"
            comparison_text += f"  PE: {s['pe_ratio'] or 'N/A'}, PB: {s['pb_ratio'] or 'N/A'}, 市值: {s['market_cap'] or 'N/A'}\n"
            comparison_text += f"  EPS: {s['eps'] or 'N/A'}, ROE: {s['roe'] or 'N/A'}%\n"
            comparison_text += f"  营收增速: {s['revenue_growth'] or 'N/A'}%, 利润增速: {s['profit_growth'] or 'N/A'}%\n\n"

        # 创建对比Agent并执行
        agent = SimpleAgent(name="股票对比专家", llm=llm, system_prompt=COMPARE_PROMPT)
        response = agent.run(comparison_text)

        # 解析JSON
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "{" in response:
                json_str = response[response.find("{"):response.rfind("}")+1]
            else:
                json_str = response
            result = json.loads(json_str)
        except:
            result = {"summary": response[:200], "rankings": []}

        return CompareResponse(
            success=True,
            message=f"对比完成，共 {len(stocks_data)} 只股票",
            data={"stocks_data": stocks_data, "analysis": result}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"对比分析失败: {str(e)}")
