<script setup lang="ts">
import { CirclePlus, Delete, RefreshRight, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  createTaskBookkeepingOwner,
  deleteTaskBookkeepingOwner,
  fetchTaskBookkeepingOwners,
  fetchTaskBookkeepingRecords,
} from '../api'
import ListPaginationFooter from '../components/ListPaginationFooter.vue'
import { useViewport } from '../composables/useViewport'
import { useAuthStore } from '../stores/auth'
import type { TaskBookkeepingOwner, TaskBookkeepingRecord } from '../types/api'
import { formatDateTime } from '../utils/format'

const authStore = useAuthStore()
const { isMobile, viewportHeight } = useViewport()

const loading = ref(false)
const submitLoading = ref(false)
const dialogVisible = ref(false)
const keyword = ref('')
const currentPage = ref(1)
const statusText = ref('准备就绪')
const owners = ref<TaskBookkeepingOwner[]>([])
const records = ref<TaskBookkeepingRecord[]>([])
const pageSize = 20
const desktopTableHeight = computed(() => Math.max(420, viewportHeight.value - 360))

const form = reactive({
  name: '',
})

const canEdit = computed(() => {
  return authStore.canWrite('task_bookkeeping')
})

const usageCountMap = computed(() => {
  const map = new Map<string, number>()

  records.value.forEach((record) => {
    map.set(record.owner_name, (map.get(record.owner_name) ?? 0) + 1)
  })

  return map
})

const filteredOwners = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase()
  if (!normalizedKeyword) {
    return owners.value
  }

  return owners.value.filter((owner) => owner.name.toLowerCase().includes(normalizedKeyword))
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredOwners.value.length / pageSize)))

const paginatedOwners = computed(() => {
  const startIndex = (currentPage.value - 1) * pageSize
  return filteredOwners.value.slice(startIndex, startIndex + pageSize)
})

const statusDisplay = computed(() => {
  if (!keyword.value.trim()) {
    return statusText.value
  }

  return `关键词过滤：${keyword.value.trim()}`
})

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    return String(error.response?.data?.detail ?? error.message ?? fallback)
  }

  if (error instanceof Error && error.message) {
    return error.message
  }

  return fallback
}

function resetForm() {
  form.name = ''
}

async function loadData(message = '正在同步负责人名单...') {
  loading.value = true
  statusText.value = message

  try {
    const [ownerData, recordData] = await Promise.all([
      fetchTaskBookkeepingOwners(),
      fetchTaskBookkeepingRecords(),
    ])

    owners.value = ownerData
    records.value = recordData
    statusText.value = `已加载 ${ownerData.length} 个负责人`
  } catch (error) {
    const messageText = getErrorMessage(error, '加载负责人名单失败')
    statusText.value = messageText
    ElMessage.error(messageText)
  } finally {
    loading.value = false
  }
}

async function submitOwner() {
  submitLoading.value = true

  try {
    const name = form.name.trim()
    if (!name) {
      ElMessage.warning('负责人名称不能为空')
      return
    }

    await createTaskBookkeepingOwner({ name })
    dialogVisible.value = false
    ElMessage.success('负责人新增成功')
    await loadData('正在刷新负责人名单...')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '新增负责人失败'))
  } finally {
    submitLoading.value = false
  }
}

async function confirmDelete(owner: TaskBookkeepingOwner) {
  const usageCount = usageCountMap.value.get(owner.name) ?? 0
  const message = usageCount
    ? `负责人“${owner.name}”已关联 ${usageCount} 条历史任务记录，删除名单不会删除历史数据。确认继续吗？`
    : `确定删除负责人“${owner.name}”吗？`

  try {
    await ElMessageBox.confirm(message, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })

    await deleteTaskBookkeepingOwner(owner.id)
    ElMessage.success('删除成功')
    await loadData('正在刷新负责人名单...')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, '删除负责人失败'))
  }
}

watch(dialogVisible, (visible) => {
  if (!visible) {
    resetForm()
  }
})

watch(keyword, () => {
  currentPage.value = 1
})

watch(
  () => filteredOwners.value.length,
  () => {
    if (currentPage.value > totalPages.value) {
      currentPage.value = totalPages.value
    }
  },
)

onMounted(loadData)
</script>

