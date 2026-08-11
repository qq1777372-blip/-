import { createRouter, createWebHistory } from "@ionic/vue-router";
import { createWebHashHistory, type RouteRecordRaw } from "vue-router";
import { loadSession } from "./session";
import { isNativeApp } from "./runtime";

const routes: RouteRecordRaw[] = [
  { path: "/", redirect: "/tabs/home" },
  {
    path: "/login",
    component: () => import("./views/LoginPage.vue"),
    meta: { public: true },
  },
  {
    path: "/tabs",
    component: () => import("./layouts/AppTabs.vue"),
    children: [
      { path: "", redirect: "/tabs/home" },
      { path: "home", component: () => import("./views/HomePage.vue") },
      { path: "tasks", component: () => import("./views/TasksPage.vue") },
      // The ledger tab is a quick-entry form; history stays in the workbench.
      {
        path: "ledger",
        component: () => import("./views/ExpenseFormPage.vue"),
      },
      { path: "links", component: () => import("./views/LinkPlazaPage.vue") },
      {
        path: "workbench",
        component: () => import("./views/WorkbenchPage.vue"),
      },
      { path: "mine", component: () => import("./views/MinePage.vue") },

      {
        path: "list/shops",
        component: () => import("./views/ShopListPage.vue"),
      },
      {
        path: "list/owners",
        component: () => import("./views/OwnersPage.vue"),
      },
      {
        path: "list/users",
        component: () => import("./views/AdminUsersPage.vue"),
      },
      {
        path: "list/license-keys",
        component: () => import("./views/LicenseKeysPage.vue"),
      },
      {
        path: "shops/fields",
        component: () => import("./views/ShopFieldsPage.vue"),
      },
      {
        path: "detail/shops/:id",
        component: () => import("./views/ShopDetailPage.vue"),
      },
      {
        path: "form/shops/:id?",
        component: () => import("./views/ShopFormPage.vue"),
      },
      {
        path: "list/tasks",
        component: () => import("./views/TaskListPage.vue"),
      },
      {
        path: "detail/tasks/:id",
        component: () => import("./views/TaskDetailPage.vue"),
      },
      {
        path: "form/tasks/:id?",
        component: () => import("./views/TaskFormPage.vue"),
      },
      {
        path: "list/company-expenses",
        component: () => import("./views/ExpenseListPage.vue"),
      },
      {
        path: "detail/company-expenses/:id",
        component: () => import("./views/ExpenseDetailPage.vue"),
      },
      {
        path: "form/company-expenses/:id?",
        component: () => import("./views/ExpenseFormPage.vue"),
      },
      {
        path: "list/profits",
        component: () => import("./views/ProfitPage.vue"),
      },
      {
        path: "detail/links/:id",
        component: () => import("./views/LinkDetailPage.vue"),
      },
      {
        path: "form/links/:id?",
        component: () => import("./views/LinkFormPage.vue"),
      },
      {
        path: "form/articles/:id?",
        component: () => import("./views/LinkFormPage.vue"),
      },
      // The old iframe-based publisher is gone; keep the path as a redirect so
      // existing links and bookmarks land on the native article editor.
      {
        path: "legacy/article-publisher/:id?",
        redirect: (to) =>
          `/tabs/form/articles${to.params.id ? `/${to.params.id}` : ""}`,
      },
      {
        path: "module/ai-workspace",
        component: () => import("./views/AiWorkspacePage.vue"),
      },
      {
        path: "module/ai-models",
        component: () => import("./views/AiModelsPage.vue"),
      },
      {
        path: "module/ai-knowledge",
        component: () => import("./views/AiKnowledgePage.vue"),
      },
      {
        path: "module/ai-operations",
        component: () => import("./views/AiOperationsPage.vue"),
      },
      {
        path: "module/ai-capabilities",
        component: () => import("./views/AiCapabilitiesPage.vue"),
      },
      {
        path: "manage/:resource/:id",
        component: () => import("./views/RecordManagerDetailPage.vue"),
      },
      {
        path: "manage/:resource",
        component: () => import("./views/RecordManagerPage.vue"),
      },
      {
        path: "module/warehouse",
        component: () => import("./views/WarehousePage.vue"),
      },
      {
        path: "module/server",
        component: () => import("./views/ServerPage.vue"),
      },
      { path: "module/sycm", component: () => import("./views/SycmPage.vue") },
      {
        path: "warehouse/form/:kind/:id?",
        component: () => import("./views/WarehouseFormPage.vue"),
      },
      { path: "search", component: () => import("./views/SearchPage.vue") },
      { path: "alerts", component: () => import("./views/AlertsPage.vue") },
      {
        path: "module/:moduleKey",
        component: () => import("./views/ModulePage.vue"),
      },
      {
        path: "list/:resource",
        component: () => import("./views/ListPage.vue"),
      },
      {
        path: "detail/:resource/:id",
        component: () => import("./views/DetailPage.vue"),
      },
      {
        path: "settings",
        component: () => import("./views/SystemSettingsPage.vue"),
      },
      {
        path: "app-settings",
        component: () => import("./views/SettingsPage.vue"),
      },
    ],
  },
  {
    path: "/ai-workspace/shared/:id",
    component: () => import("./views/AiSharedChatPage.vue"),
    meta: { public: true },
  },

  // The personal ledger was removed from the app. Old links land on the company
  // ledger rather than a blank page; the backend records are untouched.
  { path: "/tabs/list/personal-expenses", redirect: "/tabs/ledger" },
  { path: "/tabs/detail/personal-expenses/:id", redirect: "/tabs/ledger" },
  { path: "/tabs/form/personal-expenses/:id?", redirect: "/tabs/ledger" },
  { path: "/tabs/ledger/:book", redirect: "/tabs/ledger" },

  // Legacy flat paths kept as redirects so old links, the iOS WebView entry and
  // any bookmarked URL still resolve into the tab shell.
  {
    path: "/list/:resource",
    redirect: (to) => `/tabs/list/${to.params.resource}`,
  },
  {
    path: "/detail/:resource/:id",
    redirect: (to) => `/tabs/detail/${to.params.resource}/${to.params.id}`,
  },
  {
    path: "/form/:resource/:id?",
    redirect: (to) =>
      `/tabs/form/${to.params.resource}${to.params.id ? `/${to.params.id}` : ""}`,
  },
  {
    path: "/module/:moduleKey",
    redirect: (to) => `/tabs/module/${to.params.moduleKey}`,
  },
  { path: "/shops/fields", redirect: "/tabs/shops/fields" },
  {
    path: "/warehouse/form/:kind/:id?",
    redirect: (to) =>
      `/tabs/warehouse/form/${to.params.kind}${to.params.id ? `/${to.params.id}` : ""}`,
  },
  {
    path: "/legacy/article-publisher/:id?",
    redirect: (to) =>
      `/tabs/form/articles${to.params.id ? `/${to.params.id}` : ""}`,
  },
  { path: "/search", redirect: "/tabs/search" },
  { path: "/alerts", redirect: "/tabs/alerts" },
  { path: "/settings", redirect: "/tabs/settings" },
  { path: "/app-settings", redirect: "/tabs/app-settings" },

  // Anything unmatched (old bookmarks, resources that never got a real form)
  // lands on home instead of rendering a blank outlet.
  { path: "/:pathMatch(.*)*", redirect: "/tabs/home" },
];

const router = createRouter({
  history: isNativeApp ? createWebHashHistory() : createWebHistory("/app/"),
  routes,
});
router.beforeEach(async (to) => {
  // Ionic keeps previous pages mounted during transitions. Release focus before
  // it marks the outgoing page aria-hidden to avoid hidden focused controls.
  if (document.activeElement instanceof HTMLElement)
    document.activeElement.blur();
  return to.meta.public || (await loadSession())
    ? true
    : { path: "/login", query: { redirect: to.fullPath } };
});
export default router;
