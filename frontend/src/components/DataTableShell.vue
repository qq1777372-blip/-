<script setup lang="ts">
withDefaults(
  defineProps<{
    loading?: boolean
    empty?: boolean
    minHeight?: number
  }>(),
  {
    loading: false,
    empty: false,
    minHeight: 420,
  },
)
</script>

<template>
  <section class="data-table-shell">
    <header v-if="$slots.filters" class="data-table-shell__filters">
      <slot name="filters" />
    </header>

    <div v-if="$slots.toolbar" class="data-table-shell__toolbar">
      <slot name="toolbar" />
    </div>

    <div
      v-loading="loading"
      class="data-table-shell__body"
      :style="{ minHeight: `${minHeight}px` }"
    >
      <slot v-if="!empty" />
      <slot v-else name="empty">
        <el-empty description="暂无数据" />
      </slot>
    </div>

    <footer v-if="$slots.footer" class="data-table-shell__footer">
      <slot name="footer" />
    </footer>
  </section>
</template>

<style scoped>
.data-table-shell {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
  border: 1px solid var(--ui-border);
  border-radius: var(--ui-radius-panel);
  background: var(--ui-surface);
}

.data-table-shell__filters {
  padding: var(--ui-space-5);
  border-bottom: 1px solid var(--ui-border);
}

.data-table-shell__toolbar {
  padding: var(--ui-space-4) var(--ui-space-5);
}

.data-table-shell__body {
  min-width: 0;
  overflow: auto;
  padding: 0 var(--ui-space-5);
}

.data-table-shell__footer {
  padding: var(--ui-space-3) var(--ui-space-5) var(--ui-space-4);
  background: var(--ui-surface);
}

@media (max-width: 768px) {
  .data-table-shell__filters,
  .data-table-shell__toolbar,
  .data-table-shell__body,
  .data-table-shell__footer {
    padding-left: var(--ui-space-3);
    padding-right: var(--ui-space-3);
  }
}
</style>
