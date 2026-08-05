<script setup lang="ts">
import { ArrowLeft, EditPen, Link, PictureFilled, Top } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchSavedLinks } from '../api'
import { useAuthStore } from '../stores/auth'
import type { SavedLink } from '../types/api'
import { formatDateTime } from '../utils/format'
import {
  estimateReadingMinutes,
  extractUrlsFromText,
  getAuthorInitial,
  getPrimaryUrlFromSavedLink,
  getReaderCategoryStats,
  getReaderRelatedLinks,
  isValidHttpUrl,
} from '../utils/readerDetail'
import { renderSavedLinkMarkdown } from '../utils/savedLinkMarkdown'
import {
  getTutorialDocCategoryLabel,
  getTutorialDocExcerpt,
  getTutorialDocPlainText,
  isTutorialDoc,
  stripTutorialDocCategory,
} from '../utils/tutorialDocs'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const loading = ref(false)
const article = ref<SavedLink | null>(null)
const allLinks = ref<SavedLink[]>([])

function looksLikeHtml(value: string | null | undefined) {
  const normalized = String(value ?? '').trim()
  if (!normalized) {
    return false
  }

  return /<\/?[a-z][\s\S]*>/i.test(normalized)
}

const articleHtml = computed(() => {
  const description = article.value?.description ?? ''
  return looksLikeHtml(description) ? description : renderSavedLinkMarkdown(description)
})

const authorName = computed(() => {
  const currentArticle = article.value
  if (!currentArticle) {
    return ''
  }

  const currentUser = authStore.currentUser
  if (currentUser && currentUser.id === currentArticle.author_user_id) {
    return currentUser.display_name?.trim() || currentUser.username
  }

  return currentArticle.author_username
})

const authorAvatarUrl = computed(() => {
  const currentArticle = article.value
  if (!currentArticle) {
    return null
  }

  const currentUser = authStore.currentUser
  if (currentUser && currentUser.id === currentArticle.author_user_id) {
    return currentUser.avatar_url
  }

  return currentArticle.author_avatar_url
})

const backButtonText = computed(() => {
  if (window.opener && !window.opener.closed) {
    return '关闭窗口'
  }

  return '返回链接广场'
})

const categoryLabel = computed(() =>
  getTutorialDocCategoryLabel(stripTutorialDocCategory(article.value?.category)),
)
const primaryUrl = computed(() => getPrimaryUrlFromSavedLink(article.value))
const articlePlainText = computed(() => getTutorialDocPlainText(article.value?.description ?? ''))
const articleExcerpt = computed(() => {
  const excerpt = getTutorialDocExcerpt(article.value?.description ?? '', 120)
  const title = article.value?.title?.trim() ?? ''
  return excerpt && excerpt !== title ? excerpt : ''
})
const readingMinutes = computed(() => estimateReadingMinutes(articlePlainText.value))
const contentLength = computed(() => articlePlainText.value.replace(/\s+/g, '').trim().length)
const contentLinkCount = computed(() => {
  const currentArticle = article.value
  if (!currentArticle) {
    return 0
  }

  const urls = new Set(extractUrlsFromText(currentArticle.description))
  const normalizedUrl = currentArticle.url?.trim() ?? ''
  if (normalizedUrl && isValidHttpUrl(normalizedUrl)) {
    urls.add(normalizedUrl)
  }

  return urls.size
})
const authorEntryCount = computed(() => {
  const currentArticle = article.value
  if (!currentArticle) {
    return 0
  }

  return allLinks.value.filter((item) => item.author_user_id === currentArticle.author_user_id).length
})
const relatedLinks = computed(() => getReaderRelatedLinks(article.value, allLinks.value, 5))
const categoryStats = computed(() => getReaderCategoryStats(allLinks.value, true, 8))
const canEdit = computed(() => {
  const currentUser = authStore.currentUser
  const currentArticle = article.value
  if (!currentUser || !currentArticle) {
    return false
  }

  return authStore.canWrite('links') && (currentUser.role === 'superadmin' || currentUser.id === currentArticle.author_user_id)
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

function getUrlHost(value: string | null | undefined) {
  if (!value) {
    return '无外部链接'
  }

  try {
    return new URL(value).hostname.replace(/^www\./, '') || '无外部链接'
  } catch {
    return '无外部链接'
  }
}

async function loadArticle() {
  const articleId = Number(route.params.id)
  if (!Number.isFinite(articleId) || articleId <= 0) {
    await router.replace({ name: 'links' })
    return
  }

  loading.value = true
  try {
    const data = await fetchSavedLinks()
    allLinks.value = data

    const target = data.find((item) => item.id === articleId && isTutorialDoc(item))
    if (!target) {
      throw new Error('未找到对应文章')
    }

    article.value = target
    document.title = `${target.title} - 阅读全文`
    window.scrollTo({ top: 0 })
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '加载文章失败'))
    await router.replace({ name: 'links' })
  } finally {
    loading.value = false
  }
}

