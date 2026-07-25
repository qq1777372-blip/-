<script setup lang="ts">
import { CirclePlus, Delete, EditPen, RefreshRight, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { deleteSavedLink, fetchSavedLinks } from '../api'
import type { SavedLink } from '../types/api'
import { formatDateTime } from '../utils/format'
import {
  getTutorialDocCategoryLabel,
  getTutorialDocExcerpt,
  getTutorialDocPlainText,
  isTutorialDoc,
} from '../utils/tutorialDocs'

const router = useRouter()

const loading = ref(false)
const keyword = ref('')
const docs = ref<SavedLink[]>([])

const filteredDocs = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase()
  if (!normalizedKeyword) {
    return docs.value
  }

  return docs.value.filter((doc) =>
    [
      doc.title,
      getTutorialDocCategoryLabel(doc.category),
      getTutorialDocPlainText(doc.description),
      doc.author_username,
    ]
      .join(' ')
      .toLowerCase()
      .includes(normalizedKeyword),
  )
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

function getWordCount(doc: SavedLink) {
  return getTutorialDocPlainText(doc.description).length
}

function openCreatePage() {
  const openedWindow = window.open(router.resolve({ name: 'tutorial-docs-editor-new' }).href, '_blank')

  if (openedWindow) {
    openedWindow.focus()
    return
  }

  router.push({ name: 'tutorial-docs-editor-new' })
}

function openEditPage(doc: SavedLink) {
  const openedWindow = window.open(
    router.resolve({ name: 'tutorial-docs-editor-edit', params: { id: doc.id } }).href,
    '_blank',
  )

  if (openedWindow) {
    openedWindow.focus()
    return
  }

  router.push({ name: 'tutorial-docs-editor-edit', params: { id: doc.id } })
}

async function loadDocs() {
  loading.value = true

  try {
    const data = await fetchSavedLinks()
    docs.value = data.filter(isTutorialDoc)
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '加载教程文档失败'))
  } finally {
    loading.value = false
  }
}

async function confirmDelete(doc: SavedLink) {
  try {
    await ElMessageBox.confirm(
      `确定删除《${doc.title}》吗？删除后无法恢复。`,
      '删除教程文档',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      },
    )

    await deleteSavedLink(doc.id)
    docs.value = docs.value.filter((item) => item.id !== doc.id)
    ElMessage.success('教程文档已删除')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, '删除教程文档失败'))
  }
}

onMounted(loadDocs)
</script>

<template>
  <div class="page-stack">
    <section class="page-block tutorial-docs-board" v-loading="loading">
      <div class="tutorial-docs-board__topbar">
        <div class="tutorial-docs-board__heading">
          <h2 class="section-title">教程文档中心</h2>
          <p class="section-desc">
            在这里管理教程正文。新建后会进入专门的 Markdown 编辑页，支持左侧编写、右侧实时预览。
          </p>
        </div>

        <div class="tutorial-docs-board__actions">
          <el-input
            v-model="keyword"
            class="tutorial-docs-search"
            clearable
            placeholder="搜索标题、分类或正文"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>

          <el-button :icon="RefreshRight" @click="loadDocs">刷新</el-button>
          <el-button type="primary" :icon="CirclePlus" @click="openCreatePage">新建教程</el-button>
        </div>
      </div>

      <div class="tutorial-docs-board__summary">
        <span>共 {{ docs.length }} 篇教程</span>
        <span v-if="keyword.trim()">筛选后 {{ filteredDocs.length }} 篇</span>
      </div>

      <div v-if="filteredDocs.length" class="tutorial-docs-grid">
        <article v-for="doc in filteredDocs" :key="doc.id" class="tutorial-doc-card">
          <div class="tutorial-doc-card__meta">
            <span class="tutorial-doc-card__category">{{ getTutorialDocCategoryLabel(doc.category) }}</span>
            <span class="tutorial-doc-card__time">更新于 {{ formatDateTime(doc.updated_at) }}</span>
          </div>

          <h3 class="tutorial-doc-card__title">{{ doc.title }}</h3>

          <p class="tutorial-doc-card__excerpt">
            {{ getTutorialDocExcerpt(doc.description, 160) || '这篇教程还没有正文内容。' }}
          </p>

          <div class="tutorial-doc-card__footer">
            <div class="tutorial-doc-card__stats">
              <span>{{ getWordCount(doc) }} 字</span>
              <span>{{ doc.images.length }} 张图</span>
              <span>作者 {{ doc.author_username }}</span>
            </div>

            <div class="tutorial-doc-card__actions">
              <el-button text type="primary" :icon="EditPen" @click="openEditPage(doc)">继续写</el-button>
              <el-button text type="danger" :icon="Delete" @click="confirmDelete(doc)">删除</el-button>
            </div>
          </div>
        </article>
      </div>

      <el-empty
        v-else
        :description="keyword.trim() ? '没有匹配的教程文档' : '还没有教程文档，先新建一篇吧'"
      />
    </section>
  </div>
</template>

<style scoped>
.tutorial-docs-board {
  padding: 24px;
}

.tutorial-docs-board__topbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;
}

.tutorial-docs-board__heading {
  display: grid;
  gap: 8px;
}

.tutorial-docs-board__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  flex: 1 1 420px;
  flex-wrap: wrap;
}

.tutorial-docs-search {
  width: min(100%, 320px);
}

.tutorial-docs-board__summary {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: 14px;
  color: var(--text-secondary);
  font-size: 13px;
}

.tutorial-docs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 18px;
  margin-top: 22px;
}

.tutorial-doc-card {
  display: grid;
  gap: 14px;
  padding: 18px;
  border: 1px solid var(--panel-border);
  border-radius: 20px;
  background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.06);
}

.tutorial-doc-card__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.tutorial-doc-card__category {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  background: #ecf5ff;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
}

.tutorial-doc-card__time {
  color: var(--text-secondary);
  font-size: 12px;
}

.tutorial-doc-card__title {
  margin: 0;
  color: var(--text-primary);
  font-size: 20px;
  line-height: 1.35;
}

.tutorial-doc-card__excerpt {
  margin: 0;
  color: #475569;
  line-height: 1.8;
  min-height: 88px;
  white-space: pre-wrap;
  word-break: break-word;
}

.tutorial-doc-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
  padding-top: 14px;
  border-top: 1px solid rgba(226, 232, 240, 0.9);
}

.tutorial-doc-card__stats {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 12px;
}

.tutorial-doc-card__actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.tutorial-doc-card__actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

@media (max-width: 768px) {
  .tutorial-docs-board {
    padding: 16px;
  }

  .tutorial-docs-board__actions {
    justify-content: flex-start;
  }

  .tutorial-doc-card__footer {
    align-items: flex-start;
  }
}
</style>
