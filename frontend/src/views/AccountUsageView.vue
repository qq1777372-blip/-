<script setup lang="ts">
import {
  CirclePlus,
  Delete,
  EditPen,
  Hide,
  RefreshRight,
  Search,
  Select,
  View,
} from '@element-plus/icons-vue'
import type { TableInstance } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  batchDeleteAccountUsageRecords,
  batchUpdateAccountUsageStatus,
  createAccountUsageRecord,
  deleteAccountUsageRecord,
  fetchAccountUsageRecordForEdit,
  fetchAccountUsageRecords,
  fetchUiSetting,
  revealAccountUsagePassword,
  saveUiSetting,
  updateAccountUsageRecord,
} from '../api'
import ListPaginationFooter from '../components/ListPaginationFooter.vue'
import TableHeaderManager, { type ManagedTableColumn } from '../components/TableHeaderManager.vue'
import ProtectedRevealField from '../components/ProtectedRevealField.vue'
import { useProtectedReveal } from '../composables/useProtectedReveal'
import { useViewport } from '../composables/useViewport'
import { useAuthStore } from '../stores/auth'
import type { AccountUsageRecord } from '../types/api'
import { formatDateTime } from '../utils/format'

const authStore = useAuthStore()
const { isMobile, viewportHeight } = useViewport()
const passwordReveal = useProtectedReveal({
  promptMessage: '请输入当前登录管理员密码，验证通过后才能查看该账号密码。',
  promptTitle: '验证查看密码',
  inputPlaceholder: '请输入当前登录密码',
  confirmButtonText: '验证查看',
  cancelButtonText: '取消',
  successMessage: '密码验证通过',
  errorMessage: '密码验证失败',
})
const revealLoading = passwordReveal.loading
const revealedPassword = passwordReveal.revealedValue
const passwordVisible = passwordReveal.visible

const loading = ref(false)
const submitLoading = ref(false)
const batchLoading = ref(false)
const currentPage = ref(1)
const keyword = ref('')
const statusText = ref('准备就绪')
const records = ref<AccountUsageRecord[]>([])
const selectedIds = ref<number[]>([])
const tableRef = ref<TableInstance>()
const tableColumns = ref<ManagedTableColumn[]>([
  { key: 'id', label: 'ID', minWidth: 100, visible: true },
  { key: 'account_name', label: '账号名称', minWidth: 180, visible: true },
  { key: 'password', label: '密码', minWidth: 150, visible: true },
  { key: 'phone_number', label: '手机号', minWidth: 150, visible: true },
  { key: 'device_name', label: '手机设备', minWidth: 120, visible: true },
  { key: 'usage_notes', label: '使用记录', minWidth: 360, visible: true },
  { key: 'is_banned', label: '是否被封', minWidth: 110, visible: true },
  { key: 'banned_reason', label: '封禁备注', minWidth: 180, visible: true },
  { key: 'created_at', label: '创建时间', minWidth: 170, visible: true },
])
const visibleTableColumns = computed(() => tableColumns.value.filter((column) => column.visible))
async function saveTableColumns(columns: ManagedTableColumn[]) {
  tableColumns.value = columns
  await saveUiSetting('account-usage-columns', columns)
}

const dialogVisible = ref(false)
const editingRecordId = ref<number | null>(null)
const form = reactive({
  account_name: '',
  password: '',
  phone_number: '',
  device_name: '',
  usage_notes: '',
  is_banned: false,
  banned_reason: '',
  extra_fields: {} as Record<string, string>,
})

const canEditRecords = computed(() => {
  return authStore.canWrite('account_usage')
})

const desktopTableHeight = computed(() => Math.max(420, viewportHeight.value - 360))
const pageSize = computed(() => 20)

