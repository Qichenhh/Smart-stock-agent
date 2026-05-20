<template>
  <div class="result-container">
    <div v-if="!report" class="empty-state">
      <a-empty description="暂无分析报告">
        <a-button type="primary" @click="$router.push('/')">返回首页</a-button>
      </a-empty>
    </div>

    <template v-else>
      <div class="result-header">
        <a-button class="back-btn" @click="$router.push('/')">← 返回</a-button>
        <div class="header-main">
          <h2>{{ report.company_name }}</h2>
          <span class="symbol-tag">{{ report.symbol }} · {{ report.market === 'A' ? 'A股' : '港股' }}</span>
        </div>
        <a-tag :color="ratingColor(report.overall_rating)" style="font-size: 18px; padding: 4px 16px">
          {{ report.overall_rating }}
        </a-tag>
      </div>

      <a-card class="section-card" title="分析摘要">
        <p style="white-space: pre-line; line-height: 1.8">{{ report.summary }}</p>
      </a-card>

      <a-row :gutter="16" style="margin: 16px 0">
        <a-col :span="8">
          <a-card hoverable>
            <a-statistic title="技术面评分" :value="report.technical_analysis.score" suffix="/ 100"
              :value-style="{ color: scoreColor(report.technical_analysis.score) }" />
            <p style="margin-top: 8px; color: #666; font-size: 13px">{{ report.technical_analysis.summary }}</p>
          </a-card>
        </a-col>
        <a-col :span="8">
          <a-card hoverable>
            <a-statistic title="基本面评分" :value="report.fundamental_analysis.score" suffix="/ 100"
              :value-style="{ color: scoreColor(report.fundamental_analysis.score) }" />
            <p style="margin-top: 8px; color: #666; font-size: 13px">{{ report.fundamental_analysis.summary }}</p>
          </a-card>
        </a-col>
        <a-col :span="8">
          <a-card hoverable>
            <a-statistic title="情绪面评分" :value="report.sentiment_analysis.score" suffix="/ 100"
              :value-style="{ color: scoreColor(report.sentiment_analysis.score) }" />
            <p style="margin-top: 8px; color: #666; font-size: 13px">{{ report.sentiment_analysis.summary }}</p>
          </a-card>
        </a-col>
      </a-row>

      <a-card class="section-card" title="K线走势图">
        <div ref="chartRef" style="width: 100%; height: 400px"></div>
      </a-card>

      <a-card class="section-card" title="技术指标">
        <a-table
          :columns="indicatorColumns"
          :data-source="report.technical_analysis.indicators"
          :pagination="false"
          row-key="name"
          size="middle"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'signal'">
              <a-tag :color="record.signal === 'buy' ? 'green' : record.signal === 'sell' ? 'red' : 'blue'">
                {{ record.signal === 'buy' ? '买入' : record.signal === 'sell' ? '卖出' : '中性' }}
              </a-tag>
            </template>
          </template>
        </a-table>
      </a-card>

      <a-card v-if="hasFundData" class="section-card" title="基本面数据">
        <a-row :gutter="[16, 16]">
          <a-col v-for="item in fundDataItems" :key="item.label" :span="8">
            <a-statistic :title="item.label" :value="item.value" :value-style="{ fontSize: '18px' }" />
          </a-col>
        </a-row>
      </a-card>

      <a-card v-if="report.sentiment_analysis.items.length" class="section-card" title="市场情绪">
        <a-timeline>
          <a-timeline-item
            v-for="(item, i) in report.sentiment_analysis.items"
            :key="i"
            :color="item.sentiment === 'positive' ? 'green' : item.sentiment === 'negative' ? 'red' : 'blue'"
          >
            <strong>{{ item.title }}</strong>
            <a-tag :color="item.sentiment === 'positive' ? 'green' : item.sentiment === 'negative' ? 'red' : 'blue'" size="small" style="margin-left: 8px">
              {{ item.sentiment === 'positive' ? '正面' : item.sentiment === 'negative' ? '负面' : '中性' }}
            </a-tag>
            <p style="color: #666; margin-top: 4px">{{ item.summary }}</p>
          </a-timeline-item>
        </a-timeline>
      </a-card>

      <a-row :gutter="16" style="margin-top: 16px">
        <a-col :span="12">
          <a-card class="section-card" title="风险提示">
            <ul style="padding-left: 20px; line-height: 2">
              <li v-for="(risk, i) in report.risks" :key="i" style="color: #ff4d4f">{{ risk }}</li>
            </ul>
          </a-card>
        </a-col>
        <a-col :span="12">
          <a-card class="section-card" title="操作建议">
            <p style="white-space: pre-line; line-height: 1.8; color: #333">{{ report.suggestions }}</p>
          </a-card>
        </a-col>
      </a-row>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getStockHistory } from '@/services/api'
