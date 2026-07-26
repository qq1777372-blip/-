<script setup lang="ts">
import {
  ArrowDown,
  Cellphone,
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
} from '@element-plus/icons-vue'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AdminManageDialog from '../components/AdminManageDialog.vue'
import ChangePasswordDialog from '../components/ChangePasswordDialog.vue'
import EditProfileDialog from '../components/EditProfileDialog.vue'
import SessionManageDialog from '../components/SessionManageDialog.vue'
import { useViewport } from '../composables/useViewport'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { isTablet } = useViewport()

const passwordDialogVisible = ref(false)
const profileDialogVisible = ref(false)
const adminDialogVisible = ref(false)
const sessionDialogVisible = ref(false)
const mobileMenuVisible = ref(false)
const desktopSidebarCollapsed = ref(false)
const webVersion = '2026.07.26.18'

const activeMenuPath = computed(() => String(route.meta.activeMenu ?? route.path))
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

watch(
  () => route.fullPath,
  () => {
    mobileMenuVisible.value = false
    passwordDialogVisible.value = false
    profileDialogVisible.value = false
    adminDialogVisible.value = false
    sessionDialogVisible.value = false
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
    adminDialogVisible.value = true
    return
  }

  if (command === 'manage-sessions') {
    sessionDialogVisible.value = true
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
          <strong>RuoShop Admin</strong>
          <span>任务记账与店铺后台</span>
        </div>
      </div>

      <el-menu
        :default-active="activeMenuPath"
        :default-openeds="['authorization', 'task-bookkeeping', 'store']"
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

        <el-menu-item index="/links">
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

        <el-sub-menu index="task-bookkeeping">
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

        <el-menu-item index="/dingtalk-profits">
          <el-icon><TrendCharts /></el-icon>
          <span>钉钉利润</span>
        </el-menu-item>

        <el-sub-menu index="store">
          <template #title>
            <el-icon><Management /></el-icon>
            <span>店铺管理</span>
          </template>
          <el-menu-item index="/shop-records">
            <el-icon><Management /></el-icon>
            <span>店铺账号</span>
          </el-menu-item>
          <el-menu-item index="/peer-shops">
            <el-icon><Management /></el-icon>
            <span>同行店铺</span>
          </el-menu-item>
          <el-menu-item index="/licenses">
            <el-icon><Document /></el-icon>
            <span>执照档案</span>
          </el-menu-item>
          <el-menu-item index="/account-usage">
            <el-icon><Cellphone /></el-icon>
            <span>账号使用记录</span>
          </el-menu-item>
          <el-menu-item index="/mobile-devices">
            <el-icon><Cellphone /></el-icon>
            <span>手机设备</span>
          </el-menu-item>
        </el-sub-menu>

        <el-menu-item index="/audit-logs" v-if="canManageAdmins">
          <el-icon><Setting /></el-icon>
          <span>安全日志</span>
        </el-menu-item>
      </el-menu>

      <div class="layout-version">Web v{{ webVersion }}</div>

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

      <section v-if="isTablet" class="layout-mobile-toolbar page-block">
        <div class="section-desc">全局搜索和账户操作都收纳到右上角。</div>
      </section>

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
          <strong>RuoShop Admin</strong>
          <span>任务记账与店铺后台</span>
        </div>
      </div>

      <el-menu
        :default-active="activeMenuPath"
        :default-openeds="['authorization', 'task-bookkeeping', 'store']"
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

        <el-menu-item index="/links">
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

        <el-sub-menu index="task-bookkeeping">
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

        <el-menu-item index="/dingtalk-profits">
          <el-icon><TrendCharts /></el-icon>
          <span>钉钉利润</span>
        </el-menu-item>

        <el-sub-menu index="store">
          <template #title>
            <el-icon><Management /></el-icon>
            <span>店铺管理</span>
          </template>
          <el-menu-item index="/shop-records">
            <el-icon><Management /></el-icon>
            <span>店铺账号</span>
          </el-menu-item>
          <el-menu-item index="/peer-shops">
            <el-icon><Management /></el-icon>
            <span>同行店铺</span>
          </el-menu-item>
          <el-menu-item index="/licenses">
            <el-icon><Document /></el-icon>
            <span>执照档案</span>
          </el-menu-item>
          <el-menu-item index="/account-usage">
            <el-icon><Cellphone /></el-icon>
            <span>账号使用记录</span>
          </el-menu-item>
          <el-menu-item index="/mobile-devices">
            <el-icon><Cellphone /></el-icon>
            <span>手机设备</span>
          </el-menu-item>
        </el-sub-menu>

        <el-menu-item index="/audit-logs" v-if="canManageAdmins">
          <el-icon><Setting /></el-icon>
          <span>安全日志</span>
        </el-menu-item>
      </el-menu>
    </div>
  </el-drawer>

  <EditProfileDialog v-model="profileDialogVisible" />
  <ChangePasswordDialog v-model="passwordDialogVisible" />
  <AdminManageDialog v-if="canManageAdmins" v-model="adminDialogVisible" />
  <SessionManageDialog v-model="sessionDialogVisible" />
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

.layout-mobile-toolbar {
  margin: 0 24px 0;
  padding: 12px 16px;
}

@media (max-width: 900px) {
  .layout-header {
    padding: 14px 16px 10px;
  }

  .layout-main {
    padding: 10px 16px 16px;
  }

  .layout-mobile-toolbar {
    margin: 0 16px 0;
  }

  .layout-title {
    font-size: 24px;
  }

  .header-shortcut span {
    display: none;
  }

  .header-shortcut {
    min-width: 44px;
    justify-content: center;
    padding: 0 12px;
  }
}
</style>
