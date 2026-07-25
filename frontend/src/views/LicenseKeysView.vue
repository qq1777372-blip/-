<script setup lang="ts">
import { CirclePlus, Key, Monitor, RefreshRight, Search, SwitchButton } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  createLicenseAdminLicenses,
  fetchLicenseAdminLicenses,
  fetchLicenseAdminStats,
  unbindLicenseAdminDevices,
  updateLicenseAdminStatus,
  type LicenseAdminCreatePayload,
  type LicenseAdminItem,
  type LicenseAdminStats,
} from '../api'
import ListPaginationFooter from '../components/ListPaginationFooter.vue'
import { useViewport } from '../composables/useViewport'
import { useAuthStore } from '../stores/auth'
import { formatDateTime } from '../utils/format'

const authStore = useAuthStore()
const { isMobile, viewportHeight } = useViewport()

const loading = ref(false)
const submitLoading = ref(false)
const actionLoadingKey = ref('')
const dialogVisible = ref(false)
const devicesDialogVisible = ref(false)
const currentPage = ref(1)
const keyword = ref('')
const statusText = ref('准备就绪')
const items = ref<LicenseAdminItem[]>([])
const stats = ref<LicenseAdminStats>({
  total_licenses: 0,
  active_licenses: 0,
  disabled_licenses: 0,
  bound_devices: 0,
})
const selectedLicenseKey = ref('')

const form = reactive({
  plan_name: '标准版',
  count: 5,
  duration_days: 30,
  max_devices: 1,
  note: '',
  feature_flags_text: '{"pro": true}',
})

const canManageLicenseKeys = computed(() => authStore.currentUser?.role === 'superadmin')
const pageSize = computed(() => 20)
const desktopTableHeight = computed(() => Math.max(420, viewportHeight.value - 360))
const mobileListHeight = computed(() => Math.max(420, viewportHeight.value - 300))
const selectedLicense = computed(() =>
  items.value.find((item) => item.license_key === selectedLicenseKey.value) ?? null,
)

const filteredItems = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase()
  if (!normalizedKeyword) {
    return items.value
  }

  return items.value.filter((item) => {
    return [
      item.license_key,
      item.plan_name,
      item.status,
      item.note,
      JSON.stringify(item.feature_flags),
      ...item.devices.map((device) => [device.device_id, device.device_name, device.platform, device.app_version, device.last_ip].join(' ')),
    ]
      .join(' ')
      .toLowerCase()
      .includes(normalizedKeyword)
  })
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredItems.value.length / pageSize.value)))

const paginatedItems = computed(() => {
  const startIndex = (currentPage.value - 1) * pageSize.value
  return filteredItems.value.slice(startIndex, startIndex + pageSize.value)
})

