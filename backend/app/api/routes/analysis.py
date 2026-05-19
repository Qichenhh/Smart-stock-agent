"""股票分析API路由 — Agent 协同分析端点"""

from fastapi import APIRouter, HTTPException
from ...models.schemas import StockAnalysisRequest, AnalysisResponse, ErrorResponse
from ...agents.stock_analyst_agent import get_stock_analyst

router = APIRouter(prefix="/stock", tags=["股票分析"])


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    summary="智能股票分析",
    description="使用多Agent协同系统对股票进行综合分析：技术面 + 基本面 + 情绪面 → 综合报告"
)
async def analyze_stock(request: StockAnalysisRequest):
    """
    智能股票分析

    调用链：
    1. 技术面 Agent   → 获取行情+K线 → 技术指标分析
    2. 基本面 Agent   → 获取财务数据 → 估值分析
    3. 情绪面 Agent   → 获取行情 → 市场情绪分析
    4. 报告 Agent     → 综合前三步 → 结构化JSON报告

    Args:
        request: 股票分析请求 { symbol, market, analysis_type, date_range, free_text_input }

    Returns:
        综合分析报告 { symbol, summary, technical_analysis, fundamental_analysis,
                      sentiment_analysis, overall_rating, risks, suggestions }
    """
    try:
        print(f"\n{'='*60}")
        print(f"[API] 收到分析请求: {request.symbol}")
        print(f"{'='*60}\n")

        # 获取Agent系统实例（全局单例，首次调用时初始化）
        analyst = get_stock_analyst()

        # 执行四Agent协同分析
        report = analyst.analyze_stock(request)

        print("[API] 分析完成，返回报告\n")

        return AnalysisResponse(
            success=True,
            message=f"{request.symbol} 分析完成",
            data=report
        )

    except Exception as e:
        print(f"[API] 分析失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"股票分析失败: {str(e)}"
        )


@router.get(
    "/health",
    summary="分析服务健康检查"
)
async def health_check():
    """健康检查 — 确认 Agent 系统是否就绪"""
    try:
        analyst = get_stock_analyst()
        return {
            "status": "healthy",
            "service": "stock-analyst",
            "agents": {
                "technical": analyst.technical_agent.name,
                "fundamental": analyst.fundamental_agent.name,
                "sentiment": analyst.sentiment_agent.name,
                "report": analyst.report_agent.name,
            },
            "technical_agent_tools": len(analyst.technical_agent.list_tools()),
            "report_agent_tools": len(analyst.report_agent.list_tools()),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"分析服务不可用: {str(e)}")
