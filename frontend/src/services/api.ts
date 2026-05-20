import axios from 'axios'
import type {
  StockAnalysisRequest, AnalysisResponse,
  StockQuoteResponse, KLineResponse, StockSearchResponse
} from '@/types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000, // 5分钟（Agent分析需要较长时间）
  headers: { 'Content-Type': 'application/json' }
})

apiClient.interceptors.request.use(
  (config) => { console.log('[API]', config.method?.toUpperCase(), config.url); return config },
  (error) => { console.error('[API] 请求错误:', error); return Promise.reject(error) }
)

apiClient.interceptors.response.use(
  (response) => { console.log('[API]', response.status, response.config.url); return response },
  (error) => { console.error('[API] 响应错误:', error.response?.status, error.message); return Promise.reject(error) }
)

/** 智能股票分析（四Agent协同） */
export async function analyzeStock(formData: StockAnalysisRequest): Promise<AnalysisResponse> {
  const response = await apiClient.post<AnalysisResponse>('/api/stock/analyze', formData)
  return response.data
}

/** 获取实时行情 */
export async function getStockQuote(symbol: string): Promise<StockQuoteResponse> {
  const response = await apiClient.get<StockQuoteResponse>(`/api/stock/quote/${symbol}`)
  return response.data
}

/** 获取历史K线 */
export async function getStockHistory(symbol: string, period = '3m'): Promise<KLineResponse> {
  const response = await apiClient.get<KLineResponse>(`/api/stock/history/${symbol}`, { params: { period } })
  return response.data
}

/** 搜索股票 */
export async function searchStock(keyword: string): Promise<StockSearchResponse> {
  const response = await apiClient.get<StockSearchResponse>('/api/stock/search', { params: { keyword } })
  return response.data
}

/** 健康检查 */
export async function healthCheck() {
  const response = await apiClient.get('/health')
  return response.data
}

export default apiClient