const statusDisplay = computed(() => {
  if (!keyword.value.trim()) {
    return statusText.value
  }

  return `关键词过滤：${keyword.value.trim()}`
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

function buildStatusTagType(status: LicenseAdminItem['status']) {
  if (status === 'active') {
    return 'success'
  }
  if (status === 'disabled') {
    return 'danger'
  }
  if (status === 'expired') {
    return 'warning'
  }
  return 'info'
}

function getStatusLabel(status: LicenseAdminItem['status']) {
  if (status === 'active') {
    return '生效中'
  }
  if (status === 'disabled') {
    return '已禁用'
  }
  if (status === 'expired') {
    return '已过期'
  }
  return status
}

function formatExpireText(item: LicenseAdminItem) {
  if (item.expire_at) {
    return formatDateTime(item.expire_at)
  }
  if (item.activated_at) {
    return '永久'
  }
  return '未激活'
}

function formatActivatedText(item: LicenseAdminItem) {
  return item.activated_at ? formatDateTime(item.activated_at) : '未激活'
}

function formatFeatureFlagEntries(item: LicenseAdminItem) {
  return Object.entries(item.feature_flags ?? {}).slice(0, 4)
}

function buildCreatePayload(): LicenseAdminCreatePayload {
  const planName = form.plan_name.trim()
  if (!planName) {
    throw new Error('套餐名称不能为空')
  }

  let featureFlags: Record<string, unknown> = {}
  const rawFeatureFlags = form.feature_flags_text.trim()
  if (rawFeatureFlags) {
    try {
      const parsed = JSON.parse(rawFeatureFlags)
      if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
        throw new Error('功能标记必须是 JSON 对象')
      }
      featureFlags = parsed as Record<string, unknown>
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error('功能标记 JSON 格式不正确')
    }
  }

  return {
    plan_name: planName,
    count: Number(form.count || 0),
    duration_days: Number(form.duration_days || 0),
    max_devices: Number(form.max_devices || 0),
    note: form.note.trim() || null,
    feature_flags: featureFlags,
  }
}

function resetForm() {
  form.plan_name = '标准版'
  form.count = 5
  form.duration_days = 30
  form.max_devices = 1
  form.note = ''
  form.feature_flags_text = '{"pro": true}'
}

function openCreateDialog() {
  resetForm()
  dialogVisible.value = true
}

async function copyLicenseKey(licenseKey: string) {
  try {
    await navigator.clipboard.writeText(licenseKey)
    ElMessage.success('卡密已复制')
  } catch {
    ElMessage.warning('复制失败，请手动复制')
  }
}

function openDevicesDialog(item: LicenseAdminItem) {
  selectedLicenseKey.value = item.license_key
  devicesDialogVisible.value = true
}

function mergeUpdatedItem(updatedItem: LicenseAdminItem) {
  items.value = items.value.map((item) => (item.license_key === updatedItem.license_key ? updatedItem : item))
}

async function loadData(message = '正在同步卡密数据...') {
  if (!canManageLicenseKeys.value) {
    return
  }

  loading.value = true
  statusText.value = message

  try {
    const [nextStats, nextItems] = await Promise.all([fetchLicenseAdminStats(), fetchLicenseAdminLicenses()])
    stats.value = nextStats
    items.value = nextItems
    statusText.value = `已加载 ${nextItems.length} 条卡密`
  } catch (error) {
    const messageText = getErrorMessage(error, '加载卡密数据失败')
    statusText.value = messageText
    ElMessage.error(messageText)
  } finally {
    loading.value = false
  }
}

async function submitCreate() {
  submitLoading.value = true

  try {
    const payload = buildCreatePayload()
    const createdItems = await createLicenseAdminLicenses(payload)
    dialogVisible.value = false
    await loadData('正在刷新卡密数据...')
    ElMessage.success(`已生成 ${createdItems.length} 个卡密`)
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '生成卡密失败'))
  } finally {
    submitLoading.value = false
  }
}

async function handleToggleStatus(item: LicenseAdminItem) {
  const targetStatus = item.status === 'disabled' ? 'active' : 'disabled'
  const actionText = targetStatus === 'active' ? '启用' : '禁用'

  try {
    await ElMessageBox.confirm(`确定${actionText}卡密 ${item.license_key} 吗？`, `${actionText}确认`, {
      type: 'warning',
      confirmButtonText: actionText,
      cancelButtonText: '取消',
    })

    actionLoadingKey.value = `status:${item.license_key}`
    const updatedItem = await updateLicenseAdminStatus(item.license_key, { status: targetStatus })
    mergeUpdatedItem(updatedItem)
    await loadData('正在刷新卡密状态...')
    ElMessage.success(`卡密已${actionText}`)
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, `${actionText}卡密失败`))
  } finally {
    actionLoadingKey.value = ''
  }
}

