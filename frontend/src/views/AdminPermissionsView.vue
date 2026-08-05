<script setup lang="ts">
import { Check, Plus, RefreshRight, Search, User } from '@element-plus/icons-vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { createAdminUser, fetchAdminUsers, resetAdminUserPassword, updateAdminUserAccess, updateAdminUserStatus } from '../api'
import ListPaginationFooter from '../components/ListPaginationFooter.vue'
import { useAuthStore } from '../stores/auth'
import type { AdminPermissions, AdminUser, PermissionLevel, PermissionModule, RoleType } from '../types/api'
import { formatDateTime } from '../utils/format'

const authStore = useAuthStore()
const loading = ref(false)
const saving = ref(false)
const creating = ref(false)
const createDialogVisible = ref(false)
const permissionDialogVisible = ref(false)
const passwordDialogVisible = ref(false)
const passwordSaving = ref(false)
const keyword = ref('')
const adminUsers = ref<AdminUser[]>([])
const selectedUserId = ref<number | null>(null)
const currentPage = ref(1)
const pageSize = 20

const permissionDefinitions: Array<{ key: PermissionModule; label: string; description: string }> = [
  { key: 'dashboard', label: '运营工作台', description: '经营统计、提醒中心和全局搜索' },
  { key: 'links', label: '链接广场', description: '链接内容、文章发布与图片管理' },
  { key: 'task_bookkeeping', label: '任务记账', description: '任务记录、负责人和店铺资料' },
  { key: 'dingtalk_profits', label: '钉钉利润', description: '利润统计与明细数据' },
  { key: 'shop_records', label: '店铺账号', description: '店铺档案及自定义字段' },
  { key: 'peer_shops', label: '同行店铺', description: '同行链接与截图资料' },
  { key: 'licenses', label: '执照档案', description: '执照资料、图片和字段配置' },
  { key: 'account_usage', label: '账号使用记录', description: '账号分配、状态和敏感信息' },
  { key: 'mobile_devices', label: '手机设备', description: '设备资料与使用状态' },
  { key: 'warehouse', label: '仓储与发货', description: '仓库、商品库存、入库、出库及库存流水' },
]

const permissionOptions: Array<{ value: PermissionLevel; label: string }> = [
  { value: 'none', label: '不可访问' },
  { value: 'read', label: '只读' },
  { value: 'write', label: '可编辑' },
]

function buildPermissions(level: PermissionLevel): AdminPermissions {
  return Object.fromEntries(permissionDefinitions.map((item) => [item.key, level])) as AdminPermissions
}

const accessForm = reactive<{ role: RoleType; permissions: AdminPermissions }>({
  role: 'editor',
  permissions: buildPermissions('write'),
})

const createForm = reactive({
  username: '',
  password: '',
  role: 'editor' as RoleType,
})

const passwordForm = reactive({
  newPassword: '',
  confirmPassword: '',
})

const filteredUsers = computed(() => {
  const normalized = keyword.value.trim().toLowerCase()
  if (!normalized) return adminUsers.value
  return adminUsers.value.filter((user) =>
    `${user.username} ${user.display_name ?? ''}`.toLowerCase().includes(normalized),
  )
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredUsers.value.length / pageSize)))

const paginatedUsers = computed(() => {
  const startIndex = (currentPage.value - 1) * pageSize
  return filteredUsers.value.slice(startIndex, startIndex + pageSize)
})

watch(keyword, () => {
  currentPage.value = 1
})

watch(totalPages, (value) => {
  if (currentPage.value > value) currentPage.value = value
})

const selectedUser = computed(() =>
  adminUsers.value.find((user) => user.id === selectedUserId.value) ?? null,
)

const isCurrentUser = computed(() => selectedUser.value?.id === authStore.currentUser?.id)

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    return String(error.response?.data?.detail ?? error.message ?? fallback)
  }
  return error instanceof Error && error.message ? error.message : fallback
}

function getRoleLabel(role: RoleType) {
  return { viewer: '只读账号', editor: '编辑员', superadmin: '超级管理员' }[role]
}

