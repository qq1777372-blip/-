<script setup lang="ts">
import { ArrowDown, CirclePlus, Delete, EditPen, Link, MoreFilled, RefreshRight, Search, UploadFilled } from '@element-plus/icons-vue'
import type { UploadFile, UploadInstance, UploadRawFile } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import type { ComponentPublicInstance } from 'vue'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  appendSavedLinkImages,
  createSavedLink,
  deleteSavedLink,
  deleteSavedLinkImage as deleteSavedLinkImageRequest,
  fetchSavedLinks,
  pinSavedLink,
  replaceSavedLinkImage as replaceSavedLinkImageRequest,
  scheduleSavedLinkPush,
  unpinSavedLink,
  updateSavedLink,
} from '../api'
import { useViewport } from '../composables/useViewport'
import { useAuthStore } from '../stores/auth'
import type { SavedLink, SavedLinkPayload, SavedLinkPushPayload } from '../types/api'
import { getApiTimestamp, parseApiDateTime } from '../utils/format'
import { getTutorialDocPlainText, isTutorialDoc, stripTutorialDocCategory } from '../utils/tutorialDocs'
import ListPaginationFooter from '../components/ListPaginationFooter.vue'

type FeedTabKey = 'latest' | 'with-images' | 'mine'
type DescriptionSegment = { type: 'text' | 'link'; value: string }
type SavedLinkImage = SavedLink['images'][number]
type PushMode = 'now' | 'schedule'
type PostMenuAction = 'pin' | 'unpin' | 'push'
type PostMenuCommand = {
  action: PostMenuAction
  linkId: number
}

const URL_PATTERN_SOURCE = 'https?:\\/\\/[^\\s<]+'
const URL_TRAILING_CHARS = '.,!?;:)"\'}]>，。；：！？）】》、'

const authStore = useAuthStore()
const { viewportWidth } = useViewport()
const router = useRouter()

const loading = ref(false)
const submitLoading = ref(false)
const dialogVisible = ref(false)
const editingLinkId = ref<number | null>(null)
const previewDialogVisible = ref(false)
const previewDialogUrl = ref('')
const previewDialogTitle = ref('')
const pushDialogVisible = ref(false)
const pushDialogLoading = ref(false)
const pushTargetLink = ref<SavedLink | null>(null)
const activeFeedTab = ref<FeedTabKey>('latest')
const currentPage = ref(1)
const keyword = ref('')
const statusText = ref('准备就绪')
const links = ref<SavedLink[]>([])
const expandedDescriptionIds = ref<number[]>([])
const collapsibleDescriptionIds = ref<number[]>([])
const feedScrollRef = ref<HTMLElement | null>(null)
const FEED_PAGE_SIZE = 20
const descriptionElements = new Map<number, HTMLElement>()

const uploadRef = ref<UploadInstance>()
const uploadFileList = ref<UploadFile[]>([])
const selectedImageFiles = ref<UploadRawFile[]>([])
const currentImages = ref<SavedLink['images']>([])
const queuedImagePreviewUrls = ref<string[]>([])
const imageActionLoadingKey = ref('')
const postActionLoadingKey = ref('')

const form = reactive({
  title: '',
  url: '',
  category: '',
  description: '',
  sort_order: 0,
})

const pushForm = reactive({
  mode: 'now' as PushMode,
  scheduled_at: '',
})

let objectPreviewUrls: string[] = []

const canPost = computed(() => authStore.canWrite('links'))
const detectedFormUrls = computed(() => extractUrlsFromText(form.description))

function getLinkActivityTimestamp(link: SavedLink) {
  const source = link.updated_at || link.created_at
  return getApiTimestamp(source)
}

function getLinkDisplayTime(link: SavedLink) {
  return link.updated_at || link.created_at
}

function compareSavedLinks(a: SavedLink, b: SavedLink) {
  if (a.is_pinned !== b.is_pinned) {
    return a.is_pinned ? -1 : 1
  }

  if (a.sort_order !== b.sort_order) {
    return a.sort_order - b.sort_order
  }

  const timeDiff = getLinkActivityTimestamp(b) - getLinkActivityTimestamp(a)
  if (timeDiff !== 0) {
    return timeDiff
  }

  return b.id - a.id
}

const feedTabs = computed(() => {
  const currentUserId = authStore.currentUser?.id

  return [
    {
      value: 'latest' as const,
      label: '最新',
      count: links.value.length,
    },
    {
      value: 'with-images' as const,
      label: '带图',
      count: links.value.filter((link) => link.images.length > 0).length,
    },
    {
      value: 'mine' as const,
      label: '我发布的',
      count: currentUserId
        ? links.value.filter((link) => link.author_user_id === currentUserId).length
        : 0,
    },
  ]
})

const tabScopedLinks = computed(() => {
  let source = links.value

  if (activeFeedTab.value === 'with-images') {
    source = source.filter((link) => link.images.length > 0)
  } else if (activeFeedTab.value === 'mine') {
    const currentUserId = authStore.currentUser?.id
    source = currentUserId ? source.filter((link) => link.author_user_id === currentUserId) : []
  }

  return source
})

const filteredLinks = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase()
  let source = tabScopedLinks.value

  if (!normalizedKeyword) {
    return [...source].sort(compareSavedLinks)
  }

  return source
    .filter((link) =>
      [
        link.title,
        link.url,
        link.category ?? '',
        getDisplayDescription(link),
        link.author_username,
        ...link.images.map((item) => item.name ?? ''),
      ]
        .join(' ')
        .toLowerCase()
        .includes(normalizedKeyword),
    )
    .sort(compareSavedLinks)
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredLinks.value.length / FEED_PAGE_SIZE)))

const paginatedLinks = computed(() => {
  const startIndex = (currentPage.value - 1) * FEED_PAGE_SIZE
  return filteredLinks.value.slice(startIndex, startIndex + FEED_PAGE_SIZE)
})

const statusDisplay = computed(() => {
  const currentTabLabel = feedTabs.value.find((tab) => tab.value === activeFeedTab.value)?.label ?? '最新'

  if (!keyword.value.trim()) {
    return statusText.value
  }

  return `当前筛选：${currentTabLabel} · ${keyword.value.trim()}`
})

const totalImageCount = computed(() =>
  links.value.reduce((count, link) => count + link.images.length, 0),
)

const categoryCount = computed(
  () =>
    new Set(
      tabScopedLinks.value
        .map((link) => getCategoryLabel(link.category))
        .filter(Boolean),
    ).size,
)

const latestActivityTime = computed(() => {
  if (!links.value.length) {
    return null
  }

  return links.value.reduce<string | null>((latest, link) => {
    const candidate = link.updated_at || link.created_at
    if (!latest) {
      return candidate
    }

    return getApiTimestamp(candidate) > getApiTimestamp(latest) ? candidate : latest
  }, null)
})

const feedSummary = computed(() => {
  if (!links.value.length) {
    return '还没有帖子，先发布第一条资源链接。'
  }

  const summaryParts = [
    `当前显示 ${filteredLinks.value.length} / ${links.value.length} 帖`,
    `${totalImageCount.value} 张配图`,
    `${categoryCount.value} 个分类`,
  ]

  if (latestActivityTime.value) {
    summaryParts.push(`最近更新 ${formatFeedTime(latestActivityTime.value)}`)
  }

  return summaryParts.join(' · ')
})

function canManageLink(link: SavedLink) {
  const currentUser = authStore.currentUser
  if (!currentUser) {
    return false
  }

  return authStore.canWrite('links') && (currentUser.role === 'superadmin' || currentUser.id === link.author_user_id)
}

function getAuthorName(link: SavedLink) {
  const currentUser = authStore.currentUser
  if (currentUser && currentUser.id === link.author_user_id) {
    return currentUser.display_name?.trim() || currentUser.username
  }

  return link.author_username
}

function getAuthorAvatarUrl(link: SavedLink) {
  const currentUser = authStore.currentUser
  if (currentUser && currentUser.id === link.author_user_id) {
    return currentUser.avatar_url
  }

  return link.author_avatar_url
}

