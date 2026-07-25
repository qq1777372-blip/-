<script setup lang="ts">
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  appendSavedLinkImages,
  createSavedLink,
  fetchSavedLinks,
  updateSavedLink,
} from '../api'
import type { SavedLink, SavedLinkPayload } from '../types/api'
import { renderSavedLinkMarkdown } from '../utils/savedLinkMarkdown'
import { buildTutorialDocCategory, isTutorialDoc, stripTutorialDocCategory } from '../utils/tutorialDocs'

type SavedLinkImage = SavedLink['images'][number]
type ToolbarAction = {
  key: string
  label: string
  title?: string
  run: () => void
}

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const submitLoading = ref(false)
const imageUploading = ref(false)
const currentLinkId = ref<number | null>(null)
const editorRef = ref<HTMLTextAreaElement | null>(null)

const form = reactive({
  title: '',
  category: '',
  description: '',
  is_pinned: false,
  sort_order: 0,
})

const isEditing = computed(() => currentLinkId.value !== null)
const pageTitle = computed(() => (isEditing.value ? `编辑文章 #${currentLinkId.value}` : '文章发布'))
const previewHtml = computed(() => renderSavedLinkMarkdown(form.description))

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    return String(error.response?.data?.detail ?? error.message ?? fallback)
  }

  if (error instanceof Error && error.message) {
    return error.message
  }

  return fallback
}

function stripTrailingUrlPunctuation(value: string) {
  let normalized = value.trim()
  const trailingChars = '.,!?;:)"\'}]>'
  while (normalized && trailingChars.includes(normalized[normalized.length - 1] ?? '')) {
    normalized = normalized.slice(0, -1)
  }
  return normalized
}

