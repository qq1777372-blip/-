<script setup lang="ts">
import { Delete, Monitor, RefreshRight, SwitchButton } from '@element-plus/icons-vue'
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { fetchAuthSessions, revokeAuthSession, revokeOtherAuthSessions } from '../api'
import { useViewport } from '../composables/useViewport'
import { useAuthStore } from '../stores/auth'
import type { AdminSessionInfo } from '../types/api'
import { formatDateTime } from '../utils/format'
import router from '../router'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const authStore = useAuthStore()
const { isMobile } = useViewport()
const loading = ref(false)
const actionSessionId = ref<number | null>(null)
const revokeOthersLoading = ref(false)
const sessions = ref<AdminSessionInfo[]>([])

const otherSessionCount = computed(() => sessions.value.filter((item) => !item.is_current).length)

function closeDialog() {
  emit('update:modelValue', false)
}

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    return String(error.response?.data?.detail ?? error.message ?? fallback)
  }

  if (error instanceof Error && error.message) {
    return error.message
  }

  return fallback
}

async function loadSessions() {
  loading.value = true

  try {
    sessions.value = await fetchAuthSessions()
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '加载在线设备失败'))
  } finally {
    loading.value = false
  }
}

async function handleRevokeSession(session: AdminSessionInfo) {
  const actionText = session.is_current ? '退出当前设备' : '强制下线'

  try {
    await ElMessageBox.confirm(
      session.is_current
        ? '确认退出当前设备吗？退出后需要重新登录。'
        : `确认下线设备“${session.device_name}”吗？`,
      '会话确认',
      {
        type: 'warning',
        confirmButtonText: actionText,
        cancelButtonText: '取消',
      },
    )

    actionSessionId.value = session.id
    await revokeAuthSession(session.id)

    if (session.is_current) {
      authStore.clearAuth()
      closeDialog()
      await router.replace({ name: 'login' })
      return
    }

    ElMessage.success('设备已下线')
    await loadSessions()
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, `${actionText}失败`))
  } finally {
    actionSessionId.value = null
  }
}

async function handleRevokeOthers() {
  try {
    await ElMessageBox.confirm(
      '确认仅保留当前设备，强制下线其他所有设备吗？',
      '单点登录确认',
      {
        type: 'warning',
        confirmButtonText: '下线其他设备',
        cancelButtonText: '取消',
      },
    )

    revokeOthersLoading.value = true
    const result = await revokeOtherAuthSessions()
    ElMessage.success(result.updated_count ? `已下线 ${result.updated_count} 台设备` : '没有其他在线设备')
    await loadSessions()
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, '下线其他设备失败'))
  } finally {
    revokeOthersLoading.value = false
  }
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      loadSessions()
    }
  },
)
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="在线设备"
    width="880px"
    destroy-on-close
    @close="closeDialog"
  >
    <div class="page-stack" v-loading="loading">
      <el-card shadow="never">
        <div class="session-banner">
          <div class="session-banner__content">
            <h3 class="section-title" style="font-size: 16px">单点登录已启用</h3>
            <p class="section-desc">
              新设备登录会自动让旧设备会话失效。你也可以在这里查看当前设备信息，并手动下线指定设备。
            </p>
          </div>

          <div class="session-banner__actions">
            <el-button :icon="RefreshRight" @click="loadSessions">
              刷新列表
            </el-button>
            <el-button
              type="warning"
              plain
              :icon="Delete"
              :disabled="otherSessionCount === 0"
              :loading="revokeOthersLoading"
              @click="handleRevokeOthers"
            >
              下线其他设备
            </el-button>
          </div>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div>
            <h3 class="section-title" style="font-size: 16px">会话列表</h3>
            <p class="section-desc">当前账号共有 {{ sessions.length }} 个有效会话。</p>
          </div>
        </template>

        <el-table v-if="!isMobile && sessions.length" :data="sessions" stripe>
          <el-table-column label="设备" min-width="220">
            <template #default="{ row }">
              <div class="session-device">
                <div class="session-device__title">
                  <el-icon><Monitor /></el-icon>
                  <span>{{ row.device_name }}</span>
                  <el-tag v-if="row.is_current" type="success" round>当前设备</el-tag>
                </div>
                <div class="session-device__meta mono-text">{{ row.user_agent }}</div>
              </div>
            </template>
          </el-table-column>

          <el-table-column prop="ip_address" label="IP" min-width="140" />

          <el-table-column label="登录时间" min-width="180">
            <template #default="{ row }">
              {{ formatDateTime(row.created_at) }}
            </template>
          </el-table-column>

          <el-table-column label="过期时间" min-width="180">
            <template #default="{ row }">
              {{ formatDateTime(row.expires_at) }}
            </template>
          </el-table-column>

          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button
                :type="row.is_current ? 'warning' : 'danger'"
                link
                :loading="actionSessionId === row.id"
                @click="handleRevokeSession(row)"
              >
                {{ row.is_current ? '退出当前设备' : '强制下线' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-else-if="sessions.length" class="session-mobile-list">
          <article
            v-for="session in sessions"
            :key="session.id"
            class="session-mobile-card"
          >
            <div class="session-mobile-card__head">
              <div>
                <h4 class="session-mobile-card__title">{{ session.device_name }}</h4>
                <p class="session-mobile-card__meta">{{ session.ip_address }}</p>
              </div>
              <el-tag v-if="session.is_current" type="success" round>当前设备</el-tag>
            </div>

            <div class="session-mobile-card__field">
              <span class="session-mobile-card__label">登录时间</span>
              <span class="session-mobile-card__value">{{ formatDateTime(session.created_at) }}</span>
            </div>

            <div class="session-mobile-card__field">
              <span class="session-mobile-card__label">过期时间</span>
              <span class="session-mobile-card__value">{{ formatDateTime(session.expires_at) }}</span>
            </div>

            <div class="session-mobile-card__field">
              <span class="session-mobile-card__label">User-Agent</span>
              <span class="session-mobile-card__value mono-text">{{ session.user_agent }}</span>
            </div>

            <el-button
              :type="session.is_current ? 'warning' : 'danger'"
              plain
              :icon="session.is_current ? SwitchButton : Delete"
              :loading="actionSessionId === session.id"
              @click="handleRevokeSession(session)"
            >
              {{ session.is_current ? '退出当前设备' : '强制下线' }}
            </el-button>
          </article>
        </div>

        <el-empty v-else description="暂无在线设备记录" />
      </el-card>
    </div>

    <template #footer>
      <el-button @click="closeDialog">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.session-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.session-banner__content {
  flex: 1;
  min-width: 240px;
}

.session-banner__actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.session-device {
  display: grid;
  gap: 8px;
}

.session-device__title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-weight: 600;
}

.session-device__meta {
  font-size: 12px;
  color: var(--text-secondary);
  word-break: break-word;
}

.session-mobile-list {
  display: grid;
  gap: 12px;
}

.session-mobile-card {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--panel-border);
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: 0 10px 24px rgba(31, 41, 55, 0.06);
}

.session-mobile-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.session-mobile-card__title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.4;
}

.session-mobile-card__meta {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
}

.session-mobile-card__field {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border: 1px solid #e6edf7;
  border-radius: 14px;
  background: #fbfdff;
}

.session-mobile-card__label {
  color: var(--text-secondary);
  font-size: 12px;
}

.session-mobile-card__value {
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}
</style>
