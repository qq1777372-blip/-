<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { IonContent, IonIcon, IonPage, IonSpinner, alertController, toastController } from '@ionic/vue'
import { closeOutline, imageOutline } from 'ionicons/icons'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import { api, ApiError } from '../api'
import { firstUrl, normalizePath, parseContent, renderMarkdown } from '../markdown'
import type { SavedLink } from './LinkPlazaPage.vue'

type StoredImage = { url: string; name?: string; storage_name: string }
type PendingImage = { url: string; file: File }

const route = useRoute()
const router = useRouter()
const id = computed(() => (route.params.id ? Number(route.params.id) : 0))
// Articles and posts share this editor. Articles put images inline in the body
// and drop the link/pin/sort fields; the tutorial: prefix marks the category.
const articleMode = computed(() => route.path.startsWith('/tabs/form/articles'))
const saving = ref(false)
const loading = ref(true)
const mode = ref<'write' | 'split' | 'preview'>('write')
const body = ref<HTMLTextAreaElement | null>(null)
const inlinePicker = ref<HTMLInputElement | null>(null)
// Inline images picked before the record exists. They live as blob: URLs in the
// body so the preview works, then get swapped for real URLs on save.
const pending = ref<PendingImage[]>([])
const galleryFiles = ref<File[]>([])
const galleryPreviews = ref<string[]>([])
const removed = ref<string[]>([])

const form = reactive({
  title: '',
  category: '',
  description: '',
  url: '',
  is_pinned: false,
  sort_order: 0,
  existingImages: [] as StoredImage[],
})

const tools = [
  { label: 'H1', hint: '一级标题', apply: () => linePrefix('# ') },
  { label: 'H2', hint: '二级标题', apply: () => linePrefix('## ') },
  { label: '粗体', hint: '加粗', apply: () => wrap('**', '**') },
  { label: '斜体', hint: '斜体', apply: () => wrap('*', '*') },
  { label: '引用', hint: '引用', apply: () => linePrefix('> ') },
  { label: '列表', hint: '无序列表', apply: () => linePrefix('- ') },
  { label: '编号', hint: '有序列表', apply: () => orderedList() },
  { label: '链接', hint: '插入链接', apply: () => wrap('[', '](https://)') },
  { label: '行内码', hint: '行内代码', apply: () => wrap('`', '`') },
  { label: '代码块', hint: '代码块', apply: () => insertCodeBlock() },
  { label: '表格', hint: '插入表格', apply: () => insertTable() },
  { label: '分割线', hint: '分割线', apply: () => insertSnippet('\n---\n') },
  { label: '居中', hint: '居中对齐', apply: () => block('::: align-center', ':::') },
]

const blocks = computed(() => parseContent(form.description, form.title || '配图'))
const previewHtml = computed(() => renderMarkdown(form.description))
const keptImages = computed(() => form.existingImages.filter((image) => !removed.value.includes(image.storage_name)))
// Images already placed in the body are managed there, so only the leftovers
// need a management strip. Older articles can have unreferenced images.
const referenced = computed(() => new Set(blocks.value.filter((block) => block.type === 'image').map((block) => normalizePath(block.src))))
const strayImages = computed(() => keptImages.value.filter((image) => !referenced.value.has(normalizePath(image.url))))
const canSave = computed(() => Boolean(form.title.trim()) && !saving.value && !loading.value)
const heading = computed(() => (articleMode.value ? (id.value ? '编辑文章' : '发布文章') : id.value ? '编辑帖子' : '发布帖子'))

function articleCategory(value?: string) {
  return String(value || '').replace(/^tutorial:/i, '').trim()
}

async function showError(error: unknown, fallback: string) {
  const toast = await toastController.create({
    message: error instanceof ApiError ? error.detail : error instanceof Error ? error.message : fallback,
    duration: 2300,
    color: 'danger',
  })
  await toast.present()
}

