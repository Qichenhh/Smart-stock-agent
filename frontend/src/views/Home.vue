<template>
  <div class="home-container">
    <div class="page-header">
      <h1 class="page-title">智能股票分析助手</h1>
      <p class="page-subtitle">多Agent协同分析 · 技术面 + 基本面 + 情绪面 → 综合报告</p>
    </div>

    <!-- 新闻预警通知 -->
    <a-alert
      v-for="alert in newsAlerts.slice(0, 3)"
      :key="alert.title"
      :message="alert.title"
      :type="alert.impact === 'negative' ? 'error' : alert.impact === 'positive' ? 'success' : 'info'"
      :description="alert.summary"
      closable
      show-icon
      style="margin-bottom: 12px; max-width: 700px; margin-left: auto; margin-right: auto"
    />

    <a-card class="form-card" :bordered="false">
      <a-form :model="formData" layout="vertical" @finish="handleSubmit">

        <!-- 股票代码 -->
        <div class="form-section">
          <div class="section-title">股票代码</div>
          <a-form-item name="symbol" :rules="[{ required: true, message: '请输入股票代码' }]">
            <a-auto-complete
              v-model:value="formData.symbol"
              :options="searchOptions"
              placeholder="输入代码或名称搜索，如 000001 或 平安银行"
              size="large"
              @search="onSearch"
              @select="onSelectStock"
            >
              <template #option="{ value, label, industry }">
                <div style="display: flex; justify-content: space-between">
                  <span>{{ value }} - {{ label }}</span>
                  <span v-if="industry" style="color: #999">{{ industry }}</span>
                </div>
              </template>
            </a-auto-complete>
          </a-form-item>
        </div>

        <!-- 分析参数 -->
        <div class="form-section">
          <div class="section-title">分析参数</div>
          <a-row :gutter="16">
            <a-col :span="8">
              <a-form-item label="市场">
                <a-select v-model:value="formData.market" size="large">
                  <a-select-option value="A">A股</a-select-option>
                  <a-select-option value="HK">港股</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item label="分析类型">
                <a-select v-model:value="formData.analysis_type" size="large">
                  <a-select-option value="comprehensive">综合分析</a-select-option>
                  <a-select-option value="technical">技术面</a-select-option>
                  <a-select-option value="fundamental">基本面</a-select-option>
                  <a-select-option value="sentiment">情绪面</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item label="时间范围">
                <a-select v-model:value="formData.date_range" size="large">
                  <a-select-option value="1m">近1个月</a-select-option>
                  <a-select-option value="3m">近3个月</a-select-option>
                  <a-select-option value="6m">近6个月</a-select-option>
                  <a-select-option value="1y">近1年</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
          </a-row>
        </div>

        <!-- 额外要求 -->
        <div class="form-section">
          <div class="section-title">额外要求（可选）</div>
          <a-form-item name="free_text_input">
            <a-textarea
              v-model:value="formData.free_text_input"
              placeholder="例如：重点关注北向资金流向、与同行业对比、给出具体买卖点位建议..."
              :rows="3"
              size="large"
            />
          </a-form-item>
        </div>

        <!-- 提交 -->
        <a-form-item>
          <a-space style="width: 100%" direction="vertical">
            <a-button type="primary" html-type="submit" :loading="loading" size="large" block>
              {{ loading ? '分析中...' : '开始分析' }}
            </a-button>
            <a-button type="dashed" @click="$router.push('/compare')" size="large" block>
              多股票对比
            </a-button>
            <a-button type="dashed" @click="$router.push('/sectors')" size="large" block>
              板块热度
            </a-button>
            <a-button :type="newsSubscribed ? 'primary' : 'default'" @click="toggleNewsAlert" size="large" block>
              {{ newsSubscribed ? '新闻预警 ON' : '订阅新闻预警' }}
            </a-button>
          </a-space>
        </a-form-item>

        <!-- 进度条 -->
        <div v-if="loading" style="margin-top: 16px">
          <a-progress :percent="progress" status="active" :stroke-color="{ from: '#108ee9', to: '#87d068' }" />
          <div style="text-align: center; margin-top: 8px; color: #999">{{ statusText }}</div>
        </div>
      </a-form>
    </a-card>

    <!-- 新闻推送面板 -->
    <div v-if="newsSubscribed || newsAlerts.length > 0" class="news-feed-panel">
      <div class="news-feed-header">
        <span>📡 新闻预警 · {{ formData.symbol || '--' }}</span>
        <a-tag v-if="newsSubscribed" color="green">实时推送中</a-tag>
        <a-tag v-else color="default">已断开</a-tag>
      </div>
      <div class="news-feed-list" v-if="newsAlerts.length > 0">
        <div
          v-for="(alert, i) in newsAlerts"
          :key="i"
          class="news-feed-item"
          :class="'impact-' + alert.impact"
        >
          <div class="news-feed-time">{{ alert.time }}</div>
          <div class="news-feed-tag">
            <a-badge
              :status="alert.impact === 'positive' ? 'success' : alert.impact === 'negative' ? 'error' : 'processing'"
            />
            {{ alert.level === 'high' ? '重要' : alert.level === 'medium' ? '中等' : '一般' }}
          </div>
          <div class="news-feed-title">{{ alert.title }}</div>
        </div>
      </div>
      <a-empty v-else description="等待第一条预警...（每60秒轮询）" :image="false" style="padding: 20px" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { analyzeStock, searchStock } from '@/services/api'