function getCategoryLabel(category: string | null | undefined) {
  const normalized = stripTutorialDocCategory(category)
  return normalized || '未分类'
}

function getDisplayDescription(link: SavedLink) {
  if (!link.description) {
    return ''
  }

  return isTutorialDoc(link) ? getTutorialDocPlainText(link.description) : link.description
}

function getArticleExcerpt(link: SavedLink, maxLength = 150) {
  const normalized = getDisplayDescription(link).trim()
  if (normalized.length <= maxLength) {
    return normalized
  }

  return `${normalized.slice(0, maxLength).trim()}...`
}

function getArticleCover(link: SavedLink) {
  return link.images[0]?.url ?? null
}

function getFeedDescription(link: SavedLink) {
  return isTutorialDoc(link) ? getArticleExcerpt(link) : getDisplayDescription(link)
}

function handleFeedImageClick(link: SavedLink, image: SavedLinkImage, index: number) {
  if (index === 2 && link.images.length > 3) {
    openArticleDetail(link)
    return
  }

  openImage(image.url, `${link.title} - 图片 ${index + 1}`)
}

function openRouteInNewTab(routeLocation: Parameters<typeof router.resolve>[0]) {
  const targetRoute = router.resolve(routeLocation)
  window.open(targetRoute.href, '_blank', 'noopener,noreferrer')
}

function openArticleDetail(link: SavedLink) {
  openRouteInNewTab({
    name: isTutorialDoc(link) ? 'tutorial-docs-detail' : 'links-detail',
    params: { id: link.id },
  })
}

function shouldCollapseLink(link: SavedLink) {
  if (isTutorialDoc(link)) {
    return false
  }

  return isDescriptionCollapsible(link.id)
}

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    return String(error.response?.data?.detail ?? error.message ?? fallback)
  }

  if (error instanceof Error && error.message) {
    return error.message
  }

  return fallback
}

function isValidHttpUrl(value: string) {
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

function stripTrailingUrlPunctuation(value: string) {
  let normalized = value.trim()
  while (normalized && URL_TRAILING_CHARS.includes(normalized[normalized.length - 1] ?? '')) {
    normalized = normalized.slice(0, -1)
  }
  return normalized
}

function extractUrlsFromText(value: string | null | undefined) {
  if (!value) {
    return []
  }

  const matches = value.match(new RegExp(URL_PATTERN_SOURCE, 'gi')) ?? []
  const urls: string[] = []
  const seen = new Set<string>()

  for (const match of matches) {
    const normalized = stripTrailingUrlPunctuation(match)
    if (!normalized || !isValidHttpUrl(normalized) || seen.has(normalized)) {
      continue
    }

    seen.add(normalized)
    urls.push(normalized)
  }

  return urls
}

function getPrimaryUrl(source: { url: string | null; description: string | null }) {
  const inlineUrls = extractUrlsFromText(source.description)
  if (inlineUrls.length) {
    return inlineUrls[0]
  }

  const normalized = source.url?.trim() ?? ''
  if (normalized && isValidHttpUrl(normalized)) {
    return normalized
  }

  return null
}

function descriptionContainsLinks(description: string | null | undefined) {
  return extractUrlsFromText(description).length > 0
}

function getDescriptionSegments(description: string | null | undefined): DescriptionSegment[] {
  const source = description ?? ''
  if (!source) {
    return []
  }

  const pattern = new RegExp(URL_PATTERN_SOURCE, 'gi')
  const segments: DescriptionSegment[] = []
  let lastIndex = 0

  for (const match of source.matchAll(pattern)) {
    const rawValue = match[0] ?? ''
    const matchIndex = match.index ?? 0
    const normalized = stripTrailingUrlPunctuation(rawValue)

    if (matchIndex > lastIndex) {
      segments.push({ type: 'text', value: source.slice(lastIndex, matchIndex) })
    }

    if (normalized && isValidHttpUrl(normalized)) {
      segments.push({ type: 'link', value: normalized })
      const rawTrailingText = rawValue.slice(normalized.length)
      if (rawTrailingText) {
        segments.push({ type: 'text', value: rawTrailingText })
      }
    } else {
      segments.push({ type: 'text', value: rawValue })
    }

    lastIndex = matchIndex + rawValue.length
  }

  if (lastIndex < source.length) {
    segments.push({ type: 'text', value: source.slice(lastIndex) })
  }

  return segments.filter((segment) => segment.value)
}

function getUserInitial(username: string) {
  return (username || '?').slice(0, 1).toUpperCase()
}

function getUrlHost(value: string | null | undefined) {
  if (!value) {
    return '外部链接'
  }
  try {
    return new URL(value).hostname.replace(/^www\./, '') || '外部链接'
  } catch {
    return '外部链接'
  }
}

function formatFeedTime(value: string | null | undefined) {
  if (!value) {
    return '-'
  }

  const date = parseApiDateTime(value)
  if (!date) {
    return value
  }

  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const startOfTarget = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const dayDiff = Math.round((startOfToday.getTime() - startOfTarget.getTime()) / (24 * 60 * 60 * 1000))
  const timeText = date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })

  if (dayDiff === 0) {
    return `今天 ${timeText}`
  }

  if (dayDiff === 1) {
    return `昨天 ${timeText}`
  }

  if (date.getFullYear() === now.getFullYear()) {
    return `${date.getMonth() + 1}月${date.getDate()}日 ${timeText}`
  }

  return `${date.toLocaleDateString('zh-CN')} ${timeText}`
}

