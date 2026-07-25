<script setup lang="ts">
import {
  ArrowDown,
  ArrowUp,
  CirclePlus,
  Delete,
  Download,
  EditPen,
  Hide,
  Picture,
  RefreshLeft,
  RefreshRight,
  Search,
  Select,
  Setting,
  UploadFilled,
  View,
} from '@element-plus/icons-vue'
import type { TableInstance, UploadFile, UploadInstance, UploadProps, UploadRawFile } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
  batchDeleteLicenseRecords,
  createLicenseRecord,
  deleteLicenseImage,
  deleteLicenseRecord,
  fetchLicenseRecords,
  fetchUiSetting,
  saveUiSetting,
  updateLicenseRecord,
  uploadLicenseImage,
} from '../api'
import ListPaginationFooter from '../components/ListPaginationFooter.vue'
import { useViewport } from '../composables/useViewport'
import { useAuthStore } from '../stores/auth'
import type { LicenseRecord } from '../types/api'
import { formatDate, formatDateTime } from '../utils/format'

const authStore = useAuthStore()
const { isMobile, viewportHeight } = useViewport()

const loading = ref(false)
const submitLoading = ref(false)
const batchLoading = ref(false)
const currentPage = ref(1)
const keyword = ref('')
const sortKey = ref<string | null>(null)
const sortOrder = ref<'ascending' | 'descending' | null>(null)
const statusText = ref('准备就绪')
const records = ref<LicenseRecord[]>([])
const selectedIds = ref<number[]>([])
const tableRef = ref<TableInstance>()

const dialogVisible = ref(false)
const columnDialogVisible = ref(false)
const editingRecordId = ref<number | null>(null)
const imageActionLoadingId = ref<number | null>(null)
const previewDialogVisible = ref(false)
const previewDialogUrl = ref('')
const previewDialogTitle = ref('')
const previewRotation = ref(0)
const previewStageRef = ref<HTMLElement | null>(null)
const previewStageSize = reactive({ width: 0, height: 0 })

const previewImageStyle = computed(() => {
  const availableWidth = Math.max(1, previewStageSize.width - 24)
  const availableHeight = Math.max(1, previewStageSize.height - 24)
  const isSideways = previewRotation.value % 180 !== 0

  return {
    width: `${isSideways ? availableHeight : availableWidth}px`,
    height: `${isSideways ? availableWidth : availableHeight}px`,
    transform: `translate(-50%, -50%) rotate(${previewRotation.value}deg)`,
  }
})

const uploadRef = ref<UploadInstance>()
const quickReplaceInputRef = ref<HTMLInputElement | null>(null)
const quickReplaceTargetRecordId = ref<number | null>(null)
const selectedImageFile = ref<File | null>(null)
const imagePreviewUrl = ref('')
const currentImageUrl = ref('')
const uploadFileList = ref<UploadFile[]>([])

type BuiltinLicenseColumnKey =
  | 'subject_name'
  | 'credit_code'
  | 'image'
  | 'legal_representative'
  | 'issue_date'
  | 'expiry_date'
  | 'created_at'
  | 'remark'

interface LicenseColumnSetting {
  key: string
  label: string
  minWidth: number
  visible: boolean
  custom?: boolean
}

const licenseColumnStorageKey = 'ruoshop.licenses.columns.v1'
const defaultLicenseColumns: LicenseColumnSetting[] = [
  { key: 'subject_name', label: '主体名称', minWidth: 220, visible: true },
  { key: 'credit_code', label: '统一社会信用代码', minWidth: 210, visible: true },
  { key: 'image', label: '执照图片', minWidth: 320, visible: true },
  { key: 'legal_representative', label: '法人', minWidth: 120, visible: true },
  { key: 'issue_date', label: '发证日期', minWidth: 120, visible: true },
  { key: 'expiry_date', label: '到期日期', minWidth: 120, visible: true },
  { key: 'created_at', label: '创建时间', minWidth: 160, visible: true },
  { key: 'remark', label: '备注', minWidth: 180, visible: true },
]

function createDefaultLicenseColumns() {
  return defaultLicenseColumns.map((column) => ({ ...column }))
}

