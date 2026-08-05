(function () {
  const marker = "company-expense-entry";
  const panelMarker = "data-company-expense-panel";
  function isCompanyExpenseActive() { return window.location.hash === "#company-expenses"; }
  function isAppClientMode() {
    const params = new URLSearchParams(window.location.search);
    const userAgent = navigator.userAgent || "";
    const isIosWebView = /iPhone|iPad|iPod/i.test(userAgent) && /AppleWebKit/i.test(userAgent) && !/Safari\//i.test(userAgent);
    return document.documentElement.classList.contains("app-client-mode")
      || params.get("app") === "1"
      || isIosWebView
      || window.matchMedia?.("(display-mode: standalone)").matches
      || navigator.standalone === true
      || Boolean(window.XiaoXuApp)
      || Boolean(window.webkit?.messageHandlers?.xiaoxuApp);
  }
  function installPanelStyle() {
    if (document.querySelector("style[data-company-expense-style]")) return;
    const style = document.createElement("style");
    style.setAttribute("data-company-expense-style", "true");
    style.textContent = `
      .layout-main.company-expense-active { position: relative; min-height: calc(100vh - 86px); }
      .layout-main.company-expense-active > :not([data-company-expense-panel]) { display: none !important; }
      [data-company-expense-panel] { position: absolute; inset: 10px 24px 24px; overflow: hidden; border: 1px solid #e5e7eb; border-radius: 12px; background: #f5f7fa; box-shadow: 0 8px 24px rgb(15 23 42 / 5%); z-index: 5; }
      [data-company-expense-panel] iframe { display: block; width: 100%; height: 100%; border: 0; background: #f5f7fa; }
      @media (max-width: 900px) {
        .layout-main.company-expense-active { position: static !important; min-height: 0 !important; padding: 0 !important; }
        [data-company-expense-panel] { position: fixed !important; inset: calc(56px + env(safe-area-inset-top,0px)) 0 0 !important; width: auto !important; height: auto !important; border: 0 !important; border-radius: 0 !important; box-shadow: none !important; z-index: 9999 !important; }
        html.app-client-mode [data-company-expense-panel] { bottom: calc(70px + env(safe-area-inset-bottom,0px)) !important; }
      }
    `;
    document.head.appendChild(style);
  }
  function renderCompanyExpensePanel() {
    const active = isCompanyExpenseActive();
    document.querySelectorAll(`[data-${marker}]`).forEach((item) => item.classList.toggle("is-active", active));
    if (active) document.querySelectorAll(`.layout-menu .el-menu-item:not([data-${marker}])`).forEach((item) => item.classList.remove("is-active"));
    const mains = Array.from(document.querySelectorAll(".layout-main"));
    const main = mains.find((item) => item.isConnected && item.getClientRects().length > 0) || mains[0];
    if (!main) return;
    const existing = main.querySelector(`[${panelMarker}]`);
    if (!active) {
      existing?.remove();
      main.classList.remove("company-expense-active");
      return;
    }
    main.classList.add("company-expense-active");
    if (!existing) {
      const panel = document.createElement("section");
      panel.setAttribute(panelMarker, "true");
      const appMode = isAppClientMode();
      const directEntry = sessionStorage.getItem("company-expense-direct-entry") === "1";
      if (directEntry) sessionStorage.removeItem("company-expense-direct-entry");
      panel.innerHTML = `<iframe src="/company-expenses-app/?embedded=1&v=20260731-quick6&app=${appMode ? "1" : "0"}&entry=${directEntry ? "1" : "0"}" title="\u516c\u53f8\u8bb0\u8d26"></iframe>`;
      main.appendChild(panel);
    }
    const title = document.querySelector(".layout-title");
    if (title && title.textContent !== "\u516c\u53f8\u8bb0\u8d26") title.textContent = "\u516c\u53f8\u8bb0\u8d26";
    const breadcrumb = document.querySelector(".layout-breadcrumb");
    if (breadcrumb && breadcrumb.textContent !== "\u4efb\u52a1\u8bb0\u8d26 / \u516c\u53f8\u8bb0\u8d26") breadcrumb.textContent = "\u4efb\u52a1\u8bb0\u8d26 / \u516c\u53f8\u8bb0\u8d26";
  }
  function openCompanyExpense(event) {
    event.preventDefault();
    if (!isCompanyExpenseActive()) window.history.pushState(null, "", window.location.pathname + window.location.search + "#company-expenses");
    renderCompanyExpensePanel();
  }
  function moveEntry(menu, itemLabel, groupLabel, markerName, insertFirst) {
    const group = Array.from(menu.children).find((node) => {
      if (!node.matches?.(".el-sub-menu")) return false;
      const title = node.querySelector(":scope > .el-sub-menu__title");
      return (title?.textContent || "").trim() === groupLabel;
    });
    if (!group) return;
    const submenu = group.querySelector(":scope > .el-menu--inline");
    if (!submenu) return;
    let item = Array.from(menu.children).find((node) => {
      return node.matches?.(".el-menu-item") && (node.textContent || "").trim() === itemLabel;
    });
    if (!item) item = submenu.querySelector(`[data-menu-layout="${markerName}"]`);
    if (!item || item.parentElement === submenu) return;
    const nestedSample = submenu.querySelector(":scope > .el-menu-item");
    item.setAttribute("data-menu-layout", markerName);
    if (nestedSample) {
      const nestedStyle = getComputedStyle(nestedSample);
      item.style.paddingLeft = nestedStyle.paddingLeft;
      item.style.paddingRight = nestedStyle.paddingRight;
    }
    if (insertFirst && submenu.firstElementChild) submenu.insertBefore(item, submenu.firstElementChild);
    else submenu.appendChild(item);
  }
  function ensureSubmenuIcon(menu, itemLabel, pathData) {
    menu.querySelectorAll(".el-menu--inline > .el-menu-item").forEach((item) => {
      if ((item.textContent || "").trim() !== itemLabel || item.querySelector(":scope > .el-icon")) return;
      const icon = document.createElement("i");
      icon.className = "el-icon";
      icon.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="${pathData}"/></svg>`;
      item.insertBefore(icon, item.firstChild);
    });
  }
  function addEntry(menu) {
    if (!menu || menu.querySelector(`[data-${marker}]`)) return;
    const item = document.createElement("li");
    item.className = "el-menu-item";
    item.setAttribute(`data-${marker}`, "true");
    item.innerHTML = '<i class="el-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm1 3v4h12V6H6Zm0 7v2h2v-2H6Zm5 0v2h2v-2h-2Zm5 0v2h2v-2h-2ZM6 17v2h2v-2H6Zm5 0v2h2v-2h-2Zm5 0v2h2v-2h-2Z"/></svg></i><span>\u516c\u53f8\u8bb0\u8d26</span>';
    item.addEventListener("click", openCompanyExpense);
    const taskGroup = Array.from(menu.querySelectorAll(":scope > .el-sub-menu")).find((group) => {
      const title = group.querySelector(":scope > .el-sub-menu__title");
      return (title?.textContent || "").trim() === "\u4efb\u52a1\u8bb0\u8d26";
    });
    const submenu = taskGroup?.querySelector(":scope > .el-menu--inline");
    if (submenu) submenu.appendChild(item);
    else menu.appendChild(item);
  }
  function syncMenus() {
    document.querySelectorAll(".layout-menu").forEach((menu) => {
      if (!menu.dataset.companyExpenseExitBound) {
        menu.dataset.companyExpenseExitBound = "true";
        menu.addEventListener("click", (event) => {
          const target = event.target.closest(".el-menu-item");
          if (!target || target.hasAttribute(`data-${marker}`) || !isCompanyExpenseActive()) return;
          window.history.replaceState(null, "", window.location.pathname + window.location.search);
          renderCompanyExpensePanel();
        }, true);
      }
      moveEntry(menu, "\u8d26\u53f7\u4e0e\u6743\u9650", "\u7cfb\u7edf\u7ba1\u7406", "account-permissions", true);
      moveEntry(menu, "\u9489\u9489\u5229\u6da6", "\u4efb\u52a1\u8bb0\u8d26", "dingtalk-profits", false);
      addEntry(menu);
      ensureSubmenuIcon(menu, "\u5b89\u5168\u65e5\u5fd7", "M12 2 20 5v6c0 5-3.4 9.7-8 11-4.6-1.3-8-6-8-11V5l8-3Zm0 3.1L7 7v4c0 3.4 2 6.6 5 7.8 3-1.2 5-4.4 5-7.8V7l-5-1.9Zm-1 3h2v4h-2v-4Zm0 5.5h2v2h-2v-2Z");
      ensureSubmenuIcon(menu, "\u7cfb\u7edf\u8bbe\u7f6e", "M19.1 13a7.4 7.4 0 0 0 .1-1 7.4 7.4 0 0 0-.1-1l2.1-1.6-2-3.4-2.6 1a8 8 0 0 0-1.7-1L14.5 3h-5L9 6a8 8 0 0 0-1.7 1l-2.6-1-2 3.4L4.9 11a7.4 7.4 0 0 0-.1 1 7.4 7.4 0 0 0 .1 1l-2.1 1.6 2 3.4 2.6-1a8 8 0 0 0 1.7 1l.4 3h5l.5-3a8 8 0 0 0 1.7-1l2.6 1 2-3.4L19.1 13ZM12 15.5A3.5 3.5 0 1 1 12 8a3.5 3.5 0 0 1 0 7.5Z");
      ensureSubmenuIcon(menu, "\u5e93\u5b58\u603b\u89c8", "M4 3h16a1 1 0 0 1 1 1v16H3V4a1 1 0 0 1 1-1Zm2 11v4h3v-4H6Zm5-5v9h3V9h-3Zm5-3v12h3V6h-3Z");
      ensureSubmenuIcon(menu, "\u5165\u5e93\u7ba1\u7406", "M4 3h16v6h-2V5H6v14h12v-4h2v6H4V3Zm9 5 5 4-5 4v-3H8v-2h5V8Z");
      ensureSubmenuIcon(menu, "\u51fa\u5e93\u53d1\u8d27", "M4 3h16v18H4V3Zm2 2v14h12V5H6Zm5 3h2v3h3v2h-3v3h-2v-3H8v-2h3V8Z");
      ensureSubmenuIcon(menu, "\u5e93\u5b58\u6d41\u6c34", "M5 4h14v2H5V4Zm0 5h14v2H5V9Zm0 5h9v2H5v-2Zm11 0 4 3-4 3v-2h-3v-2h3v-2Z");
      ensureSubmenuIcon(menu, "\u57fa\u7840\u8d44\u6599", "M12 3c4.4 0 8 1.3 8 3s-3.6 3-8 3-8-1.3-8-3 3.6-3 8-3Zm-8 6.2C5.7 10.4 8.7 11 12 11s6.3-.6 8-1.8V13c0 1.7-3.6 3-8 3s-8-1.3-8-3V9.2Zm0 7C5.7 17.4 8.7 18 12 18s6.3-.6 8-1.8V19c0 1.7-3.6 3-8 3s-8-1.3-8-3v-2.8Z");
    });
    renderCompanyExpensePanel();
  }
  installPanelStyle();
  new MutationObserver(syncMenus).observe(document.documentElement, { childList: true, subtree: true });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", syncMenus);
  else syncMenus();
  window.addEventListener("hashchange", syncMenus);
  window.addEventListener("popstate", syncMenus);
})();
