<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import {
  IonButton,
  IonContent,
  IonFooter,
  IonIcon,
  IonModal,
  IonPage,
  IonSpinner,
  IonTextarea,
  toastController,
} from '@ionic/vue'
import { arrowUpOutline, closeOutline, copyOutline, documentTextOutline, refreshOutline, searchOutline } from 'ionicons/icons'
import PageHeader from '../components/PageHeader.vue'

type KnowledgeDocument = {
  id: string
  title: string
  category?: string
  source?: string
  updated?: string
  path?: string
  content?: string
  score?: number
  images?: Array<string | { path: string; width?: number; height?: number }>
  blocks?: Array<{ type: string; text?: string; path?: string; width?: number; height?: number }>
  integrity_issues?: string[]
}
type ChatMessage = { id: string; role: 'user' | 'assistant'; text: string; sources?: KnowledgeDocument[] }

const tab = ref<'ask' | 'library' | 'quality'>('ask')
const question = ref('')
const sending = ref(false)
const documents = ref<KnowledgeDocument[]>([])
const quality = ref<KnowledgeDocument[]>([])
const messages = ref<ChatMessage[]>([])
const searchText = ref('')
const selectedDocument = ref<KnowledgeDocument | null>(null)
const contentRef = ref<InstanceType<typeof IonContent> | null>(null)

const filteredDocuments = computed(() => {
  const keyword = searchText.value.trim().toLowerCase()
  if (!keyword) return documents.value
  return documents.value.filter((item) => [item.title, item.category, item.path, item.content].some((value) => String(value || '').toLowerCase().includes(keyword)))
})