function loadLicenseColumns() {
  try {
    const saved = JSON.parse(localStorage.getItem(licenseColumnStorageKey) ?? '[]') as Array<{
      key?: string
      label?: string
      visible?: boolean
      minWidth?: number
      custom?: boolean
    }>
    const byKey = new Map(defaultLicenseColumns.map((column) => [column.key, column]))
    const restored = saved
      .map((item) => {
        const column = byKey.get(item.key ?? '')
        return column
          ? {
              ...column,
              visible: item.visible !== false,
              minWidth: Math.min(500, Math.max(100, Number(item.minWidth) || column.minWidth)),
            }
          : item.custom && item.key && item.label
            ? { key: item.key, label: item.label, visible: item.visible !== false, minWidth: Math.min(500, Math.max(100, Number(item.minWidth) || 180)), custom: true }
            : null
      })
      .filter((column): column is LicenseColumnSetting => column !== null)
    const restoredKeys = new Set(restored.map((column) => column.key))
    return [...restored, ...createDefaultLicenseColumns().filter((column) => !restoredKeys.has(column.key))]
  } catch {
    return createDefaultLicenseColumns()
  }
}

const licenseColumns = ref<LicenseColumnSetting[]>(loadLicenseColumns())
const customColumnLabel = ref('')
const extraFormValues = reactive<Record<string, string>>({})
const visibleLicenseColumns = computed(() => licenseColumns.value.filter((column) => column.visible))

function saveLicenseColumns() {
  localStorage.setItem(
    licenseColumnStorageKey,
    JSON.stringify(licenseColumns.value),
  )
}

async function persistLicenseColumns() {
  saveLicenseColumns()
  try {
    await saveUiSetting(
      'license-records-columns',
      licenseColumns.value,
    )
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '表头设置保存到服务器失败'))
  }
}

function toggleLicenseColumn(column: LicenseColumnSetting) {
  if (column.visible && visibleLicenseColumns.value.length === 1) {
    ElMessage.warning('至少保留一个显示列')
    return
  }
  column.visible = !column.visible
  void persistLicenseColumns()
}

function moveLicenseColumn(column: LicenseColumnSetting, direction: 'up' | 'down') {
  const index = licenseColumns.value.findIndex((item) => item.key === column.key)
  const targetIndex = direction === 'up' ? index - 1 : index + 1
  if (index < 0 || targetIndex < 0 || targetIndex >= licenseColumns.value.length) return
  const reordered = [...licenseColumns.value]
  const [current] = reordered.splice(index, 1)
  reordered.splice(targetIndex, 0, current)
  licenseColumns.value = reordered
  void persistLicenseColumns()
}

function resetLicenseColumns() {
  licenseColumns.value = createDefaultLicenseColumns()
  void persistLicenseColumns()
  ElMessage.success('表头已恢复默认')
}

function updateLicenseColumnWidth(column: LicenseColumnSetting, value: number | undefined) {
  column.minWidth = Math.min(500, Math.max(100, Number(value) || 100))
  saveLicenseColumns()
}

async function persistLicenseColumnWidth(column: LicenseColumnSetting, value: number | undefined) {
  updateLicenseColumnWidth(column, value)
  await persistLicenseColumns()
}

function applyServerLicenseColumns(saved: Array<{ key?: string; label?: string; visible?: boolean; minWidth?: number; custom?: boolean }>) {
  const byKey = new Map(defaultLicenseColumns.map((column) => [column.key, column]))
  const restored = saved
    .map((item) => {
      const column = byKey.get(item.key as BuiltinLicenseColumnKey)
      return column
        ? {
            ...column,
            visible: item.visible !== false,
            minWidth: Math.min(500, Math.max(100, Number(item.minWidth) || column.minWidth)),
          }
        : item.custom && item.key && item.label
          ? { key: item.key, label: item.label, visible: item.visible !== false, minWidth: Math.min(500, Math.max(100, Number(item.minWidth) || 180)), custom: true }
          : null
    })
    .filter((column): column is LicenseColumnSetting => column !== null)
  const restoredKeys = new Set(restored.map((column) => column.key))
  licenseColumns.value = [...restored, ...createDefaultLicenseColumns().filter((column) => !restoredKeys.has(column.key))]
  saveLicenseColumns()
}

function addLicenseColumn() {
  const label = customColumnLabel.value.trim()
  if (!label) return ElMessage.warning('请输入表头名称')
  licenseColumns.value.push({ key: `custom_${Date.now()}`, label, minWidth: 180, visible: true, custom: true })
  customColumnLabel.value = ''
  void persistLicenseColumns()
}

function removeLicenseColumn(column: LicenseColumnSetting) {
  if (!column.custom) return
  licenseColumns.value = licenseColumns.value.filter((item) => item.key !== column.key)
  void persistLicenseColumns()
}

const form = reactive({
  subject_name: '',
  credit_code: '',
  legal_representative: '',
  issue_date: '',
  expiry_date: '',
  remark: '',
})

let objectPreviewUrl: string | null = null

const canEditLicenses = computed(() => {
  const role = authStore.currentUser?.role
  return role === 'editor' || role === 'superadmin'
})

const editingImageRecord = computed(() =>
  editingRecordId.value === null
    ? null
    : records.value.find((record) => record.id === editingRecordId.value) ?? null,
)

