# 智能旅行助手 → 智能股票分析助手：完整迁移计划

---

## 第一部分：架构全景图

### 1.1 当前项目文件映射（按职责分层）

```
┌── 配置层 ─────────────────────────────────────────────────────┐
│ backend/.env              ← LLM Key、高德 Key、Unsplash Key    │
│ backend/app/config.py     ← pydantic-settings，读 .env         │
│ frontend/.env             ← VITE_API_BASE_URL、高德 Web Key    │
│ frontend/vite.config.ts   ← Vite 代理 /api → :8000            │
└──────────────────────────────────────────────────────────────┘

┌── 启动层 ─────────────────────────────────────────────────────┐
│ backend/run.py             ← uvicorn.run("app.api.main:app")   │
│ frontend/index.html        ← <script src="/src/main.ts">       │
│ frontend/src/main.ts       ← createApp + router + Antd        │
└──────────────────────────────────────────────────────────────┘

┌── API 路由层 ─────────────────────────────────────────────────┐
│ backend/app/api/main.py        ← FastAPI app 工厂，注册路由     │
│ backend/app/api/routes/trip.py ← POST /api/trip/plan           │
│ backend/app/api/routes/map.py  ← /api/map/poi,weather,route    │
│ backend/app/api/routes/poi.py  ← /api/poi/detail,search,photo  │
└──────────────────────────────────────────────────────────────┘

┌── Agent 层（核心业务逻辑）────────────────────────────────────┐
│ backend/app/agents/trip_planner_agent.py                       │
│   ├─ MultiAgentTripPlanner.__init__()  → 4 个 SimpleAgent      │
│   ├─ MultiAgentTripPlanner.plan_trip() → 顺序执行 4 步         │
│   ├─ _parse_response()                 → JSON 提取             │
│   └─ _create_fallback_plan()           → 硬编码兜底            │
└──────────────────────────────────────────────────────────────┘

┌── 数据模型层 ─────────────────────────────────────────────────┐
│ backend/app/models/schemas.py  ← 22 个 Pydantic 类             │
│ frontend/src/types/index.ts    ← 对应 TS 接口                  │
└──────────────────────────────────────────────────────────────┘

┌── 服务层（数据源封装）────────────────────────────────────────┐
│ backend/app/services/llm_service.py      ← HelloAgentsLLM 单例 │
│ backend/app/services/amap_service.py     ← MCPTool("amap")     │
│ backend/app/services/unsplash_service.py ← Unsplash REST API   │
└──────────────────────────────────────────────────────────────┘

┌── 前端视图层 ─────────────────────────────────────────────────┐
│ frontend/src/App.vue              ← 根布局 (a-layout)          │
│ frontend/src/views/Home.vue       ← 旅行表单                    │
│ frontend/src/views/Result.vue     ← 行程结果（含高德地图）      │
│ frontend/src/services/api.ts      ← Axios 封装                 │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 当前调用链（/api/trip/plan）

```
[浏览器 Home.vue]
  │ 用户填写城市、日期、偏好
  │ handleSubmit() → generateTripPlan(formData)
  │
  ▼
[api.ts]  axios.post('/api/trip/plan', formData)
  │ Vite proxy: /api → localhost:8000
  ▼
[FastAPI main.py]  trip.router → POST /api/trip/plan
  ▼
[routes/trip.py]  get_trip_planner_agent().plan_trip(request)
  ▼
[trip_planner_agent.py]
  │ Step1: attraction_agent.run()   → [TOOL_CALL:amap_maps_text_search:...]
  │ Step2: weather_agent.run()      → [TOOL_CALL:amap_maps_weather:...]
  │ Step3: hotel_agent.run()        → [TOOL_CALL:amap_maps_text_search:...]
  │ Step4: planner_agent.run()      → 综合前三步 + JSON Schema → 结构化JSON
  │ _parse_response() → TripPlan.model_validate()
  ▼
[TripPlanResponse] → 浏览器
  │ sessionStorage.setItem('tripPlan', JSON.stringify(data))
  │ router.push('/result')
  ▼
