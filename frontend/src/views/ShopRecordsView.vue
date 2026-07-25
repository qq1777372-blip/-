<script setup lang="ts">
import {
  ArrowDown,
  ArrowUp,
  CirclePlus,
  Delete,
  EditPen,
  Hide,
  Plus,
  RefreshRight,
  Search,
  Select,
  Setting,
  View,
} from '@element-plus/icons-vue'
import type { TableInstance } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  batchDeleteShopRecords,
  createCustomField,
  createShopRecord,
  deleteCustomField,
  deleteShopRecord,
  fetchCustomFields,
  fetchUiSetting,
  reorderCustomFields,
  saveUiSetting,
  fetchShopRecords,
  updateCustomField,
  updateShopRecord,
} from '../api'
import ListPaginationFooter from '../components/ListPaginationFooter.vue'
import { useViewport } from '../composables/useViewport'
import { useAuthStore } from '../stores/auth'
import type { CustomField, CustomFieldCreatePayload, ShopRecord } from '../types/api'
import { formatDate, formatMoney, stringifyRecordValues } from '../utils/format'

const authStore = useAuthStore()
const { isMobile, viewportHeight } = useViewport()

const loading = ref(false)
const submitLoading = ref(false)
const fieldSubmitLoading = ref(false)
const batchLoading = ref(false)
const fieldActionLoading = ref(false)
const currentPage = ref(1)
const keyword = ref('')
const statusText = ref('准备就绪')
const records = ref<ShopRecord[]>([])
const fields = ref<CustomField[]>([])
const selectedIds = ref<number[]>([])
const tableRef = ref<TableInstance>()
const shopColumnWidthStorageKey = 'ruoshop.shop-records.column-widths.v1'

function loadShopColumnWidths() {
  try {
    const saved = JSON.parse(localStorage.getItem(shopColumnWidthStorageKey) ?? '{}') as Record<string, unknown>
    return Object.fromEntries(
      Object.entries(saved).map(([key, value]) => [key, Math.min(500, Math.max(100, Number(value) || 150))]),
    )
  } catch {
    return {}
  }
}

const shopColumnWidths = ref<Record<string, number>>(loadShopColumnWidths())

const recordDialogVisible = ref(false)
const fieldDialogVisible = ref(false)
const editingRecordId = ref<number | null>(null)
const sortState = ref<{ prop: string; order: 'ascending' | 'descending' } | null>(null)

const recordFormValues = reactive<Record<string, string | number | null>>({})
const fieldForm = reactive<CustomFieldCreatePayload>({
  label: '',
  field_name: null,
  field_type: 'text',
  required: false,
})

const orderedFields = computed(() => [...fields.value].sort((left, right) => left.sort_order - right.sort_order))
const visibleFields = computed(() => orderedFields.value.filter((field) => field.is_visible))

const filteredRecords = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase()
  if (!normalizedKeyword) {
    return records.value
  }

  return records.value.filter((record) => stringifyRecordValues(record.values).includes(normalizedKeyword))
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredRecords.value.length / pageSize.value)))

const sortedRecords = computed(() => {
  if (!sortState.value) return filteredRecords.value
  const { prop, order } = sortState.value
  const direction = order === 'ascending' ? 1 : -1
  return [...filteredRecords.value].sort((left, right) => {
    const leftValue = prop === 'id' ? left.id : left.values[prop.replace(/^values\./, '')]
    const rightValue = prop === 'id' ? right.id : right.values[prop.replace(/^values\./, '')]
    if (leftValue == null || leftValue === '') return rightValue == null || rightValue === '' ? 0 : 1
    if (rightValue == null || rightValue === '') return -1
    const leftNumber = Number(leftValue)
    const rightNumber = Number(rightValue)
    const comparison = Number.isFinite(leftNumber) && Number.isFinite(rightNumber)
      ? leftNumber - rightNumber
      : String(leftValue).localeCompare(String(rightValue), 'zh-CN', { numeric: true, sensitivity: 'base' })
    return comparison * direction
  })
})

const paginatedRecords = computed(() => {
  const startIndex = (currentPage.value - 1) * pageSize.value
  return sortedRecords.value.slice(startIndex, startIndex + pageSize.value)
})

function handleTableSortChange({ prop, order }: { prop: string; order: 'ascending' | 'descending' | null }) {
  sortState.value = order ? { prop, order } : null
  currentPage.value = 1
  clearSelectedRows()
}