function isValidHttpUrl(value: string) {
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

function extractUrlsFromText(value: string | null | undefined) {
  if (!value) {
    return []
  }

  const matches = value.match(/https?:\/\/[^\s<]+/gi) ?? []
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

function focusEditor(selectionStart?: number, selectionEnd?: number) {
  nextTick(() => {
    const editor = editorRef.value
    if (!editor) {
      return
    }

    editor.focus()
    if (selectionStart !== undefined && selectionEnd !== undefined) {
      editor.setSelectionRange(selectionStart, selectionEnd)
    }
  })
}

function updateEditorValue(value: string, selectionStart?: number, selectionEnd?: number) {
  form.description = value
  focusEditor(selectionStart, selectionEnd ?? selectionStart)
}

function getEditorSelection() {
  const editor = editorRef.value
  const start = editor?.selectionStart ?? form.description.length
  const end = editor?.selectionEnd ?? form.description.length

  return {
    start,
    end,
    selectedText: form.description.slice(start, end),
  }
}

function wrapSelection(prefix: string, suffix: string, placeholder: string) {
  const { start, end, selectedText } = getEditorSelection()
  const replacement = selectedText || placeholder
  const nextValue = `${form.description.slice(0, start)}${prefix}${replacement}${suffix}${form.description.slice(end)}`
  const selectionStart = start + prefix.length
  const selectionEnd = selectionStart + replacement.length
  updateEditorValue(nextValue, selectionStart, selectionEnd)
}

function transformSelectedLines(transform: (lines: string[]) => string) {
  const { start, end } = getEditorSelection()
  const source = form.description
  const blockStart = source.lastIndexOf('\n', Math.max(0, start - 1)) + 1
  let blockEnd = source.indexOf('\n', end)
  if (blockEnd === -1) {
    blockEnd = source.length
  }

  const originalBlock = source.slice(blockStart, blockEnd)
  const nextBlock = transform((originalBlock || '').split('\n'))
  const nextValue = `${source.slice(0, blockStart)}${nextBlock}${source.slice(blockEnd)}`
  updateEditorValue(nextValue, blockStart, blockStart + nextBlock.length)
}

function insertSnippet(snippet: string, selectionStartOffset?: number, selectionEndOffset?: number) {
  const { start, end } = getEditorSelection()
  const nextValue = `${form.description.slice(0, start)}${snippet}${form.description.slice(end)}`
  const nextSelectionStart = start + (selectionStartOffset ?? snippet.length)
  const nextSelectionEnd = start + (selectionEndOffset ?? nextSelectionStart - start)
  updateEditorValue(nextValue, nextSelectionStart, nextSelectionEnd)
}

function insertBlockSnippet(content: string, selectionStartOffset: number, selectionEndOffset: number) {
  const { start, end } = getEditorSelection()
  const needsLeadingBreak = start > 0 && form.description[start - 1] !== '\n'
  const needsTrailingBreak = end < form.description.length && form.description[end] !== '\n'
  const prefix = needsLeadingBreak ? '\n' : ''
  const suffix = needsTrailingBreak ? '\n' : ''
  insertSnippet(`${prefix}${content}${suffix}`, prefix.length + selectionStartOffset, prefix.length + selectionEndOffset)
}

function applyHeading(level: number) {
  transformSelectedLines((lines) =>
    lines
      .map((line) => `${'#'.repeat(level)} ${line.replace(/^#{1,6}\s+/, '').trim() || '标题'}`)
      .join('\n'),
  )
}

function applyQuote() {
  transformSelectedLines((lines) =>
    lines.map((line) => `> ${line.replace(/^>\s?/, '').trim() || '引用内容'}`).join('\n'),
  )
}

function applyBulletList() {
  transformSelectedLines((lines) =>
    lines.map((line) => `- ${line.replace(/^\s*[-*+]\s+/, '').trim() || '列表项'}`).join('\n'),
  )
}

function applyOrderedList() {
  transformSelectedLines((lines) =>
    lines
      .map((line, index) => `${index + 1}. ${line.replace(/^\s*\d+\.\s+/, '').trim() || `列表项 ${index + 1}`}`)
      .join('\n'),
  )
}

function insertLink() {
  const { start, end, selectedText } = getEditorSelection()
  const label = selectedText || '链接文字'
  const url = 'https://example.com'
  const snippet = `[${label}](${url})`
  const nextValue = `${form.description.slice(0, start)}${snippet}${form.description.slice(end)}`
  const urlStart = start + label.length + 3
  updateEditorValue(nextValue, urlStart, urlStart + url.length)
}

function insertInlineCode() {
  wrapSelection('`', '`', '代码')
}

function insertCodeBlock() {
  const { selectedText } = getEditorSelection()
  const content = selectedText || '在这里填写代码'
  const snippet = `\n\`\`\`bash\n${content}\n\`\`\`\n`
  insertSnippet(snippet, 9, 9 + content.length)
}

function insertTable() {
  const snippet = '\n| 列 1 | 列 2 |\n| --- | --- |\n| 内容 1 | 内容 2 |\n'
  insertSnippet(snippet, 3, 6)
}

function insertDivider() {
  insertSnippet('\n---\n')
}

function insertAlignmentBlock(alignment: 'left' | 'center' | 'right') {
  const { selectedText } = getEditorSelection()
  const content = selectedText.trim() || `${alignment === 'center' ? '居中' : alignment === 'right' ? '右对齐' : '左对齐'}内容`
  const snippet = `::: align-${alignment}\n${content}\n:::`
  const contentStart = `::: align-${alignment}\n`.length
  insertBlockSnippet(snippet, contentStart, contentStart + content.length)
}

function getPrimaryUrl(description: string | null | undefined) {
  return extractUrlsFromText(description)[0] ?? null
}

function buildPayload(): SavedLinkPayload {
  return {
    title: form.title.trim(),
    url: getPrimaryUrl(form.description),
    category: buildTutorialDocCategory(form.category),
    description: form.description.trim() || null,
    is_pinned: form.is_pinned,
    sort_order: Number(form.sort_order || 0),
  }
}

async function persistDocument(options: { notify?: boolean; syncRoute?: boolean } = {}) {
  const { notify = true, syncRoute = true } = options
  const payload = buildPayload()

  if (!payload.title) {
    throw new Error('请先填写文章标题')
  }

  const creating = currentLinkId.value === null
  let savedRecord: SavedLink

  if (creating) {
    savedRecord = await createSavedLink(payload)
  } else {
    const existingId = currentLinkId.value
    if (existingId === null) {
      throw new Error('当前文章缺少 ID，无法保存')
    }
    savedRecord = await updateSavedLink(existingId, payload)
  }

  currentLinkId.value = savedRecord.id

  if (notify) {
    ElMessage.success(creating ? '文章已创建' : '文章已保存')
  }

  if (syncRoute && (route.name === 'tutorial-docs-new' || route.name === 'tutorial-docs-editor-new')) {
    await router.replace({ name: 'tutorial-docs-editor-edit', params: { id: savedRecord.id } })
  }

  return savedRecord
}

async function submitDocument() {
  submitLoading.value = true
  try {
    const creating = currentLinkId.value === null
    await persistDocument({ notify: false, syncRoute: false })
    ElMessage.success(creating ? '文章已发布到链接广场' : '文章已更新到链接广场')
    if (window.opener && !window.opener.closed) {
      try {
        window.opener.location.reload()
      } catch {
        // Ignore opener refresh failures and still try to close the popup.
      }

      window.close()
      return
    }

    await router.push({ name: 'links' })
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '发布文章失败'))
  } finally {
    submitLoading.value = false
  }
}