function goBack() {
  if (window.opener && !window.opener.closed) {
    window.close()
    return
  }

  if (window.history.length > 1) {
    router.back()
    return
  }

  void router.push({ name: 'links' })
}

function editArticle() {
  if (!article.value) {
    return
  }

  const target = router.resolve({ name: 'tutorial-docs-editor-edit', params: { id: article.value.id } })
  const openedWindow = window.open(target.href, '_blank')

  if (openedWindow) {
    openedWindow.focus()
    return
  }

  void router.push({ name: 'tutorial-docs-editor-edit', params: { id: article.value.id } })
}

function openExternal() {
  if (!primaryUrl.value) {
    return
  }

  window.open(primaryUrl.value, '_blank', 'noopener,noreferrer')
}

function openPrimaryImage() {
  const currentArticle = article.value
  if (!currentArticle?.images.length) {
    return
  }

  window.open(currentArticle.images[0].url, '_blank', 'noopener,noreferrer')
}

function openRelatedLink(link: SavedLink) {
  const target = isTutorialDoc(link)
    ? { name: 'tutorial-docs-reader' as const, params: { id: link.id } }
    : { name: 'links-reader' as const, params: { id: link.id } }

  void router.push(target)
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => {
  void loadArticle()
})

watch(
  () => route.params.id,
  (currentId, previousId) => {
    if (currentId !== previousId) {
      void loadArticle()
    }
  },
)
</script>

