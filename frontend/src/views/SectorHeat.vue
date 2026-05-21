<template>
  <div class="sector-container">
    <div class="page-header">
      <a-button class="back-btn" @click="$router.push('/')">← 返回</a-button>
      <h2>板块热度</h2>
      <a-button @click="fetchData" :loading="loading" type="primary" ghost>刷新</a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="sectors"
      :loading="loading"
      :pagination="{ pageSize: 30 }"
      row-key="name"
      size="middle"
      :row-class-name="(_record: any, index: number) => index < 3 ? 'top-row' : ''"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'rank'">
          <span :style="{ color: record.rank <= 3 ? '#ff4d4f' : record.rank > sectors.length - 3 ? '#52c41a' : '#666' }">
            <strong>{{ record.rank <= 3 ? '🔥 ' : record.rank > sectors.length - 3 ? '❄ ' : '' }}{{ record.rank }}</strong>
          </span>
        </template>
        <template v-if="column.key === 'change_pct'">
          <span :style="{ color: record.change_pct > 0 ? '#cf1322' : record.change_pct < 0 ? '#3f8600' : '#666', fontWeight: 'bold' }">
            {{ record.change_pct > 0 ? '+' : '' }}{{ record.change_pct }}%
          </span>
        </template>
        <template v-if="column.key === 'strength'">
          <a-progress
            :percent="record.up_count / record.total_count * 100"
            :stroke-color="record.change_pct > 0 ? '#ff4d4f' : '#52c41a'"
            :show-info="false"
            size="small"
          />
          <span style="font-size: 12px; color: #999">{{ record.up_count }}/{{ record.total_count }}</span>
        </template>
        <template v-if="column.key === 'amount'">
          {{ record.amount > 1e8 ? (record.amount / 1e8).toFixed(1) + '亿' : (record.amount / 1e4).toFixed(0) + '万' }}
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import apiClient from '@/services/api'

const sectors = ref<any[]>([])
const loading = ref(false)

const columns = [
  { title: '排名', key: 'rank', width: 70 },
  { title: '板块', dataIndex: 'name', key: 'name', width: 120 },
  { title: '涨跌幅', key: 'change_pct', width: 100 },
  { title: '多空比', key: 'strength', width: 200 },
  { title: '成交额', key: 'amount', width: 120 },
  { title: '涨家', dataIndex: 'up_count', key: 'up', width: 70 },
  { title: '跌家', dataIndex: 'down_count', key: 'down', width: 70 },
]

async function fetchData() {
  loading.value = true
  try {
    const res = await apiClient.get('/api/stock/sectors')
    if (res.data.success) {
      sectors.value = res.data.data.map((s: any, i: number) => ({ ...s, rank: i + 1 }))
    }
  } catch { /* ignore */ }
  finally { loading.value = false }
}

onMounted(fetchData)
</script>

<style scoped>
.sector-container { max-width: 800px; margin: 0 auto; padding: 20px; }
.page-header { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
.page-header h2 { margin: 0; flex: 1; }
.back-btn { flex-shrink: 0; }
:deep(.top-row) { background: #fff7e6; }
</style>