import type { AnalysisReport, KLineData } from '@/types'

const report = ref<AnalysisReport | null>(null)
const chartRef = ref<HTMLElement | null>(null)
let chartInstance: any = null

onMounted(async () => {
  const raw = sessionStorage.getItem('analysisReport')
  if (raw) {
    try { report.value = JSON.parse(raw) } catch { /* ignore */ }
  }
  if (report.value) {
    await nextTick()
    await loadChart()
  }
})

async function loadChart() {
  if (!chartRef.value || !report.value) return
  try {
    const res = await getStockHistory(report.value.symbol, '3m')
    if (res.success && res.data && res.data.length > 0) {
      renderChart(res.data)
    }
  } catch { /* ignore */ }
}

function renderChart(klines: KLineData[]) {
  if (!chartRef.value) return
  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)

  const dates = klines.map(k => k.date)
  const ohlc = klines.map(k => [k.open, k.close, k.low, k.high])
  const volumes = klines.map(k => k.volume)

  chartInstance.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    grid: [
      { left: '8%', right: '8%', top: '5%', height: '60%' },
      { left: '8%', right: '8%', top: '72%', height: '20%' }
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 1 }
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, scale: true },
      { type: 'value', gridIndex: 1 }
    ],
    series: [
      {
        name: 'K线', type: 'candlestick', data: ohlc, gridIndex: 0,
        itemStyle: { color: '#ef5350', color0: '#26a69a', borderColor: '#ef5350', borderColor0: '#26a69a' }
      },
      {
        name: '成交量', type: 'bar', data: volumes, gridIndex: 1,
        itemStyle: {
          color: (params: any) => {
            const k = klines[params.dataIndex]
            return k ? (k.close >= k.open ? '#ef5350' : '#26a69a') : '#888'
          }
        }
      }
    ]
  })

  window.addEventListener('resize', () => chartInstance?.resize())
}

const indicatorColumns = [
  { title: '指标', dataIndex: 'name', key: 'name', width: 120 },
  { title: '数值', dataIndex: 'value', key: 'value' },
  { title: '信号', dataIndex: 'signal', key: 'signal', width: 80 },
  { title: '解读', dataIndex: 'description', key: 'description' },
]

const fundDataItems = computed(() => {
  const d = report.value?.fundamental_analysis?.data
  if (!d) return []
  const items: { label: string; value: any }[] = []
  if (d.pe_ratio != null) items.push({ label: '市盈率(PE)', value: d.pe_ratio.toFixed(2) })
  if (d.pb_ratio != null) items.push({ label: '市净率(PB)', value: d.pb_ratio.toFixed(2) })
  if (d.market_cap != null) items.push({ label: '总市值(亿)', value: d.market_cap.toFixed(0) })
  if (d.roe != null) items.push({ label: 'ROE(%)', value: d.roe.toFixed(2) })
  if (d.eps != null) items.push({ label: 'EPS', value: d.eps.toFixed(2) })
  if (d.revenue_growth != null) items.push({ label: '营收增速(%)', value: d.revenue_growth.toFixed(2) })
  return items
})

const hasFundData = computed(() => fundDataItems.value.length > 0)

function ratingColor(rating: string) {
  if (rating.includes('买入')) return 'green'
  if (rating.includes('卖出')) return 'red'
  return 'orange'
}

function scoreColor(score: number) {
  if (score >= 70) return '#3f8600'
  if (score >= 40) return '#faad14'
  return '#cf1322'
}
</script>

<style scoped>
.result-container { max-width: 1000px; margin: 0 auto; padding: 20px; }
.empty-state { text-align: center; padding: 80px 0; }
.result-header {
  display: flex; align-items: center; gap: 16px; margin-bottom: 20px;
  padding: 16px; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.back-btn { flex-shrink: 0; }
.header-main { flex: 1; }
.header-main h2 { margin: 0; font-size: 24px; display: inline; }
.symbol-tag { margin-left: 8px; color: #888; font-size: 14px; }
.section-card { margin-bottom: 16px; border-radius: 8px; }
</style>