<template>
  <div class="page-stack">
    <section class="page-block reader-shell" v-loading="loading">
      <template v-if="article">
        <div class="reader-frame">
          <header class="reader-page-head">
            <div class="reader-page-head__main">
              <div class="reader-page-head__crumb">
                <el-button text :icon="ArrowLeft" @click="goBack">{{ backButtonText }}</el-button>
                <span>链接广场</span>
                <span>教程文章</span>
              </div>

              <strong class="reader-page-head__title">{{ article.title }}</strong>
            </div>

            <div class="reader-page-head__actions">
              <el-button v-if="primaryUrl" plain @click="openExternal">打开原链</el-button>
              <el-button v-if="canEdit" plain @click="editArticle">编辑</el-button>
            </div>
          </header>

          <div class="reader-layout">
            <aside class="reader-floatbar" aria-label="阅读操作">
              <button type="button" class="reader-floatbar__item" :title="backButtonText" @click="goBack">
                <el-icon><ArrowLeft /></el-icon>
              </button>
              <button
                v-if="primaryUrl"
                type="button"
                class="reader-floatbar__item"
                title="打开原始链接"
                @click="openExternal"
              >
                <el-icon><Link /></el-icon>
              </button>
              <button
                v-if="article.images.length"
                type="button"
                class="reader-floatbar__item"
                title="查看主图"
                @click="openPrimaryImage"
              >
                <el-icon><PictureFilled /></el-icon>
              </button>
              <button type="button" class="reader-floatbar__item" title="回到顶部" @click="scrollToTop">
                <el-icon><Top /></el-icon>
              </button>
              <button
                v-if="canEdit"
                type="button"
                class="reader-floatbar__item"
                title="编辑文章"
                @click="editArticle"
              >
                <el-icon><EditPen /></el-icon>
              </button>
            </aside>

            <div class="reader-main">
              <section class="reader-post-card">
                <div class="reader-post-card__head">
                  <div class="reader-post-card__headline">
                    <div class="reader-post-card__labels">
                      <span class="reader-post-card__badge">{{ categoryLabel }}</span>
                      <span class="reader-post-card__type">教程文章</span>
                    </div>

                    <div class="reader-post-card__actions">
                      <el-button v-if="primaryUrl" text type="primary" @click="openExternal">
                        打开原链
                      </el-button>
                      <el-button v-if="canEdit" text @click="editArticle">编辑</el-button>
                    </div>
                  </div>

                  <h1 class="reader-post-card__title">{{ article.title }}</h1>

                  <div class="reader-post-card__meta">
                    <div class="reader-post-card__author">
                      <span class="reader-post-card__author-avatar">
                        <img
                          v-if="authorAvatarUrl"
                          :src="authorAvatarUrl || ''"
                          :alt="authorName"
                          class="reader-post-card__author-avatar-image"
                        />
                        <span v-else class="reader-post-card__author-avatar-fallback">
                          {{ getAuthorInitial(authorName) }}
                        </span>
                      </span>
                      <strong>{{ authorName }}</strong>
                    </div>

                    <span>{{ formatDateTime(article.created_at) }}</span>
                    <span>阅读 {{ readingMinutes }} 分钟</span>
                    <span>{{ contentLength }} 字</span>
                  </div>
                </div>

                <div v-if="articleExcerpt" class="reader-post-card__summary">
                  {{ articleExcerpt }}
                </div>

                <div class="reader-post-card__section">
                  <div class="reader-post-card__section-title">
                    <span></span>
                    <strong>正文内容</strong>
                  </div>

                  <div class="reader-post-card__content">
                    <article v-if="articleHtml" class="reader-content" v-html="articleHtml"></article>

                    <article v-else class="reader-empty">
                      <strong>暂无正文内容</strong>
                      <span>这篇文章还没有填入正文。</span>
                    </article>
                  </div>
                </div>
              </section>

              <aside class="reader-sidebar">
                <section class="reader-sidecard reader-sidecard--author">
                  <div class="reader-author-card">
                    <div class="reader-author-card__top">
                      <span class="reader-author-card__avatar">
                        <img
                          v-if="authorAvatarUrl"
                          :src="authorAvatarUrl || ''"
                          :alt="authorName"
                          class="reader-author-card__avatar-image"
                        />
                        <span v-else class="reader-author-card__avatar-fallback">
                          {{ getAuthorInitial(authorName) }}
                        </span>
                      </span>

                      <div class="reader-author-card__identity">
                        <strong>{{ authorName }}</strong>
                        <span>{{ categoryLabel }}</span>
                      </div>
                    </div>

                    <div class="reader-author-card__stats">
                      <div>
                        <strong>{{ authorEntryCount }}</strong>
                        <span>作者内容</span>
                      </div>
                      <div>
                        <strong>{{ contentLinkCount || 0 }}</strong>
                        <span>链接线索</span>
                      </div>
                      <div>
                        <strong>{{ article.images.length }}</strong>
                        <span>配图数量</span>
                      </div>
                    </div>

                    <div class="reader-author-card__info">
                      <span>发布时间：{{ formatDateTime(article.created_at) }}</span>
                      <span>来源站点：{{ getUrlHost(primaryUrl) }}</span>
                    </div>

                    <div class="reader-author-card__actions">
                      <el-button v-if="primaryUrl" type="primary" @click="openExternal">打开原链</el-button>
                      <el-button v-if="canEdit" plain @click="editArticle">编辑文章</el-button>
                    </div>
                  </div>
                </section>

                <section class="reader-sidecard">
                  <div class="reader-sidecard__head">
                    <strong>相关推荐</strong>
                    <span>{{ relatedLinks.length }} 条</span>
                  </div>

                  <div v-if="relatedLinks.length" class="reader-related-list">
                    <button
                      v-for="item in relatedLinks"
                      :key="item.id"
                      type="button"
                      class="reader-related-item"
                      @click="openRelatedLink(item)"
                    >
                      <strong class="reader-related-item__title">{{ item.title }}</strong>
                      <span class="reader-related-item__meta">
                        {{ getTutorialDocCategoryLabel(stripTutorialDocCategory(item.category)) }} ·
                        {{ formatDateTime(item.updated_at) }}
                      </span>
                    </button>
                  </div>

                  <div v-else class="reader-empty reader-empty--compact">
                    <strong>暂无推荐</strong>
                    <span>当前分类下还没有更多相近文章。</span>
                  </div>
                </section>

                <section class="reader-sidecard">
                  <div class="reader-sidecard__head">
                    <strong>热门分类</strong>
                    <span>教程文章</span>
                  </div>

                  <div class="reader-topic-list">
                    <div v-for="(item, index) in categoryStats" :key="item.label" class="reader-topic-item">
                      <div class="reader-topic-item__main">
                        <em>{{ index + 1 }}</em>
                        <span>{{ item.label }}</span>
                      </div>
                      <strong>{{ item.count }}</strong>
                    </div>
                  </div>
                </section>
              </aside>
            </div>
          </div>
        </div>
      </template>
    </section>
  </div>