async function handleUnbind(item: LicenseAdminItem, deviceId: string | null) {
  const actionLabel = deviceId ? '解绑该设备' : '解绑全部设备'
  const confirmText = deviceId ? `确定解绑设备 ${deviceId} 吗？` : `确定清空 ${item.license_key} 的全部设备绑定吗？`

  try {
    await ElMessageBox.confirm(confirmText, actionLabel, {
      type: 'warning',
      confirmButtonText: '确认解绑',
      cancelButtonText: '取消',
    })

    actionLoadingKey.value = `unbind:${item.license_key}:${deviceId ?? 'all'}`
    const updatedItem = await unbindLicenseAdminDevices(item.license_key, { device_id: deviceId })
    mergeUpdatedItem(updatedItem)
    await loadData('正在刷新绑定设备...')
    ElMessage.success('设备解绑完成')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, '设备解绑失败'))
  } finally {
    actionLoadingKey.value = ''
  }
}

watch(keyword, () => {
  currentPage.value = 1
})

watch(
  () => filteredItems.value.length,
  () => {
    if (currentPage.value > totalPages.value) {
      currentPage.value = totalPages.value
    }
  },
)

onMounted(() => {
  resetForm()
  void loadData()
})
</script>

<template>
  <div class="page-stack">
    <section v-if="!canManageLicenseKeys" class="page-block permission-block">
      <el-result icon="warning" title="仅超级管理员可访问" sub-title="卡密生成和设备解绑能力已收口到超级管理员。" />
    </section>

    <template v-else>
      <section class="page-block list-surface list-surface--fixed license-surface">
        <div class="license-surface__section">
          <div class="filter-panel">
            <div class="query-grow">
              <div class="section-desc" style="margin-bottom: 8px">卡密搜索</div>
              <el-input
                v-model="keyword"
                placeholder="搜索卡密、套餐、备注、设备名或设备 ID"
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
              <h3 class="section-title" style="font-size: 16px">卡密管理</h3>
              <p class="section-desc">这里接入的是服务器上的卡密服务，但展示和操作统一走 RuoShop 后台风格。</p>
            </div>

            <div class="toolbar-actions">
              <el-button type="primary" :icon="CirclePlus" @click="openCreateDialog">生成卡密</el-button>
              <el-button :icon="RefreshRight" @click="loadData('正在手动刷新卡密数据...')">刷新数据</el-button>
            </div>
          </div>

          <div class="table-area license-surface__metrics">
            <div class="metric-grid">
              <article class="metric-card license-metric-card">
                <div class="metric-label">卡密总数</div>
                <div class="metric-value">{{ stats.total_licenses }}</div>
                <div class="metric-note">当前已生成的全部卡密数量</div>
              </article>
              <article class="metric-card license-metric-card">
                <div class="metric-label">生效中</div>
                <div class="metric-value">{{ stats.active_licenses }}</div>
                <div class="metric-note">底层服务统计为 active 的卡密</div>
              </article>
              <article class="metric-card license-metric-card">
                <div class="metric-label">已禁用</div>
                <div class="metric-value">{{ stats.disabled_licenses }}</div>
                <div class="metric-note">已经人工停用的卡密数量</div>
              </article>
              <article class="metric-card license-metric-card">
                <div class="metric-label">绑定设备</div>
                <div class="metric-value">{{ stats.bound_devices }}</div>
                <div class="metric-note">当前全部卡密绑定设备总数</div>
              </article>
            </div>
          </div>
        </div>

        <div class="license-surface__section">
          <div class="toolbar-row license-surface__toolbar">
            <div>
              <h3 class="section-title" style="font-size: 16px">卡密列表</h3>
              <p class="section-desc">支持生成、复制、启停和设备解绑，所有动作都通过 RuoShop 后端代理。</p>
            </div>
          </div>

          <div v-if="!isMobile" class="table-area fixed-list-shell">
          <el-table :data="paginatedItems" stripe :height="desktopTableHeight" v-loading="loading">
            <el-table-column prop="license_key" label="卡密" min-width="260" fixed="left" sortable>
              <template #default="{ row }">
                <div class="license-key-cell">
                  <strong class="mono-text">{{ row.license_key }}</strong>
                  <el-button text type="primary" @click="copyLicenseKey(row.license_key)">复制</el-button>
                </div>
              </template>
            </el-table-column>

            <el-table-column prop="status" label="状态" width="120" sortable>
              <template #default="{ row }">
                <el-tag :type="buildStatusTagType(row.status)" round>{{ getStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>

            <el-table-column prop="plan_name" label="套餐" min-width="140" sortable />

            <el-table-column prop="validity_policy" label="有效策略" min-width="220" sortable>
              <template #default="{ row }">
                <div class="info-stack">
                  <span>有效天数：{{ row.duration_days }}</span>
                  <span>最大设备：{{ row.max_devices }}</span>
                </div>
              </template>
            </el-table-column>

            <el-table-column prop="activated_at" label="激活 / 到期" min-width="220" sortable>
              <template #default="{ row }">
                <div class="info-stack">
                  <span>激活：{{ formatActivatedText(row) }}</span>
                  <span>到期：{{ formatExpireText(row) }}</span>
                </div>
              </template>
            </el-table-column>

            <el-table-column prop="bound_devices_count" label="绑定设备" min-width="240" sortable>
              <template #default="{ row }">
                <div class="device-summary-cell">
                  <el-tag round>{{ row.bound_devices_count }} 台</el-tag>
                  <span v-if="row.devices[0]" class="single-line-text muted">
                    {{ row.devices[0].device_name || row.devices[0].device_id }}
                  </span>
                  <el-button text type="primary" :icon="Monitor" @click="openDevicesDialog(row)">查看</el-button>
                </div>
              </template>
            </el-table-column>

            <el-table-column prop="feature_flags" label="功能标记" min-width="220" sortable>
              <template #default="{ row }">
                <div class="flag-list">
                  <el-tag v-for="[flagKey, flagValue] in formatFeatureFlagEntries(row)" :key="flagKey" round>
                    {{ flagKey }}={{ String(flagValue) }}
                  </el-tag>
                  <span v-if="!formatFeatureFlagEntries(row).length" class="muted">无</span>
                </div>
              </template>
            </el-table-column>

            <el-table-column prop="note" label="备注" min-width="200" show-overflow-tooltip sortable />

            <el-table-column label="操作" width="260" fixed="right">
              <template #default="{ row }">
                <div class="cell-actions">
                  <el-button text type="primary" :icon="Monitor" @click="openDevicesDialog(row)">设备</el-button>
                  <el-button
                    text
                    :icon="SwitchButton"
                    :loading="actionLoadingKey === `status:${row.license_key}`"
                    @click="handleToggleStatus(row)"
                  >
                    {{ row.status === 'disabled' ? '启用' : '禁用' }}
                  </el-button>
                  <el-button
                    text
                    type="danger"
                    :icon="Key"
                    :loading="actionLoadingKey === `unbind:${row.license_key}:all`"
                    @click="handleUnbind(row, null)"
                  >
                    解绑全部
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>

          <ListPaginationFooter
            v-model:current-page="currentPage"
            :total-pages="totalPages"
            :page-size="pageSize"
            :total-items="filteredItems.length"
          />
          </div>

          <div v-else class="table-area fixed-list-shell">
            <div v-loading="loading" class="license-card-list fixed-list-mobile" :style="{ maxHeight: `${mobileListHeight}px` }">
              <template v-if="paginatedItems.length">
                <article v-for="item in paginatedItems" :key="item.license_key" class="license-card-mobile">
                  <div class="license-card-mobile__head">
                    <div class="license-card-mobile__title-wrap">
                      <h4 class="license-card-mobile__title mono-text">{{ item.license_key }}</h4>
                      <p class="license-card-mobile__meta">{{ item.plan_name }} · {{ getStatusLabel(item.status) }}</p>
                    </div>
                    <el-tag :type="buildStatusTagType(item.status)" round>{{ getStatusLabel(item.status) }}</el-tag>
                  </div>

                  <div class="license-card-mobile__grid">
                    <div class="license-card-mobile__field">
                      <span class="license-card-mobile__label">有效天数</span>
                      <span class="license-card-mobile__value">{{ item.duration_days }}</span>
                    </div>
                    <div class="license-card-mobile__field">
                      <span class="license-card-mobile__label">最大设备</span>
                      <span class="license-card-mobile__value">{{ item.max_devices }}</span>
                    </div>
                    <div class="license-card-mobile__field">
                      <span class="license-card-mobile__label">激活</span>
                      <span class="license-card-mobile__value">{{ formatActivatedText(item) }}</span>
                    </div>
                    <div class="license-card-mobile__field">
                      <span class="license-card-mobile__label">到期</span>
                      <span class="license-card-mobile__value">{{ formatExpireText(item) }}</span>
                    </div>
                  </div>

                  <div class="license-card-mobile__notes">
                    <div class="license-card-mobile__label">备注</div>
                    <p class="license-card-mobile__notes-text">{{ item.note || '暂无备注' }}</p>
                  </div>

                  <div class="license-card-mobile__actions">
                    <el-button plain @click="copyLicenseKey(item.license_key)">复制</el-button>
                    <el-button plain :icon="Monitor" @click="openDevicesDialog(item)">设备</el-button>
                    <el-button plain :icon="SwitchButton" :loading="actionLoadingKey === `status:${item.license_key}`" @click="handleToggleStatus(item)">
                      {{ item.status === 'disabled' ? '启用' : '禁用' }}
                    </el-button>
                    <el-button
                      plain
                      type="danger"
                      :icon="Key"
                      :loading="actionLoadingKey === `unbind:${item.license_key}:all`"
                      @click="handleUnbind(item, null)"
                    >
                      解绑全部
                    </el-button>
                  </div>
                </article>
              </template>

              <el-empty v-else :description="keyword.trim() ? '没有匹配的卡密' : '暂无卡密数据'" />
            </div>

            <ListPaginationFooter
              v-model:current-page="currentPage"
              :total-pages="totalPages"
              :page-size="pageSize"
              :total-items="filteredItems.length"
            />
          </div>
        </div>
      </section>
    </template>

    <el-dialog v-model="dialogVisible" title="生成卡密" width="720px" destroy-on-close>
      <el-form label-position="top">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="套餐名称" required>
              <el-input v-model="form.plan_name" placeholder="例如：标准版 / 月卡 / 年卡" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="生成数量" required>
              <el-input-number v-model="form.count" :min="1" :max="100" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="有效天数" required>
              <el-input-number v-model="form.duration_days" :min="0" :max="3650" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最大设备数" required>
              <el-input-number v-model="form.max_devices" :min="1" :max="1000" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.note" placeholder="例如：首批测试用户 / 拼团活动 / 抖音渠道" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="功能标记 JSON">
              <el-input v-model="form.feature_flags_text" type="textarea" :rows="6" placeholder='例如：{"pro": true, "upload_limit": 999}' />
              <div class="section-desc" style="margin-top: 8px">这里只接收 JSON 对象，后端会原样转发给卡密服务。</div>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="submitCreate">生成卡密</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="devicesDialogVisible" :title="selectedLicense ? `设备绑定 · ${selectedLicense.license_key}` : '设备绑定'" width="820px" destroy-on-close>
      <template v-if="selectedLicense">
        <div class="device-dialog-toolbar">
          <div>
            <div class="section-title" style="font-size: 16px">{{ selectedLicense.plan_name }}</div>
            <p class="section-desc">当前绑定 {{ selectedLicense.bound_devices_count }} 台设备，可单独解绑或一键清空。</p>
          </div>
          <el-button
            type="danger"
            plain
            :icon="Key"
            :loading="actionLoadingKey === `unbind:${selectedLicense.license_key}:all`"
            @click="handleUnbind(selectedLicense, null)"
          >
            解绑全部设备
          </el-button>
        </div>

        <div v-if="selectedLicense.devices.length" class="device-grid">
          <article v-for="device in selectedLicense.devices" :key="device.device_id" class="device-card">
            <div class="device-card__head">
              <div>
                <strong>{{ device.device_name || '未命名设备' }}</strong>
                <div class="section-desc mono-text" style="margin-top: 6px">{{ device.device_id }}</div>
              </div>
              <el-button
                text
                type="danger"
                :loading="actionLoadingKey === `unbind:${selectedLicense.license_key}:${device.device_id}`"
                @click="handleUnbind(selectedLicense, device.device_id)"
              >
                解绑
              </el-button>
            </div>

            <div class="info-stack">
              <span>平台：{{ device.platform || '-' }}</span>
              <span>版本：{{ device.app_version || '-' }}</span>
              <span>绑定时间：{{ formatDateTime(device.bound_at) }}</span>
              <span>最近心跳：{{ formatDateTime(device.last_seen_at) }}</span>
              <span>最近 IP：{{ device.last_ip || '-' }}</span>
            </div>
          </article>
        </div>

        <el-empty v-else description="当前没有绑定设备" />
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.permission-block {
  padding: 32px 24px;
}

.license-surface {
  overflow: hidden;
}

.license-surface__section {
  min-width: 0;
}

.license-surface__section:last-child {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.license-surface__section + .license-surface__section {
  border-top: 1px solid var(--panel-border);
}

.license-surface__metrics {
  padding-top: 18px;
}

.license-surface__toolbar {
  padding-top: 22px;
}

.license-surface__section:last-child .table-area {
  flex: 1 1 auto;
  min-height: 0;
}

.license-metric-card {
  border: 1px solid #e6edf7;
  border-radius: var(--panel-radius);
  background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
  box-shadow: none;
}

.license-key-cell {
  display: grid;
  gap: 6px;
}

.info-stack {
  display: grid;
  gap: 4px;
  color: var(--text-secondary);
  font-size: 13px;
}

.device-summary-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.flag-list {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.license-card-list {
  display: grid;
  gap: 12px;
  min-height: 180px;
}

.license-card-mobile {
  display: grid;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--panel-border);
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: 0 10px 24px rgba(31, 41, 55, 0.06);
}

.license-card-mobile__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.license-card-mobile__title-wrap {
  min-width: 0;
}

.license-card-mobile__title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.35;
  word-break: break-all;
}

.license-card-mobile__meta {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.license-card-mobile__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.license-card-mobile__field {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid #e6edf7;
  border-radius: 14px;
  background: #fbfdff;
}

.license-card-mobile__label {
  color: var(--text-secondary);
  font-size: 12px;
}

.license-card-mobile__value {
  font-size: 14px;
  line-height: 1.5;
  word-break: break-word;
}

.license-card-mobile__notes {
  display: grid;
  gap: 8px;
}

.license-card-mobile__notes-text {
  margin: 0;
  padding: 12px 14px;
  border: 1px solid #e6edf7;
  border-radius: 14px;
  background: #fbfdff;
  line-height: 1.65;
  color: var(--text-main);
}

.license-card-mobile__actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.license-card-mobile__actions .el-button {
  width: 100%;
  margin: 0;
}

.device-dialog-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.device-grid {
  display: grid;
  gap: 12px;
}

.device-card {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--panel-border);
  border-radius: 16px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}

.device-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

@media (max-width: 768px) {
  .license-surface__toolbar {
    padding-top: 16px;
  }
}

@media (max-width: 640px) {
  .license-card-mobile__grid,
  .license-card-mobile__actions {
    grid-template-columns: 1fr;
  }
}
</style>


