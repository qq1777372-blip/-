<script setup lang="ts">
import { RefreshRight, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { computed, onMounted, ref, watch } from 'vue'
import { fetchDingTalkProfits } from '../api'
import ListPaginationFooter from '../components/ListPaginationFooter.vue'
import { useViewport } from '../composables/useViewport'
import type { DingTalkProfitRecord } from '../types/api'
import { formatDate, formatDateTime, formatMoney } from '../utils/format'

const { isMobile, viewportHeight } = useViewport()

const loading = ref(false)
const currentPage = ref(1)
const keyword = ref('')
const selectedStore = ref('')
const selectedReporter = ref('')
const dateRange = ref<string[]>([])
const statusText = ref('准备就绪')
const records = ref<DingTalkProfitRecord[]>([])

const pageSize = computed(() => 20)
const desktopTableHeight = computed(() => Math.max(420, viewportHeight.value - 420))

const storeOptions = computed(() =>
  [...new Set(records.value.map((record) => record.store_name.trim()).filter(Boolean))].sort((left, right) =>
    left.localeCompare(right, 'zh-CN'),
  ),
)

const reporterOptions = computed(() =>
  [...new Set(records.value.map((record) => record.reporter_name.trim()).filter(Boolean))].sort((left, right) =>
    left.localeCompare(right, 'zh-CN'),
  ),
)

const filteredRecords = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase()
  const startDate = dateRange.value[0] ? new Date(`${dateRange.value[0]}T00:00:00`).getTime() : null
  const endDate = dateRange.value[1] ? new Date(`${dateRange.value[1]}T23:59:59`).getTime() : null

  return records.value.filter((record) => {
    const reportDateTime = new Date(`${record.report_date}T12:00:00`).getTime()

    if (startDate !== null && !Number.isNaN(reportDateTime) && reportDateTime < startDate) {
      return false
    }

    if (endDate !== null && !Number.isNaN(reportDateTime) && reportDateTime > endDate) {
      return false
    }

    if (selectedStore.value && record.store_name !== selectedStore.value) {
      return false
    }

    if (selectedReporter.value && record.reporter_name !== selectedReporter.value) {
      return false
    }

    if (!normalizedKeyword) {
      return true
    }

    return [
      String(record.source_record_id),
      record.report_date,
      record.store_name,
      record.reporter_name,
      record.reporter_id ?? '',
      record.batch_id ?? '',
      record.source_message_id ?? '',
      String(record.profit),
    ]
      .join(' ')
      .toLowerCase()
      .includes(normalizedKeyword)
  })
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredRecords.value.length / pageSize.value)))

const paginatedRecords = computed(() => {
  const startIndex = (currentPage.value - 1) * pageSize.value
  return filteredRecords.value.slice(startIndex, startIndex + pageSize.value)
})

const activeFilterCount = computed(() => {
  let count = 0
  if (keyword.value.trim()) count += 1
  if (selectedStore.value) count += 1
  if (selectedReporter.value) count += 1
  if (dateRange.value.length) count += 1
  return count
})

const statusDisplay = computed(() => {
  if (loading.value) {
    return statusText.value
  }

  if (!records.value.length) {
    return '当前还没有同步到任何钉钉利润记录'
  }

  if (activeFilterCount.value > 0) {
    return `已启用 ${activeFilterCount.value} 项筛选，当前命中 ${filteredRecords.value.length} 条记录`
  }

  return statusText.value
})

watch([keyword, selectedStore, selectedReporter, dateRange], () => {
  currentPage.value = 1
})

watch(totalPages, (value) => {
  if (currentPage.value > value) {
    currentPage.value = value
  }
})

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    return String(error.response?.data?.detail ?? error.message ?? fallback)
  }

  if (error instanceof Error && error.message) {
    return error.message
  }

  return fallback
}

function resetFilters() {
  keyword.value = ''
  selectedStore.value = ''
  selectedReporter.value = ''
  dateRange.value = []
}