function formatDateTimeInput(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

function parseDateTimeInput(value: string | null | undefined) {
  const normalized = String(value || '').trim()
  if (!normalized) {
    return null
  }

  const date = new Date(normalized.replace(' ', 'T'))
  return Number.isNaN(date.getTime()) ? null : date
}

function getPushStatusLabel(link: SavedLink) {
  switch (link.push_status) {
    case 'scheduled':
      return '已定时推送'
    case 'sending':
      return '推送中'
    case 'sent':
      return '已推送'
    case 'failed':
      return '推送失败'
    default:
      return '未推送'
  }
}

function getPushStatusClass(link: SavedLink) {
  switch (link.push_status) {
    case 'scheduled':
      return 'saved-link-post__badge saved-link-post__badge--scheduled'
    case 'sending':
      return 'saved-link-post__badge saved-link-post__badge--sending'
    case 'sent':
      return 'saved-link-post__badge saved-link-post__badge--sent'
    case 'failed':
      return 'saved-link-post__badge saved-link-post__badge--failed'
    default:
      return 'saved-link-post__badge'
  }
}

function getPushStatusSummary(link: SavedLink) {
  if (link.push_status === 'scheduled' && link.push_scheduled_at) {
    return `计划时间：${formatFeedTime(link.push_scheduled_at)}`
  }

  if (link.push_status === 'sent' && link.push_sent_at) {
    return `最近推送：${formatFeedTime(link.push_sent_at)}`
  }

  if (link.push_status === 'failed' && link.push_error) {
    return link.push_error
  }

  return '支持立即推送到钉钉群，也可以指定未来时间自动推送。'
}

function setDescriptionElement(linkId: number, element: Element | ComponentPublicInstance | null) {
  if (element instanceof HTMLElement) {
    descriptionElements.set(linkId, element)
    return
  }

  descriptionElements.delete(linkId)
}

function isDescriptionCollapsible(linkId: number) {
  return collapsibleDescriptionIds.value.includes(linkId)
}

function isDescriptionExpanded(linkId: number) {
  return expandedDescriptionIds.value.includes(linkId)
}

function toggleDescription(linkId: number) {
  if (isDescriptionExpanded(linkId)) {
    expandedDescriptionIds.value = expandedDescriptionIds.value.filter((id) => id !== linkId)
    return
  }

  expandedDescriptionIds.value = [...expandedDescriptionIds.value, linkId]
}

async function measureDescriptionOverflow() {
  await nextTick()

  const nextCollapsibleIds: number[] = []
  for (const link of paginatedLinks.value) {
    const descriptionElement = descriptionElements.get(link.id)
    if (!descriptionElement) {
      continue
    }

    const computedStyle = window.getComputedStyle(descriptionElement)
    const lineHeight = Number.parseFloat(computedStyle.lineHeight)
    const maxAllowedHeight = Number.isFinite(lineHeight) ? lineHeight * 3 + 2 : 72

    if (descriptionElement.scrollHeight > maxAllowedHeight) {
      nextCollapsibleIds.push(link.id)
    }
  }

  collapsibleDescriptionIds.value = nextCollapsibleIds
}

function scrollFeedToTop() {
  feedScrollRef.value?.scrollTo({ top: 0, behavior: 'smooth' })
}

function releasePreviewUrls() {
  objectPreviewUrls.forEach((url) => URL.revokeObjectURL(url))
  objectPreviewUrls = []
  queuedImagePreviewUrls.value = []
}

function setExistingPreview(images: SavedLink['images']) {
  currentImages.value = images
}

function syncSelectedImageFiles() {
  selectedImageFiles.value = uploadFileList.value
    .map((file) => file.raw)
    .filter((file): file is UploadRawFile => Boolean(file))

  releasePreviewUrls()
  objectPreviewUrls = selectedImageFiles.value.map((file) => URL.createObjectURL(file))
  queuedImagePreviewUrls.value = [...objectPreviewUrls]
}

function getUploadFileKey(file: UploadFile) {
  const rawFile = file.raw
  if (rawFile) {
    return `${rawFile.name}-${rawFile.size}-${rawFile.lastModified}`
  }

  return `${file.name}-${file.size ?? ''}-${file.uid}`
}

function mergeUploadFiles(existingFiles: UploadFile[], incomingFiles: UploadFile[]) {
  const merged = [...existingFiles]
  const existingIndexMap = new Map(merged.map((file, index) => [getUploadFileKey(file), index]))

  for (const file of incomingFiles) {
    const key = getUploadFileKey(file)
    const existingIndex = existingIndexMap.get(key)
    if (existingIndex === undefined) {
      existingIndexMap.set(key, merged.length)
      merged.push(file)
      continue
    }

    merged[existingIndex] = file
  }

  return merged.slice(0, 9)
}

function resetUploadState() {
  selectedImageFiles.value = []
  uploadFileList.value = []
  currentImages.value = []
  releasePreviewUrls()
  uploadRef.value?.clearFiles()
}

function resetForm() {
  editingLinkId.value = null
  form.title = ''
  form.url = ''
  form.category = ''
  form.description = ''
  form.sort_order = 0
  resetUploadState()
}

function openCreateDialog() {
  resetForm()
  dialogVisible.value = true
}

function handlePublishCommand(command: string | number | object) {
  if (command === 'post-publish') {
    openCreateDialog()
    return
  }

  if (command === 'article-publish') {
    openRouteInNewTab({ name: 'tutorial-docs-new' })
  }
}

function openEditDialog(link: SavedLink) {
  editingLinkId.value = link.id
  form.title = link.title
  form.url = link.url ?? ''
  form.category = link.category ?? ''
  form.description = link.description ?? ''
  form.sort_order = Number(link.sort_order || 0)
  uploadFileList.value = []
  selectedImageFiles.value = []
  setExistingPreview(link.images)
  dialogVisible.value = true
}

function handleEditLink(link: SavedLink) {
  if (isTutorialDoc(link)) {
    openRouteInNewTab({ name: 'tutorial-docs-edit', params: { id: link.id } })
    return
  }

  openEditDialog(link)
}

function openPushDialog(link: SavedLink) {
  pushTargetLink.value = link

  if (link.push_status === 'scheduled' && link.push_scheduled_at) {
    pushForm.mode = 'schedule'
    pushForm.scheduled_at = formatDateTimeInput(parseDateTimeInput(link.push_scheduled_at) ?? new Date())
  } else {
    pushForm.mode = 'now'
    pushForm.scheduled_at = formatDateTimeInput(new Date(Date.now() + 10 * 60 * 1000))
  }

  pushDialogVisible.value = true
}

function applySavedLinkUpdate(updatedLink: SavedLink) {
  links.value = links.value.map((link) => (link.id === updatedLink.id ? updatedLink : link))
  if (editingLinkId.value === updatedLink.id) {
    setExistingPreview(updatedLink.images)
  }
  if (pushTargetLink.value?.id === updatedLink.id) {
    pushTargetLink.value = updatedLink
  }
}

function getRemainingUploadSlots() {
  return Math.max(0, 9 - currentImages.value.length - uploadFileList.value.length)
}

function validateImageFile(rawFile: Pick<File, 'type' | 'size'>) {
  const allowedTypes = ['image/jpeg', 'image/png', 'image/webp']
  if (!allowedTypes.includes(rawFile.type)) {
    ElMessage.error('仅支持 JPG、PNG、WebP 图片')
    return false
  }

  if (rawFile.size > 15 * 1024 * 1024) {
    ElMessage.error('图片大小不能超过 15MB')
    return false
  }

  return true
}

function pickSingleImageFile() {
  return new Promise<File | null>((resolve) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'image/jpeg,image/png,image/webp'
    input.onchange = () => {
      resolve(input.files?.[0] ?? null)
    }
    input.click()
  })
}

function getSavedImageStorageName(image: SavedLinkImage) {
  const explicitName = String(image.storage_name ?? '').trim()
  if (explicitName) {
    return explicitName
  }

  try {
    const url = new URL(image.url, window.location.origin)
    const pathnameParts = url.pathname.split('/').filter(Boolean)
    return decodeURIComponent(pathnameParts[pathnameParts.length - 1] ?? '')
  } catch {
    const pathnameParts = String(image.url ?? '').split('/').filter(Boolean)
    return decodeURIComponent(pathnameParts[pathnameParts.length - 1] ?? '')
  }
}

async function replaceCurrentImage(image: SavedLinkImage) {
  const linkId = editingLinkId.value
  if (linkId === null) {
    return
  }

  const selectedFile = await pickSingleImageFile()
  if (!selectedFile || !validateImageFile(selectedFile)) {
    return
  }

  const imageStorageName = getSavedImageStorageName(image)
  if (!imageStorageName) {
    ElMessage.error('当前图片标识无效，请刷新页面后重试')
    return
  }

  imageActionLoadingKey.value = `replace:${imageStorageName}`
  try {
    const updatedLink = await replaceSavedLinkImageRequest(linkId, imageStorageName, selectedFile)
    applySavedLinkUpdate(updatedLink)
    ElMessage.success('图片已替换')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '替换图片失败'))
  } finally {
    imageActionLoadingKey.value = ''
  }
}

async function deleteCurrentImage(image: SavedLinkImage) {
  const linkId = editingLinkId.value
  if (linkId === null) {
    return
  }

  try {
    await ElMessageBox.confirm('确定删除这张图片吗？删除后不会影响其他图片。', '删除图片', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })

    const imageStorageName = getSavedImageStorageName(image)
    if (!imageStorageName) {
      ElMessage.error('当前图片标识无效，请刷新页面后重试')
      return
    }

    imageActionLoadingKey.value = `delete:${imageStorageName}`
    const updatedLink = await deleteSavedLinkImageRequest(linkId, imageStorageName)
    applySavedLinkUpdate(updatedLink)
    ElMessage.success('图片已删除')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, '删除图片失败'))
  } finally {
    imageActionLoadingKey.value = ''
  }
}

function buildPayload(): SavedLinkPayload {
  const preservedUrl = form.url.trim()
  return {
    title: form.title.trim(),
    url: (detectedFormUrls.value[0] ?? preservedUrl) || null,
    category: form.category.trim() || null,
    description: form.description.trim() || null,
    sort_order: Number(form.sort_order || 0),
  }
}

function openLink(url: string | null | undefined) {
  if (!url) {
    return
  }
  window.open(url, '_blank', 'noopener,noreferrer')
}

