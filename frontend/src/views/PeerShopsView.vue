<script setup lang="ts">
import {
  CirclePlus,
  Delete,
  EditPen,
  Link as LinkIcon,
  Picture,
  RefreshRight,
  Search,
  Select,
  UploadFilled,
} from '@element-plus/icons-vue'
import type { TableInstance, UploadFile, UploadInstance, UploadProps, UploadRawFile } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
  batchDeletePeerShops,
  createPeerShop,
  deletePeerShop,
  deletePeerShopImage,
  fetchPeerShops,
  fetchUiSetting,
  saveUiSetting,
  updatePeerShop,
  uploadPeerShopImage,
} from '../api'
import ListPaginationFooter from '../components/ListPaginationFooter.vue'
import TableHeaderManager, { type ManagedTableColumn } from '../components/TableHeaderManager.vue'
import { useViewport } from '../composables/useViewport'
import { useAuthStore } from '../stores/auth'
import type { PeerShop } from '../types/api'
import { formatDateTime } from '../utils/format'

const authStore = useAuthStore()
const { isMobile, viewportHeight } = useViewport()

const loading = ref(false)
const submitLoading = ref(false)
const batchLoading = ref(false)
const currentPage = ref(1)
const keyword = ref('')
const statusText = ref('准备就绪')
const records = ref<PeerShop[]>([])
const selectedIds = ref<number[]>([])
const tableRef = ref<TableInstance>()
const tableColumns = ref<ManagedTableColumn[]>([
  { key: 'id', label: 'ID', minWidth: 100, visible: true },
  { key: 'shop_name', label: '店铺名称', minWidth: 220, visible: true },
  { key: 'shop_url', label: '店铺链接', minWidth: 260, visible: true },
  { key: 'image', label: '执照图片', minWidth: 320, visible: true },
  { key: 'remark', label: '备注', minWidth: 220, visible: true },
  { key: 'created_at', label: '创建时间', minWidth: 160, visible: true },
])
const visibleTableColumns = computed(() => tableColumns.value.filter((column) => column.visible))
async function saveTableColumns(columns: ManagedTableColumn[]) {
  tableColumns.value = columns
  await saveUiSetting('peer-shop-columns', columns)
}

const dialogVisible = ref(false)
const editingRecordId = ref<number | null>(null)
const imageActionLoadingId = ref<number | null>(null)
const previewDialogVisible = ref(false)
const previewDialogUrl = ref('')
const previewDialogTitle = ref('')

const uploadRef = ref<UploadInstance>()
const quickReplaceInputRef = ref<HTMLInputElement | null>(null)
const quickReplaceTargetRecordId = ref<number | null>(null)
const selectedImageFile = ref<File | null>(null)
const imagePreviewUrl = ref('')
const currentImageUrl = ref('')
const uploadFileList = ref<UploadFile[]>([])

const form = reactive({
  shop_name: '',
  shop_url: '',
  remark: '',
  extra_fields: {} as Record<string, string>,
})

let objectPreviewUrl: string | null = null

const canEditPeerShops = computed(() => {
  return authStore.canWrite('peer_shops')
})

const editingPeerShopRecord = computed(() =>
  editingRecordId.value === null
    ? null
    : records.value.find((record) => record.id === editingRecordId.value) ?? null,
)

const desktopTableHeight = computed(() => Math.max(420, viewportHeight.value - 360))
const pageSize = computed(() => 20)

