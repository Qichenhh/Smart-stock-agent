"""股票分析API路由 — Agent 协同分析端点"""

import json
import asyncio
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from ...models.schemas import StockAnalysisRequest, AnalysisResponse, ErrorResponse
from ...agents.stock_analyst_agent import get_stock_analyst
from ...services.news_monitor import get_news_monitor

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


@router.websocket("/ws/analyze")
async def analyze_websocket(ws: WebSocket):
    """WebSocket 实时分析进度推送"""
    await ws.accept()
    try:
        # 接收分析请求
        raw = await ws.receive_text()
        request = StockAnalysisRequest(**json.loads(raw))

        # 发送开始信号
        await ws.send_json({"type": "start", "symbol": request.symbol})

        # 获取 Agent
        analyst = get_stock_analyst()

        # 在线程中运行 Agent（避免阻塞事件循环）
        import threading
        result_holder: dict = {"report": None, "error": None}

        def run_agent():
            try:
                result_holder["report"] = analyst.analyze_stock(request)
            except Exception as e:
                result_holder["error"] = str(e)

        # 发送中间进度
        await ws.send_json({"type": "progress", "step": 0, "text": "获取实时行情..."})

        thread = threading.Thread(target=run_agent)
        thread.start()

        # 进度推送 + keepalive ping（每3秒发一次，防止 WebSocket 超时断开）
        steps = [
            (1, "技术面 Agent 分析中..."),
            (2, "基本面 Agent 分析中..."),
            (3, "情绪面 Agent 分析中..."),
            (4, "生成综合报告..."),
        ]
        step_idx = 0
        while thread.is_alive():
            await asyncio.sleep(3)
            # 发送进度或 ping
            if step_idx < len(steps):
                await ws.send_json({"type": "progress", "step": steps[step_idx][0], "text": steps[step_idx][1]})
                step_idx += 1
            else:
                await ws.send_json({"type": "ping"})  # keepalive

        thread.join()

        if result_holder["error"]:
            await ws.send_json({"type": "error", "message": result_holder["error"]})
        else:
            report = result_holder["report"]
            await ws.send_json({
                "type": "done",
                "data": report.model_dump(),
                "summary": f"{report.overall_rating} — 技术面{report.technical_analysis.score}分, 基本面{report.fundamental_analysis.score}分, 情绪面{report.sentiment_analysis.score}分"
            })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except:
            pass


@router.websocket("/ws/alerts")
async def news_alerts_websocket(ws: WebSocket):
    """WebSocket 新闻预警推送 — 订阅股票后实时接收新闻预警"""
    await ws.accept()
    monitor = get_news_monitor()
    subscribed = []

    async def send_heartbeat():
        """每30秒发心跳保活"""
        while True:
            await asyncio.sleep(30)
            try:
                await ws.send_json({"type": "ping"})
            except Exception:
                break

    heartbeat_task = asyncio.create_task(send_heartbeat())

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)

            if msg.get("action") == "subscribe":
                symbols = msg.get("symbols", [])
                for sym in symbols:
                    monitor.subscribe(sym, ws)
                    subscribed.append(sym)
                await ws.send_json({
                    "type": "subscribed",
                    "symbols": subscribed,
                    "message": f"已订阅 {len(subscribed)} 只股票的新闻预警"
                })

            elif msg.get("action") == "unsubscribe":
                symbols = msg.get("symbols", [])
                for sym in symbols:
                    monitor.unsubscribe(sym, ws)
                    if sym in subscribed:
                        subscribed.remove(sym)
                await ws.send_json({
                    "type": "unsubscribed",
                    "symbols": symbols
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        heartbeat_task.cancel()
        for sym in subscribed:
            monitor.unsubscribe(sym, ws)