const filteredRecords = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase()
  if (!normalizedKeyword) {
    return records.value
  }

  return records.value.filter((record) => {
    return [
      record.account_name,
      record.phone_number ?? '',
      record.device_name ?? '',
      record.usage_notes ?? '',
      record.banned_reason ?? '',
      ...Object.values(record.extra_fields ?? {}),
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

const statusDisplay = computed(() => {
  if (!keyword.value.trim()) {
    return statusText.value
  }

  return `关键字过滤：${keyword.value.trim()}`
})

const passwordDisplay = computed(() => {
  if (editingRecordId.value === null) {
    return form.password ? '已输入新密码' : '未设置'
  }

  if (passwordReveal.visible.value) {
    return revealedPassword.value || '未设置'
  }

  return '已隐藏，点击验证查看'
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
  passwordReveal.reset()
  form.account_name = ''
  form.password = ''
  form.phone_number = ''
  form.device_name = ''
  form.usage_notes = ''
  form.is_banned = false
  form.banned_reason = ''
  form.extra_fields = {}
}

function openCreateDialog() {
  resetForm()
  dialogVisible.value = true
}

async function openEditDialog(record: AccountUsageRecord) {
  resetForm()

  try {
    const fullRecord = await fetchAccountUsageRecordForEdit(record.id)
    editingRecordId.value = fullRecord.id
    form.account_name = fullRecord.account_name
    form.phone_number = fullRecord.phone_number ?? ''
    form.device_name = fullRecord.device_name ?? ''
    form.usage_notes = fullRecord.usage_notes ?? ''
    form.is_banned = fullRecord.is_banned
    form.banned_reason = fullRecord.banned_reason ?? ''
    form.extra_fields = Object.fromEntries(Object.entries(fullRecord.extra_fields ?? {}).map(([key, value]) => [key, String(value ?? '')]))
    dialogVisible.value = true
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '加载账号记录详情失败'))
  }
}

function buildPayload() {
  return {
    account_name: editingRecordId.value === null ? form.account_name.trim() : form.account_name.trim() || null,
    password: form.password.trim() || null,
    phone_number: form.phone_number.trim() || null,
    device_name: form.device_name.trim() || null,
    usage_notes: form.usage_notes.trim() || null,
    is_banned: form.is_banned,
    banned_reason: form.banned_reason.trim() || null,
    extra_fields: { ...form.extra_fields },
  }
}

async function loadData(message = '正在同步账号使用记录...') {
  loading.value = true
  statusText.value = message

  try {
    const [recordData, savedColumns] = await Promise.all([
      fetchAccountUsageRecords(),
      fetchUiSetting<ManagedTableColumn[]>('account-usage-columns').catch(() => null),
    ])
    records.value = recordData
    if (Array.isArray(savedColumns) && savedColumns.length) tableColumns.value = savedColumns
    tableRef.value?.clearSelection()
    selectedIds.value = []
    statusText.value = `已加载 ${records.value.length} 条账号记录`
  } catch (error) {
    const messageText = getErrorMessage(error, '加载账号使用记录失败')
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
    if (editingRecordId.value === null && !payload.account_name) {
      ElMessage.warning('账号名称不能为空')
      return
    }

    if (editingRecordId.value === null) {
      await createAccountUsageRecord(payload)
      ElMessage.success('新增账号记录成功')
    } else {
      await updateAccountUsageRecord(editingRecordId.value, payload)
      ElMessage.success('更新账号记录成功')
    }

    dialogVisible.value = false
    await loadData('正在刷新账号记录...')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '保存账号记录失败'))
  } finally {
    submitLoading.value = false
  }
}

