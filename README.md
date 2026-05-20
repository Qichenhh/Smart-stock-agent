# 智能股票分析助手

基于 HelloAgents 多 Agent 框架的 A 股智能分析系统，4 个 AI Agent 协同完成技术面 + 基本面 + 情绪面 → 综合报告。

## 功能特点

- **多 Agent 协同分析**：技术面 Agent、基本面 Agent、情绪面 Agent、综合报告 Agent 四步流水线
- **实时数据**：baostock + akshare 双数据源自动降级，覆盖行情/K线/财务/新闻
- **智能工具调用**：Agent 通过 `[TOOL_CALL:...]` 协议自动获取真实数据
- **ECharts K线图**：前端 candlestick + 成交量双图，涨红跌绿
- **新闻舆情**：东方财富个股新闻实时抓取，正负面情绪自动分类
- **导出报告**：支持 PNG / PDF 导出分析报告

## 技术栈

| 层 | 技术 |
|----|------|
| Agent 框架 | HelloAgents (SimpleAgent + Tool + @tool_action) |
| LLM | DeepSeek v4-pro |
| 后端 | FastAPI + Pydantic v2 |
| 数据源 | baostock + akshare |
| 前端 | Vue 3 + TypeScript + Vite + Ant Design Vue |
| 图表 | ECharts (candlestick K线) |
| 导出 | html2canvas + jsPDF |

## 项目结构

```
Smart-stock-analyst/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   └── stock_analyst_agent.py   # 4 Agent 系统 + StockDataTool
│   │   ├── api/
│   │   │   ├── main.py                  # FastAPI 应用
│   │   │   └── routes/
│   │   │       ├── stock.py             # 行情/搜索/K线/缓存端点
│   │   │       └── analysis.py          # 分析端点 (Agent 调用入口)
│   │   ├── services/
│   │   │   ├── stock_data_service.py    # 双数据源 + 缓存 + 财务/新闻
│   │   │   └── llm_service.py           # LLM 单例
│   │   ├── models/
│   │   │   └── schemas.py               # Pydantic 数据模型
│   │   └── config.py                    # pydantic-settings 配置
│   ├── requirements.txt
│   ├── run.py
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── Home.vue                 # 股票查询表单 (搜索+参数)
│   │   │   └── Result.vue              # 分析报告 (K线+评分+情绪)
│   │   ├── services/api.ts             # Axios API 封装
│   │   ├── types/index.ts              # TypeScript 类型定义
│   │   ├── main.ts                     # Vue 入口 + 路由
│   │   └── App.vue                     # 根布局
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## 快速启动

### 前提

- Python 3.10+ (conda 环境推荐)
- Node.js 16+
- DeepSeek API Key

### 后端

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 配置 .env（参考 .env.example）
cp .env.example .env
# 编辑 .env: LLM_API_KEY=你的DeepSeek Key

# 启动
python run.py
# API 文档: http://localhost:8000/docs
```

### 前端

```bash
cd frontend

npm install
cp .env.example .env

npm run dev
# 打开 http://localhost:5173
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/stock/analyze` | 核心：四 Agent 协同分析 |
| GET | `/api/stock/quote/{symbol}` | 实时行情 |
| GET | `/api/stock/history/{symbol}` | 历史K线 |
| GET | `/api/stock/search?keyword=` | 股票搜索 |
| GET | `/api/stock/cache` | 缓存统计 |
| POST | `/api/stock/cache/clear` | 清空缓存 |
| GET | `/health` | 服务健康检查 |

## Agent 架构

```
POST /api/stock/analyze
  │
  ├─ Agent 1 (技术面) → stock_quote + stock_history → MACD/RSI/KDJ/均线/成交量
  ├─ Agent 2 (基本面) → stock_quote + stock_financials → PE/PB/ROE/EPS/增长率
  ├─ Agent 3 (情绪面) → stock_quote + stock_news → 行情信号 + 新闻正负面
  └─ Agent 4 (综合报告) → 加权评分 → JSON 报告 (买入/持有/卖出 + 风险 + 建议)
```

每个 Agent 通过 `[TOOL_CALL:tool_name:param=value]` 协议调用工具，HelloAgents 框架自动拦截并执行。

## 致谢

- [HelloAgents](https://github.com/datawhalechina/Hello-Agents) - 智能体框架
- [AKShare](https://github.com/akfamily/akshare) - A 股数据接口
- [Baostock](http://baostock.com) - 证券数据