import type { StockAnalysisRequest, StockSearchResult } from '@/types'

const router = useRouter()

const formData = reactive<StockAnalysisRequest>({
  symbol: '',
  market: 'A',
  analysis_type: 'comprehensive',
  date_range: '3m',
  free_text_input: '',
})

const loading = ref(false)
const progress = ref(0)
const statusText = ref('')
const searchOptions = ref<{ value: string; label: string; industry?: string }[]>([])
const newsSubscribed = ref(false)
const newsAlerts = ref<any[]>([])
let alertSocket: WebSocket | null = null

let progressTimer: any = null

// 股票搜索（输入时防抖）
let searchTimer: any = null
function onSearch(keyword: string) {
  if (searchTimer) clearTimeout(searchTimer)
  if (!keyword || keyword.length < 1) {
    searchOptions.value = []
    return
  }
  searchTimer = setTimeout(async () => {
    try {
      const res = await searchStock(keyword)
      if (res.success && res.data) {
        searchOptions.value = res.data.map((s: StockSearchResult) => ({
          value: s.symbol,
          label: s.name,
          industry: s.industry,
        }))
      }
    } catch { /* ignore */ }
  }, 400)
}

function onSelectStock(value: string, option: any) {
  formData.symbol = value
}

// 提交分析（WebSocket 实时进度）
async function handleSubmit() {
  if (!formData.symbol) {
    message.warning('请输入股票代码')
    return
  }

  loading.value = true
  progress.value = 0
  statusText.value = '正在连接...'

  const wsUrl = `ws://localhost:8000/api/stock/ws/analyze`
  const ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    ws.send(JSON.stringify({ ...formData }))
  }

  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data)
    if (msg.type === 'start') {
      progress.value = 5
      statusText.value = '开始分析 ' + msg.symbol + '...'
    } else if (msg.type === 'progress') {
      const stepPct = Math.min(msg.step * 22, 90)
      progress.value = stepPct
      statusText.value = `[${msg.step}/4] ${msg.text}`
    } else if (msg.type === 'done') {
      progress.value = 100
      statusText.value = '分析完成！'
      ws.close()
      sessionStorage.setItem('analysisReport', JSON.stringify(msg.data))
      message.success('分析完成')
      setTimeout(() => router.push('/result'), 300)
    } else if (msg.type === 'error') {
      progress.value = 0
      statusText.value = ''
      ws.close()
      message.error(msg.message || '分析失败')
    }
  }

  ws.onerror = () => {
    // WebSocket 连接失败，回退到 REST API
    console.warn('[WS] WebSocket 不可用，使用 REST API')
    ws.close()
    fallbackRestAPI()
  }

  ws.onclose = () => {
    loading.value = false
  }
}

// REST API 兜底（WebSocket 不可用时）
async function fallbackRestAPI() {
  progress.value = 10
  statusText.value = '正在获取实时行情...'
  progressTimer = setInterval(() => {
    if (progress.value < 30) progress.value += 2
    else if (progress.value < 50) { progress.value += 1; statusText.value = 'Agent 分析中 (技术面)...' }
    else if (progress.value < 70) { progress.value += 0.5; statusText.value = 'Agent 分析中 (基本面+情绪面)...' }
    else if (progress.value < 90) { progress.value += 0.3; statusText.value = '正在生成综合报告...' }
  }, 500)

  try {
    const response = await analyzeStock({ ...formData })
    if (progressTimer) clearInterval(progressTimer)
    progress.value = 100
    statusText.value = '分析完成！'
    if (response.success && response.data) {
      sessionStorage.setItem('analysisReport', JSON.stringify(response.data))
      message.success('分析完成')
      setTimeout(() => router.push('/result'), 500)
    } else {
      message.error(response.message || '分析失败')
    }
  } catch (e: any) {
    if (progressTimer) clearInterval(progressTimer)
    message.error(e.response?.data?.detail || e.message || '请求失败')
  } finally {
    setTimeout(() => { loading.value = false; progress.value = 0; statusText.value = '' }, 1000)
  }
}