function validateImageFile(rawFile: Pick<File, 'type' | 'size'>) {
  const allowedTypes = ['image/jpeg', 'image/png', 'image/webp']
  if (!allowedTypes.includes(rawFile.type)) {
    ElMessage.error('只支持 JPG、PNG、WebP 图片')
    return false
  }

  if (rawFile.size > 15 * 1024 * 1024) {
    ElMessage.error('图片大小不能超过 15MB')
    return false
  }

  return true
}

function insertImageMarkdown(image: SavedLinkImage) {
  const altText = image.name || '图片说明'
  const imageUrl = image.url
  insertSnippet(`\n![${altText}](${imageUrl})\n`)
}

async function uploadImageFileAndInsert(file: File, successMessage: string) {
  const savedRecord = await persistDocument({ notify: false, syncRoute: false })
  const updatedRecord = await appendSavedLinkImages(savedRecord.id, [file])
  currentLinkId.value = updatedRecord.id
  const uploadedImage = updatedRecord.images[updatedRecord.images.length - 1]

  if (uploadedImage) {
    insertImageMarkdown(uploadedImage)
  }

  ElMessage.success(successMessage)
}

async function pickSingleImageFile() {
  return new Promise<File | null>((resolve) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'image/jpeg,image/png,image/webp'
    input.onchange = () => resolve(input.files?.[0] ?? null)
    input.click()
  })
}

async function uploadImageAndInsert() {
  const file = await pickSingleImageFile()
  if (!file || !validateImageFile(file)) {
    return
  }

  imageUploading.value = true
  try {
    await uploadImageFileAndInsert(file, '图片已上传并插入正文')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '上传图片失败'))
  } finally {
    imageUploading.value = false
  }
}

function handleEditorPaste(event: ClipboardEvent) {
  if (imageUploading.value) {
    return
  }

  const clipboardItems = Array.from(event.clipboardData?.items ?? [])
  const imageItem = clipboardItems.find((item) => item.type.startsWith('image/'))
  const imageFile = imageItem?.getAsFile()

  if (!imageFile || !validateImageFile(imageFile)) {
    return
  }

  event.preventDefault()
  imageUploading.value = true
  void uploadImageFileAndInsert(imageFile, '截图已粘贴并插入正文')
    .catch((error) => {
      ElMessage.error(getErrorMessage(error, '粘贴图片失败'))
    })
    .finally(() => {
      imageUploading.value = false
    })
}

function handleTabIndent(event: KeyboardEvent) {
  if (event.key !== 'Tab') {
    return
  }

  event.preventDefault()
  insertSnippet('  ')
}