[Result.vue]  initMap() + 展示行程
```

---

## 第二部分：可复用 vs 需替换分析

### 2.1 逐文件分析

| 文件 | 复用度 | 操作 | 原因 |
|------|--------|------|------|
| **完全复用（不改）** ||||
| `backend/app/services/llm_service.py` | 100% | **不动** | LLM 单例与领域无关 |
| `frontend/vite.config.ts` | 100% | **不动** | Vite + Vue + 代理完全通用 |
| `frontend/tsconfig.json` | 100% | **不动** | TS 编译配置通用 |
| `backend/.gitignore` | 100% | **不动** | Python 通用 |
| `frontend/.gitignore` | 100% | **不动** | 前端通用 |
| **小幅修改（保留骨架）** ||||
| `backend/run.py` | 95% | **改 import 路径** | uvicorn 启动逻辑通用 |
| `backend/app/__init__.py` | 90% | **改版本号和描述** | 包声明 |
| `backend/app/api/main.py` | 85% | **改 title + 替换路由** | FastAPI 工厂 + CORS 通用 |
| `backend/app/config.py` | 60% | **删除高德/Unsplash，添加股票 Key** | pydantic-settings 模式复用 |
| `backend/.env` | 40% | **删除高德/Unsplash，添加股票 Key** | 环境变量结构复用 |
| `backend/requirements.txt` | 70% | **保留框架，加股票库** | hello-agents, fastapi, uvicorn 保留 |
| `frontend/src/main.ts` | 80% | **改路由** | Vue App + Antd 注册复用 |
| `frontend/src/App.vue` | 80% | **改标题** | 布局壳复用 |
| `frontend/src/services/api.ts` | 70% | **改 API 函数** | Axios 实例 + 拦截器复用 |
| `frontend/package.json` | 60% | **删除 amap，添加 echarts** | 框架依赖保留 |
| `frontend/.env` | 50% | **删除高德 Key** | VITE_API_BASE_URL 保留 |
| `frontend/index.html` | 80% | **改 title** | HTML 骨架复用 |
| **完全重写（领域绑定）** ||||
| `backend/app/models/schemas.py` | 10% | **重写** | 全部旅行语义 |
| `backend/app/agents/trip_planner_agent.py` | 20% | **重写（模式复用）** | Agent 骨架可参考 |
| `backend/app/api/routes/trip.py` | 15% | **重写** | 旅行端点 |
| `backend/app/api/routes/map.py` | 0% | **删除** | 地图端点 |
| `backend/app/api/routes/poi.py` | 0% | **删除** | POI 端点 |
| `backend/app/services/amap_service.py` | 10% | **删除（模式复用）** | 高德 MCP |
| `backend/app/services/unsplash_service.py` | 5% | **删除** | 图片服务 |
| `frontend/src/types/index.ts` | 10% | **重写** | 全部旅行类型 |
| `frontend/src/views/Home.vue` | 20% | **重写（交互模式复用）** | 旅行表单 |
| `frontend/src/views/Result.vue` | 20% | **重写（布局模式复用）** | 行程展示 |

---

## 第三部分：股票分析助手新架构设计

### 3.1 目标架构图

```
backend/
├── .env                              # LLM + 股票数据 API Key
├── requirements.txt                  # + akshare, stock_mcp 依赖
├── run.py                            # 启动入口（不改）
└── app/
    ├── __init__.py
    ├── config.py                     # Settings: 删除高德/Unsplash，添加股票相关
    ├── api/
    │   ├── __init__.py
    │   ├── main.py                   # FastAPI: title="智能股票分析助手"，注册 stock+analysis 路由
    │   └── routes/
    │       ├── __init__.py
    │       ├── stock.py              # NEW: GET /api/stock/quote, /api/stock/search, /api/stock/history
    │       └── analysis.py           # NEW: POST /api/stock/analyze  (核心分析端点)
    ├── models/
    │   ├── __init__.py
    │   └── schemas.py                # NEW: StockQueryRequest, AnalysisReport, StockQuote, ...
    ├── agents/
    │   ├── __init__.py
    │   └── stock_analyst_agent.py    # NEW: 4-Agent 股票分析系统
    └── services/
        ├── __init__.py
        ├── llm_service.py            # 不改
        └── stock_data_service.py     # NEW: AKShare 数据获取 + MCP 包装
