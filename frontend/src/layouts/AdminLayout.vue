<script setup lang="ts">
import {
  ArrowDown,
  Bell,
  Box,
  Cellphone,
  ChatDotSquare,
  Document,
  Fold,
  House,
  Key,
  Link as LinkIcon,
  Management,
  Monitor,
  Search,
  Setting,
  SwitchButton,
  Tickets,
  TrendCharts,
  User,
  UserFilled,
} from '@element-plus/icons-vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchSystemAlerts } from '../api'
import ChangePasswordDialog from '../components/ChangePasswordDialog.vue'
import EditProfileDialog from '../components/EditProfileDialog.vue'
import SessionManageDialog from '../components/SessionManageDialog.vue'
import TotpSecurityDialog from '../components/TotpSecurityDialog.vue'
import { useViewport } from '../composables/useViewport'
import { useAuthStore } from '../stores/auth'
import type { SystemAlertItem } from '../types/api'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { isTablet } = useViewport()

const passwordDialogVisible = ref(false)
const profileDialogVisible = ref(false)
const sessionDialogVisible = ref(false)
const totpDialogVisible = ref(false)
const mobileMenuVisible = ref(false)
const desktopSidebarCollapsed = ref(false)
// Read at runtime from the version.json the release stamps into dist/, rather
// than a literal someone has to remember to bump. The literal had drifted to
// 2026.07.28.19 while the deployed build was 2026.08.07.24.
const webVersion = ref('')
const openAlertCount = ref(0)
const unreadAlertCount = ref(0)
const alertPreview = ref<SystemAlertItem[]>([])
const alertPopoverVisible = ref(false)
const showAllAlerts = ref(false)
const alertUpdatedAt = ref('')

interface AlertGroup {
  category: SystemAlertItem['category']
  severity: SystemAlertItem['severity']
  title: string
  description: string
  count: number
  route: string
}

const alertGroups = computed<AlertGroup[]>(() => {
  const severityRank = { critical: 3, warning: 2, info: 1 }
  const groups = new Map<SystemAlertItem['category'], SystemAlertItem[]>()
  for (const alert of alertPreview.value) {
    groups.set(alert.category, [...(groups.get(alert.category) ?? []), alert])
  }

  // 后端 build_system_alerts 会发 data 类（利润为空/停更、库存缺成本价），漏了它
  // 会让 titleMap[category] 取到 undefined、调用时抛 TypeError，整块 computed 崩掉、
  // 铃铛面板打不开。可选链兜底：以后后端再加新类别只是文案退化，不会再崩。
  const titleMap: Partial<Record<SystemAlertItem['category'], (count: number) => string>> = {
    inventory: (count) => `${count} 种商品库存异常`,
    outbound: (count) => `${count} 张出库单待处理`,
    license: (count) => `${count} 项执照到期提醒`,
    task: (count) => `${count} 项任务长时间未完成`,
    security: (count) => `${count} 项登录安全异常`,
    data: (count) => `${count} 项数据异常`,
  }

  return [...groups.entries()]
    .map(([category, items]) => {
      const sortedItems = [...items].sort((a, b) => severityRank[b.severity] - severityRank[a.severity])
      const criticalCount = items.filter((item) => item.severity === 'critical').length
      return {
        category,
        severity: sortedItems[0].severity,
        title: titleMap[category]?.(items.length) ?? `${items.length} 项待处理提醒`,
        description: criticalCount ? `其中 ${criticalCount} 项紧急，点击立即处理` : sortedItems[0].description,
        count: items.length,
        route: sortedItems[0].route,
      }
    })
    .sort((a, b) => severityRank[b.severity] - severityRank[a.severity])
})

const activeMenuPath = computed(() => String(route.meta.activeMenu ?? route.path))
const defaultOpeneds = computed(() => {
  const path = activeMenuPath.value

  if (['/license-keys', '/software-users'].includes(path)) {
    return ['authorization']
  }

  if (path.startsWith('/task-bookkeeping/')) {
    return ['task-bookkeeping']
  }

  if (path.startsWith('/warehouse/')) {
    return ['warehouse']
  }

  if (['/audit-logs', '/system-settings'].includes(path)) {
    return ['system-management']
  }

  if (['/sycm', '/shop-records', '/peer-shops', '/licenses', '/account-usage', '/mobile-devices', '/knowledge'].includes(path)) {
    return ['store']
  }

  return []
})
const pageTitle = computed(() => String(route.meta.title ?? '后台管理'))
const pageSection = computed(() => String(route.meta.section ?? '系统'))
const canManageAdmins = computed(() => authStore.currentUser?.role === 'superadmin')
const desktopAsideWidth = computed(() => (desktopSidebarCollapsed.value ? '88px' : '256px'))
const userInitial = computed(() =>
  String(authStore.currentUser?.display_name || authStore.currentUser?.username || 'A')
    .slice(0, 1)
    .toUpperCase(),
)