</template>

<style scoped>
.reader-shell {
  overflow: visible;
  padding: 14px 20px 40px;
  background: #f5f7fb;
}

.reader-frame {
  max-width: 1320px;
  margin: 0 auto;
  display: grid;
  gap: 14px;
}

.reader-page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  min-height: 58px;
  padding: 12px 16px;
  border: 1px solid #edf1f5;
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
}

.reader-page-head__main {
  display: flex;
  align-items: center;
  min-width: 0;
  flex: 1 1 auto;
}

.reader-page-head__crumb {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  color: #86909c;
  font-size: 13px;
  min-width: 0;
}

.reader-page-head__crumb span + span::before {
  content: '/';
  margin-right: 10px;
  color: #c9cdd4;
}

.reader-page-head__title {
  display: none;
}

.reader-page-head__crumb span:last-child {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  background: #f2f3f5;
  color: #4e5969;
}

.reader-page-head__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.reader-layout {
  display: grid;
  grid-template-columns: 62px minmax(0, 1fr);
  gap: 22px;
  align-items: start;
}

.reader-floatbar {
  position: sticky;
  top: 120px;
  display: grid;
  gap: 14px;
}

.reader-floatbar__item {
  display: inline-grid;
  place-items: center;
  width: 46px;
  height: 46px;
  padding: 0;
  border: 1px solid #edf1f5;
  border-radius: 999px;
  background: #ffffff;
  color: #4e5969;
  cursor: pointer;
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.06);
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    color 0.18s ease;
}

.reader-floatbar__item:hover {
  transform: translateY(-1px);
  color: #1677ff;
  box-shadow: 0 10px 20px rgba(22, 119, 255, 0.12);
}

.reader-floatbar__item :deep(.el-icon) {
  font-size: 18px;
}

.reader-main {
  display: grid;
  grid-template-columns: minmax(0, 820px) 280px;
  gap: 22px;
  justify-content: center;
  align-items: start;
}

.reader-post-card,
.reader-sidecard {
  border: 1px solid #edf1f5;
  border-radius: 16px;
  background: #ffffff;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
}

.reader-post-card {
  padding: 28px 32px 34px;
}

.reader-post-card__head {
  display: grid;
  gap: 18px;
}