async function loadDocument() {
  const rawId = Number(route.params.id)
  if (!Number.isFinite(rawId) || rawId <= 0) {
    currentLinkId.value = null
    form.title = ''
    form.category = ''
    form.description = ''
    form.is_pinned = false
    form.sort_order = 0
    return
  }

  loading.value = true
  try {
    const data = await fetchSavedLinks()
    const target = data.find((item) => item.id === rawId && isTutorialDoc(item))

    if (!target) {
      throw new Error('没有找到对应文章')
    }

    currentLinkId.value = target.id
    form.title = target.title
    form.category = stripTutorialDocCategory(target.category)
    form.description = target.description ?? ''
    form.is_pinned = target.is_pinned
    form.sort_order = Number(target.sort_order || 0)
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

  void router.push({ name: 'links' })
}

const toolbarActions: ToolbarAction[] = [
  { key: 'h1', label: '标题1', title: '一级标题', run: () => applyHeading(1) },
  { key: 'h2', label: '标题2', title: '二级标题', run: () => applyHeading(2) },
  { key: 'bold', label: '加粗', title: '加粗文本', run: () => wrapSelection('**', '**', '加粗内容') },
  { key: 'italic', label: '斜体', title: '斜体文本', run: () => wrapSelection('*', '*', '斜体内容') },
  { key: 'quote', label: '引用', title: '引用块', run: applyQuote },
  { key: 'center', label: '居中', title: '居中内容', run: () => insertAlignmentBlock('center') },
  { key: 'link', label: '链接', title: '插入链接', run: insertLink },
  { key: 'image', label: '图片', title: '上传并插入图片', run: uploadImageAndInsert },
  { key: 'inline-code', label: '行内码', title: '行内代码', run: insertInlineCode },
  { key: 'code-block', label: '代码块', title: '代码块', run: insertCodeBlock },
  { key: 'ul', label: '无序列', title: '无序列表', run: applyBulletList },
  { key: 'ol', label: '有序列', title: '有序列表', run: applyOrderedList },
  { key: 'table', label: '表格', title: '插入表格', run: insertTable },
  { key: 'divider', label: '分割线', title: '分割线', run: insertDivider },
]

onMounted(loadDocument)
</script>

<template>
  <div class="page-stack">
    <section class="page-block tutorial-editor-shell" v-loading="loading">
      <div class="tutorial-editor-topbar">
        <el-button text :icon="ArrowLeft" @click="goBack">返回链接广场</el-button>

        <div class="tutorial-editor-topbar__actions">
          <el-button type="primary" :loading="submitLoading" @click="submitDocument">提交</el-button>
        </div>
      </div>

      <div class="tutorial-editor-intro">
        <div class="tutorial-editor-intro__copy">
          <span class="tutorial-editor-intro__eyebrow">{{ isEditing ? '文章编辑' : '文章发布' }}</span>
          <h2 class="section-title">{{ pageTitle }}</h2>
          <p class="section-desc">
            Markdown 编写、实时预览、图片插入都集中在这一页完成。
          </p>
        </div>
      </div>

      <div class="tutorial-editor-fields">
        <label class="tutorial-editor-field tutorial-editor-field--title">
          <span class="tutorial-editor-field__label">标题</span>
          <input
            v-model="form.title"
            class="tutorial-editor-field__input tutorial-editor-field__input--title"
            type="text"
            placeholder="给这篇文章起一个清晰的标题"
          />
        </label>

        <div class="tutorial-editor-fields__row">
          <label class="tutorial-editor-field">
            <span class="tutorial-editor-field__label">分类</span>
            <input v-model="form.category" class="tutorial-editor-field__input" type="text" placeholder="例如：店铺教程 / 使用指南 / 系统操作" />
          </label>

          <label class="tutorial-editor-field tutorial-editor-field--compact">
            <span class="tutorial-editor-field__label">排序</span>
            <el-input-number v-model="form.sort_order" :min="0" :max="9999" controls-position="right" />
          </label>
        </div>
      </div>

      <div class="tutorial-editor-toolbar-shell">
        <div class="tutorial-editor-toolbar-shell__label">快捷工具栏</div>
        <div class="tutorial-editor-toolbar">
          <button
            v-for="action in toolbarActions"
            :key="action.key"
            class="tutorial-toolbar-button"
            type="button"
            :title="action.title || action.label"
            @click="action.run"
          >
            {{ action.label }}
          </button>
        </div>
      </div>

      <div class="tutorial-editor-workbench">
        <section class="tutorial-editor-pane tutorial-editor-pane--write">
          <header class="tutorial-editor-pane__header">
            <strong>正文</strong>
            <span>Markdown 输入</span>
          </header>

          <textarea
            ref="editorRef"
            v-model="form.description"
            class="tutorial-editor-textarea"
            placeholder="从这里开始写正文..."
            spellcheck="false"
            @keydown="handleTabIndent"
            @paste="handleEditorPaste"
          />
        </section>

        <section class="tutorial-editor-pane tutorial-editor-pane--preview">
          <header class="tutorial-editor-pane__header">
            <strong>预览</strong>
            <span>实时渲染结果</span>
          </header>

          <div class="tutorial-editor-preview-scroll">
            <div v-if="previewHtml" class="tutorial-preview-content" v-html="previewHtml"></div>
            <div v-else class="tutorial-preview-empty">
              <strong>这里会显示实时预览</strong>
              <span>开始输入 Markdown 后，右侧会自动渲染成文档效果。</span>
            </div>
          </div>
        </section>
      </div>
    </section>
  </div>
</template>

<style scoped>
.tutorial-editor-shell {
  padding: 16px 18px 18px;
}

.tutorial-editor-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}