function openImage(url: string, title: string) {
  previewDialogUrl.value = url
  previewDialogTitle.value = title
  previewDialogVisible.value = true
}

async function togglePinnedState(link: SavedLink) {
  const nextPinned = !link.is_pinned
  postActionLoadingKey.value = `${link.id}:pin`

  try {
    const updatedLink = nextPinned ? await pinSavedLink(link.id) : await unpinSavedLink(link.id)
    applySavedLinkUpdate(updatedLink)
    await loadData('正在刷新链接广场...')
    ElMessage.success(nextPinned ? '帖子已置顶' : '帖子已取消置顶')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, nextPinned ? '置顶帖子失败' : '取消置顶失败'))
  } finally {
    postActionLoadingKey.value = ''
  }
}

function handlePostMenuCommand(link: SavedLink, command: PostMenuAction) {
  if (command === 'pin' || command === 'unpin') {
    void togglePinnedState(link)
    return
  }

  if (command === 'push') {
    openPushDialog(link)
  }
}

function handlePostMenuCommandFromDropdown(command: string | number | PostMenuCommand) {
  if (!command || typeof command !== 'object' || !('action' in command) || !('linkId' in command)) {
    return
  }

  const targetLink = links.value.find((link) => link.id === command.linkId)
  if (!targetLink) {
    return
  }

  handlePostMenuCommand(targetLink, command.action)
}

async function submitPushPlan() {
  const target = pushTargetLink.value
  if (!target) {
    return
  }

  const payload: SavedLinkPushPayload = {
    scheduled_at: null,
  }
  let successMessage = '帖子已推送到钉钉群'

  if (pushForm.mode === 'schedule') {
    const scheduledAt = parseDateTimeInput(pushForm.scheduled_at)
    if (!scheduledAt) {
      ElMessage.warning('请先选择有效的推送时间')
      return
    }

    if (scheduledAt.getTime() <= Date.now()) {
      ElMessage.warning('定时推送时间必须晚于当前时间')
      return
    }

    payload.scheduled_at = formatDateTimeInput(scheduledAt)
    successMessage = `已安排 ${payload.scheduled_at} 推送到钉钉群`
  }

  pushDialogLoading.value = true
  try {
    const updatedLink = await scheduleSavedLinkPush(target.id, payload)
    applySavedLinkUpdate(updatedLink)
    pushDialogVisible.value = false
    await loadData('正在刷新链接广场...')
    ElMessage.success(successMessage)
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '帖子推送失败'))
  } finally {
    pushDialogLoading.value = false
  }
}

async function loadData(message = '正在同步链接广场...') {
  loading.value = true
  statusText.value = message

  try {
    const data = await fetchSavedLinks()
    const visibleLinks = data
    links.value = visibleLinks
    expandedDescriptionIds.value = expandedDescriptionIds.value.filter((id) =>
      visibleLinks.some((link) => link.id === id),
    )
    statusText.value = `已加载 ${visibleLinks.length} 条帖子`
  } catch (error) {
    const messageText = getErrorMessage(error, '加载链接广场失败')
    statusText.value = messageText
    ElMessage.error(messageText)
  } finally {
    loading.value = false
  }
}

async function submitLink() {
  submitLoading.value = true

  try {
    const payload = buildPayload()
    if (!payload.title) {
      ElMessage.warning('标题不能为空')
      return
    }

    if (payload.url && !isValidHttpUrl(payload.url)) {
      ElMessage.warning('链接地址必须以 http:// 或 https:// 开头')
      return
    }

    const isCreating = editingLinkId.value === null
    let savedRecord: SavedLink
    if (isCreating) {
      savedRecord = await createSavedLink(payload)
      editingLinkId.value = savedRecord.id
    } else {
      const linkId = editingLinkId.value
      if (linkId === null) {
        throw new Error('当前帖子缺少 ID，无法更新')
      }
      savedRecord = await updateSavedLink(linkId, payload)
    }

    let imageUploadErrorMessage = ''
    if (selectedImageFiles.value.length) {
      try {
        savedRecord = await appendSavedLinkImages(savedRecord.id, selectedImageFiles.value)
      } catch (error) {
        imageUploadErrorMessage = getErrorMessage(error, '帖子图片上传失败')
      }
    }

    setExistingPreview(savedRecord.images)

    dialogVisible.value = false
    await loadData('正在刷新链接广场...')

    if (imageUploadErrorMessage) {
      ElMessage.warning(
        `${isCreating ? '帖子已发布' : '帖子已更新'}，但图片上传失败：${imageUploadErrorMessage}`,
      )
      return
    }

    ElMessage.success(isCreating ? '帖子发布成功' : '帖子更新成功')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '保存帖子失败'))
  } finally {
    submitLoading.value = false
  }
}