async function load() {
  if (!id.value) {
    loading.value = false
    return
  }
  try {
    const rows = await api<SavedLink[]>('/saved-links')
    const item = rows.find((row) => row.id === id.value)
    if (item) {
      Object.assign(form, {
        title: item.title,
        category: articleMode.value ? articleCategory(item.category) : item.category || '',
        description: item.description || '',
        url: item.url || '',
        is_pinned: item.is_pinned,
        sort_order: Number(item.sort_order || 0),
        existingImages: item.images || [],
      })
    }
  } catch (error) {
    await showError(error, articleMode.value ? '文章加载失败' : '帖子加载失败')
  } finally {
    loading.value = false
  }
}

// Markdown helpers operate on the live selection so the caret stays put.
function edit(transform: (text: string, start: number, end: number) => { text: string; start: number; end: number }) {
  const field = body.value
  if (!field) return
  const result = transform(form.description, field.selectionStart, field.selectionEnd)
  form.description = result.text
  requestAnimationFrame(() => {
    field.focus()
    field.setSelectionRange(result.start, result.end)
  })
}

function wrap(before: string, after: string) {
  edit((text, start, end) => ({
    text: `${text.slice(0, start)}${before}${text.slice(start, end)}${after}${text.slice(end)}`,
    start: start + before.length,
    end: end + before.length,
  }))
}

function linePrefix(prefix: string) {
  edit((text, start, end) => {
    const lineStart = text.lastIndexOf('\n', start - 1) + 1
    return {
      text: `${text.slice(0, lineStart)}${prefix}${text.slice(lineStart)}`,
      start: start + prefix.length,
      end: end + prefix.length,
    }
  })
}

function orderedList() {
  edit((text, start, end) => {
    const lineStart = text.lastIndexOf('\n', start - 1) + 1
    const lineEnd = text.indexOf('\n', end) === -1 ? text.length : text.indexOf('\n', end)
    const lines = text.slice(lineStart, lineEnd).split('\n')
    const nextNumber = () => {
      const previousLines = text.slice(0, start).split('\n').reverse()
      const previous = previousLines.find((line) => /^\s*\d+\.\s+/.test(line))
      return previous ? Number(previous.match(/^\s*(\d+)/)?.[1] || 0) + 1 : 1
    }
    const base = start === end ? nextNumber() : 1
    const replacement = lines.map((line, index) => `${base + index}. ${line.replace(/^\s*\d+\.\s+/, '').trim() || `列表项 ${base + index}`}`).join('\n')
    return { text: `${text.slice(0, lineStart)}${replacement}${text.slice(lineEnd)}`, start: lineStart, end: lineStart + replacement.length }
  })
}

function insertSnippet(snippet: string) {
  edit((text, start) => ({ text: `${text.slice(0, start)}${snippet}${text.slice(start)}`, start: start + snippet.length, end: start + snippet.length }))
}

function insertCodeBlock() {
  insertSnippet('\n```text\n在这里填写代码\n```\n')
}

function insertTable() {
  insertSnippet('\n| 列 1 | 列 2 |\n| --- | --- |\n| 内容 1 | 内容 2 |\n')
}

function block(open: string, close: string) {
  edit((text, start, end) => {
    const selected = text.slice(start, end) || '在这里输入内容'
    const inserted = `${open}\n${selected}\n${close}\n`
    return {
      text: `${text.slice(0, start)}${inserted}${text.slice(end)}`,
      start: start + open.length + 1,
      end: start + open.length + 1 + selected.length,
    }
  })
}

// Images always land on their own line, which is what the parser expects.
function insertImageMarkdown(alt: string, url: string) {
  edit((text, start) => {
    const prefix = text.slice(0, start)
    const lead = prefix && !prefix.endsWith('\n') ? '\n' : ''
    const snippet = `${lead}![${alt}](${url})\n`
    return {
      text: `${prefix}${snippet}${text.slice(start)}`,
      start: start + snippet.length,
      end: start + snippet.length,
    }
  })
}

function pickInlineImages() {
  inlinePicker.value?.click()
}