function normalizeFieldToken(value: string | null | undefined) {
  return String(value ?? '').trim().toLowerCase()
}

function isDepositField(field: CustomField) {
  const normalizedLabel = field.label.trim()
  const normalizedFieldName = normalizeFieldToken(field.field_name)

  return (
    normalizedLabel === '保证金' ||
    normalizedLabel.includes('保证金') ||
    ['deposit', 'deposit_amount', 'security_deposit', 'margin'].includes(normalizedFieldName)
  )
}

void normalizeFieldToken
void isDepositField

const depositField = computed<CustomField | null>(() => null)

const depositSummary = computed(() => {
  if (!depositField.value) {
    return null
  }

  const total = filteredRecords.value.reduce((sum, record) => {
    const rawValue = record.values[depositField.value!.field_name]

    if (rawValue === null || rawValue === undefined || rawValue === '') {
      return sum
    }

    const numericValue = Number(
      String(rawValue)
        .replaceAll(',', '')
        .replaceAll('￥', '')
        .replaceAll('¥', '')
        .trim(),
    )
    return Number.isFinite(numericValue) ? sum + numericValue : sum
  }, 0)

  return {
    label: depositField.value.label,
    total,
    recordCount: filteredRecords.value.length,
  }
})

const canEditRecords = computed(() => {
  const role = authStore.currentUser?.role
  return role === 'editor' || role === 'superadmin'
})

const canManageFields = computed(() => authStore.currentUser?.role === 'superadmin')

const desktopTableHeight = computed(() => Math.max(420, viewportHeight.value - 420))
const mobileListHeight = computed(() => Math.max(420, viewportHeight.value - 320))
const pageSize = computed(() => 20)

const statusDisplay = computed(() => {
  if (!keyword.value.trim()) {
    return statusText.value
  }

  return `关键字过滤：${keyword.value.trim()}`
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

function getLoadedMessage() {
  return `已加载 ${records.value.length} 条，字段 ${fields.value.length} 个`
}

function getCurrentDateValue() {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function resetRecordForm() {
  editingRecordId.value = null

  Object.keys(recordFormValues).forEach((key) => {
    delete recordFormValues[key]
  })

  orderedFields.value.forEach((field) => {
    if (field.field_type === 'date' && field.field_name === 'date') {
      recordFormValues[field.field_name] = getCurrentDateValue()
      return
    }

    recordFormValues[field.field_name] = ''
  })
}

function openCreateDialog() {
  resetRecordForm()
  recordDialogVisible.value = true
}

function openEditDialog(record: ShopRecord) {
  resetRecordForm()
  editingRecordId.value = record.id

  orderedFields.value.forEach((field) => {
    const rawValue = record.values[field.field_name]
    recordFormValues[field.field_name] = rawValue === null || rawValue === undefined ? '' : (rawValue as string | number)
  })

  recordDialogVisible.value = true
}

function resetFieldForm() {
  fieldForm.label = ''
  fieldForm.field_name = null
  fieldForm.field_type = 'text'
  fieldForm.required = false
}

function formatFieldValue(field: CustomField, row: ShopRecord) {
  const rawValue = row.values[field.field_name]

  if (rawValue === null || rawValue === undefined || rawValue === '') {
    return '-'
  }

  if (field.field_type === 'number') {
    return formatMoney(Number(rawValue))
  }

  if (field.field_type === 'date') {
    return formatDate(String(rawValue))
  }

  return String(rawValue)
}

function getFieldMinWidth(field: CustomField) {
  const configuredWidth = shopColumnWidths.value[field.field_name]
  if (configuredWidth) return configuredWidth

  const token = `${field.field_name} ${field.label}`.toLowerCase()

  if (/remark|note|备注/.test(token)) return 260
  if (/shop.*name|store.*name|account|username|店铺名称|店铺名|账号/.test(token)) return 220
  if (/phone|mobile|手机|电话/.test(token)) return 150
  if (/link|url|链接/.test(token)) return 220
  return 150
}

function updateFieldWidth(field: CustomField, value: number | undefined) {
  shopColumnWidths.value = {
    ...shopColumnWidths.value,
    [field.field_name]: Math.min(500, Math.max(100, Number(value) || 150)),
  }
  localStorage.setItem(shopColumnWidthStorageKey, JSON.stringify(shopColumnWidths.value))
}

async function persistFieldWidth(field: CustomField, value: number | undefined) {
  updateFieldWidth(field, value)
  try {
    await saveUiSetting('shop-records-columns', shopColumnWidths.value)
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '列宽保存到服务器失败'))
  }
}

function buildRecordPayload() {
  const values: Record<string, unknown> = {}

  orderedFields.value.forEach((field) => {
    const rawValue = recordFormValues[field.field_name]

    if (field.field_type === 'number') {
      values[field.field_name] = rawValue === '' || rawValue === null ? null : Number(rawValue)
      return
    }

    if (typeof rawValue === 'string') {
      const normalized = rawValue.trim()
      values[field.field_name] = normalized ? normalized : null
      return
    }

    values[field.field_name] = rawValue ?? null
  })

  return { values }
}

async function loadData(message = '正在同步店铺台账...') {
  loading.value = true
  statusText.value = message

  try {
    const [recordData, fieldData, serverWidths] = await Promise.all([
      fetchShopRecords(),
      fetchCustomFields(),
      fetchUiSetting<Record<string, number>>('shop-records-columns').catch(() => null),
    ])
    records.value = recordData
    fields.value = fieldData
    if (serverWidths && typeof serverWidths === 'object') {
      shopColumnWidths.value = Object.fromEntries(
        Object.entries(serverWidths).map(([key, value]) => [key, Math.min(500, Math.max(100, Number(value) || 150))]),
      )
      localStorage.setItem(shopColumnWidthStorageKey, JSON.stringify(shopColumnWidths.value))
    }
    tableRef.value?.clearSelection()
    selectedIds.value = []
    statusText.value = getLoadedMessage()

    if (!recordDialogVisible.value) {
      resetRecordForm()
    }
  } catch (error) {
    const messageText = getErrorMessage(error, '加载店铺台账失败')
    statusText.value = messageText
    ElMessage.error(messageText)
  } finally {
    loading.value = false
  }
}

async function submitRecord() {
  submitLoading.value = true

  try {
    const payload = buildRecordPayload()

    if (editingRecordId.value === null) {
      await createShopRecord(payload)
      ElMessage.success('新增记录成功')
    } else {
      await updateShopRecord(editingRecordId.value, payload)
      ElMessage.success('更新记录成功')
    }

    recordDialogVisible.value = false
    await loadData('正在刷新台账列表...')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '保存记录失败'))
  } finally {
    submitLoading.value = false
  }
}

