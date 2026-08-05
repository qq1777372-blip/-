(() => {
  const itemMarker = 'data-knowledge-menu-item'
  const groupMarker = 'data-knowledge-menu-group'
  const panelMarker = 'data-knowledge-panel'
  const viewMarker = 'data-knowledge-view'
  const views = [
    { id: 'ask', label: '\u77e5\u8bc6\u95ee\u7b54' },
    { id: 'library', label: '\u77e5\u8bc6\u7ba1\u7406' },
    { id: 'quality', label: '\u6570\u636e\u8d28\u91cf' },
  ]
  let currentView = 'ask'

  if (window.location.pathname === '/ui/knowledge') {
    window.history.replaceState(null, '', '/ui/dashboard#knowledge')
  }

  const style = document.createElement('style')
  style.textContent = `
    .layout-main.knowledge-active { position: relative; min-height: calc(100vh - 86px); }
    .layout-main.knowledge-active > :not([data-knowledge-panel]) { visibility: hidden !important; }
    [data-knowledge-panel] { position: absolute; inset: 10px 24px 24px; display: flex; flex-direction: column; overflow: hidden; border: 1px solid #e5e7eb; border-radius: 12px; background: #f5f7fa; box-shadow: 0 8px 24px rgb(15 23 42 / 5%); z-index: 5; }
    [data-knowledge-tabs] { flex: none; display: flex; align-items: center; gap: 4px; min-height: 54px; padding: 8px 14px; border-bottom: 1px solid #ebeef5; background: #fff; }
    [data-knowledge-tabs] button { border: 0; border-radius: 6px; background: transparent; color: #606266; cursor: pointer; padding: 8px 14px; font-size: 13px; }
    [data-knowledge-tabs] button:hover { color: #409eff; background: #f5faff; }
    [data-knowledge-tabs] button.is-active { color: #409eff; background: #ecf5ff; font-weight: 600; }
    [data-knowledge-panel] iframe { display: block; flex: 1; width: 100%; min-height: 0; border: 0; background: #f5f7fa; }
    @media (max-width: 900px) { [data-knowledge-panel] { inset: 10px 16px 16px; } }
    html.app-client-mode [data-knowledge-panel] { position: fixed !important; inset: var(--ah) 0 var(--an) !important; width: auto !important; height: auto !important; border: 0 !important; border-radius: 0 !important; box-shadow: none !important; z-index: 9999 !important; }
    html.app-client-mode [data-knowledge-tabs] { min-height: 48px; padding: 6px 10px; overflow-x: auto; flex-wrap: nowrap; scrollbar-width: none; }
    html.app-client-mode [data-knowledge-tabs]::-webkit-scrollbar { display: none; }
    html.app-client-mode [data-knowledge-tabs] button { flex: none; padding: 8px 11px; }
  `
  document.head.appendChild(style)

  function isKnowledgeActive() { return window.location.hash === '#knowledge' }
  function knowledgeSource(view) {
    const appMode = document.documentElement.classList.contains('app-client-mode')
    return `/knowledge/?embedded=1&layout=2327&view=${view}&app=${appMode ? '1' : '0'}&v=20260801-app11`
  }
  function setView(view) {
    currentView = views.some((item) => item.id === view) ? view : 'ask'
    const panel = document.querySelector(`[${panelMarker}]`)
    if (!panel) return
    panel.querySelectorAll(`[${viewMarker}]`).forEach((button) => button.classList.toggle('is-active', button.dataset.knowledgeView === currentView))
    const iframe = panel.querySelector('iframe')
    const nextSrc = knowledgeSource(currentView)
    if (iframe && iframe.getAttribute('src') !== nextSrc) iframe.setAttribute('src', nextSrc)
    const title = document.querySelector('.layout-title')
    const nextTitle = views.find((item) => item.id === currentView)?.label || '\u77e5\u8bc6\u95ee\u7b54'
    if (title && title.textContent !== nextTitle) title.textContent = nextTitle
  }
  function openKnowledge(event, view = 'ask') { event.preventDefault(); currentView = view; if (!isKnowledgeActive()) window.history.pushState(null, '', window.location.pathname + window.location.search + '#knowledge'); renderKnowledgePanel() }
  function createMenuEntry() {
    const item = document.createElement('li')
    item.className = 'el-menu-item'
    item.setAttribute(groupMarker, 'true')
    item.setAttribute('role', 'menuitem')
    item.setAttribute('tabindex', '-1')
    item.innerHTML = `<i class="el-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M4 4h16v12H7.8L4 19.5V4Zm2 2v9.2l1.1-1.2H18V6H6Zm2 2h8v2H8V8Zm0 4h6v2H8v-2Z"/></svg></i><span>\u77e5\u8bc6\u5e93</span>`
    item.addEventListener('click', (event) => openKnowledge(event, 'ask'))
    return item
  }
  function installMenuItems() {
    document.querySelectorAll('.layout-menu').forEach((menu) => {
      if (!menu.dataset.knowledgeExitBound) {
        menu.dataset.knowledgeExitBound = 'true'
        menu.addEventListener('click', (event) => {
          const target = event.target.closest('.el-menu-item')
          if (!target || target.hasAttribute(groupMarker) || !isKnowledgeActive()) return
          window.history.replaceState(null, '', window.location.pathname + window.location.search)
          renderKnowledgePanel()
        }, true)
      }      if (menu.querySelector(`[${groupMarker}]`)) return
      const storeGroup = [...menu.querySelectorAll('.el-sub-menu')].find((group) => {
        const title = group.querySelector('.el-sub-menu__title')
        return title?.textContent?.trim() === '\u5e97\u94fa\u7ba1\u7406'
      })
      const submenu = storeGroup?.querySelector('.el-menu--inline')
      const entry = createMenuEntry()
      if (submenu) {
        submenu.appendChild(entry)
        storeGroup.classList.add('is-opened')
      } else {
        menu.appendChild(entry)
      }
    })
  }
  function renderKnowledgePanel() {
    const main = document.querySelector('.layout-main')
    const active = isKnowledgeActive()
    document.querySelectorAll(`[${groupMarker}]`).forEach((item) => item.classList.toggle('is-active', active))
    if (active) document.querySelectorAll(`.layout-menu .el-menu-item:not([${groupMarker}])`).forEach((item) => item.classList.remove('is-active'))
    if (!main) return
    const existingPanel = main.querySelector(`[${panelMarker}]`)
    if (!active) { existingPanel?.remove(); main.classList.remove('knowledge-active'); return }
    main.classList.add('knowledge-active')
    if (!existingPanel) {
      const panel = document.createElement('section')
      panel.setAttribute(panelMarker, 'true')
      panel.innerHTML = `<nav data-knowledge-tabs>${views.map((view) => `<button type="button" data-knowledge-view="${view.id}">${view.label}</button>`).join('')}</nav><iframe src="${knowledgeSource(currentView)}" title="AI \u8fd0\u8425\u77e5\u8bc6\u5e93"></iframe>`
      panel.querySelectorAll(`[${viewMarker}]`).forEach((button) => button.addEventListener('click', () => setView(button.dataset.knowledgeView)))
      main.appendChild(panel)
    }
    setView(currentView)
    const breadcrumb = document.querySelector('.layout-breadcrumb')
    if (breadcrumb && breadcrumb.textContent !== 'AI \u8fd0\u8425\u77e5\u8bc6\u5e93') breadcrumb.textContent = 'AI \u8fd0\u8425\u77e5\u8bc6\u5e93'
  }
  function syncKnowledgeUi() { installMenuItems(); renderKnowledgePanel() }
  const observer = new MutationObserver(syncKnowledgeUi)
  observer.observe(document.documentElement, { childList: true, subtree: true })
  window.addEventListener('DOMContentLoaded', syncKnowledgeUi)
  window.addEventListener('hashchange', syncKnowledgeUi)
  window.addEventListener('popstate', syncKnowledgeUi)
  syncKnowledgeUi()
})()