async function confirmDelete(link: SavedLink) {
  try {
    await ElMessageBox.confirm(`确定删除帖子“${link.title}”吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })

    await deleteSavedLink(link.id)
    ElMessage.success('删除成功')
    await loadData('正在刷新链接广场...')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    ElMessage.error(getErrorMessage(error, '删除帖子失败'))
  }
}

function beforeImageUpload(rawFile: UploadRawFile) {
  if (!validateImageFile(rawFile)) {
    return false
  }

  if (getRemainingUploadSlots() <= 0) {
    ElMessage.warning('最多上传 9 张图片')
    return false
  }

  return true
}

function handleUploadChange(_: UploadFile, fileList: UploadFile[]) {
  uploadFileList.value = mergeUploadFiles(uploadFileList.value, fileList)
  syncSelectedImageFiles()
}

function handleUploadRemove(_: UploadFile, fileList: UploadFile[]) {
  uploadFileList.value = fileList
  syncSelectedImageFiles()
}

function removeQueuedImage(targetFile: UploadFile | undefined) {
  if (!targetFile) {
    return
  }

  uploadFileList.value = uploadFileList.value.filter((file) => file.uid !== targetFile.uid)
  syncSelectedImageFiles()
}

function handleUploadExceed(files: File[]) {
  const remainingCount = getRemainingUploadSlots()
  if (remainingCount === 0) {
    ElMessage.warning('最多上传 9 张图片')
    return
  }

  ElMessage.warning(`本次选择了 ${files.length} 张，当前最多还能再加 ${remainingCount} 张`)
}

watch(dialogVisible, (visible) => {
  if (!visible) {
    resetForm()
  }
})

watch(pushDialogVisible, (visible) => {
  if (!visible) {
    pushTargetLink.value = null
    pushDialogLoading.value = false
    pushForm.mode = 'now'
    pushForm.scheduled_at = ''
  }
})

watch([activeFeedTab, keyword], () => {
  currentPage.value = 1
})

watch(
  () => filteredLinks.value.length,
  () => {
    if (currentPage.value > totalPages.value) {
      currentPage.value = totalPages.value
    }
  },
)

watch(currentPage, () => {
  scrollFeedToTop()
})

watch(
  () => paginatedLinks.value.map((link) => `${link.id}:${getDisplayDescription(link)}`).join('|'),
  () => {
    void measureDescriptionOverflow()
  },
)

watch(viewportWidth, () => {
  void measureDescriptionOverflow()
})

watch(
  () => ({
    id: authStore.currentUser?.id ?? null,
    username: authStore.currentUser?.username ?? '',
    displayName: authStore.currentUser?.display_name ?? '',
    avatarUrl: authStore.currentUser?.avatar_url ?? null,
  }),
  ({ id, username, displayName, avatarUrl }) => {
    if (!id) {
      return
    }

    const nextAuthorName = String(displayName || username || '').trim()
    links.value = links.value.map((link) =>
      link.author_user_id === id
        ? {
            ...link,
            author_username: nextAuthorName || link.author_username,
            author_avatar_url: avatarUrl,
          }
        : link,
    )
  },
)

onMounted(loadData)
onBeforeUnmount(releasePreviewUrls)
</script>

<template>
  <div class="page-stack">
    <section class="page-block list-surface list-surface--fixed saved-links-board">
      <div class="saved-links-topbar">
        <div class="saved-links-tabs" role="tablist" aria-label="帖子筛选">
          <button
            v-for="tab in feedTabs"
            :key="tab.value"
            type="button"
            class="saved-links-tab"
            :class="{ 'saved-links-tab--active': activeFeedTab === tab.value }"
            :aria-pressed="activeFeedTab === tab.value"
            @click="activeFeedTab = tab.value"
          >
            <span>{{ tab.label }}</span>
            <em>{{ tab.count }}</em>
          </button>
        </div>

        <div class="saved-links-topbar__actions">
          <el-input
            v-model="keyword"
            class="saved-links-search"
            placeholder="搜索标题、用户、分类、链接地址或正文"
            size="large"
            :prefix-icon="Search"
            clearable
          />
          <el-dropdown trigger="click" @command="handlePublishCommand">
            <el-button type="primary" :icon="CirclePlus" :disabled="!canPost">
            发布帖子
              <el-icon class="saved-links-publish-caret"><ArrowDown /></el-icon>
            </el-button>

            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="post-publish" :disabled="!canPost">
                  发布帖子
                </el-dropdown-item>
                <el-dropdown-item command="article-publish" :disabled="!canPost">
                  文章发布
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button text :icon="RefreshRight" @click="loadData('正在手动刷新链接广场...')">
            刷新
          </el-button>
        </div>
      </div>

      <div class="saved-links-subbar">
        <div class="saved-links-subbar__main">
          <strong class="saved-links-subbar__title">链接广场</strong>
          <span class="saved-links-subbar__summary">{{ feedSummary }}</span>
        </div>
        <span class="saved-links-subbar__status" :title="statusDisplay">{{ statusDisplay }}</span>
      </div>

      <div class="saved-link-feed-shell" v-loading="loading">
        <template v-if="filteredLinks.length">
          <div ref="feedScrollRef" class="saved-link-feed-scroll">
            <div class="saved-link-feed">
              <article
                v-for="link in paginatedLinks"
                :key="link.id"
                class="saved-link-post"
                :class="{ 'saved-link-post--article': isTutorialDoc(link) }"
              >
                <template v-if="false">
                  <button type="button" class="saved-article-card" @click="openArticleDetail(link)">
                    <div v-if="getArticleCover(link)" class="saved-article-card__cover">
                      <img :src="getArticleCover(link) || ''" :alt="link.title" />
                    </div>

                    <div class="saved-article-card__body">
                      <div class="saved-article-card__meta">
                        <span class="saved-article-card__tag">{{ getCategoryLabel(link.category) }}</span>
                        <span>{{ formatFeedTime(getLinkDisplayTime(link)) }}</span>
                        <span>{{ getAuthorName(link) }}</span>
                      </div>

                      <h4 class="saved-article-card__title">{{ link.title }}</h4>
                      <p class="saved-article-card__excerpt">
                        {{ getArticleExcerpt(link) || '这篇文章还没有摘要内容。' }}
                      </p>

                      <div class="saved-article-card__footer">
                        <span class="saved-article-card__note">文章 #{{ link.id }}</span>

                        <div class="saved-link-post__actions">
                          <el-button text type="primary" @click.stop="openArticleDetail(link)">
                            阅读全文
                          </el-button>
                          <el-button v-if="canManageLink(link)" text :icon="EditPen" @click.stop="handleEditLink(link)">
                            编辑
                          </el-button>
                          <el-button v-if="canManageLink(link)" text type="danger" :icon="Delete" @click.stop="confirmDelete(link)">
                            删除
                          </el-button>
                        </div>
                      </div>
                    </div>
                  </button>
                </template>

                <template v-else>
                <div class="saved-link-post__header">
                  <div class="saved-link-post__user">
                    <div class="saved-link-post__avatar">
                      <img
                        v-if="getAuthorAvatarUrl(link)"
                        :src="getAuthorAvatarUrl(link) || ''"
                        :alt="getAuthorName(link)"
                        class="saved-link-post__avatar-image"
                      />
                      <template v-else>{{ getUserInitial(getAuthorName(link)) }}</template>
                    </div>
                    <div class="saved-link-post__identity">
                      <div class="saved-link-post__author-row">
                        <strong class="saved-link-post__author">{{ getAuthorName(link) }}</strong>
                        <span v-if="link.is_pinned" class="saved-link-post__badge saved-link-post__badge--pinned">置顶</span>
                        <span class="saved-link-post__category">{{ getCategoryLabel(link.category) }}</span>
                        <span v-if="link.push_status !== 'idle'" :class="getPushStatusClass(link)">
                          {{ getPushStatusLabel(link) }}
                        </span>
                      </div>
                      <div class="saved-link-post__meta">
                        <span>{{ formatFeedTime(getLinkDisplayTime(link)) }}</span>
                        <span v-if="getPrimaryUrl(link)">{{ getUrlHost(getPrimaryUrl(link)) }}</span>
                        <span v-if="link.images.length">{{ link.images.length }} 张图</span>
                        <span v-if="link.sort_order > 0">排序 {{ link.sort_order }}</span>
                      </div>
                    </div>
                  </div>
                  <div v-if="canManageLink(link)" class="saved-link-post__header-actions">
                    <el-dropdown trigger="click" @command="handlePostMenuCommandFromDropdown">
                      <el-button
                        text
                        circle
                        class="saved-link-post__menu-button"
                        :icon="MoreFilled"
                        :loading="postActionLoadingKey === `${link.id}:pin`"
                        aria-label="帖子更多操作"
                      />
                      <template #dropdown>
                        <el-dropdown-menu>
                          <el-dropdown-item :command="{ action: link.is_pinned ? 'unpin' : 'pin', linkId: link.id }">
                            {{ link.is_pinned ? '取消置顶' : '顶置帖子' }}
                          </el-dropdown-item>
                          <el-dropdown-item :command="{ action: 'push', linkId: link.id }">帖子推送</el-dropdown-item>
                        </el-dropdown-menu>
                      </template>
                    </el-dropdown>
                  </div>
                </div>

                <div class="saved-link-post__body">
                  <button type="button" class="saved-link-post__title" @click="openArticleDetail(link)">
                    {{ link.title }}
                  </button>

                  <div
                    v-if="getFeedDescription(link)"
                    :ref="(element) => setDescriptionElement(link.id, element)"
                    class="saved-link-post__description"
                    :class="{
                      'saved-link-post__description--collapsed':
                        shouldCollapseLink(link) && !isDescriptionExpanded(link.id),
                    }"
                  >
                    <template
                      v-for="(segment, index) in getDescriptionSegments(getFeedDescription(link))"
                      :key="`${link.id}-segment-${index}`"
                    >
                      <a
                        v-if="segment.type === 'link'"
                        :href="segment.value"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="saved-link-post__description-link"
                      >
                        {{ segment.value }}
                      </a>
                      <span v-else>{{ segment.value }}</span>
                    </template>
                  </div>

                  <button
                    v-if="shouldCollapseLink(link)"
                    type="button"
                    class="saved-link-post__more"
                    @click="toggleDescription(link.id)"
                  >
                    {{ isDescriptionExpanded(link.id) ? '收起' : '查看全文' }}
                  </button>

                  <button
                    v-if="!isTutorialDoc(link) && getPrimaryUrl(link) && !descriptionContainsLinks(link.description)"
                    type="button"
                    class="saved-link-post__url"
                    @click="openLink(getPrimaryUrl(link))"
                  >
                    <strong class="saved-link-post__url-host">{{ getUrlHost(getPrimaryUrl(link)) }}</strong>
                    <span class="saved-link-post__url-text mono-text">{{ getPrimaryUrl(link) }}</span>
                  </button>

                  <div
                    v-if="link.images.length"
                    class="saved-link-gallery"
                    :class="{
                      'saved-link-gallery--single': link.images.length === 1,
                      'saved-link-gallery--double': link.images.length === 2,
                    }"
                  >
                    <button
                      v-for="(image, index) in link.images.slice(0, 3)"
                      :key="`${link.id}-${index}`"
                      type="button"
                      class="saved-link-gallery__item"
                      @click="handleFeedImageClick(link, image, index)"
                    >
                      <img :src="image.url" :alt="image.name || `${link.title} 配图 ${index + 1}`" />
                      <span v-if="index === 2 && link.images.length > 3" class="saved-link-gallery__more">
                        +{{ link.images.length - 3 }}
                      </span>
                    </button>
                  </div>
                </div>

                <div class="saved-link-post__footer">
                  <div class="saved-link-post__footer-note">帖子 #{{ link.id }}</div>

                  <div class="saved-link-post__actions">
                    <el-button text type="primary" @click="openArticleDetail(link)">
                      阅读全文
                    </el-button>
                    <el-button v-if="false" text type="primary" :icon="Link" @click="openLink(getPrimaryUrl(link))">
                      打开链接
                    </el-button>
                    <el-button v-if="canManageLink(link)" text :icon="EditPen" @click="handleEditLink(link)">
                      编辑
                    </el-button>
                    <el-button v-if="canManageLink(link)" text type="danger" :icon="Delete" @click="confirmDelete(link)">
                      删除
                    </el-button>
                  </div>
                </div>
                </template>
              </article>
            </div>
          </div>

          <ListPaginationFooter
            v-model:current-page="currentPage"
            :total-pages="totalPages"
            :page-size="FEED_PAGE_SIZE"
            :total-items="filteredLinks.length"
            item-unit="帖"
          />
        </template>

        <el-empty v-else :description="keyword.trim() ? '没有匹配的帖子' : '暂无帖子'" />
      </div>
    </section>

    <el-dialog
      v-model="dialogVisible"
      :title="editingLinkId === null ? '发布帖子' : `编辑帖子 #${editingLinkId}`"
      width="900px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-row :gutter="16">
          <el-col :span="16">
            <el-form-item label="标题" required>
              <el-input v-model="form.title" placeholder="例如：活动链接 / 商品入口 / 常用工具" />
            </el-form-item>
          </el-col>

          <el-col :span="8">
            <el-form-item label="分类">
              <el-input v-model="form.category" placeholder="例如：店铺后台 / 运营工具 / 素材资源" />
            </el-form-item>
          </el-col>

          <el-col :span="24">
            <el-form-item label="正文说明">
              <el-input
                v-model="form.description"
                type="textarea"
                :rows="6"
                placeholder="像论坛发帖一样写正文，可直接粘贴一个或多个 http/https 链接，系统会自动识别第一条作为主链接"
              />
              <div class="saved-link-editor-tip">
                <span>链接不用单独填，直接贴在正文里就行。</span>
                <span v-if="detectedFormUrls.length">已识别 {{ detectedFormUrls.length }} 个链接，主链接将使用第 1 个。</span>
                <span v-else-if="form.url">当前保留旧帖子里的历史主链接，直接保存不会丢。</span>
              </div>
            </el-form-item>
          </el-col>

          <el-col :span="6">
            <el-form-item label="排序值">
              <el-input-number v-model="form.sort_order" :min="0" :max="9999" style="width: 100%" />
            </el-form-item>
          </el-col>

          <el-col :span="24">
            <el-form-item label="帖子图片">
              <el-upload
                ref="uploadRef"
                v-model:file-list="uploadFileList"
                action="#"
                :multiple="true"
                accept="image/jpeg,image/png,image/webp"
                :limit="9"
                :auto-upload="false"
                :show-file-list="false"
                :before-upload="beforeImageUpload"
                :on-change="handleUploadChange"
                :on-remove="handleUploadRemove"
                :on-exceed="handleUploadExceed"
              >
                <el-button type="primary" plain :icon="UploadFilled">批量选择图片</el-button>
                <template #tip>
                  <div class="section-desc" style="margin-top: 8px">
                    支持 JPG / PNG / WebP，单张不超过 15MB，最多 9 张。可一次多选，也可分几次继续追加。
                  </div>
                </template>
              </el-upload>
            </el-form-item>
          </el-col>

          <el-col v-if="queuedImagePreviewUrls.length" :span="24">
            <el-form-item label="图片预览">
              <div class="saved-link-editor-gallery">
                <div
                  v-for="(imageUrl, index) in queuedImagePreviewUrls"
                  :key="`${imageUrl}-${index}`"
                  class="saved-link-editor-gallery__item saved-link-editor-gallery__item--queued"
                >
                  <span class="saved-link-editor-gallery__badge saved-link-editor-gallery__badge--queued">待上传</span>
                  <img :src="imageUrl" :alt="`预览图片 ${index + 1}`" />
                  <div class="saved-link-editor-gallery__meta">
                    <span class="saved-link-editor-gallery__name">
                      {{ uploadFileList[index]?.name || `待上传图片 ${index + 1}` }}
                    </span>
                    <div class="saved-link-editor-gallery__actions">
                      <el-button
                        text
                        type="primary"
                        @click="openImage(imageUrl, uploadFileList[index]?.name || `待上传图片 ${index + 1}`)"
                      >
                        预览
                      </el-button>
                      <el-button text type="danger" @click="removeQueuedImage(uploadFileList[index])">
                        移除
                      </el-button>
                    </div>
                  </div>
                </div>
              </div>
            </el-form-item>
          </el-col>

          <el-col v-if="currentImages.length" :span="24">
            <el-form-item label="已保存图片">
              <div class="saved-link-editor-gallery">
                <div
                  v-for="(image, index) in currentImages"
                  :key="getSavedImageStorageName(image) || image.url"
                  class="saved-link-editor-gallery__item saved-link-editor-gallery__item--saved"
                >
                  <img :src="image.url" :alt="image.name || `已保存图片 ${index + 1}`" />
                  <span class="saved-link-editor-gallery__badge">{{ index === 0 ? '主图' : `#${index + 1}` }}</span>
                  <div class="saved-link-editor-gallery__meta">
                    <span class="saved-link-editor-gallery__name">{{ image.name || `图片 ${index + 1}` }}</span>
                    <div class="saved-link-editor-gallery__actions">
                      <el-button text type="primary" @click="openImage(image.url, image.name || `帖子图片 ${index + 1}`)">
                        预览
                      </el-button>
                      <el-button
                        text
                        :loading="imageActionLoadingKey === `replace:${getSavedImageStorageName(image)}`"
                        @click="replaceCurrentImage(image)"
                      >
                        替换
                      </el-button>
                      <el-button
                        text
                        type="danger"
                        :loading="imageActionLoadingKey === `delete:${getSavedImageStorageName(image)}`"
                        @click="deleteCurrentImage(image)"
                      >
                        删除
                      </el-button>
                    </div>
                  </div>
                </div>
              </div>
              <div class="section-desc" style="margin-top: 8px">
                这里是已经保存到帖子里的图片。删除或替换只作用于当前这一张，不会把整组图片一起改掉。
              </div>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="submitLink">
          {{ editingLinkId === null ? '发布帖子' : '保存修改' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="pushDialogVisible"
      :title="pushTargetLink ? `帖子推送 #${pushTargetLink.id}` : '帖子推送'"
      width="560px"
      destroy-on-close
    >
      <div v-if="pushTargetLink" class="saved-link-push-dialog">
        <div class="saved-link-push-dialog__summary">
          <strong class="saved-link-push-dialog__title">{{ pushTargetLink.title }}</strong>
          <span class="saved-link-push-dialog__status">{{ getPushStatusSummary(pushTargetLink) }}</span>
          <span v-if="pushTargetLink.push_error" class="saved-link-push-dialog__error">
            {{ pushTargetLink.push_error }}
          </span>
        </div>

        <el-form label-position="top">
          <el-form-item label="推送方式">
            <el-radio-group v-model="pushForm.mode">
              <el-radio-button label="now">立即推送</el-radio-button>
              <el-radio-button label="schedule">定时推送</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item v-if="pushForm.mode === 'schedule'" label="推送时间">
            <el-date-picker
              v-model="pushForm.scheduled_at"
              type="datetime"
              value-format="YYYY-MM-DD HH:mm:ss"
              format="YYYY-MM-DD HH:mm:ss"
              placeholder="选择推送时间"
              style="width: 100%"
            />
          </el-form-item>

          <div class="saved-link-push-dialog__tip">
            推送会通过服务器上的钉钉机器人发到群里。未配置 `DINGTALK_ROBOT_WEBHOOK` 时会直接报错。
          </div>
        </el-form>
      </div>

      <template #footer>
        <el-button @click="pushDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="pushDialogLoading" @click="submitPushPlan">
          {{ pushForm.mode === 'schedule' ? '保存推送时间' : '立即推送' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="previewDialogVisible"
      :title="previewDialogTitle || '帖子图片预览'"
      width="960px"
      destroy-on-close
    >
      <div class="saved-link-image-dialog">
        <img v-if="previewDialogUrl" :src="previewDialogUrl" :alt="previewDialogTitle || '帖子图片预览'" />
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.saved-links-board {
  overflow: hidden;
  background: #ffffff;
}

.saved-links-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 14px 20px 10px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.82);
}

.saved-links-tabs {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.saved-links-tab {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  font: inherit;
  transition:
    color 0.2s ease,
    background-color 0.2s ease,
    box-shadow 0.2s ease;
}

.saved-links-tab:hover {
  background: #f3f6fb;
  color: #1f2937;
}

.saved-links-tab--active {
  background: #f1f5ff;
  color: #1d4ed8;
  font-weight: 700;
}

.saved-links-tab em {
  display: inline-grid;
  place-items: center;
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.18);
  font-style: normal;
  font-size: 12px;
}

.saved-links-tab--active em {
  background: rgba(29, 78, 216, 0.12);
}

.saved-links-topbar__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  flex: 1 1 360px;
  min-width: 0;
}

.saved-links-search {
  width: min(100%, 260px);
  flex: 1 1 220px;
}

.saved-links-search :deep(.el-input__wrapper) {
  min-height: 40px;
  border-radius: 999px;
  background: #f7f8fa;
  box-shadow: inset 0 0 0 1px #eef2f7;
}

.saved-links-search :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px rgba(22, 119, 255, 0.28);
}

.saved-links-publish-caret {
  margin-left: 6px;
  font-size: 12px;
}

.saved-links-subbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 20px 4px;
}

.saved-links-subbar__main {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  min-width: 0;
}

.saved-links-subbar__title {
  color: #0f172a;
  font-size: 16px;
}

.saved-links-subbar__summary,
.saved-links-subbar__status {
  color: #94a3b8;
  font-size: 12px;
}

.saved-link-feed-shell {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  gap: 12px;
  padding: 0 20px 16px;
}

.saved-link-feed-scroll {
  max-height: min(72vh, 980px);
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}

@media (min-width: 769px) {
  .saved-link-feed-shell {
    height: max(520px, calc(100vh - 250px));
    min-height: 0;
  }

  .saved-link-feed-scroll {
    min-height: 0;
    max-height: none;
  }
}

.saved-link-feed {
  display: grid;
  gap: 0;
  padding: 0 12px 6px 0;
  justify-items: center;
}


.saved-links-board .saved-link-feed-shell {
  overflow-y: auto;
  overscroll-behavior: contain;
}

.saved-link-post {
  display: grid;
  gap: 0;
  padding: 18px 0;
  width: min(100%, 860px);
  border-bottom: 1px solid rgba(226, 232, 240, 0.82);
}

.saved-link-post:last-child {
  border-bottom: none;
}

.saved-link-post--article {
  padding: 18px 0;
}

.saved-article-card {
  display: grid;
  grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
  gap: 0;
  width: 100%;
  overflow: hidden;
  padding: 0;
  border: 1px solid rgba(226, 232, 240, 0.92);
  border-radius: 22px;
  background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
  text-align: left;
  cursor: pointer;
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.06);
  transition:
    transform 0.22s ease,
    box-shadow 0.22s ease,
    border-color 0.22s ease;
}

.saved-article-card:hover {
  transform: translateY(-2px);
  border-color: rgba(37, 99, 235, 0.18);
  box-shadow: 0 22px 44px rgba(15, 23, 42, 0.08);
}

.saved-article-card__cover {
  min-height: 100%;
  background: #eef2f7;
}

.saved-article-card__cover img {
  display: block;
  width: 100%;
  height: 100%;
  min-height: 220px;
  object-fit: cover;
}

.saved-article-card__body {
  display: grid;
  gap: 14px;
  padding: 22px 24px;
}

.saved-article-card__meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  color: #94a3b8;
  font-size: 12px;
}