const isGlobalSearchRoute = computed(() => route.name === 'global-search')

function closeMobileMenu() {
  mobileMenuVisible.value = false
}

function toggleDesktopSidebar() {
  desktopSidebarCollapsed.value = !desktopSidebarCollapsed.value
}

async function goToGlobalSearch() {
  if (isGlobalSearchRoute.value) {
    return
  }

  await router.push({ name: 'global-search' })
}

async function refreshAlertCount() {
  try {
    const result = await fetchSystemAlerts('', 'open')
    openAlertCount.value = result.open_count
    alertPreview.value = result.items
    const currentKeys = result.items.map((item) => item.key)
    const seenKeys = readSeenAlertKeys().filter((key) => currentKeys.includes(key))
    localStorage.setItem(getAlertStorageKey(), JSON.stringify(seenKeys))
    unreadAlertCount.value = currentKeys.filter((key) => !seenKeys.includes(key)).length
    alertUpdatedAt.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch {
    openAlertCount.value = 0
    unreadAlertCount.value = 0
    alertPreview.value = []
  }
}

function getAlertStorageKey() {
  return `ruoshop-seen-alerts:${authStore.currentUser?.username ?? 'anonymous'}`
}

function readSeenAlertKeys(): string[] {
  try {
    const value = JSON.parse(localStorage.getItem(getAlertStorageKey()) ?? '[]')
    return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
  } catch {
    return []
  }
}

async function handleAlertPopoverShow() {
  await refreshAlertCount()
  localStorage.setItem(getAlertStorageKey(), JSON.stringify(alertPreview.value.map((item) => item.key)))
  unreadAlertCount.value = 0
}

async function openAlertBusiness(alert: { route: string }) {
  alertPopoverVisible.value = false
  if (alert.route) {
    await router.push(alert.route)
  }
}

function getAlertCategoryLabel(category: SystemAlertItem['category']) {
  const labels: Partial<Record<SystemAlertItem['category'], string>> = {
    inventory: '库存', outbound: '出库', license: '执照', task: '任务', security: '安全', data: '数据',
  }
  return labels[category] ?? '提醒'
}

async function loadWebVersion() {
  // BASE_URL is '/ui/' in a build and '/' under `npm run dev`, where no
  // version.json exists -- the catch leaves the label hidden rather than
  // showing a wrong number.
  try {
    const response = await fetch(`${import.meta.env.BASE_URL}version.json`, { cache: 'no-store' })
    if (!response.ok) return
    const payload = await response.json()
    if (typeof payload?.version === 'string') webVersion.value = payload.version
  } catch {
    // leave blank
  }
}

onMounted(refreshAlertCount)
onMounted(loadWebVersion)

watch(alertPopoverVisible, (visible) => {
  if (!visible) showAllAlerts.value = false
})

watch(
  () => route.fullPath,
  () => {
    mobileMenuVisible.value = false
    passwordDialogVisible.value = false
    profileDialogVisible.value = false
    sessionDialogVisible.value = false
    totpDialogVisible.value = false
    alertPopoverVisible.value = false
    void refreshAlertCount()
  },
)

async function handleLogout() {
  await authStore.signOut()
  await router.replace({ name: 'login' })
}

async function handleUserCommand(command: string | number | object) {
  if (command === 'edit-profile') {
    profileDialogVisible.value = true
    return
  }

  if (command === 'change-password') {
    passwordDialogVisible.value = true
    return
  }

  if (command === 'manage-admins') {
    await router.push({ name: 'admin-permissions' })
    return
  }

  if (command === 'manage-sessions') {
    sessionDialogVisible.value = true
    return
  }

  if (command === 'totp-security') {
    totpDialogVisible.value = true
    return
  }

  if (command === 'logout') {
    await handleLogout()
  }
}
</script>

<template>
  <el-container class="app-shell">
    <el-aside
      v-if="!isTablet"
      class="layout-aside"
      :class="{ 'layout-aside--collapsed': desktopSidebarCollapsed }"
      :width="desktopAsideWidth"
    >
      <div class="layout-brand">
        <div class="brand-logo">RS</div>
        <div class="layout-brand-copy">
          <strong>内部管理系统</strong>
          <span>任务记账与店铺后台</span>
        </div>
      </div>

      <el-menu
        :default-active="activeMenuPath"
        :default-openeds="defaultOpeneds"
        unique-opened
        class="layout-menu"
        router
        :collapse="desktopSidebarCollapsed"
        :collapse-transition="false"
        background-color="transparent"
        text-color="#b7c6d8"
        active-text-color="#ffffff"
      >
        <el-menu-item index="/dashboard">
          <el-icon><House /></el-icon>
          <span>运营工作台</span>
        </el-menu-item>

        <el-menu-item v-if="canManageAdmins" index="/server-status">
          <el-icon><Monitor /></el-icon>
          <span>服务器运行</span>
        </el-menu-item>

        <el-menu-item v-if="canManageAdmins" index="/admin-permissions">
          <el-icon><UserFilled /></el-icon>
          <span>账号与权限</span>
        </el-menu-item>

        <el-menu-item v-if="authStore.canAccess('links')" index="/links">
          <el-icon><LinkIcon /></el-icon>
          <span>链接广场</span>
        </el-menu-item>

        <el-sub-menu v-if="canManageAdmins" index="authorization">
          <template #title>
            <el-icon><Key /></el-icon>
            <span>授权管理</span>
          </template>
          <el-menu-item index="/license-keys">
            <el-icon><Key /></el-icon>
            <span>卡密管理</span>
          </el-menu-item>
          <el-menu-item index="/software-users">
            <el-icon><User /></el-icon>
            <span>软件账号</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="authStore.canAccess('task_bookkeeping')" index="task-bookkeeping">
          <template #title>
            <el-icon><Tickets /></el-icon>
            <span>任务记账</span>
          </template>
          <el-menu-item index="/task-bookkeeping/records">
            <el-icon><Document /></el-icon>
            <span>任务记录</span>
          </el-menu-item>
          <el-menu-item index="/task-bookkeeping/owners">
            <el-icon><User /></el-icon>
            <span>负责人管理</span>
          </el-menu-item>
        </el-sub-menu>

        <el-menu-item v-if="authStore.canAccess('dingtalk_profits')" index="/dingtalk-profits">
          <el-icon><TrendCharts /></el-icon>
          <span>钉钉利润</span>
        </el-menu-item>

        <el-sub-menu
          v-if="authStore.canAccess('shop_records') || authStore.canAccess('peer_shops') || authStore.canAccess('licenses') || authStore.canAccess('account_usage') || authStore.canAccess('mobile_devices')"
          index="store"
        >
          <template #title>
            <el-icon><Management /></el-icon>
            <span>店铺管理</span>
          </template>
          <el-menu-item v-if="authStore.canAccess('shop_records')" index="/sycm">
            <el-icon><TrendCharts /></el-icon>
            <span>生意参谋</span>
          </el-menu-item>
          <el-menu-item v-if="authStore.canAccess('shop_records')" index="/shop-records">
            <el-icon><Management /></el-icon>
            <span>店铺账号</span>
          </el-menu-item>
          <el-menu-item v-if="authStore.canAccess('peer_shops')" index="/peer-shops">
            <el-icon><Management /></el-icon>
            <span>同行店铺</span>
          </el-menu-item>
          <el-menu-item v-if="authStore.canAccess('licenses')" index="/licenses">
            <el-icon><Document /></el-icon>
            <span>执照档案</span>
          </el-menu-item>
          <el-menu-item v-if="authStore.canAccess('account_usage')" index="/account-usage">
            <el-icon><Cellphone /></el-icon>
            <span>账号使用记录</span>
          </el-menu-item>
          <el-menu-item v-if="authStore.canAccess('mobile_devices')" index="/mobile-devices">
            <el-icon><Cellphone /></el-icon>
            <span>手机设备</span>
          </el-menu-item>
          <el-menu-item index="/knowledge">
            <el-icon><ChatDotSquare /></el-icon>
            <span>知识库</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="authStore.canAccess('warehouse')" index="warehouse">
          <template #title><el-icon><Box /></el-icon><span>仓储管理</span></template>
          <el-menu-item index="/warehouse/stock">库存总览</el-menu-item>
          <el-menu-item index="/warehouse/inbound">入库管理</el-menu-item>
          <el-menu-item index="/warehouse/outbound">出库发货</el-menu-item>
          <el-menu-item index="/warehouse/movements">库存流水</el-menu-item>
          <el-menu-item index="/warehouse/master-data">基础资料</el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="canManageAdmins" index="system-management">
          <template #title><el-icon><Setting /></el-icon><span>系统管理</span></template>
          <el-menu-item index="/audit-logs">安全日志</el-menu-item>
          <el-menu-item index="/system-settings">系统设置</el-menu-item>
        </el-sub-menu>
      </el-menu>

      <div v-if="webVersion" class="layout-version">Web v{{ webVersion }}</div>

      <button type="button" class="aside-collapse-button" @click="toggleDesktopSidebar">
        <el-icon class="aside-collapse-button__icon">
          <Fold />
        </el-icon>
        <span>{{ desktopSidebarCollapsed ? '展开侧栏' : '收起侧栏' }}</span>
      </button>
    </el-aside>

    <el-container class="layout-content-shell">
      <el-header class="layout-header">
        <div class="header-left">
          <el-button v-if="isTablet" circle class="menu-trigger" @click="mobileMenuVisible = true">
            <el-icon><Fold /></el-icon>
          </el-button>

          <div class="title-stack">
            <div class="layout-breadcrumb">{{ pageSection }}</div>
            <h1 class="layout-title">{{ pageTitle }}</h1>
          </div>
        </div>

        <div class="layout-userbar">
          <el-popover
            v-model:visible="alertPopoverVisible"
            placement="bottom-end"
            trigger="click"
            :width="380"
            popper-class="system-alert-popover"
            @show="handleAlertPopoverShow"
          >
            <template #reference>
              <el-badge :value="unreadAlertCount" :hidden="unreadAlertCount === 0" :max="99" class="header-alert-badge">
                <button
                  type="button"
                  class="header-icon-button"
                  :class="{ 'header-icon-button--active': alertPopoverVisible }"
                  aria-label="异常提醒"
                >
                  <el-icon><Bell /></el-icon>
                </button>
              </el-badge>
            </template>

            <div class="alert-popover-panel">
              <div class="alert-popover-header">
                <div>
                  <strong>异常提醒</strong>
                  <span v-if="openAlertCount">{{ alertGroups.length }} 类异常 · {{ openAlertCount }} 项待处理</span>
                </div>
                <button type="button" class="alert-popover-close" aria-label="关闭" @click="alertPopoverVisible = false">×</button>
              </div>

              <div v-if="alertGroups.length && !showAllAlerts" class="alert-popover-list">
                <button
                  v-for="alert in alertGroups"
                  :key="alert.category"
                  type="button"
                  class="alert-popover-item"
                  @click="openAlertBusiness(alert)"
                >
                  <span class="alert-popover-item__icon" :class="`alert-popover-item__icon--${alert.severity}`">
                    <el-icon><Bell /></el-icon>
                  </span>
                  <span class="alert-popover-item__content">
                    <strong>{{ alert.title }}</strong>
                    <span>{{ alert.description }}</span>
                  </span>
                  <span class="alert-popover-item__category">{{ getAlertCategoryLabel(alert.category) }} · {{ alert.count }}</span>
                </button>
              </div>

              <div v-else-if="alertPreview.length" class="alert-popover-list alert-popover-list--all">
                <button
                  v-for="alert in alertPreview"
                  :key="alert.key"
                  type="button"
                  class="alert-popover-item"
                  @click="openAlertBusiness(alert)"
                >
                  <span class="alert-popover-item__icon" :class="`alert-popover-item__icon--${alert.severity}`">
                    <el-icon><Bell /></el-icon>
                  </span>
                  <span class="alert-popover-item__content">
                    <strong>{{ alert.title }}</strong>
                    <span>{{ alert.description }}</span>
                  </span>
                  <span class="alert-popover-item__category">{{ getAlertCategoryLabel(alert.category) }}</span>
                </button>
              </div>

              <div v-else class="alert-popover-empty">
                <span class="alert-popover-empty__icon"><el-icon><Bell /></el-icon></span>
                <strong>暂无异常</strong>
                <span>当前没有需要处理的异常提醒</span>
              </div>

              <div v-if="alertUpdatedAt" class="alert-popover-updated">最近更新：{{ alertUpdatedAt }}</div>
              <button
                v-if="openAlertCount"
                type="button"
                class="alert-popover-footer"
                @click="showAllAlerts = !showAllAlerts"
              >
                {{ showAllAlerts ? '返回分类摘要' : `查看全部（${openAlertCount}）` }}
              </button>

            </div>
          </el-popover>

          <button
            type="button"
            class="header-shortcut"
            :class="{ 'header-shortcut--active': isGlobalSearchRoute }"
            @click="goToGlobalSearch"
          >
            <el-icon><Search /></el-icon>
            <span>全局搜索</span>
          </button>

          <el-dropdown trigger="click" @command="handleUserCommand">
            <button type="button" class="user-chip user-chip-button">
              <span class="user-avatar">
                <img
                  v-if="authStore.currentUser?.avatar_url"
                  :src="authStore.currentUser.avatar_url"
                  :alt="authStore.displayName"
                  class="user-avatar-image"
                />
                <template v-else>{{ userInitial }}</template>
              </span>
              <span class="single-line-text">{{ authStore.displayName }}</span>
              <el-icon class="user-chip-caret"><ArrowDown /></el-icon>
            </button>

            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="edit-profile">
                  <span class="dropdown-item-label">
                    <el-icon><User /></el-icon>
                    账号资料
                  </span>
                </el-dropdown-item>

                <el-dropdown-item command="change-password">
                  <span class="dropdown-item-label">
                    <el-icon><Key /></el-icon>
                    修改密码
                  </span>
                </el-dropdown-item>

                <el-dropdown-item v-if="canManageAdmins" command="manage-admins">
                  <span class="dropdown-item-label">
                    <el-icon><Setting /></el-icon>
                    管理员管理
                  </span>
                </el-dropdown-item>

                <el-dropdown-item command="manage-sessions">
                  <span class="dropdown-item-label">
                    <el-icon><Monitor /></el-icon>
                    在线设备
                  </span>
                </el-dropdown-item>

                <el-dropdown-item command="totp-security">
                  <span class="dropdown-item-label">
                    <el-icon><Key /></el-icon>
                    登录二次验证
                  </span>
                </el-dropdown-item>

                <el-dropdown-item command="logout" divided>
                  <span class="dropdown-item-label danger-text">
                    <el-icon><SwitchButton /></el-icon>
                    退出登录
                  </span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="layout-main">
        <router-view v-slot="{ Component }">
          <Transition name="page-fade" mode="out-in">
            <component :is="Component" :key="route.fullPath" />
          </Transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>

  <el-drawer
    v-if="isTablet"
    v-model="mobileMenuVisible"
    size="280px"
    direction="ltr"
    :with-header="false"
    class="mobile-nav-drawer"
  >
    <div class="layout-aside mobile-aside">
      <div class="layout-brand">
        <div class="brand-logo">RS</div>
        <div>
          <strong>内部管理系统</strong>
          <span>任务记账与店铺后台</span>
        </div>
      </div>

      <el-menu
        :default-active="activeMenuPath"
        :default-openeds="defaultOpeneds"
        unique-opened
        class="layout-menu"
        router
        background-color="transparent"
        text-color="#b7c6d8"
        active-text-color="#ffffff"
        @select="closeMobileMenu"
      >
        <el-menu-item index="/dashboard">
          <el-icon><House /></el-icon>
          <span>运营工作台</span>
        </el-menu-item>

        <el-menu-item v-if="canManageAdmins" index="/server-status">
          <el-icon><Monitor /></el-icon>
          <span>服务器运行</span>
        </el-menu-item>

        <el-menu-item v-if="canManageAdmins" index="/admin-permissions">
          <el-icon><UserFilled /></el-icon>
          <span>账号与权限</span>
        </el-menu-item>

        <el-menu-item v-if="authStore.canAccess('links')" index="/links">
          <el-icon><LinkIcon /></el-icon>
          <span>链接广场</span>
        </el-menu-item>

        <el-sub-menu v-if="canManageAdmins" index="authorization">
          <template #title>
            <el-icon><Key /></el-icon>
            <span>授权管理</span>
          </template>
          <el-menu-item index="/license-keys">
            <el-icon><Key /></el-icon>
            <span>卡密管理</span>
          </el-menu-item>
          <el-menu-item index="/software-users">
            <el-icon><User /></el-icon>
            <span>软件账号</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="authStore.canAccess('task_bookkeeping')" index="task-bookkeeping">
          <template #title>
            <el-icon><Tickets /></el-icon>
            <span>任务记账</span>
          </template>
          <el-menu-item index="/task-bookkeeping/records">
            <el-icon><Document /></el-icon>
            <span>任务记录</span>
          </el-menu-item>
          <el-menu-item index="/task-bookkeeping/owners">
            <el-icon><User /></el-icon>
            <span>负责人管理</span>
          </el-menu-item>
        </el-sub-menu>

        <el-menu-item v-if="authStore.canAccess('dingtalk_profits')" index="/dingtalk-profits">
          <el-icon><TrendCharts /></el-icon>
          <span>钉钉利润</span>
        </el-menu-item>

        <el-sub-menu
          v-if="authStore.canAccess('shop_records') || authStore.canAccess('peer_shops') || authStore.canAccess('licenses') || authStore.canAccess('account_usage') || authStore.canAccess('mobile_devices')"
          index="store"
        >
          <template #title>
            <el-icon><Management /></el-icon>
            <span>店铺管理</span>
          </template>
          <el-menu-item v-if="authStore.canAccess('shop_records')" index="/sycm">
            <el-icon><TrendCharts /></el-icon>
            <span>生意参谋</span>
          </el-menu-item>
          <el-menu-item v-if="authStore.canAccess('shop_records')" index="/shop-records">
            <el-icon><Management /></el-icon>
            <span>店铺账号</span>
          </el-menu-item>
          <el-menu-item v-if="authStore.canAccess('peer_shops')" index="/peer-shops">
            <el-icon><Management /></el-icon>
            <span>同行店铺</span>
          </el-menu-item>
          <el-menu-item v-if="authStore.canAccess('licenses')" index="/licenses">
            <el-icon><Document /></el-icon>
            <span>执照档案</span>
          </el-menu-item>
          <el-menu-item v-if="authStore.canAccess('account_usage')" index="/account-usage">
            <el-icon><Cellphone /></el-icon>
            <span>账号使用记录</span>
          </el-menu-item>
          <el-menu-item v-if="authStore.canAccess('mobile_devices')" index="/mobile-devices">
            <el-icon><Cellphone /></el-icon>
            <span>手机设备</span>
          </el-menu-item>
          <el-menu-item index="/knowledge">
            <el-icon><ChatDotSquare /></el-icon>
            <span>知识库</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="authStore.canAccess('warehouse')" index="warehouse">
          <template #title><el-icon><Box /></el-icon><span>仓储管理</span></template>
          <el-menu-item index="/warehouse/stock">库存总览</el-menu-item>
          <el-menu-item index="/warehouse/inbound">入库管理</el-menu-item>
          <el-menu-item index="/warehouse/outbound">出库发货</el-menu-item>
          <el-menu-item index="/warehouse/movements">库存流水</el-menu-item>
          <el-menu-item index="/warehouse/master-data">基础资料</el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="canManageAdmins" index="system-management">
          <template #title><el-icon><Setting /></el-icon><span>系统管理</span></template>
          <el-menu-item index="/audit-logs">安全日志</el-menu-item>
          <el-menu-item index="/system-settings">系统设置</el-menu-item>
        </el-sub-menu>
      </el-menu>
    </div>
  </el-drawer>

  <EditProfileDialog v-model="profileDialogVisible" />
  <ChangePasswordDialog v-model="passwordDialogVisible" />
  <SessionManageDialog v-model="sessionDialogVisible" />
  <TotpSecurityDialog v-model="totpDialogVisible" />
</template>

<style scoped>
.layout-content-shell {
  min-width: 0;
}

.layout-aside {
  display: flex;
  flex-direction: column;
  height: 100vh;
  min-height: 100vh;
  overflow: hidden;
  padding: 16px 12px;
  background: var(--nav-bg);
  color: var(--nav-text);
  box-shadow: none;
  transition: width 0.2s ease, padding 0.2s ease;
  animation: sidebar-enter 0.32s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.mobile-aside {
  min-height: 100%;
  box-shadow: none;
}

.layout-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 8px 22px;
  border-bottom: 0;
}

.layout-brand-copy {
  min-width: 0;
}

.brand-logo {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  background: #6366f1;
  color: #ffffff;
  font-weight: 800;
}

.layout-brand strong {
  display: block;
  color: #ffffff;
  font-size: 15px;
}

.layout-brand span {
  display: block;
  margin-top: 4px;
  color: #9ca3af;
  font-size: 12px;
}

.layout-menu {
  flex: 1;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  margin-top: 0;
  border-right: none;
  min-width: 0;
}

.layout-menu::-webkit-scrollbar {
  width: 6px;
}

.layout-menu::-webkit-scrollbar-thumb {
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.18);
}

