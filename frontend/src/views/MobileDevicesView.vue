<script setup lang="ts">
import { CirclePlus, Delete, EditPen, RefreshRight, Search, Select } from '@element-plus/icons-vue'
import type { TableInstance } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  batchDeleteMobileDevices,
  createMobileDevice,
  deleteMobileDevice,
  fetchMobileDevices,
  fetchUiSetting,
  saveUiSetting,
  updateMobileDevice,
} from '../api'
import ListPaginationFooter from '../components/ListPaginationFooter.vue'
import TableHeaderManager, { type ManagedTableColumn } from '../components/TableHeaderManager.vue'
import { useViewport } from '../composables/useViewport'
import { useAuthStore } from '../stores/auth'
import type { MobileDeviceRecord } from '../types/api'
import { formatDateTime } from '../utils/format'

const authStore = useAuthStore()
const { isMobile, viewportHeight } = useViewport()

const loading = ref(false)
const submitLoading = ref(false)
const batchLoading = ref(false)
const currentPage = ref(1)
const keyword = ref('')
const statusText = ref('准备就绪')
const records = ref<MobileDeviceRecord[]>([])
const selectedIds = ref<number[]>([])
const tableRef = ref<TableInstance>()
const tableColumns = ref<ManagedTableColumn[]>([
  { key: 'id', label: 'ID', minWidth: 100, visible: true },
  { key: 'device_name', label: '手机设备', minWidth: 180, visible: true },
  { key: 'primary_card', label: '主卡', minWidth: 180, visible: true },
  { key: 'secondary_card', label: '副口', minWidth: 180, visible: true },
  { key: 'remark', label: '备注', minWidth: 280, visible: true },
  { key: 'created_at', label: '创建时间', minWidth: 170, visible: true },
])
const visibleTableColumns = computed(() => tableColumns.value.filter((column) => column.visible))

async function saveTableColumns(columns: ManagedTableColumn[]) {
  tableColumns.value = columns
  await saveUiSetting('mobile-device-columns', columns)
}

const dialogVisible = ref(false)
const editingRecordId = ref<number | null>(null)
const form = reactive({
  device_name: '',
  primary_card: '',
  secondary_card: '',
  remark: '',
  extra_fields: {} as Record<string, string>,
})

const canEditRecords = computed(() => {
  return authStore.canWrite('mobile_devices')
})

const desktopTableHeight = computed(() => Math.max(420, viewportHeight.value - 360))
const pageSize = computed(() => 20)

const filteredRecords = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase()
  if (!normalizedKeyword) {
    return records.value
  }

  return records.value.filter((record) =>
    [
      record.device_name,
      record.primary_card ?? '',
      record.secondary_card ?? '',
      record.remark ?? '',
      ...Object.values(record.extra_fields ?? {}),
    ]
      .join(' ')
      .toLowerCase()
      .includes(normalizedKeyword),
  )
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredRecords.value.length / pageSize.value)))

const paginatedRecords = computed(() => {
  const startIndex = (currentPage.value - 1) * pageSize.value
  return filteredRecords.value.slice(startIndex, startIndex + pageSize.value)
})

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

function resetForm() {
  editingRecordId.value = null
  form.device_name = ''
  form.primary_card = ''
  form.secondary_card = ''
  form.remark = ''
  form.extra_fields = {}
}

function openCreateDialog() {
  resetForm()
  dialogVisible.value = true
}

function openEditDialog(record: MobileDeviceRecord) {
  resetForm()
  editingRecordId.value = record.id
  form.device_name = record.device_name
  form.primary_card = record.primary_card ?? ''
  form.secondary_card = record.secondary_card ?? ''
  form.remark = record.remark ?? ''
  form.extra_fields = Object.fromEntries(Object.entries(record.extra_fields ?? {}).map(([key, value]) => [key, String(value ?? '')]))
  dialogVisible.value = true
}

function buildPayload() {
  return {
    device_name: form.device_name.trim(),
    primary_card: form.primary_card.trim() || null,
    secondary_card: form.secondary_card.trim() || null,
    remark: form.remark.trim() || null,
    extra_fields: { ...form.extra_fields },
  }
}

async function loadData(message = '正在同步手机设备列表...') {
  loading.value = true
  statusText.value = message

  try {
    const [recordData, savedColumns] = await Promise.all([
      fetchMobileDevices(),
      fetchUiSetting<ManagedTableColumn[]>('mobile-device-columns').catch(() => null),
    ])
    records.value = recordData
    if (Array.isArray(savedColumns) && savedColumns.length) tableColumns.value = savedColumns
    tableRef.value?.clearSelection()
    selectedIds.value = []
    statusText.value = `已加载 ${records.value.length} 条手机设备记录`
  } catch (error) {
    const messageText = getErrorMessage(error, '加载手机设备列表失败')
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
    if (!payload.device_name) {
      ElMessage.warning('手机设备不能为空')
      return
    }

    if (editingRecordId.value === null) {
      await createMobileDevice(payload)
      ElMessage.success('新增手机设备成功')
    } else {
      await updateMobileDevice(editingRecordId.value, payload)
      ElMessage.success('更新手机设备成功')
    }

    dialogVisible.value = false
    await loadData('正在刷新手机设备列表...')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '保存手机设备失败'))
  } finally {
    submitLoading.value = false
  }
}

