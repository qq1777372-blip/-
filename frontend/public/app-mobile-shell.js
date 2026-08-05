(function () {
  const ua = navigator.userAgent || "";
  const params = new URLSearchParams(location.search);
  const iosWebView = /iPhone|iPad|iPod/i.test(ua) && /AppleWebKit/i.test(ua) && !/Safari\//i.test(ua);
  const appClient = params.get("app") === "1" || iosWebView || matchMedia?.("(display-mode: standalone)").matches || navigator.standalone === true || Boolean(window.XiaoXuApp) || Boolean(window.webkit?.messageHandlers?.xiaoxuApp);
  if (!appClient) return;
  const root = document.documentElement;
  root.classList.add("app-client-mode", "app-redesign");
  root.classList.remove("mobile-web-mode");
  const appModuleGroups = {
    authorization:new Set(["/license-keys","/software-users"]),
    bookkeeping:new Set(["/task-bookkeeping/records","/task-bookkeeping/owners","/dingtalk-profits"]),
    shop:new Set(["/shop-records","/peer-shops","/licenses","/account-usage","/mobile-devices"]),
    warehouse:new Set(["/warehouse/stock","/warehouse/inbound","/warehouse/outbound","/warehouse/movements","/warehouse/master-data"]),
    system:new Set(["/admin-permissions","/audit-logs","/system-settings"])
  };
  const appModuleClasses = Object.keys(appModuleGroups).map((group)=>`app-module-${group}`);
  const appRouteReadySelectors = {
    "/license-keys":".license-surface",
    "/software-users":".software-user-surface",
    "/task-bookkeeping/records":".task-filter-shell",
    "/task-bookkeeping/owners":".owner-card-list",
    "/dingtalk-profits":".profit-card-list",
    "/shop-records":".shop-card-list",
    "/peer-shops":".peer-shop-card-list",
    "/licenses":".license-card-list",
    "/account-usage":".account-card-list",
    "/mobile-devices":".account-card-list",
    "/warehouse/stock":".warehouse-page",
    "/warehouse/inbound":".warehouse-page",
    "/warehouse/outbound":".warehouse-page",
    "/warehouse/movements":".warehouse-page",
    "/warehouse/master-data":".warehouse-page",
    "/admin-permissions":".admin-access-page",
    "/audit-logs":".audit-card-list",
    "/system-settings":".settings-page"
  };
  function currentAppRoute() { return location.pathname.replace(/^\/ui/,"") || "/dashboard"; }
  function appModuleGroup(route = currentAppRoute()) {
    return Object.entries(appModuleGroups).find(([,routes])=>routes.has(route))?.[0] || "";
  }
  function setAppRouteState(route = currentAppRoute(), pending = false) {
    const group = appModuleGroup(route);
    root.classList.remove(...appModuleClasses);
    root.classList.toggle("app-module-route",Boolean(group));
    if (group) root.classList.add(`app-module-${group}`);
    root.classList.toggle("app-route-pending",Boolean(group && group !== "warehouse" && pending));
    if (pending) root.classList.remove("app-route-ready");
  }
  setAppRouteState(currentAppRoute(),root.classList.contains("app-route-pending"));
  ["pushState","replaceState"].forEach((method)=>{
    const nativeMethod = history[method].bind(history);
    history[method] = function (state,title,url) {
      if (url) {
        try { prepareAppRoute(new URL(String(url),location.href).pathname.replace(/^\/ui/,"") || "/dashboard"); } catch {}
      }
      return nativeMethod(state,title,url);
    };
  });
  function normalizeAppViewport() {
    let viewport = document.querySelector('meta[name="viewport"]');
    if (!viewport) { viewport = document.createElement("meta"); viewport.name = "viewport"; document.head.appendChild(viewport); }
    viewport.content = "width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover,interactive-widget=resizes-content";
    root.style.removeProperty("zoom");
    document.body?.style.removeProperty("zoom");
  }
  normalizeAppViewport();
  const originalWindowOpen = window.open.bind(window);
  window.open = function (url, target, features) {
    try {
      const parsed = new URL(String(url || ""),location.href);
      if (parsed.origin === location.origin && parsed.pathname.startsWith("/ui/")) {
        const route = `${parsed.pathname.replace(/^\/ui/,"")}${parsed.search}${parsed.hash}`;
        setTimeout(async()=>{
          const router = vueRouter();
          if (router?.push) { try { await router.push(route); } catch {} }
          else { history.pushState(null,"",parsed.href); dispatchEvent(new PopStateEvent("popstate",{state:history.state})); }
          root.classList.remove("app-native-hub-open");
          const title = route.includes("tutorial-docs/new") ? "\u6587\u7ae0\u53d1\u5e03" : route.includes("tutorial-docs") ? "\u6587\u7ae0\u8be6\u60c5" : "\u94fe\u63a5\u5e7f\u573a";
          updateHeader(title,true);
          updateBottom("links");
        },0);
        return window;
      }
    } catch {}
    return originalWindowOpen(url,target,features);
  };
  const taskLabels = new Set(["\u4efb\u52a1\u8bb0\u5f55", "\u8d1f\u8d23\u4eba\u7ba1\u7406", "\u9489\u9489\u5229\u6da6", "\u516c\u53f8\u8bb0\u8d26"]);
  const mineLabels = new Set(["\u8d26\u53f7\u4e0e\u6743\u9650", "\u5361\u5bc6\u7ba1\u7406", "\u8f6f\u4ef6\u8d26\u53f7", "\u5b89\u5168\u65e5\u5fd7", "\u7cfb\u7edf\u8bbe\u7f6e"]);
  const groupOrder = ["\u5e38\u7528\u529f\u80fd", "\u6388\u6743\u7ba1\u7406", "\u4efb\u52a1\u8bb0\u8d26", "\u5e97\u94fa\u7ba1\u7406", "\u4ed3\u50a8\u7ba1\u7406", "\u7cfb\u7edf\u7ba1\u7406", "\u5176\u4ed6\u529f\u80fd"];
  const standaloneGroups = new Map([["\u8fd0\u8425\u5de5\u4f5c\u53f0","\u5e38\u7528\u529f\u80fd"],["\u670d\u52a1\u5668\u8fd0\u884c","\u5e38\u7528\u529f\u80fd"],["\u94fe\u63a5\u5e7f\u573a","\u5e38\u7528\u529f\u80fd"],["\u77e5\u8bc6\u5e93","\u5e38\u7528\u529f\u80fd"],["\u8d26\u53f7\u4e0e\u6743\u9650","\u7cfb\u7edf\u7ba1\u7406"],["\u5b89\u5168\u65e5\u5fd7","\u7cfb\u7edf\u7ba1\u7406"],["\u7cfb\u7edf\u8bbe\u7f6e","\u7cfb\u7edf\u7ba1\u7406"]]);
  const fixedFeatures = [
    ["\u8fd0\u8425\u5de5\u4f5c\u53f0","\u5e38\u7528\u529f\u80fd","/dashboard"],
    ["\u670d\u52a1\u5668\u8fd0\u884c","\u5e38\u7528\u529f\u80fd","/server-status"],
    ["\u94fe\u63a5\u5e7f\u573a","\u5e38\u7528\u529f\u80fd","/links"],
    ["\u77e5\u8bc6\u5e93","\u5e38\u7528\u529f\u80fd","#knowledge"],
    ["\u5361\u5bc6\u7ba1\u7406","\u6388\u6743\u7ba1\u7406","/license-keys"],
    ["\u8f6f\u4ef6\u8d26\u53f7","\u6388\u6743\u7ba1\u7406","/software-users"],
    ["\u4efb\u52a1\u8bb0\u5f55","\u4efb\u52a1\u8bb0\u8d26","/task-bookkeeping/records"],
    ["\u8d1f\u8d23\u4eba\u7ba1\u7406","\u4efb\u52a1\u8bb0\u8d26","/task-bookkeeping/owners"],
    ["\u9489\u9489\u5229\u6da6","\u4efb\u52a1\u8bb0\u8d26","/dingtalk-profits"],
    ["\u516c\u53f8\u8bb0\u8d26","\u4efb\u52a1\u8bb0\u8d26","#company-expenses"],
    ["\u5e97\u94fa\u8d26\u53f7","\u5e97\u94fa\u7ba1\u7406","/shop-records"],
    ["\u540c\u884c\u5e97\u94fa","\u5e97\u94fa\u7ba1\u7406","/peer-shops"],
    ["\u6267\u7167\u6863\u6848","\u5e97\u94fa\u7ba1\u7406","/licenses"],
    ["\u8d26\u53f7\u4f7f\u7528\u8bb0\u5f55","\u5e97\u94fa\u7ba1\u7406","/account-usage"],
    ["\u624b\u673a\u8bbe\u5907","\u5e97\u94fa\u7ba1\u7406","/mobile-devices"],
    ["\u5e93\u5b58\u603b\u89c8","\u4ed3\u50a8\u7ba1\u7406","/warehouse/stock"],
    ["\u5165\u5e93\u7ba1\u7406","\u4ed3\u50a8\u7ba1\u7406","/warehouse/inbound"],
    ["\u51fa\u5e93\u53d1\u8d27","\u4ed3\u50a8\u7ba1\u7406","/warehouse/outbound"],
    ["\u5e93\u5b58\u6d41\u6c34","\u4ed3\u50a8\u7ba1\u7406","/warehouse/movements"],
    ["\u57fa\u7840\u8d44\u6599","\u4ed3\u50a8\u7ba1\u7406","/warehouse/master-data"],
    ["\u8d26\u53f7\u4e0e\u6743\u9650","\u7cfb\u7edf\u7ba1\u7406","/admin-permissions"],
    ["\u5b89\u5168\u65e5\u5fd7","\u7cfb\u7edf\u7ba1\u7406","/audit-logs"],
    ["\u7cfb\u7edf\u8bbe\u7f6e","\u7cfb\u7edf\u7ba1\u7406","/system-settings"]
  ].map(([label,group,route])=>({label,group,route,node:null}));
  const favoriteLabels = ["\u516c\u53f8\u8bb0\u8d26","\u4efb\u52a1\u8bb0\u5f55","\u9489\u9489\u5229\u6da6","\u5e97\u94fa\u8d26\u53f7","\u5e93\u5b58\u603b\u89c8","\u94fe\u63a5\u5e7f\u573a","\u77e5\u8bc6\u5e93","\u670d\u52a1\u5668\u8fd0\u884c","\u624b\u673a\u8bbe\u5907"];
  const permissionByLabel = new Map([
    ["\u8fd0\u8425\u5de5\u4f5c\u53f0","dashboard"],["\u77e5\u8bc6\u5e93","dashboard"],["\u94fe\u63a5\u5e7f\u573a","links"],
    ["\u4efb\u52a1\u8bb0\u5f55","task_bookkeeping"],["\u8d1f\u8d23\u4eba\u7ba1\u7406","task_bookkeeping"],["\u516c\u53f8\u8bb0\u8d26","task_bookkeeping"],
    ["\u9489\u9489\u5229\u6da6","dingtalk_profits"],["\u5e97\u94fa\u8d26\u53f7","shop_records"],["\u540c\u884c\u5e97\u94fa","peer_shops"],
    ["\u6267\u7167\u6863\u6848","licenses"],["\u8d26\u53f7\u4f7f\u7528\u8bb0\u5f55","account_usage"],["\u624b\u673a\u8bbe\u5907","mobile_devices"],
    ["\u5e93\u5b58\u603b\u89c8","warehouse"],["\u5165\u5e93\u7ba1\u7406","warehouse"],["\u51fa\u5e93\u53d1\u8d27","warehouse"],
    ["\u5e93\u5b58\u6d41\u6c34","warehouse"],["\u57fa\u7840\u8d44\u6599","warehouse"]
  ]);
  const superadminLabels = new Set(["\u670d\u52a1\u5668\u8fd0\u884c","\u5361\u5bc6\u7ba1\u7406","\u8f6f\u4ef6\u8d26\u53f7","\u8d26\u53f7\u4e0e\u6743\u9650","\u5b89\u5168\u65e5\u5fd7","\u7cfb\u7edf\u8bbe\u7f6e"]);
  let currentView = "home", menuSignature = "", refreshTimer = 0, dashboardTimer = 0, dashboardSignature = "", accessUser = null, permissionsLoaded = false, directExpenseOpening = false, moduleTimer = 0, stockSignature = "", appNotifications = [], notificationTimer = 0, notificationReturnView = "home", shopDetailSequence = 0;
  const shopDetailRecords = new Map();
  const iconPaths = {
    grid:"M3 3h8v8H3V3Zm10 0h8v8h-8V3ZM3 13h8v8H3v-8Zm10 0h8v8h-8v-8Z",
    record:"M5 3h14v18H5V3Zm3 4v2h8V7H8Zm0 5v2h3v-2H8Zm5 0v2h3v-2h-3Zm-5 4v2h3v-2H8Zm5 0v2h3v-2h-3Z",
    shop:"M4 4h16l1 5a4 4 0 0 1-2 3.5V21H5v-8.5A4 4 0 0 1 3 9l1-5Zm3 9v6h10v-6a4 4 0 0 1-3-1.4A4 4 0 0 1 12 13a4 4 0 0 1-2-1.4A4 4 0 0 1 7 13Z",
    user:"M12 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10Zm0 2c-5 0-9 2.7-9 6v2h18v-2c0-3.3-4-6-9-6Z",
    phone:"M7 2h10a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Zm0 3v14h10V5H7Zm4 11h2v2h-2v-2Z",
    server:"M4 3h16v6H4V3Zm3 2v2h2V5H7Zm-3 6h16v10H4V11Zm3 3v2h2v-2H7Zm5 0v2h5v-2h-5Z"
  };
  function iconPath(label) {
    if (["\u8bb0\u8d26","\u5229\u6da6","\u8bb0\u5f55"].some((key)=>label.includes(key))) return iconPaths.record;
    if (["\u5e97\u94fa","\u4ed3","\u5e93\u5b58","\u5165\u5e93","\u51fa\u5e93"].some((key)=>label.includes(key))) return iconPaths.shop;
    if (["\u8d26\u53f7","\u8d1f\u8d23\u4eba","\u6743\u9650","\u8f6f\u4ef6"].some((key)=>label.includes(key))) return iconPaths.user;
    if (["\u624b\u673a","\u8bbe\u5907"].some((key)=>label.includes(key))) return iconPaths.phone;
    if (["\u670d\u52a1\u5668","\u7cfb\u7edf","\u5b89\u5168"].some((key)=>label.includes(key))) return iconPaths.server;
    return iconPaths.grid;
  }
  function escapeHtml(value) {
    return String(value || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
  }
  function preferredMenu() {
    return Array.from(document.querySelectorAll(".layout-menu")).sort((a,b)=>b.querySelectorAll(".el-menu-item").length-a.querySelectorAll(".el-menu-item").length)[0];
  }
  function canShowFeature(item) {
    if (!permissionsLoaded) return false;
    if (accessUser?.role === "superadmin") return true;
    if (superadminLabels.has(item.label)) return false;
    const permission = permissionByLabel.get(item.label);
    const level = permission ? accessUser?.permissions?.[permission] : "";
    return permission ? level === "read" || level === "write" : Boolean(item.node);
  }
  async function loadAccess() {
    try {
      const response = await fetch("/auth/me",{credentials:"same-origin",headers:{Accept:"application/json"}});
      if (response.ok) accessUser = await response.json();
    } catch {}
    permissionsLoaded = true;
    updateAppAvatar();
    if (root.classList.contains("app-native-hub-open")) showHub(currentView);
    loadAppNotifications();
  }
  function updateAppAvatar() {
    const avatar = document.querySelector("[data-app-profile]");
    if (!avatar || !accessUser) return;
    const name = accessUser.display_name || accessUser.username || userName();
    avatar.replaceChildren();
    avatar.classList.toggle("has-image",Boolean(accessUser.avatar_url));
    if (accessUser.avatar_url) {
      const image = document.createElement("img");
      image.src = accessUser.avatar_url;
      image.alt = name;
      image.addEventListener("error",()=>{avatar.classList.remove("has-image");avatar.textContent=name.slice(0,2)},{once:true});
      avatar.appendChild(image);
    } else avatar.textContent = name.slice(0,2);
  }
  function notificationSignature() {
    return appNotifications.map((item)=>`${item.title}:${item.value}`).join("|");
  }
  function unreadNotificationCount() {
    if (!appNotifications.length) return 0;
    return localStorage.getItem("app-notification-read-signature") === notificationSignature() ? 0 : appNotifications.length;
  }
  function updateNotificationBadges() {
    const count = unreadNotificationCount();
    document.querySelectorAll(".app-notification-badge").forEach((badge)=>{
      badge.hidden = count < 1;
      badge.textContent = count > 99 ? "99+" : String(count);
    });
  }
  function markNotificationsRead() {
    localStorage.setItem("app-notification-read-signature",notificationSignature());
    updateNotificationBadges();
  }
  async function loadAppNotifications() {
    if (!permissionsLoaded) return;
    const requestJson = async (url)=>{
      const response = await fetch(url,{credentials:"same-origin",headers:{Accept:"application/json"}});
      if (!response.ok) return null;
      return response.json();
    };
    const [dashboardResult,warehouseResult,expenseResult] = await Promise.allSettled([
      requestJson("/dashboard/stats"),requestJson("/warehouse/summary"),requestJson("/company-expenses/summary")
    ]);
    const dashboard = dashboardResult.status === "fulfilled" ? dashboardResult.value : null;
    const warehouse = warehouseResult.status === "fulfilled" ? warehouseResult.value : null;
    const expenses = expenseResult.status === "fulfilled" ? expenseResult.value : null;
    const available = new Set(readFeatures().map((item)=>item.label));
    const items = [];
    const add = (condition,title,value,note,target,tone="primary")=>{
      if (!condition || (target && !available.has(target))) return;
      items.push({title,value:String(value),note,target,tone});
    };
    if (dashboard) {
      add(dashboard.expired_license_count > 0,"\u6267\u7167\u5df2\u8fc7\u671f",`${dashboard.expired_license_count} \u9879`,`\u8bf7\u5c3d\u5feb\u5904\u7406\u5df2\u8fc7\u671f\u4e3b\u4f53\u8d44\u6599`,"\u6267\u7167\u6863\u6848","danger");
      add(dashboard.expiring_license_count > 0,"30\u5929\u5185\u5230\u671f",`${dashboard.expiring_license_count} \u9879`,`\u63d0\u524d\u7eed\u8bc1\uff0c\u907f\u514d\u5e97\u94fa\u8d44\u6599\u65ad\u6863`,"\u6267\u7167\u6863\u6848","warning");
      add(dashboard.banned_account_count > 0,"\u5df2\u5c01\u8d26\u53f7",`${dashboard.banned_account_count} \u4e2a`,`\u68c0\u67e5\u5c01\u7981\u539f\u56e0\u548c\u66ff\u6362\u65b9\u6848`,"\u8d26\u53f7\u4f7f\u7528\u8bb0\u5f55","danger");
      add(dashboard.pending_task_count > 0,"\u5f85\u7b7e\u6536\u4efb\u52a1",`${dashboard.pending_task_count} \u6761`,`\u53ca\u65f6\u8ddf\u8fdb\u4efb\u52a1\u7b7e\u6536\u72b6\u6001`,"\u4efb\u52a1\u8bb0\u5f55");
      add(dashboard.pending_settlement_count > 0,"\u5f85\u7ed3\u7b97\u4efb\u52a1",`${dashboard.pending_settlement_count} \u6761`,`\u5c3d\u5feb\u5904\u7406\u56de\u6b3e\u548c\u7ed3\u7b97`,"\u4efb\u52a1\u8bb0\u5f55","warning");
    }
    if (warehouse) {
      add(warehouse.low_stock_count > 0,"\u5e93\u5b58\u9884\u8b66",`${warehouse.low_stock_count} \u9879`,`\u53ef\u7528\u5e93\u5b58\u5df2\u8fbe\u5230\u9884\u8b66\u503c`,"\u5e93\u5b58\u603b\u89c8","danger");
      add(warehouse.pending_outbound_count > 0,"\u5f85\u51fa\u5e93",`${warehouse.pending_outbound_count} \u5355`,`\u5c1a\u672a\u5b8c\u6210\u53d1\u8d27\u7684\u51fa\u5e93\u5355`,"\u51fa\u5e93\u53d1\u8d27","warning");
    }
    if (expenses && available.has("\u516c\u53f8\u8bb0\u8d26")) {
      const currency = (value)=>`\u00a5${Number(value || 0).toLocaleString("zh-CN",{minimumFractionDigits:2,maximumFractionDigits:2})}`;
      add(expenses.pending_approval_total > 0,"\u8bb0\u8d26\u5f85\u5ba1\u6279",currency(expenses.pending_approval_total),"\u672c\u6708\u5f85\u5ba1\u6279\u7684\u516c\u53f8\u6d88\u8d39", "\u516c\u53f8\u8bb0\u8d26","warning");
      add(expenses.pending_reimbursement_total > 0,"\u8bb0\u8d26\u5f85\u62a5\u9500",currency(expenses.pending_reimbursement_total),"\u672c\u6708\u5f85\u62a5\u9500\u7684\u516c\u53f8\u6d88\u8d39", "\u516c\u53f8\u8bb0\u8d26","primary");
    }
    appNotifications = items;
    updateNotificationBadges();
    if (currentView === "notifications" && root.classList.contains("app-native-hub-open")) renderNotifications();
  }
  function readFeatures() {
    const menu = preferredMenu();
    const seen = new Set();
    const live = menu ? Array.from(menu.querySelectorAll(".el-menu-item")).map((node) => {
      const label = (node.textContent || "").trim();
      if (!label || seen.has(label)) return null;
      seen.add(label);
      const groupNode = node.closest(".el-sub-menu");
      const groupTitle = (groupNode?.querySelector(":scope > .el-sub-menu__title")?.textContent || "").trim();
      return { label, group:standaloneGroups.get(label) || groupTitle || "\u5e38\u7528\u529f\u80fd", node };
    }).filter(Boolean) : [];
    const liveByLabel = new Map(live.map((item)=>[item.label,item]));
    const result = fixedFeatures.map((item)=>({...item,node:liveByLabel.get(item.label)?.node||null}));
    live.forEach((item)=>{if(!fixedFeatures.some((fixed)=>fixed.label===item.label))result.push(item)});
    return result.filter(canShowFeature);
  }
  function grouped(items) {
    const groups = new Map();
    items.forEach((item) => {
      const name = groupOrder.includes(item.group) ? item.group : "\u5176\u4ed6\u529f\u80fd";
      if (!groups.has(name)) groups.set(name, []);
      groups.get(name).push(item);
    });
    return groupOrder.map((name)=>[name,groups.get(name)||[]]).filter(([,items])=>items.length);
  }
  function featureButton(item) {
    return `<button type="button" class="app-native-feature" data-app-feature="${item.label}"><span class="app-native-feature-icon"><svg viewBox="0 0 24 24"><path fill="currentColor" d="${iconPath(item.label)}"/></svg></span><span>${item.label}</span></button>`;
  }
  function sections(groups) {
    if (!groups.length) return '<div class="app-native-empty">\u6682\u65e0\u529f\u80fd</div>';
    return groups.map(([name,items])=>`<section class="app-native-section"><div class="app-native-section-head"><h2>${name}</h2><span>${items.length} \u9879</span></div><div class="app-native-feature-grid">${items.map(featureButton).join("")}</div></section>`).join("");
  }
  function userName() {
    return (document.querySelector(".layout-userbar")?.textContent || "").replace(/\u5168\u5c40\u641c\u7d22/g,"").trim() || "\u7ba1\u7406\u5458";
  }
  function bindFeatures() {
    document.querySelectorAll("[data-app-feature]").forEach((button)=>{
      if (button.dataset.appFeatureBound === "1") return;
      button.dataset.appFeatureBound = "1";
      button.addEventListener("click",()=>openFeature(button.dataset.appFeature));
    });
    document.querySelector("[data-app-open-all]")?.addEventListener("click",()=>showHub("all"));
  }

  function renderHome() {
    if (!permissionsLoaded) {
      document.querySelector(".app-native-hub").innerHTML = '<div class="app-native-loading"><span></span><p>\u6b63\u5728\u52a0\u8f7d\u8d26\u53f7\u6743\u9650</p></div>';
      return;
    }
    const all = readFeatures(), byLabel = new Map(all.map((item)=>[item.label,item]));
    const items = favoriteLabels.map((label)=>byLabel.get(label)).filter(Boolean);
    const allButton = `<button type="button" class="app-native-feature" data-app-open-all><span class="app-native-feature-icon"><svg viewBox="0 0 24 24"><path fill="currentColor" d="${iconPaths.grid}"/></svg></span><span>\u5168\u90e8\u529f\u80fd</span></button>`;
    document.querySelector(".app-native-hub").innerHTML = `<section class="app-native-section app-native-section--first"><div class="app-native-section-head"><h2>\u5e38\u7528\u529f\u80fd</h2><span>${items.length + 1} \u9879</span></div><div class="app-native-feature-grid">${items.map(featureButton).join("")}${allButton}</div></section><section class="app-native-dashboard-section"><div class="app-native-section-head"><h2>\u7ecf\u8425\u6570\u636e</h2></div><div class="app-native-dashboard-host" id="appNativeDashboard"><div class="app-native-empty">\u6570\u636e\u52a0\u8f7d\u4e2d</div></div></section>`;
    bindFeatures();
    ensureDashboardRoute();
    scheduleDashboardSync();
  }
  async function ensureDashboardRoute() {
    const route = location.pathname.replace(/^\/ui/,"") || "/dashboard";
    if (route !== "/dashboard") {
      const router = vueRouter();
      if (router?.replace) { try { await router.replace("/dashboard"); } catch {} }
      else { history.replaceState(null,"","/ui/dashboard"); dispatchEvent(new PopStateEvent("popstate",{state:history.state})); }
      await nextPaint();
    }
    scheduleDashboardSync(40);
  }
  function scheduleDashboardSync(delay = 100) {
    clearTimeout(dashboardTimer);
    dashboardTimer = setTimeout(syncDashboardSnapshot,delay);
  }
  function scheduleModuleSync(delay = 100) {
    clearTimeout(moduleTimer);
    moduleTimer = setTimeout(syncAppModuleView,delay);
  }
  function prepareAppRoute(route) {
    if (!route || route.startsWith("#")) return;
    setAppRouteState(route,true);
  }
  function finishAppRoute() {
    requestAnimationFrame(()=>{
      root.classList.remove("app-route-pending");
      root.classList.add("app-route-ready");
    });
  }
  function syncGenericModuleShell(route) {
    const group = appModuleGroup(route);
    setAppRouteState(route,root.classList.contains("app-route-pending"));
    if (!group) { root.classList.remove("app-route-pending","app-route-ready"); return true; }
    const main = document.querySelector(".layout-main");
    const readySelector = appRouteReadySelectors[route];
    if (!main || (readySelector && !main.querySelector(readySelector))) { scheduleModuleSync(80); return false; }
    main.classList.add("app-module-main");
    main.querySelectorAll(":scope .filter-panel, :scope .warehouse-filter-panel").forEach((filter)=>{
      filter.dataset.appFilterReady = "1";
      filter.classList.remove("app-filter-collapsed");
      filter.classList.add("app-direct-search-panel");
      const bar = filter.previousElementSibling;
      if (bar?.classList.contains("app-module-filter-bar--generic")) bar.remove();
    });
    return true;
  }
  function syncShopRecordCards() {
    document.querySelectorAll(".layout-main .shop-card-list .shop-mobile-card").forEach((card)=>{
      const fieldsHost = card.querySelector(".shop-mobile-card__fields");
      if (!fieldsHost) return;
      const fields = Array.from(fieldsHost.children).filter((node)=>node.classList.contains("shop-mobile-card__field"));
      if (!fields.length) return;
      const title = card.querySelector(".shop-mobile-card__title")?.textContent?.trim() || "\u672a\u547d\u540d\u5e97\u94fa";
      const meta = card.querySelector(".shop-mobile-card__meta")?.textContent?.replace(/\s+/g," ").trim() || "";
      const recordFields = fields.map((field)=>({
        label:field.querySelector(".shop-mobile-card__label")?.textContent?.trim() || "\u672a\u547d\u540d\u5b57\u6bb5",
        value:field.querySelector(".shop-mobile-card__value")?.textContent?.trim() || "-"
      }));
      const signature = `${title}|${meta}|${recordFields.map((field)=>`${field.label}:${field.value}`).join("|")}`;
      const existing = Array.from(card.children).find((node)=>node.classList?.contains("app-shop-data-panel"));
      const head = card.querySelector(".shop-mobile-card__head");
      const existingDetail = head?.querySelector(".app-shop-head-detail");
      if (existing && existing.dataset.signature === signature && existingDetail) return;
      existing?.remove();
      existingDetail?.remove();
      fieldsHost.classList.add("app-shop-source-fields");
      const detailId = card.dataset.appShopDetailId || `shop-${++shopDetailSequence}`;
      card.dataset.appShopDetailId = detailId;
      shopDetailRecords.set(detailId,{id:detailId,title,meta,fields:recordFields,card});
      const metricKeywords = ["\u4fdd\u8bc1\u91d1","\u5229\u6da6","\u8425\u4e1a\u989d","\u8425\u6536","\u91d1\u989d","\u4f59\u989d","\u72b6\u6001","\u9500\u552e"];
      const longKeywords = ["\u5907\u6ce8","\u8bf4\u660e","\u5730\u5740","\u94fe\u63a5","\u539f\u56e0"];
      const sensitiveKeywords = ["\u5bc6\u7801","\u53e3\u4ee4","\u5bc6\u94a5","token","secret"];
      const metrics = recordFields.filter((field)=>metricKeywords.some((keyword)=>field.label.toLowerCase().includes(keyword))).slice(0,3);
      const previews = recordFields.filter((field)=>!metrics.includes(field) && !longKeywords.some((keyword)=>field.label.includes(keyword)) && !sensitiveKeywords.some((keyword)=>field.label.toLowerCase().includes(keyword))).slice(0,3);
      const panel = document.createElement("section");
      panel.className = "app-shop-data-panel";
      panel.dataset.signature = signature;
      panel.innerHTML = `${metrics.length?`<div class="app-shop-summary-metrics">${metrics.map((field)=>`<div><span>${escapeHtml(field.label)}</span><strong>${escapeHtml(field.value)}</strong></div>`).join("")}</div>`:""}<div class="app-shop-summary-list">${previews.map((field)=>`<div><span>${escapeHtml(field.label)}</span><strong>${escapeHtml(field.value)}</strong></div>`).join("")}</div>`;
      if (head) {
        const detailButton = document.createElement("button");
        detailButton.type = "button";
        detailButton.className = "app-shop-head-detail";
        detailButton.innerHTML = "\u8be6\u60c5 <i>\u203a</i>";
        detailButton.addEventListener("click",()=>openShopDetail(detailId));
        head.appendChild(detailButton);
      }
      fieldsHost.insertAdjacentElement("afterend",panel);
    });
  }
  function copyAppText(value,button) {
    const finish = ()=>{if(!button)return;const previous=button.textContent;button.textContent="\u5df2\u590d\u5236";setTimeout(()=>button.textContent=previous,1200)};
    if (navigator.clipboard?.writeText) navigator.clipboard.writeText(value).then(finish).catch(()=>fallbackCopy());
    else fallbackCopy();
    function fallbackCopy() {
      const input = document.createElement("textarea");
      input.value = value;
      input.style.position = "fixed";
      input.style.opacity = "0";
      document.body.appendChild(input);
      input.select();
      try { document.execCommand("copy"); finish(); } catch {}
      input.remove();
    }
  }
  function shopDetailSection(title,fields) {
    if (!fields.length) return "";
    const sensitiveKeywords = ["\u5bc6\u7801","\u53e3\u4ee4","\u5bc6\u94a5","token","secret"];
    return `<section class="app-shop-detail-section"><h2>${title}</h2><div class="app-shop-detail-list">${fields.map((field,index)=>{
      const sensitive = sensitiveKeywords.some((keyword)=>field.label.toLowerCase().includes(keyword));
      const displayValue = sensitive && field.value !== "-" ? "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022" : field.value;
      return `<div class="app-shop-detail-row"><span>${escapeHtml(field.label)}</span><div><strong data-shop-detail-value="${escapeHtml(field.value)}" data-sensitive="${sensitive?"1":"0"}">${escapeHtml(displayValue)}</strong><div class="app-shop-detail-actions">${sensitive&&field.value!=="-"?`<button type="button" data-shop-reveal="${index}">\u67e5\u770b</button>`:""}${field.value!=="-"?`<button type="button" data-shop-copy="${escapeHtml(field.value)}">\u590d\u5236</button>`:""}</div></div></div>`;
    }).join("")}</div></section>`;
  }
  function openShopDetail(detailId) {
    const record = shopDetailRecords.get(detailId);
    if (!record) return;
    currentView = "shop-detail";
    root.classList.add("app-native-hub-open","app-native-shop-detail-view");
    root.classList.remove("app-native-mine-view","app-native-settings-view","app-native-notifications-view");
    const metricKeywords = ["\u4fdd\u8bc1\u91d1","\u5229\u6da6","\u8425\u4e1a\u989d","\u8425\u6536","\u91d1\u989d","\u4f59\u989d","\u72b6\u6001","\u9500\u552e"];
    const loginKeywords = ["\u8d26\u53f7","\u7528\u6237\u540d","\u767b\u5f55","\u5bc6\u7801","\u53e3\u4ee4","\u624b\u673a","\u7535\u8bdd","\u90ae\u7bb1","\u5bc6\u94a5","token","secret"];
    const noteKeywords = ["\u5907\u6ce8","\u8bf4\u660e","\u5730\u5740","\u94fe\u63a5","\u539f\u56e0"];
    const business = [], login = [], notes = [], basics = [];
    record.fields.forEach((field)=>{
      const label = field.label.toLowerCase();
      if (metricKeywords.some((keyword)=>label.includes(keyword))) business.push(field);
      else if (loginKeywords.some((keyword)=>label.includes(keyword))) login.push(field);
      else if (noteKeywords.some((keyword)=>label.includes(keyword))) notes.push(field);
      else basics.push(field);
    });
    const status = record.fields.find((field)=>field.label.includes("\u72b6\u6001"))?.value || "\u8d44\u6599\u5df2\u5f52\u6863";
    const metricCards = business.slice(0,3).map((field)=>`<div><span>${escapeHtml(field.label)}</span><strong>${escapeHtml(field.value)}</strong></div>`).join("");
    const canEdit = Boolean(Array.from(record.card.querySelectorAll(".shop-mobile-card__actions button")).find((button)=>button.textContent.includes("\u7f16\u8f91")));
    document.querySelector(".app-native-hub").innerHTML = `<header class="app-shop-detail-head"><button type="button" data-shop-detail-back aria-label="\u8fd4\u56de"><svg viewBox="0 0 24 24"><path fill="currentColor" d="m15.4 5.4-1.4-1.4L6 12l8 8 1.4-1.4L8.8 12l6.6-6.6Z"/></svg></button><strong>\u5e97\u94fa\u8be6\u60c5</strong>${canEdit?`<button type="button" data-shop-detail-edit>\u7f16\u8f91</button>`:"<span></span>"}</header><main class="app-shop-detail-page"><section class="app-shop-detail-hero"><span>${escapeHtml(record.meta || "\u5e97\u94fa\u8d26\u53f7")}</span><h1>${escapeHtml(record.title)}</h1><em>${escapeHtml(status)}</em></section>${metricCards?`<section class="app-shop-detail-metrics">${metricCards}</section>`:""}${shopDetailSection("\u767b\u5f55\u8d44\u6599",login)}${shopDetailSection("\u57fa\u7840\u8d44\u6599",basics)}${shopDetailSection("\u7ecf\u8425\u6570\u636e",business.slice(3))}${shopDetailSection("\u5907\u6ce8\u4fe1\u606f",notes)}</main>`;
    const close = ()=>{
      root.classList.remove("app-native-hub-open","app-native-shop-detail-view");
      currentView = "module";
      updateHeader("\u5e97\u94fa\u8d26\u53f7",true);
      updateBottom("");
      scheduleModuleSync(80);
    };
    document.querySelector("[data-shop-detail-back]")?.addEventListener("click",close);
    document.querySelector("[data-shop-detail-edit]")?.addEventListener("click",()=>{
      const editButton = Array.from(record.card.querySelectorAll(".shop-mobile-card__actions button")).find((button)=>button.textContent.includes("\u7f16\u8f91"));
      close();
      setTimeout(()=>editButton?.click(),60);
    });
    document.querySelectorAll("[data-shop-copy]").forEach((button)=>button.addEventListener("click",()=>copyAppText(button.dataset.shopCopy || "",button)));
    document.querySelectorAll("[data-shop-reveal]").forEach((button)=>button.addEventListener("click",()=>{
      const valueNode = button.closest(".app-shop-detail-row")?.querySelector("[data-shop-detail-value]");
      if (!valueNode) return;
      const revealed = valueNode.dataset.revealed === "1";
      valueNode.textContent = revealed ? "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022" : valueNode.dataset.shopDetailValue;
      valueNode.dataset.revealed = revealed ? "0" : "1";
      button.textContent = revealed ? "\u67e5\u770b" : "\u9690\u85cf";
    }));
  }
  function syncAppModuleView() {
    if (root.classList.contains("app-native-hub-open")) return;
    const route = currentAppRoute();
    if (!syncGenericModuleShell(route)) return;
    syncShopRecordCards();
    syncTaskRecordModule(route);
    if (route !== "/warehouse/stock") { finishAppRoute(); return; }
    const panel = document.querySelector(".layout-main .warehouse-view-panel");
    const table = panel?.querySelector(":scope > .el-table");
    if (!panel || !table) { scheduleModuleSync(220); return; }
    const headers = Array.from(table.querySelectorAll(".el-table__header-wrapper th .cell")).map((node)=>node.textContent.trim());
    const rows = Array.from(table.querySelectorAll(".el-table__body-wrapper tbody tr"));
    const signature = rows.map((row)=>row.textContent.replace(/\s+/g," ").trim()).join("|");
    if (signature === stockSignature && panel.classList.contains("app-stock-ready")) return;
    stockSignature = signature;
    let host = panel.querySelector(":scope > .app-stock-list");
    if (!host) { host = document.createElement("div"); host.className = "app-stock-list"; table.insertAdjacentElement("afterend",host); }
    const indexOf = (keyword)=>headers.findIndex((label)=>label.includes(keyword));
    const indexes = {warehouse:indexOf("\u4ed3\u5e93"),sku:indexOf("SKU"),name:indexOf("\u5546\u54c1\u540d\u79f0"),spec:indexOf("\u89c4\u683c"),total:indexOf("\u5b9e\u9645\u5e93\u5b58"),locked:indexOf("\u5df2\u9501\u5b9a"),available:indexOf("\u53ef\u7528\u5e93\u5b58"),cost:indexOf("\u6210\u672c\u4ef7"),status:indexOf("\u72b6\u6001")};
    host.innerHTML = rows.length ? rows.map((row)=>{
      const cells = Array.from(row.querySelectorAll("td .cell"));
      const text = (index)=>index >= 0 ? (cells[index]?.textContent || "").replace(/\s+/g," ").trim() : "";
      const image = cells[0]?.querySelector("img")?.src || "";
      const status = text(indexes.status);
      return `<article class="app-stock-row"><div class="app-stock-image">${image?`<img src="${escapeHtml(image)}" alt="">`:'<span>\u8d27</span>'}</div><div class="app-stock-main"><div class="app-stock-title"><strong>${escapeHtml(text(indexes.name) || text(indexes.sku) || "\u672a\u547d\u540d\u5546\u54c1")}</strong><em class="${status.includes("\u4e0d\u8db3")?"is-danger":""}">${escapeHtml(status || "\u6b63\u5e38")}</em></div><p>${escapeHtml([text(indexes.sku),text(indexes.warehouse),text(indexes.spec)].filter(Boolean).join(" \u00b7 "))}</p><div class="app-stock-values"><span><small>\u53ef\u7528</small><b>${escapeHtml(text(indexes.available) || "0")}</b></span><span><small>\u5b9e\u9645</small><b>${escapeHtml(text(indexes.total) || "0")}</b></span><span><small>\u9501\u5b9a</small><b>${escapeHtml(text(indexes.locked) || "0")}</b></span><span><small>\u6210\u672c</small><b>${escapeHtml(text(indexes.cost) || "\u00a50.00")}</b></span></div></div></article>`;
    }).join("") : '<div class="app-native-empty">\u6682\u65e0\u5e93\u5b58\u5546\u54c1</div>';
    panel.classList.add("app-stock-ready");
    finishAppRoute();
  }
  function syncTaskRecordModule(route) {
    const active = route === "/task-bookkeeping/records";
    root.classList.toggle("app-task-records-route",active);
    if (!active) return;
    const filter = document.querySelector(".layout-main .task-filter-shell");
    if (!filter) { scheduleModuleSync(220); return; }
    const bar = filter.previousElementSibling;
    if (bar?.classList.contains("app-module-filter-bar")) bar.remove();
    filter.classList.remove("app-filter-collapsed");
    filter.classList.add("app-direct-search-panel");
  }
  function syncDashboardSnapshot() {
    if (currentView !== "home" || !root.classList.contains("app-native-hub-open")) return;
    const host = document.getElementById("appNativeDashboard");
    const source = document.querySelector(".layout-main .dashboard-surface");
    if (!host || !source) { scheduleDashboardSync(240); return; }
    const signature = source.innerHTML;
    if (signature === dashboardSignature && host.querySelector(".app-data-carousel")) return;
    dashboardSignature = signature;
    const clean = (value)=>String(value || "").replace(/\s+/g," ").trim();
    const escape = (value)=>escapeHtml(clean(value));
    const collect = (selector,labelSelector,valueSelector,noteSelector)=>Array.from(source.querySelectorAll(selector)).map((node)=>({
      label:clean(node.querySelector(labelSelector)?.textContent),
      value:clean(node.querySelector(valueSelector)?.textContent),
      note:clean(node.querySelector(noteSelector)?.textContent)
    })).filter((item)=>item.label && item.value);
    const metrics = collect(".dashboard-metric-card",".metric-label",".metric-value",".metric-note");
    const warehouse = collect(".warehouse-dashboard-shell .reminder-card",".reminder-card__title",".reminder-card__value",".reminder-card__note");
    const reminders = collect(".reminder-shell .reminder-card",".reminder-card__title",".reminder-card__value",".reminder-card__note");
    const server = Array.from(source.querySelectorAll(".server-metric-card")).map((node)=>({label:clean(node.querySelector("span")?.textContent),value:clean(node.querySelector("strong")?.textContent),note:clean(node.querySelector("small")?.textContent)})).filter((item)=>item.label && item.value);
    const rows = (items,group)=>items.map((item)=>`<button type="button" class="app-data-row" data-app-data-target="${group}"><span><strong>${escape(item.label)}</strong><small>${escape(item.note)}</small></span><b>${escape(item.value)}</b><i>\u203a</i></button>`).join("");
    const renderSlide = (title,items,target="",overview=false)=>`<section class="app-data-slide${overview?" app-data-slide--overview":""}"><div class="app-data-slide-head"><strong>${title}</strong>${target?`<button type="button" data-app-data-target="${target}" aria-label="\u67e5\u770b${title}">\u203a</button>`:""}</div><div class="app-data-matrix">${items.map((item)=>`<div class="app-data-cell"><span>${escape(item.label)}</span><strong>${escape(item.value)}</strong>${item.note?`<small>${escape(item.note)}</small>`:""}</div>`).join("")}</div></section>`;
    const slides = [metrics.length?renderSlide("\u7ecf\u8425\u6982\u89c8",metrics,"",true):"",warehouse.length?renderSlide("\u4ed3\u50a8\u6570\u636e",warehouse,"warehouse"):"",reminders.length?renderSlide("\u5f85\u529e\u63d0\u9192",reminders):""].filter(Boolean);
    const carousel = slides.length ? `<section class="app-data-carousel"><div class="app-data-track">${slides.join("")}</div><div class="app-data-dots">${slides.map((_,index)=>`<i class="${index===0?"is-active":""}"></i>`).join("")}</div></section>` : '<div class="app-native-empty">\u6682\u65e0\u7ecf\u8425\u6570\u636e</div>';
    const profitChart = renderProfitChart(source,escape);
    const groups = [
      server.length ? `<section class="app-data-group"><div class="app-data-group-head"><h3>\u8fd0\u884c\u72b6\u6001</h3><button type="button" data-app-data-target="server">\u8be6\u60c5</button></div><div class="app-data-list">${rows(server,"server")}</div></section>` : ""
    ].join("");
    host.innerHTML = `${carousel}${profitChart}${groups}`;
    bindFeatures();
    const track = host.querySelector(".app-data-track");
    const dots = Array.from(host.querySelectorAll(".app-data-dots i"));
    let slideFrame = 0;
    track?.addEventListener("scroll",()=>{cancelAnimationFrame(slideFrame);slideFrame=requestAnimationFrame(()=>{const index=Math.max(0,Math.min(dots.length-1,Math.round(track.scrollLeft/Math.max(1,track.clientWidth))));dots.forEach((dot,dotIndex)=>dot.classList.toggle("is-active",dotIndex===index))})},{passive:true});
    host.querySelectorAll("[data-app-data-target]").forEach((button)=>button.addEventListener("click",()=>{
      const target = button.dataset.appDataTarget;
      if (target === "warehouse") openFeature("\u5e93\u5b58\u603b\u89c8");
      else if (target === "server") openFeature("\u670d\u52a1\u5668\u8fd0\u884c");
    }));
  }
  function renderProfitChart(source,escape) {
    const table = source.querySelector(".summary-shell .el-table") || source.querySelector(".summary-table");
    if (!table) return "";
    const headers = Array.from(table.querySelectorAll(".el-table__header-wrapper th .cell")).map((node)=>node.textContent.trim());
    const monthIndex = headers.findIndex((label)=>label.includes("\u6708\u4efd"));
    const profitIndex = headers.findIndex((label)=>label.includes("\u603b\u5229\u6da6"));
    if (monthIndex < 0 || profitIndex < 0) return "";
    const data = Array.from(table.querySelectorAll(".el-table__body-wrapper tbody tr")).map((row)=>{
      const cells = Array.from(row.querySelectorAll("td .cell")).map((node)=>node.textContent.trim());
      return {month:cells[monthIndex] || "",value:Number(String(cells[profitIndex] || "0").replace(/[^0-9.-]/g,"")) || 0};
    }).filter((item)=>item.month).slice(0,6).reverse();
    if (!data.length) return "";
    const width = 320, height = 132, left = 12, right = 12, top = 27, bottom = 22;
    const values = data.map((item)=>item.value), min = Math.min(0,...values), max = Math.max(1,...values), range = Math.max(1,max-min);
    const points = data.map((item,index)=>({x:left+(data.length===1?(width-left-right)/2:index*(width-left-right)/(data.length-1)),y:top+(max-item.value)*(height-top-bottom)/range,...item}));
    const line = points.map((point,index)=>`${index?"L":"M"}${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(" ");
    const area = `${line} L${points[points.length-1].x.toFixed(1)} ${height-bottom} L${points[0].x.toFixed(1)} ${height-bottom} Z`;
    const labels = points.map((point)=>`<text x="${point.x.toFixed(1)}" y="${height-5}" text-anchor="middle">${escape(point.month.replace(/^\d{4}[-/]/,""))}</text>`).join("");
    const compactProfit = (value)=>{
      const absolute = Math.abs(value);
      if (absolute >= 10000) return `${(value/10000).toFixed(1)}\u4e07`;
      if (absolute >= 1000) return `${(value/1000).toFixed(1)}k`;
      return value.toFixed(0);
    };
    const valueLabels = points.map((point)=>`<text class="app-profit-value" x="${point.x.toFixed(1)}" y="${Math.max(11,point.y-8).toFixed(1)}" text-anchor="middle">\u00a5${escape(compactProfit(point.value))}</text>`).join("");
    const dots = points.map((point)=>`<circle cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="3"/>`).join("");
    const total = values.reduce((sum,value)=>sum+value,0);
    return `<section class="app-profit-chart"><div class="app-data-group-head"><h3>\u9489\u9489\u5229\u6da6\u8d8b\u52bf</h3><button type="button" data-app-feature="\u9489\u9489\u5229\u6da6">\u67e5\u770b\u8be6\u60c5</button></div><div class="app-profit-chart-head"><span>\u8fd1 ${data.length} \u4e2a\u6708\u00b7\u6bcf\u70b9\u4e3a\u5f53\u6708\u5229\u6da6</span><strong>\u00a5${total.toLocaleString("zh-CN",{minimumFractionDigits:2,maximumFractionDigits:2})}</strong></div><svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet"><path class="app-profit-area" d="${area}"/><path class="app-profit-line" d="${line}"/>${dots}${valueLabels}${labels}</svg></section>`;
  }
  function renderAll(filter = "") {
    const all = readFeatures();
    const key = filter.trim().toLowerCase();
    const items = key ? all.filter((item)=>item.label.toLowerCase().includes(key)) : all;
    document.querySelector(".app-native-hub").innerHTML = `<div class="app-native-all-summary"><strong>\u5168\u90e8\u529f\u80fd</strong><span>${items.length} \u9879</span></div><label class="app-native-search"><svg viewBox="0 0 24 24"><path fill="currentColor" d="m21 19.6-4.7-4.7a7.5 7.5 0 1 0-1.4 1.4l4.7 4.7 1.4-1.4ZM5 10.5a5.5 5.5 0 1 1 11 0 5.5 5.5 0 0 1-11 0Z"/></svg><input id="appNativeSearch" type="search" value="${filter.replace(/"/g,"&quot;")}" placeholder="\u641c\u7d22\u5168\u90e8\u529f\u80fd"></label>${sections(grouped(items))}`;
    bindFeatures();
    const input = document.getElementById("appNativeSearch");
    input?.addEventListener("input",()=>renderAll(input.value));
    if (key) { input?.focus({preventScroll:true}); input?.setSelectionRange(input.value.length,input.value.length); }
  }
  function renderTask() {
    const items = readFeatures().filter((item)=>taskLabels.has(item.label));
    document.querySelector(".app-native-hub").innerHTML = sections([["\u4efb\u52a1\u529f\u80fd",items]]);
    bindFeatures();
  }
  function profileAvatarMarkup(name,className="app-mine-avatar") {
    const image = accessUser?.avatar_url ? `<img src="${escapeHtml(accessUser.avatar_url)}" alt="${escapeHtml(name)}">` : "";
    return `<div class="${className}"><span>${escapeHtml(name.slice(0,2))}</span>${image}</div>`;
  }
  function accountRows(items) {
    if (!items.length) return "";
    return `<section class="app-mine-menu">${items.map((item)=>`<button type="button" data-app-feature="${escapeHtml(item.label)}"><span class="app-mine-menu-icon"><svg viewBox="0 0 24 24"><path fill="currentColor" d="${iconPath(item.label)}"/></svg></span><strong>${escapeHtml(item.label)}</strong><i>\u203a</i></button>`).join("")}</section>`;
  }
  function notificationButtonMarkup(className="app-native-head-action") {
    return `<button type="button" class="${className} app-notification-button" data-app-notifications aria-label="\u901a\u77e5"><svg viewBox="0 0 24 24"><path fill="currentColor" d="M12 22a2.4 2.4 0 0 0 2.3-2h-4.6a2.4 2.4 0 0 0 2.3 2Zm7-6v-5a7 7 0 0 0-5.5-6.8V3a1.5 1.5 0 0 0-3 0v1.2A7 7 0 0 0 5 11v5l-2 2v1h18v-1l-2-2ZM7 17v-6a5 5 0 0 1 10 0v6H7Z"/></svg><span class="app-notification-badge" hidden>0</span></button>`;
  }
  function bindNotificationButtons(scope=document) {
    scope.querySelectorAll("[data-app-notifications]").forEach((button)=>{
      if (button.dataset.notificationBound === "1") return;
      button.dataset.notificationBound = "1";
      button.addEventListener("click",()=>{if(currentView !== "notifications")notificationReturnView=currentView;showHub("notifications")});
    });
    updateNotificationBadges();
  }
  function renderNotifications(markRead=true) {
    if (markRead) markNotificationsRead();
    const list = appNotifications.length ? appNotifications.map((item)=>`<button type="button" class="app-notification-row app-notification-row--${item.tone}" data-notification-target="${escapeHtml(item.target || "")}"><span class="app-notification-icon"><i></i></span><span><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.note)}</small></span><b>${escapeHtml(item.value)}</b><em>\u203a</em></button>`).join("") : `<div class="app-notification-empty"><svg viewBox="0 0 24 24"><path fill="currentColor" d="M12 22a2.4 2.4 0 0 0 2.3-2h-4.6a2.4 2.4 0 0 0 2.3 2Zm7-6v-5a7 7 0 0 0-5.5-6.8V3a1.5 1.5 0 0 0-3 0v1.2A7 7 0 0 0 5 11v5l-2 2v1h18v-1l-2-2ZM7 17v-6a5 5 0 0 1 10 0v6H7Z"/></svg><strong>\u6682\u65e0\u65b0\u901a\u77e5</strong><span>\u4efb\u52a1\u3001\u5e93\u5b58\u548c\u8bb0\u8d26\u63d0\u9192\u4f1a\u663e\u793a\u5728\u8fd9\u91cc</span></div>`;
    document.querySelector(".app-native-hub").innerHTML = `<header class="app-notifications-head"><button type="button" data-notifications-back aria-label="\u8fd4\u56de"><svg viewBox="0 0 24 24"><path fill="currentColor" d="m15.4 5.4-1.4-1.4L6 12l8 8 1.4-1.4L8.8 12l6.6-6.6Z"/></svg></button><strong>\u901a\u77e5</strong><button type="button" data-notifications-refresh>\u5237\u65b0</button></header><div class="app-notification-summary"><strong>${appNotifications.length}</strong><span>\u5f53\u524d\u63d0\u9192</span></div><section class="app-notification-list">${list}</section>`;
    document.querySelector("[data-notifications-back]")?.addEventListener("click",()=>showHub(notificationReturnView === "notifications" ? "home" : notificationReturnView));
    document.querySelector("[data-notifications-refresh]")?.addEventListener("click",async (event)=>{event.currentTarget.disabled=true;await loadAppNotifications();event.currentTarget.disabled=false});
    document.querySelectorAll("[data-notification-target]").forEach((button)=>button.addEventListener("click",()=>{const target=button.dataset.notificationTarget;if(target)openFeature(target)}));
  }
  function renderMine() {
    const items = readFeatures().filter((item)=>mineLabels.has(item.label));
    const name = accessUser?.display_name || accessUser?.username || userName();
    const role = accessUser?.role === "superadmin" ? "\u8d85\u7ea7\u7ba1\u7406\u5458" : "\u5f53\u524d\u8d26\u53f7";
    const permissionCount = Object.values(accessUser?.permissions || {}).filter((level)=>level === "read" || level === "write").length;
    const featureCount = readFeatures().length;
    document.querySelector(".app-native-hub").innerHTML = `<section class="app-mine-hero"><div class="app-mine-toolbar"><strong>\u4e2a\u4eba\u4e2d\u5fc3</strong><div><button type="button" data-mine-theme aria-label="\u5207\u6362\u591c\u89c8\u6a21\u5f0f"><svg viewBox="0 0 24 24"><path fill="currentColor" d="M20.5 15.4A8.5 8.5 0 0 1 8.6 3.5 9 9 0 1 0 20.5 15.4Z"/></svg></button><button type="button" data-mine-settings aria-label="\u8bbe\u7f6e"><svg viewBox="0 0 24 24"><path fill="currentColor" d="M19.4 13a7.8 7.8 0 0 0 .1-1 7.8 7.8 0 0 0-.1-1l2.1-1.6-2-3.4-2.5 1a7.5 7.5 0 0 0-1.7-1L15 3.3h-4L10.6 6a7.5 7.5 0 0 0-1.7 1L6.4 6l-2 3.4L6.5 11a7.8 7.8 0 0 0-.1 1 7.8 7.8 0 0 0 .1 1l-2.1 1.6 2 3.4 2.5-1a7.5 7.5 0 0 0 1.7 1l.4 2.7h4l.4-2.7a7.5 7.5 0 0 0 1.7-1l2.5 1 2-3.4-2.2-1.6ZM13 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7Z"/></svg></button></div></div><div class="app-mine-identity">${profileAvatarMarkup(name)}<div><h1>${escapeHtml(name)}</h1><span>${role}</span><p>${escapeHtml(accessUser?.username || "\u5df2\u767b\u5f55\u8d26\u53f7")}</p></div></div><div class="app-mine-stats"><div><strong>${featureCount}</strong><span>\u53ef\u7528\u529f\u80fd</span></div><div><strong>${permissionCount}</strong><span>\u6388\u6743\u6a21\u5757</span></div><div><strong>${accessUser?.role === "superadmin" ? "\u8d85\u7ea7" : "\u666e\u901a"}</strong><span>\u8d26\u53f7\u8eab\u4efd</span></div></div></section><div class="app-mine-content"><section class="app-mine-section-title"><strong>\u8d26\u53f7\u4e0e\u7cfb\u7edf</strong><span>${items.length} \u9879</span></section>${accountRows(items)}<button type="button" class="app-mine-settings-entry" data-mine-settings><span><strong>\u8bbe\u7f6e</strong><small>\u68c0\u67e5\u66f4\u65b0\u4e0e\u9000\u51fa\u767b\u5f55</small></span><i>\u203a</i></button></div>`;
    document.querySelector("[data-mine-theme]")?.addEventListener("click",toggleTheme);
    const mineActions = document.querySelector(".app-mine-toolbar>div");
    const settingsButton = mineActions?.querySelector("[data-mine-settings]");
    if (mineActions && settingsButton) settingsButton.insertAdjacentHTML("beforebegin",notificationButtonMarkup(""));
    document.querySelectorAll("[data-mine-settings]").forEach((button)=>button.addEventListener("click",()=>showHub("settings")));
    bindNotificationButtons(document.querySelector(".app-native-hub"));
    bindFeatures();
  }
  function renderSettings() {
    document.querySelector(".app-native-hub").innerHTML = `<header class="app-settings-head"><button type="button" data-settings-back aria-label="\u8fd4\u56de"><svg viewBox="0 0 24 24"><path fill="currentColor" d="m15.4 5.4-1.4-1.4L6 12l8 8 1.4-1.4L8.8 12l6.6-6.6Z"/></svg></button><strong>\u8bbe\u7f6e</strong><span></span></header><section class="app-settings-list"><button type="button" data-settings-update><span><strong>\u68c0\u67e5\u66f4\u65b0</strong><small>App \u7248\u672c 0.0.13</small></span><b>\u5df2\u662f\u6700\u65b0</b></button><button type="button" class="app-settings-logout" data-app-logout><span><strong>\u9000\u51fa\u767b\u5f55</strong><small>\u9000\u51fa\u5f53\u524d\u8d26\u53f7</small></span></button></section>`;
    document.querySelector("[data-settings-back]")?.addEventListener("click",()=>showHub("mine"));
    document.querySelector("[data-app-logout]")?.addEventListener("click",logoutAccount);
    document.querySelector("[data-settings-update]")?.addEventListener("click",(event)=>{const text=event.currentTarget.querySelector("b");if(text)text.textContent="\u5f53\u524d\u5df2\u662f\u6700\u65b0\u7248\u672c"});
  }
  async function logoutAccount() {
    const button = document.querySelector("[data-app-logout]");
    if (button) { button.disabled = true; button.querySelector("strong").textContent = "\u6b63\u5728\u9000\u51fa"; }
    try { await fetch("/auth/logout",{method:"POST",credentials:"same-origin"}); } catch {}
    location.replace("/ui/login");
  }
  function updateHeader(title,modulePage) {
    const titleNode = document.querySelector(".app-native-title strong");
    const subtitle = document.querySelector(".app-native-title span");
    const back = document.querySelector(".app-native-back");
    const subtitleText = modulePage ? "\u8fd4\u56de\u4e0a\u4e00\u7ea7" : "\u624b\u673a\u4e13\u5c5e\u5e03\u5c40";
    if (titleNode && titleNode.textContent !== title) titleNode.textContent = title;
    if (subtitle && subtitle.textContent !== subtitleText) subtitle.textContent = subtitleText;
    if (back && back.hidden === modulePage) back.hidden = !modulePage;
  }
  function visibleAppLayer() {
    return Array.from(document.querySelectorAll(".el-overlay")).reverse().find((overlay)=>{
      if (getComputedStyle(overlay).display === "none") return false;
      return overlay.querySelector(".el-dialog, .el-drawer");
    }) || null;
  }
  function restoreRouteHeader() {
    const route = currentAppRoute();
    const feature = fixedFeatures.find((item)=>item.route===route);
    if (feature) updateHeader(feature.label,true);
  }
  function syncAppLayerState() {
    const layer = visibleAppLayer();
    const wasOpen = root.classList.contains("app-form-layer-open");
    root.classList.toggle("app-form-layer-open",Boolean(layer));
    root.classList.remove("app-task-form-layer","app-shop-form-layer","app-warehouse-form-layer");
    if (layer) {
      const title = layer.querySelector(".el-dialog__title, .el-drawer__title")?.textContent?.replace(/\s+/g," ").trim();
      if (/\u4efb\u52a1\u8bb0\u5f55|\u4efb\u52a1/.test(title || "")) root.classList.add("app-task-form-layer");
      else if (/\u5e97\u94fa|\u53f0\u8d26|\u6267\u7167|\u8d26\u53f7/.test(title || "")) root.classList.add("app-shop-form-layer");
      else if (/\u5e93\u5b58|\u5165\u5e93|\u51fa\u5e93|\u4ed3\u5e93|\u5546\u54c1/.test(title || "")) root.classList.add("app-warehouse-form-layer");
      if (title) updateHeader(title,true);
    } else if (wasOpen && !root.classList.contains("app-native-hub-open")) restoreRouteHeader();
  }
  function closeVisibleAppLayer() {
    const layer = visibleAppLayer();
    if (!layer) return false;
    const closeButton = layer.querySelector(".el-dialog__headerbtn, .el-drawer__close-btn");
    if (closeButton) closeButton.click();
    else {
      const cancel = Array.from(layer.querySelectorAll("button")).find((button)=>/[\u53d6\u6d88\u5173\u95ed\u8fd4\u56de]/.test(button.textContent || ""));
      if (cancel) cancel.click();
      else document.dispatchEvent(new KeyboardEvent("keydown",{key:"Escape",code:"Escape",bubbles:true}));
    }
    return true;
  }
  function handleAppBack() {
    if (closeVisibleAppLayer()) return;
    if (root.classList.contains("app-native-hub-open")) {
      if (currentView === "settings") showHub("mine");
      else if (currentView !== "home") showHub("home");
      return;
    }
    const group = appModuleGroup(currentAppRoute());
    if (group === "bookkeeping") showHub("task");
    else showHub("all");
  }
  function updateBottom(active) {
    document.querySelectorAll(".app-native-nav-item").forEach((button)=>button.classList.toggle("is-active",button.dataset.appNativeNav===active));
  }
  function showHub(view) {
    currentView = view;
    root.classList.add("app-native-hub-open");
    root.classList.remove("app-native-shop-detail-view");
    root.classList.toggle("app-native-mine-view",view === "mine");
    root.classList.toggle("app-native-settings-view",view === "settings");
    root.classList.toggle("app-native-notifications-view",view === "notifications");
    if (location.hash === "#company-expenses") {
      history.replaceState(null,"",location.pathname+location.search);
      dispatchEvent(new HashChangeEvent("hashchange"));
    }
    if (view === "all") { renderAll(); updateHeader("\u5168\u90e8\u529f\u80fd",true); updateBottom("home"); }
    else if (view === "task") { renderTask(); updateHeader("\u4efb\u52a1\u4e2d\u5fc3",false); updateBottom("task"); }
    else if (view === "mine") { renderMine(); updateHeader("\u6211\u7684",false); updateBottom("mine"); }
    else if (view === "settings") { renderSettings(); updateBottom("mine"); }
    else if (view === "notifications") { renderNotifications(); updateBottom(""); }
    else { renderHome(); updateHeader("\u9996\u9875",false); updateBottom("home"); }
  }
  function vueRouter() {
    return document.getElementById("app")?.__vue_app__?.config?.globalProperties?.$router || null;
  }
  function nextPaint() {
    return new Promise((resolve)=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
  }
  async function clickFeature(label) {
    const feature = readFeatures().find((entry)=>entry.label===label);
    if (!feature) return false;
    if (feature.node) {
      feature.node.click();
      await nextPaint();
    } else if (feature.route?.startsWith("#")) {
      if (location.hash !== feature.route) location.hash = feature.route.slice(1);
      else dispatchEvent(new HashChangeEvent("hashchange"));
      await nextPaint();
    } else if (feature.route) {
      prepareAppRoute(feature.route);
      const router = vueRouter();
      if (router?.push) {
        try { await router.push(feature.route); } catch {}
      } else {
        history.pushState(null,"",`/ui${feature.route}`);
        dispatchEvent(new PopStateEvent("popstate",{state:history.state}));
      }
      await nextPaint();
    }
    return true;
  }
  async function openFeature(label) {
    normalizeAppViewport();
    scrollTo({top:0,left:0,behavior:"auto"});
    if (label === "\u8fd0\u8425\u5de5\u4f5c\u53f0") {
      showHub("home");
      setTimeout(()=>document.querySelector(".app-native-dashboard-section")?.scrollIntoView({behavior:"smooth",block:"start"}),80);
      return;
    }
    if (label === "\u516c\u53f8\u8bb0\u8d26") {
      directExpenseOpening = false;
      updateHeader(label,true); updateBottom("task");
      if (location.hash !== "#company-expenses") location.hash = "company-expenses";
      else dispatchEvent(new HashChangeEvent("hashchange"));
      return;
    }
    const feature = readFeatures().find((entry)=>entry.label===label);
    if (feature?.route) prepareAppRoute(feature.route);
    root.classList.remove("app-native-mine-view","app-native-settings-view","app-native-notifications-view");
    if (location.hash && !feature?.route?.startsWith("#")) history.replaceState(null,"",location.pathname+location.search);
    updateHeader(label,true);
    updateBottom(label === "\u94fe\u63a5\u5e7f\u573a" ? "links" : taskLabels.has(label) ? "task" : "");
    await clickFeature(label);
    root.classList.remove("app-native-hub-open");
  }
  function openExpenseEntry() {
    directExpenseOpening = true;
    sessionStorage.setItem("company-expense-direct-entry","1");
    updateHeader("\u65b0\u589e\u8bb0\u8d26",true);
    updateBottom("task");
    root.classList.remove("app-native-hub-open");
    root.classList.remove("app-native-mine-view","app-native-settings-view","app-native-notifications-view");
    document.querySelector(".app-expense-launcher")?.remove();
    const launcher = document.createElement("div");
    launcher.className = "app-expense-launcher";
    launcher.innerHTML = '<div class="app-native-loading"><span></span><p>\u6b63\u5728\u6253\u5f00\u8bb0\u8d26</p></div>';
    document.body.appendChild(launcher);
    if (location.hash !== "#company-expenses") location.hash = "company-expenses";
    else dispatchEvent(new HashChangeEvent("hashchange"));
    let attempts = 0;
    const timer = setInterval(()=>{
      attempts += 1;
      const frame = document.querySelector("[data-company-expense-panel] iframe");
      frame?.contentWindow?.postMessage({type:"company-expense-open-entry"},location.origin);
      try {
        if (frame?.contentDocument?.body?.classList.contains("entry-page-open")) {
          launcher.remove();
          clearInterval(timer);
          return;
        }
      } catch {}
      if (attempts > 40) { launcher.remove(); clearInterval(timer); }
    },100);
  }
  function toggleTheme() {
    const enabled = localStorage.getItem("site-night-mode") !== "1";
    localStorage.setItem("site-night-mode",enabled?"1":"0");
    root.classList.toggle("site-night-mode",enabled);
    updateThemeButton();
  }
  function updateThemeButton() {
    const button = document.querySelector("[data-app-theme]");
    if (!button) return;
    const night = root.classList.contains("site-night-mode");
    button.setAttribute("aria-label",night ? "\u5207\u6362\u65e5\u95f4\u6a21\u5f0f" : "\u5207\u6362\u591c\u89c8\u6a21\u5f0f");
    button.innerHTML = night ? '<svg viewBox="0 0 24 24"><path fill="currentColor" d="M12 4V1h1v3h-1Zm0 19v-3h1v3h-1ZM4 13H1v-1h3v1Zm19 0h-3v-1h3v1ZM5.6 6.3 3.5 4.2l.7-.7 2.1 2.1-.7.7Zm13.4 13.4-2.1-2.1.7-.7 2.1 2.1-.7.7ZM18.4 6.3l-.7-.7 2.1-2.1.7.7-2.1 2.1ZM4.2 20.5l-.7-.7 2.1-2.1.7.7-2.1 2.1ZM12.5 6a6.5 6.5 0 1 1 0 13 6.5 6.5 0 0 1 0-13Z"/></svg>' : '<svg viewBox="0 0 24 24"><path fill="currentColor" d="M20.5 15.4A8.5 8.5 0 0 1 8.6 3.5 9 9 0 1 0 20.5 15.4Z"/></svg>';
  }

  function installShell() {
    if (document.querySelector(".app-native-header") || !document.querySelector(".layout-content-shell")) return false;
    document.querySelector(".app-global-bottom-nav")?.remove();
    document.querySelector(".app-more-backdrop")?.remove();
    const header = document.createElement("header");
    header.className = "app-native-header";
    header.innerHTML = `<button type="button" class="app-native-back" hidden aria-label="\u8fd4\u56de\u4e0a\u4e00\u7ea7"><svg viewBox="0 0 24 24"><path fill="currentColor" d="m15.4 5.4-1.4-1.4L6 12l8 8 1.4-1.4L8.8 12l6.6-6.6Z"/></svg></button><div class="app-native-title"><strong>\u9996\u9875</strong><span>\u624b\u673a\u4e13\u5c5e\u5e03\u5c40</span></div><div class="app-native-head-actions"><button type="button" class="app-native-head-action" data-app-theme aria-label="\u5207\u6362\u591c\u89c8\u6a21\u5f0f"></button><button type="button" class="app-native-head-action" data-app-search aria-label="\u641c\u7d22"><svg viewBox="0 0 24 24"><path fill="currentColor" d="m21 19.6-4.7-4.7a7.5 7.5 0 1 0-1.4 1.4l4.7 4.7 1.4-1.4ZM5 10.5a5.5 5.5 0 1 1 11 0 5.5 5.5 0 0 1-11 0Z"/></svg></button><button type="button" class="app-native-avatar" data-app-profile>${userName().slice(0,2)}</button></div>`;
    const searchButton = header.querySelector("[data-app-search]");
    searchButton?.insertAdjacentHTML("beforebegin",notificationButtonMarkup());
    header.querySelector("[data-app-profile]")?.remove();
    const hub = document.createElement("main");
    hub.className = "app-native-hub";
    const bottom = document.createElement("nav");
    bottom.className = "app-native-bottom";
    bottom.innerHTML = `<button type="button" class="app-native-nav-item is-active" data-app-native-nav="home"><svg viewBox="0 0 24 24"><path fill="currentColor" d="M3 11.2 12 3l9 8.2v9.3a.5.5 0 0 1-.5.5H15v-6H9v6H3.5a.5.5 0 0 1-.5-.5v-9.3Z"/></svg><span>\u9996\u9875</span></button><button type="button" class="app-native-nav-item" data-app-native-nav="task"><svg viewBox="0 0 24 24"><path fill="currentColor" d="${iconPaths.record}"/></svg><span>\u4efb\u52a1</span></button><button type="button" class="app-native-add" data-app-native-add aria-label="\u65b0\u589e\u8bb0\u8d26">+</button><button type="button" class="app-native-nav-item" data-app-native-nav="links"><svg viewBox="0 0 24 24"><path fill="currentColor" d="M8.7 15.3a1 1 0 0 1 0-1.4l5.2-5.2a4 4 0 1 1 5.7 5.6l-3.1 3.1a4 4 0 0 1-5.7 0l1.4-1.4a2 2 0 0 0 2.9 0l3.1-3.1a2 2 0 1 0-2.9-2.8l-5.2 5.2a1 1 0 0 1-1.4 0Z"/></svg><span>\u94fe\u63a5</span></button><button type="button" class="app-native-nav-item" data-app-native-nav="mine"><svg viewBox="0 0 24 24"><path fill="currentColor" d="${iconPaths.user}"/></svg><span>\u6211\u7684</span></button>`;
    document.body.append(header,hub,bottom);
    header.querySelector(".app-native-back").addEventListener("click",handleAppBack);
    header.querySelector("[data-app-theme]").addEventListener("click",toggleTheme);
    header.querySelector("[data-app-search]").addEventListener("click",()=>{showHub("all");setTimeout(()=>document.getElementById("appNativeSearch")?.focus(),30)});
    header.querySelector("[data-app-profile]")?.addEventListener("click",()=>showHub("mine"));
    bindNotificationButtons(header);
    bottom.querySelector('[data-app-native-nav="home"]').addEventListener("click",()=>showHub("home"));
    bottom.querySelector('[data-app-native-nav="task"]').addEventListener("click",()=>showHub("task"));
    bottom.querySelector("[data-app-native-add]").addEventListener("click",openExpenseEntry);
    bottom.querySelector('[data-app-native-nav="links"]').addEventListener("click",()=>openFeature("\u94fe\u63a5\u5e7f\u573a"));
    bottom.querySelector('[data-app-native-nav="mine"]').addEventListener("click",()=>showHub("mine"));
    updateThemeButton();
    normalizeAppViewport();
    loadAccess();
    clearInterval(notificationTimer);
    notificationTimer = setInterval(loadAppNotifications,60000);
    const route = location.pathname.replace(/^\/ui/,"") || "/dashboard";
    const current = fixedFeatures.find((item)=>item.route===route);
    if (location.hash === "#company-expenses") { root.classList.remove("app-native-hub-open"); updateHeader("\u516c\u53f8\u8bb0\u8d26",true); updateBottom("task"); }
    else if (location.hash === "#knowledge") { root.classList.remove("app-native-hub-open"); updateHeader("\u77e5\u8bc6\u5e93",true); updateBottom(""); }
    else if (current && route !== "/dashboard") { root.classList.remove("app-native-hub-open"); updateHeader(current.label,true); updateBottom(current.label === "\u94fe\u63a5\u5e7f\u573a" ? "links" : taskLabels.has(current.label) ? "task" : ""); }
    else showHub("home");
    menuSignature = readFeatures().map((item)=>`${item.group}:${item.label}`).join("|");
    return true;
  }
  function refreshFeatures() {
    if (!document.querySelector(".app-native-header")) { installShell(); return; }
    const next = readFeatures().map((item)=>`${item.group}:${item.label}`).join("|");
    if (!next || next === menuSignature) return;
    menuSignature = next;
    if (!root.classList.contains("app-native-hub-open") || document.activeElement?.id === "appNativeSearch") return;
    if (currentView === "all") renderAll(); else if (currentView === "task") renderTask(); else if (currentView === "mine") renderMine(); else if (currentView === "settings") renderSettings(); else if (currentView === "notifications") renderNotifications(false); else if (currentView !== "shop-detail") renderHome();
  }
  new MutationObserver(()=>{clearTimeout(refreshTimer);refreshTimer=setTimeout(refreshFeatures,80);if(currentView==="home")scheduleDashboardSync(120);scheduleModuleSync(140);syncAppLayerState()}).observe(document.documentElement,{childList:true,subtree:true});
  addEventListener("popstate",()=>{normalizeAppViewport();setAppRouteState(currentAppRoute(),true);scheduleModuleSync(0)});
  addEventListener("hashchange",()=>{if(location.hash==="#company-expenses"){root.classList.remove("app-native-hub-open");updateHeader(directExpenseOpening?"\u65b0\u589e\u8bb0\u8d26":"\u516c\u53f8\u8bb0\u8d26",true);updateBottom("task")}});
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded",installShell); else installShell();
})();
