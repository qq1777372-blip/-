<script setup lang="ts">
import {
  ArrowDown,
  ArrowUp,
  CirclePlus,
  Delete,
  EditPen,
  Finished,
  RefreshRight,
  Search,
  Select,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { TableInstance } from 'element-plus'
import axios from 'axios'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  batchDeleteTaskBookkeepingRecords,
  batchUpdateTaskBookkeepingRecordStatus,
  createTaskBookkeepingRecord,
  deleteTaskBookkeepingRecord,
  fetchShopRecords,
  fetchTaskBookkeepingOwners,
  fetchTaskBookkeepingRecords,
  updateTaskBookkeepingRecord,
} from '../api'
import ListPaginationFooter from '../components/ListPaginationFooter.vue'
import { useViewport } from '../composables/useViewport'
import { useAuthStore } from '../stores/auth'
import type {
  ShopRecord,
  TaskBookkeepingOwner,
  TaskBookkeepingRecord,
  TaskBookkeepingRecordPayload,
  TaskStatusType,
} from '../types/api'
import { formatDateTime, formatMoney, getApiTimestamp, parseApiDateTime } from '../utils/format'

const authStore = useAuthStore()
const { isMobile, viewportHeight } = useViewport()

const loading = ref(false)
const submitLoading = ref(false)
const batchLoading = ref(false)
const currentPage = ref(1)
const keyword = ref('')
const statusText = ref('准备就绪')
const records = ref<TaskBookkeepingRecord[]>([])
const shops = ref<string[]>([])
const owners = ref<TaskBookkeepingOwner[]>([])
const selectedIds = ref<number[]>([])
const tableRef = ref<TableInstance>()
const filtersExpanded = ref(false)

const recordDialogVisible = ref(false)
const editingRecordId = ref<number | null>(null)

const filters = reactive({
  startDate: '',
  endDate: '',
  shopName: '',
  ownerName: '',
  signedStatus: 'all',
  settlementStatus: 'all',
})

const form = reactive({
  task_time: '',
  shop_name: '',
  owner_name: '',
  principal_amount: 0,
  order_count: 1,
  commission_amount: 0,
  gift_amount: 0,
  signed_status: 'pending' as TaskStatusType,
  settlement_status: 'pending' as TaskStatusType,
  note: '',
})

const canEditRecords = computed(() => {
  const role = authStore.currentUser?.role
  return role === 'editor' || role === 'superadmin'
})

const desktopTableHeight = computed(() => Math.max(380, viewportHeight.value - 540))
const mobileListHeight = computed(() => Math.max(420, viewportHeight.value - 320))
const pageSize = computed(() => 20)

const signedStatusOptions = [
  { label: '全部签收状态', value: 'all' },
  { label: '处理中', value: 'pending' },
  { label: '已完成', value: 'completed' },
]

const settlementStatusOptions = [
  { label: '全部结算状态', value: 'all' },
  { label: '处理中', value: 'pending' },
  { label: '已完成', value: 'completed' },
]

