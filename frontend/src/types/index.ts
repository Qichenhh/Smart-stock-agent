// ============ 请求类型 ============

export interface StockAnalysisRequest {
  symbol: string
  market: string          // A / HK / US
  analysis_type: string   // technical / fundamental / sentiment / comprehensive
  date_range: string      // 1m / 3m / 6m / 1y
  free_text_input?: string
}

// ============ 数据模型 ============

export interface StockQuote {
  symbol: string
  name: string
  price: number
  change: number
  change_percent: number
  volume: number
  amount: number
  high: number
  low: number
  open: number
  prev_close: number
  turnover_rate?: number
  market_cap?: number
}

export interface TechnicalIndicator {
  name: string
  value: string
  signal: 'buy' | 'sell' | 'neutral'
  description: string
}

export interface FundamentalData {
  pe_ratio?: number
  pb_ratio?: number
  ps_ratio?: number
  market_cap?: number
  revenue?: number
  net_profit?: number
  eps?: number
  roe?: number
  roa?: number
  gross_margin?: number
  net_margin?: number
  debt_ratio?: number
  current_ratio?: number
  revenue_growth?: number
  profit_growth?: number
}

export interface SentimentItem {
  source: string
  title: string
  summary: string
  sentiment: 'positive' | 'negative' | 'neutral'
  timestamp?: string
}

export interface KLineData {
  date: string
  open: number
  close: number
  high: number
  low: number
  volume: number
  amount?: number
}

// ============ 分析报告 ============

export interface TechnicalSection {
  score: number
  summary: string
  indicators: TechnicalIndicator[]
}

export interface FundamentalSection {
  score: number
  summary: string
  data: FundamentalData
}

export interface SentimentSection {
  score: number
  summary: string
  items: SentimentItem[]
}

export interface AnalysisReport {
  symbol: string
  company_name: string
  market: string
  generated_at: string
  summary: string
  technical_analysis: TechnicalSection
  fundamental_analysis: FundamentalSection
  sentiment_analysis: SentimentSection
  overall_rating: string
  risks: string[]
  suggestions: string
}

// ============ 响应类型 ============

export interface AnalysisResponse {
  success: boolean
  message: string
  data?: AnalysisReport
}

export interface StockQuoteResponse {
  success: boolean
  message: string
  data?: StockQuote
}

export interface KLineResponse {
  success: boolean
  message: string
  data?: KLineData[]
}

export interface StockSearchResult {
  symbol: string
  name: string
  market: string
  industry?: string
}

export interface StockSearchResponse {
  success: boolean
  message: string
  data?: StockSearchResult[]
}
