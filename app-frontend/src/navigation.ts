// Every in-app page now lives inside the /tabs shell, so paths look like
// /tabs/detail/shops/3. Strip that prefix once here and let the table below
// describe sections only.
const TAB_ROOTS = [
  "/tabs/home",
  "/tabs/tasks",
  "/tabs/ledger",
  "/tabs/links",
  "/tabs/workbench",
  "/tabs/mine",
];

function section(path: string) {
  const pathname = path.split(/[?#]/, 1)[0];
  return pathname.startsWith("/tabs/") ? pathname.slice(5) : pathname;
}

export function fallbackPath(path: string) {
  const pathname = section(path);
  if (
    pathname.startsWith("/form/shops") ||
    pathname.startsWith("/detail/shops") ||
    pathname === "/shops/fields"
  )
    return "/tabs/list/shops";
  if (
    pathname.startsWith("/form/tasks") ||
    pathname.startsWith("/detail/tasks")
  )
    return "/tabs/list/tasks";
  if (
    pathname.startsWith("/form/company-expenses") ||
    pathname.startsWith("/detail/company-expenses")
  )
    return "/tabs/list/company-expenses";
  if (
    pathname.startsWith("/form/links") ||
    pathname.startsWith("/form/articles") ||
    pathname.startsWith("/detail/links")
  )
    return "/tabs/links";
  if (pathname.startsWith("/warehouse/form/"))
    return "/tabs/module/warehouse?tab=warehouses";
  if (/^\/manage\/[^/]+\/[^/]+$/.test(pathname))
    return pathname.replace(/\/[^/]+$/, "");
  const genericChild = pathname.match(/^\/(?:form|detail)\/([^/]+)/);
  if (genericChild) return `/tabs/list/${genericChild[1]}`;
  if (pathname === "/list/tasks" || pathname === "/list/profits")
    return "/tabs/tasks";
  if (pathname === "/app-settings") return "/tabs/mine";
  if (
    pathname === "/settings" ||
    pathname.startsWith("/list/") ||
    pathname.startsWith("/module/")
  )
    return "/tabs/workbench";
  if (pathname === "/alerts" || pathname === "/search") return "/tabs/home";
  return "/tabs/home";
}

// Tab roots have no parent to slide back to, so the edge swipe must be disabled
// there or it drags the user out of the shell.
export function canSwipeBack(path: string) {
  const pathname = path.split(/[?#]/, 1)[0];
  return pathname !== "/login" && !TAB_ROOTS.includes(pathname);
}