function getPermissionSummary(user: AdminUser) {
  if (user.role === 'superadmin') return '全部模块'
  const levels = Object.values(user.permissions)
  const writable = levels.filter((level) => level === 'write').length
  const readable = levels.filter((level) => level === 'read').length
  return `${writable} 个可编辑 · ${readable} 个只读`
}

function selectUser(user: AdminUser) {
  selectedUserId.value = user.id
  accessForm.role = user.role
  accessForm.permissions = { ...user.permissions }
}

function openPermissionDialog(user: AdminUser) {
  selectUser(user)
  permissionDialogVisible.value = true
}

function openPasswordDialog(user: AdminUser) {
  selectUser(user)
  passwordForm.newPassword = ''
  passwordForm.confirmPassword = ''
  passwordDialogVisible.value = true
}

function applyRolePreset(role: RoleType) {
  accessForm.role = role
  const level: PermissionLevel = role === 'viewer' ? 'read' : 'write'
  accessForm.permissions = buildPermissions(level)
}

async function loadUsers(preferredId?: number) {
  loading.value = true
  try {
    adminUsers.value = await fetchAdminUsers()
    const target = adminUsers.value.find((user) => user.id === (preferredId ?? selectedUserId.value))
      ?? adminUsers.value[0]
    if (target) selectUser(target)
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '加载账号列表失败'))
  } finally {
    loading.value = false
  }
}

async function saveAccess() {
  const user = selectedUser.value
  if (!user) return

  saving.value = true
  try {
    await updateAdminUserAccess(user.id, {
      role: accessForm.role,
      permissions: { ...accessForm.permissions },
    })
    ElMessage.success('账号权限已更新，该账号需要重新登录')
    await loadUsers(user.id)
    permissionDialogVisible.value = false
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '保存账号权限失败'))
  } finally {
    saving.value = false
  }
}

async function toggleStatus() {
  const user = selectedUser.value
  if (!user) return
  const action = user.is_active ? '禁用' : '启用'

  try {
    await ElMessageBox.confirm(`确定${action}账号「${user.username}」吗？`, `${action}账号`, {
      type: 'warning',
      confirmButtonText: action,
      cancelButtonText: '取消',
    })
    await updateAdminUserStatus(user.id, { is_active: !user.is_active })
    ElMessage.success(`账号已${action}`)
    await loadUsers(user.id)
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getErrorMessage(error, `${action}账号失败`))
  }
}

async function toggleUserStatus(user: AdminUser) {
  selectUser(user)
  await toggleStatus()
}

async function createUser() {
  if (!createForm.username.trim() || createForm.password.length < 8) {
    ElMessage.warning('请填写账号和至少 8 位的初始密码')
    return
  }

  creating.value = true
  try {
    const level: PermissionLevel = createForm.role === 'viewer' ? 'read' : 'write'
    const created = await createAdminUser({
      username: createForm.username.trim(),
      password: createForm.password,
      role: createForm.role,
      permissions: buildPermissions(level),
    })
    createDialogVisible.value = false
    createForm.username = ''
    createForm.password = ''
    createForm.role = 'editor'
    ElMessage.success('账号创建成功')
    await loadUsers(created.id)
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '创建账号失败'))
  } finally {
    creating.value = false
  }
}

async function resetPassword() {
  const user = selectedUser.value
  if (!user) return
  if (passwordForm.newPassword.length < 8) {
    ElMessage.warning('新密码至少需要 8 位')
    return
  }
  if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }

  passwordSaving.value = true
  try {
    await resetAdminUserPassword(user.id, { new_password: passwordForm.newPassword })
    passwordDialogVisible.value = false
    ElMessage.success('密码已修改，该账号需要重新登录')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '修改密码失败'))
  } finally {
    passwordSaving.value = false
  }
}

onMounted(() => loadUsers())
</script>