.tutorial-editor-topbar__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.tutorial-editor-intro {
  margin-top: 6px;
  padding: 8px 0 2px;
}

.tutorial-editor-intro__copy {
  display: grid;
  gap: 4px;
}

.tutorial-editor-intro__eyebrow {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  min-height: 24px;
  padding: 0 9px;
  border-radius: 999px;
  background: #edf4ff;
  color: var(--brand-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.tutorial-editor-fields {
  display: grid;
  gap: 10px;
  margin: 8px 0 12px;
}

.tutorial-editor-fields__row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 180px;
  gap: 12px;
  align-items: end;
}

.tutorial-editor-field {
  display: grid;
  gap: 6px;
}

.tutorial-editor-field__label {
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 700;
}

.tutorial-editor-field__input {
  min-height: 42px;
  padding: 0 14px;
  border: 1px solid var(--panel-border);
  border-radius: 16px;
  background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
  color: var(--text-main);
  font: inherit;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.tutorial-editor-field__input:focus {
  border-color: #b7d2ff;
  box-shadow: 0 0 0 4px rgba(22, 119, 255, 0.08);
}

.tutorial-editor-field__input--title {
  min-height: 58px;
  font-size: clamp(20px, 2.8vw, 30px);
  font-weight: 800;
  line-height: 1.2;
}

.tutorial-editor-field__input--title::placeholder {
  color: #c0cad8;
}

.tutorial-editor-field--compact :deep(.el-input-number) {
  width: 100%;
}

.tutorial-editor-toolbar-shell {
  display: grid;
  gap: 8px;
  margin-bottom: 12px;
  padding: 12px 14px;
  border: 1px solid #e6edf7;
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
}

.tutorial-editor-toolbar-shell__label {
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 700;
}

.tutorial-editor-toolbar {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-wrap: wrap;
}

.tutorial-toolbar-button {
  min-width: 52px;
  height: 32px;
  padding: 0 10px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #ffffff;
  color: #334155;
  font: inherit;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease;
}

.tutorial-toolbar-button:hover {
  background: #eef4fb;
  border-color: #dbeafe;
  color: #1d4ed8;
}

.tutorial-editor-workbench {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  min-height: 640px;
  overflow: hidden;
  border: 1px solid var(--panel-border);
  border-radius: 18px;
  background: #ffffff;
}

.tutorial-editor-pane {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-width: 0;
}

.tutorial-editor-pane--preview {
  border-left: 1px solid var(--panel-border);
  background: linear-gradient(180deg, #fbfcfe 0%, #ffffff 100%);
}

.tutorial-editor-pane__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.9);
  color: var(--text-secondary);
  font-size: 12px;
}

.tutorial-editor-pane__header strong {
  color: var(--text-main);
  font-size: 13px;
}

.tutorial-editor-textarea {
  width: 100%;
  min-height: 100%;
  padding: 16px 18px;
  border: none;
  resize: none;
  background: transparent;
  color: var(--text-main);
  font: 15px/1.9 'Microsoft YaHei', 'PingFang SC', sans-serif;
  outline: none;
  white-space: pre-wrap;
  word-break: break-word;
}

.tutorial-editor-preview-scroll {
  overflow: auto;
  min-height: 0;
  padding: 18px 20px;
}

.tutorial-preview-empty {
  display: grid;
  place-items: center;
  gap: 10px;
  min-height: 100%;
  color: var(--text-secondary);
  text-align: center;
}

.tutorial-preview-empty strong {
  color: var(--text-main);
}

.tutorial-preview-content {
  color: #0f172a;
  line-height: 1.9;
  word-break: break-word;
}

.tutorial-preview-content :deep(h1),
.tutorial-preview-content :deep(h2),
.tutorial-preview-content :deep(h3),
.tutorial-preview-content :deep(h4) {
  margin: 1.4em 0 0.7em;
  color: #0f172a;
  line-height: 1.3;
}

.tutorial-preview-content :deep(h1:first-child),
.tutorial-preview-content :deep(h2:first-child),
.tutorial-preview-content :deep(h3:first-child) {
  margin-top: 0;
}

.tutorial-preview-content :deep(p),
.tutorial-preview-content :deep(ul),
.tutorial-preview-content :deep(ol),
.tutorial-preview-content :deep(blockquote),
.tutorial-preview-content :deep(table),
.tutorial-preview-content :deep(pre) {
  margin: 0 0 1em;
}

.tutorial-preview-content :deep(a) {
  color: #2563eb;
  text-decoration: none;
}

.tutorial-preview-content :deep(a:hover) {
  text-decoration: underline;
}

.tutorial-preview-content :deep(blockquote) {
  margin-left: 0;
  padding: 10px 14px;
  border-left: 4px solid #93c5fd;
  border-radius: 0 14px 14px 0;
  background: #eff6ff;
  color: #1e3a8a;
}

.tutorial-preview-content :deep(code) {
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.06);
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 0.92em;
}