function onInlinePick(event: Event) {
  const input = event.target as HTMLInputElement
  const selected = Array.from(input.files || [])
  input.value = ''
  const room = 9 - keptImages.value.length - pending.value.length - galleryFiles.value.length
  if (room <= 0) {
    void showError(null, '最多 9 张图片')
    return
  }
  for (const file of selected.slice(0, room)) {
    const url = URL.createObjectURL(file)
    pending.value = [...pending.value, { url, file }]
    insertImageMarkdown(file.name.replace(/\.[^.]+$/, '') || '配图', url)
  }
  if (selected.length > room) void showError(null, `最多 9 张图片，已添加前 ${room} 张`)
}

function insertStored(image: StoredImage) {
  insertImageMarkdown(image.name || form.title || '配图', image.url)
}

// Post mode keeps a trailing gallery, so it has its own multi-file picker.
function chooseGallery(event: Event) {
  const input = event.target as HTMLInputElement
  const selected = Array.from(input.files || []).slice(0, 9)
  galleryPreviews.value.forEach(URL.revokeObjectURL)
  galleryFiles.value = selected
  galleryPreviews.value = selected.map(URL.createObjectURL)
  input.value = ''
}

function dropGalleryFile(index: number) {
  URL.revokeObjectURL(galleryPreviews.value[index])
  galleryFiles.value = galleryFiles.value.filter((_, position) => position !== index)
  galleryPreviews.value = galleryPreviews.value.filter((_, position) => position !== index)
}

function dropPending(item: PendingImage) {
  // Drop the markdown line too, otherwise the body keeps a dead blob reference.
  form.description = form.description
    .split('\n')
    .filter((line) => !line.includes(item.url))
    .join('\n')
  URL.revokeObjectURL(item.url)
  pending.value = pending.value.filter((entry) => entry.url !== item.url)
}

async function dropStored(image: StoredImage) {
  const confirm = await alertController.create({
    header: '移除配图',
    message: '保存后这张图片会被删除，确定移除吗？',
    buttons: [
      { text: '取消', role: 'cancel' },
      {
        text: '移除',
        role: 'destructive',
        handler: () => {
          removed.value = [...removed.value, image.storage_name]
          form.description = form.description
            .split('\n')
            .filter((line) => !line.includes(image.url))
            .join('\n')
        },
      },
    ],
  })
  await confirm.present()
}

// Unresolved blob refs must never be persisted, so they are stripped from the
// first save and only restored once the upload returns real URLs.
function stripPending(text: string) {
  if (!pending.value.length) return text
  return text
    .split('\n')
    .filter((line) => !pending.value.some((item) => line.includes(item.url)))
    .join('\n')
    .trim()
}

function buildPayload(description: string) {
  const category = form.category.trim()
  return {
    title: form.title.trim(),
    category: articleMode.value ? `tutorial:${category}` : category || null,
    description: description || null,
    // Article links are derived from the body; skip blob: refs so a pending
    // image never becomes the article's primary URL.
    url: articleMode.value ? firstUrl(description.replace(/blob:\S+/g, '')) : form.url.trim() || null,
    is_pinned: form.is_pinned,
    sort_order: Number(form.sort_order || 0),
  }
}

// The live backend has no bulk to_delete field, so removals go one by one
// through the documented DELETE endpoint.
async function applyRemovals(recordId: number) {
  for (const name of removed.value) {
    const response = await fetch(`/saved-links/${recordId}/images/${encodeURIComponent(name)}`, {
      method: 'DELETE',
      credentials: 'include',
    })
    if (!response.ok && response.status !== 404) {
      const result = await response.json().catch(() => ({}))
      throw new Error(result.detail || '图片删除失败')
    }
  }
  removed.value = []
}