const desktopTableHeight = computed(() => Math.max(420, viewportHeight.value - 360))
const mobileListHeight = computed(() => Math.max(420, viewportHeight.value - 300))
const pageSize = computed(() => 20)

const filteredRecords = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase()
  if (!normalizedKeyword) {
    return records.value
  }

  return records.value.filter((record) => {
    return [
      record.subject_name,
      record.credit_code,
      record.legal_representative ?? '',
      record.remark ?? '',
      record.issue_date ?? '',
      record.expiry_date ?? '',
      record.image_name ?? '',
    ]
      .join(' ')
      .toLowerCase()
      .includes(normalizedKeyword)
  })
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredRecords.value.length / pageSize.value)))

const sortedRecords = computed(() => {
  if (!sortKey.value || !sortOrder.value) return filteredRecords.value

  const direction = sortOrder.value === 'ascending' ? 1 : -1
  const key = sortKey.value
  return [...filteredRecords.value].sort((left, right) => {
    if (key === 'id') return (left.id - right.id) * direction
    if (key === 'image') return (Number(Boolean(left.image_url)) - Number(Boolean(right.image_url))) * direction

    const builtinKey = key as Exclude<BuiltinLicenseColumnKey, 'image'>
    const leftValue = String(key.startsWith('custom_') ? left.extra_fields[key] ?? '' : left[builtinKey] ?? '').trim()
    const rightValue = String(key.startsWith('custom_') ? right.extra_fields[key] ?? '' : right[builtinKey] ?? '').trim()
    return leftValue.localeCompare(rightValue, 'zh-CN', { numeric: true, sensitivity: 'base' }) * direction
  })
})

const paginatedRecords = computed(() => {
  const startIndex = (currentPage.value - 1) * pageSize.value
  return sortedRecords.value.slice(startIndex, startIndex + pageSize.value)
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

function formatLicenseColumnValue(column: LicenseColumnSetting, row: LicenseRecord) {
  if (column.key === 'issue_date') return formatDate(row.issue_date)
  if (column.key === 'expiry_date') return formatDate(row.expiry_date)
  if (column.key === 'created_at') return formatDateTime(row.created_at)
  if (column.key === 'image') return ''
  if (column.custom) return String(row.extra_fields[column.key] ?? '-').trim() || '-'
  return String(row[column.key as Exclude<BuiltinLicenseColumnKey, 'image'>] ?? '-').trim() || '-'
}

function handleTableSortChange({ prop, order }: { prop: string; order: 'ascending' | 'descending' | null }) {
  sortKey.value = order ? prop : null
  sortOrder.value = order
  currentPage.value = 1
  clearSelectedRows()
}

function releasePreviewUrl() {
  if (objectPreviewUrl) {
    URL.revokeObjectURL(objectPreviewUrl)
    objectPreviewUrl = null
  }
}

function setExistingPreview(url: string | null) {
  releasePreviewUrl()
  currentImageUrl.value = url ?? ''
  imagePreviewUrl.value = url ?? ''
}

function setFilePreview(file: File) {
  releasePreviewUrl()
  objectPreviewUrl = URL.createObjectURL(file)
  imagePreviewUrl.value = objectPreviewUrl
}

function validateImageFile(file: Pick<File, 'type' | 'size'>) {
  const allowedTypes = ['image/jpeg', 'image/png', 'image/webp']
  if (!allowedTypes.includes(file.type)) {
    ElMessage.error('仅支持 JPG、PNG、WebP 图片')
    return false
  }

  if (file.size > 15 * 1024 * 1024) {
    ElMessage.error('图片大小不能超过 15MB')
    return false
  }

  return true
}

function mergeUpdatedRecord(updatedRecord: LicenseRecord) {
  records.value = records.value.map((record) => (record.id === updatedRecord.id ? updatedRecord : record))

  if (editingRecordId.value === updatedRecord.id) {
    selectedImageFile.value = null
    uploadFileList.value = []
    uploadRef.value?.clearFiles()
    setExistingPreview(updatedRecord.image_url)
  }
}

function resetForm() {
  editingRecordId.value = null
  form.subject_name = ''
  form.credit_code = ''
  form.legal_representative = ''
  form.issue_date = ''
  form.expiry_date = ''
  form.remark = ''
  Object.keys(extraFormValues).forEach((key) => delete extraFormValues[key])
  selectedImageFile.value = null
  uploadFileList.value = []
  setExistingPreview(null)
  uploadRef.value?.clearFiles()
}

function openCreateDialog() {
  resetForm()
  dialogVisible.value = true
}

function openEditDialog(record: LicenseRecord) {
  resetForm()
  editingRecordId.value = record.id
  form.subject_name = record.subject_name
  form.credit_code = record.credit_code
  form.legal_representative = record.legal_representative ?? ''
  form.issue_date = record.issue_date ?? ''
  form.expiry_date = record.expiry_date ?? ''
  form.remark = record.remark ?? ''
  licenseColumns.value.filter((column) => column.custom).forEach((column) => {
    extraFormValues[column.key] = String(record.extra_fields[column.key] ?? '')
  })
  setExistingPreview(record.image_url)
  dialogVisible.value = true
}

const handleManualUpload: UploadProps['httpRequest'] = async (options) => {
  selectedImageFile.value = options.file as File
  setFilePreview(options.file as File)
  options.onSuccess?.({})
}

function buildPayload() {
  return {
    subject_name: form.subject_name.trim(),
    credit_code: form.credit_code.trim(),
    legal_representative: form.legal_representative.trim() || null,
    issue_date: form.issue_date || null,
    expiry_date: form.expiry_date || null,
    remark: form.remark.trim() || null,
    extra_fields: Object.fromEntries(licenseColumns.value.filter((column) => column.custom).map((column) => [column.key, extraFormValues[column.key]?.trim() || null])),
  }
}

function triggerQuickReplace(record: LicenseRecord) {
  quickReplaceTargetRecordId.value = record.id
  if (quickReplaceInputRef.value) {
    quickReplaceInputRef.value.value = ''
    quickReplaceInputRef.value.click()
  }
}

async function handleQuickReplaceInput(event: Event) {
  const input = event.target as HTMLInputElement | null
  const file = input?.files?.[0]
  const recordId = quickReplaceTargetRecordId.value

  if (!file || recordId === null) {
    return
  }

  if (!validateImageFile(file)) {
    input.value = ''
    return
  }

  imageActionLoadingId.value = recordId
  try {
    const updatedRecord = await uploadLicenseImage(recordId, file)
    mergeUpdatedRecord(updatedRecord)
    ElMessage.success('执照图片已替换')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '替换执照图片失败'))
  } finally {
    imageActionLoadingId.value = null
    quickReplaceTargetRecordId.value = null
    input.value = ''
  }
}

