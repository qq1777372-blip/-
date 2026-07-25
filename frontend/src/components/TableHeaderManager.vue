<script setup lang="ts">
import { ArrowDown, ArrowUp, Hide, Setting, View } from '@element-plus/icons-vue'

export interface ManagedTableColumn {
  key: string
  label: string
  minWidth: number
  visible: boolean
}

const props = defineProps<{ columns: ManagedTableColumn[] }>()
const emit = defineEmits<{
  (event: 'update:columns', value: ManagedTableColumn[]): void
  (event: 'save', value: ManagedTableColumn[]): void
}>()

const dialogVisible = defineModel<boolean>('visible', { default: false })

function update(columns: ManagedTableColumn[], save = true) {
  emit('update:columns', columns)
  if (save) emit('save', columns)
}

function move(index: number, offset: -1 | 1) {
  const target = index + offset
  if (target < 0 || target >= props.columns.length) return
  const columns = props.columns.map((column) => ({ ...column }))
  const [column] = columns.splice(index, 1)
  columns.splice(target, 0, column)
  update(columns)
}

function toggle(index: number) {
  const visibleCount = props.columns.filter((column) => column.visible).length
  if (props.columns[index].visible && visibleCount <= 1) return
  const columns = props.columns.map((column, current) => current === index ? { ...column, visible: !column.visible } : { ...column })
  update(columns)
}

function resize(index: number, value: number | undefined, save: boolean) {
  const columns = props.columns.map((column, current) => current === index
    ? { ...column, minWidth: Math.min(500, Math.max(100, Number(value) || 100)) }
    : { ...column })
  update(columns, save)
}
</script>

<template>
  <el-button type="success" plain :icon="Setting" @click="dialogVisible = true">表头管理</el-button>
  <el-dialog v-model="dialogVisible" title="表头管理" width="760px" destroy-on-close>
    <div class="managed-column-scroll">
      <div v-for="(column, index) in columns" :key="column.key" class="managed-column-card">
        <div class="managed-column-name">
          <strong>{{ column.label }}</strong>
          <small>{{ column.visible ? '列表显示' : '列表隐藏' }}</small>
        </div>
        <div class="managed-column-actions">
          <div class="managed-column-width">
            <span>列宽 {{ column.minWidth }}</span>
            <el-slider
              :model-value="column.minWidth"
              :min="100"
              :max="500"
              :step="10"
              @input="(value: number | undefined) => resize(index, value, false)"
              @change="(value: number | undefined) => resize(index, value, true)"
            />
          </div>
          <el-button :icon="ArrowUp" :disabled="index === 0" @click="move(index, -1)">上移</el-button>
          <el-button :icon="ArrowDown" :disabled="index === columns.length - 1" @click="move(index, 1)">下移</el-button>
          <el-button :icon="column.visible ? Hide : View" @click="toggle(index)">{{ column.visible ? '隐藏' : '显示' }}</el-button>
        </div>
      </div>
    </div>
    <template #footer><el-button type="primary" @click="dialogVisible = false">完成</el-button></template>
  </el-dialog>
</template>

<style scoped>
.managed-column-scroll { display: grid; gap: 12px; max-height: 480px; padding-right: 6px; overflow-y: auto; scrollbar-width: thin; }
.managed-column-card { display: grid; gap: 14px; padding: 14px 16px; border: 1px solid var(--panel-border); border-radius: 8px; background: #f8fafc; }
.managed-column-name { display: flex; justify-content: space-between; gap: 12px; }
.managed-column-name small { color: var(--text-secondary); }
.managed-column-actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
.managed-column-width { display: grid; grid-template-columns: 72px 160px; align-items: center; gap: 8px; margin-right: auto; color: var(--text-secondary); font-size: 12px; white-space: nowrap; }
</style>