// append preserves order and returns the full list, so the last N entries are
// the N files just uploaded, in the order they were sent.
async function uploadImages(recordId: number, uploads: File[]) {
  const payload = new FormData()
  uploads.forEach((file) => payload.append('images', file))
  const response = await fetch(`/saved-links/${recordId}/images/append`, {
    method: 'POST',
    credentials: 'include',
    body: payload,
  })
  if (!response.ok) {
    const result = await response.json().catch(() => ({}))
    throw new Error(result.detail || '图片上传失败')
  }
  const saved = (await response.json()) as SavedLink
  const images = saved.images || []
  return images.slice(Math.max(0, images.length - uploads.length))
}

async function save() {
  if (!canSave.value) return
  saving.value = true
  try {
    const typed = form.description.trim()
    // Saved first without the blob refs so a failed upload can never leave
    // broken image links in a published article.
    const safeBody = stripPending(typed)
    const record = await api<SavedLink>(id.value ? `/saved-links/${id.value}` : '/saved-links', {
      method: id.value ? 'PUT' : 'POST',
      body: JSON.stringify(buildPayload(safeBody)),
    })

    await applyRemovals(record.id)

    // A line can be deleted by hand after picking, so only upload blobs the body
    // still references; the rest are dropped.
    const live = pending.value.filter((item) => typed.includes(item.url))
    pending.value.filter((item) => !live.includes(item)).forEach((item) => URL.revokeObjectURL(item.url))
    pending.value = live
    const uploads = [...live.map((item) => item.file), ...galleryFiles.value]
    if (uploads.length) {
      const fresh = await uploadImages(record.id, uploads)
      let finalBody = typed
      live.forEach((item, index) => {
        const target = fresh[index]
        if (target) finalBody = finalBody.split(item.url).join(target.url)
      })
      finalBody = finalBody.trim()
      if (finalBody !== safeBody) {
        await api<SavedLink>(`/saved-links/${record.id}`, {
          method: 'PUT',
          body: JSON.stringify(buildPayload(finalBody)),
        })
      }
      pending.value.forEach((item) => URL.revokeObjectURL(item.url))
      pending.value = []
      galleryPreviews.value.forEach(URL.revokeObjectURL)
      galleryFiles.value = []
      galleryPreviews.value = []
    }

    const toast = await toastController.create({
      message: articleMode.value ? '文章已保存' : '帖子已保存',
      duration: 1400,
      color: 'success',
    })
    await toast.present()
    router.replace(`/tabs/detail/links/${record.id}`)
  } catch (error) {
    await showError(error, '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
onUnmounted(() => {
  pending.value.forEach((item) => URL.revokeObjectURL(item.url))
  galleryPreviews.value.forEach(URL.revokeObjectURL)
})
</script>

<template>
  <IonPage>
    <PageHeader :title="heading" :subtitle="articleMode ? '支持 Markdown' : '链接广场'" back />
    <IonContent>
      <div v-if="loading" class="editor-loading"><IonSpinner />正在加载</div>
      <main v-else class="editor">
        <section class="editor-meta">
          <input v-model="form.title" class="editor-title" :class="{ 'is-missing': !form.title.trim() }" maxlength="100" :placeholder="articleMode ? '文章标题' : '帖子标题'">
          <div class="editor-meta-row">
            <input v-model="form.category" maxlength="50" :placeholder="articleMode ? '分类，例如：店铺教程' : '分类，例如：工作安排'">
            <input v-model.number="form.sort_order" type="number" inputmode="numeric" min="0" max="9999" placeholder="排序">
          </div>
        </section>

        <section class="editor-shell">
          <div class="editor-modes">
            <button :class="{ active: mode === 'write' }" @click="mode = 'write'">编辑</button>
            <button :class="{ active: mode === 'split' }" @click="mode = 'split'">分栏</button>
            <button :class="{ active: mode === 'preview' }" @click="mode = 'preview'">预览</button>
          </div>
          <div v-show="mode === 'write'" class="editor-toolbar">
            <button v-for="tool in tools" :key="tool.label" type="button" :title="tool.hint" @click="tool.apply()">{{ tool.label }}</button>
            <button type="button" class="tool-image" title="插入图片" @click="pickInlineImages">
              <IonIcon :icon="imageOutline" />图片
            </button>
          </div>
          <textarea
            v-show="mode !== 'preview'"
            ref="body"
            v-model="form.description"
            class="editor-body"
            :placeholder="articleMode ? '从这里开始写正文。点上方“图片”把图插进当前位置，支持 Markdown 和链接' : '输入内容、工作说明或相关链接'"
          ></textarea>
          <div v-show="mode !== 'write'" class="editor-preview">
            <h1 v-if="form.title">{{ form.title }}</h1>
            <div v-if="previewHtml" class="editor-preview-content" v-html="previewHtml"></div>
            <p v-else class="editor-preview-empty">正文还是空的</p>
          </div>
        </section>

        <input ref="inlinePicker" class="editor-hidden-file" type="file" accept="image/jpeg,image/png,image/webp" multiple @change="onInlinePick">

        <p v-if="pending.length" class="editor-pending-note">
          {{ pending.length }} 张新图待上传，保存后会替换正文里的临时地址。
          <button type="button" v-for="item in pending" :key="item.url" @click="dropPending(item)">撤销一张</button>
        </p>

        <section v-if="!articleMode" class="editor-extra">
          <label>主链接（选填）<input v-model="form.url" inputmode="url" placeholder="https://"></label>
          <label class="editor-switch">
            <span><b>置顶帖子</b><small>置顶后优先显示在广场顶部</small></span>
            <input v-model="form.is_pinned" type="checkbox">
          </label>
        </section>

        <!-- Posts show their images as a trailing gallery, so they keep a picker.
             Articles only surface leftovers that are not already in the body. -->
        <section v-if="!articleMode" class="editor-images">
          <div class="editor-images-head">
            <strong>帖子图片</strong>
            <label class="editor-pick"><IonIcon :icon="imageOutline" />选择图片<input type="file" accept="image/jpeg,image/png,image/webp" multiple @change="chooseGallery"></label>
          </div>
          <div v-if="keptImages.length || galleryPreviews.length" class="editor-image-grid">
            <div v-for="image in keptImages" :key="image.storage_name" class="editor-image">
              <img :src="image.url" :alt="image.name || form.title">
              <button type="button" aria-label="移除图片" @click="dropStored(image)"><IonIcon :icon="closeOutline" /></button>
            </div>
            <div v-for="(preview, index) in galleryPreviews" :key="preview" class="editor-image is-pending">
              <img :src="preview" alt="待上传图片">
              <button type="button" aria-label="取消这张图片" @click="dropGalleryFile(index)"><IonIcon :icon="closeOutline" /></button>
              <em>待上传</em>
            </div>
          </div>
        </section>

        <section v-else-if="strayImages.length" class="editor-images">
          <div class="editor-images-head">
            <strong>未插入正文的图片</strong>
            <span class="editor-images-count">{{ strayImages.length }} 张</span>
          </div>
          <p class="editor-images-hint">这些图会显示在文章末尾。点图片可插入正文，或移除。</p>
          <div class="editor-image-grid">
            <div v-for="image in strayImages" :key="image.storage_name" class="editor-image">
              <img :src="image.url" :alt="image.name || form.title" @click="insertStored(image)">
              <button type="button" aria-label="移除图片" @click="dropStored(image)"><IonIcon :icon="closeOutline" /></button>
            </div>
          </div>
        </section>
      </main>
    </IonContent>
    <footer class="editor-footer">
      <p v-if="!form.title.trim()" class="editor-footer-hint">请先填写最上方的{{ articleMode ? '文章标题' : '帖子标题' }}</p>
      <button @click="router.back()">取消</button>
      <button class="primary" :disabled="!canSave" @click="save">{{ saving ? '保存中…' : articleMode ? (id ? '保存修改' : '发布文章') : '保存帖子' }}</button>
    </footer>
  </IonPage>
</template>

<style scoped>
.editor-loading{display:flex;justify-content:center;gap:8px;padding:70px;color:var(--app-muted)}
.editor{display:flex;flex-direction:column;gap:10px;padding:12px 14px 24px}
.editor section{padding:14px;border:1px solid var(--app-line);border-radius:16px;background:var(--app-card)}

.editor-meta{display:grid;gap:10px}
/* Title is the only required field, so it gets at least as much visual weight as
   the optional category below it. It used to be borderless on a transparent
   background, which read as a section label -- people typed the title into the
   category box instead and then could not work out why 发布 stayed greyed out. */
.editor-title{width:100%;box-sizing:border-box;padding:11px;border:1px solid var(--app-line);border-radius:11px;outline:0;color:var(--app-text);background:var(--ion-background-color);font:700 19px inherit}
.editor-title.is-missing{border-color:#e5484d}
.editor-meta-row{display:grid;grid-template-columns:1fr;gap:10px}
.editor-meta-row:has(input+input){grid-template-columns:2fr 1fr}
.editor-meta-row input{width:100%;box-sizing:border-box;padding:11px;border:1px solid var(--app-line);border-radius:11px;outline:0;color:var(--app-text);background:var(--ion-background-color);font:16px inherit}

.editor-shell{display:flex;flex-direction:column;padding:0!important;overflow:hidden}
.editor-modes{display:grid;grid-template-columns:repeat(3,1fr);gap:3px;padding:4px;border-bottom:1px solid var(--app-line)}
.editor-modes button{height:34px;border:0;border-radius:9px;color:var(--app-muted);background:transparent;font:inherit;font-size:13px}
.editor-modes button.active{color:#1677ff;background:#eff5ff;font-weight:700}
.editor-toolbar{display:flex;gap:0;overflow-x:auto;padding:6px;border-bottom:1px solid var(--app-line);scrollbar-width:none}
.editor-toolbar::-webkit-scrollbar{display:none}
.editor-toolbar button{flex:0 0 auto;min-width:44px;height:36px;padding:0 10px;border:0;border-radius:9px;color:var(--app-text);background:transparent;font:inherit;font-size:13px}
.editor-toolbar button:active{background:var(--app-soft)}
.tool-image{display:inline-flex;align-items:center;gap:4px;color:#1677ff!important;font-weight:600}
.tool-image ion-icon{font-size:17px}
.editor-hidden-file{display:none}
.editor-body{width:100%;box-sizing:border-box;min-height:300px;padding:14px;border:0;outline:0;resize:vertical;color:var(--app-text);background:transparent;font:16px/1.7 inherit}
.editor-preview{min-height:300px;padding:14px;font-size:15px;line-height:1.75}
.editor-preview h1{margin:0 0 12px;font-size:21px;line-height:1.4}
.editor-preview p{margin:0 0 13px;white-space:pre-wrap;overflow-wrap:anywhere}
.editor-preview-content{overflow-wrap:anywhere}
.editor-preview-content :deep(p){margin:0 0 13px}
.editor-preview-content :deep(h1),.editor-preview-content :deep(h2),.editor-preview-content :deep(h3){margin:16px 0 8px;line-height:1.35}
.editor-preview-content :deep(ul),.editor-preview-content :deep(ol){padding-left:24px;margin:8px 0 14px}
.editor-preview-content :deep(blockquote){margin:12px 0;padding:8px 12px;border-left:3px solid #60a5fa;background:var(--app-soft);color:var(--app-muted)}
.editor-preview-content :deep(pre){overflow:auto;padding:12px;border-radius:10px;background:#111827;color:#e5e7eb}
.editor-preview-content :deep(code){padding:2px 4px;border-radius:4px;background:var(--app-soft);font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.editor-preview-content :deep(pre code){padding:0;background:transparent;color:inherit}
.editor-preview-content :deep(table){width:100%;border-collapse:collapse;margin:12px 0}
.editor-preview-content :deep(th),.editor-preview-content :deep(td){padding:7px 8px;border:1px solid var(--app-line);text-align:left}
.editor-preview-content :deep(img){display:block;max-width:100%;height:auto;border-radius:9px;margin:12px 0}
.editor-preview-content :deep(a){color:#1677ff}
.editor-preview-content :deep(.saved-link-align-center){text-align:center}
.editor-preview-content :deep(.saved-link-align-right){text-align:right}
.editor-preview .align-center{text-align:center}
.editor-preview .align-right{text-align:right}
.editor-preview a{color:#1677ff}
.editor-preview figure{margin:12px 0}
.editor-preview figure img{display:block;max-width:100%;border-radius:9px}
.editor-preview figure.align-center img{margin-inline:auto}
.editor-preview figure.align-right img{margin-left:auto}
.editor-preview-empty{color:var(--app-muted)}

.editor-pending-note{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin:0;padding:10px 13px!important;border:1px solid #bfdbfe!important;border-radius:12px!important;background:#eff6ff!important;color:#1d4ed8;font-size:11px;line-height:1.6}
.editor-pending-note button{padding:3px 8px;border:1px solid #93c5fd;border-radius:7px;color:#1d4ed8;background:#fff;font:inherit;font-size:10px}

.editor-extra{display:grid;gap:14px}
.editor-extra label{display:block;color:var(--app-muted);font-size:13px}
.editor-extra input:not([type=checkbox]){width:100%;box-sizing:border-box;margin-top:7px;padding:11px;border:1px solid var(--app-line);border-radius:11px;outline:0;color:var(--app-text);background:var(--ion-background-color);font:16px inherit}
.editor-switch{display:flex;align-items:center;justify-content:space-between;gap:12px;color:var(--app-text)}
.editor-switch b,.editor-switch small{display:block}
.editor-switch small{margin-top:3px;color:var(--app-muted);font-size:10px}
.editor-switch input{width:22px;height:22px;margin:0;flex:none}

.editor-images-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
.editor-images-head strong{font-size:14px}
.editor-images-count{color:var(--app-muted);font-size:11px}
.editor-pick{display:inline-flex;align-items:center;gap:5px;padding:8px 12px;border:1px solid #60a5fa;border-radius:10px;color:#1677ff;background:#eff6ff;font-size:13px}
.editor-pick input{display:none}
.editor-images-hint{margin:9px 0 0;color:var(--app-muted);font-size:11px;line-height:1.6}
.editor-image-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:11px}
.editor-image{position:relative}
.editor-image img{display:block;width:100%;height:88px;object-fit:cover;border-radius:10px;background:var(--app-soft)}
.editor-image button{position:absolute;right:4px;top:4px;width:22px;height:22px;display:grid;place-items:center;border:0;border-radius:50%;color:#fff;background:#0009;font-size:14px}
.editor-image.is-pending img{opacity:.72}
.editor-image em{position:absolute;left:4px;bottom:4px;padding:2px 6px;border-radius:6px;color:#fff;background:#0009;font-size:9px;font-style:normal}

.editor-footer{display:grid;grid-template-columns:1fr 2fr;gap:10px;padding:10px 14px calc(10px + env(safe-area-inset-bottom));border-top:1px solid var(--app-line);background:var(--app-card)}
.editor-footer button{height:46px;border:1px solid var(--app-line);border-radius:13px;color:var(--app-text);background:transparent;font:600 16px inherit}
.editor-footer .primary{color:#fff;border-color:#1677ff;background:#1677ff}
.editor-footer button:disabled{opacity:.5}
/* Spans both columns so it reads as a caption for the row, not a third button. */
.editor-footer-hint{grid-column:1/-1;margin:0 0 2px;color:#d4380d;font-size:13px}
.ion-palette-dark .editor-pick{background:#142b49}
.ion-palette-dark .editor-pending-note{border-color:#1e3a5f!important;background:#132338!important;color:#93c5fd}
.ion-palette-dark .editor-pending-note button{border-color:#1e40af;color:#93c5fd;background:#0f1e33}
</style>