async function loadData(message = '正在同步执照档案...') {
  loading.value = true
  statusText.value = message

  try {
    const [recordData, serverColumns] = await Promise.all([
      fetchLicenseRecords(),
      fetchUiSetting<Array<{ key?: string; label?: string; visible?: boolean; minWidth?: number; custom?: boolean }>>('license-records-columns').catch(() => null),
    ])
    records.value = recordData
    if (Array.isArray(serverColumns)) applyServerLicenseColumns(serverColumns)
    tableRef.value?.clearSelection()
    selectedIds.value = []
    statusText.value = `已加载 ${records.value.length} 条执照记录`
  } catch (error) {
    const messageText = getErrorMessage(error, '加载执照档案失败')
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

    if (!payload.subject_name || !payload.credit_code) {
      ElMessage.warning('主体名称和统一社会信用代码不能为空')
      return
    }

    const isCreating = editingRecordId.value === null
    let savedRecord: LicenseRecord
    if (isCreating) {
      savedRecord = await createLicenseRecord(payload)
      editingRecordId.value = savedRecord.id
    } else {
      const recordId = editingRecordId.value
      if (recordId === null) {
        throw new Error('当前执照记录缺少 ID，无法更新')
      }
      savedRecord = await updateLicenseRecord(recordId, payload)
    }

    let imageUploadErrorMessage = ''
    if (selectedImageFile.value) {
      try {
        savedRecord = await uploadLicenseImage(savedRecord.id, selectedImageFile.value)
      } catch (error) {
        imageUploadErrorMessage = getErrorMessage(error, '执照图片上传失败')
      }
    }

    if (savedRecord.image_url) {
      setExistingPreview(savedRecord.image_url)
    }

    dialogVisible.value = false
    await loadData('正在刷新执照档案...')

    if (imageUploadErrorMessage) {
      ElMessage.warning(
        `${isCreating ? '执照资料已新增' : '执照资料已更新'}，但图片上传失败：${imageUploadErrorMessage}`,
      )
      return
    }

    ElMessage.success(isCreating ? '新增执照成功' : '更新执照成功')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '保存执照失败'))
  } finally {
    submitLoading.value = false
  }
}

