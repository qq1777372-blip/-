(function () {
  const storageKey = "site-night-mode";
  const className = "site-night-mode";
  const clientParams = new URLSearchParams(window.location.search);
  const userAgent = navigator.userAgent || "";
  const isIosWebView = /iPhone|iPad|iPod/i.test(userAgent)
    && /AppleWebKit/i.test(userAgent)
    && !/Safari\//i.test(userAgent);
  const isStandaloneClient = window.matchMedia?.("(display-mode: standalone)").matches || navigator.standalone === true;
  const isNativeAppClient = clientParams.get("app") === "1" || isIosWebView || Boolean(window.XiaoXuApp) || Boolean(window.webkit?.messageHandlers?.xiaoxuApp);
  const isAppClient = isStandaloneClient || isNativeAppClient;
  document.documentElement.classList.toggle("app-client-mode", isAppClient);
  document.documentElement.classList.toggle("mobile-web-mode", !isAppClient);
  const style = document.createElement("style");
  style.setAttribute("data-night-mode-style", "true");
  style.textContent = `
    html.${className} { color-scheme: dark; --el-bg-color:#111827; --el-bg-color-page:#0b1220; --el-bg-color-overlay:#172033; --el-text-color-primary:#e5edf7; --el-text-color-regular:#c5d0de; --el-text-color-secondary:#93a4b8; --el-text-color-placeholder:#6f8196; --el-border-color:#334155; --el-border-color-light:#2b3a4d; --el-border-color-lighter:#243246; --el-fill-color:#1d2939; --el-fill-color-light:#202d3e; --el-fill-color-lighter:#172235; --el-fill-color-blank:#111827; --el-mask-color:rgba(2,6,23,.72); --app-bg:#0b1220; --panel-bg:#111827; --panel-border:#2b3a4d; --ui-surface:#111827; --ui-border:#2b3a4d; --text-main:#e5edf7; --text-secondary:#91a1b5; --shadow-soft:0 8px 24px rgba(0,0,0,.22); }
    html.${className} body, html.${className} .layout-content-shell, html.${className} .layout-main, html.${className} .el-main { background:#0b1220 !important; color:#e5edf7 !important; }
    html.${className} .layout-header, html.${className} .el-header { background:#111827 !important; border-color:#263449 !important; color:#e5edf7 !important; }
    html.${className} .layout-title, html.${className} .layout-breadcrumb, html.${className} h1, html.${className} h2, html.${className} h3, html.${className} h4 { color:#e5edf7; }
    html.${className} .el-card, html.${className} .el-dialog, html.${className} .el-drawer, html.${className} .el-table, html.${className} .el-table tr, html.${className} .el-table th.el-table__cell, html.${className} .el-table td.el-table__cell, html.${className} .el-descriptions__body, html.${className} .el-collapse-item__wrap { background:#111827 !important; color:#d9e3ef !important; border-color:#2b3a4d !important; }
    html.${className} .el-table--enable-row-hover .el-table__body tr:hover>td.el-table__cell, html.${className} .el-table__body tr.current-row>td.el-table__cell { background:#1b2a3d !important; }
    html.${className} .el-input__wrapper, html.${className} .el-select__wrapper, html.${className} .el-textarea__inner, html.${className} .el-input-number, html.${className} .el-date-editor, html.${className} .el-upload-dragger { background:#172033 !important; box-shadow:0 0 0 1px #334155 inset !important; color:#e5edf7 !important; }
    html.${className} input, html.${className} textarea, html.${className} select { color:#e5edf7 !important; }
    html.${className} .el-popper, html.${className} .el-dropdown-menu, html.${className} .el-select-dropdown, html.${className} .el-picker-panel, html.${className} .el-message-box, html.${className} .el-popover { background:#172033 !important; border-color:#334155 !important; color:#e5edf7 !important; }
    html.${className} .el-dropdown-menu__item:not(.is-disabled):focus, html.${className} .el-dropdown-menu__item:not(.is-disabled):hover, html.${className} .el-select-dropdown__item.is-hovering { background:#24364d !important; color:#fff !important; }
    html.${className} .el-tabs__item, html.${className} .el-form-item__label, html.${className} .el-checkbox, html.${className} .el-radio { color:#bdc9d8; }
    html.${className} .el-empty__description p, html.${className} .muted, html.${className} .text-secondary { color:#8394aa !important; }
    html.${className} .auth-shell { background:#0b1220 !important; }
    html.${className} .auth-card { background:#111827 !important; border-color:#334155 !important; color:#e5edf7 !important; }
    html.${className} [data-company-expense-panel], html.${className} [data-knowledge-panel] { background:#0b1220 !important; border-color:#2b3a4d !important; }
    html.${className} [data-knowledge-tabs] { background:#111827 !important; border-color:#2b3a4d !important; }
    html.${className} [data-knowledge-tabs] button { color:#aebdce !important; }
    html.${className} [data-knowledge-tabs] button.is-active { color:#66b1ff !important; background:#1c3048 !important; }
    html.${className} .dashboard-surface, html.${className} .dashboard-surface__section { background:#0b1220 !important; color:#e5edf7 !important; }
    html.${className} .dashboard-surface__section + .dashboard-surface__section { border-color:#263449 !important; }
    html.${className} .dashboard-metric-card, html.${className} .reminder-shell, html.${className} .summary-shell, html.${className} .warehouse-dashboard-shell, html.${className} .server-shell, html.${className} .server-metric-card, html.${className} .server-list-panel { background:#111827 !important; border-color:#334155 !important; color:#e5edf7 !important; }
    html.${className} .dashboard-metric-card--accent { background:#14203a !important; border-color:#4b5fc7 !important; }
    html.${className} .reminder-card { background:linear-gradient(180deg,#172033 0%,#111827 100%) !important; border-color:#334155 !important; color:#e5edf7 !important; box-shadow:none !important; }
    html.${className} .reminder-card--danger { border-color:#7f3d48 !important; }
    html.${className} .reminder-card--warning { border-color:#75552d !important; }
    html.${className} .reminder-card--primary { border-color:#3d5f91 !important; }
    html.${className} .reminder-head__badge { background:#1c3048 !important; color:#79bbff !important; }
    html.${className} .dashboard-metric-card .metric-label, html.${className} .dashboard-metric-card .metric-note, html.${className} .reminder-card__title, html.${className} .reminder-card__note, html.${className} .server-meta, html.${className} .server-metric-card > span, html.${className} .server-metric-card > small, html.${className} .server-list-title p, html.${className} .database-name-cell span { color:#91a1b5 !important; }
    html.${className} .dashboard-metric-card .metric-value, html.${className} .reminder-head h3, html.${className} .summary-head h3, html.${className} .warehouse-dashboard-head h3, html.${className} .server-head h3, html.${className} .server-list-title h4 { color:#e5edf7 !important; }
    html.${className} .summary-table, html.${className} .summary-table .el-table, html.${className} .summary-table .el-table__inner-wrapper, html.${className} .summary-table .el-table__header-wrapper, html.${className} .summary-table .el-table__body-wrapper { background:#111827 !important; }
    .mobile-nav-drawer, .mobile-nav-drawer .el-drawer__body { background:#111827 !important; border-color:#111827 !important; }
    .mobile-nav-drawer .el-drawer__body { color:#dbe7f5 !important; }
    .mobile-nav-drawer, .mobile-nav-drawer * { scrollbar-color:#64748b #111827; }
    .mobile-nav-drawer::-webkit-scrollbar, .mobile-nav-drawer *::-webkit-scrollbar { width:6px; height:6px; }
    .mobile-nav-drawer::-webkit-scrollbar-track, .mobile-nav-drawer *::-webkit-scrollbar-track { background:#111827; }
    .mobile-nav-drawer::-webkit-scrollbar-thumb, .mobile-nav-drawer *::-webkit-scrollbar-thumb { background:#64748b; border-radius:999px; }
    html.${className} .el-overlay, html.${className} .el-overlay-dialog { background:rgba(2,6,23,.72) !important; }
    html.${className} .saved-links-board { background:#111827 !important; color:#e5edf7 !important; }
    html.${className} .saved-links-topbar, html.${className} .saved-link-post, html.${className} .saved-article-card__footer { border-color:#2b3a4d !important; }
    html.${className} .saved-links-tab { color:#aebdce !important; }
    html.${className} .saved-links-tab:hover { color:#fff !important; background:#1b2a3d !important; }
    html.${className} .saved-links-tab--active { color:#79bbff !important; background:#1c3048 !important; }
    html.${className} .saved-links-tab em { background:#334155 !important; color:#cbd8e7 !important; }
    html.${className} .saved-links-tab--active em { background:#31577e !important; color:#dbeafe !important; }
    html.${className} .saved-links-search .el-input__wrapper { background:#172033 !important; box-shadow:inset 0 0 0 1px #334155 !important; }
    html.${className} .saved-links-subbar__title, html.${className} .saved-link-post__author, html.${className} .saved-link-post__title, html.${className} .saved-article-card__title, html.${className} .saved-link-push-dialog__title { color:#e5edf7 !important; }
    html.${className} .saved-links-subbar__summary, html.${className} .saved-links-subbar__status, html.${className} .saved-link-post__description, html.${className} .saved-link-post__meta, html.${className} .saved-article-card__meta, html.${className} .saved-article-card__excerpt, html.${className} .saved-link-push-dialog__status, html.${className} .saved-link-push-dialog__tip { color:#91a1b5 !important; }
    html.${className} .saved-link-post__menu-button { background:#172033 !important; border-color:#334155 !important; color:#aebdce !important; box-shadow:none !important; }
    html.${className} .saved-link-post__menu-button:hover { background:#20324a !important; color:#fff !important; }
    html.${className} .saved-link-post__category { background:#243247 !important; color:#c4d0df !important; }
    html.${className} .saved-link-post__url { background:#172033 !important; border-color:#334155 !important; }
    html.${className} .saved-link-post__url-host { color:#cbd8e7 !important; }
    html.${className} .saved-article-card { background:linear-gradient(180deg,#172033 0%,#111827 100%) !important; border-color:#334155 !important; box-shadow:none !important; }
    html.${className} .saved-article-card:hover { border-color:#4b6b91 !important; box-shadow:0 18px 36px rgba(0,0,0,.22) !important; }
    html.${className} .saved-article-card__cover, html.${className} .saved-link-gallery__item { background:#1b2a3d !important; box-shadow:inset 0 0 0 1px #334155 !important; }
    html.${className} .saved-links-board .el-pagination button, html.${className} .saved-links-board .el-pager li { background:#172033 !important; color:#cbd8e7 !important; }
    html.${className} .saved-links-board .el-pagination button:disabled { color:#64748b !important; }
    html.${className} .saved-links-board .el-pager li.is-active { background:#6366f1 !important; color:#fff !important; }
    html.${className} .saved-link-image-dialog { background:#111827 !important; }
    html.${className} .saved-link-image-dialog img { background:#172033 !important; }
    html.${className} .saved-link-push-dialog__summary { background:#172033 !important; border-color:#334155 !important; }
    html.${className} .saved-link-editor-gallery__item { background:#172033 !important; border-color:#334155 !important; }
    html, body, #app { min-height:100dvh; }
    @media (max-width:900px) {
      .layout-header { min-height:calc(56px + env(safe-area-inset-top,0px)) !important; padding-top:calc(8px + env(safe-area-inset-top,0px)) !important; padding-right:max(12px,env(safe-area-inset-right,0px)) !important; padding-left:max(12px,env(safe-area-inset-left,0px)) !important; }
      .layout-main { padding-right:max(12px,env(safe-area-inset-right,0px)) !important; padding-bottom:calc(16px + env(safe-area-inset-bottom,0px)) !important; padding-left:max(12px,env(safe-area-inset-left,0px)) !important; }
      html.app-client-mode .layout-main { padding-bottom:calc(92px + env(safe-area-inset-bottom,0px)) !important; }
      html.app-client-mode .layout-header .menu-trigger { display:none !important; }
      html.app-client-mode .layout-header .header-left { min-width:0; }
      html.app-client-mode .layout-header .title-stack { margin-left:0 !important; }
      html.app-client-mode .el-overlay:has(.mobile-nav-drawer) { display:none !important; pointer-events:none !important; }
      .mobile-nav-drawer { height:100dvh !important; }
      .mobile-nav-drawer .el-drawer__body { padding-top:env(safe-area-inset-top,0px) !important; padding-right:max(0px,env(safe-area-inset-right,0px)) !important; padding-bottom:env(safe-area-inset-bottom,0px) !important; padding-left:max(0px,env(safe-area-inset-left,0px)) !important; }
      .el-overlay-dialog .el-dialog { max-height:calc(100dvh - env(safe-area-inset-top,0px) - env(safe-area-inset-bottom,0px) - 12px) !important; }
    }
    .site-night-toggle { width:38px; height:38px; flex:0 0 38px; display:grid; place-items:center; padding:0; border:1px solid #dcdfe6; border-radius:8px; background:#fff; color:#445069; cursor:pointer; }
    .site-night-toggle:hover { color:#409eff; border-color:#a0cfff; background:#ecf5ff; }
    .site-night-toggle svg { width:18px; height:18px; }
    html.${className} .site-night-toggle { background:#172033; color:#dbe7f5; border-color:#334155; }
    html.${className} .site-night-toggle:hover { background:#20324a; color:#79bbff; border-color:#4b6b91; }
    @media (max-width:640px) {
      input, textarea, select, .el-input__inner, .el-textarea__inner { font-size:16px !important; }
      button, a, input, textarea, select { touch-action:manipulation; }
      .auth-shell { width:100%; height:var(--app-visual-height,100dvh) !important; min-height:var(--app-visual-height,100dvh) !important; max-height:var(--app-visual-height,100dvh); overflow-y:auto; overscroll-behavior:contain; padding:12px max(12px,env(safe-area-inset-right)) max(12px,env(safe-area-inset-bottom)) max(12px,env(safe-area-inset-left)) !important; scroll-padding:16px 0; }
      .auth-card { width:min(400px,100%) !important; }
      .auth-shell .el-input__inner { font-size:16px !important; }
      .auth-shell input, .auth-shell textarea, .auth-shell select { font-size:16px !important; }
      html.mobile-keyboard-open body { height:var(--app-visual-height,100dvh); overflow:hidden; }
      html.mobile-keyboard-open .auth-shell { place-items:start center !important; padding-top:8px !important; }
      html.mobile-keyboard-open .auth-card { margin:0 auto !important; padding:16px 18px 18px !important; }
      html.mobile-keyboard-open .auth-brand { display:none !important; }
      html.mobile-keyboard-open .el-form-item { margin-bottom:12px; }
      html.mobile-keyboard-open .auth-remember-row { margin-bottom:10px !important; }
    }
    .app-global-bottom-nav { display:none; }
    @media (max-width:900px) {
      html.app-client-mode .app-global-bottom-nav { position:fixed; left:0; right:0; bottom:0; z-index:12000; display:grid; grid-template-columns:1fr 1fr 82px 1fr 1fr; align-items:end; min-height:64px; padding:7px max(8px,env(safe-area-inset-right,0px)) calc(6px + env(safe-area-inset-bottom,0px)) max(8px,env(safe-area-inset-left,0px)); background:rgba(255,255,255,.96); border-top:1px solid #e5e7eb; box-shadow:0 -8px 28px rgba(15,23,42,.09); backdrop-filter:blur(20px); -webkit-backdrop-filter:blur(20px); }
      .app-global-nav-item { appearance:none; min-width:0; height:49px; padding:2px 0; border:0; background:transparent; color:#7b8493; display:grid; place-items:center; align-content:center; gap:2px; font-size:11px; line-height:1.1; }
      .app-global-nav-item svg { width:22px; height:22px; }
      .app-global-nav-item.is-active { color:#1687f8; font-weight:700; }
      .app-global-nav-add { align-self:start; justify-self:center; width:58px; height:58px; margin-top:-27px; padding:0; border:6px solid #f5f7fa; border-radius:50%; background:linear-gradient(145deg,#2297ff,#27c7ec); color:#fff; box-shadow:0 9px 22px rgba(22,135,248,.38); font-size:36px; font-weight:300; line-height:44px; text-align:center; }
      .app-global-nav-add:active { transform:scale(.94); }
      html.${className} .app-global-bottom-nav { background:rgba(17,24,39,.97); border-color:#2b3a4d; }
      html.${className} .app-global-nav-item { color:#8fa0b5; }
      html.${className} .app-global-nav-item.is-active { color:#67b7ff; }
      html.${className} .app-global-nav-add { border-color:#0b1220; }
      html.mobile-keyboard-open .app-global-bottom-nav { display:none; }
      .app-more-backdrop { position:fixed; inset:0; z-index:13000; display:grid; align-items:end; background:rgba(2,6,23,.48); opacity:0; visibility:hidden; transition:opacity .2s ease,visibility .2s ease; }
      .app-more-backdrop.is-open { opacity:1; visibility:visible; }
      .app-more-sheet { width:100%; max-height:min(82dvh,720px); overflow:auto; overscroll-behavior:contain; padding:16px max(16px,env(safe-area-inset-right,0px)) calc(18px + env(safe-area-inset-bottom,0px)) max(16px,env(safe-area-inset-left,0px)); border-radius:22px 22px 0 0; background:#fff; color:#172033; box-shadow:0 -18px 45px rgba(2,6,23,.22); transform:translateY(105%); transition:transform .24s ease; }
      .app-more-backdrop.is-open .app-more-sheet { transform:translateY(0); }
      .app-more-handle { width:38px; height:4px; margin:0 auto 14px; border-radius:999px; background:#d8dee8; }
      .app-more-header { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:14px; }
      .app-more-header strong { display:block; font-size:20px; }
      .app-more-header span { color:#8a95a6; font-size:13px; }
      .app-more-close { width:36px; height:36px; border:0; border-radius:50%; background:#f0f3f7; color:#596579; font-size:24px; line-height:1; }
      .app-more-section { padding:14px 0 2px; border-top:1px solid #edf0f4; }
      .app-more-section h3 { margin:0 0 11px; color:#7b8798; font-size:13px; font-weight:650; }
      .app-more-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px 8px; }
      .app-more-action { min-width:0; min-height:74px; padding:9px 3px 7px; border:0; border-radius:13px; background:#f6f8fb; color:#253247; display:grid; place-items:center; align-content:center; gap:6px; font-size:12px; }
      .app-more-action svg { width:25px; height:25px; color:#2389f5; }
      .app-more-action:active { transform:scale(.96); background:#eaf4ff; }
      .app-more-action[hidden] { display:none !important; }
      html.app-more-open, html.app-more-open body { overflow:hidden !important; }
      html.${className} .app-more-sheet { background:#111827; color:#e5edf7; }
      html.${className} .app-more-handle { background:#475569; }
      html.${className} .app-more-header span, html.${className} .app-more-section h3 { color:#91a1b5; }
      html.${className} .app-more-section { border-color:#27364a; }
      html.${className} .app-more-close, html.${className} .app-more-action { background:#172033; color:#dce7f3; }
    }
  `;
  document.head.appendChild(style);

  function isEnabled() { return localStorage.getItem(storageKey) === "1"; }
  function icon(enabled) {
    return enabled
      ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 4V2h1v2h-1Zm0 18v-2h1v2h-1ZM4 13H2v-1h2v1Zm18 0h-2v-1h2v1ZM5.6 6.3 4.2 4.9l.7-.7 1.4 1.4-.7.7Zm13.5 13.5-1.4-1.4.7-.7 1.4 1.4-.7.7ZM18.4 6.3l-.7-.7 1.4-1.4.7.7-1.4 1.4ZM4.9 19.8l-.7-.7 1.4-1.4.7.7-1.4 1.4ZM12.5 7a5.5 5.5 0 1 1 0 11 5.5 5.5 0 0 1 0-11Z"/></svg>'
      : '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M20.7 15.2A8.5 8.5 0 0 1 8.8 3.3 9 9 0 1 0 20.7 15.2ZM5 12a7 7 0 0 1 2-4.9A10.5 10.5 0 0 0 16.9 17 7 7 0 0 1 5 12Z"/></svg>';
  }
  function applyTheme() {
    const enabled = isEnabled();
    document.documentElement.classList.toggle(className, enabled);
    document.querySelectorAll(".site-night-toggle").forEach((button) => {
      const state = enabled ? "night" : "day";
      if (button.dataset.themeState !== state) {
        button.innerHTML = icon(enabled);
        button.dataset.themeState = state;
      }
      button.title = enabled ? "\u5207\u6362\u4e3a\u65e5\u95f4\u6a21\u5f0f" : "\u5207\u6362\u4e3a\u591c\u95f4\u6a21\u5f0f";
      button.setAttribute("aria-label", button.title);
    });
  }
  function installButton() {
    document.querySelectorAll(".layout-userbar").forEach((userbar) => {
      if (userbar.querySelector(":scope > .site-night-toggle")) return;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "site-night-toggle";
      button.addEventListener("click", () => {
        localStorage.setItem(storageKey, isEnabled() ? "0" : "1");
        applyTheme();
      });
      userbar.insertBefore(button, userbar.firstChild);
    });
    applyTheme();
  }
  function clickMenuItem(label) {
    const items = Array.from(document.querySelectorAll(".layout-menu .el-menu-item"));
    const item = items.find((node) => (node.textContent || "").trim() === label);
    if (!item) return false;
    item.click();
    return true;
  }
  function openExpensePanel(openEntry) {
    if (window.location.hash !== "#company-expenses") {
      window.location.hash = "company-expenses";
    } else {
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    }
    if (!openEntry) return;
    let attempts = 0;
    const timer = window.setInterval(() => {
      attempts += 1;
      const frame = document.querySelector("[data-company-expense-panel] iframe");
      if (frame?.contentWindow) {
        frame.contentWindow.postMessage({ type:"company-expense-open-entry" }, window.location.origin);
        try {
          if (frame.contentDocument?.body?.classList.contains("entry-page-open")) window.clearInterval(timer);
        } catch {}
      }
      if (attempts >= 30) {
        window.clearInterval(timer);
      }
    }, 100);
  }
  function updateAppNav() {
    const nav = document.querySelector(".app-global-bottom-nav");
    if (!nav) return;
    const hash = window.location.hash;
    let active = "home";
    if (hash === "#company-expenses") active = "ledger";
    else {
      const selected = Array.from(document.querySelectorAll(".layout-menu .el-menu-item.is-active"))
        .map((node) => (node.textContent || "").trim()).join(" ");
      if (selected.includes("????")) active = "links";
    }
    nav.querySelectorAll("[data-app-nav]").forEach((button) => button.classList.toggle("is-active", button.dataset.appNav === active));
  }
  const moreSections = [
    { title:"?????", items:["????","?????","????","????"] },
    { title:"?????", items:["????","????","????","????","????","????","????","????"] },
    { title:"?????", items:["?????","????","????","????","????"] }
  ];
  function moreIcon(label) {
    if (label.includes("??") || label.includes("??") || label.includes("??")) return "M5 3h14v18H5V3Zm3 4v2h8V7H8Zm0 5v2h3v-2H8Zm5 0v2h3v-2h-3Zm-5 4v2h3v-2H8Zm5 0v2h3v-2h-3Z";
    if (label.includes("??") || label.includes("?") || label.includes("??") || label.includes("??") || label.includes("??")) return "M4 4h16l1 5a4 4 0 0 1-2 3.5V21H5v-8.5A4 4 0 0 1 3 9l1-5Zm3 9v6h10v-6a4 4 0 0 1-3-1.4A4 4 0 0 1 12 13a4 4 0 0 1-2-1.4A4 4 0 0 1 7 13Z";
    if (label.includes("??") || label.includes("???") || label.includes("??")) return "M12 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10Zm0 2c-5 0-9 2.7-9 6v2h18v-2c0-3.3-4-6-9-6Z";
    if (label.includes("??") || label.includes("??")) return "M7 2h10a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Zm0 3v14h10V5H7Zm4 11h2v2h-2v-2Z";
    return "M12 2 20 5v6c0 5-3.4 9.7-8 11-4.6-1.3-8-6-8-11V5l8-3Zm0 5a3 3 0 1 0 0 6 3 3 0 0 0 0-6Zm-5 9.2V18c0-2.2 2.2-3.5 5-3.5s5 1.3 5 3.5v.2c1.2-1.8 2-4.2 2-7.2V6.4L12 4 5 6.4V11c0 3 .8 5.4 2 7.2Z";
  }
  function closeAppMore() {
    document.querySelector(".app-more-backdrop")?.classList.remove("is-open");
    document.documentElement.classList.remove("app-more-open");
    window.setTimeout(updateAppNav, 80);
  }
  function openAppMore() {
    const backdrop = document.querySelector(".app-more-backdrop");
    if (!backdrop) return;
    syncAppMoreAvailability();
    backdrop.classList.add("is-open");
    document.documentElement.classList.add("app-more-open");
    document.querySelectorAll(".app-global-nav-item").forEach((button) => button.classList.toggle("is-active", button.dataset.appNav === "mine"));
  }
  function syncAppMoreAvailability() {
    const labels = new Set(Array.from(document.querySelectorAll(".layout-menu .el-menu-item")).map((node) => (node.textContent || "").trim()));
    document.querySelectorAll(".app-more-action").forEach((button) => {
      button.hidden = button.dataset.moreTarget !== "????" && !labels.has(button.dataset.moreTarget);
    });
  }
  function installAppMore() {
    if (document.documentElement.classList.contains("app-redesign")) return;
    if (!isAppClient || document.querySelector(".app-more-backdrop")) {
      syncAppMoreAvailability();
      return;
    }
    const backdrop = document.createElement("div");
    backdrop.className = "app-more-backdrop";
    backdrop.innerHTML = `<section class="app-more-sheet" role="dialog" aria-modal="true" aria-label="????"><div class="app-more-handle"></div><header class="app-more-header"><div><strong>????</strong><span>??????????</span></div><button type="button" class="app-more-close" aria-label="??">?</button></header>${moreSections.map((section) => `<section class="app-more-section"><h3>${section.title}</h3><div class="app-more-grid">${section.items.map((label) => `<button type="button" class="app-more-action" data-more-target="${label}"><svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="${moreIcon(label)}"/></svg><span>${label}</span></button>`).join("")}</div></section>`).join("")}</section>`;
    backdrop.addEventListener("click", (event) => { if (event.target === backdrop) closeAppMore(); });
    backdrop.querySelector(".app-more-close").addEventListener("click", closeAppMore);
    backdrop.querySelectorAll(".app-more-action").forEach((button) => button.addEventListener("click", () => {
      const label = button.dataset.moreTarget;
      closeAppMore();
      if (label === "????") openExpensePanel(false);
      else {
        if (window.location.hash) window.history.replaceState(null, "", window.location.pathname + window.location.search);
        clickMenuItem(label);
      }
    }));
    document.body.appendChild(backdrop);
    syncAppMoreAvailability();
  }
  function closeLegacyDrawer() {
    if (!isAppClient) return;
    const drawer = document.querySelector(".mobile-nav-drawer");
    const overlay = drawer?.closest(".el-overlay");
    if (overlay && getComputedStyle(overlay).display !== "none") overlay.dispatchEvent(new MouseEvent("click", { bubbles:true }));
  }
  function installAppNav() {
    if (document.documentElement.classList.contains("app-redesign")) return;
    if (!isAppClient || !document.querySelector(".layout-header") || document.querySelector(".app-global-bottom-nav")) {
      updateAppNav();
      return;
    }
    const nav = document.createElement("nav");
    nav.className = "app-global-bottom-nav";
    nav.setAttribute("aria-label", "App????");
    nav.innerHTML = `
      <button type="button" class="app-global-nav-item" data-app-nav="home" aria-label="\u9996\u9875"><svg viewBox="0 0 24 24"><path fill="currentColor" d="M3 11.2 12 3l9 8.2v9.3a.5.5 0 0 1-.5.5H15v-6H9v6H3.5a.5.5 0 0 1-.5-.5v-9.3Z"/></svg><span>\u9996\u9875</span></button>
      <button type="button" class="app-global-nav-item" data-app-nav="ledger" aria-label="\u8bb0\u8d26"><svg viewBox="0 0 24 24"><path fill="currentColor" d="M5 3h14a2 2 0 0 1 2 2v16H3V5a2 2 0 0 1 2-2Zm1 3v4h12V6H6Zm0 7v2h3v-2H6Zm5 0v2h3v-2h-3Zm5 0v2h2v-2h-2ZM6 17v2h3v-2H6Zm5 0v2h3v-2h-3Zm5 0v2h2v-2h-2Z"/></svg><span>\u8bb0\u8d26</span></button>
      <button type="button" class="app-global-nav-add" data-app-add aria-label="\u65b0\u589e\u8bb0\u8d26">+</button>
      <button type="button" class="app-global-nav-item" data-app-nav="links" aria-label="\u94fe\u63a5"><svg viewBox="0 0 24 24"><path fill="currentColor" d="M8.7 15.3a1 1 0 0 1 0-1.4l5.2-5.2a4 4 0 1 1 5.7 5.6l-3.1 3.1a4 4 0 0 1-5.7 0 1 1 0 0 1 1.4-1.4 2 2 0 0 0 2.9 0l3.1-3.1a2 2 0 1 0-2.9-2.8l-5.2 5.2a1 1 0 0 1-1.4 0Zm6.6-6.6a1 1 0 0 1 0 1.4l-5.2 5.2a4 4 0 1 1-5.7-5.6l3.1-3.1a4 4 0 0 1 5.7 0 1 1 0 0 1-1.4 1.4 2 2 0 0 0-2.9 0l-3.1 3.1a2 2 0 1 0 2.9 2.8l5.2-5.2a1 1 0 0 1 1.4 0Z"/></svg><span>\u94fe\u63a5</span></button>
      <button type="button" class="app-global-nav-item" data-app-nav="mine" aria-label="\u6211\u7684"><svg viewBox="0 0 24 24"><path fill="currentColor" d="M12 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10Zm0 2c-5 0-9 2.7-9 6v2h18v-2c0-3.3-4-6-9-6Z"/></svg><span>\u6211\u7684</span></button>`;
    nav.querySelector('[data-app-nav="home"]').addEventListener("click", () => {
      if (window.location.hash) window.history.replaceState(null, "", window.location.pathname + window.location.search);
      if (!clickMenuItem("\u8fd0\u8425\u5de5\u4f5c\u53f0")) window.location.assign("/ui/dashboard");
      window.setTimeout(updateAppNav, 80);
    });
    nav.querySelector('[data-app-nav="ledger"]').addEventListener("click", () => openExpensePanel(false));
    nav.querySelector("[data-app-add]").addEventListener("click", () => openExpensePanel(true));
    nav.querySelector('[data-app-nav="links"]').addEventListener("click", () => {
      if (window.location.hash) window.history.replaceState(null, "", window.location.pathname + window.location.search);
      clickMenuItem("\u94fe\u63a5\u5e7f\u573a");
      window.setTimeout(updateAppNav, 80);
    });
    nav.querySelector('[data-app-nav="mine"]').addEventListener("click", openAppMore);
    document.body.appendChild(nav);
    updateAppNav();
  }
  function installChrome() {
    installButton();
    installAppNav();
    installAppMore();
    closeLegacyDrawer();
  }
  let maximumVisualHeight = window.visualViewport?.height || window.innerHeight;
  let viewportTimer = 0;
  function scrollFocusedField() {
    const active = document.activeElement;
    if (!(active instanceof HTMLInputElement) && !(active instanceof HTMLTextAreaElement)) return;
    const target = active.closest(".el-form-item") || active;
    target.scrollIntoView({ block:"center", inline:"nearest", behavior:"smooth" });
  }
  function syncVisualViewport() {
    const height = Math.round(window.visualViewport?.height || window.innerHeight);
    maximumVisualHeight = Math.max(maximumVisualHeight, height);
    document.documentElement.style.setProperty("--app-visual-height", `${height}px`);
    const keyboardOpen = window.innerWidth <= 640 && maximumVisualHeight - height > 120;
    document.documentElement.classList.toggle("mobile-keyboard-open", keyboardOpen);
    clearTimeout(viewportTimer);
    if (keyboardOpen) viewportTimer = window.setTimeout(scrollFocusedField, 80);
  }
  window.visualViewport?.addEventListener("resize", syncVisualViewport);
  window.visualViewport?.addEventListener("scroll", syncVisualViewport);
  window.addEventListener("resize", syncVisualViewport);
  document.addEventListener("focusin", (event) => {
    if (!event.target.closest?.(".auth-shell")) return;
    window.setTimeout(() => { syncVisualViewport(); scrollFocusedField(); }, 180);
  });
  document.addEventListener("focusout", (event) => {
    if (!event.target.closest?.(".auth-shell")) return;
    window.setTimeout(syncVisualViewport, 220);
  });
  new MutationObserver(installChrome).observe(document.documentElement, { childList:true, subtree:true });
  window.addEventListener("storage", (event) => { if (event.key === storageKey) applyTheme(); });
  window.addEventListener("hashchange", updateAppNav);
  window.addEventListener("popstate", updateAppNav);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", installChrome);
  else installChrome();
  syncVisualViewport();
  applyTheme();
})();