.saved-article-card__tag {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  background: #ecf5ff;
  color: #2563eb;
  font-weight: 700;
}

.saved-article-card__title {
  margin: 0;
  color: #0f172a;
  font-size: 24px;
  line-height: 1.28;
  letter-spacing: -0.02em;
}

.saved-article-card__excerpt {
  margin: 0;
  color: #475569;
  font-size: 14px;
  line-height: 1.85;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 4;
  overflow: hidden;
}

.saved-article-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: auto;
  padding-top: 14px;
  border-top: 1px solid rgba(226, 232, 240, 0.88);
}

.saved-article-card__note {
  color: #94a3b8;
  font-size: 12px;
}

.saved-link-post__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  grid-row: 1;
  margin-bottom: 10px;
}

.saved-link-post__header-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.saved-link-post__menu-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  padding: 0;
  border: 1px solid #dbe3ee;
  border-radius: 999px;
  background: #ffffff;
  color: #64748b;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
}

.saved-link-post__menu-button :deep(.el-icon) {
  font-size: 18px;
  font-weight: 700;
}

.saved-link-post__menu-button:hover {
  color: #0f172a;
  border-color: #cbd5e1;
  background: #f8fafc;
}

.saved-link-post__user {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.saved-link-post__identity {
  min-width: 0;
}

.saved-link-post__avatar {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  overflow: hidden;
  border-radius: 50%;
  background: linear-gradient(135deg, #2563eb, #0ea5e9);
  color: #ffffff;
  font-size: 11px;
  font-weight: 800;
}

.saved-link-post__avatar-image {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  background: #f8fafc;
}

.saved-link-post__author-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.saved-link-post__author {
  font-size: 13px;
  color: #111827;
}

.saved-link-post__category {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: #f2f4f8;
  color: #5b6472;
  font-size: 11px;
  font-weight: 600;
}

.saved-link-post__badge {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
}

.saved-link-post__badge--pinned {
  background: #eff6ff;
  color: #1d4ed8;
}

.saved-link-post__badge--scheduled {
  background: #fff7ed;
  color: #c2410c;
}

.saved-link-post__badge--sending {
  background: #ecfeff;
  color: #0f766e;
}

.saved-link-post__badge--sent {
  background: #ecfdf5;
  color: #047857;
}

.saved-link-post__badge--failed {
  background: #fef2f2;
  color: #b91c1c;
}

.saved-link-post__meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 2px;
  color: #97a0af;
  font-size: 12px;
}

.saved-link-post__body {
  display: grid;
  gap: 8px;
  grid-row: 2;
  margin-top: 0;
  padding-left: 0;
}

.saved-link-post__title {
  display: block;
  max-width: 100%;
  overflow: hidden;
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  font-size: 18px;
  font-weight: 700;
  line-height: 1.4;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #0f172a;
  cursor: pointer;
}

.saved-link-post__title:hover {
  color: #1d4ed8;
}

.saved-link-post__description {
  display: -webkit-box;
  overflow: hidden;
  margin: 0;
  color: #475569;
  line-height: 1.75;
  white-space: normal;
  word-break: break-word;
  font-size: 14px;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.saved-link-post__description-link {
  color: #1677ff;
  text-decoration: none;
}

.saved-link-post__description-link:hover {
  text-decoration: underline;
}

.saved-link-post__description--collapsed {
  -webkit-line-clamp: 2;
}

.saved-link-post__more {
  display: none;
  padding: 0;
  border: none;
  background: transparent;
  color: #1d4ed8;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.saved-link-post__url {
  display: grid;
  gap: 2px;
  max-width: min(100%, 720px);
  padding: 10px 12px;
  border: 1px solid #edf2f7;
  border-radius: 12px;
  background: #fafbfc;
  text-align: left;
  cursor: pointer;
}

.saved-link-post__url-host {
  color: #334155;
  font-size: 13px;
  font-weight: 600;
}

.saved-link-post__url-text {
  color: #1d4ed8;
  font-size: 12px;
  word-break: break-all;
}

.saved-link-gallery {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  max-width: 560px;
}

.saved-link-gallery--single {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.saved-link-gallery--double {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.saved-link-gallery__item {
  position: relative;
  display: block;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  padding: 0;
  border: none;
  border-radius: 12px;
  background: #edf2f7;
  cursor: zoom-in;
  box-shadow: inset 0 0 0 1px rgba(203, 213, 225, 0.86);
}

.saved-link-gallery__more {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgba(15, 23, 42, 0.58);
  color: #ffffff;
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
}

.saved-link-gallery__item img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.24s ease;
}

.saved-link-gallery__item:hover img {
  transform: scale(1.04);
}

.saved-link-post__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 10px;
  padding-left: 0;
}

.saved-link-post__footer-note {
  color: #94a3b8;
  font-size: 12px;
}

.saved-link-post__actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-wrap: wrap;
}

.saved-link-post__actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.saved-link-editor-gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(132px, 1fr));
  gap: 12px;
  width: 100%;
}