.layout-menu::-webkit-scrollbar-track {
  background: transparent;
}

.layout-menu :deep(.el-menu-item),
.layout-menu :deep(.el-sub-menu__title) {
  height: 40px;
  margin-bottom: 2px;
  border-radius: 8px;
  font-size: 13px;
  transition: color 0.16s ease, background-color 0.16s ease;
}

.layout-menu :deep(.el-menu-item:hover),
.layout-menu :deep(.el-sub-menu__title:hover) {
  background: rgba(255, 255, 255, 0.05);
  color: #ffffff;
}

.layout-menu :deep(.el-menu--collapse) {
  width: 100%;
}

.layout-menu :deep(.el-menu-item.is-active) {
  background: rgba(255, 255, 255, 0.1);
}

.layout-menu :deep(.el-menu-item.is-active .el-icon),
.layout-menu :deep(.el-sub-menu.is-active > .el-sub-menu__title .el-icon) {
  animation: nav-icon-pop 0.24s cubic-bezier(0.22, 1, 0.36, 1);
}

.layout-version {
  padding: 4px 8px 0;
  color: rgba(255, 255, 255, 0.46);
  font-size: 11px;
  line-height: 1.4;
  text-align: center;
}

.aside-collapse-button {
  margin-top: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  min-height: 40px;
  padding: 0 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.82);
  text-align: center;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
}