async function loadData(message = '正在同步钉钉利润数据...') {
  loading.value = true
  statusText.value = message

  try {
    const recordData = await fetchDingTalkProfits()
    records.value = recordData
    statusText.value = `已同步 ${recordData.length} 条钉钉利润记录`
  } catch (error) {
    const messageText = getErrorMessage(error, '加载钉钉利润数据失败')
    statusText.value = messageText
    ElMessage.error(messageText)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <div class="page-stack">
    <section class="page-block list-surface list-surface--fixed">
      <div class="filter-panel">
        <div class="query-grow">
          <div class="section-desc" style="margin-bottom: 8px">关键字查询</div>
          <el-input
            v-model="keyword"
            placeholder="搜索店铺、录入人、批次号、消息 ID"
            size="large"
            :prefix-icon="Search"
            clearable
          />
        </div>

        <div class="filter-status">
          <div class="section-desc" style="margin-bottom: 8px">同步状态</div>
          <div class="status-box" :title="statusDisplay">{{ statusDisplay }}</div>
        </div>
      </div>

      <div class="toolbar-row">
        <div>
          <h3 class="section-title" style="font-size: 16px">钉钉利润明细</h3>
          <p class="section-desc">
            这里仅保留筛选和明细，月度统计已经统一挪到运营工作台。
          </p>
        </div>

        <div class="toolbar-actions">
          <el-select v-model="selectedStore" placeholder="筛选店铺" clearable filterable style="width: 180px">
            <el-option v-for="store in storeOptions" :key="store" :label="store" :value="store" />
          </el-select>

          <el-select
            v-model="selectedReporter"
            placeholder="筛选录入人"
            clearable
            filterable
            style="width: 180px"
          >
            <el-option
              v-for="reporter in reporterOptions"
              :key="reporter"
              :label="reporter"
              :value="reporter"
            />
          </el-select>

          <el-date-picker
            v-model="dateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            clearable
          />

          <el-button plain @click="resetFilters">清空筛选</el-button>
          <el-button :icon="RefreshRight" @click="loadData('正在手动刷新钉钉利润数据...')">
            刷新数据
          </el-button>
        </div>
      </div>

      <div v-if="!isMobile" class="table-area fixed-list-shell">
        <el-table
          :data="paginatedRecords"
          stripe
          :height="desktopTableHeight"
          v-loading="loading"
        >
          <el-table-column prop="source_record_id" label="源 ID" width="88" fixed="left" sortable />
          <el-table-column prop="report_date" label="报表日期" min-width="120" sortable />
          <el-table-column prop="store_name" label="店铺" min-width="180" sortable />
          <el-table-column prop="profit" label="利润" min-width="130" sortable>
            <template #default="{ row }">¥ {{ formatMoney(row.profit) }}</template>
          </el-table-column>
          <el-table-column prop="reporter_name" label="录入人" min-width="130" sortable />
          <el-table-column prop="batch_id" label="批次号" min-width="180" show-overflow-tooltip sortable />
          <el-table-column prop="source_message_id" label="消息 ID" min-width="180" show-overflow-tooltip sortable />
          <el-table-column prop="source_created_at" label="源创建时间" min-width="170" sortable>
            <template #default="{ row }">{{ formatDateTime(row.source_create_time) }}</template>
          </el-table-column>
          <el-table-column prop="created_at" label="网站同步时间" min-width="170" sortable>
            <template #default="{ row }">{{ formatDateTime(row.synced_at) }}</template>
          </el-table-column>
        </el-table>

        <ListPaginationFooter
          v-model:current-page="currentPage"
          :total-pages="totalPages"
          :page-size="pageSize"
          :total-items="filteredRecords.length"
          item-unit="条"
        />
      </div>

      <div v-else class="table-area fixed-list-shell">
        <div
          v-loading="loading"
          class="profit-card-list fixed-list-mobile"
        >
          <template v-if="paginatedRecords.length">
            <article
              v-for="record in paginatedRecords"
              :key="record.id"
              class="profit-mobile-card"
            >
              <div class="profit-mobile-card__head">
                <div>
                  <h4 class="profit-mobile-card__title">{{ record.store_name }}</h4>
                  <p class="profit-mobile-card__meta">
                    #{{ record.source_record_id }} · {{ record.reporter_name }} · {{ formatDate(record.report_date) }}
                  </p>
                </div>
                <strong class="profit-mobile-card__profit">¥ {{ formatMoney(record.profit) }}</strong>
              </div>

              <div class="profit-mobile-card__fields">
                <div class="profit-mobile-card__field">
                  <span class="profit-mobile-card__label">批次号</span>
                  <span class="profit-mobile-card__value">{{ record.batch_id || '-' }}</span>
                </div>
                <div class="profit-mobile-card__field">
                  <span class="profit-mobile-card__label">消息 ID</span>
                  <span class="profit-mobile-card__value">{{ record.source_message_id || '-' }}</span>
                </div>
                <div class="profit-mobile-card__field">
                  <span class="profit-mobile-card__label">源创建时间</span>
                  <span class="profit-mobile-card__value">{{ formatDateTime(record.source_create_time) }}</span>
                </div>
                <div class="profit-mobile-card__field">
                  <span class="profit-mobile-card__label">同步时间</span>
                  <span class="profit-mobile-card__value">{{ formatDateTime(record.synced_at) }}</span>
                </div>
              </div>
            </article>
          </template>

          <el-empty v-else description="暂无匹配的钉钉利润数据" />
        </div>

        <ListPaginationFooter
          v-model:current-page="currentPage"
          :total-pages="totalPages"
          :page-size="pageSize"
          :total-items="filteredRecords.length"
          item-unit="条"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.profit-card-list {
  display: grid;
  gap: 12px;
  min-height: 180px;
}

.profit-mobile-card {
  display: grid;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--panel-border);
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: 0 10px 24px rgba(31, 41, 55, 0.06);
}

.profit-mobile-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.profit-mobile-card__title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
}

.profit-mobile-card__meta {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
}

.profit-mobile-card__profit {
  color: var(--brand-primary);
  font-size: 18px;
  white-space: nowrap;
}

.profit-mobile-card__fields {
  display: grid;
  gap: 10px;
}

.profit-mobile-card__field {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border: 1px solid #e6edf7;
  border-radius: 14px;
  background: #fbfdff;
}

.profit-mobile-card__label {
  color: var(--text-secondary);
  font-size: 12px;
}

.profit-mobile-card__value {
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

@media (max-width: 768px) {
  .profit-mobile-card__head {
    flex-direction: column;
  }
}
</style>