.saved-link-editor-tip {
  display: flex;
  gap: 8px 16px;
  flex-wrap: wrap;
  margin-top: 8px;
  color: #94a3b8;
  font-size: 12px;
  line-height: 1.6;
}

.saved-link-editor-gallery__item {
  position: relative;
  overflow: hidden;
  aspect-ratio: 1 / 1;
  border-radius: 14px;
  background: #e8eef7;
  box-shadow:
    inset 0 0 0 1px rgba(148, 163, 184, 0.22),
    0 10px 24px rgba(15, 23, 42, 0.06);
}

.saved-link-editor-gallery__item img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition:
    transform 0.24s ease,
    filter 0.24s ease;
}

.saved-link-editor-gallery__item:hover img {
  transform: scale(1.04);
  filter: saturate(1.02);
}

.saved-link-editor-gallery__item--queued {
  border: 1px dashed rgba(59, 130, 246, 0.3);
  background: #eef5ff;
}

.saved-link-editor-gallery__badge {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 2;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.7);
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: 0.02em;
}

.saved-link-editor-gallery__badge--queued {
  background: rgba(37, 99, 235, 0.88);
}

.saved-link-editor-gallery__meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 2;
  padding: 40px 10px 10px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0) 0%, rgba(15, 23, 42, 0.24) 30%, rgba(15, 23, 42, 0.82) 100%);
}

