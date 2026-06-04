# 智能股票分析助手

基于 HelloAgents 多 Agent 框架的 A 股智能分析系统。4 个 AI Agent 协同完成技术面 + 基本面 + 情绪面 → 综合报告，配备跨会话 Memory 和金融知识库 RAG。

## 功能特点

- **多 Agent 协同**：技术面(价格/量/指标) → 基本面(PE/PB/ROE) → 情绪面(行情+新闻) → 综合报告
- **实时分析进度**：WebSocket 推送每个 Agent 的执行状态
- **新闻预警推送**：订阅股票后实时推送新闻，自动判断利好/利空及影响等级
- **板块热度分析**：90 个行业板块涨跌幅排行、多空比、成交额
- **实时数据**：baostock + akshare 双数据源自动降级，覆盖行情/K线/财务/新闻
- **跨会话 Memory**：自动记录每次分析，下次查询时对比历史评分变化趋势
- **金融知识库 RAG**：内置估值方法论、技术指标指南、投资原则
- **多股票对比**：并排对比 2-5 只股票，LLM 排名 + 推荐
- **ECharts K线图**：candlestick + 成交量双图，涨红跌绿
- **导出报告**：PNG / PDF 一键导出
- **Docker 部署**：docker-compose up 一键启动

## 技术栈

| 层 | 技术 |
|----|------|
| Agent 框架 | HelloAgents (SimpleAgent + Tool + @tool_action) |
| LLM | DeepSeek v4-pro |
| 后端 | FastAPI + Pydantic v2 |
| 数据源 | baostock + akshare |
| Memory | 轻量 JSON 文件存储，线程安全 |
| RAG | HelloAgents RAGTool + 预置金融知识文本 |
| 缓存 | StockCache 线程安全类，TTL 差异化 (60s~600s) |
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
│   │   │       ├── stock.py             # 行情/搜索/K线/缓存/板块
│   │   │       ├── analysis.py          # Agent + WebSocket
│   │   │       └── compare.py           # 多股票对比
│   │   ├── services/
│   │   │   ├── stock_data_service.py    # 双数据源 + 缓存 + 板块
│   │   │   ├── llm_service.py           # LLM 单例
│   │   │   ├── memory_service.py        # Memory 服务
│   │   │   ├── rag_service.py           # RAG 知识库
│   │   │   └── news_monitor.py          # 新闻监控预警
│   │   ├── models/
│   │   │   └── schemas.py               # Pydantic 数据模型
│   │   └── config.py                    # pydantic-settings 配置
│   ├── knowledge_base/                  # 金融知识库文本
│   ├── memory_data/                     # Memory 存储 (gitignore)
│   ├── requirements.txt
│   ├── run.py
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── Home.vue                 # 查询表单 + 新闻预警面板
│   │   │   ├── Result.vue              # 分析报告 (K线+评分+情绪)
│   │   │   ├── Compare.vue             # 多股票对比
│   │   │   └── SectorHeat.vue          # 板块热度排行
│   │   ├── services/api.ts             # Axios API 封装
│   │   ├── types/index.ts              # TypeScript 类型
│   │   ├── main.ts                     # Vue 入口 + 路由
│   │   └── App.vue                     # 根布局
│   ├── package.json
│   ├── vite.config.ts
│   ├── nginx.conf                      # 生产部署 nginx 配置
│   └── Dockerfile                      # 多阶段构建
├── scripts/
│   └── kill_port.cmd                   # Windows 端口清理
├── docker-compose.yml
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

# 配置 .env
cp .env.example .env
# 编辑 .env: LLM_API_KEY=你的DeepSeek Key

# 启动（端口被占用时用 --kill 自动清理）
python run.py --kill
# API 文档: http://localhost:8000/docs
```

### 前端

```bash
cd frontend
npm install
npm run dev
# 打开 http://localhost:5173
```

### Docker 一键部署

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env 填入 LLM_API_KEY
docker compose up -d
# 访问 http://localhost
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/stock/analyze` | 四 Agent 协同分析 |
| WS | `/api/stock/ws/analyze` | 实时分析进度推送 |
| WS | `/api/stock/ws/alerts` | 新闻预警推送 |
| POST | `/api/stock/compare` | 多股票对比 (2-5只) |
| GET | `/api/stock/quote/{symbol}` | 实时行情 |
| GET | `/api/stock/history/{symbol}` | 历史K线 |
| GET | `/api/stock/search?keyword=` | 股票搜索 |
| GET | `/api/stock/sectors` | 板块热度排行 |
| GET | `/api/stock/cache` | 缓存统计 |
| POST | `/api/stock/cache/clear` | 清空缓存 |
| GET | `/health` | 服务健康检查 |

## Agent 架构

```
POST /api/stock/analyze  (或 WebSocket ws/analyze 实时进度)
  │
  ├─ Agent 1 (技术面) → stock_quote + stock_history → MACD/RSI/KDJ/均线/成交量
  ├─ Agent 2 (基本面) → stock_quote + stock_financials → PE/PB/ROE/EPS/增长率
  ├─ Agent 3 (情绪面) → stock_quote + stock_news → 行情信号 + 新闻正负面
  │
  └─ Agent 4 (综合报告) → Memory检索 + RAG知识库 + 加权评分
       ├─ [TOOL_CALL:memory_search:query=000001历史分析]
       ├─ [TOOL_CALL:rag_search:query=银行业估值]
       └─ → 结构化报告 → memory_record() 存入长期记忆

实时功能:
  ws/analyze  → WebSocket 推送每步进度 (替代假进度条)
  ws/alerts   → WebSocket 新闻预警 (订阅+关键词分析+浏览器通知)
  /sectors    → 板块涨跌幅排行 (同花顺90行业)
```

每个 Agent 通过 `[TOOL_CALL:tool_name:param=value]` 协议调用工具。

## 致谢

- [HelloAgents](https://github.com/datawhalechina/Hello-Agents) - 智能体框架
- [AKShare](https://github.com/akfamily/akshare) - A 股数据接口
- [Baostock](http://baostock.com) - 证券数据