async function confirmDeleteRecord(record: ShopRecord) {
  try {
    await ElMessageBox.confirm(`确定删除记录 #${record.id} 吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })

    await deleteShopRecord(record.id)
    ElMessage.success('删除成功')
    await loadData('正在刷新台账列表...')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, '删除记录失败'))
  }
}

function handleSelectionChange(rows: ShopRecord[]) {
  selectedIds.value = rows.map((row) => row.id)
}

function clearSelectedRows() {
  tableRef.value?.clearSelection()
  selectedIds.value = []
}

async function confirmBatchDelete() {
  if (!selectedIds.value.length) {
    return
  }

  try {
    await ElMessageBox.confirm(`确定删除已选的 ${selectedIds.value.length} 条台账记录吗？`, '批量删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })

    batchLoading.value = true
    await batchDeleteShopRecords({
      record_ids: selectedIds.value,
    })
    ElMessage.success('批量删除成功')
    await loadData('正在刷新台账列表...')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, '批量删除台账记录失败'))
  } finally {
    batchLoading.value = false
  }
}

async function handleBatchCommand(command: string | number | object) {
  if (command === 'delete') {
    await confirmBatchDelete()
    return
  }

  if (command === 'clear-selection') {
    clearSelectedRows()
  }
}

async function submitField() {
  fieldSubmitLoading.value = true

  try {
    await createCustomField({
      label: fieldForm.label.trim(),
      field_name: fieldForm.field_name?.trim() ? fieldForm.field_name.trim() : null,
      field_type: fieldForm.field_type,
      required: fieldForm.required,
    })

    ElMessage.success('表头新增成功')
    resetFieldForm()
    await loadData('正在刷新字段配置...')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '新增表头失败'))
  } finally {
    fieldSubmitLoading.value = false
  }
}

async function confirmDeleteField(field: CustomField) {
  try {
    await ElMessageBox.confirm(`确定删除表头「${field.label}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })

    await deleteCustomField(field.id)
    ElMessage.success('表头删除成功')
    await loadData('正在刷新字段配置...')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, '删除表头失败'))
  }
}