.aside-collapse-button:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.16);
}

.aside-collapse-button__icon {
  font-size: 16px;
  transition: transform 0.2s ease;
}

.layout-aside--collapsed .aside-collapse-button__icon {
  transform: rotate(180deg);
}

.layout-aside--collapsed {
  padding-left: 10px;
  padding-right: 10px;
}

.layout-aside--collapsed .layout-brand {
  justify-content: center;
  padding-left: 0;
  padding-right: 0;
}

.layout-aside--collapsed .layout-brand-copy,
.layout-aside--collapsed .layout-version,
.layout-aside--collapsed .aside-collapse-button span {
  display: none;
}

.layout-aside--collapsed .aside-collapse-button {
  padding-left: 0;
  padding-right: 0;
}

.layout-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  min-width: 0;
  min-height: 60px;
  padding: 8px 24px;
  border-bottom: 1px solid #e5e7eb;
  background: #ffffff;
  animation: header-enter 0.28s ease-out both;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.title-stack {
  min-width: 0;
}

.layout-breadcrumb {
  color: var(--text-secondary);
  font-size: 12px;
}

.layout-title {
  margin: 2px 0 0;
  font-size: 21px;
  font-weight: 600;
  line-height: 1.1;
}

.menu-trigger {
  flex: 0 0 auto;
}

