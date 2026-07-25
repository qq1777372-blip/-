<script setup lang="ts">
import { UserFilled } from '@element-plus/icons-vue'
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import {
  createAdminUser,
  fetchAdminUsers,
  updateAdminUserStatus,
} from '../api'
import { useViewport } from '../composables/useViewport'
import { useAuthStore } from '../stores/auth'
import type { AdminUser, RoleType } from '../types/api'
import { formatDateTime } from '../utils/format'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const authStore = useAuthStore()
const { isMobile } = useViewport()
const loading = ref(false)
const submitLoading = ref(false)
const adminUsers = ref<AdminUser[]>([])

const form = reactive({
  username: '',
  password: '',
  role: 'editor' as RoleType,
})

const isSuperAdmin = computed(() => authStore.currentUser?.role === 'superadmin')

function closeDialog() {
  emit('update:modelValue', false)
}

function resetForm() {
  form.username = ''
  form.password = ''
  form.role = 'editor'
}

function getRoleLabel(role: RoleType) {
  const roleMap: Record<RoleType, string> = {
    viewer: '只读',
    editor: '编辑员',
    superadmin: '超级管理员',
  }

  return roleMap[role]
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

async function loadAdminData() {
  if (!isSuperAdmin.value) {
    return
  }

  loading.value = true

  try {
    adminUsers.value = await fetchAdminUsers()
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '加载管理员信息失败'))
  } finally {
    loading.value = false
  }
}

async function handleCreateAdminUser() {
  if (!form.username.trim() || !form.password) {
    ElMessage.warning('请完整填写新账号信息')
    return
  }

  if (form.password.length < 8) {
    ElMessage.warning('初始密码至少 8 位')
    return
  }

  submitLoading.value = true

  try {
    await createAdminUser({
      username: form.username.trim(),
      password: form.password,
      role: form.role,
    })

    ElMessage.success('管理员账号创建成功')
    resetForm()
    await loadAdminData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '新增管理员失败'))
  } finally {
    submitLoading.value = false
  }
}

async function handleToggleStatus(user: AdminUser) {
  const actionText = user.is_active ? '禁用' : '启用'

  try {
    await ElMessageBox.confirm(`确定${actionText}账号「${user.username}」吗？`, '状态确认', {
      type: 'warning',
      confirmButtonText: actionText,
      cancelButtonText: '取消',
    })

    await updateAdminUserStatus(user.id, { is_active: !user.is_active })
    ElMessage.success(`账号已${actionText}`)
    await loadAdminData()
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, `${actionText}失败`))
  }
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      loadAdminData()
      return
    }

    resetForm()
  },
)
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="管理员管理"
    width="860px"
    destroy-on-close
    @close="closeDialog"
  >
    <div class="page-stack" v-loading="loading">
      <el-card shadow="never">
        <template #header>
          <div>
            <h3 class="section-title" style="font-size: 16px">新增管理员</h3>
            <p class="section-desc">默认推荐创建编辑员账号，超级管理员数量尽量控制。</p>
          </div>
        </template>

        <el-form label-position="top">
          <el-row :gutter="16">
            <el-col :xs="24" :sm="24" :md="8">
              <el-form-item label="新账号" required>
                <el-input v-model="form.username" placeholder="例如：admin02" />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :sm="24" :md="8">
              <el-form-item label="初始密码" required>
                <el-input v-model="form.password" type="password" show-password placeholder="至少 8 位密码" />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :sm="24" :md="8">
              <el-form-item label="角色">
                <el-select v-model="form.role" style="width: 100%">
                  <el-option label="只读" value="viewer" />
                  <el-option label="编辑员" value="editor" />
                  <el-option label="超级管理员" value="superadmin" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-button type="primary" :icon="UserFilled" :loading="submitLoading" @click="handleCreateAdminUser">
            新增管理员
          </el-button>
        </el-form>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div>
            <h3 class="section-title" style="font-size: 16px">账号列表</h3>
            <p class="section-desc">禁用账号后，该账号当前会话会立即失效。</p>
          </div>
        </template>

        <el-table v-if="!isMobile" :data="adminUsers" stripe>
          <el-table-column prop="username" label="账号" min-width="180" />
          <el-table-column label="角色" min-width="120">
            <template #default="{ row }">
              <el-tag round>{{ getRoleLabel(row.role) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" min-width="110">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" round>
                {{ row.is_active ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" min-width="180">
            <template #default="{ row }">
              {{ formatDateTime(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button
                :type="row.is_active ? 'danger' : 'success'"
                link
                @click="handleToggleStatus(row)"
              >
                {{ row.is_active ? '禁用' : '启用' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-else class="admin-mobile-list">
          <template v-if="adminUsers.length">
            <article
              v-for="user in adminUsers"
              :key="user.id"
              class="admin-mobile-card"
            >
              <div class="admin-mobile-card__head">
                <div>
                  <h4 class="admin-mobile-card__title">{{ user.username }}</h4>
                  <p class="admin-mobile-card__meta">{{ formatDateTime(user.created_at) }}</p>
                </div>

                <div class="admin-mobile-card__tags">
                  <el-tag round>{{ getRoleLabel(user.role) }}</el-tag>
                  <el-tag :type="user.is_active ? 'success' : 'info'" round>
                    {{ user.is_active ? '启用' : '禁用' }}
                  </el-tag>
                </div>
              </div>

              <el-button
                :type="user.is_active ? 'danger' : 'success'"
                plain
                @click="handleToggleStatus(user)"
              >
                {{ user.is_active ? '禁用' : '启用' }}
              </el-button>
            </article>
          </template>

          <el-empty v-else description="暂无管理员账号" />
        </div>
      </el-card>
    </div>

    <template #footer>
      <el-button @click="closeDialog">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.admin-mobile-list {
  display: grid;
  gap: 12px;
}

.admin-mobile-card {
  display: grid;
  gap: 12px;
  padding: 14px;
  border: 1px solid #e6edf7;
  border-radius: 16px;
  background: #fbfdff;
}

.admin-mobile-card__head {
  display: grid;
  gap: 10px;
}

.admin-mobile-card__title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
}

.admin-mobile-card__meta {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
}

.admin-mobile-card__tags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