.tutorial-preview-content :deep(pre) {
  overflow: auto;
  padding: 16px;
  border-radius: 16px;
  background: #0f172a;
}

.tutorial-preview-content :deep(pre code) {
  padding: 0;
  background: transparent;
  color: #e2e8f0;
}

.tutorial-preview-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
}

.tutorial-preview-content :deep(th),
.tutorial-preview-content :deep(td) {
  padding: 10px 12px;
  border: 1px solid rgba(203, 213, 225, 0.88);
  text-align: left;
}

.tutorial-preview-content :deep(th) {
  background: #f8fafc;
}

.tutorial-preview-content :deep(img) {
  display: block;
  max-width: 100%;
  border-radius: 16px;
  box-shadow: 0 16px 32px rgba(15, 23, 42, 0.08);
}

.tutorial-preview-content :deep(.saved-link-align-left) {
  text-align: left;
}

.tutorial-preview-content :deep(.saved-link-align-center) {
  text-align: center;
}

.tutorial-preview-content :deep(.saved-link-align-right) {
  text-align: right;
}

.tutorial-preview-content :deep(.saved-link-align-center img),
.tutorial-preview-content :deep(.saved-link-align-center table) {
  margin-left: auto;
  margin-right: auto;
}

.tutorial-preview-content :deep(.saved-link-align-center ul),
.tutorial-preview-content :deep(.saved-link-align-center ol) {
  display: inline-block;
  text-align: left;
}

@media (max-width: 1024px) {
  .tutorial-editor-workbench {
    grid-template-columns: minmax(0, 1fr);
  }

  .tutorial-editor-pane--preview {
    border-top: 1px solid var(--panel-border);
    border-left: none;
  }

  .tutorial-editor-fields__row {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 768px) {
  .tutorial-editor-shell {
    padding: 16px;
  }

  .tutorial-editor-field__input--title {
    min-height: 52px;
    font-size: 18px;
  }

  .tutorial-editor-toolbar-shell {
    padding: 12px;
  }
}
</style>