```

### 3.2 新 Agent 架构（对应旅行助手的 4 Agent 模式）

```
MultiAgentStockAnalyst
│
├─ MCPTool("stock")              ← uvx china-stock-mcp-server
│                                   (AKShare: 行情/技术指标/财务/新闻)
│
├─ technical_agent               SimpleAgent("技术面分析专家")
│   system_prompt: K线形态、均线、MACD/RSI/KDJ、成交量分析
│   tool: MCPTool("stock")
│   调用: [TOOL_CALL:stock_technical: symbol=000001, period=daily]
│
├─ fundamental_agent             SimpleAgent("基本面分析专家")
│   system_prompt: PE/PB/ROE、营收利润、行业对比、估值分析
│   tool: MCPTool("stock")
│   调用: [TOOL_CALL:stock_fundamentals: symbol=000001]
│
├─ sentiment_agent               SimpleAgent("市场情绪分析专家")
│   system_prompt: 新闻舆情、资金流向、机构评级、市场热度
│   tool: MCPTool("stock")
│   调用: [TOOL_CALL:stock_news: symbol=000001]
│
└─ report_agent                  SimpleAgent("综合报告专家")  ← 无 Tool
    system_prompt: JSON Schema for AnalysisReport
    输入: 前三步结果 + 用户查询
    输出: 结构化 JSON 分析报告
```

### 3.3 新数据流程图（/api/stock/analyze）

```
[浏览器 Home.vue]
  │ 用户输入股票代码、分析类型、可选日期范围
  │ handleSubmit() → analyzeStock(formData)
  │
  ▼
[api.ts]  axios.post('/api/stock/analyze', formData)
  │ Vite proxy: /api → localhost:8000
  ▼
[FastAPI main.py]  analysis.router → POST /api/stock/analyze
  ▼
[routes/analysis.py]  get_stock_analyst().analyze_stock(request)
  ▼
[stock_analyst_agent.py]
  │ Step1: technical_agent.run()    → [TOOL_CALL:stock_technical:...]
  │ Step2: fundamental_agent.run()  → [TOOL_CALL:stock_fundamentals:...]
  │ Step3: sentiment_agent.run()    → [TOOL_CALL:stock_news:...]
  │ Step4: report_agent.run()       → JSON Schema → 结构化分析报告
  │ _parse_response() → AnalysisReport.model_validate()
  ▼
[AnalysisResponse] → 浏览器
  │ sessionStorage.setItem('analysisReport', ...)
  │ router.push('/result')
  ▼
[Result.vue]  renderChart() + 展示报告
```

---

## 第四部分：分阶段迁移计划

### 阶段一：基础设施 + 数据模型 + 数据源

**目标：** 后端能启动，基础股票查询端点可用，返回真实数据

**修改的文件（6个）：**

| 文件 | 操作 | 具体改动 |
|------|------|----------|
| `backend/.env` | **修改** | 删除 `AMAP_API_KEY`, `UNSPLASH_*`；新增 `STOCK_MCP_SERVER=china-stock-mcp-server`；保留 LLM 配置 |
| `backend/app/config.py` | **修改** | 删除 `amap_api_key`, `unsplash_*` 字段；新增 `stock_mcp_server` 字段；修改 `validate_config()` 不再检查高德 Key；修改 `print_config()` 打印股票相关配置 |
| `backend/app/models/schemas.py` | **重写** | 全部替换为股票模型（详见下方） |
| `backend/requirements.txt` | **修改** | 添加 `akshare>=1.14.0`；保留 `hello-agents[protocols]`, `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `httpx`, `loguru` |
| `backend/app/services/stock_data_service.py` | **新建** | 参考 `amap_service.py` 的 MCPTool 模式，封装 china-stock-mcp-server |
| `backend/app/api/routes/stock.py` | **新建** | 基础查询端点 |

**新建的 schemas.py 关键模型：**
```python
# 请求模型
class StockAnalysisRequest(BaseModel):
    symbol: str                    # 股票代码，如 "000001" 或 "AAPL"
    market: str = "A"              # A/HK/US
    analysis_type: str = "comprehensive"  # technical/fundamental/sentiment/comprehensive
    date_range: str = "3m"         # 1m/3m/6m/1y

# 响应模型
class StockQuote(BaseModel):
    symbol, name, price, change, change_percent, volume, amount,
    high, low, open, prev_close, turnover_rate

class TechnicalIndicator(BaseModel):
    name, value, signal(buy/sell/neutral), description

class FundamentalData(BaseModel):
    pe_ratio, pb_ratio, market_cap, revenue, profit, eps, roe, ...

class SentimentItem(BaseModel):
    source, title, summary, sentiment(positive/negative/neutral), timestamp

class AnalysisReport(BaseModel):
    symbol, company_name, market, generated_at,
    summary,                         # LLM 生成的摘要
    technical_analysis: TechnicalSection,
    fundamental_analysis: FundamentalSection,
    sentiment_analysis: SentimentSection,
    overall_rating: str,            # "强烈买入"/"买入"/"持有"/"卖出"/"强烈卖出"
    risks: List[str],
    suggestions: str

class AnalysisResponse(BaseModel):
    success: bool
    message: str
    data: Optional[AnalysisReport]
```