<template>
  <div class="page-stack" v-loading="loading">
    <section class="page-block list-surface list-surface--fixed admin-account-surface">
      <div class="filter-panel">
        <div class="query-grow">
          <div class="section-desc" style="margin-bottom: 8px">账号搜索</div>
          <el-input
            v-model="keyword"
            clearable
            :prefix-icon="Search"
            placeholder="搜索账号或姓名"
            size="large"
          />
        </div>
        <div class="filter-status">
          <div class="section-desc" style="margin-bottom: 8px">账号统计</div>
          <div class="status-box">共 {{ adminUsers.length }} 个后台账号</div>
        </div>
      </div>

      <div class="toolbar-row">
        <div>
          <h3 class="section-title" style="font-size: 16px">后台账号列表</h3>
          <p class="section-desc">管理登录账号、角色、启用状态以及各业务模块访问权限。</p>
        </div>
        <div class="toolbar-actions">
          <el-button type="primary" :icon="Plus" @click="createDialogVisible = true">新增账号</el-button>
          <el-button :icon="RefreshRight" @click="loadUsers()">刷新数据</el-button>
        </div>
      </div>

      <div class="table-area fixed-list-shell admin-account-table-area">
        <el-table :data="paginatedUsers" stripe height="100%" empty-text="暂无后台账号">
          <el-table-column label="账号" min-width="210">
            <template #default="{ row }">
              <div class="admin-account-cell">
                <span class="admin-account-cell__avatar"><User /></span>
                <div>
                  <strong>{{ row.display_name || row.username }}</strong>
                  <span>{{ row.username }}</span>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="角色" min-width="130">
            <template #default="{ row }">
              <el-tag :type="row.role === 'superadmin' ? 'primary' : 'info'">{{ getRoleLabel(row.role) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="权限范围" min-width="220">
            <template #default="{ row }">{{ getPermissionSummary(row) }}</template>
          </el-table-column>
          <el-table-column label="状态" min-width="110">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" min-width="180">
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="285" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" link @click="openPermissionDialog(row)">修改权限</el-button>
              <el-button type="primary" link :disabled="row.id === authStore.currentUser?.id" @click="openPasswordDialog(row)">
                修改密码
              </el-button>
              <el-button
                :type="row.is_active ? 'danger' : 'success'"
                link
                :disabled="row.id === authStore.currentUser?.id"
                @click="toggleUserStatus(row)"
              >
                {{ row.is_active ? '禁用' : '启用' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <ListPaginationFooter
          v-model:current-page="currentPage"
          :total-pages="totalPages"
          :page-size="pageSize"
          :total-items="filteredUsers.length"
        />
      </div>
    </section>

    <el-dialog
      v-model="permissionDialogVisible"
      title="修改账号权限"
      width="820px"
      destroy-on-close
      class="admin-permission-dialog"
    >
      <template v-if="selectedUser">
        <div class="admin-permission-dialog__identity">
          <span class="admin-account-cell__avatar"><User /></span>
          <div>
            <strong>{{ selectedUser.display_name || selectedUser.username }}</strong>
            <span>{{ selectedUser.username }} · {{ getRoleLabel(selectedUser.role) }}</span>
          </div>
        </div>

        <div class="admin-role-editor">
          <div>
            <strong>账号角色</strong>
            <span>切换角色会应用默认权限，之后仍可逐项调整。</span>
          </div>
          <el-segmented
            :model-value="accessForm.role"
            :options="[
              { label: '只读账号', value: 'viewer' },
              { label: '编辑员', value: 'editor' },
              { label: '超级管理员', value: 'superadmin' },
            ]"
            :disabled="isCurrentUser"
            @change="applyRolePreset($event as RoleType)"
          />
        </div>

        <div class="admin-permission-dialog__head">
          <div>
            <strong>模块权限</strong>
            <span>不可访问的模块不会显示在该账号左侧导航中。</span>
          </div>
          <el-tag v-if="accessForm.role === 'superadmin'" type="primary">全部权限</el-tag>
        </div>

        <div class="admin-permission-grid">
          <div v-for="permission in permissionDefinitions" :key="permission.key" class="admin-permission-row">
            <div class="admin-permission-row__copy">
              <strong>{{ permission.label }}</strong>
              <span>{{ permission.description }}</span>
            </div>
            <el-segmented
              v-model="accessForm.permissions[permission.key]"
              :options="permission.key === 'dashboard' ? permissionOptions.slice(1) : permissionOptions"
              :disabled="accessForm.role === 'superadmin'"
              size="small"
            />
          </div>
        </div>
      </template>

      <template #footer>
        <span class="admin-permission-dialog__note">保存后该账号需要重新登录。</span>
        <el-button @click="permissionDialogVisible = false">取消</el-button>
        <el-button type="primary" :icon="Check" :loading="saving" @click="saveAccess">保存权限</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="passwordDialogVisible" title="修改账号密码" width="480px" destroy-on-close>
      <template v-if="selectedUser">
        <div class="admin-password-target">
          正在修改账号 <strong>{{ selectedUser.username }}</strong> 的登录密码
        </div>
        <el-form label-position="top">
          <el-form-item label="新密码" required>
            <el-input
              v-model="passwordForm.newPassword"
              type="password"
              show-password
              autocomplete="new-password"
              placeholder="至少 8 位密码"
            />
          </el-form-item>
          <el-form-item label="确认新密码" required>
            <el-input
              v-model="passwordForm.confirmPassword"
              type="password"
              show-password
              autocomplete="new-password"
              placeholder="再次输入新密码"
              @keyup.enter="resetPassword"
            />
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="passwordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="passwordSaving" @click="resetPassword">确认修改</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="createDialogVisible" title="新增后台账号" width="520px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="登录账号" required>
          <el-input v-model="createForm.username" placeholder="例如：admin02" />
        </el-form-item>
        <el-form-item label="初始密码" required>
          <el-input v-model="createForm.password" type="password" show-password placeholder="至少 8 位密码" />
        </el-form-item>
        <el-form-item label="初始角色">
          <el-select v-model="createForm.role" style="width: 100%">
            <el-option label="只读账号" value="viewer" />
            <el-option label="编辑员" value="editor" />
            <el-option label="超级管理员" value="superadmin" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createUser">创建账号</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.admin-access-page {
  min-height: 0;
  align-content: start;
}

.admin-access-workbench {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  min-height: 680px;
  overflow: hidden;
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  background: #fff;
}

.admin-account-panel {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-width: 0;
  border-right: 1px solid var(--panel-border);
  background: #f8fafc;
}

.admin-account-panel__search {
  padding: 14px;
  border-bottom: 1px solid var(--panel-border);
  background: #fff;
}

.admin-account-list {
  padding: 8px;
  overflow: auto;
}

.admin-account-item {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr) 8px;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--text-main);
  text-align: left;
  cursor: pointer;
  transition: background 150ms ease, border-color 150ms ease;
}

