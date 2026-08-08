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
    meta: { title: '文章发布', standalone: true, permission: 'links', writePermission: true },
  },
  {
    path: '/article-publisher/:id/edit',
    name: 'tutorial-docs-editor-edit',
    component: () => import('../views/TutorialDocEditorView.vue'),
    meta: { title: '编辑文章', standalone: true, permission: 'links', writePermission: true },
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
        meta: { title: '运营工作台', section: '工作台', permission: 'dashboard' },
      },
      {
        path: 'server-status',
        name: 'server-status',
        component: () => import('../views/DashboardView.vue'),
        props: { serverOnly: true },
        meta: { title: '服务器运行', section: '系统运维' },
      },
      {
        path: 'system-settings',
        name: 'system-settings',
        component: () => import('../views/SystemSettingsView.vue'),
        meta: { title: '系统设置中心', section: '系统管理', superadminOnly: true },
      },
      {
        path: 'admin-permissions',
        name: 'admin-permissions',
        component: () => import('../views/AdminPermissionsView.vue'),
        meta: { title: '账号与权限', section: '系统管理', superadminOnly: true },
      },
      {
        path: 'global-search',
        name: 'global-search',
        component: () => import('../views/GlobalSearchView.vue'),
        meta: { title: '全局搜索', section: '工作台', permission: 'dashboard' },
      },
      {
        path: 'links',
        name: 'links',
        component: () => import('../views/SavedLinksView.vue'),
        meta: { title: '链接广场', section: '工具', permission: 'links' },
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
        meta: { title: '任务记录', section: '任务记账', permission: 'task_bookkeeping' },
      },
      {
        path: 'task-bookkeeping/owners',
        name: 'task-bookkeeping-owners',
        component: () => import('../views/TaskBookkeepingOwnersView.vue'),
        meta: { title: '负责人管理', section: '任务记账', permission: 'task_bookkeeping' },
      },
      {
        path: 'dingtalk-profits',
        name: 'dingtalk-profits',
        component: () => import('../views/DingTalkProfitsView.vue'),
        meta: { title: '钉钉利润', section: '利润中心', permission: 'dingtalk_profits' },
      },
      {
        path: 'warehouse',
        name: 'warehouse',
        redirect: { name: 'warehouse-stock' },
      },
      {
        path: 'warehouse/stock', name: 'warehouse-stock', component: () => import('../views/WarehouseView.vue'), props: { mode: 'stock' },
        meta: { title: '库存总览', section: '仓储管理', permission: 'warehouse' },
      },
      {
        path: 'warehouse/inbound', name: 'warehouse-inbound', component: () => import('../views/WarehouseView.vue'), props: { mode: 'inbound' },
        meta: { title: '入库管理', section: '仓储管理', permission: 'warehouse' },
      },
      {
        path: 'warehouse/outbound', name: 'warehouse-outbound', component: () => import('../views/WarehouseView.vue'), props: { mode: 'outbound' },
        meta: { title: '出库发货', section: '仓储管理', permission: 'warehouse' },
      },
      {
        path: 'warehouse/movements', name: 'warehouse-movements', component: () => import('../views/WarehouseView.vue'), props: { mode: 'movement' },
        meta: { title: '库存流水', section: '仓储管理', permission: 'warehouse' },
      },
      {
        path: 'warehouse/master-data', name: 'warehouse-master-data', component: () => import('../views/WarehouseView.vue'), props: { mode: 'master' },
        meta: { title: '基础资料', section: '仓储管理', permission: 'warehouse' },
      },
      {
        path: 'warehouse/products', name: 'warehouse-products', component: () => import('../views/WarehouseView.vue'), props: { mode: 'products' },
        meta: { title: '商品档案', section: '仓储管理', permission: 'warehouse' },
      },
      {
        path: 'warehouse/warehouses', name: 'warehouse-warehouses', component: () => import('../views/WarehouseView.vue'), props: { mode: 'warehouses' },
        meta: { title: '仓库管理', section: '仓储管理', permission: 'warehouse' },
      },
      {
        path: 'sycm',
        name: 'sycm',
        component: () => import('../views/SycmView.vue'),
        meta: { title: '生意参谋', section: '店铺管理', permission: 'shop_records' },
      },
      {
        path: 'shop-records',
        name: 'shop-records',
        component: () => import('../views/ShopRecordsView.vue'),
        meta: { title: '店铺账号管理', section: '店铺管理', permission: 'shop_records' },
      },
      {
        path: 'peer-shops',
        name: 'peer-shops',
        component: () => import('../views/PeerShopsView.vue'),
        meta: { title: '同行店铺', section: '店铺管理', permission: 'peer_shops' },
      },
      {
        path: 'licenses',
        name: 'licenses',
        component: () => import('../views/LicensesView.vue'),
        meta: { title: '执照档案', section: '店铺管理', permission: 'licenses' },
      },
      {
        path: 'account-usage',
        name: 'account-usage',
        component: () => import('../views/AccountUsageView.vue'),
        meta: { title: '账号使用记录', section: '店铺管理', permission: 'account_usage' },
      },
      {
        path: 'mobile-devices',
        name: 'mobile-devices',
        component: () => import('../views/MobileDevicesView.vue'),
        meta: { title: '手机设备', section: '店铺管理', permission: 'mobile_devices' },
      },
      {
        // 知识问答由独立服务提供（knowledge-base.service，见 deploy/README.md），
        // 这里只是把它嵌进后台。以前这个入口是 public/knowledge-menu.js 在运行时
        // 往侧边栏 DOM 里插一个假菜单项，Vue 重渲染菜单时会把它清掉，dev 下基本
        // 看不到。改成正常路由后由 Vue 自己管理，不再依赖菜单的内部结构。
        // 没有 knowledge 权限键，因此不加 permission，与原脚本的无条件插入一致。
        path: 'knowledge',
        name: 'knowledge',
        component: () => import('../views/KnowledgeView.vue'),
        meta: { title: '知识问答', section: '店铺管理' },
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

  if (to.meta.superadminOnly && authStore.currentUser.role !== 'superadmin') {
    return { name: 'dashboard' }
  }

  const permission = to.meta.permission
  if (typeof permission === 'string') {
    if (!authStore.canAccess(permission as import('../types/api').PermissionModule)) {
      return { name: 'dashboard' }
    }
    if (to.meta.writePermission && !authStore.canWrite(permission as import('../types/api').PermissionModule)) {
      return { name: 'links' }
    }
  }

  return true
})

export default router