.reader-post-card__headline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.reader-post-card__labels {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.reader-post-card__badge {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1677ff;
  font-size: 12px;
  font-weight: 700;
}

.reader-post-card__type {
  color: #86909c;
  font-size: 12px;
}

.reader-post-card__actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.reader-post-card__title {
  margin: 0;
  color: #1d2129;
  font-size: clamp(28px, 4vw, 40px);
  line-height: 1.3;
  letter-spacing: -0.02em;
  word-break: break-word;
}

.reader-post-card__meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  color: #86909c;
  font-size: 13px;
}

.reader-post-card__author {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #4e5969;
}

.reader-post-card__author-avatar {
  display: inline-grid;
  place-items: center;
  width: 28px;
  height: 28px;
  overflow: hidden;
  border-radius: 50%;
  background: linear-gradient(135deg, #1677ff, #57a5ff);
  color: #ffffff;
}

.reader-post-card__author-avatar-image {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.reader-post-card__author-avatar-fallback {
  font-size: 12px;
  font-weight: 700;
}

.reader-post-card__summary {
  margin-top: 22px;
  padding: 16px 18px;
  border-radius: 12px;
  background: #f7f8fa;
  color: #4e5969;
  font-size: 14px;
  line-height: 1.9;
}

.reader-post-card__section {
  margin-top: 28px;
  padding-top: 24px;
  border-top: 1px solid #edf1f5;
}

.reader-post-card__section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
  color: #1d2129;
  font-size: 16px;
}

.reader-post-card__section-title span {
  width: 4px;
  height: 16px;
  border-radius: 999px;
  background: #1677ff;
}

.reader-post-card__content {
  min-height: 220px;
}

.reader-content {
  color: #1f2937;
  font-size: 16px;
  line-height: 1.95;
  word-break: break-word;
}

.reader-empty {
  display: grid;
  gap: 10px;
  padding: 18px 0;
  color: #86909c;
  text-align: center;
}

.reader-empty strong {
  color: #1d2129;
  font-size: 17px;
}

.reader-empty--compact {
  padding: 6px 0 0;
}

.reader-content :deep(h1),
.reader-content :deep(h2),
.reader-content :deep(h3),
.reader-content :deep(h4) {
  margin: 1.5em 0 0.72em;
  color: #1d2129;
  line-height: 1.35;
}

.reader-content :deep(h1) {
  font-size: 1.9em;
}

.reader-content :deep(h2) {
  font-size: 1.5em;
}

.reader-content :deep(h3) {
  font-size: 1.25em;
}

.reader-content :deep(h1:first-child),
.reader-content :deep(h2:first-child),
.reader-content :deep(h3:first-child) {
  margin-top: 0;
}

.reader-content :deep(p),
.reader-content :deep(ul),
.reader-content :deep(ol),
.reader-content :deep(blockquote),
.reader-content :deep(table),
.reader-content :deep(pre) {
  margin: 0 0 1.05em;
}

.reader-content :deep(ul),
.reader-content :deep(ol) {
  padding-left: 1.5em;
}

.reader-content :deep(li + li) {
  margin-top: 0.3em;
}

.reader-content :deep(a) {
  color: #1677ff;
  text-decoration: none;
}

.reader-content :deep(a:hover) {
  text-decoration: underline;
}

.reader-content :deep(blockquote) {
  margin-left: 0;
  padding: 14px 16px;
  border-left: 4px solid #91caff;
  border-radius: 8px;
  background: #f5faff;
  color: #3f4a5a;
}

.reader-content :deep(code) {
  padding: 2px 6px;
  border-radius: 6px;
  background: #f2f3f5;
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 0.92em;
}

.reader-content :deep(pre) {
  overflow: auto;
  padding: 16px;
  border-radius: 12px;
  background: #1f2937;
}

.reader-content :deep(pre code) {
  padding: 0;
  background: transparent;
  color: #e5e7eb;
}

.reader-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
}

.reader-content :deep(th),
.reader-content :deep(td) {
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  text-align: left;
}