.admin-account-item:hover {
  background: #eef3f9;
}

.admin-account-item.is-active {
  border-color: #cfe0ff;
  background: #eaf2ff;
}

.admin-account-item__avatar,
.admin-permission-identity__avatar {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 6px;
  background: #dce9ff;
  color: var(--brand-primary);
  font-weight: 700;
}

.admin-account-item__avatar svg {
  width: 17px;
}

.admin-account-item__copy {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.admin-account-item__copy strong,
.admin-account-item__copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.admin-account-item__copy strong {
  font-size: 13px;
}

.admin-account-item__copy small {
  color: var(--text-secondary);
  font-size: 11px;
}

.admin-account-item__status {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
}

.admin-account-item__status.is-disabled {
  background: #a8b1bd;
}

.admin-permission-panel {
  min-width: 0;
  padding: 20px 24px;
  overflow: auto;
}

.admin-permission-header,
.admin-permission-footer,
.admin-role-section,
.admin-permission-list__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.admin-permission-header {
  padding-bottom: 18px;
  border-bottom: 1px solid var(--panel-border);
}

.admin-permission-identity,
.admin-permission-header__actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.admin-permission-identity h3,
.admin-role-section h4,
.admin-permission-list__head h4 {
  margin: 0;
}

.admin-permission-identity p,
.admin-role-section p,
.admin-permission-list__head p {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
}

.admin-role-section {
  padding: 20px 0;
  border-bottom: 1px solid var(--panel-border);
}

.admin-permission-list {
  padding-top: 20px;
}

.admin-permission-list__head {
  margin-bottom: 12px;
}

.admin-permission-row {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto;
  align-items: center;
  gap: 20px;
  min-height: 60px;
  padding: 10px 12px;
  border-top: 1px solid #edf0f4;
}

.admin-permission-row__copy {
  display: grid;
  gap: 3px;
}

.admin-permission-row__copy strong {
  font-size: 13px;
}

.admin-permission-row__copy span {
  color: var(--text-secondary);
  font-size: 12px;
}

.admin-permission-footer {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--panel-border);
  color: var(--text-secondary);
  font-size: 12px;
}