.layout-userbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.header-icon-button {
  display: inline-grid;
  place-items: center;
  width: 36px;
  height: 36px;
  padding: 0;
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  background: var(--panel-bg);
  color: var(--text-main);
  cursor: pointer;
  transition: color 0.15s ease, background-color 0.15s ease, border-color 0.15s ease;
}

.header-icon-button:hover {
  border-color: #d1d5db;
  background: #f3f4f6;
}

.header-icon-button--active {
  border-color: #c7d2fe;
  background: #eef2ff;
  color: var(--brand-primary);
}

.header-icon-button :deep(.el-icon) {
  font-size: 17px;
}

.header-alert-badge {
  display: inline-flex;
}

.header-alert-badge :deep(.el-badge__content) {
  top: 3px;
  right: 6px;
  min-width: 17px;
  height: 17px;
  padding: 0 4px;
  border-width: 2px;
  font-size: 10px;
  line-height: 13px;
}

:global(.system-alert-popover.el-popover) {
  max-width: calc(100vw - 24px);
  padding: 0;
  overflow: hidden;
  border-radius: 8px;
  box-shadow: 0 14px 38px rgba(15, 23, 42, 0.16);
}

.alert-popover-panel {
  color: #0f172a;
}

.alert-popover-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 15px 16px;
  border-bottom: 1px solid #e5e7eb;
}

