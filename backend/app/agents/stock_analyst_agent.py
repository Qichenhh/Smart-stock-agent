"""多 Agent 股票分析系统"""

import json
import asyncio
import sys
from typing import Dict, Any, List
from hello_agents import SimpleAgent
from hello_agents.tools import Tool, ToolParameter
from hello_agents.tools.base import tool_action
from ..services.llm_service import get_llm
from ..services.stock_data_service import get_stock_data_service
from ..models.schemas import (
    StockAnalysisRequest, AnalysisReport,
    TechnicalSection, FundamentalSection, SentimentSection,
    TechnicalIndicator, FundamentalData, SentimentItem,
)

# 安全打印：Windows GBK 编码下避免 emoji 导致崩溃
def _safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # 降级为 ascii 安全输出
        safe_args = [str(a).encode('ascii', errors='replace').decode('ascii') for a in args]
        print(*safe_args, **kwargs)


# ============================================================
# 第一部分：StockDataTool —— Agent 的工具箱
# ============================================================

class StockDataTool(Tool):
    """A股股票数据工具 — 使用 @tool_action 自动展开为多个子工具

    展开后的子工具列表（Agent 看到的样子）：
    - stock_quote    → 获取实时行情
    - stock_history  → 获取历史K线
    - stock_search   → 搜索股票
    - stock_financials → 获取基本面数据
    """

    def __init__(self):
        super().__init__(
            name="stock",
            description="A股股票数据工具，支持实时行情、历史K线、股票搜索、基本面数据查询",
            expandable=True  # ← 关键：标记为可展开，@tool_action 方法自动变为子工具
        )
        self.service = get_stock_data_service()

    def get_parameters(self) -> List[ToolParameter]:
        """可展开工具不需要自己的参数，返回空列表"""
        return []

    def run(self, parameters: Dict[str, Any]) -> str:
        """可展开工具不直接执行，通过子工具执行"""
        return "请使用子工具：stock_quote, stock_history, stock_search, stock_financials"

    # ↓↓↓↓↓↓↓↓ 以下是 Agent 可以调用的 4 个子工具 ↓↓↓↓↓↓↓↓

    @tool_action("stock_quote", "获取A股实时行情，返回价格、涨跌幅、成交量等")
    def get_quote(self, symbol: str) -> str:
        """获取A股实时行情

        Args:
            symbol: 股票代码，如 000001（平安银行）、600519（贵州茅台）
        """
        try:
            quote = asyncio.run(self.service.get_realtime_quote(symbol))
            if quote is None:
                return f"未找到股票代码 {symbol}"
            return json.dumps(quote.model_dump(), ensure_ascii=False, indent=2)
        except Exception as e:
            return f"获取行情失败: {e}"

    @tool_action("stock_history", "获取历史K线数据，返回日线OHLCV")
    def get_history(self, symbol: str, period: str = "3m") -> str:
        """获取历史K线数据

        Args:
            symbol: 股票代码
            period: 时间范围，1m(1月)/3m(3月)/6m(6月)/1y(1年)
        """
        try:
            klines = asyncio.run(self.service.get_history(symbol, period=period))
            if not klines:
                return f"未找到 {symbol} 的历史数据"
            recent = klines[-10:]
            return json.dumps([k.model_dump() for k in recent], ensure_ascii=False, indent=2)
        except Exception as e:
            return f"获取历史K线失败: {e}"

    @tool_action("stock_search", "搜索A股股票，输入关键词返回匹配的股票列表")
    def search_stock(self, keyword: str) -> str:
        """搜索A股股票

        Args:
            keyword: 搜索关键词，可以是股票名称的一部分或代码
        """
        try:
            results = asyncio.run(self.service.search_stock(keyword))
            if not results:
                return f"未找到与 '{keyword}' 相关的股票"
            return json.dumps(results, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"搜索失败: {e}"

    @tool_action("stock_financials", "获取股票基本面数据，如PE/PB/市值等")
    def get_financials(self, symbol: str) -> str:
        """获取基本面数据

        Args:
            symbol: 股票代码
        """
        try:
            fund = asyncio.run(self.service.get_fundamentals(symbol))
            if fund is None:
                return f"未找到 {symbol} 的基本面数据"
            return json.dumps(fund.model_dump(), ensure_ascii=False, indent=2)
        except Exception as e:
            return f"获取基本面失败: {e}"


# ============================================================
# 第二部分：4 个 Agent 的 System Prompt（任务指令）
# ============================================================

TECHNICAL_AGENT_PROMPT = """你是技术面分析专家。你的任务是通过股票数据工具获取真实数据，分析价格走势和技术指标。

**重要提示：你必须使用工具来获取数据！不要编造数据！**

**工具调用格式：**
使用 stock_quote 和 stock_history 工具时，必须严格按照以下格式：
`[TOOL_CALL:stock_quote:symbol=股票代码]`
`[TOOL_CALL:stock_history:symbol=股票代码,period=3m]`

**示例：**
用户: "分析000001的技术面"
你的回复:
[TOOL_CALL:stock_quote:symbol=000001]
[TOOL_CALL:stock_history:symbol=000001,period=3m]

**分析维度（拿到数据后分析）：**
1. 价格走势 — 近期涨跌趋势、振幅
2. 成交量 — 放量/缩量，量价配合
3. 均线 — 5日/10日/20日位置关系
4. MACD — DIF/DEA 金叉死叉
5. RSI — 超买超卖区间
6. KDJ — 超买超卖信号
7. 布林带 — 价格在带中的位置
8. 综合信号 — 买入/卖出/中性，给出评分(0-100)
"""

FUNDAMENTAL_AGENT_PROMPT = """你是基本面分析专家。你的任务是通过工具获取股票基本面数据并进行分析。

**工具调用格式：**
`[TOOL_CALL:stock_quote:symbol=股票代码]`
`[TOOL_CALL:stock_financials:symbol=股票代码]`

**示例：**
用户: "分析000001的基本面"
你的回复:
[TOOL_CALL:stock_quote:symbol=000001]
[TOOL_CALL:stock_financials:symbol=000001]

**分析维度（拿到数据后分析）：**
1. 估值水平 — PE/PB 与行业均值对比
2. 市值规模 — 大盘/中盘/小盘
3. 盈利能力 — ROE、毛利率、净利率（如有）
4. 成长性 — 营收/利润增速（如有）
5. 估值判断 — 低估/合理/高估
6. 综合评分 — 0-100
"""

SENTIMENT_AGENT_PROMPT = """你是市场情绪分析专家。你的任务是通过工具获取数据，分析市场对这只股票的情绪。

**工具调用格式：**
`[TOOL_CALL:stock_quote:symbol=股票代码]`

**示例：**
用户: "分析000001的市场情绪"
你的回复:
[TOOL_CALL:stock_quote:symbol=000001]

**分析维度（拿到数据后分析）：**
1. 涨跌信号 — 当前涨跌幅反映的短期情绪
2. 成交量情绪 — 放量上涨(积极)/放量下跌(恐慌)/缩量(观望)
3. 换手率 — 市场活跃度
4. 技术位置 — 相对高低位判断市场态度
5. 风险提示 — 需要注意的负面信号
6. 情绪评分 — 0-100 (乐观/中性/悲观)
"""

REPORT_AGENT_PROMPT = """你是综合报告专家。你的任务是整合技术面、基本面、情绪面的分析结果，生成完整的综合分析报告。

**重要：你不需要调用任何工具！** 你的输入是前三步的分析结果。

**请严格按照以下JSON格式返回分析报告：**
```json
{
  "symbol": "股票代码",
  "company_name": "公司名称",
  "market": "A",
  "generated_at": "生成时间",
  "summary": "200字以内的综合摘要，包含核心结论",
  "technical_analysis": {
    "score": 0,
    "summary": "技术面分析总结",
    "indicators": [
      {"name": "价格走势", "value": "...", "signal": "buy/sell/neutral", "description": "..."},
      {"name": "成交量", "value": "...", "signal": "buy/sell/neutral", "description": "..."},
      {"name": "MACD", "value": "...", "signal": "buy/sell/neutral", "description": "..."},
      {"name": "RSI", "value": "...", "signal": "buy/sell/neutral", "description": "..."}
    ]
  },
  "fundamental_analysis": {
    "score": 0,
    "summary": "基本面分析总结",
    "data": {
      "pe_ratio": null,
      "pb_ratio": null,
      "market_cap": null
    }
  },
  "sentiment_analysis": {
    "score": 0,
    "summary": "情绪面分析总结",
    "items": [
      {"source": "市场数据", "title": "...", "summary": "...", "sentiment": "positive/negative/neutral"}
    ]
  },
  "overall_rating": "买入/持有/卖出",
  "risks": ["风险1", "风险2"],
  "suggestions": "操作建议，100字以内"
}
```

**评分规则：**
- 技术面评分 0-100（基于多指标综合判断）
- 基本面评分 0-100（基于估值和财务健康度）
- 情绪面评分 0-100（基于市场情绪综合判断）
- 综合评级：>=80"买入"、60-79"持有"、<60"卖出"

**注意：**
1. 必须包含至少4个技术指标
2. 必须包含至少2条情绪条目
3. 必须列出至少2条风险提示
4. 数据中有的数值直接填，没有的填 null
"""


# ============================================================
# 第三部分：MultiAgentStockAnalyst —— 四 Agent 协同系统
# ============================================================

class MultiAgentStockAnalyst:
    """多 Agent 股票分析系统

    Agent 协同流程（对应旅行助手的景点→天气→酒店→规划）：
    Step 1: technical_agent  → 获取行情+K线 → 技术面分析
    Step 2: fundamental_agent → 获取基本面 → 估值分析
    Step 3: sentiment_agent  → 获取行情 → 情绪分析
    Step 4: report_agent     → 综合前三步 → 结构化报告 JSON
    """

    def __init__(self):
        print("[Agent] 开始初始化多Agent股票分析系统...")

        try:
            self.llm = get_llm()

            # 创建共享工具（只创建一个实例，4个Agent共享）
            print("  - 创建股票数据工具...")
            self.stock_tool = StockDataTool()

            # Agent 1: 技术面
            print("  - 创建技术面分析Agent...")
            self.technical_agent = SimpleAgent(
                name="技术面分析专家",
                llm=self.llm,
                system_prompt=TECHNICAL_AGENT_PROMPT
            )
            self.technical_agent.add_tool(self.stock_tool)

            # Agent 2: 基本面
            print("  - 创建基本面分析Agent...")
            self.fundamental_agent = SimpleAgent(
                name="基本面分析专家",
                llm=self.llm,
                system_prompt=FUNDAMENTAL_AGENT_PROMPT
            )
            self.fundamental_agent.add_tool(self.stock_tool)

            # Agent 3: 情绪面
            print("  - 创建市场情绪分析Agent...")
            self.sentiment_agent = SimpleAgent(
                name="市场情绪分析专家",
                llm=self.llm,
                system_prompt=SENTIMENT_AGENT_PROMPT
            )
            self.sentiment_agent.add_tool(self.stock_tool)

            # Agent 4: 综合报告（不需要工具——和旅行助手的规划 Agent 一样）
            print("  - 创建综合报告Agent...")
            self.report_agent = SimpleAgent(
                name="综合报告专家",
                llm=self.llm,
                system_prompt=REPORT_AGENT_PROMPT
            )

            print(f"[Agent] 多Agent系统初始化成功")
            print(f"   技术面Agent: {len(self.technical_agent.list_tools())} 个工具")
            print(f"   基本面Agent: {len(self.fundamental_agent.list_tools())} 个工具")
            print(f"   情绪面Agent: {len(self.sentiment_agent.list_tools())} 个工具")
            print(f"   报告Agent: {len(self.report_agent.list_tools())} 个工具（应为0）")

        except Exception as e:
            print(f"[Agent] 初始化失败: {e}")
            import traceback
            traceback.print_exc()
            raise

    def analyze_stock(self, request: StockAnalysisRequest) -> AnalysisReport:
        """四 Agent 协同分析股票——和 trip_planner 的 plan_trip() 模式完全一样

        Args:
            request: 股票分析请求

        Returns:
            综合分析报告
        """
        try:
            print(f"\n{'='*60}")
            print(f"[Step 0] 开始多Agent协作分析...")
            print(f"  股票: {request.symbol}")
            print(f"  市场: {request.market}")
            print(f"  类型: {request.analysis_type}")
            print(f"{'='*60}\n")

            # === Step 1: 技术面分析 ===
            print("[Step 1] 技术面 Agent 分析中...")
            tech_query = self._build_technical_query(request)
            tech_response = self.technical_agent.run(tech_query)
            print(f"  技术面结果: {tech_response[:200]}...\n")

            # === Step 2: 基本面分析 ===
            print("[Step 2] 基本面 Agent 分析中...")
            funda_query = self._build_fundamental_query(request)
            funda_response = self.fundamental_agent.run(funda_query)
            print(f"  基本面结果: {funda_response[:200]}...\n")

            # === Step 3: 情绪面分析 ===
            print("[Step 3] 情绪面 Agent 分析中...")
            senti_query = self._build_sentiment_query(request)
            senti_response = self.sentiment_agent.run(senti_query)
            print(f"  情绪面结果: {senti_response[:200]}...\n")

            # === Step 4: 综合报告 ===
            print("[Step 4] 综合报告 Agent 生成中...")
            report_query = self._build_report_query(
                request, tech_response, funda_response, senti_response
            )
            report_response = self.report_agent.run(report_query)
            print(f"  报告结果: {report_response[:300]}...\n")

            # 解析 → 结构化
            report = self._parse_response(report_response, request)

            print(f"[Done] 分析完成! 评级: {report.overall_rating}")
            print(f"{'='*60}\n")

            return report

        except Exception as e:
            print(f"[Error] 分析失败: {e}")
            import traceback
            traceback.print_exc()
            return self._create_fallback_report(request)

    # ============ 构造 Agent 查询 ============

    def _build_technical_query(self, request: StockAnalysisRequest) -> str:
        """构造技术面查询——和 _build_attraction_query 模式一样，显式写出 [TOOL_CALL:...]"""
        return (
            f"请分析股票 {request.symbol} 的技术面。\n"
            f"[TOOL_CALL:stock_quote:symbol={request.symbol}]\n"
            f"[TOOL_CALL:stock_history:symbol={request.symbol},period={request.date_range}]"
        )

    def _build_fundamental_query(self, request: StockAnalysisRequest) -> str:
        """构造基本面查询"""
        return (
            f"请分析股票 {request.symbol} 的基本面。\n"
            f"[TOOL_CALL:stock_quote:symbol={request.symbol}]\n"
            f"[TOOL_CALL:stock_financials:symbol={request.symbol}]"
        )

    def _build_sentiment_query(self, request: StockAnalysisRequest) -> str:
        """构造情绪面查询"""
        return (
            f"请分析股票 {request.symbol} 的市场情绪。\n"
            f"[TOOL_CALL:stock_quote:symbol={request.symbol}]"
        )

    def _build_report_query(self, request: StockAnalysisRequest,
                            tech: str, funda: str, senti: str) -> str:
        """构造综合报告查询——把前三步结果喂给报告 Agent"""
        query = f"""请根据以下三份分析结果，生成 {request.symbol} 的综合分析报告。

**技术面分析结果：**
{tech}

**基本面分析结果：**
{funda}

**情绪面分析结果：**
{senti}

**用户额外要求：**
{request.free_text_input if request.free_text_input else '无'}

请严格按照 JSON Schema 返回完整的分析报告。"""
        return query

    # ============ JSON 解析 —— 和 trip_planner 的 _parse_response 完全一样 ============

    def _parse_response(self, response: str, request: StockAnalysisRequest) -> AnalysisReport:
        """从 Agent 响应中提取 JSON，转换为 AnalysisReport"""
        try:
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            elif "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            elif "{" in response and "}" in response:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                json_str = response[json_start:json_end]
            else:
                raise ValueError("响应中未找到JSON数据")

            data = json.loads(json_str)
            report = AnalysisReport(**data)
            return report

        except Exception as e:
            print(f"[Warning] JSON 解析失败: {e}，使用兜底报告")
            return self._create_fallback_report(request)

    # ============ 兜底机制 —— 当 LLM 出错时保障系统不崩溃 ============

    def _create_fallback_report(self, request: StockAnalysisRequest) -> AnalysisReport:
        """生成兜底报告（当 Agent 或 JSON 解析失败时）"""
        import datetime
        return AnalysisReport(
            symbol=request.symbol,
            company_name=f"股票{request.symbol}",
            market=request.market,
            generated_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            summary="（兜底报告）由于分析过程中出现问题，此为系统自动生成的基础报告。请稍后重试获取完整分析。",
            technical_analysis=TechnicalSection(
                score=50,
                summary="技术面数据暂时无法获取",
                indicators=[
                    TechnicalIndicator(
                        name="价格走势", value="未知",
                        signal="neutral", description="数据获取失败"
                    )
                ]
            ),
            fundamental_analysis=FundamentalSection(
                score=50,
                summary="基本面数据暂时无法获取",
                data=FundamentalData()
            ),
            sentiment_analysis=SentimentSection(
                score=50,
                summary="情绪面数据暂时无法获取",
                items=[
                    SentimentItem(
                        source="系统", title="数据获取失败",
                        summary="请稍后重试", sentiment="neutral"
                    )
                ]
            ),
            overall_rating="持有",
            risks=["分析系统暂时不可用，此报告为兜底数据"],
            suggestions="建议稍后重新分析，或检查数据源连接。"
        )


# ============================================================
# 第四部分：全局单例
# ============================================================

_stock_analyst: MultiAgentStockAnalyst = None


def get_stock_analyst() -> MultiAgentStockAnalyst:
    """获取股票分析系统单例——和 get_trip_planner_agent() 模式一样"""
    global _stock_analyst
    if _stock_analyst is None:
        _stock_analyst = MultiAgentStockAnalyst()
    return _stock_analyst