const filteredRecords = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase()
  if (!normalizedKeyword) {
    return records.value
  }

  return records.value.filter((record) =>
    [
      record.shop_name,
      record.shop_url ?? '',
      record.remark ?? '',
      record.image_name ?? '',
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

function mergeUpdatedRecord(updatedRecord: PeerShop) {
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
  form.shop_name = ''
  form.shop_url = ''
  form.remark = ''
  form.extra_fields = {}
  selectedImageFile.value = null
  uploadFileList.value = []
  setExistingPreview(null)
  uploadRef.value?.clearFiles()
}

function openCreateDialog() {
  resetForm()
  dialogVisible.value = true
}

function openEditDialog(record: PeerShop) {
  resetForm()
  editingRecordId.value = record.id
  form.shop_name = record.shop_name
  form.shop_url = record.shop_url ?? ''
  form.remark = record.remark ?? ''
  form.extra_fields = Object.fromEntries(Object.entries(record.extra_fields ?? {}).map(([key, value]) => [key, String(value ?? '')]))
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
    shop_name: form.shop_name.trim(),
    shop_url: form.shop_url.trim() || null,
    remark: form.remark.trim() || null,
    extra_fields: { ...form.extra_fields },
  }
}

function openLink(url: string | null | undefined) {
  if (!url) {
    return
  }
  window.open(url, '_blank', 'noopener,noreferrer')
}

function triggerQuickReplace(record: PeerShop) {
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
    const updatedRecord = await uploadPeerShopImage(recordId, file)
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

async function loadData(message = '正在同步同行店铺...') {
  loading.value = true
  statusText.value = message

  try {
    const [recordData, savedColumns] = await Promise.all([
      fetchPeerShops(),
      fetchUiSetting<ManagedTableColumn[]>('peer-shop-columns').catch(() => null),
    ])
    records.value = recordData
    if (Array.isArray(savedColumns) && savedColumns.length) tableColumns.value = savedColumns
    tableRef.value?.clearSelection()
    selectedIds.value = []
    statusText.value = `已加载 ${records.value.length} 条同行店铺记录`
  } catch (error) {
    const messageText = getErrorMessage(error, '加载同行店铺失败')
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

    if (!payload.shop_name) {
      ElMessage.warning('店铺名称不能为空')
      return
    }

    const isCreating = editingRecordId.value === null
    let savedRecord: PeerShop
    if (isCreating) {
      savedRecord = await createPeerShop(payload)
      editingRecordId.value = savedRecord.id
    } else {
      const recordId = editingRecordId.value
      if (recordId === null) {
        throw new Error('当前同行店铺记录缺少 ID，无法更新')
      }
      savedRecord = await updatePeerShop(recordId, payload)
    }

    let imageUploadErrorMessage = ''
    if (selectedImageFile.value) {
      try {
        savedRecord = await uploadPeerShopImage(savedRecord.id, selectedImageFile.value)
      } catch (error) {
        imageUploadErrorMessage = getErrorMessage(error, '执照图片上传失败')
      }
    }

    if (savedRecord.image_url) {
      setExistingPreview(savedRecord.image_url)
    }

    dialogVisible.value = false
    await loadData('正在刷新同行店铺...')

    if (imageUploadErrorMessage) {
      ElMessage.warning(
        `${isCreating ? '同行店铺已新增' : '同行店铺已更新'}，但图片上传失败：${imageUploadErrorMessage}`,
      )
      return
    }

    ElMessage.success(isCreating ? '新增同行店铺成功' : '更新同行店铺成功')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '保存同行店铺失败'))
  } finally {
    submitLoading.value = false
  }
}