**新建的 stock_data_service.py 模式（参考 amap_service.py）：**
```python
# 单例 MCPTool
_stock_mcp_tool = None

def get_stock_mcp_tool() -> MCPTool:
    global _stock_mcp_tool
    if _stock_mcp_tool is None:
        _stock_mcp_tool = MCPTool(
            name="stock",
            description="A股股票数据服务",
            server_command=["uvx", "china-stock-mcp-server"],
            auto_expand=True
        )
    return _stock_mcp_tool

class StockDataService:
    def get_realtime_quote(self, symbol: str) -> StockQuote: ...
    def get_history(self, symbol: str, period: str) -> List[dict]: ...
    def get_fundamentals(self, symbol: str) -> FundamentalData: ...
```

**新建的路由 stock.py：**
```python
router = APIRouter(prefix="/stock", tags=["股票数据"])

@router.get("/quote/{symbol}")     # 实时行情
@router.get("/history/{symbol}")   # 历史K线 (query: period=1m/3m/6m/1y)
@router.get("/search")             # 股票搜索 (query: keyword)
@router.get("/health")
```

**还需要修改 main.py：**
- 删除 `from .routes import trip, poi, map as map_routes`
- 替换为 `from .routes import stock, analysis`
- 替换 `app.include_router()` 调用
- 修改 `title="智能股票分析助手"`

**风险：**
- `china-stock-mcp-server` 可能网络不稳定或接口变更
- AKShare 数据源可能偶发不可用

**测试方法：**
1. `cd backend && python run.py` — 确认启动无报错
2. 浏览器打开 `http://localhost:8000/docs` — 确认 Swagger UI 显示新端点
3. `curl http://localhost:8000/api/stock/health` — 返回 200
4. `curl http://localhost:8000/api/stock/quote/000001` — 返回平安银行实时行情 JSON
5. `curl http://localhost:8000/health` — 返回 healthy

---

### 阶段二：多 Agent 分析系统

**目标：** 实现核心技术面+基本面+情绪面+综合报告的四 Agent 协同分析

**修改的文件（3个）：**

| 文件 | 操作 | 具体改动 |
|------|------|----------|
| `backend/app/agents/stock_analyst_agent.py` | **新建** | 4 Agent 系统，参考 trip_planner_agent.py 的完整架构 |
| `backend/app/api/routes/analysis.py` | **新建** | POST /api/stock/analyze 端点，参考 trip.py |
| `backend/app/api/main.py` | **修改** | 注册 analysis.router |

**stock_analyst_agent.py 详细设计（1:1 映射旅行助手）：**

