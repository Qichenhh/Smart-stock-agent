"""股票数据API路由"""

from fastapi import APIRouter, HTTPException, Query
from ...models.schemas import (
    StockQuoteResponse,
    KLineResponse,
    StockSearchResponse,
    ErrorResponse,
)
from ...services.stock_data_service import get_stock_data_service

router = APIRouter(prefix="/stock", tags=["股票数据"])


@router.get(
    "/quote/{symbol}",
    response_model=StockQuoteResponse,
    summary="获取实时行情",
    description="根据股票代码获取A股实时行情数据"
)
async def get_quote(symbol: str):
    """
    获取实时行情

    Args:
        symbol: 股票代码，如 000001（平安银行）、600519（贵州茅台）
    """
    try:
        service = get_stock_data_service()
        quote = await service.get_realtime_quote(symbol)

        if quote is None:
            raise HTTPException(
                status_code=404,
                detail=f"未找到股票代码 {symbol}，请检查代码是否正确"
            )

        return StockQuoteResponse(
            success=True,
            message="获取行情成功",
            data=quote
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 获取行情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取行情失败: {str(e)}")


@router.get(
    "/history/{symbol}",
    response_model=KLineResponse,
    summary="获取历史K线",
    description="获取A股历史K线数据，支持日K线"
)
async def get_history(
    symbol: str,
    period: str = Query(default="daily", description="K线周期: daily(日线)"),
    start_date: str = Query(default=None, description="起始日期 YYYYMMDD"),
    end_date: str = Query(default=None, description="结束日期 YYYYMMDD"),
):
    """
    获取历史K线数据

    Args:
        symbol: 股票代码
        period: K线周期
        start_date: 起始日期
        end_date: 结束日期
    """
    try:
        service = get_stock_data_service()
        klines = await service.get_history(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )

        return KLineResponse(
            success=True,
            message=f"获取K线数据成功，共 {len(klines)} 条",
            data=klines
        )

    except Exception as e:
        print(f"❌ 获取K线失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取K线失败: {str(e)}")


@router.get(
    "/search",
    response_model=StockSearchResponse,
    summary="搜索股票",
    description="根据关键词搜索股票代码或名称"
)
async def search_stock(
    keyword: str = Query(..., description="搜索关键词（代码或名称）", min_length=1),
):
    """
    搜索股票

    Args:
        keyword: 搜索关键词，如 "平安" 或 "000001"
    """
    try:
        service = get_stock_data_service()
        results = await service.search_stock(keyword)

        return StockSearchResponse(
            success=True,
            message=f"搜索完成，找到 {len(results)} 只股票",
            data=results
        )

    except Exception as e:
        print(f"❌ 搜索股票失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索股票失败: {str(e)}")


@router.get(
    "/health",
    summary="股票数据服务健康检查"
)
async def health_check():
    """健康检查"""
    try:
        service = get_stock_data_service()
        return {
            "status": "healthy",
            "service": "stock-data",
            "provider": "AKShare",
            "cache_ttl": "300s"
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"服务不可用: {str(e)}"
        )