@media (max-width: 900px) {
  .admin-access-workbench {
    grid-template-columns: 1fr;
  }

  .admin-account-panel {
    max-height: 330px;
    border-right: none;
    border-bottom: 1px solid var(--panel-border);
  }

  .admin-permission-header,
  .admin-role-section,
  .admin-permission-list__head,
  .admin-permission-footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .admin-permission-row {
    grid-template-columns: 1fr;
    gap: 10px;
  }
}

.admin-account-table-block {
  padding: 0;
  overflow: hidden;
}

.admin-account-table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--panel-border);
  color: var(--text-secondary);
  font-size: 12px;
}

.admin-account-search {
  width: min(340px, 100%);
}

.admin-account-table {
  width: 100%;
}

.admin-account-cell,
.admin-permission-dialog__identity {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.admin-account-cell__avatar {
  display: grid;
  place-items: center;
  flex: 0 0 34px;
  width: 34px;
  height: 34px;
  border-radius: 6px;
  background: #e8f0ff;
  color: var(--brand-primary);
}

.admin-account-cell__avatar :deep(svg) {
  width: 16px;
}

.admin-account-cell > div,
.admin-permission-dialog__identity > div,
.admin-role-editor > div,
.admin-permission-dialog__head > div {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.admin-account-cell strong,
.admin-account-cell span,
.admin-permission-dialog__identity strong,
.admin-permission-dialog__identity span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.admin-account-cell strong,
.admin-permission-dialog__identity strong {
  font-size: 13px;
}

.admin-account-cell span,
.admin-permission-dialog__identity span,
.admin-role-editor span,
.admin-permission-dialog__head span {
  color: var(--text-secondary);
  font-size: 12px;
}

.admin-permission-dialog__identity {
  padding: 0 0 14px;
  border-bottom: 1px solid var(--panel-border);
}

.admin-role-editor,
.admin-permission-dialog__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 16px 0;
}

.admin-role-editor {
  border-bottom: 1px solid var(--panel-border);
}

.admin-permission-dialog__head {
  padding-bottom: 10px;
}

.admin-permission-grid {
  max-height: 430px;
  overflow: auto;
  border: 1px solid var(--panel-border);
  border-radius: 6px;
}

.admin-permission-grid .admin-permission-row:first-child {
  border-top: none;
}

.admin-permission-dialog__note {
  margin-right: auto;
  color: var(--text-secondary);
  font-size: 12px;
}

.admin-password-target {
  margin-bottom: 16px;
  padding: 10px 12px;
  border: 1px solid #dce6f4;
  border-radius: 6px;
  background: #f7f9fc;
  color: var(--text-secondary);
  font-size: 13px;
}

.admin-password-target strong {
  color: var(--text-main);
}

:deep(.admin-permission-dialog .el-dialog__footer) {
  display: flex;
  align-items: center;
  gap: 10px;
}

@media (max-width: 700px) {
  .admin-account-table-toolbar,
  .admin-role-editor,
  .admin-permission-dialog__head {
    align-items: stretch;
    flex-direction: column;
  }

  .admin-account-search {
    width: 100%;
  }
}
</style>