<template>
  <div class="page-stack">
    <section class="page-block list-surface list-surface--fixed">
      <div class="filter-panel">
        <div class="query-grow">
          <div class="section-desc" style="margin-bottom: 8px">关键词查询</div>
          <el-input
            v-model="keyword"
            placeholder="搜索负责人名称"
            size="large"
            :prefix-icon="Search"
            clearable
          />
        </div>

        <div class="filter-status">
          <div class="section-desc" style="margin-bottom: 8px">系统状态</div>
          <div class="status-box" :title="statusDisplay">{{ statusDisplay }}</div>
        </div>
      </div>

      <div class="toolbar-row">
        <div>
          <h3 class="section-title">负责人管理</h3>
          <p class="section-desc">录入任务时可直接选择已有负责人，也支持后续逐步沉淀到名单里。</p>
        </div>

        <div class="toolbar-actions">
          <el-button type="primary" :icon="CirclePlus" :disabled="!canEdit" @click="dialogVisible = true">
            新增负责人
          </el-button>
          <el-button :icon="RefreshRight" @click="loadData('正在手动刷新负责人名单...')">刷新数据</el-button>
        </div>
      </div>

      <div v-if="!isMobile" class="table-area fixed-list-shell">
        <el-table :data="paginatedOwners" stripe :height="desktopTableHeight" v-loading="loading">
          <el-table-column prop="id" label="ID" width="72" sortable />
          <el-table-column prop="name" label="负责人名称" min-width="220" sortable />
          <el-table-column prop="record_count" label="已关联任务数" min-width="140" sortable>
            <template #default="{ row }">
              {{ usageCountMap.get(row.name) ?? 0 }}
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" min-width="180" sortable>
            <template #default="{ row }">
              {{ formatDateTime(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column v-if="canEdit" label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <div class="cell-actions">
                <el-button type="danger" link :icon="Delete" @click="confirmDelete(row)">删除</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <ListPaginationFooter
          v-model:current-page="currentPage"
          :total-pages="totalPages"
          :page-size="pageSize"
          :total-items="filteredOwners.length"
        />
      </div>

      <div v-else class="table-area fixed-list-shell">
        <div
          v-loading="loading"
          class="owner-card-list fixed-list-mobile"
        >
          <template v-if="filteredOwners.length">
            <article v-for="owner in paginatedOwners" :key="owner.id" class="owner-mobile-card">
              <div class="owner-mobile-card__head">
                <div>
                  <h4 class="owner-mobile-card__title">{{ owner.name }}</h4>
                  <p class="owner-mobile-card__meta">
                    ID {{ owner.id }} · {{ formatDateTime(owner.created_at) }}
                  </p>
                </div>
              </div>

              <div class="owner-mobile-card__field">
                <span class="owner-mobile-card__label">已关联任务数</span>
                <span class="owner-mobile-card__value">{{ usageCountMap.get(owner.name) ?? 0 }}</span>
              </div>

              <div v-if="canEdit" class="owner-mobile-card__actions">
                <el-button type="danger" plain :icon="Delete" @click="confirmDelete(owner)">
                  删除
                </el-button>
              </div>
            </article>
          </template>

          <el-empty
            v-else
            :description="keyword.trim() ? '没有匹配的负责人' : '暂无负责人'"
          />
        </div>

        <ListPaginationFooter
          v-model:current-page="currentPage"
          :total-pages="totalPages"
          :page-size="pageSize"
          :total-items="filteredOwners.length"
        />
      </div>
    </section>

    <el-dialog v-model="dialogVisible" title="新增负责人" width="520px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="负责人名称" required>
          <el-input v-model="form.name" placeholder="请输入负责人名称" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="submitOwner">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.owner-card-list {
  display: grid;
  gap: 12px;
  min-height: 180px;
}

.owner-mobile-card {
  display: grid;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--panel-border);
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: 0 10px 24px rgba(31, 41, 55, 0.06);
}

.owner-mobile-card__title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
}

.owner-mobile-card__meta {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
}

.owner-mobile-card__field {
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border: 1px solid #e6edf7;
  border-radius: 14px;
  background: #fbfdff;
}

.owner-mobile-card__label {
  color: var(--text-secondary);
  font-size: 12px;
}

.owner-mobile-card__value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
}

.owner-mobile-card__actions .el-button {
  width: 100%;
  margin: 0;
}
</style>