async function toggleFieldVisibility(field: CustomField) {
  if (field.is_builtin) {
    return
  }

  fieldActionLoading.value = true

  try {
    await updateCustomField(field.id, {
      is_visible: !field.is_visible,
    })
    ElMessage.success(field.is_visible ? '字段已隐藏' : '字段已显示')
    await loadData('正在刷新字段配置...')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '更新字段显示状态失败'))
  } finally {
    fieldActionLoading.value = false
  }
}

async function moveField(field: CustomField, direction: 'up' | 'down') {
  const fieldIndex = orderedFields.value.findIndex((item) => item.id === field.id)
  if (fieldIndex < 0) {
    return
  }

  const targetIndex = direction === 'up' ? fieldIndex - 1 : fieldIndex + 1
  if (targetIndex < 0 || targetIndex >= orderedFields.value.length) {
    return
  }

  const reordered = [...orderedFields.value]
  const [currentField] = reordered.splice(fieldIndex, 1)
  reordered.splice(targetIndex, 0, currentField)

  fieldActionLoading.value = true

  try {
    await reorderCustomFields({
      field_ids: reordered.map((item) => item.id),
    })
    ElMessage.success('字段顺序已更新')
    await loadData('正在刷新字段顺序...')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '更新字段顺序失败'))
  } finally {
    fieldActionLoading.value = false
  }
}

watch(recordDialogVisible, (visible) => {
  if (!visible) {
    resetRecordForm()
  }
})

watch(fieldDialogVisible, (visible) => {
  if (!visible) {
    resetFieldForm()
  }
})