async function confirmDeleteRecord(record: PeerShop) {
  try {
    await ElMessageBox.confirm(`确定删除同行店铺「${record.shop_name}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })

    await deletePeerShop(record.id)
    ElMessage.success('删除成功')
    await loadData('正在刷新同行店铺...')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, '删除同行店铺失败'))
  }
}

async function confirmDeleteImage(record: PeerShop) {
  if (!record.image_url) {
    ElMessage.warning('当前没有可删除的执照图片')
    return
  }

  try {
    await ElMessageBox.confirm(`确定删除「${record.shop_name}」的执照图片吗？`, '删除图片确认', {
      type: 'warning',
      confirmButtonText: '删除图片',
      cancelButtonText: '取消',
    })

    imageActionLoadingId.value = record.id
    const updatedRecord = await deletePeerShopImage(record.id)
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

function handleSelectionChange(rows: PeerShop[]) {
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
    await ElMessageBox.confirm(`确定删除已选的 ${selectedIds.value.length} 条同行店铺记录吗？`, '批量删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })

    batchLoading.value = true
    await batchDeletePeerShops({
      record_ids: selectedIds.value,
    })
    ElMessage.success('批量删除成功')
    await loadData('正在刷新同行店铺...')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, '批量删除同行店铺失败'))
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
  previewDialogVisible.value = true
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
})

onMounted(loadData)
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
            placeholder="搜索店铺名称、店铺链接或备注"
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
          <h3 class="section-title" style="font-size: 16px">同行店铺列表</h3>
          <p class="section-desc">独立维护同行店铺名称、链接和执照图片，不和店铺账号数据混用。</p>
        </div>

        <div class="toolbar-actions">
          <el-button type="primary" :icon="CirclePlus" :disabled="!canEditPeerShops" @click="openCreateDialog">
            新增同行店铺
          </el-button>
          <TableHeaderManager v-model:columns="tableColumns" @save="saveTableColumns" />
          <div v-if="!isMobile && canEditPeerShops" class="toolbar-batch-group">
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
          <el-button :icon="RefreshRight" @click="loadData('正在手动刷新同行店铺...')">
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
          <el-table-column v-if="canEditPeerShops" type="selection" width="50" fixed="left" />
          <el-table-column
            v-for="column in visibleTableColumns"
            :key="column.key"
            :prop="column.key === 'image' ? undefined : column.key"
            :label="column.label"
            :min-width="column.minWidth"
            show-overflow-tooltip
            :sortable="column.key === 'image' ? false : true"
          >
            <template #default="{ row }">
              <div v-if="column.key === 'shop_url'" class="cell-actions">
                <a
                  v-if="row.shop_url"
                  class="shop-link"
                  :href="row.shop_url"
                  target="_blank"
                  rel="noopener noreferrer"
                  :title="`打开店铺：${row.shop_url}`"
                  @click.stop
                >
                  <span class="shop-link__text">{{ row.shop_url }}</span>
                  <el-icon class="shop-link__icon"><LinkIcon /></el-icon>
                </a>
                <span v-else class="single-line-text">未设置</span>
              </div>
              <div v-else-if="column.key === 'image'" class="cell-actions">
                <el-tag :type="row.image_url ? 'success' : 'info'" round>
                  {{ row.image_url ? '已上传' : '未上传' }}
                </el-tag>
                <el-button
                  v-if="row.image_url"
                  type="primary"
                  link
                  :icon="Picture"
                  @click="openImage(row.image_url, row.image_name || row.shop_name)"
                >
                  查看
                </el-button>
                <el-button
                  v-if="canEditPeerShops"
                  type="primary"
                  link
                  :loading="imageActionLoadingId === row.id"
                  @click="triggerQuickReplace(row)"
                >
                  {{ row.image_url ? '替换' : '上传' }}
                </el-button>
                <el-button
                  v-if="canEditPeerShops && row.image_url"
                  type="danger"
                  link
                  :loading="imageActionLoadingId === row.id"
                  @click="confirmDeleteImage(row)"
                >
                  删除图片
                </el-button>
              </div>
              <span v-else-if="column.key === 'created_at'">{{ formatDateTime(row.created_at) }}</span>
              <span v-else-if="column.custom">{{ row.extra_fields?.[column.key] ?? '-' }}</span>
              <span v-else>{{ row[column.key as keyof PeerShop] ?? '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column v-if="canEditPeerShops" label="操作" width="160" fixed="right">
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
        <div v-loading="loading" class="peer-shop-card-list fixed-list-mobile">
          <template v-if="paginatedRecords.length">
            <article
              v-for="record in paginatedRecords"
              :key="record.id"
              class="peer-shop-mobile-card"
            >
              <div class="peer-shop-mobile-card__head">
                <div class="peer-shop-mobile-card__title-wrap">
                  <h4 class="peer-shop-mobile-card__title">{{ record.shop_name }}</h4>
                  <p class="peer-shop-mobile-card__meta">ID {{ record.id }} 路 {{ formatDateTime(record.created_at) }}</p>
                </div>

                <el-tag :type="record.image_url ? 'success' : 'info'" round>
                  {{ record.image_url ? '已上传执照' : '未上传执照' }}
                </el-tag>
              </div>

              <div class="peer-shop-mobile-card__grid">
                <div class="peer-shop-mobile-card__field">
                  <span class="peer-shop-mobile-card__label">店铺链接</span>
                  <a
                    v-if="record.shop_url"
                    class="peer-shop-mobile-card__value shop-link"
                    :href="record.shop_url"
                    target="_blank"
                    rel="noopener noreferrer"
                    :title="`打开店铺：${record.shop_url}`"
                  >
                    <span class="shop-link__text">{{ record.shop_url }}</span>
                    <el-icon class="shop-link__icon"><LinkIcon /></el-icon>
                  </a>
                  <span v-else class="peer-shop-mobile-card__value">未设置</span>
                </div>

                <div class="peer-shop-mobile-card__field">
                  <span class="peer-shop-mobile-card__label">备注</span>
                  <span class="peer-shop-mobile-card__value">{{ record.remark || '暂无备注' }}</span>
                </div>
              </div>

              <div v-if="record.image_url || canEditPeerShops" class="peer-shop-mobile-card__actions">
                <el-button
                  v-if="record.shop_url"
                  type="primary"
                  plain
                  :icon="LinkIcon"
                  @click="openLink(record.shop_url)"
                >
                  打开链接
                </el-button>
                <el-button
                  v-if="record.image_url"
                  type="primary"
                  plain
                  :icon="Picture"
                  @click="openImage(record.image_url, record.image_name || record.shop_name)"
                >
                  查看执照
                </el-button>
                <el-button
                  v-if="canEditPeerShops"
                  type="primary"
                  plain
                  :loading="imageActionLoadingId === record.id"
                  :icon="UploadFilled"
                  @click="triggerQuickReplace(record)"
                >
                  {{ record.image_url ? '替换执照' : '上传执照' }}
                </el-button>
                <el-button
                  v-if="canEditPeerShops && record.image_url"
                  type="danger"
                  plain
                  :loading="imageActionLoadingId === record.id"
                  :icon="Delete"
                  @click="confirmDeleteImage(record)"
                >
                  删除执照
                </el-button>
                <el-button
                  v-if="canEditPeerShops"
                  type="primary"
                  plain
                  :icon="EditPen"
                  @click="openEditDialog(record)"
                >
                  编辑
                </el-button>
                <el-button
                  v-if="canEditPeerShops"
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
            :description="keyword.trim() ? '没有匹配的同行店铺' : '暂无同行店铺记录'"
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
      :title="editingRecordId === null ? '新增同行店铺' : `编辑同行店铺 #${editingRecordId}`"
      width="860px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="店铺名称" required>
              <el-input v-model="form.shop_name" placeholder="请输入同行店铺名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="店铺链接">
              <el-input v-model="form.shop_url" placeholder="请输入 http:// 或 https:// 店铺链接" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input
                v-model="form.remark"
                type="textarea"
                :rows="4"
                placeholder="记录对标说明、类目特点或补充信息"
              />
            </el-form-item>
          </el-col>
          <el-col v-for="column in tableColumns.filter((item) => item.custom)" :key="column.key" :span="12">
            <el-form-item :label="column.label">
              <el-input v-model="form.extra_fields[column.key]" :placeholder="`请输入${column.label}`" />
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
                <el-button type="primary" plain :icon="UploadFilled">选择执照图片</el-button>
                <template #tip>
                  <div class="section-desc" style="margin-top: 8px">
                    支持 JPG / PNG / WebP，大小不超过 15MB。保存后会自动上传。
                  </div>
                </template>
              </el-upload>
              <div v-if="editingPeerShopRecord && currentImageUrl" class="peer-shop-image-inline-actions">
                <el-button
                  text
                  type="danger"
                  :icon="Delete"
                  :loading="imageActionLoadingId === editingPeerShopRecord.id"
                  @click="confirmDeleteImage(editingPeerShopRecord)"
                >
                  删除当前执照
                </el-button>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="24" v-if="imagePreviewUrl">
            <el-form-item label="图片预览">
              <div class="page-block" style="padding: 14px; width: 100%">
                <img
                  :src="imagePreviewUrl"
                  alt="同行店铺执照预览"
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
          {{ editingRecordId === null ? '新增同行店铺' : '保存修改' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="previewDialogVisible"
      :title="previewDialogTitle || '同行店铺执照预览'"
      width="900px"
      destroy-on-close
    >
      <div
        style="display: grid; place-items: center; min-height: 320px; border-radius: 16px; background: #f7f9fc; padding: 12px;"
      >
        <img
          v-if="previewDialogUrl"
          :src="previewDialogUrl"
          :alt="previewDialogTitle || '同行店铺执照预览'"
          style="display: block; max-width: 100%; max-height: 70vh; object-fit: contain; border-radius: 12px; background: #ffffff;"
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

.peer-shop-image-inline-actions {
  margin-top: 8px;
}

.shop-link {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
  max-width: 100%;
  color: var(--brand-primary);
  font-weight: 500;
  line-height: 1.5;
  text-decoration: none;
  transition: color 160ms ease, text-decoration-color 160ms ease;
}

.shop-link:hover {
  color: var(--brand-primary-hover);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.shop-link:focus-visible {
  border-radius: 4px;
  outline: 2px solid color-mix(in srgb, var(--brand-primary) 36%, transparent);
  outline-offset: 2px;
}

.shop-link__text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.shop-link__icon {
  flex: 0 0 auto;
  font-size: 13px;
}

.peer-shop-card-list {
  display: grid;
  gap: 12px;
  min-height: 180px;
}

.peer-shop-mobile-card {
  display: grid;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--panel-border);
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: 0 10px 24px rgba(31, 41, 55, 0.06);
}

.peer-shop-mobile-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.peer-shop-mobile-card__title-wrap {
  min-width: 0;
}

.peer-shop-mobile-card__title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.35;
  word-break: break-word;
}

.peer-shop-mobile-card__meta {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.peer-shop-mobile-card__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.peer-shop-mobile-card__field {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid #e6edf7;
  border-radius: 14px;
  background: #fbfdff;
}

.peer-shop-mobile-card__label {
  color: var(--text-secondary);
  font-size: 12px;
}

.peer-shop-mobile-card__value {
  font-size: 14px;
  line-height: 1.5;
  word-break: break-word;
}

.peer-shop-mobile-card__actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.peer-shop-mobile-card__actions .el-button {
  width: 100%;
  margin: 0;
}

@media (max-width: 640px) {
  .peer-shop-mobile-card__grid,
  .peer-shop-mobile-card__actions {
    grid-template-columns: 1fr;
  }
}
</style>