.saved-link-editor-gallery__name {
  color: #ffffff;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-shadow: 0 1px 2px rgba(15, 23, 42, 0.4);
}

.saved-link-editor-gallery__actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  opacity: 0;
  transform: translateY(6px);
  pointer-events: none;
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.saved-link-editor-gallery__item:hover .saved-link-editor-gallery__actions,
.saved-link-editor-gallery__item:focus-within .saved-link-editor-gallery__actions {
  opacity: 1;
  transform: translateY(0);
  pointer-events: auto;
}

.saved-link-editor-gallery__actions :deep(.el-button) {
  min-height: 28px;
  margin: 0;
  padding: 0 10px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  color: #ffffff;
  backdrop-filter: blur(8px);
}

.saved-link-editor-gallery__actions :deep(.el-button:hover) {
  border-color: rgba(255, 255, 255, 0.34);
  background: rgba(255, 255, 255, 0.2);
  color: #ffffff;
}

.saved-link-editor-gallery__actions :deep(.el-button--danger) {
  border-color: rgba(248, 113, 113, 0.26);
  background: rgba(239, 68, 68, 0.18);
}

.saved-link-editor-gallery__actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.saved-link-image-dialog {
  display: grid;
  place-items: center;
  min-height: 320px;
  padding: 12px;
  border-radius: 18px;
  background: #f7f9fc;
}

.saved-link-image-dialog img {
  display: block;
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
  border-radius: 14px;
  background: #ffffff;
}

.saved-link-push-dialog {
  display: grid;
  gap: 16px;
}

.saved-link-push-dialog__summary {
  display: grid;
  gap: 8px;
  padding: 14px 16px;
  border-radius: 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.saved-link-push-dialog__title {
  color: #0f172a;
  font-size: 16px;
  line-height: 1.5;
}

.saved-link-push-dialog__status {
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.saved-link-push-dialog__error {
  color: #b91c1c;
  font-size: 12px;
  line-height: 1.6;
}

.saved-link-push-dialog__tip {
  color: #64748b;
  font-size: 12px;
  line-height: 1.7;
}

@media (max-width: 768px) {
  .saved-links-topbar {
    display: grid;
    gap: 10px;
    padding: 12px 14px;
  }

  .saved-links-tabs {
    flex-wrap: nowrap;
    width: 100%;
    overflow-x: auto;
    scrollbar-width: none;
  }

  .saved-links-tabs::-webkit-scrollbar {
    display: none;
  }

  .saved-links-tab {
    flex: 0 0 auto;
    padding: 7px 10px;
  }

  .saved-links-topbar__actions {
    width: 100%;
    justify-content: stretch;
    gap: 8px;
  }

  .saved-links-search {
    width: auto;
  }

  .saved-links-subbar {
    padding: 10px 14px 6px;
  }

  .saved-links-subbar__status {
    display: none;
  }

  .saved-link-feed {
    padding: 0;
    justify-items: stretch;
  }

  .saved-link-feed-shell {
    padding: 0 14px 14px;
  }

  .saved-link-editor-gallery {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .saved-link-editor-gallery__actions {
    opacity: 1;
    transform: translateY(0);
    pointer-events: auto;
  }

  .saved-link-feed-scroll {
    max-height: none;
    overflow: visible;
  }

  .saved-link-post,
  .saved-link-post--article {
    width: 100%;
    padding: 14px 0;
  }

  .saved-link-post__header {
    flex-direction: row;
    align-items: flex-start;
    gap: 8px;
    margin-bottom: 8px;
  }

  .saved-link-post__user {
    flex: 1 1 auto;
  }

  .saved-link-post__author-row {
    gap: 6px;
  }

  .saved-link-post__menu-button {
    width: 32px;
    height: 32px;
    box-shadow: none;
  }

  .saved-link-post__body,
  .saved-link-post__footer {
    padding-left: 0;
  }

  .saved-link-post__title {
    font-size: 17px;
    line-height: 1.45;
    white-space: normal;
  }

  .saved-link-post__description {
    font-size: 14px;
    line-height: 1.65;
    -webkit-line-clamp: 3;
  }

  .saved-link-post__url {
    padding: 9px 10px;
    border-radius: 6px;
  }

  .saved-article-card {
    grid-template-columns: minmax(0, 1fr);
  }

  .saved-article-card__cover img {
    min-height: 180px;
  }

  .saved-article-card__body {
    padding: 16px;
  }

  .saved-link-gallery,
  .saved-link-gallery--double {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 6px;
    max-width: 100%;
  }

  .saved-link-gallery--single {
    grid-template-columns: minmax(0, 1fr);
    max-width: 280px;
  }

  .saved-link-gallery__item {
    border-radius: 6px;
  }

  .saved-link-post__footer {
    align-items: center;
    flex-wrap: nowrap;
    margin-top: 8px;
  }

  .saved-link-post__actions {
    flex-wrap: nowrap;
    margin-left: auto;
  }

  .saved-link-post__actions :deep(.el-button) {
    padding-inline: 6px;
  }
}
</style>