watch(keyword, () => {
  currentPage.value = 1
  clearSelectedRows()
})

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
  resetRecordForm()
  loadData()
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
            placeholder="搜索任意字段值"
            size="large"
            :prefix-icon="Search"
            clearable
          />
        </div>

        <div class="filter-status">
          <div class="section-desc" style="margin-bottom: 8px">系统状态</div>
          <div class="status-box" :title="statusDisplay">{{ statusDisplay }}</div>
        </div>
      </div>

      <div class="toolbar-row">
        <div>
          <h3 class="section-title" style="font-size: 16px">台账列表</h3>
          <p class="section-desc">动态表头来自后端 `custom-fields` 配置，页面已支持在线维护。</p>
        </div>

        <div class="toolbar-actions">
          <el-button type="primary" :icon="CirclePlus" :disabled="!canEditRecords" @click="openCreateDialog">
            新增记录
          </el-button>
          <el-button type="success" plain :icon="Setting" :disabled="!canManageFields" @click="fieldDialogVisible = true">
            表头管理
          </el-button>
          <div v-if="!isMobile && canEditRecords" class="toolbar-batch-group">
            <el-dropdown trigger="click" @command="handleBatchCommand">
              <el-button class="toolbar-batch-action" plain :icon="Select" :loading="batchLoading">
                批量操作
              </el-button>

              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="delete" :disabled="!selectedIds.length">
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
          <el-button :icon="RefreshRight" @click="loadData('正在手动刷新台账...')">
            刷新数据
          </el-button>
        </div>
      </div>

      <div v-if="depositSummary" class="shop-summary-wrap">
        <article class="shop-summary-card">
          <div class="shop-summary-label">{{ depositSummary.label }}总额</div>
          <div class="shop-summary-value">¥ {{ formatMoney(depositSummary.total) }}</div>
          <div class="shop-summary-note">按当前筛选结果统计，共 {{ depositSummary.recordCount }} 条记录</div>
        </article>
      </div>

      <div v-if="!isMobile" class="table-area fixed-list-shell">
        <el-table
          ref="tableRef"
          :data="paginatedRecords"
          stripe
          :height="desktopTableHeight"
          v-loading="loading"
          @selection-change="handleSelectionChange"
          @sort-change="handleTableSortChange"
        >
          <el-table-column v-if="canEditRecords" type="selection" width="50" fixed="left" />
          <el-table-column prop="id" label="ID" width="80" fixed="left" sortable="custom" />

          <el-table-column
            v-for="field in visibleFields"
            :key="field.id"
            :label="field.label"
            :min-width="getFieldMinWidth(field)"
            :prop="`values.${field.field_name}`"
            sortable="custom"
          >
            <template #header>
              <div class="shop-table-header">
                <span>{{ field.label }}</span>
                <span v-if="depositSummary && depositField?.id === field.id" class="shop-table-header__note">
                  总计 ¥ {{ formatMoney(depositSummary.total) }}
                </span>
              </div>
            </template>

            <template #default="{ row }">
              <span class="shop-table-value" :title="formatFieldValue(field, row)">
                {{ formatFieldValue(field, row) }}
              </span>
            </template>
          </el-table-column>

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
        <div v-loading="loading" class="shop-card-list fixed-list-mobile" :style="{ maxHeight: `${mobileListHeight}px` }">
          <template v-if="paginatedRecords.length">
            <article
              v-for="record in paginatedRecords"
              :key="record.id"
              class="shop-mobile-card"
            >
              <div class="shop-mobile-card__head">
                <div>
                  <h4 class="shop-mobile-card__title">台账记录 #{{ record.id }}</h4>
                  <p class="shop-mobile-card__meta">展示字段 {{ visibleFields.length }} 项</p>
                </div>
              </div>

              <div class="shop-mobile-card__fields">
                <div
                  v-for="field in visibleFields"
                  :key="field.id"
                  class="shop-mobile-card__field"
                >
                  <span class="shop-mobile-card__label">{{ field.label }}</span>
                  <span class="shop-mobile-card__value">{{ formatFieldValue(field, record) }}</span>
                </div>
              </div>

              <div v-if="canEditRecords" class="shop-mobile-card__actions">
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
            :description="keyword.trim() ? '没有匹配的台账记录' : '暂无台账记录'"
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
      :title="editingRecordId === null ? '新增记录' : `编辑记录 #${editingRecordId}`"
      width="840px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-row :gutter="16">
          <el-col v-for="field in orderedFields" :key="field.id" :span="field.field_name === 'remark' ? 24 : 12">
            <el-form-item :label="field.label" :required="field.required">
              <el-input
                v-if="field.field_type === 'text' && field.field_name !== 'remark'"
                v-model="recordFormValues[field.field_name]"
                :placeholder="`请输入${field.label}`"
              />

              <el-input
                v-else-if="field.field_type === 'text'"
                v-model="recordFormValues[field.field_name]"
                type="textarea"
                :rows="4"
                :placeholder="`请输入${field.label}`"
              />

              <el-input-number
                v-else-if="field.field_type === 'number'"
                v-model="recordFormValues[field.field_name] as number | null"
                style="width: 100%"
                :min="0"
                :precision="2"
              />

              <el-date-picker
                v-else
                v-model="recordFormValues[field.field_name]"
                type="date"
                value-format="YYYY-MM-DD"
                format="YYYY-MM-DD"
                style="width: 100%"
                :placeholder="`请选择${field.label}`"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-empty v-if="!orderedFields.length" description="当前还没有字段，请先新增表头。" />
      </el-form>

      <template #footer>
        <el-button @click="recordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="submitRecord">
          {{ editingRecordId === null ? '新增记录' : '保存修改' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="fieldDialogVisible" title="表头管理" width="780px" destroy-on-close>
      <div class="page-stack">
        <el-form label-position="top">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="表头名称" required>
                <el-input v-model="fieldForm.label" placeholder="例如：保证金" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="字段标识">
                <el-input v-model="fieldForm.field_name" placeholder="可选，例如：deposit_amount" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="字段类型">
                <el-select v-model="fieldForm.field_type" style="width: 100%">
                  <el-option label="文本" value="text" />
                  <el-option label="数字" value="number" />
                  <el-option label="日期" value="date" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="字段设置">
                <el-checkbox v-model="fieldForm.required">必填字段</el-checkbox>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>

        <div class="toolbar-actions">
          <el-button type="primary" :icon="Plus" :loading="fieldSubmitLoading" @click="submitField">
            新增表头
          </el-button>
        </div>

        <el-card shadow="never">
          <template #header>
            <div>
              <h3 class="section-title" style="font-size: 16px">当前字段</h3>
              <p class="section-desc">删除表头会影响全部台账记录，请谨慎操作。</p>
            </div>
          </template>

          <div v-if="orderedFields.length">
            <div class="section-desc" style="margin-bottom: 8px">上下滚动管理全部表头</div>
            <div class="field-cards-scroll">
              <div v-for="field in orderedFields" :key="field.id" class="field-manager-panel">
              <div style="min-width: 0">
                <div style="font-weight: 700">{{ field.label }}</div>
                <div class="section-desc">
                  {{ field.field_name }} · {{ field.field_type }} · {{ field.required ? '必填' : '选填' }}
                  <span v-if="field.is_builtin"> · 内置字段</span>
                  <span> · {{ field.is_visible ? '列表显示' : '列表隐藏' }}</span>
                </div>
              </div>

              <div class="field-manage-actions">
                <div class="field-column-width">
                  <span>列宽 {{ getFieldMinWidth(field) }}</span>
                  <el-slider
                    :model-value="getFieldMinWidth(field)"
                    :min="100"
                    :max="500"
                    :step="10"
                    @input="(value: number | undefined) => updateFieldWidth(field, value)"
                    @change="(value: number | undefined) => persistFieldWidth(field, value)"
                  />
                </div>
                <el-button
                  plain
                  :icon="ArrowUp"
                  :disabled="fieldActionLoading || orderedFields[0]?.id === field.id"
                  @click="moveField(field, 'up')"
                >
                  上移
                </el-button>
                <el-button
                  plain
                  :icon="ArrowDown"
                  :disabled="fieldActionLoading || orderedFields[orderedFields.length - 1]?.id === field.id"
                  @click="moveField(field, 'down')"
                >
                  下移
                </el-button>
                <el-button
                  plain
                  :icon="field.is_visible ? Hide : View"
                  :disabled="fieldActionLoading || field.is_builtin"
                  @click="toggleFieldVisibility(field)"
                >
                  {{ field.is_visible ? '隐藏' : '显示' }}
                </el-button>
                <el-button
                  type="danger"
                  plain
                  :icon="Delete"
                  :disabled="fieldActionLoading"
                  @click="confirmDeleteField(field)"
                >
                  删除
                </el-button>
              </div>
              </div>
            </div>
          </div>

          <el-empty v-else description="当前没有字段" />
        </el-card>
      </div>

      <template #footer>
        <el-button @click="fieldDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.shop-summary-wrap {
  padding: 18px 22px 0;
}

.shop-summary-card {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
  border: 1px solid #dbe6f5;
  border-radius: 16px;
  background: linear-gradient(180deg, #ffffff 0%, #f6faff 100%);
}

.shop-summary-label {
  color: var(--text-secondary);
  font-size: 13px;
}

.shop-summary-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.1;
}

.shop-summary-note {
  color: var(--text-secondary);
  font-size: 12px;
}

.shop-table-header {
  display: grid;
  gap: 2px;
}

.shop-table-header__note {
  color: var(--brand-primary);
  font-size: 12px;
  font-weight: 600;
}

.shop-table-value {
  display: block;
  width: 100%;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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

.field-manage-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.field-manager-panel {
  display: grid;
  gap: 16px;
  padding: 16px;
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  background: #f8fafc;
}

.field-cards-scroll {
  display: grid;
  gap: 12px;
  max-height: 420px;
  padding-right: 6px;
  overflow-y: auto;
  scrollbar-width: thin;
}

.field-column-width {
  display: grid;
  grid-template-columns: 72px 180px;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 13px;
  white-space: nowrap;
}

.field-column-width :deep(.el-slider) {
  width: 180px;
}

.shop-card-list {
  display: grid;
  gap: 12px;
  min-height: 180px;
}

.shop-mobile-card {
  display: grid;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--panel-border);
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: 0 10px 24px rgba(31, 41, 55, 0.06);
}

.shop-mobile-card__title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
}

.shop-mobile-card__meta {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
}

.shop-mobile-card__fields {
  display: grid;
  gap: 10px;
}

.shop-mobile-card__field {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border: 1px solid #e6edf7;
  border-radius: 14px;
  background: #fbfdff;
}

.shop-mobile-card__label {
  color: var(--text-secondary);
  font-size: 12px;
}

.shop-mobile-card__value {
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.shop-mobile-card__actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.shop-mobile-card__actions .el-button {
  width: 100%;
  margin: 0;
}

@media (max-width: 768px) {
  .shop-summary-wrap {
    padding: 16px 16px 0;
  }

  .shop-summary-value {
    font-size: 24px;
  }
}

@media (max-width: 520px) {
  .shop-mobile-card__actions {
    grid-template-columns: 1fr;
  }
}
</style>