```python
# ===== Agent System Prompts =====

TECHNICAL_AGENT_PROMPT = """你是技术面分析专家。
必须使用工具获取真实数据！
工具格式: [TOOL_CALL:stock_technical: symbol=股票代码, period=日线]

分析维度:
1. 价格走势(涨跌幅、振幅)
2. 均线系统(MA5/MA10/MA20/MA60)
3. MACD(金叉死叉)
4. RSI(超买超卖)
5. KDJ
6. 成交量(放量缩量)
7. 布林带位置
"""

FUNDAMENTAL_AGENT_PROMPT = """你是基本面分析专家。
工具格式: [TOOL_CALL:stock_fundamentals: symbol=股票代码]

分析维度:
1. 估值(PE/PB/PS)
2. 盈利能力(ROE/ROA/毛利率/净利率)
3. 成长性(营收增速/利润增速)
4. 财务健康(资产负债率/流动比率)
5. 行业对比
"""

SENTIMENT_AGENT_PROMPT = """你是市场情绪分析专家。
工具格式: [TOOL_CALL:stock_news: symbol=股票代码]

分析维度:
1. 近期新闻及影响
2. 资金流向(主力/散户)
3. 机构持仓变化
4. 融资融券
5. 市场关注度
"""

REPORT_AGENT_PROMPT = """你是综合报告专家(无工具)。
输入: 技术面、基本面、情绪面三个分析结果
输出: 严格JSON格式的综合分析报告
Schema: { "symbol": "...", "company_name": "...", "summary": "...",
  "technical_analysis": { "score": 0-100, "summary": "...", "indicators": [...] },
  "fundamental_analysis": { "score": 0-100, "summary": "...", "data": {...} },
  "sentiment_analysis": { "score": 0-100, "summary": "...", "items": [...] },
  "overall_rating": "买入/持有/卖出",
  "risks": [...], "suggestions": "..." }
"""

# ===== MultiAgentStockAnalyst =====

class MultiAgentStockAnalyst:
    def __init__(self):
        self.stock_tool = MCPTool(
            name="stock",
            server_command=["uvx", "china-stock-mcp-server"],
            auto_expand=True
        )
        self.technical_agent = SimpleAgent("技术面分析专家", llm, TECHNICAL_AGENT_PROMPT)
        self.technical_agent.add_tool(self.stock_tool)
        
        self.fundamental_agent = SimpleAgent("基本面分析专家", llm, FUNDAMENTAL_AGENT_PROMPT)
        self.fundamental_agent.add_tool(self.stock_tool)
        
        self.sentiment_agent = SimpleAgent("市场情绪分析专家", llm, SENTIMENT_AGENT_PROMPT)
        self.sentiment_agent.add_tool(self.stock_tool)
        
        self.report_agent = SimpleAgent("综合报告专家", llm, REPORT_AGENT_PROMPT)
        # 无工具

    def analyze_stock(self, request: StockAnalysisRequest) -> AnalysisReport:
        # Step1: 技术面
        tech_query = f"[TOOL_CALL:stock_technical:symbol={request.symbol}]"
        tech_result = self.technical_agent.run(tech_query)
        
        # Step2: 基本面
        funda_query = f"[TOOL_CALL:stock_fundamentals:symbol={request.symbol}]"
        funda_result = self.fundamental_agent.run(funda_query)
        
        # Step3: 情绪面
        senti_query = f"[TOOL_CALL:stock_news:symbol={request.symbol}]"
        senti_result = self.sentiment_agent.run(senti_query)
        
        # Step4: 综合
        report_query = self._build_report_query(request, tech_result, funda_result, senti_result)
        report_result = self.report_agent.run(report_query)
        
        return self._parse_response(report_result)
```

**新建的 analysis.py 路由（参考 trip.py：13-61 行）：**
```python
router = APIRouter(prefix="/stock", tags=["股票分析"])

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_stock(request: StockAnalysisRequest):
    agent = get_stock_analyst()
    report = agent.analyze_stock(request)
    return AnalysisResponse(success=True, message="分析完成", data=report)
```

**风险：**
- LLM 可能不遵循 `[TOOL_CALL:...]` 格式，导致 Agent 跳过工具调用
- china-stock-mcp-server 返回数据格式与 Agent Prompt 期望不匹配
- Fallback 数据需要覆盖 A 股常见股票

**测试方法：**
1. 确认阶段一所有测试仍通过
2. `curl -X POST http://localhost:8000/api/stock/analyze -H "Content-Type: application/json" -d '{"symbol":"000001","market":"A","analysis_type":"comprehensive"}'`
3. 验证返回 JSON 包含 `technical_analysis`, `fundamental_analysis`, `sentiment_analysis`, `overall_rating`
4. 后端控制台应打印 4 步 Agent 执行日志
5. 断开 MCP Server → 验证 fallback plan 是否生成兜底报告

---

### 阶段三：前端改造

**目标：** 将旅行 UI 完全替换为股票分析 UI

**修改的文件（8个）：**

| 文件 | 操作 | 具体改动 |
|------|------|----------|
| `frontend/src/types/index.ts` | **重写** | 替换全部旅行为股票类型（匹配阶段一的后端 schema） |
| `frontend/src/services/api.ts` | **修改** | `generateTripPlan()` → `analyzeStock()`；新增 `getStockQuote()` |
| `frontend/src/views/Home.vue` | **重写** | 旅行表单 → 股票查询表单 |
| `frontend/src/views/Result.vue` | **重写** | 行程展示 → 分析报告展示（K线图+报告卡片） |
| `frontend/src/main.ts` | **修改** | 路由名称 `Home`/`Result` → `Search`/`Report`（路径可不变） |
| `frontend/src/App.vue` | **修改** | 标题 "智能旅行助手" → "智能股票分析助手" |
| `frontend/index.html` | **修改** | `<title>` 标签 |
| `frontend/package.json` | **修改** | 删除 `@amap/amap-jsapi-loader`, `html2canvas`, `jspdf`；添加 `echarts`, `vue-echarts` |
| `frontend/.env` | **修改** | 删除 `VITE_AMAP_WEB_KEY`, `VITE_AMAP_WEB_JS_KEY` |