const filteredRecords = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase()
  const startAt = filters.startDate ? new Date(`${filters.startDate}T00:00:00`).getTime() : null
  const endAt = filters.endDate ? new Date(`${filters.endDate}T23:59:59`).getTime() : null

  return records.value.filter((record) => {
    const taskTime = getApiTimestamp(record.task_time)

    if (startAt !== null && !Number.isNaN(taskTime) && taskTime < startAt) {
      return false
    }

    if (endAt !== null && !Number.isNaN(taskTime) && taskTime > endAt) {
      return false
    }

    if (filters.shopName && record.shop_name !== filters.shopName) {
      return false
    }

    if (filters.ownerName && record.owner_name !== filters.ownerName) {
      return false
    }

    if (filters.signedStatus !== 'all' && record.signed_status !== filters.signedStatus) {
      return false
    }

    if (filters.settlementStatus !== 'all' && record.settlement_status !== filters.settlementStatus) {
      return false
    }

    if (!normalizedKeyword) {
      return true
    }

    return [
      record.order_no,
      record.shop_name,
      record.owner_name,
      record.note ?? '',
      statusLabel(record.signed_status),
      statusLabel(record.settlement_status),
      String(record.principal_amount),
      String(record.commission_amount),
      String(record.gift_amount),
      String(record.order_count),
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

const stats = computed(() => {
  const principalTotal = filteredRecords.value.reduce((sum, record) => sum + Number(record.principal_amount || 0), 0)
  const commissionTotal = filteredRecords.value.reduce(
    (sum, record) => sum + Number(record.commission_amount || 0),
    0,
  )
  const giftTotal = filteredRecords.value.reduce((sum, record) => sum + Number(record.gift_amount || 0), 0)
  const unsettledPrincipalTotal = filteredRecords.value.reduce((sum, record) => {
    if (record.settlement_status === 'pending') {
      return sum + Number(record.principal_amount || 0)
    }

    return sum
  }, 0)

  return {
    totalCount: filteredRecords.value.length,
    principalTotal,
    commissionTotal,
    giftTotal,
    unsettledPrincipalTotal,
  }
})

const activeFilterCount = computed(() => {
  let count = 0

  if (keyword.value.trim()) count += 1
  if (filters.shopName) count += 1
  if (filters.ownerName) count += 1
  if (filters.startDate) count += 1
  if (filters.endDate) count += 1
  if (filters.signedStatus !== 'all') count += 1
  if (filters.settlementStatus !== 'all') count += 1

  return count
})

const hasActiveFilters = computed(() => activeFilterCount.value > 0)

const filterMetaText = computed(() => {
  return hasActiveFilters.value ? `已启用 ${activeFilterCount.value} 项筛选` : '未启用筛选'
})

const advancedFiltersActive = computed(() => {
  return Boolean(
    filters.startDate ||
      filters.endDate ||
      filters.signedStatus !== 'all' ||
      filters.settlementStatus !== 'all',
  )
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

function statusLabel(value: TaskStatusType) {
  return value === 'completed' ? '已完成' : '处理中'
}

function signedTagType(value: TaskStatusType) {
  return value === 'completed' ? 'success' : 'warning'
}

function settlementTagType(value: TaskStatusType) {
  return value === 'completed' ? 'success' : 'danger'
}

function extractShopName(record: ShopRecord) {
  const rawValue = record.values.shop_name
  if (typeof rawValue !== 'string') {
    return ''
  }

  return rawValue.trim()
}

function buildShopOptions(shopRecords: ShopRecord[]) {
  return [...new Set(shopRecords.map(extractShopName).filter(Boolean))].sort((left, right) =>
    left.localeCompare(right, 'zh-CN'),
  )
}

function pad(value: number) {
  return String(value).padStart(2, '0')
}

function getCurrentDateTimeValue() {
  const now = new Date()
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}

function normalizeDateTimeValue(value: string | null | undefined) {
  if (!value) {
    return getCurrentDateTimeValue()
  }

  const date = parseApiDateTime(value)
  if (!date) {
    return value.slice(0, 19)
  }

  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

function resetForm() {
  editingRecordId.value = null
  form.task_time = getCurrentDateTimeValue()
  form.shop_name = ''
  form.owner_name = ''
  form.principal_amount = 0
  form.order_count = 1
  form.commission_amount = 0
  form.gift_amount = 0
  form.signed_status = 'pending'
  form.settlement_status = 'pending'
  form.note = ''
}

function resetFilters() {
  keyword.value = ''
  filters.shopName = ''
  filters.ownerName = ''
  filters.startDate = ''
  filters.endDate = ''
  filters.signedStatus = 'all'
  filters.settlementStatus = 'all'
  filtersExpanded.value = false
}

function toggleFiltersExpanded() {
  filtersExpanded.value = !filtersExpanded.value
}

function openCreateDialog() {
  resetForm()
  recordDialogVisible.value = true
}

function openEditDialog(record: TaskBookkeepingRecord) {
  resetForm()
  editingRecordId.value = record.id
  form.task_time = normalizeDateTimeValue(record.task_time)
  form.shop_name = record.shop_name
  form.owner_name = record.owner_name
  form.principal_amount = Number(record.principal_amount || 0)
  form.order_count = Number(record.order_count || 1)
  form.commission_amount = Number(record.commission_amount || 0)
  form.gift_amount = Number(record.gift_amount || 0)
  form.signed_status = record.signed_status
  form.settlement_status = record.settlement_status
  form.note = record.note ?? ''
  recordDialogVisible.value = true
}

function buildPayload(): TaskBookkeepingRecordPayload {
  return {
    task_time: form.task_time || null,
    shop_name: form.shop_name.trim(),
    owner_name: form.owner_name.trim(),
    principal_amount: Number(form.principal_amount || 0),
    order_count: Number(form.order_count || 1),
    commission_amount: Number(form.commission_amount || 0),
    gift_amount: Number(form.gift_amount || 0),
    signed_status: form.signed_status,
    settlement_status: form.settlement_status,
    note: form.note.trim() || null,
  }
}

async function loadData(message = '正在同步任务记录...') {
  loading.value = true
  statusText.value = message

  try {
    const [recordData, shopRecordData, ownerData] = await Promise.all([
      fetchTaskBookkeepingRecords(),
      fetchShopRecords(),
      fetchTaskBookkeepingOwners(),
    ])

    records.value = recordData
    shops.value = buildShopOptions(shopRecordData)
    owners.value = ownerData
    tableRef.value?.clearSelection()
    selectedIds.value = []
    statusText.value = `已加载 ${recordData.length} 条任务记录`
  } catch (error) {
    const messageText = getErrorMessage(error, '加载任务记录失败')
    statusText.value = messageText
    ElMessage.error(messageText)
  } finally {
    loading.value = false
  }
}

async function submitRecord() {
  submitLoading.value = true

  try {
    const payload = buildPayload()

    if (!payload.shop_name || !payload.owner_name) {
      ElMessage.warning('店铺名称和负责人不能为空')
      return
    }

    if (editingRecordId.value === null) {
      await createTaskBookkeepingRecord(payload)
      ElMessage.success('任务记录新增成功')
    } else {
      await updateTaskBookkeepingRecord(editingRecordId.value, payload)
      ElMessage.success('任务记录更新成功')
    }

    recordDialogVisible.value = false
    await loadData('正在刷新任务记录...')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '保存任务记录失败'))
  } finally {
    submitLoading.value = false
  }
}

async function confirmDeleteRecord(record: TaskBookkeepingRecord) {
  try {
    await ElMessageBox.confirm(`确定删除任务记录 #${record.id} 吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })

    await deleteTaskBookkeepingRecord(record.id)
    ElMessage.success('删除成功')
    await loadData('正在刷新任务记录...')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, '删除任务记录失败'))
  }
}

async function applyBatchStatus(
  field: 'signed_status' | 'settlement_status',
  value: TaskStatusType,
  successMessage: string,
) {
  if (!selectedIds.value.length) {
    return
  }

  batchLoading.value = true

  try {
    await batchUpdateTaskBookkeepingRecordStatus({
      record_ids: selectedIds.value,
      field,
      value,
    })
    ElMessage.success(successMessage)
    await loadData('正在刷新任务记录...')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '批量更新状态失败'))
  } finally {
    batchLoading.value = false
  }
}

async function confirmBatchDelete() {
  if (!selectedIds.value.length) {
    return
  }

  try {
    await ElMessageBox.confirm(`确定删除已选的 ${selectedIds.value.length} 条任务记录吗？`, '批量删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })

    batchLoading.value = true
    await batchDeleteTaskBookkeepingRecords({
      record_ids: selectedIds.value,
    })
    ElMessage.success('批量删除成功')
    await loadData('正在刷新任务记录...')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, '批量删除任务记录失败'))
  } finally {
    batchLoading.value = false
  }
}

function clearSelectedRows() {
  tableRef.value?.clearSelection()
  selectedIds.value = []
}

async function handleBatchCommand(command: string | number | object) {
  if (command === 'signed-completed') {
    await applyBatchStatus('signed_status', 'completed', '批量标记签收完成成功')
    return
  }

  if (command === 'settlement-completed') {
    await applyBatchStatus('settlement_status', 'completed', '批量标记结算完成成功')
    return
  }

  if (command === 'signed-pending') {
    await applyBatchStatus('signed_status', 'pending', '批量标记签收处理中成功')
    return
  }

  if (command === 'delete') {
    await confirmBatchDelete()
    return
  }

  if (command === 'clear-selection') {
    clearSelectedRows()
  }
}

function handleSelectionChange(rows: TaskBookkeepingRecord[]) {
  selectedIds.value = rows.map((row) => row.id)
}

function handleMobileSelectionToggle(recordId: number, checked: unknown) {
  const normalizedChecked = Boolean(checked)

  if (normalizedChecked) {
    if (!selectedIds.value.includes(recordId)) {
      selectedIds.value = [...selectedIds.value, recordId]
    }
    return
  }

  selectedIds.value = selectedIds.value.filter((id) => id !== recordId)
}

function escapeCsvValue(value: unknown) {
  const text = String(value ?? '')
  if (text.includes('"') || text.includes(',') || text.includes('\n')) {
    return `"${text.replace(/"/g, '""')}"`
  }

  return text
}

function exportCsv() {
  const headers = [
    'ID',
    '订单编号',
    '任务时间',
    '店铺名称',
    '负责人',
    '单笔本金',
    '刷单数量',
    '佣金支出',
    '礼品花费',
    '签收状态',
    '结算状态',
    '备注',
  ]

  const rows = filteredRecords.value.map((record) => [
    record.id,
    record.order_no,
    formatDateTime(record.task_time),
    record.shop_name,
    record.owner_name,
    record.principal_amount,
    record.order_count,
    record.commission_amount,
    record.gift_amount,
    statusLabel(record.signed_status),
    statusLabel(record.settlement_status),
    record.note ?? '',
  ])

  const csvContent = [headers, ...rows]
    .map((row) => row.map((item) => escapeCsvValue(item)).join(','))
    .join('\r\n')

  const blob = new Blob([`\ufeff${csvContent}`], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `task-bookkeeping-${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

watch(recordDialogVisible, (visible) => {
  if (!visible) {
    resetForm()
  }
})

watch(
  () => [
    keyword.value,
    filters.startDate,
    filters.endDate,
    filters.shopName,
    filters.ownerName,
    filters.signedStatus,
    filters.settlementStatus,
  ],
  () => {
    currentPage.value = 1
    clearSelectedRows()
  },
)

watch(
  () => filteredRecords.value.length,
  () => {
    if (currentPage.value > totalPages.value) {
      currentPage.value = totalPages.value
    }
  },
)

watch(currentPage, () => {
  clearSelectedRows()
})

onMounted(() => {
  resetForm()
  loadData()
})
</script>

<template>
  <div class="page-stack">
    <section class="page-block list-surface list-surface--fixed">
      <div class="task-filter-shell">
        <div class="task-filter-head">
          <div>
            <h3 class="section-title">筛选条件</h3>
            <p class="section-desc">按订单编号、关键词、店铺、负责人快速定位记录，其它条件按需展开</p>
          </div>

          <div class="task-filter-meta">
            <span class="filter-meta-chip filter-meta-chip--primary">{{ statusText }}</span>
            <span class="filter-meta-chip">{{ filterMetaText }}</span>
            <el-button plain :icon="RefreshRight" :disabled="!hasActiveFilters" @click="resetFilters">
              重置筛选
            </el-button>
          </div>
        </div>

        <div class="task-filter-compact-row">
          <el-input
            v-model="keyword"
            class="filter-compact-keyword"
            placeholder="搜索订单编号、店铺、负责人、备注或状态"
            size="large"
            :prefix-icon="Search"
            clearable
          />

          <el-select v-model="filters.shopName" placeholder="全部店铺" clearable filterable size="large">
            <el-option v-for="shop in shops" :key="shop" :label="shop" :value="shop" />
          </el-select>

          <el-select v-model="filters.ownerName" placeholder="全部负责人" clearable filterable size="large">
            <el-option v-for="owner in owners" :key="owner.id" :label="owner.name" :value="owner.name" />
          </el-select>

          <el-button
            class="filter-expand-button"
            plain
            :type="advancedFiltersActive ? 'primary' : undefined"
            @click="toggleFiltersExpanded"
          >
            <el-icon><component :is="filtersExpanded ? ArrowUp : ArrowDown" /></el-icon>
          </el-button>
        </div>

        <div v-if="filtersExpanded" class="task-filter-advanced-grid">
          <label class="filter-field">
            <span class="filter-label">开始日期</span>
            <el-date-picker
              v-model="filters.startDate"
              type="date"
              value-format="YYYY-MM-DD"
              format="YYYY-MM-DD"
              placeholder="开始日期"
              size="large"
              clearable
            />
          </label>

          <label class="filter-field">
            <span class="filter-label">结束日期</span>
            <el-date-picker
              v-model="filters.endDate"
              type="date"
              value-format="YYYY-MM-DD"
              format="YYYY-MM-DD"
              placeholder="结束日期"
              size="large"
              clearable
            />
          </label>

          <label class="filter-field">
            <span class="filter-label">签收状态</span>
            <el-select v-model="filters.signedStatus" placeholder="全部签收状态" size="large">
              <el-option
                v-for="option in signedStatusOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </label>

          <label class="filter-field">
            <span class="filter-label">结算状态</span>
            <el-select v-model="filters.settlementStatus" placeholder="全部结算状态" size="large">
              <el-option
                v-for="option in settlementStatusOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </label>
        </div>
      </div>

      <div class="task-metric-grid">
        <article class="task-metric-card">
          <div class="metric-label">记录数</div>
          <div class="metric-value small">{{ stats.totalCount }}</div>
        </article>
        <article class="task-metric-card">
          <div class="metric-label">待回款本金</div>
          <div class="metric-value small">¥ {{ formatMoney(stats.unsettledPrincipalTotal) }}</div>
        </article>
        <article class="task-metric-card">
          <div class="metric-label">本金投入</div>
          <div class="metric-value small">¥ {{ formatMoney(stats.principalTotal) }}</div>
        </article>
        <article class="task-metric-card">
          <div class="metric-label">佣金支出</div>
          <div class="metric-value small">¥ {{ formatMoney(stats.commissionTotal) }}</div>
        </article>
        <article class="task-metric-card">
          <div class="metric-label">礼品花费</div>
          <div class="metric-value small">¥ {{ formatMoney(stats.giftTotal) }}</div>
        </article>
      </div>

      <div class="toolbar-row">
        <div>
          <h3 class="section-title">任务记录</h3>
          <p class="section-desc">支持新增、编辑、筛选、批量处理和导出。</p>
        </div>

        <div class="toolbar-actions">
          <el-button type="primary" :icon="CirclePlus" :disabled="!canEditRecords" @click="openCreateDialog">
            新增任务
          </el-button>
          <el-button :icon="RefreshRight" @click="loadData('正在手动刷新任务记录...')">刷新数据</el-button>
          <el-button type="success" plain :icon="Finished" @click="exportCsv">导出 CSV</el-button>

          <div class="toolbar-batch-group">
            <el-dropdown trigger="click" popper-class="batch-actions-popper" @command="handleBatchCommand">
              <el-button class="toolbar-batch-action" plain :icon="Select" :loading="batchLoading" :disabled="!canEditRecords">
                更多批量操作
              </el-button>

              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="signed-completed" :disabled="!selectedIds.length">
                    标记签收完成
                  </el-dropdown-item>
                  <el-dropdown-item command="settlement-completed" :disabled="!selectedIds.length">
                    标记结算完成
                  </el-dropdown-item>
                  <el-dropdown-item command="signed-pending" :disabled="!selectedIds.length">
                    标记签收处理中
                  </el-dropdown-item>
                  <el-dropdown-item command="delete" :disabled="!selectedIds.length" divided>
                    <span class="danger-text">批量删除</span>
                  </el-dropdown-item>
                  <el-dropdown-item command="clear-selection" :disabled="!selectedIds.length">
                    取消选择
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>

            <span class="toolbar-selected-count">已选 {{ selectedIds.length }}</span>
          </div>
        </div>
      </div>

      <div v-if="!isMobile" class="table-area fixed-list-shell">
        <el-table
          ref="tableRef"
          :data="paginatedRecords"
          stripe
          :height="desktopTableHeight"
          v-loading="loading"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="50" fixed="left" />
          <el-table-column prop="id" label="ID" width="72" fixed="left" sortable />
          <el-table-column prop="order_no" label="订单编号" min-width="180" sortable />
          <el-table-column prop="task_time" label="任务时间" min-width="180" sortable>
            <template #default="{ row }">
              {{ formatDateTime(row.task_time) }}
            </template>
          </el-table-column>
          <el-table-column prop="shop_name" label="店铺名称" min-width="160" sortable />
          <el-table-column prop="owner_name" label="负责人" min-width="140" sortable />
          <el-table-column prop="unit_principal" label="单笔本金" min-width="120" sortable>
            <template #default="{ row }">¥ {{ formatMoney(row.principal_amount) }}</template>
          </el-table-column>
          <el-table-column prop="order_count" label="刷单数量" min-width="110" sortable />
          <el-table-column prop="commission_expense" label="佣金支出" min-width="120" sortable>
            <template #default="{ row }">¥ {{ formatMoney(row.commission_amount) }}</template>
          </el-table-column>
          <el-table-column prop="gift_expense" label="礼品花费" min-width="120" sortable>
            <template #default="{ row }">¥ {{ formatMoney(row.gift_amount) }}</template>
          </el-table-column>
          <el-table-column prop="is_signed" label="签收状态" min-width="110" sortable>
            <template #default="{ row }">
              <el-tag :type="signedTagType(row.signed_status)" effect="light">
                {{ statusLabel(row.signed_status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="is_settled" label="结算状态" min-width="110" sortable>
            <template #default="{ row }">
              <el-tag :type="settlementTagType(row.settlement_status)" effect="light">
                {{ statusLabel(row.settlement_status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="note" label="备注" min-width="220" show-overflow-tooltip sortable />

          <el-table-column v-if="canEditRecords" label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <div class="cell-actions">
                <el-button type="primary" link :icon="EditPen" @click="openEditDialog(row)">编辑</el-button>
                <el-button type="danger" link :icon="Delete" @click="confirmDeleteRecord(row)">删除</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <ListPaginationFooter
          v-model:current-page="currentPage"
          :total-pages="totalPages"
          :page-size="pageSize"
          :total-items="filteredRecords.length"
        />
      </div>

      <div v-else class="table-area fixed-list-shell">
        <div v-loading="loading" class="task-mobile-list fixed-list-mobile" :style="{ maxHeight: `${mobileListHeight}px` }">
          <template v-if="paginatedRecords.length">
            <article
              v-for="record in paginatedRecords"
              :key="record.id"
              class="task-mobile-card"
            >
              <div class="task-mobile-card__head">
                <div class="task-mobile-card__title-wrap">
                  <div class="task-mobile-card__title-row">
                    <el-checkbox
                      v-if="canEditRecords"
                      :model-value="selectedIds.includes(record.id)"
                      @change="handleMobileSelectionToggle(record.id, $event)"
                    />
                    <h4 class="task-mobile-card__title">{{ record.shop_name }}</h4>
                  </div>
                  <p class="task-mobile-card__meta">
                    {{ record.order_no }} · {{ record.owner_name }} · {{ formatDateTime(record.task_time) }}
                  </p>
                </div>
              </div>

              <div class="task-mobile-card__tags">
                <el-tag :type="signedTagType(record.signed_status)" effect="light">
                  签收{{ statusLabel(record.signed_status) }}
                </el-tag>
                <el-tag :type="settlementTagType(record.settlement_status)" effect="light">
                  结算{{ statusLabel(record.settlement_status) }}
                </el-tag>
              </div>

              <div class="task-mobile-card__grid">
                <div class="task-mobile-card__field">
                  <span class="task-mobile-card__label">订单编号</span>
                  <span class="task-mobile-card__value">{{ record.order_no }}</span>
                </div>
                <div class="task-mobile-card__field">
                  <span class="task-mobile-card__label">单笔本金</span>
                  <span class="task-mobile-card__value">¥ {{ formatMoney(record.principal_amount) }}</span>
                </div>
                <div class="task-mobile-card__field">
                  <span class="task-mobile-card__label">刷单数量</span>
                  <span class="task-mobile-card__value">{{ record.order_count }}</span>
                </div>
                <div class="task-mobile-card__field">
                  <span class="task-mobile-card__label">佣金支出</span>
                  <span class="task-mobile-card__value">¥ {{ formatMoney(record.commission_amount) }}</span>
                </div>
                <div class="task-mobile-card__field">
                  <span class="task-mobile-card__label">礼品花费</span>
                  <span class="task-mobile-card__value">¥ {{ formatMoney(record.gift_amount) }}</span>
                </div>
              </div>

              <div class="task-mobile-card__notes">
                <div class="task-mobile-card__label">备注</div>
                <p class="task-mobile-card__notes-text">{{ record.note || '暂无备注' }}</p>
              </div>

              <div v-if="canEditRecords" class="task-mobile-card__actions">
                <el-button type="primary" plain :icon="EditPen" @click="openEditDialog(record)">
                  编辑
                </el-button>
                <el-button type="danger" plain :icon="Delete" @click="confirmDeleteRecord(record)">
                  删除
                </el-button>
              </div>
            </article>
          </template>

          <el-empty
            v-else
            :description="keyword.trim() || hasActiveFilters ? '没有匹配的任务记录' : '暂无任务记录'"
          />
        </div>

        <ListPaginationFooter
          v-model:current-page="currentPage"
          :total-pages="totalPages"
          :page-size="pageSize"
          :total-items="filteredRecords.length"
        />
      </div>
    </section>

    <el-dialog
      v-model="recordDialogVisible"
      :title="editingRecordId === null ? '新增任务记录' : `编辑任务记录 #${editingRecordId}`"
      width="920px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="任务时间" required>
              <el-date-picker
                v-model="form.task_time"
                type="datetime"
                value-format="YYYY-MM-DDTHH:mm:ss"
                format="YYYY-MM-DD HH:mm:ss"
                style="width: 100%"
                placeholder="请选择任务时间"
              />
            </el-form-item>
          </el-col>

          <el-col :span="12">
            <el-form-item label="刷单数量" required>
              <el-input-number v-model="form.order_count" :min="1" :step="1" style="width: 100%" />
            </el-form-item>
          </el-col>

          <el-col :span="12">
            <el-form-item label="店铺名称" required>
              <el-select
                v-model="form.shop_name"
                filterable
                allow-create
                default-first-option
                :reserve-keyword="false"
                style="width: 100%"
                placeholder="选择或输入店铺名称"
              >
                <el-option v-for="shop in shops" :key="shop" :label="shop" :value="shop" />
              </el-select>
            </el-form-item>
          </el-col>

          <el-col :span="12">
            <el-form-item label="负责人" required>
              <el-select
                v-model="form.owner_name"
                filterable
                allow-create
                default-first-option
                :reserve-keyword="false"
                style="width: 100%"
                placeholder="选择或输入负责人"
              >
                <el-option v-for="owner in owners" :key="owner.id" :label="owner.name" :value="owner.name" />
              </el-select>
            </el-form-item>
          </el-col>

          <el-col :span="8">
            <el-form-item label="单笔本金">
              <el-input-number v-model="form.principal_amount" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>

          <el-col :span="8">
            <el-form-item label="佣金支出">
              <el-input-number v-model="form.commission_amount" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>

          <el-col :span="8">
            <el-form-item label="礼品花费">
              <el-input-number v-model="form.gift_amount" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>

          <el-col :span="12">
            <el-form-item label="签收状态">
              <el-radio-group v-model="form.signed_status">
                <el-radio-button label="pending">处理中</el-radio-button>
                <el-radio-button label="completed">已完成</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-col>

          <el-col :span="12">
            <el-form-item label="结算状态">
              <el-radio-group v-model="form.settlement_status">
                <el-radio-button label="pending">处理中</el-radio-button>
                <el-radio-button label="completed">已完成</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-col>

          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.note" type="textarea" :rows="4" placeholder="填写任务备注" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button @click="recordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="submitRecord">
          {{ editingRecordId === null ? '新增任务' : '保存修改' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.task-filter-shell {
  padding: 20px 22px;
  border-bottom: 1px solid var(--panel-border);
  background: linear-gradient(180deg, #fcfdff 0%, #f8fbff 100%);
}

.task-filter-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 18px;
}

.task-filter-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.filter-meta-chip {
  display: inline-flex;
  align-items: center;
  min-height: 36px;
  padding: 0 12px;
  border: 1px solid #d9e2ef;
  border-radius: 999px;
  background: #ffffff;
  color: var(--text-secondary);
  font-size: 13px;
  white-space: nowrap;
}

.filter-meta-chip--primary {
  border-color: #cfe0ff;
  background: #f5f9ff;
  color: var(--brand-primary);
}

.task-filter-compact-row {
  display: grid;
  grid-template-columns: minmax(340px, 1.4fr) minmax(220px, 1fr) minmax(220px, 1fr) 44px;
  gap: 14px 16px;
  align-items: center;
}

.filter-compact-keyword :deep(.el-input),
.task-filter-compact-row :deep(.el-select),
.task-filter-advanced-grid :deep(.el-select),
.task-filter-advanced-grid :deep(.el-date-editor) {
  width: 100%;
}

.filter-expand-button {
  width: 44px;
  min-width: 44px;
  height: 40px;
  padding: 0;
}

.task-filter-advanced-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px 16px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed #d9e2ef;
}

.filter-field {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.filter-label {
  padding-left: 2px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.task-metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  padding: 18px 22px 0;
}

.task-metric-card {
  padding: 16px;
  border: 1px solid var(--panel-border);
  border-radius: 14px;
  background: #fbfdff;
}

.task-metric-card .metric-value.small {
  margin-top: 10px;
  font-size: 24px;
}

.danger-text {
  color: var(--brand-danger);
}

.toolbar-batch-group {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.toolbar-batch-action {
  min-height: 36px;
  border-color: #b7d2ff;
  color: var(--brand-primary);
  background: #f7fbff;
}

.toolbar-selected-count {
  display: inline-flex;
  align-items: center;
  min-height: 36px;
  color: var(--text-secondary);
  font-size: 14px;
  white-space: nowrap;
}

.task-mobile-list {
  display: grid;
  gap: 12px;
  min-height: 180px;
}

.task-mobile-card {
  display: grid;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--panel-border);
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: 0 10px 24px rgba(31, 41, 55, 0.06);
}

.task-mobile-card__title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.task-mobile-card__title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.35;
  word-break: break-word;
}

.task-mobile-card__meta {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
  word-break: break-word;
}

.task-mobile-card__tags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.task-mobile-card__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.task-mobile-card__field {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid #e6edf7;
  border-radius: 14px;
  background: #fbfdff;
}

.task-mobile-card__label {
  color: var(--text-secondary);
  font-size: 12px;
}

.task-mobile-card__value {
  font-size: 14px;
  font-weight: 600;
  line-height: 1.5;
}

.task-mobile-card__notes {
  display: grid;
  gap: 8px;
}

.task-mobile-card__notes-text {
  margin: 0;
  padding: 12px 14px;
  border: 1px solid #e6edf7;
  border-radius: 14px;
  background: #fbfdff;
  color: var(--text-main);
  line-height: 1.65;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  overflow: hidden;
}

.task-mobile-card__actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.task-mobile-card__actions .el-button {
  width: 100%;
  margin: 0;
}

:global(.batch-actions-popper.el-zoom-in-top-enter-active),
:global(.batch-actions-popper.el-zoom-in-top-leave-active) {
  transition: none !important;
}

:global(.batch-actions-popper.el-zoom-in-top-enter-from),
:global(.batch-actions-popper.el-zoom-in-top-leave-to) {
  opacity: 1 !important;
  transform: none !important;
}

@media (max-width: 1280px) {
  .task-filter-advanced-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .task-filter-compact-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-compact-keyword {
    grid-column: span 2;
  }

  .task-filter-advanced-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .toolbar-batch-group {
    width: 100%;
  }
}

@media (max-width: 640px) {
  .task-filter-compact-row,
  .task-filter-advanced-grid {
    grid-template-columns: 1fr;
  }

  .filter-compact-keyword {
    grid-column: span 1;
  }

  .filter-expand-button {
    justify-self: end;
  }

  .task-mobile-card__grid,
  .task-mobile-card__actions {
    grid-template-columns: 1fr;
  }
}
</style>
