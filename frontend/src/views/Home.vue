<template>
  <div class="home-container">
    <div class="page-header">
      <h1 class="page-title">智能股票分析助手</h1>
      <p class="page-subtitle">多Agent协同分析 · 技术面 + 基本面 + 情绪面 → 综合报告</p>
    </div>

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
          </a-space>
        </a-form-item>

        <!-- 进度条 -->
        <div v-if="loading" style="margin-top: 16px">
          <a-progress :percent="progress" status="active" :stroke-color="{ from: '#108ee9', to: '#87d068' }" />
          <div style="text-align: center; margin-top: 8px; color: #999">{{ statusText }}</div>
        </div>
      </a-form>
    </a-card>
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

// 模拟进度条
function startProgress() {
  progress.value = 0
  statusText.value = '正在获取实时行情...'
  progressTimer = setInterval(() => {
    if (progress.value < 30) {
      progress.value += 2
      statusText.value = '正在获取实时行情...'
    } else if (progress.value < 50) {
      progress.value += 1
      statusText.value = 'Agent 分析中 (技术面)...'
    } else if (progress.value < 70) {
      progress.value += 0.5
      statusText.value = 'Agent 分析中 (基本面+情绪面)...'
    } else if (progress.value < 90) {
      progress.value += 0.3
      statusText.value = '正在生成综合报告...'
    }
  }, 500)
}

// 提交分析
async function handleSubmit() {
  if (!formData.symbol) {
    message.warning('请输入股票代码')
    return
  }

  loading.value = true
  startProgress()

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
    message.error(e.response?.data?.detail || e.message || '请求失败，请检查后端服务')
  } finally {
    setTimeout(() => {
      loading.value = false
      progress.value = 0
      statusText.value = ''
    }, 1000)
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
</style>