// 新闻预警订阅
function toggleNewsAlert() {
  if (newsSubscribed.value) {
    // 取消订阅
    if (alertSocket) {
      alertSocket.send(JSON.stringify({ action: 'unsubscribe', symbols: [formData.symbol] }))
      alertSocket.close()
      alertSocket = null
    }
    newsSubscribed.value = false
    newsAlerts.value = []
    message.info('已取消新闻预警')
    return
  }

  if (!formData.symbol) {
    message.warning('请先输入股票代码')
    return
  }

  const wsUrl = 'ws://localhost:8000/api/stock/ws/alerts'
  alertSocket = new WebSocket(wsUrl)

  alertSocket.onopen = () => {
    alertSocket!.send(JSON.stringify({
      action: 'subscribe',
      symbols: [formData.symbol]
    }))
  }

  alertSocket.onmessage = (e) => {
    const msg = JSON.parse(e.data)
    if (msg.type === 'subscribed') {
      newsSubscribed.value = true
      message.success(msg.message)
    } else if (msg.type === 'alert') {
      // 新预警添加到列表顶部
      newsAlerts.value.unshift(msg)
      // 浏览器通知（如果已授权）
      if (Notification.permission === 'granted') {
        new Notification(`[${msg.symbol}] ${msg.impact === 'positive' ? '利好' : msg.impact === 'negative' ? '利空' : '消息'}`, {
          body: msg.title,
          icon: '/vite.svg'
        })
      }
    } else if (msg.type === 'ping') {
      // 心跳，忽略
    }
  }

  alertSocket.onerror = () => {
    newsSubscribed.value = false
    message.warning('WebSocket 连接失败，无法订阅新闻预警')
  }

  alertSocket.onclose = () => {
    newsSubscribed.value = false
  }

  // 请求浏览器通知权限
  if (Notification.permission === 'default') {
    Notification.requestPermission()
  }
}
</script>

<style scoped>
.home-container {
  max-width: 700px;
  margin: 0 auto;
  padding: 40px 20px;
}

.page-header {
  text-align: center;
  margin-bottom: 32px;
}

.page-title {
  font-size: 32px;
  font-weight: bold;
  color: #1a1a2e;
  margin: 0 0 8px 0;
}

.page-subtitle {
  font-size: 14px;
  color: #888;
  margin: 0;
}

.form-card {
  border-radius: 12px;
  box-shadow: 0 2px 16px rgba(0,0,0,0.06);
}

.form-section {
  margin-bottom: 20px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
  padding-left: 4px;
  border-left: 3px solid #1890ff;
}

/* 新闻推送面板 */
.news-feed-panel {
  max-width: 700px;
  margin: 24px auto;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 16px rgba(0,0,0,0.06);
  overflow: hidden;
}
.news-feed-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 20px;
  background: #f5f5f5;
  font-size: 15px;
  font-weight: 600;
  border-bottom: 1px solid #eee;
}
.news-feed-list {
  max-height: 420px;
  overflow-y: auto;
}
.news-feed-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 20px;
  border-bottom: 1px solid #f0f0f0;
  transition: background 0.2s;
}
.news-feed-item:hover {
  background: #fafafa;
}
.news-feed-item.impact-positive {
  border-left: 3px solid #52c41a;
}
.news-feed-item.impact-negative {
  border-left: 3px solid #ff4d4f;
}
.news-feed-item.impact-neutral {
  border-left: 3px solid #1890ff;
}
.news-feed-time {
  color: #999;
  font-size: 12px;
  white-space: nowrap;
  min-width: 60px;
}
.news-feed-tag {
  font-size: 12px;
  white-space: nowrap;
  min-width: 50px;
}
.news-feed-title {
  font-size: 14px;
  line-height: 1.5;
  flex: 1;
}
</style>
