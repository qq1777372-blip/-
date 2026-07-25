import { createRouter, createWebHistory } from 'vue-router'
import type { RouteLocationGeneric } from 'vue-router'
import { pinia } from '../stores'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { title: '登录', requiresAuth: false },
  },
  {
    path: '/reader/links/:id',
    name: 'links-reader',
    component: () => import('../views/SavedLinkDetailView.vue'),
    meta: { title: '内容详情', standalone: true },
  },
  {
    path: '/reader/articles/:id',
    name: 'tutorial-docs-reader',
    component: () => import('../views/TutorialDocDetailView.vue'),
    meta: { title: '文章详情', standalone: true },
  },
  {
    path: '/article-publisher/new',
    name: 'tutorial-docs-editor-new',
    component: () => import('../views/TutorialDocEditorView.vue'),
    meta: { title: '文章发布', standalone: true },
  },
  {
    path: '/article-publisher/:id/edit',
    name: 'tutorial-docs-editor-edit',
    component: () => import('../views/TutorialDocEditorView.vue'),
    meta: { title: '编辑文章', standalone: true },
  },
  {
    path: '/',
    component: () => import('../layouts/AdminLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('../views/DashboardView.vue'),
        meta: { title: '运营工作台', section: '工作台' },
      },
      {
        path: 'server-status',
        name: 'server-status',
        component: () => import('../views/DashboardView.vue'),
        props: { serverOnly: true },
        meta: { title: '服务器运行', section: '系统运维' },
      },
      {
        path: 'global-search',
        name: 'global-search',
        component: () => import('../views/GlobalSearchView.vue'),
        meta: { title: '全局搜索', section: '工作台' },
      },
      {
        path: 'links',
        name: 'links',
        component: () => import('../views/SavedLinksView.vue'),
        meta: { title: '链接广场', section: '工具' },
      },
      {
        path: 'links/:id',
        name: 'links-detail',
        redirect: (to: RouteLocationGeneric) => ({
          name: 'links-reader',
          params: to.params,
          query: to.query,
          hash: to.hash,
        }),
        meta: { title: '内容详情', section: '工具', activeMenu: '/links' },
      },
      {
        path: 'tutorial-docs',
        name: 'tutorial-docs',
        redirect: { name: 'links' },
      },
      {
        path: 'tutorial-docs/new',
        name: 'tutorial-docs-new',
        redirect: { name: 'tutorial-docs-editor-new' },
        meta: { title: '文章发布', section: '工具', activeMenu: '/links' },
      },
      {
        path: 'tutorial-docs/:id',
        name: 'tutorial-docs-detail',
        redirect: (to: RouteLocationGeneric) => ({
          name: 'tutorial-docs-reader',
          params: to.params,
          query: to.query,
          hash: to.hash,
        }),
        meta: { title: '文章详情', section: '工具', activeMenu: '/links' },
      },
      {
        path: 'tutorial-docs/:id/edit',
        name: 'tutorial-docs-edit',
        redirect: (to: RouteLocationGeneric) => ({
          name: 'tutorial-docs-editor-edit',
          params: to.params,
          query: to.query,
          hash: to.hash,
        }),
        meta: { title: '编辑文章', section: '工具', activeMenu: '/links' },
      },
      {
        path: 'task-bookkeeping',
        name: 'task-bookkeeping',
        redirect: { name: 'task-bookkeeping-records' },
      },
      {
        path: 'task-bookkeeping/records',
        name: 'task-bookkeeping-records',
        component: () => import('../views/TaskBookkeepingRecordsView.vue'),
        meta: { title: '任务记录', section: '任务记账' },
      },
      {
        path: 'task-bookkeeping/owners',
        name: 'task-bookkeeping-owners',
        component: () => import('../views/TaskBookkeepingOwnersView.vue'),
        meta: { title: '负责人管理', section: '任务记账' },
      },
      {
        path: 'dingtalk-profits',
        name: 'dingtalk-profits',
        component: () => import('../views/DingTalkProfitsView.vue'),
        meta: { title: '钉钉利润', section: '利润中心' },
      },
      {
        path: 'shop-records',
        name: 'shop-records',
        component: () => import('../views/ShopRecordsView.vue'),
        meta: { title: '店铺账号管理', section: '店铺管理' },
      },
      {
        path: 'peer-shops',
        name: 'peer-shops',
        component: () => import('../views/PeerShopsView.vue'),
        meta: { title: '同行店铺', section: '店铺管理' },
      },
      {
        path: 'licenses',
        name: 'licenses',
        component: () => import('../views/LicensesView.vue'),
        meta: { title: '执照档案', section: '店铺管理' },
      },
      {
        path: 'account-usage',
        name: 'account-usage',
        component: () => import('../views/AccountUsageView.vue'),
        meta: { title: '账号使用记录', section: '店铺管理' },
      },
      {
        path: 'mobile-devices',
        name: 'mobile-devices',
        component: () => import('../views/MobileDevicesView.vue'),
        meta: { title: '手机设备', section: '店铺管理' },
      },
      {
        path: 'license-keys',
        name: 'license-keys',
        component: () => import('../views/LicenseKeysView.vue'),
        meta: { title: '卡密管理', section: '授权管理' },
      },
      {
        path: 'software-users',
        name: 'software-users',
        component: () => import('../views/SoftwareUsersView.vue'),
        meta: { title: '软件账号', section: '授权管理' },
      },
      {
        path: 'audit-logs',
        name: 'audit-logs',
        component: () => import('../views/AuditLogsView.vue'),
        meta: { title: '安全日志', section: '系统安全' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory('/ui/'),
  routes,
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore(pinia)

  if (!authStore.initialized) {
    await authStore.bootstrap()
  }

  if (to.meta.requiresAuth === false) {
    if (authStore.currentUser) {
      return { name: 'dashboard' }
    }

    return true
  }

  if (!authStore.currentUser) {
    return {
      name: 'login',
      query: { redirect: to.fullPath },
    }
  }

  return true
})

export default router
