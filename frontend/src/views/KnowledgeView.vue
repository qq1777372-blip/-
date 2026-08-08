<script setup lang="ts">
import { computed, ref } from 'vue'

// 知识库是一个独立服务（knowledge-base.service，监听 127.0.0.1:8765），不是本项目
// FastAPI 的一部分，所以这里用 iframe 嵌它自己的页面，而不是重写一套前端。
// 转发规则见 deploy/nginx/xiaoxu.conf.template 里的 /knowledge/ 与 /knowledge-api/。
//
// 这个页面替代了原来的 frontend/public/knowledge-menu.js：那个脚本在运行时把一个
// 手写的 <li> 塞进 Element Plus 侧边栏，Vue 重新渲染菜单时会把它清掉，菜单因此时有
// 时无（dev 下基本不出现）。改成正常路由后由 Vue 自己管理，两个环境行为一致。
const views = [
  { id: 'ask', label: '知识问答' },
  { id: 'library', label: '知识管理' },
  { id: 'quality', label: '数据质量' },
] as const

type ViewKey = (typeof views)[number]['id']

const currentView = ref<ViewKey>('ask')

// 知识库页面自己会读 embedded/view 参数调整布局；app=0 表示这是 PC 控制台而非
// 手机客户端。加 v 参数是为了绕过它 no-cache 之外的浏览器缓存。
const frameSource = computed(
  () => `/knowledge/?embedded=1&view=${currentView.value}&app=0&v=20260808-pc3`,
)
</script>

<template>
  <section class="knowledge-view">
    <nav class="knowledge-tabs">
      <button
        v-for="item in views"
        :key="item.id"
        type="button"
        :class="{ 'is-active': currentView === item.id }"
        @click="currentView = item.id"
      >
        {{ item.label }}
      </button>
    </nav>
    <!-- key 绑定 currentView：切换 tab 时强制重建 iframe，避免知识库页面内部保留
         上一个视图的状态。 -->
    <iframe :key="currentView" :src="frameSource" title="AI 运营知识库" />
  </section>
</template>

<style scoped>
.knowledge-view {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: calc(100vh - 152px);
  min-height: 420px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  background: var(--el-bg-color);
}

.knowledge-tabs {
  flex: none;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 14px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color-overlay);
}

.knowledge-tabs button {
  padding: 8px 14px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--el-text-color-regular);
  cursor: pointer;
  font-size: 13px;
}

.knowledge-tabs button:hover {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.knowledge-tabs button.is-active {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  font-weight: 600;
}

.knowledge-view iframe {
  display: block;
  flex: 1;
  width: 100%;
  min-height: 0;
  border: 0;
  background: var(--el-bg-color-page);
}

@media (max-width: 768px) {
  .knowledge-view {
    height: calc(100vh - 128px);
    border: 0;
    border-radius: 0;
  }

  .knowledge-tabs {
    overflow-x: auto;
    flex-wrap: nowrap;
    scrollbar-width: none;
  }

  .knowledge-tabs::-webkit-scrollbar {
    display: none;
  }

  .knowledge-tabs button {
    flex: none;
  }
}
</style>