.reader-content :deep(th) {
  background: #f7f8fa;
}

.reader-content :deep(img) {
  display: block;
  max-width: 100%;
  margin: 20px auto 24px;
  border-radius: 12px;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
}

.reader-content :deep(.saved-link-align-left) {
  text-align: left;
}

.reader-content :deep(.saved-link-align-center) {
  text-align: center;
}

.reader-content :deep(.saved-link-align-right) {
  text-align: right;
}

.reader-content :deep(.saved-link-align-center img),
.reader-content :deep(.saved-link-align-center table) {
  margin-left: auto;
  margin-right: auto;
}

.reader-content :deep(.saved-link-align-center ul),
.reader-content :deep(.saved-link-align-center ol) {
  display: inline-block;
  text-align: left;
}

.reader-sidebar {
  display: grid;
  gap: 18px;
}

.reader-sidecard {
  padding: 20px 18px;
}

.reader-sidecard__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  color: #86909c;
  font-size: 12px;
}

.reader-sidecard__head strong {
  color: #1d2129;
  font-size: 16px;
}

.reader-author-card {
  display: grid;
  gap: 16px;
}

.reader-author-card__top {
  display: flex;
  align-items: center;
  gap: 12px;
}

.reader-author-card__avatar {
  display: inline-grid;
  place-items: center;
  width: 54px;
  height: 54px;
  overflow: hidden;
  border-radius: 50%;
  background: linear-gradient(135deg, #1677ff, #57a5ff);
  color: #ffffff;
}

.reader-author-card__avatar-image {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.reader-author-card__avatar-fallback {
  font-size: 20px;
  font-weight: 700;
}

.reader-author-card__identity {
  display: grid;
  gap: 4px;
}

.reader-author-card__identity strong {
  color: #1d2129;
  font-size: 18px;
}

.reader-author-card__identity span {
  color: #86909c;
  font-size: 13px;
}

.reader-author-card__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.reader-author-card__stats div {
  display: grid;
  gap: 4px;
  padding: 12px 8px;
  border-radius: 12px;
  background: #f7f8fa;
  text-align: center;
}

.reader-author-card__stats strong {
  color: #1d2129;
  font-size: 18px;
}

.reader-author-card__stats span,
.reader-author-card__info span {
  color: #86909c;
  font-size: 12px;
}

.reader-author-card__info {
  display: grid;
  gap: 8px;
}

.reader-author-card__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.reader-related-list,
.reader-topic-list {
  display: grid;
  gap: 10px;
}

.reader-related-item {
  display: grid;
  gap: 6px;
  width: 100%;
  padding: 12px 0;
  border: none;
  border-bottom: 1px solid #edf1f5;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.reader-related-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.reader-related-item__title {
  color: #1d2129;
  font-size: 14px;
  line-height: 1.6;
}

.reader-related-item__meta {
  color: #86909c;
  font-size: 12px;
}

.reader-related-item:hover .reader-related-item__title {
  color: #1677ff;
}

.reader-topic-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 6px 0;
}

.reader-topic-item__main {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #4e5969;
  font-size: 13px;
}

.reader-topic-item__main em {
  display: inline-grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #f2f3f5;
  color: #86909c;
  font-style: normal;
  font-size: 12px;
}

.reader-topic-item strong {
  color: #1d2129;
  font-size: 13px;
}

@media (max-width: 1200px) {
  .reader-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .reader-floatbar {
    display: none;
  }
}

@media (max-width: 1080px) {
  .reader-main {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 768px) {
  .reader-shell {
    padding: 12px 12px 24px;
  }

  .reader-page-head {
    padding: 12px 14px;
  }

  .reader-post-card,
  .reader-sidecard {
    border-radius: 14px;
  }

  .reader-post-card {
    padding: 22px 18px 24px;
  }

  .reader-post-card__title {
    font-size: 28px;
  }

  .reader-post-card__headline,
  .reader-post-card__meta {
    align-items: flex-start;
  }

  .reader-author-card__stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