async function knowledgeApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/knowledge-api/${path.replace(/^\//, '')}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  const data = await response.json().catch(() => ({})) as T & { detail?: string; error?: string }
  if (!response.ok) throw new Error(data.detail || data.error || `请求失败（${response.status}）`)
  return data
}

async function notify(message: string, color?: string) {
  const toast = await toastController.create({ message, duration: 2200, color })
  await toast.present()
}

async function loadDocuments() {
  try {
    const data = await knowledgeApi<{ documents: KnowledgeDocument[] }>('documents')
    documents.value = Array.isArray(data.documents) ? data.documents : []
  } catch (error) {
    await notify(error instanceof Error ? error.message : '知识资料加载失败', 'danger')
  }
}

async function loadQuality() {
  try {
    const data = await knowledgeApi<{ documents: KnowledgeDocument[] }>('integrity')
    quality.value = Array.isArray(data.documents) ? data.documents : []
  } catch (error) {
    await notify(error instanceof Error ? error.message : '数据质量加载失败', 'danger')
  }
}

async function scrollToBottom() {
  await nextTick()
  await contentRef.value?.$el?.scrollToBottom?.(250)
}

async function sendQuestion() {
  const text = question.value.trim()
  if (!text || sending.value) return
  question.value = ''
  messages.value.push({ id: `user-${Date.now()}`, role: 'user', text })
  sending.value = true
  await scrollToBottom()
  try {
    const searchResult = await knowledgeApi<{ documents: KnowledgeDocument[] }>('search', {
      method: 'POST',
      body: JSON.stringify({ query: text, limit: 5 }),
    })
    const sources = Array.isArray(searchResult.documents) ? searchResult.documents : []
    if (!sources.length) throw new Error('知识库中没有找到相关资料')
    const result = await knowledgeApi<{ answer: string }>('chat', {
      method: 'POST',
      body: JSON.stringify({ question: text, documents: sources }),
    })
    messages.value.push({ id: `assistant-${Date.now()}`, role: 'assistant', text: result.answer || '暂时没有生成答案', sources })
  } catch (error) {
    messages.value.push({ id: `assistant-${Date.now()}`, role: 'assistant', text: `暂时无法回答：${error instanceof Error ? error.message : '请求失败'}` })
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}

function imageUrl(path?: string) {
  if (!path) return ''
  if (/^https?:\/\//i.test(path) || path.startsWith('/knowledge/')) return path
  return `/knowledge/${path.replace(/^\//, '')}`
}

function documentBlocks(document: KnowledgeDocument): Array<{ type: string; text?: string; path?: string }> {
  if (document.blocks?.length) return document.blocks
  return [{ type: 'text', text: document.content || '' }, ...(document.images || []).map((image) => ({ type: 'image', path: typeof image === 'string' ? image : image.path }))]
}

async function copyAnswer(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    await notify('回答已复制')
  } catch {
    await notify('复制失败，请长按选择文字', 'warning')
  }
}

async function reimport(document: KnowledgeDocument) {
  try {
    await knowledgeApi('reimport-document', { method: 'POST', body: JSON.stringify({ id: document.id }) })
    await notify('已启动重新采集')
    await loadQuality()
  } catch (error) {
    await notify(error instanceof Error ? error.message : '重新采集失败', 'danger')
  }
}

onMounted(() => Promise.all([loadDocuments(), loadQuality()]))
</script>

<template>
  <IonPage class="knowledge-page">
    <PageHeader title="知识问答" subtitle="内部规则与运营资料" back />
    <IonContent ref="contentRef" :scroll-y="true">
      <main class="knowledge-main">
        <nav class="knowledge-tabs">
          <button :class="{ active: tab === 'ask' }" @click="tab = 'ask'">问答</button>
          <button :class="{ active: tab === 'library' }" @click="tab = 'library'">资料 <small>{{ documents.length }}</small></button>
          <button :class="{ active: tab === 'quality' }" @click="tab = 'quality'">质量 <small>{{ quality.length }}</small></button>
        </nav>

        <section v-if="tab === 'ask'" class="chat-view">
          <div v-if="!messages.length" class="knowledge-welcome">
            <span class="welcome-icon"><IonIcon :icon="documentTextOutline" /></span>
            <h2>想了解什么？</h2>
            <p>答案会检索公司内部知识资料，并列出引用来源。</p>
            <button v-for="prompt in ['商品发布失败怎么排查？','如何优化推广投入产出比？','店铺运营有哪些风险项？']" :key="prompt" @click="question = prompt; sendQuestion()">{{ prompt }}</button>
          </div>
          <div v-for="message in messages" :key="message.id" class="chat-message" :class="message.role">
            <div class="chat-bubble">
              <div class="answer-text">{{ message.text }}</div>
              <div v-if="message.sources?.length" class="source-list">
                <b>引用来源</b>
                <button v-for="(source, index) in message.sources" :key="source.id" @click="selectedDocument = source">
                  <span>[{{ index + 1 }}]</span><em>{{ source.title }}</em><small>{{ source.updated || source.category }}</small>
                </button>
              </div>
              <button v-if="message.role === 'assistant'" class="copy-answer" @click="copyAnswer(message.text)"><IonIcon :icon="copyOutline" />复制</button>
            </div>
          </div>
          <div v-if="sending" class="chat-message assistant"><div class="chat-bubble loading"><IonSpinner name="dots" /> 正在检索并生成答案</div></div>
        </section>

        <section v-else-if="tab === 'library'" class="library-view">
          <label class="native-search"><IonIcon :icon="searchOutline" /><input v-model="searchText" inputmode="search" placeholder="搜索标题、分类或正文"></label>
          <button v-for="document in filteredDocuments" :key="document.id" class="document-row" @click="selectedDocument = document">
            <span class="document-icon"><IonIcon :icon="documentTextOutline" /></span>
            <span><b>{{ document.title }}</b><small>{{ document.path || document.category || '内部资料' }}</small></span>
            <em>{{ document.updated }}</em>
          </button>
          <div v-if="!filteredDocuments.length" class="empty-state">没有匹配的知识资料</div>
        </section>

        <section v-else class="quality-view">
          <div class="quality-summary"><div><b>{{ quality.length }}</b><span>篇资料需要检查</span></div><button @click="loadQuality"><IonIcon :icon="refreshOutline" />刷新</button></div>
          <article v-for="document in quality" :key="document.id" class="quality-row">
            <div><b>{{ document.title }}</b><small>{{ document.path || document.source }}</small></div>
            <div class="issue-tags"><span v-for="issue in document.integrity_issues" :key="issue">{{ issue }}</span></div>
            <button @click="reimport(document)">重新采集</button>
          </article>
          <div v-if="!quality.length" class="empty-state">当前资料质量正常</div>
        </section>
      </main>
    </IonContent>

    <IonFooter v-if="tab === 'ask'" class="knowledge-composer">
      <div class="composer-inner">
        <IonTextarea v-model="question" :auto-grow="true" :rows="1" :maxlength="1000" enterkeyhint="send" placeholder="输入问题，例如：商品发布失败后怎么排查？" @keydown.enter.exact.prevent="sendQuestion" />
        <IonButton :disabled="!question.trim() || sending" aria-label="发送" @click="sendQuestion"><IonIcon :icon="arrowUpOutline" /></IonButton>
      </div>
      <small>回答来自内部知识库，请以引用原文为准</small>
    </IonFooter>

    <IonModal :is-open="Boolean(selectedDocument)" @did-dismiss="selectedDocument = null">
      <IonPage v-if="selectedDocument" class="document-modal">
        <header><button @click="selectedDocument = null"><IonIcon :icon="closeOutline" /></button><div><b>{{ selectedDocument.title }}</b><small>{{ selectedDocument.category }} · {{ selectedDocument.updated }}</small></div></header>
        <IonContent><article class="document-body">
          <template v-for="(block, index) in documentBlocks(selectedDocument)" :key="index">
            <p v-if="block.type === 'text'">{{ block.text }}</p>
            <img v-else-if="block.type === 'image' && block.path" :src="imageUrl(block.path)" :alt="selectedDocument.title">
          </template>
        </article></IonContent>
      </IonPage>
    </IonModal>
  </IonPage>
</template>

<style scoped>
.knowledge-main{min-height:100%;padding:10px 12px 24px}.knowledge-tabs{position:sticky;top:0;z-index:5;display:grid;grid-template-columns:repeat(3,1fr);gap:4px;padding:5px;border:1px solid var(--app-line);border-radius:14px;background:color-mix(in srgb,var(--app-card) 94%,transparent);backdrop-filter:blur(18px)}.knowledge-tabs button{height:38px;border:0;border-radius:10px;color:var(--app-muted);background:transparent;font-weight:600}.knowledge-tabs button.active{color:#1677ff;background:color-mix(in srgb,#1677ff 12%,var(--app-card));box-shadow:0 1px 3px rgba(15,23,42,.08)}.knowledge-tabs small{font-size:10px}.chat-view{padding:14px 0}.knowledge-welcome{padding:44px 20px;text-align:center}.welcome-icon{width:58px;height:58px;margin:auto;display:grid;place-items:center;border-radius:20px;color:#1677ff;background:#eaf4ff;font-size:28px}.knowledge-welcome h2{margin:16px 0 6px;font-size:22px}.knowledge-welcome p{margin:0 0 22px;color:var(--app-muted);font-size:13px;line-height:1.6}.knowledge-welcome button{display:block;width:100%;margin:9px 0;padding:13px 14px;border:1px solid var(--app-line);border-radius:13px;text-align:left;color:var(--app-text);background:var(--app-card)}.chat-message{display:flex;margin:10px 0}.chat-message.user{justify-content:flex-end}.chat-bubble{max-width:88%;padding:13px 14px;border:1px solid var(--app-line);border-radius:16px;background:var(--app-card);box-shadow:0 4px 14px rgba(15,23,42,.04)}.user .chat-bubble{color:#fff;border-color:#1677ff;border-bottom-right-radius:5px;background:#1677ff}.assistant .chat-bubble{border-bottom-left-radius:5px}.answer-text{font-size:15px;line-height:1.72;white-space:pre-wrap;overflow-wrap:anywhere}.loading{display:flex;gap:8px;align-items:center;color:var(--app-muted)}.source-list{margin-top:14px;padding-top:12px;border-top:1px solid var(--app-line)}.source-list>b{font-size:12px}.source-list button{width:100%;display:grid;grid-template-columns:auto 1fr auto;gap:7px;margin-top:7px;padding:9px;border:0;border-radius:10px;text-align:left;color:var(--app-text);background:var(--ion-background-color)}.source-list span{color:#1677ff}.source-list em{font-style:normal;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.source-list small{color:var(--app-muted)}.copy-answer{display:flex;align-items:center;gap:4px;margin-top:9px;padding:5px 0;border:0;color:var(--app-muted);background:transparent}.native-search{height:44px;margin:12px 0;display:flex;align-items:center;gap:8px;padding:0 13px;border:1px solid var(--app-line);border-radius:13px;background:var(--app-card)}.native-search input{min-width:0;flex:1;border:0;outline:0;color:var(--app-text);background:transparent;font-size:16px}.document-row{width:100%;display:grid;grid-template-columns:38px 1fr auto;gap:10px;align-items:center;padding:13px 4px;border:0;border-bottom:1px solid var(--app-line);text-align:left;color:var(--app-text);background:transparent}.document-icon{width:36px;height:36px;display:grid;place-items:center;border-radius:11px;color:#1677ff;background:#eaf4ff}.document-row b,.document-row small{display:block}.document-row b{font-size:14px}.document-row small{max-width:230px;margin-top:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--app-muted);font-size:11px}.document-row em{font-style:normal;color:var(--app-muted);font-size:11px}.quality-summary{display:flex;align-items:center;justify-content:space-between;padding:18px 4px}.quality-summary b{font-size:25px}.quality-summary span{margin-left:6px;color:var(--app-muted);font-size:12px}.quality-summary button,.quality-row>button{border:0;border-radius:10px;padding:8px 11px;color:#1677ff;background:#eaf4ff}.quality-row{padding:15px 4px;border-bottom:1px solid var(--app-line)}.quality-row b,.quality-row small{display:block}.quality-row small{margin-top:5px;color:var(--app-muted);font-size:11px;line-height:1.5}.issue-tags{display:flex;flex-wrap:wrap;gap:5px;margin:9px 0}.issue-tags span{padding:4px 7px;border-radius:999px;color:#dc2626;background:#fee2e2;font-size:10px}.knowledge-composer{padding:8px 10px calc(7px + env(safe-area-inset-bottom));border-top:1px solid var(--app-line);background:color-mix(in srgb,var(--app-card) 96%,transparent);backdrop-filter:blur(20px)}.composer-inner{display:grid;grid-template-columns:1fr 42px;gap:8px;align-items:end}.composer-inner ion-textarea{min-height:42px;max-height:118px;overflow:auto;border:1px solid var(--app-line);border-radius:14px;--padding-start:12px;--padding-end:12px;--padding-top:10px;--padding-bottom:10px;--background:var(--ion-background-color);font-size:16px}.composer-inner ion-button{width:42px;height:42px;margin:0;--border-radius:13px}.knowledge-composer>small{display:block;margin-top:5px;text-align:center;color:var(--app-muted);font-size:10px}.document-modal header{display:grid;grid-template-columns:42px 1fr;gap:8px;align-items:center;padding:calc(10px + env(safe-area-inset-top)) 12px 10px;border-bottom:1px solid var(--app-line);background:var(--app-card)}.document-modal header button{width:40px;height:40px;border:1px solid var(--app-line);border-radius:12px;color:var(--app-text);background:transparent}.document-modal header b,.document-modal header small{display:block}.document-modal header b{font-size:16px}.document-modal header small{margin-top:3px;color:var(--app-muted);font-size:11px}.document-body{padding:18px 18px 50px}.document-body p{white-space:pre-wrap;line-height:1.75;font-size:15px}.document-body img{display:block;width:100%;height:auto;margin:12px 0;border-radius:12px}.ion-palette-dark .welcome-icon,.ion-palette-dark .document-icon,.ion-palette-dark .quality-summary button,.ion-palette-dark .quality-row>button{background:#142b49}.ion-palette-dark .issue-tags span{background:#451a1a}
</style>
