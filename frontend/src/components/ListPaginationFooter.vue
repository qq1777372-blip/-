<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    currentPage: number
    totalPages: number
    pageSize: number
    totalItems: number
    itemUnit?: string
    showPagination?: boolean
  }>(),
  {
    itemUnit: '条',
    showPagination: true,
  },
)

const emit = defineEmits<{
  (event: 'update:currentPage', value: number): void
}>()

const shouldShowPagination = computed(() => props.showPagination)
</script>

<template>
  <div class="list-pagination-footer">
    <div class="list-pagination-footer__summary">
      <span class="list-pagination-footer__badge">共 {{ totalItems }} {{ itemUnit }}</span>
      <span>第 {{ currentPage }} / {{ totalPages }} 页</span>
      <span>每页 {{ pageSize }} {{ itemUnit }}</span>
    </div>

    <el-pagination
      v-if="shouldShowPagination"
      :current-page="currentPage"
      :page-size="pageSize"
      :total="totalItems"
      layout="prev, pager, next"
      background
      @update:current-page="emit('update:currentPage', $event)"
    />
  </div>
</template>

<style scoped>
.list-pagination-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 14px 0 2px;
  border-top: 1px solid rgba(226, 232, 240, 0.82);
}

.list-pagination-footer__summary {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  color: #64748b;
  font-size: 12px;
}

.list-pagination-footer__summary span {
  display: inline-flex;
  align-items: center;
}

.list-pagination-footer__summary span + span::before {
  content: '';
  width: 4px;
  height: 4px;
  margin-right: 10px;
  border-radius: 999px;
  background: #cbd5e1;
}

.list-pagination-footer__badge {
  min-height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1677ff;
  font-weight: 700;
}

.list-pagination-footer__summary .list-pagination-footer__badge::before {
  content: none;
  margin-right: 0;
}

.list-pagination-footer :deep(.el-pagination) {
  margin-left: auto;
}

.list-pagination-footer :deep(.el-pager li),
.list-pagination-footer :deep(.btn-prev),
.list-pagination-footer :deep(.btn-next) {
  min-width: 34px;
  height: 34px;
  border-radius: 10px;
}

@media (max-width: 768px) {
  .list-pagination-footer {
    padding-top: 12px;
  }

  .list-pagination-footer :deep(.el-pagination) {
    margin-left: 0;
  }
}
</style>