async function confirmDeleteRecord(record: MobileDeviceRecord) {
  try {
    await ElMessageBox.confirm(`确定删除手机设备「${record.device_name}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })

    await deleteMobileDevice(record.id)
    ElMessage.success('删除成功')
    await loadData('正在刷新手机设备列表...')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, '删除手机设备失败'))
  }
}

function handleSelectionChange(rows: MobileDeviceRecord[]) {
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
    await ElMessageBox.confirm(`确定删除已选的 ${selectedIds.value.length} 条手机设备记录吗？`, '批量删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })

    batchLoading.value = true
    await batchDeleteMobileDevices({ record_ids: selectedIds.value })
    ElMessage.success('批量删除成功')
    await loadData('正在刷新手机设备列表...')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, '批量删除手机设备失败'))
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

watch(dialogVisible, (visible) => {
  if (!visible) {
    resetForm()
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

onMounted(loadData)
</script>

<template>
  <div class="page-stack">
    <section class="page-block list-surface list-surface--fixed">
      <div class="filter-panel">
        <div class="query-grow">
          <div class="section-desc" style="margin-bottom: 8px">关键字查询</div>
          <el-input
            v-model="keyword"
            placeholder="搜索手机设备、主卡、副口或备注"
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
          <h3 class="section-title" style="font-size: 16px">手机设备列表</h3>
          <p class="section-desc">独立维护手机设备、主卡、副口和备注，风格与店铺管理下其他二级列表保持一致。</p>
        </div>

        <div class="toolbar-actions">
          <el-button type="primary" :icon="CirclePlus" :disabled="!canEditRecords" @click="openCreateDialog">
            新增手机设备
          </el-button>
          <TableHeaderManager v-model:columns="tableColumns" @save="saveTableColumns" />
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
          <el-button :icon="RefreshRight" @click="loadData('正在手动刷新手机设备列表...')">
            刷新数据
          </el-button>
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
          <el-table-column v-if="canEditRecords" type="selection" width="50" fixed="left" />
          <el-table-column
            v-for="column in visibleTableColumns"
            :key="column.key"
            :prop="column.key"
            :label="column.label"
            :min-width="column.minWidth"
            show-overflow-tooltip
            sortable
          >
            <template #default="{ row }">
              {{ column.custom ? (row.extra_fields?.[column.key] ?? '-') : column.key === 'created_at' ? formatDateTime(row.created_at) : (row[column.key as keyof MobileDeviceRecord] ?? '-') }}
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
        <div v-loading="loading" class="account-card-list fixed-list-mobile">
          <template v-if="paginatedRecords.length">
            <article
              v-for="record in paginatedRecords"
              :key="record.id"
              class="account-mobile-card"
            >
              <div class="account-mobile-card__head">
                <div class="account-mobile-card__title-block">
                  <h4 class="account-mobile-card__title">{{ record.device_name }}</h4>
                  <p class="account-mobile-card__meta">
                    ID {{ record.id }} · {{ formatDateTime(record.created_at) }}
                  </p>
                </div>
              </div>

              <div class="account-mobile-card__grid">
                <div class="account-mobile-card__field">
                  <span class="account-mobile-card__label">主卡</span>
                  <span class="account-mobile-card__value">{{ record.primary_card || '未设置' }}</span>
                </div>

                <div class="account-mobile-card__field">
                  <span class="account-mobile-card__label">副口</span>
                  <span class="account-mobile-card__value">{{ record.secondary_card || '未设置' }}</span>
                </div>
              </div>

              <div class="account-mobile-card__notes">
                <div class="account-mobile-card__label">备注</div>
                <p class="account-mobile-card__notes-text">
                  {{ record.remark || '暂无备注' }}
                </p>
              </div>

              <div v-if="canEditRecords" class="account-mobile-card__actions">
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
            :description="keyword.trim() ? '没有匹配的手机设备' : '暂无手机设备记录'"
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
      v-model="dialogVisible"
      :title="editingRecordId === null ? '新增手机设备' : `编辑手机设备 #${editingRecordId}`"
      width="860px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="手机设备" required>
              <el-input v-model="form.device_name" placeholder="例如：小米13 / 华为 Mate 60 / 1号机" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="主卡">
              <el-input v-model="form.primary_card" placeholder="例如：移动主号 / 电信卡" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="副口">
              <el-input v-model="form.secondary_card" placeholder="例如：联通副卡 / 备用卡" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input
                v-model="form.remark"
                type="textarea"
                :rows="4"
                placeholder="记录设备用途、归属人、套餐说明或其它补充信息"
              />
            </el-form-item>
          </el-col>
          <el-col v-for="column in tableColumns.filter((item) => item.custom)" :key="column.key" :span="12">
            <el-form-item :label="column.label">
              <el-input v-model="form.extra_fields[column.key]" :placeholder="`请输入${column.label}`" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="submitRecord">
          {{ editingRecordId === null ? '新增手机设备' : '保存修改' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
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

.account-card-list {
  display: grid;
  gap: 12px;
  min-height: 180px;
}

.account-mobile-card {
  display: grid;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--panel-border);
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: 0 10px 24px rgba(31, 41, 55, 0.06);
}

.account-mobile-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.account-mobile-card__title-block {
  min-width: 0;
}

.account-mobile-card__title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.35;
  word-break: break-all;
}

.account-mobile-card__meta {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.account-mobile-card__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.account-mobile-card__field {
  display: grid;
  gap: 4px;
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid #e6edf7;
  border-radius: 14px;
  background: #fbfdff;
}

.account-mobile-card__label {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.4;
}

.account-mobile-card__value {
  min-width: 0;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.45;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.account-mobile-card__notes {
  display: grid;
  gap: 8px;
}

.account-mobile-card__notes-text {
  margin: 0;
  padding: 12px 14px;
  border: 1px solid #e6edf7;
  border-radius: 14px;
  background: #fbfdff;
  line-height: 1.65;
  color: var(--text-main);
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

.account-mobile-card__actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.account-mobile-card__actions .el-button {
  width: 100%;
  margin: 0;
}

@media (max-width: 520px) {
  .account-mobile-card__grid,
  .account-mobile-card__actions {
    grid-template-columns: 1fr;
  }
}
</style>