**Home.vue 改造映射：**

| 旅行表单元素 | → | 股票查询元素 |
|-------------|-----|-------------|
| 目的地城市 `<a-input>` | → | 股票代码/名称 `<a-auto-complete>` (支持搜索) |
| 开始/结束日期 `<a-date-picker>` | → | 分析时间范围 `<a-select>` (1月/3月/6月/1年) |
| 交通方式 `<a-select>` | → | 市场选择 `<a-select>` (A股/港股) |
| 住宿偏好 `<a-select>` | → | 分析类型 `<a-checkbox-group>` (技术面/基本面/情绪面/综合) |
| 旅行偏好标签 | → | 删除或换成关注指标选择 |
| 自由文本输入 | → | 保留（额外分析要求，如"重点关注北向资金"） |
| 提交按钮 | → | 保留，文字改为 "开始分析 📊" |
| 进度条 | → | 保留 |

**Result.vue 改造映射：**

| 旅行展示元素 | → | 股票分析展示 |
|-------------|-----|-------------|
| 侧边导航 (overview/budget/map/days/weather) | → | 侧边导航 (overview/technical/fundamental/sentiment/chart) |
| 行程概览卡片 | → | 分析摘要卡片 (评分、评级、建议) |
| 预算明细 (4格) | → | 关键指标卡片 (最新价/涨跌幅/PE/市值/成交量) |
| 高德地图 (AMap) | → | **ECharts K线图** + 成交量柱状图 + 技术指标叠加 |
| 每日行程面板 (a-collapse) | → | 分析维度面板 (技术面/基本面/情绪面 各自折叠) |
| 景点卡片 (2列网格) | → | 指标卡片网格 (MACD/RSI/KDJ/BOLL 各一张卡片) |
| 酒店卡片 | → | 删除 |
| 餐饮列表 | → | 删除 |
| 天气卡片 | → | 新闻舆情卡片 (标题+情绪标签+时间) |
| 导出 PNG/PDF | → | 保留（导出分析报告） |
| 编辑模式 | → | 删除 |

**K线图组件（ECharts 实现示例）：**
```typescript
// 使用 echarts.init() 渲染 K 线图
// xAxis: 日期
// yAxis: 价格
// series: candlestick (OHLC) + MA5/MA10/MA20 line overlay
// 下方: volume bar chart
```

**风险：**
- ECharts 配置复杂，K线图数据格式需要与后端对齐
- `vue-echarts` 版本兼容性
- sessionStorage 数据结构完全改变，需要确保 Home→Result 数据传递正确

**测试方法：**
1. `cd frontend && npm run dev` — 确认 dev server 启动
2. 打开 `http://localhost:5173` — 看到股票查询表单（非旅行表单）
3. 输入 "000001" → 点击分析 → 进度条 → 跳转结果页
4. 结果页展示：评分卡片 + K线图 + 技术/基本/情绪面板
5. K线图可交互（缩放、hover 显示 OHLC）
6. 导出报告按钮可用

---

### 阶段四：完善与优化

**目标：** 接入更多数据源、优化用户体验、容错增强

**修改的文件（4个）：**

| 文件 | 操作 | 具体改动 |
|------|------|----------|
| `backend/app/services/stock_data_service.py` | **修改** | 添加缓存（5分钟TTL），添加数据源健康检查 |
| `backend/app/agents/stock_analyst_agent.py` | **修改** | 优化 Prompt（根据实测效果调优），完善 fallback 数据 |
| `frontend/src/views/Result.vue` | **修改** | 添加多股票对比视图，优化移动端响应式 |
| `README.md` | **新建** | 项目说明文档 |

**优化项：**

1. **缓存机制**（参考 stock_mcp 的 5 分钟缓存）：
   - StockDataService 添加 `@lru_cache` 或手动 TTL 缓存
   - 避免频繁调用 MCP Server