.alert-popover-header > div {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.alert-popover-header strong {
  font-size: 16px;
}

.alert-popover-header span {
  color: #64748b;
  font-size: 12px;
}

.alert-popover-close {
  width: 28px;
  height: 28px;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: #f1f5f9;
  color: #64748b;
  font-size: 19px;
  line-height: 1;
  cursor: pointer;
}

.alert-popover-list {
  max-height: 360px;
  overflow-y: auto;
}

.alert-popover-list--all {
  max-height: min(480px, 62vh);
}

.alert-popover-item {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  align-items: start;
  gap: 10px;
  width: 100%;
  padding: 12px 16px;
  border: none;
  border-bottom: 1px solid #eef2f7;
  background: #ffffff;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.alert-popover-item:hover {
  background: #f8fafc;
}

.alert-popover-item__icon {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 7px;
  background: #eff6ff;
  color: #2563eb;
}

.alert-popover-item__icon--warning {
  background: #fff7ed;
  color: #d97706;
}

.alert-popover-item__icon--critical {
  background: #fef2f2;
  color: #dc2626;
}

.alert-popover-item__content {
  display: grid;
  min-width: 0;
  gap: 4px;
}

.alert-popover-item__content strong,
.alert-popover-item__content span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alert-popover-item__content strong {
  font-size: 13px;
}

.alert-popover-item__content span,
.alert-popover-item__category {
  color: #64748b;
  font-size: 12px;
}

.alert-popover-item__category {
  padding-top: 2px;
  white-space: nowrap;
}

.alert-popover-empty {
  display: grid;
  justify-items: center;
  gap: 7px;
  padding: 34px 20px 30px;
  color: #94a3b8;
  font-size: 12px;
}

.alert-popover-empty strong {
  color: #334155;
  font-size: 14px;
}

.alert-popover-empty__icon {
  display: grid;
  place-items: center;
  width: 52px;
  height: 52px;
  margin-bottom: 4px;
  border-radius: 50%;
  background: #f1f5f9;
  color: #94a3b8;
  font-size: 22px;
}

.alert-popover-updated {
  padding: 9px 16px;
  border-top: 1px solid #eef2f7;
  background: #f8fafc;
  color: #94a3b8;
  font-size: 11px;
  text-align: right;
}

.alert-popover-footer {
  width: 100%;
  padding: 11px 16px;
  border: none;
  border-top: 1px solid #e5e7eb;
  background: #ffffff;
  color: var(--brand-primary);
  font-weight: 600;
  cursor: pointer;
}

.alert-popover-footer:hover {
  background: #f8fafc;
}

.header-shortcut {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  padding: 0 11px;
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  background: var(--panel-bg);
  color: var(--text-main);
  cursor: pointer;
  transition: color 0.15s ease, background-color 0.15s ease, border-color 0.15s ease;
}

.header-shortcut:hover {
  border-color: #d1d5db;
  background: #f3f4f6;
}

.header-shortcut--active {
  border-color: #c7d2fe;
  background: #eef2ff;
  color: var(--brand-primary);
}

.header-shortcut :deep(.el-icon) {
  font-size: 16px;
}

.user-chip {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 4px 8px 4px 12px;
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  background: var(--panel-bg);
}

.user-chip-button {
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}

.user-chip-button:hover {
  border-color: #d1d5db;
  background: #f9fafb;
}

.user-chip-button:focus-visible {
  outline: 2px solid rgba(99, 102, 241, 0.3);
  outline-offset: 2px;
}

.user-chip-caret {
  color: var(--text-secondary);
  font-size: 14px;
}

.user-avatar {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  overflow: hidden;
  border-radius: 999px;
  background: #e0e7ff;
  color: #4f46e5;
  font-size: 13px;
  font-weight: 700;
}

.user-avatar-image {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.dropdown-item-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.danger-text {
  color: var(--brand-danger);
}

.layout-main {
  padding: 20px 24px 24px;
}

@keyframes sidebar-enter {
  from {
    opacity: 0;
    transform: translateX(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes header-enter {
  from {
    opacity: 0;
    transform: translateY(-6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes nav-icon-pop {
  0% { transform: scale(0.84); }
  70% { transform: scale(1.08); }
  100% { transform: scale(1); }
}

@media (max-width: 900px) {
  .layout-header {
    flex-wrap: nowrap;
    gap: 8px;
    min-height: 56px;
    padding: 8px 12px;
  }

  .layout-main {
    padding: 10px 12px 16px;
  }

  .layout-title {
    overflow: hidden;
    font-size: 18px;
    line-height: 1.2;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .layout-breadcrumb {
    display: none;
  }

  .header-left {
    flex: 1 1 auto;
    gap: 8px;
    overflow: hidden;
  }

  .title-stack {
    overflow: hidden;
  }

  .layout-userbar {
    flex: 0 0 auto;
    flex-wrap: nowrap;
    gap: 6px;
  }

  .header-shortcut span {
    display: none;
  }

  .header-shortcut {
    min-width: 36px;
    width: 36px;
    min-height: 36px;
    justify-content: center;
    padding: 0;
  }

  .user-chip {
    width: 36px;
    min-width: 36px;
    height: 36px;
    justify-content: center;
    padding: 3px;
  }

  .user-chip .single-line-text,
  .user-chip-caret {
    display: none;
  }

  .user-avatar {
    width: 28px;
    height: 28px;
  }
}
</style>