async function confirmDeleteRecord(record: LicenseRecord) {
  try {
    await ElMessageBox.confirm(`确定删除执照 #${record.id} 吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })

    await deleteLicenseRecord(record.id)
    ElMessage.success('删除成功')
    await loadData('正在刷新执照档案...')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, '删除执照失败'))
  }
}

async function confirmDeleteImage(record: LicenseRecord) {
  if (!record.image_url) {
    ElMessage.warning('当前没有可删除的执照图片')
    return
  }

  try {
    await ElMessageBox.confirm(`确定删除「${record.subject_name}」的执照图片吗？`, '删除图片确认', {
      type: 'warning',
      confirmButtonText: '删除图片',
      cancelButtonText: '取消',
    })

    imageActionLoadingId.value = record.id
    const updatedRecord = await deleteLicenseImage(record.id)
    mergeUpdatedRecord(updatedRecord)
    ElMessage.success('执照图片已删除')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, '删除执照图片失败'))
  } finally {
    imageActionLoadingId.value = null
  }
}

function handleSelectionChange(rows: LicenseRecord[]) {
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
    await ElMessageBox.confirm(`确定删除已选的 ${selectedIds.value.length} 条执照记录吗？`, '批量删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })

    batchLoading.value = true
    await batchDeleteLicenseRecords({
      record_ids: selectedIds.value,
    })
    ElMessage.success('批量删除成功')
    await loadData('正在刷新执照档案...')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, '批量删除执照失败'))
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

function beforeImageUpload(rawFile: UploadRawFile) {
  if (!validateImageFile(rawFile)) {
    return false
  }

  selectedImageFile.value = rawFile
  setFilePreview(rawFile)
  return true
}

function handleUploadChange(uploadFile: UploadFile) {
  uploadFileList.value = uploadFile.status === 'fail' ? [] : [uploadFile]
  if (uploadFile.raw) {
    selectedImageFile.value = uploadFile.raw
    setFilePreview(uploadFile.raw)
  }
}

function handleUploadRemove() {
  selectedImageFile.value = null
  uploadFileList.value = []
  setExistingPreview(currentImageUrl.value || null)
}

function openImage(url: string, title: string) {
  previewDialogUrl.value = url
  previewDialogTitle.value = title
  previewRotation.value = 0
  previewDialogVisible.value = true
  void nextTick(updatePreviewStageSize)
}

function updatePreviewStageSize() {
  const stage = previewStageRef.value
  if (!stage) return
  previewStageSize.width = stage.clientWidth
  previewStageSize.height = stage.clientHeight
}

function rotatePreview(step: number) {
  previewRotation.value = (previewRotation.value + step + 360) % 360
}

function resetPreviewRotation() {
  previewRotation.value = 0
}

async function downloadPreviewImage() {
  if (!previewDialogUrl.value) return

  try {
    const response = await fetch(previewDialogUrl.value, { credentials: 'same-origin' })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const objectUrl = URL.createObjectURL(await response.blob())
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = previewDialogTitle.value.trim() || 'license-image'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(objectUrl)
  } catch {
    ElMessage.error('图片下载失败，请稍后重试')
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

onBeforeUnmount(() => {
  releasePreviewUrl()
  window.removeEventListener('resize', updatePreviewStageSize)
})

onMounted(() => {
  window.addEventListener('resize', updatePreviewStageSize)
  loadData()
})
</script>

<template>
  <div class="page-stack">
    <input
      ref="quickReplaceInputRef"
      type="file"
      accept="image/jpeg,image/png,image/webp"
      style="display: none"
      @change="handleQuickReplaceInput"
    />

    <section class="page-block list-surface list-surface--fixed">
      <div class="filter-panel">
        <div class="query-grow">
          <div class="section-desc" style="margin-bottom: 8px">关键字查询</div>
          <el-input
            v-model="keyword"
            placeholder="搜索主体名称、信用代码、法人或备注"
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
          <h3 class="section-title" style="font-size: 16px">档案列表</h3>
          <p class="section-desc">执照图片和操作区都走统一的动作层级，不再一个像文本一个像按钮。</p>
        </div>

        <div class="toolbar-actions">
          <el-button type="primary" :icon="CirclePlus" :disabled="!canEditLicenses" @click="openCreateDialog">
            新增执照
          </el-button>
          <el-button type="success" plain :icon="Setting" @click="columnDialogVisible = true">
            表头管理
          </el-button>
          <div v-if="!isMobile && canEditLicenses" class="toolbar-batch-group">
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
          <el-button :icon="RefreshRight" @click="loadData('正在手动刷新执照档案...')">
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
          @sort-change="handleTableSortChange"
        >
          <el-table-column v-if="canEditLicenses" type="selection" width="50" fixed="left" />
          <el-table-column prop="id" label="ID" width="80" fixed="left" sortable="custom" />
          <el-table-column
            v-for="column in visibleLicenseColumns"
            :key="column.key"
            :prop="column.key"
            :label="column.label"
            :min-width="column.minWidth"
            sortable="custom"
          >
            <template #default="{ row }">
              <div v-if="column.key === 'image'" class="cell-actions">
                <el-tag :type="row.image_url ? 'success' : 'info'" round>
                  {{ row.image_url ? '已上传' : '未上传' }}
                </el-tag>
                <el-button
                  v-if="row.image_url"
                  type="primary"
                  link
                  :icon="Picture"
                  @click="openImage(row.image_url, row.image_name || row.subject_name)"
                >
                  查看
                </el-button>
                <el-button
                  v-if="canEditLicenses"
                  type="primary"
                  link
                  :loading="imageActionLoadingId === row.id"
                  @click="triggerQuickReplace(row)"
                >
                  {{ row.image_url ? '替换' : '上传' }}
                </el-button>
                <el-button
                  v-if="canEditLicenses && row.image_url"
                  type="danger"
                  link
                  :loading="imageActionLoadingId === row.id"
                  @click="confirmDeleteImage(row)"
                >
                  删除图片
                </el-button>
              </div>
              <span v-else class="license-table-value" :title="formatLicenseColumnValue(column, row)">
                {{ formatLicenseColumnValue(column, row) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column v-if="canEditLicenses" label="操作" width="160" fixed="right">
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
        <div v-loading="loading" class="license-card-list fixed-list-mobile" :style="{ maxHeight: `${mobileListHeight}px` }">
          <template v-if="paginatedRecords.length">
            <article
              v-for="record in paginatedRecords"
              :key="record.id"
              class="license-mobile-card"
            >
              <div class="license-mobile-card__head">
                <div class="license-mobile-card__title-wrap">
                  <h4 class="license-mobile-card__title">{{ record.subject_name }}</h4>
                  <p class="license-mobile-card__meta">
                    ID {{ record.id }} · {{ record.credit_code }}
                  </p>
                </div>

                <el-tag :type="record.image_url ? 'success' : 'info'" round>
                  {{ record.image_url ? '已上传图片' : '未上传图片' }}
                </el-tag>
              </div>

              <div class="license-mobile-card__grid">
                <div class="license-mobile-card__field">
                  <span class="license-mobile-card__label">法人</span>
                  <span class="license-mobile-card__value">{{ record.legal_representative || '未设置' }}</span>
                </div>

                <div class="license-mobile-card__field">
                  <span class="license-mobile-card__label">发证日期</span>
                  <span class="license-mobile-card__value">{{ formatDate(record.issue_date) }}</span>
                </div>

                <div class="license-mobile-card__field">
                  <span class="license-mobile-card__label">到期日期</span>
                  <span class="license-mobile-card__value">{{ formatDate(record.expiry_date) }}</span>
                </div>

                <div class="license-mobile-card__field">
                  <span class="license-mobile-card__label">创建时间</span>
                  <span class="license-mobile-card__value">{{ formatDateTime(record.created_at) }}</span>
                </div>
              </div>

              <div class="license-mobile-card__notes">
                <div class="license-mobile-card__label">备注</div>
                <p class="license-mobile-card__notes-text">{{ record.remark || '暂无备注' }}</p>
              </div>

              <div v-if="record.image_url || canEditLicenses" class="license-mobile-card__actions">
                <el-button
                  v-if="record.image_url"
                  type="primary"
                  plain
                  :icon="Picture"
                  @click="openImage(record.image_url, record.image_name || record.subject_name)"
                >
                  查看图片
                </el-button>
                <el-button
                  v-if="canEditLicenses"
                  type="primary"
                  plain
                  :loading="imageActionLoadingId === record.id"
                  :icon="UploadFilled"
                  @click="triggerQuickReplace(record)"
                >
                  {{ record.image_url ? '替换图片' : '上传图片' }}
                </el-button>
                <el-button
                  v-if="canEditLicenses && record.image_url"
                  type="danger"
                  plain
                  :loading="imageActionLoadingId === record.id"
                  :icon="Delete"
                  @click="confirmDeleteImage(record)"
                >
                  删除图片
                </el-button>
                <el-button
                  v-if="canEditLicenses"
                  type="primary"
                  plain
                  :icon="EditPen"
                  @click="openEditDialog(record)"
                >
                  编辑
                </el-button>
                <el-button
                  v-if="canEditLicenses"
                  type="danger"
                  plain
                  :icon="Delete"
                  @click="confirmDeleteRecord(record)"
                >
                  删除
                </el-button>
              </div>
            </article>
          </template>

          <el-empty
            v-else
            :description="keyword.trim() ? '没有匹配的执照记录' : '暂无执照记录'"
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

    <el-dialog v-model="columnDialogVisible" title="表头管理" width="760px" destroy-on-close>
      <div class="license-column-create">
        <el-input v-model="customColumnLabel" placeholder="输入新表头名称" maxlength="30" @keyup.enter="addLicenseColumn" />
        <el-button type="primary" :icon="CirclePlus" @click="addLicenseColumn">新增表头</el-button>
      </div>
      <div class="license-column-list">
        <div v-for="(column, index) in licenseColumns" :key="column.key" class="license-column-item">
          <div class="license-column-item__name">
            <span>{{ column.label }}</span>
            <small>{{ column.visible ? '列表显示' : '列表隐藏' }}</small>
          </div>
          <div class="license-column-item__actions">
            <div class="license-column-width">
              <span>列宽 {{ column.minWidth }}</span>
              <el-slider
                :model-value="column.minWidth"
                :min="100"
                :max="500"
                :step="10"
                @input="(value: number | undefined) => updateLicenseColumnWidth(column, value)"
                @change="(value: number | undefined) => persistLicenseColumnWidth(column, value)"
              />
            </div>
            <el-tooltip content="上移" placement="top">
              <el-button
                :icon="ArrowUp"
                :disabled="index === 0"
                aria-label="上移"
                @click="moveLicenseColumn(column, 'up')"
              />
            </el-tooltip>
            <el-tooltip content="下移" placement="top">
              <el-button
                :icon="ArrowDown"
                :disabled="index === licenseColumns.length - 1"
                aria-label="下移"
                @click="moveLicenseColumn(column, 'down')"
              />
            </el-tooltip>
            <el-button :icon="column.visible ? Hide : View" @click="toggleLicenseColumn(column)">
              {{ column.visible ? '隐藏' : '显示' }}
            </el-button>
            <el-button v-if="column.custom" type="danger" plain :icon="Delete" @click="removeLicenseColumn(column)">删除</el-button>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="resetLicenseColumns">恢复默认</el-button>
        <el-button type="primary" @click="columnDialogVisible = false">完成</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="dialogVisible"
      :title="editingRecordId === null ? '新增执照' : `编辑执照 #${editingRecordId}`"
      width="860px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="主体名称" required>
              <el-input v-model="form.subject_name" placeholder="请输入主体名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="统一社会信用代码" required>
              <el-input v-model="form.credit_code" placeholder="请输入统一社会信用代码" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="法人">
              <el-input v-model="form.legal_representative" placeholder="请输入法人姓名" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="发证日期">
              <el-date-picker
                v-model="form.issue_date"
                type="date"
                value-format="YYYY-MM-DD"
                format="YYYY-MM-DD"
                style="width: 100%"
                placeholder="请选择发证日期"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="到期日期">
              <el-date-picker
                v-model="form.expiry_date"
                type="date"
                value-format="YYYY-MM-DD"
                format="YYYY-MM-DD"
                style="width: 100%"
                placeholder="请选择到期日期"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <div v-if="licenseColumns.some((column) => column.custom)" class="license-extra-fields">
              <el-row :gutter="16">
                <el-col v-for="column in licenseColumns.filter((item) => item.custom)" :key="column.key" :span="12">
                  <el-form-item :label="column.label">
                    <el-input v-model="extraFormValues[column.key]" :placeholder="`请输入${column.label}`" />
                  </el-form-item>
                </el-col>
              </el-row>
            </div>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input
                v-model="form.remark"
                type="textarea"
                :rows="4"
                placeholder="记录执照用途、归档位置或补充说明"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="执照图片">
              <el-upload
                ref="uploadRef"
                :auto-upload="false"
                :show-file-list="true"
                :limit="1"
                v-model:file-list="uploadFileList"
                action="#"
                :http-request="handleManualUpload"
                :before-upload="beforeImageUpload"
                :on-change="handleUploadChange"
                :on-remove="handleUploadRemove"
              >
                <el-button type="primary" plain :icon="UploadFilled">选择图片</el-button>
                <template #tip>
                  <div class="section-desc" style="margin-top: 8px">
                    支持 JPG / PNG / WebP，大小不超过 15MB。保存后会自动上传。
                  </div>
                </template>
              </el-upload>
              <div v-if="editingImageRecord && currentImageUrl" class="license-image-inline-actions">
                <el-button
                  text
                  type="danger"
                  :icon="Delete"
                  :loading="imageActionLoadingId === editingImageRecord.id"
                  @click="confirmDeleteImage(editingImageRecord)"
                >
                  删除当前图片
                </el-button>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="24" v-if="imagePreviewUrl">
            <el-form-item label="图片预览">
              <div class="page-block" style="padding: 14px; width: 100%">
                <img
                  :src="imagePreviewUrl"
                  alt="执照预览"
                  style="display: block; max-width: 100%; max-height: 280px; border-radius: 12px; object-fit: contain; background: #f8fafc;"
                />
              </div>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="submitRecord">
          {{ editingRecordId === null ? '新增执照' : '保存修改' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="previewDialogVisible"
      :title="previewDialogTitle || '执照图片预览'"
      width="900px"
      destroy-on-close
    >
      <div class="license-preview-toolbar">
        <div class="license-preview-toolbar__rotation">
          <el-tooltip content="向左旋转" placement="top">
            <el-button :icon="RefreshLeft" aria-label="向左旋转" @click="rotatePreview(-90)" />
          </el-tooltip>
          <el-tooltip content="恢复原方向" placement="top">
            <el-button :disabled="previewRotation === 0" @click="resetPreviewRotation">
              {{ previewRotation }}°
            </el-button>
          </el-tooltip>
          <el-tooltip content="向右旋转" placement="top">
            <el-button :icon="RefreshRight" aria-label="向右旋转" @click="rotatePreview(90)" />
          </el-tooltip>
        </div>

        <el-button type="primary" :icon="Download" @click="downloadPreviewImage">
          下载原图
        </el-button>
      </div>

      <div ref="previewStageRef" class="license-preview-stage">
        <img
          v-if="previewDialogUrl"
          class="license-preview-image"
          :src="previewDialogUrl"
          :alt="previewDialogTitle || '执照图片预览'"
          :style="previewImageStyle"
          @load="updatePreviewStageSize"
        />
      </div>
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

.license-image-inline-actions {
  margin-top: 8px;
}

.license-table-value {
  display: block;
  width: 100%;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.license-column-list {
  display: grid;
  gap: 8px;
}

.license-column-create {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  margin-bottom: 14px;
}

.license-column-item {
  display: grid;
  grid-template-columns: 140px minmax(0, 1fr);
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 54px;
  padding: 8px 10px 8px 14px;
  border: 1px solid var(--panel-border);
  border-radius: 6px;
}

.license-column-item__name {
  display: grid;
  gap: 2px;
  min-width: 0;
  font-weight: 600;
}

.license-column-item__name small {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 400;
  white-space: nowrap;
}

.license-column-item__actions {
  display: inline-flex;
  align-items: center;
  flex: 0 0 auto;
  justify-content: flex-end;
}

.license-column-width {
  display: grid;
  grid-template-columns: 72px 150px;
  align-items: center;
  gap: 6px;
  margin-right: 8px;
  color: var(--text-secondary);
  font-size: 12px;
}

.license-column-width .el-slider {
  width: 150px;
}

.license-column-item__actions .el-button + .el-button {
  margin-left: 8px;
}

.license-preview-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.license-preview-toolbar__rotation {
  display: inline-flex;
  align-items: center;
}

.license-preview-toolbar__rotation .el-button + .el-button {
  margin-left: 8px;
}

.license-preview-stage {
  position: relative;
  min-height: 320px;
  height: min(70vh, 680px);
  overflow: hidden;
  border-radius: 8px;
  background: #f7f9fc;
}

.license-preview-image {
  position: absolute;
  top: 50%;
  left: 50%;
  display: block;
  object-fit: contain;
  border-radius: 8px;
  background: #ffffff;
  transition: transform 180ms ease;
}

.license-card-list {
  display: grid;
  gap: 12px;
  min-height: 180px;
}

.license-mobile-card {
  display: grid;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--panel-border);
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: 0 10px 24px rgba(31, 41, 55, 0.06);
}

.license-mobile-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.license-mobile-card__title-wrap {
  min-width: 0;
}

.license-mobile-card__title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.35;
  word-break: break-word;
}

.license-mobile-card__meta {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
  word-break: break-all;
}

.license-mobile-card__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.license-mobile-card__field {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid #e6edf7;
  border-radius: 14px;
  background: #fbfdff;
}

.license-mobile-card__label {
  color: var(--text-secondary);
  font-size: 12px;
}

.license-mobile-card__value {
  font-size: 14px;
  line-height: 1.5;
  word-break: break-word;
}

.license-mobile-card__notes {
  display: grid;
  gap: 8px;
}

.license-mobile-card__notes-text {
  margin: 0;
  padding: 12px 14px;
  border: 1px solid #e6edf7;
  border-radius: 14px;
  background: #fbfdff;
  line-height: 1.65;
  color: var(--text-main);
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  overflow: hidden;
}

.license-mobile-card__actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.license-mobile-card__actions .el-button {
  width: 100%;
  margin: 0;
}

@media (max-width: 640px) {
  .license-mobile-card__grid,
  .license-mobile-card__actions {
    grid-template-columns: 1fr;
  }
}
</style>