2. **多股票对比**：
   - 新增 `POST /api/stock/compare` 端点
   - 前端添加对比模式（最多 5 只股票）

3. **自选股功能**（前端 localStorage）：
   - Home.vue 添加 "自选列表" 快捷入口
   - 保存最近查询的股票代码到 localStorage

4. **错误处理增强**：
   - MCP Server 不可用时自动降级到 AKShare 直接调用
   - Agent 某一步失败时跳过该维度继续分析

5. **前端优化**：
   - K线图添加技术指标叠加切换（MA/MACD/RSI/BOLL）
   - 添加暗色主题支持

**风险：**
- 缓存可能导致数据显示不及时（缓存时间需要权衡）
- 多股票对比增加 LLM token 消耗

**测试方法：**
1. 端到端测试：前端输入 → 后端分析 → 前端展示
2. 断开 MCP Server → 验证降级是否正常
3. 快速连续请求同一股票 → 验证缓存命中
4. 多股票对比功能测试
5. `npm run build` + `npm run preview` → 验证生产构建

---

## 第五部分：文件改动总览

### 阶段一改动清单
```
修改: backend/.env
修改: backend/app/config.py
重写: backend/app/models/schemas.py
修改: backend/requirements.txt
新建: backend/app/services/stock_data_service.py
新建: backend/app/api/routes/stock.py
修改: backend/app/api/main.py
```

### 阶段二改动清单
```
新建: backend/app/agents/stock_analyst_agent.py
新建: backend/app/api/routes/analysis.py
修改: backend/app/api/main.py (注册 analysis 路由)
```

### 阶段三改动清单
```
重写: frontend/src/types/index.ts
修改: frontend/src/services/api.ts
重写: frontend/src/views/Home.vue
重写: frontend/src/views/Result.vue
修改: frontend/src/main.ts
修改: frontend/src/App.vue
修改: frontend/index.html
修改: frontend/package.json
修改: frontend/.env
```

### 阶段四改动清单
```
修改: backend/app/services/stock_data_service.py (缓存)
修改: backend/app/agents/stock_analyst_agent.py (Prompt调优)
修改: frontend/src/views/Result.vue (多股票对比)
新建: README.md
```

### 删除的文件（整个迁移完成后）
```
backend/app/api/routes/trip.py     → 被 analysis.py 替代
backend/app/api/routes/map.py      → 不需要
backend/app/api/routes/poi.py      → 不需要
backend/app/agents/trip_planner_agent.py → 被 stock_analyst_agent.py 替代
backend/app/services/amap_service.py     → 被 stock_data_service.py 替代
backend/app/services/unsplash_service.py → 不需要
```

---

## 第六部分：关键技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| A 股数据源 | `china-stock-mcp-server` (AKShare) | 零成本、无需注册、A 股数据最全 |
| MCP 集成方式 | 保持 `[TOOL_CALL:...]` 显式语法 | 与旅行助手架构完全一致，改动最小 |
| Agent 数量 | 4 个（技术/基本/情绪/报告） | 1:1 映射旅行助手的景点/天气/酒店/规划 |
| 图表库 | ECharts | 支持 K线图 candlestick，中文社区成熟 |
| 状态传递 | 保持 sessionStorage | 不引入额外依赖，与现有模式一致 |
| LLM | 保持 deepseek-v4-pro | 已在 .env 中配置，无需改动 |
| 前端框架 | 保持 Vue 3 + Ant Design Vue | 不改框架，只替换页面内容 |

---

## 第七部分：可用的 A 股 MCP Server 详情

### 推荐使用：peikuo/china-stock-mcp-server

- **GitHub**: https://github.com/peikuo/china-stock-mcp-server
- **安装**: `uvx china-stock-mcp-server`
- **数据源**: AKShare（完全免费，无需注册）
- **覆盖**: A股/B股/指数/ETF
- **工具**: 实时行情、日/分钟/tick 历史K线、基本面、板块分析、资金流向
- **协议**: FastMCP (STDIO)，与 hello-agents MCPTool 兼容

### 备选：jwangkun/stock_mcp

- **GitHub**: https://github.com/jwangkun/stock_mcp
- **特色**: 内置技术指标(MA/MACD/RSI/BOLL/KDJ)、市场情绪、新闻
- **缓存**: 5 分钟 TTL

### 备选：stockreport-mcp

- 多市场覆盖（A股+港股+美股）
- 双数据源（AKShare + Baostock）智能切换