async function confirmDeleteRecord(record: AccountUsageRecord) {
  try {
    await ElMessageBox.confirm(`确定删除账号「${record.account_name}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })

    await deleteAccountUsageRecord(record.id)
    ElMessage.success('删除成功')
    await loadData('正在刷新账号记录...')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, '删除账号记录失败'))
  }
}

function handleSelectionChange(rows: AccountUsageRecord[]) {
  selectedIds.value = rows.map((row) => row.id)
}

function clearSelectedRows() {
  tableRef.value?.clearSelection()
  selectedIds.value = []
}

async function applyBatchBannedStatus(isBanned: boolean, successMessage: string) {
  if (!selectedIds.value.length) {
    return
  }

  batchLoading.value = true

  try {
    await batchUpdateAccountUsageStatus({
      record_ids: selectedIds.value,
      is_banned: isBanned,
    })
    ElMessage.success(successMessage)
    await loadData('正在刷新账号记录...')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '批量更新账号状态失败'))
  } finally {
    batchLoading.value = false
  }
}

async function confirmBatchDelete() {
  if (!selectedIds.value.length) {
    return
  }

  try {
    await ElMessageBox.confirm(`确定删除已选的 ${selectedIds.value.length} 条账号记录吗？`, '批量删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })

    batchLoading.value = true
    await batchDeleteAccountUsageRecords({
      record_ids: selectedIds.value,
    })
    ElMessage.success('批量删除成功')
    await loadData('正在刷新账号记录...')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, '批量删除账号记录失败'))
  } finally {
    batchLoading.value = false
  }
}

async function handleBatchCommand(command: string | number | object) {
  if (command === 'ban') {
    await applyBatchBannedStatus(true, '已批量标记为封禁')
    return
  }

  if (command === 'unban') {
    await applyBatchBannedStatus(false, '已批量标记为正常')
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

async function handleRevealPassword() {
  if (!editingRecordId.value) {
    return
  }

  try {
    const { value } = await ElMessageBox.prompt('请输入当前登录管理员密码，验证通过后才能查看该账号密码。', '验证查看密码', {
      inputType: 'password',
      inputPlaceholder: '请输入当前登录密码',
      confirmButtonText: '验证查看',
      cancelButtonText: '取消',
    })

    revealLoading.value = true
    const data = await revealAccountUsagePassword(editingRecordId.value, {
      current_password: value,
    })
    revealedPassword.value = data.password ?? '未设置'
    passwordVisible.value = true
    ElMessage.success('密码验证通过')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, '密码验证失败'))
  } finally {
    revealLoading.value = false
  }
}

function hideRevealedPassword() {
  passwordVisible.value = false
}

async function handleProtectedPasswordReveal() {
  const recordId = editingRecordId.value
  if (recordId === null) {
    return
  }

  await passwordReveal.reveal(async (currentPassword) => {
    const data = await revealAccountUsagePassword(recordId, {
      current_password: currentPassword,
    })

    return data.password
  })
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
            placeholder="搜索账号、手机号、手机设备或使用记录"
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
          <h3 class="section-title" style="font-size: 16px">账号列表</h3>
          <p class="section-desc mobile-hide">按账号、手机号、设备和使用记录统一维护，风格和店铺管理下其他二级列表保持一致。</p>
        </div>

        <div class="toolbar-actions">
          <el-button type="primary" :icon="CirclePlus" :disabled="!canEditRecords" @click="openCreateDialog">
            新增账号
          </el-button>
          <TableHeaderManager v-model:columns="tableColumns" @save="saveTableColumns" />
          <div v-if="!isMobile && canEditRecords" class="toolbar-batch-group">
            <el-dropdown trigger="click" @command="handleBatchCommand">
              <el-button class="toolbar-batch-action" plain :icon="Select" :loading="batchLoading">
                批量操作
              </el-button>

              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="ban" :disabled="!selectedIds.length">
                    批量标记已封
                  </el-dropdown-item>
                  <el-dropdown-item command="unban" :disabled="!selectedIds.length">
                    批量标记正常
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
          <el-button :icon="RefreshRight" @click="loadData('正在手动刷新账号记录...')">
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
            :prop="column.key === 'password' ? undefined : column.key"
            :label="column.label"
            :min-width="column.minWidth"
            show-overflow-tooltip
            :sortable="column.key === 'password' ? false : true"
          >
            <template #default="{ row }">
              <span v-if="column.key === 'password'" class="single-line-text">{{ row.has_password ? '已隐藏' : '未设置' }}</span>
              <el-tag v-else-if="column.key === 'is_banned'" :type="row.is_banned ? 'danger' : 'success'" round>
                {{ row.is_banned ? '已被封' : '正常' }}
              </el-tag>
              <span v-else-if="column.key === 'created_at'">{{ formatDateTime(row.created_at) }}</span>
              <span v-else-if="column.custom">{{ row.extra_fields?.[column.key] ?? '-' }}</span>
              <span v-else>{{ row[column.key as keyof AccountUsageRecord] ?? '-' }}</span>
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
                  <h4 class="account-mobile-card__title">{{ record.account_name }}</h4>
                  <p class="account-mobile-card__meta">
                    ID {{ record.id }} · {{ formatDateTime(record.created_at) }}
                  </p>
                </div>

                <el-tag :type="record.is_banned ? 'danger' : 'success'" round>
                  {{ record.is_banned ? '已被封' : '正常' }}
                </el-tag>
              </div>

              <div class="account-mobile-card__grid">
                <div class="account-mobile-card__field">
                  <span class="account-mobile-card__label">手机号</span>
                  <span class="account-mobile-card__value">{{ record.phone_number || '未设置' }}</span>
                </div>

                <div class="account-mobile-card__field">
                  <span class="account-mobile-card__label">手机设备</span>
                  <span class="account-mobile-card__value">{{ record.device_name || '未设置' }}</span>
                </div>

                <div class="account-mobile-card__field">
                  <span class="account-mobile-card__label">密码</span>
                  <span class="account-mobile-card__value">{{ record.has_password ? '已隐藏' : '未设置' }}</span>
                </div>

                <div class="account-mobile-card__field">
                  <span class="account-mobile-card__label">封禁备注</span>
                  <span class="account-mobile-card__value">{{ record.banned_reason || '无' }}</span>
                </div>
              </div>

              <div class="account-mobile-card__notes">
                <div class="account-mobile-card__label">使用记录</div>
                <p class="account-mobile-card__notes-text">
                  {{ record.usage_notes || '暂无使用记录' }}
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
            :description="keyword.trim() ? '没有匹配的账号记录' : '暂无账号记录'"
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
      :title="editingRecordId === null ? '新增账号记录' : `编辑账号记录 #${editingRecordId}`"
      width="860px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="账号名称" required>
              <el-input
                v-model="form.account_name"
                :placeholder="editingRecordId === null ? '例如：tb0104269729' : '请输入账号名称'"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="密码">
              <div style="display: grid; gap: 10px;">
                <ProtectedRevealField
                  :display-value="passwordDisplay"
                  :show-reveal-button="editingRecordId !== null && !passwordVisible"
                  :show-hide-button="editingRecordId !== null && passwordVisible"
                  :loading="revealLoading"
                  reveal-text="验证查看"
                  hide-text="再次隐藏"
                  @reveal="handleProtectedPasswordReveal"
                  @hide="passwordReveal.hide"
                />
                <div v-if="false" class="cell-actions">
                  <el-button
                    v-if="editingRecordId !== null && !passwordVisible"
                    type="primary"
                    plain
                    :icon="View"
                    :loading="revealLoading"
                    @click="handleRevealPassword"
                  >
                    验证查看
                  </el-button>
                  <el-button
                    v-if="editingRecordId !== null && passwordVisible"
                    plain
                    :icon="Hide"
                    @click="hideRevealedPassword"
                  >
                    再次隐藏
                  </el-button>
                </div>
                <el-input
                  v-model="form.password"
                  type="password"
                  show-password
                  :placeholder="editingRecordId === null ? '请输入账号密码' : '留空表示不修改密码'"
                />
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="手机号">
              <el-input v-model="form.phone_number" placeholder="请输入绑定手机号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="手机设备">
              <el-input v-model="form.device_name" placeholder="例如：小米13 / 华为 / 1号机" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="使用记录">
              <el-input
                v-model="form.usage_notes"
                type="textarea"
                :rows="4"
                placeholder="记录该账号的使用时间、订单安排、操作说明等"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="是否被封">
              <el-switch
                v-model="form.is_banned"
                inline-prompt
                active-text="已封"
                inactive-text="正常"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="封禁备注">
              <el-input v-model="form.banned_reason" placeholder="如果被封，可记录原因或处理结果" />
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
          {{ editingRecordId === null ? '新增账号' : '保存修改' }}
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
