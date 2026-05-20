<template>
  <div class="compare-container">
    <div class="page-header">
      <a-button class="back-btn" @click="$router.push('/')">← 返回</a-button>
      <h2>多股票对比</h2>
    </div>

    <!-- 输入区 -->
    <a-card class="input-card">
      <a-form layout="inline" @finish="handleCompare">
        <a-form-item label="股票代码" style="flex: 1">
          <a-select
            v-model:value="symbols"
            mode="tags"
            placeholder="输入代码添加，如 000001"
            style="width: 100%"
            :max-tag-count="5"
            @search="onSearch"
          >
            <a-select-option v-for="opt in searchOptions" :key="opt.value" :value="opt.value">
              {{ opt.value }} - {{ opt.label }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" :loading="loading">
            {{ loading ? '对比中...' : '开始对比' }}
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 结果区 -->
    <template v-if="result">
      <!-- LLM 总结 -->
      <a-alert :message="result.analysis?.summary || result.analysis" type="info" show-icon style="margin-bottom: 16px" />

      <!-- 排名 -->
      <a-card v-if="result.analysis?.rankings" title="综合排名" class="section-card">
        <a-row :gutter="16">
          <a-col v-for="r in result.analysis.rankings" :key="r.rank" :span="8">
            <a-card hoverable :style="{ borderTop: '3px solid ' + rankColor(r.rank) }">
              <a-badge :count="'#' + r.rank" :number-style="{ backgroundColor: rankColor(r.rank) }" />
              <h3>{{ r.name }} ({{ r.symbol }})</h3>
              <a-progress :percent="r.score" :stroke-color="scoreColor(r.score)" :format="() => r.score + '分'" />
              <p style="margin-top: 8px; color: #666; font-size: 13px">{{ r.reason }}</p>
            </a-card>
          </a-col>
        </a-row>
      </a-card>

      <!-- 对比表格 -->
      <a-card v-if="result.analysis?.comparison_table" title="指标对比" class="section-card">
        <a-table
          :columns="tableColumns(result.analysis.comparison_table.headers)"
          :data-source="tableData(result.analysis.comparison_table.rows)"
          :pagination="false"
          bordered
          size="middle"
        />
      </a-card>

      <!-- 推荐 -->
      <a-card v-if="result.analysis?.best_pick" class="section-card">
        <a-result status="success" :title="'最佳选择: ' + result.analysis.best_pick.name + ' (' + result.analysis.best_pick.symbol + ')'">
          <template #subTitle>{{ result.analysis.best_pick.reason }}</template>
        </a-result>
      </a-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { compareStocks, searchStock } from '@/services/api'
import type { StockSearchResult } from '@/types'

const symbols = ref<string[]>([])
const searchOptions = ref<{ value: string; label: string }[]>([])
const loading = ref(false)
const result = ref<any>(null)

let searchTimer: any = null

function onSearch(keyword: string) {
  if (searchTimer) clearTimeout(searchTimer)
  if (!keyword || keyword.length < 1) { searchOptions.value = []; return }
  searchTimer = setTimeout(async () => {
    try {
      const res = await searchStock(keyword)
      if (res.success && res.data) {
        searchOptions.value = res.data.map((s: StockSearchResult) => ({ value: s.symbol, label: s.name }))
      }
    } catch { /* ignore */ }
  }, 400)
}

async function handleCompare() {
  if (symbols.value.length < 2) { message.warning('请至少选择2只股票'); return }
  loading.value = true
  try {
    const res = await compareStocks(symbols.value)
    if (res.success) {
      result.value = res.data
    } else {
      message.error(res.message)
    }
  } catch (e: any) {
    message.error(e.response?.data?.detail || e.message || '对比失败')
  } finally {
    loading.value = false
  }
}

function tableColumns(headers: string[]) {
  return headers.map((h, i) => ({ title: h, dataIndex: `col${i}`, key: `col${i}` }))
}

function tableData(rows: string[][]) {
  return rows.map((row, i) => {
    const obj: any = { key: i }
    row.forEach((cell, j) => { obj[`col${j}`] = cell })
    return obj
  })
}

function rankColor(rank: number) {
  if (rank === 1) return '#f5222d'
  if (rank === 2) return '#fa8c16'
  return '#1890ff'
}

function scoreColor(score: number) {
  if (score >= 70) return { '0%': '#87d068', '100%': '#52c41a' }
  if (score >= 50) return { '0%': '#faad14', '100%': '#fa8c16' }
  return { '0%': '#ff4d4f', '100%': '#f5222d' }
}
</script>

<style scoped>
.compare-container { max-width: 1000px; margin: 0 auto; padding: 20px; }
.page-header { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
.input-card { margin-bottom: 20px; }
.section-card { margin-bottom: 16px; }
.back-btn { flex-shrink: 0; }
</style>
