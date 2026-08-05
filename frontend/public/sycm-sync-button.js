(() => {
  const ROOT_ID = "sycm-command-center";
  const STYLE_ID = "sycm-command-center-style";
  const RELEASE = "20260805-dashboard19";
  const periods = [["today", "今日"], ["yesterday", "昨日"], ["recent7", "近7天"], ["recent30", "近30天"]];
  const state = { period: "today", shopId: "", view: "overview", shops: [], devices: [], syncing: false, syncTask: null, loading: false };

  const request = async (url, init) => {
    const response = await fetch(url, { credentials: "include", ...init });
    if (!response.ok) throw new Error(`请求失败 (${response.status})`);
    return response.json();
  };
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  };
  const icon = (name) => {
    const icons = {
      refresh: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11a8 8 0 1 0 2 5.1M20 4v7h-7"/></svg>',
      sync: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7h11l-3-3m2 13H6l3 3M18 7a7 7 0 0 1 1.9 5M6 17a7 7 0 0 1-1.9-5"/></svg>',
      eye: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="2.5"/></svg>',
      page: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v14H4zM8 9h8M8 13h5"/></svg>',
      cart: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 4h2l2.2 10h10.7l2-7H7M9 19h.01M17 19h.01"/></svg>',
      users: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M16 20v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 10a4 4 0 1 0 0-8M22 20v-2a4 4 0 0 0-3-3.8M16 2.2a4 4 0 0 1 0 7.6"/></svg>',
      money: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20M7 15h.01"/></svg>',
      rate: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 17 5-5 4 4 7-9M15 7h5v5"/></svg>',
      arrow: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>',
      device: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4"/></svg>'
    };
    const node = el("span", "sc-icon");
    node.innerHTML = icons[name] || icons.page;
    return node;
  };
  const valueOf = (shop, field) => shop?.overview?.[field]?.value ?? shop?.[field] ?? null;
  const sum = (shops, field) => {
    const values = shops.map((shop) => valueOf(shop, field)).filter((value) => value != null);
    return values.length ? values.reduce((total, value) => total + Number(value || 0), 0) : null;
  };
  const number = (value) => value == null ? "--" : new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value);
  const money = (value) => value == null ? "--" : `¥${number(value)}`;
  const percent = (value) => value == null ? "--" : `${(Number(value) * 100).toFixed(2)}%`;
  const dateTime = (value) => value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "暂无";
  const selectedShops = () => state.shopId ? state.shops.filter((shop) => shop.shopId === state.shopId) : state.shops;

  function installStyle() {
    // 必须幂等：mount() 挂在 MutationObserver 上，无条件重插 style 会自触发死循环
    const existing = document.getElementById(STYLE_ID);
    if (existing) {
      if (existing.dataset.release === RELEASE) return;
      existing.remove();
    }
    const style = el("style");
    style.id = STYLE_ID;
    style.dataset.release = RELEASE;
    style.textContent = `
      #${ROOT_ID}{--sc-primary:#6366f1;--sc-primary-strong:#4f46e5;--sc-sky:#0284c7;--sc-teal:#059669;--sc-amber:#b45309;--sc-violet:#7c3aed;--sc-red:#dc2626;--sc-ink:var(--text-main,var(--app-text,#111827));--sc-muted:var(--text-secondary,var(--app-muted,#6b7280));--sc-faint:#98a1ae;--sc-line:var(--panel-border,var(--app-line,#e5e7eb));--sc-card:var(--panel-bg,var(--app-card,#fff));--sc-subtle:color-mix(in srgb,var(--sc-card) 94%,var(--sc-line));color:var(--sc-ink);font-family:"Microsoft YaHei","PingFang SC","Segoe UI",sans-serif;letter-spacing:0}
      #${ROOT_ID} *{box-sizing:border-box;letter-spacing:0}#${ROOT_ID} button,#${ROOT_ID} select{font:inherit}.sc-shell{display:grid;gap:18px;max-width:1500px;margin:0 auto;padding-bottom:4px}.sc-icon{display:inline-grid;place-items:center;flex:0 0 auto;width:18px;height:18px}.sc-icon svg{width:100%;height:100%;fill:none;stroke:currentColor;stroke-linecap:round;stroke-linejoin:round;stroke-width:1.8}
      .sc-top{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:2px 0 0}.sc-title h1{margin:0;color:var(--sc-ink);font-size:20px;font-weight:750;line-height:1.35}.sc-title p{margin:4px 0 0;color:var(--sc-muted);font-size:12px}.sc-actions{display:flex;gap:8px}.sc-btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;height:36px;padding:0 13px;border:1px solid var(--sc-line);border-radius:7px;color:var(--sc-ink);background:var(--sc-card);font-size:12px;font-weight:650;cursor:pointer;transition:border-color .16s ease,background-color .16s ease,color .16s ease,box-shadow .16s ease,transform .12s ease}.sc-btn:hover:not(:disabled){border-color:color-mix(in srgb,var(--sc-primary) 44%,var(--sc-line));color:var(--sc-primary);background:color-mix(in srgb,var(--sc-card) 94%,var(--sc-primary))}.sc-btn:active:not(:disabled){transform:scale(.98)}.sc-btn-primary{border-color:var(--sc-primary);color:#fff;background:var(--sc-primary);box-shadow:0 3px 10px rgba(99,102,241,.2)}.sc-btn-primary:hover:not(:disabled){border-color:var(--sc-primary-strong);color:#fff;background:var(--sc-primary-strong)}.sc-btn:disabled{opacity:.62;cursor:wait}.sc-btn .sc-icon{width:15px;height:15px}
      .sc-controlbar{display:grid;grid-template-columns:minmax(220px,300px) auto 1fr;gap:18px;align-items:end;padding:14px 16px;border:1px solid var(--sc-line);border-radius:9px;background:var(--sc-card);box-shadow:0 1px 2px rgba(17,24,39,.025)}.sc-field{display:grid;gap:6px}.sc-label{color:var(--sc-muted);font-size:11px;font-weight:650}.sc-select{width:100%;height:36px;padding:0 32px 0 11px;border:1px solid var(--sc-line);border-radius:7px;color:var(--sc-ink);background:var(--sc-card);outline:0;cursor:pointer}.sc-select:focus{border-color:var(--sc-primary);box-shadow:0 0 0 3px rgba(99,102,241,.1)}.sc-periods{display:inline-flex;align-items:center;padding:3px;border:1px solid var(--sc-line);border-radius:8px;background:var(--sc-subtle)}.sc-segment{min-width:54px;height:29px;padding:0 10px;border:0;border-radius:6px;color:var(--sc-muted);background:transparent;font-size:12px;cursor:pointer;transition:color .16s ease,background-color .16s ease,box-shadow .16s ease}.sc-segment:hover{color:var(--sc-primary)}.sc-segment.active{color:var(--sc-primary);background:var(--sc-card);font-weight:700;box-shadow:0 1px 4px rgba(17,24,39,.12)}.sc-freshness{align-self:center;justify-self:end;color:var(--sc-muted);font-size:11px;text-align:right}.sc-freshness strong{color:var(--sc-ink);font-weight:600}
      .sc-kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));overflow:hidden;border:1px solid var(--sc-line);border-radius:9px;background:var(--sc-card)}.sc-kpi{--tone:var(--sc-primary);--tone-soft:rgba(99,102,241,.11);position:relative;display:grid;grid-template-columns:34px minmax(0,1fr);grid-template-areas:"icon label" "icon value" "note note";gap:2px 10px;min-width:0;padding:15px 16px}.sc-kpi+.sc-kpi{border-left:1px solid var(--sc-line)}.sc-kpi:nth-child(2){--tone:var(--sc-sky);--tone-soft:rgba(14,165,233,.1)}.sc-kpi:nth-child(3){--tone:var(--sc-violet);--tone-soft:rgba(139,92,246,.1)}.sc-kpi:nth-child(4){--tone:var(--sc-teal);--tone-soft:rgba(16,185,129,.11)}.sc-kpi:nth-child(5){--tone:var(--sc-amber);--tone-soft:rgba(245,158,11,.12)}.sc-kpi:nth-child(6){--tone:var(--sc-sky);--tone-soft:rgba(14,165,233,.1)}.sc-kpi-icon{grid-area:icon;display:grid;place-items:center;width:34px;height:34px;border-radius:9px;color:var(--tone);background:var(--tone-soft)}.sc-kpi-icon .sc-icon{width:17px;height:17px}.sc-kpi-label{grid-area:label;align-self:end;display:block;overflow:hidden;color:var(--sc-muted);font-size:11.5px;white-space:nowrap;text-overflow:ellipsis}.sc-kpi-value{grid-area:value;align-self:start;display:block;overflow:hidden;color:var(--tone);font-size:20px;font-weight:750;line-height:1.25;font-variant-numeric:tabular-nums;white-space:nowrap;text-overflow:ellipsis}.sc-kpi-note{grid-area:note;display:block;margin-top:8px;padding-top:8px;border-top:1px dashed color-mix(in srgb,var(--sc-line) 76%,transparent);color:var(--sc-faint);font-size:10px;line-height:1.45}
      .sc-nav{display:flex;align-items:center;justify-content:space-between;min-height:42px;border-bottom:1px solid var(--sc-line)}.sc-tabs{display:flex;align-items:center;gap:24px}.sc-tab{position:relative;height:42px;padding:0 1px;border:0;color:var(--sc-muted);background:transparent;font-size:12px;font-weight:600;cursor:pointer}.sc-tab:hover{color:var(--sc-ink)}.sc-tab.active{color:var(--sc-primary);font-weight:700}.sc-tab.active:after{position:absolute;right:0;bottom:-1px;left:0;height:2px;border-radius:999px;background:var(--sc-primary);content:""}.sc-context{color:var(--sc-muted);font-size:11px}
      .sc-section{overflow:hidden;border:1px solid var(--sc-line);border-radius:9px;background:var(--sc-card)}.sc-section-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 16px;border-bottom:1px solid var(--sc-line);background:color-mix(in srgb,var(--sc-card) 97%,var(--sc-line))}.sc-section-head h2{position:relative;margin:0;padding-left:10px;color:var(--sc-ink);font-size:14px;font-weight:700}.sc-section-head h2:before{position:absolute;top:2px;bottom:2px;left:0;width:3px;border-radius:999px;background:var(--sc-primary);content:""}.sc-section-head span{color:var(--sc-muted);font-size:11px}.sc-table-wrap{overflow:auto}.sc-table{width:100%;border-collapse:collapse;white-space:nowrap}.sc-table th,.sc-table td{height:45px;padding:10px 16px;border-bottom:1px solid color-mix(in srgb,var(--sc-line) 74%,transparent);font-size:12px;text-align:right;font-variant-numeric:tabular-nums}.sc-table th{height:39px;color:var(--sc-muted);font-size:11px;font-weight:650;background:var(--sc-subtle)}.sc-table th:first-child,.sc-table td:first-child{text-align:left}.sc-table tbody tr:last-child td{border-bottom:0}.sc-table tbody tr{cursor:pointer;transition:background-color .14s ease}.sc-table tbody tr:hover{background:color-mix(in srgb,var(--sc-card) 94%,var(--sc-primary))}.sc-shop-name{font-weight:650}.sc-shop-id{display:block;margin-top:2px;color:var(--sc-faint);font-size:10px}.sc-rank{display:inline-grid;width:21px;height:21px;margin-right:9px;place-items:center;border-radius:6px;color:var(--sc-muted);background:var(--sc-subtle);font-size:10px;font-weight:650}.sc-table tbody tr:nth-child(-n+3) .sc-rank{color:var(--sc-primary);background:rgba(99,102,241,.11)}.sc-positive{color:var(--sc-teal);font-weight:700}
      .sc-detail-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr))}.sc-detail{position:relative;min-width:0;padding:15px 16px;border-right:1px solid var(--sc-line);border-bottom:1px solid var(--sc-line)}.sc-detail:nth-child(4n){border-right:0}.sc-detail-name{color:var(--sc-muted);font-size:11px}.sc-detail-value{display:block;margin-top:6px;color:var(--sc-ink);font-size:18px;font-weight:700;font-variant-numeric:tabular-nums}.sc-detail-trend{display:inline-flex;margin-top:7px;padding:2px 6px;border-radius:5px;color:var(--sc-teal);background:rgba(16,185,129,.09);font-size:9px}.sc-empty{display:grid;place-items:center;min-height:170px;padding:30px 16px;text-align:center;color:var(--sc-muted);font-size:12px}.sc-status-list{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;padding:14px}.sc-status{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 13px;border:1px solid var(--sc-line);border-radius:8px;background:var(--sc-card);font-size:12px}.sc-status-info{display:flex;align-items:center;gap:9px;min-width:0}.sc-status-icon{display:grid;place-items:center;width:30px;height:30px;border-radius:8px;color:var(--sc-primary);background:rgba(99,102,241,.1)}.sc-status-icon .sc-icon{width:15px;height:15px}.sc-status strong.ok{color:var(--sc-teal)}.sc-status strong.fail{color:var(--sc-red)}.sc-status-badge{display:inline-flex;align-items:center;gap:5px;flex:0 0 auto;font-size:11px}.sc-status-badge:before{width:6px;height:6px;border-radius:50%;background:currentColor;content:""}
      .sc-loading{position:relative;pointer-events:none}.sc-loading:after{position:absolute;inset:0;z-index:10;display:grid;place-items:center;border-radius:9px;background:color-mix(in srgb,var(--sc-card) 82%,transparent);color:var(--sc-primary);font-size:12px;content:"数据加载中…"}
      @media(max-width:1150px){.sc-kpis{grid-template-columns:repeat(3,1fr)}.sc-kpi:nth-child(4){border-left:0}.sc-kpi:nth-child(n+4){border-top:1px solid var(--sc-line)}.sc-detail-grid{grid-template-columns:repeat(3,1fr)}.sc-detail:nth-child(4n){border-right:1px solid var(--sc-line)}.sc-detail:nth-child(3n){border-right:0}}
      @media(max-width:720px){.sc-shell{gap:13px}.sc-top{align-items:center}.sc-title h1{font-size:18px}.sc-title p{display:none}.sc-actions .sc-btn:not(.sc-btn-primary){display:none}.sc-btn{height:34px;padding:0 11px}.sc-controlbar{grid-template-columns:1fr;padding:12px;gap:11px}.sc-periods{display:grid;grid-template-columns:repeat(4,1fr);width:100%}.sc-segment{min-width:0;height:30px;padding:0 4px}.sc-freshness{justify-self:start;text-align:left}.sc-kpis{grid-template-columns:repeat(2,1fr)}.sc-kpi{padding:13px}.sc-kpi:nth-child(4){border-left:1px solid var(--sc-line)}.sc-kpi:nth-child(odd){border-left:0}.sc-kpi:nth-child(n+3){border-top:1px solid var(--sc-line)}.sc-kpi-value{font-size:18px}.sc-tabs{width:100%;justify-content:space-between;gap:0}.sc-tab{font-size:11.5px}.sc-context{display:none}.sc-section{border-right:0;border-left:0;border-radius:0}.sc-table{white-space:normal}.sc-table th:nth-child(3),.sc-table td:nth-child(3),.sc-table th:nth-child(5),.sc-table td:nth-child(5){display:none}.sc-table th,.sc-table td{padding:10px}.sc-table th:first-child,.sc-table td:first-child{min-width:145px}.sc-shop-id{max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.sc-detail-grid{grid-template-columns:repeat(2,1fr)}.sc-detail:nth-child(3n){border-right:1px solid var(--sc-line)}.sc-detail:nth-child(even){border-right:0}.sc-status-list{grid-template-columns:1fr}.sc-section-head{padding:12px}.sc-section-head span{max-width:50%;text-align:right}}
    `;
    document.head.append(style);
  }

  function button(label, iconName, className, handler) {
    const node = el("button", className || "sc-btn");
    node.type = "button";
    if (iconName) node.append(icon(iconName));
    node.append(el("span", "", label));
    node.onclick = handler;
    return node;
  }

  function renderHeader(root) {
    const top = el("header", "sc-top");
    const title = el("div", "sc-title");
    title.append(el("h1", "", "生意参谋"), el("p", "", "多店铺经营数据工作台"));
    const actions = el("div", "sc-actions");
    const refresh = button("刷新", "refresh", "sc-btn", load);
    const sync = button(state.syncing ? "同步中..." : "同步数据", "sync", "sc-btn sc-btn-primary", syncData);
    sync.disabled = state.syncing;
    actions.append(refresh, sync);
    top.append(title, actions);

    const controls = el("section", "sc-controlbar");
    const shopField = el("label", "sc-field");
    shopField.append(el("span", "sc-label", "店铺范围"));
    const select = el("select", "sc-select");
    select.append(new Option(`全部店铺（${state.shops.length}）`, ""));
    state.shops.forEach((shop) => select.append(new Option(shop.shopName || shop.shopId, shop.shopId)));
    select.value = state.shopId;
    select.onchange = () => { state.shopId = select.value; render(); };
    shopField.append(select);
    const periodField = el("div", "sc-field");
    periodField.append(el("span", "sc-label", "数据周期"));
    const periodBar = el("div", "sc-periods");
    periods.forEach(([value, label]) => {
      const segment = el("button", `sc-segment${state.period === value ? " active" : ""}`, label);
      segment.type = "button";
      segment.onclick = async () => { state.period = value; await load(); };
      periodBar.append(segment);
    });
    periodField.append(periodBar);
    const latest = selectedShops().reduce((last, shop) => !last || shop.collectedAt > last ? shop.collectedAt : last, "");
    const freshness = el("div", "sc-freshness");
    freshness.append(el("span", "", "数据更新 "), el("strong", "", dateTime(latest)));
    controls.append(shopField, periodField, freshness);
    root.append(top, controls);
  }

  function renderKpis(root, shops) {
    const uv = sum(shops, "uv"), pv = sum(shops, "pv"), cart = sum(shops, "cartByrCnt");
    const buyers = sum(shops, "payByrCnt"), amount = sum(shops, "payAmt");
    const rate = uv && buyers != null ? buyers / uv : null;
    const definitions = [
      ["访客数", number(uv), "覆盖店铺访问用户", "eye"],
      ["浏览量", number(pv), "页面浏览总量", "page"],
      ["加购人数", number(cart), cart == null ? "当前周期暂无该指标" : "产生加购的用户", "cart"],
      ["支付买家", number(buyers), "完成支付的用户", "users"],
      ["支付金额", money(amount), "成交支付金额", "money"],
      ["支付转化率", percent(rate), "支付买家 / 访客", "rate"],
    ];
    const grid = el("section", "sc-kpis");
    definitions.forEach(([label, value, note, iconName]) => {
      const item = el("div", "sc-kpi");
      const iconWrap = el("span", "sc-kpi-icon");
      iconWrap.append(icon(iconName));
      item.append(iconWrap, el("span", "sc-kpi-label", label), el("strong", "sc-kpi-value", value), el("span", "sc-kpi-note", note));
      grid.append(item);
    });
    root.append(grid);
  }

  function renderNavigation(root) {
    const nav = el("nav", "sc-nav");
    const tabs = el("div", "sc-tabs");
    [["overview", "店铺概览"], ["sources", "流量来源"], ["details", "详细指标"], ["status", "同步状态"]].forEach(([value, label]) => {
      const tab = el("button", `sc-tab${state.view === value ? " active" : ""}`, label);
      tab.type = "button";
      tab.onclick = () => { state.view = value; render(); };
      tabs.append(tab);
    });
    const periodLabel = periods.find(([value]) => value === state.period)?.[1] || "今日";
    nav.append(tabs, el("span", "sc-context", `${periodLabel} · ${state.shopId ? "单店" : `${state.shops.length} 家店铺`}`));
    root.append(nav);
  }

  function renderOverview(root, shops) {
    const section = el("section", "sc-section");
    const head = el("header", "sc-section-head");
    head.append(el("h2", "", "店铺经营表现"), el("span", "", state.shopId ? "当前店铺" : "按支付金额排序"));
    section.append(head);
    if (!shops.length) section.append(el("div", "sc-empty", "当前周期暂无正式数据"));
    else {
      const wrap = el("div", "sc-table-wrap");
      const table = el("table", "sc-table");
      table.innerHTML = "<thead><tr><th>店铺</th><th>支付金额</th><th>访客数</th><th>支付买家</th><th>转化率</th><th>客单价</th></tr></thead>";
      const body = el("tbody");
      [...shops].sort((a, b) => Number(valueOf(b, "payAmt") || 0) - Number(valueOf(a, "payAmt") || 0)).forEach((shop, index) => {
        const uv = valueOf(shop, "uv"), buyers = valueOf(shop, "payByrCnt"), amount = valueOf(shop, "payAmt");
        const row = el("tr");
        const name = el("td");
        name.innerHTML = `<span class="sc-rank">${index + 1}</span><span class="sc-shop-name"></span><span class="sc-shop-id"></span>`;
        name.querySelector(".sc-shop-name").textContent = shop.shopName || shop.shopId;
        name.querySelector(".sc-shop-id").textContent = shop.shopId;
        [money(amount), number(uv), number(buyers), percent(uv ? buyers / uv : null), money(buyers ? amount / buyers : null)].forEach((value, cellIndex) => row.append(el("td", cellIndex === 0 ? "sc-positive" : "", value)));
        row.prepend(name);
        row.onclick = () => { state.shopId = shop.shopId; render(); };
        body.append(row);
      });
      table.append(body); wrap.append(table); section.append(wrap);
    }
    root.append(section);
  }

  function sourceRows(shops) {
    const sources = new Map();
    shops.forEach((shop) => (Array.isArray(shop.sourceTree) ? shop.sourceTree : []).forEach((source) => {
      const name = source?.pageName?.value || "其他来源";
      const current = sources.get(name) || { name, uv: 0, buyers: 0, amount: 0 };
      current.uv += Number(source?.uv?.value || 0);
      current.buyers += Number(source?.payByrCnt?.value || 0);
      current.amount += Number(source?.payAmt?.value || 0);
      sources.set(name, current);
    }));
    return [...sources.values()].sort((a, b) => b.uv - a.uv);
  }

  function renderSources(root, shops) {
    const section = el("section", "sc-section");
    const head = el("header", "sc-section-head");
    head.append(el("h2", "", "流量来源构成"), el("span", "", state.period === "today" ? "实时来源数据" : "历史周期暂未采集来源明细"));
    section.append(head);
    const rows = state.period === "today" ? sourceRows(shops) : [];
    if (!rows.length) section.append(el("div", "sc-empty", state.period === "today" ? "暂无流量来源数据" : "该周期暂无流量来源明细"));
    else {
      const wrap = el("div", "sc-table-wrap"), table = el("table", "sc-table");
      table.innerHTML = "<thead><tr><th>来源渠道</th><th>访客数</th><th>支付买家</th><th>支付金额</th><th>转化率</th></tr></thead>";
      const body = el("tbody");
      rows.forEach((source) => {
        const row = el("tr");
        [source.name, number(source.uv), number(source.buyers), money(source.amount), percent(source.uv ? source.buyers / source.uv : null)].forEach((value) => row.append(el("td", "", value)));
        body.append(row);
      });
      table.append(body); wrap.append(table); section.append(wrap);
    }
    root.append(section);
  }

  const details = [
    ["itmUv", "商品访客", "number"], ["itmPv", "商品浏览", "number"], ["newUv", "新访客", "number"], ["oldUv", "老访客", "number"],
    ["cltCnt", "收藏次数", "number"], ["shopCltByrCnt", "店铺收藏人数", "number"], ["itmCltByrCnt", "商品收藏人数", "number"], ["crtByrCnt", "下单买家", "number"],
    ["payOrdCnt", "支付订单", "number"], ["uvValue", "访客价值", "money"], ["payPct", "客单价", "money"], ["crtRate", "下单转化率", "percent"],
  ];
  function renderDetails(root, shops) {
    const section = el("section", "sc-section");
    const head = el("header", "sc-section-head");
    head.append(el("h2", "", "详细经营指标"), el("span", "", "仅展示已采集指标"));
    section.append(head);
    const available = details.map(([field, label, type]) => ({ field, label, type, value: sum(shops, field) })).filter((item) => item.value != null);
    if (!available.length) section.append(el("div", "sc-empty", "当前数据没有更多指标"));
    else {
      const grid = el("div", "sc-detail-grid");
      available.forEach((item) => {
        const metric = el("div", "sc-detail");
        const formatted = item.type === "money" ? money(item.value) : item.type === "percent" ? percent(item.value) : number(item.value);
        metric.append(el("span", "sc-detail-name", item.label), el("strong", "sc-detail-value", formatted), el("span", "sc-detail-trend", "已采集"));
        grid.append(metric);
      });
      section.append(grid);
    }
    root.append(section);
  }

  function renderStatus(root) {
    const deviceSection = el("section", "sc-section");
    const deviceHead = el("header", "sc-section-head");
    deviceHead.append(el("h2", "", "采集设备"), el("span", "", `${state.devices.filter((item) => item.online).length} 台在线`));
    deviceSection.append(deviceHead);
    if (!state.devices.length) deviceSection.append(el("div", "sc-empty", "暂无采集设备"));
    else {
      const list = el("div", "sc-status-list");
      state.devices.forEach((device) => {
        const item = el("div", "sc-status");
        const infoWrap = el("div", "sc-status-info");
        const iconWrap = el("span", "sc-status-icon");
        iconWrap.append(icon("device"));
        const info = el("span");
        info.append(el("strong", "", device.deviceName || device.deviceId), el("small", "sc-shop-id", `${device.shopCount || 0} 家店铺 · ${dateTime(device.lastSeenAt)}`));
        infoWrap.append(iconWrap, info);
        item.append(infoWrap, el("strong", `sc-status-badge ${device.online ? "ok" : "fail"}`, device.online ? "在线" : "离线"));
        list.append(item);
      });
      deviceSection.append(list);
    }
    root.append(deviceSection);

    const section = el("section", "sc-section");
    const head = el("header", "sc-section-head");
    head.append(el("h2", "", "最近同步状态"), el("span", "", state.syncTask ? `任务 #${state.syncTask.id || "--"}` : "暂无任务"));
    section.append(head);
    const results = state.syncTask?.results;
    if (!Array.isArray(results) || !results.length) section.append(el("div", "sc-empty", "同步后将在这里显示每个店铺的结果"));
    else {
      const list = el("div", "sc-status-list");
      results.forEach((result) => {
        const item = el("div", "sc-status");
        item.append(el("span", "", result.shopName || result.shopId), el("strong", `sc-status-badge ${result.success ? "ok" : "fail"}`, result.success ? "成功" : "失败"));
        list.append(item);
      });
      section.append(list);
    }
    root.append(section);
  }

  function render() {
    const root = document.getElementById(ROOT_ID);
    if (!root) return;
    root.replaceChildren();
    const shell = el("div", `sc-shell${state.loading ? " sc-loading" : ""}`);
    shell.dataset.release = RELEASE;
    renderHeader(shell);
    const shops = selectedShops();
    renderKpis(shell, shops);
    renderNavigation(shell);
    if (state.view === "sources") renderSources(shell, shops);
    else if (state.view === "details") renderDetails(shell, shops);
    else if (state.view === "status") renderStatus(shell);
    else renderOverview(shell, shops);
    root.append(shell);
  }

  async function load() {
    state.loading = true;
    render();
    try {
      state.shops = await request(`/api/sycm/latest?period=${state.period}`);
      if (state.shopId && !state.shops.some((shop) => shop.shopId === state.shopId)) state.shopId = "";
      state.syncTask = await request("/api/sycm/sync-requests/latest").catch(() => state.syncTask);
      state.devices = await request("/api/sycm/collector-devices").catch(() => state.devices);
    } catch (error) {
      const root = document.getElementById(ROOT_ID);
      if (root) root.innerHTML = `<div class="sc-empty">${error.message || "数据加载失败"}</div>`;
      return;
    } finally {
      state.loading = false;
    }
    render();
  }

  async function syncData() {
    if (state.syncing) return;
    state.syncing = true;
    render();
    try {
      const task = await request("/api/sycm/sync-requests", { method: "POST" });
      state.syncTask = task;
      for (let attempt = 0; attempt < 90; attempt += 1) {
        const current = await request("/api/sycm/sync-requests/latest");
        state.syncTask = current;
        if (current?.id === task.id && current.status === "completed") { await load(); state.view = "status"; return; }
        if (current?.id === task.id && current.status === "failed") throw new Error(current.error || "采集端同步失败");
        await wait(2000);
      }
    } catch (error) {
      alert(error.message || "同步失败");
    } finally {
      state.syncing = false;
      render();
    }
  }

  function mount() {
    if (!location.pathname.includes("/sycm")) return;
    const native = document.querySelector(".sycm-page");
    if (!native) return;
    installStyle();
    let root = document.getElementById(ROOT_ID);
    if (!root) {
      root = el("div");
      root.id = ROOT_ID;
      native.replaceChildren(root);
      load();
    }
  }

  new MutationObserver(mount).observe(document.documentElement, { childList: true, subtree: true });
  addEventListener("popstate", mount);
  mount();
})();
