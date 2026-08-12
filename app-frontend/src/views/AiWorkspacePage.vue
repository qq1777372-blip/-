<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import MarkdownIt from "markdown-it";
import {
  IonContent, IonFooter, IonIcon, IonPage, IonSpinner, IonTextarea,
  onIonViewDidEnter, toastController,
} from "@ionic/vue";
import {
  addOutline, arrowUpOutline, attachOutline, chatbubblesOutline, checkmarkOutline, copyOutline,
  createOutline, documentOutline, downloadOutline, gitBranchOutline, globeOutline,
  imageOutline, libraryOutline, menuOutline, micOutline, optionsOutline, refreshOutline,
  shareSocialOutline, sparklesOutline, starOutline, stopOutline, trashOutline,
  volumeHighOutline,
} from "ionicons/icons";
import PageHeader from "../components/PageHeader.vue";
import { session } from "../session";

type Message = { id: string; role: "user" | "assistant"; content: string; imageUrl?: string; imageUrls?: string[] };
type Chat = { id: string; title: string; messages: Message[]; createdAt: number; updatedAt: number; modelId?: string; favorite?: boolean; archived?: boolean; folder?: string };
type Option = { id: string; name: string; model_type?: string; enabled?: number; hidden?: number; knowledge_id?: string; skill_ids?: string; tool_ids?: string };

const router = useRouter();
const tab = ref<"chat" | "history">("chat");
const chats = ref<Chat[]>([]);
const activeId = ref("");
const prompt = ref("");
const sending = ref(false);
const useKnowledge = ref(localStorage.getItem("ruoshop-app-ai-use-knowledge") === "true");
const useWebSearch = ref(false);
const imageMode = ref(false);
const imageSize = ref("1024x1024");
const pendingImages = ref<string[]>([]);
const toolsOpen = ref(false);
const recording = ref(false);
const uploading = ref(false);
const models = ref<Option[]>([]);
const knowledge = ref<Option[]>([]);
const skills = ref<Option[]>([]);
const tools = ref<Option[]>([]);
const selectedModelId = ref("");
const selectedKnowledgeId = ref("");
const selectedSkillIds = ref<string[]>([]);
const selectedToolIds = ref<string[]>([]);
const selectedAudioModelId = ref("");
const voice = ref("alloy");
const activeRequest = ref<AbortController | null>(null);
const contentRef = ref<InstanceType<typeof IonContent> | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const chatImportInput = ref<HTMLInputElement | null>(null);
const drawerOpen = ref(false);
const optionsOpen = ref(false);
const galleryOpen = ref(false);
const showArchived = ref(false);
const chatSearch = ref("");
let mediaRecorder: MediaRecorder | null = null;

const storageKey = computed(() => `ruoshop-ai-workspace:${session.user?.id || "local"}`);
const activeChat = computed(() => chats.value.find((c) => c.id === activeId.value) ?? null);
const userId = computed(() => String(session.user?.id || "local"));
const currentModelName = computed(() => models.value.find((m) => m.id === selectedModelId.value)?.name || "基础模型");
const md = new MarkdownIt({ html: false, breaks: true, linkify: true });
const audioModels = computed(() => models.value.filter((m) => m.model_type === "audio"));

const starters = [
  { icon: sparklesOutline, label: "推广数据诊断", text: "分析店铺推广数据时应该重点看哪些指标？" },
  { icon: chatbubblesOutline, label: "运营检查清单", text: "整理一份今天的店铺运营检查清单" },
  { icon: libraryOutline, label: "规则速查", text: "近期平台规则有哪些需要注意的变化？" },
];

const visibleChats = computed(() =>
  [...chats.value]
    .filter((c) => (showArchived.value ? c.archived : !c.archived) &&
      (!chatSearch.value || `${c.title} ${c.messages.map((m) => m.content).join(" ")}`.toLowerCase().includes(chatSearch.value.toLowerCase())))
    .sort((a, b) => Number(b.favorite) - Number(a.favorite) || b.updatedAt - a.updatedAt),
);

const galleryImages = computed(() =>
  chats.value.flatMap((chat) =>
    chat.messages.flatMap((msg, i) =>
      msg.imageUrl ? [{ url: msg.imageUrl, title: chat.title, prompt: [...chat.messages.slice(0, i)].reverse().find((m) => m.role === "user")?.content || "" }] : [],
    ),
  ),
);

watch(useKnowledge, (v) => localStorage.setItem("ruoshop-app-ai-use-knowledge", String(v)));

function uid() { return `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`; }
function renderMarkdown(value: string) { return md.render(value || ""); }

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/ai-api/${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-Workspace-User": userId.value, "X-Workspace-Role": session.user?.role || "user" },
    ...init,
  });
  const data = (await response.json().catch(() => ({}))) as T & { detail?: string; error?: string };
  if (!response.ok) throw new Error(data.detail || data.error || `请求失败（${response.status}）`);
  return data;
}

async function notify(message: string, color?: string) {
  const toast = await toastController.create({ message, duration: 1800, color });
  await toast.present();
}

function save() {
  localStorage.setItem(storageKey.value, JSON.stringify(chats.value.slice(0, 60)));
  void Promise.all(chats.value.slice(0, 60).map((chat) =>
    api("chats/save", { method: "POST", body: JSON.stringify({ id: chat.id, user_id: userId.value, title: chat.title, messages: chat.messages, model_id: chat.modelId || "", favorite: chat.favorite, archived: chat.archived, folder: chat.folder || "", created_at: Math.floor(chat.createdAt / 1000) }) }).catch(() => null)));
}

function createChat() {
  const now = Date.now();
  chats.value.unshift({ id: `chat-${uid()}`, title: "新对话", messages: [], modelId: selectedModelId.value, createdAt: now, updatedAt: now });
  activeId.value = chats.value[0].id;
  tab.value = "chat";
  drawerOpen.value = false;
  save();
}

function load() {
  try { const v = JSON.parse(localStorage.getItem(storageKey.value) || "[]"); chats.value = Array.isArray(v) ? v : []; }
  catch { chats.value = []; }
  if (chats.value.length) activeId.value = chats.value[0].id; else createChat();
}

function openChat(id: string) { activeId.value = id; tab.value = "chat"; drawerOpen.value = false; void scrollBottom(0); }

function removeChat(id: string) {
  chats.value = chats.value.filter((c) => c.id !== id);
  void api("chats/delete", { method: "POST", body: JSON.stringify({ id, user_id: userId.value }) }).catch(() => null);
  if (activeId.value === id) activeId.value = chats.value[0]?.id || "";
  if (!chats.value.length) createChat();
  save();
}

function toggleFavorite() { if (activeChat.value) { activeChat.value.favorite = !activeChat.value.favorite; save(); } }
function renameChat() { const c = activeChat.value; if (!c) return; const t = window.prompt("输入新名称", c.title)?.trim(); if (t) { c.title = t; c.updatedAt = Date.now(); save(); } }
function archiveChat() { const c = activeChat.value; if (!c) return; c.archived = !c.archived; showArchived.value = Boolean(c.archived); save(); }

function branchChat() {
  const src = activeChat.value; if (!src) return;
  const now = Date.now();
  chats.value.unshift({ id: `chat-${uid()}`, title: `${src.title} · 分支`, messages: structuredClone(src.messages), modelId: src.modelId, createdAt: now, updatedAt: now });
  activeId.value = chats.value[0].id; drawerOpen.value = false; save();
}

function exportChat() {
  const chat = activeChat.value; if (!chat) return;
  const blob = new Blob([JSON.stringify({ version: 1, exported_at: new Date().toISOString(), chat }, null, 2)], { type: "application/json" });
  const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = `${chat.title.replace(/[\\/:*?"<>|]+/g, "_")}.json`; link.click();
}

async function importChats(event: Event) {
  const input = event.target as HTMLInputElement; const file = input.files?.[0]; input.value = "";
  if (!file) return;
  try {
    const parsed = JSON.parse(await file.text()); const incoming = Array.isArray(parsed.chats) ? parsed.chats : parsed.chat ? [parsed.chat] : [];
    if (!incoming.length) throw new Error("文件中没有会话");
    const now = Date.now();
    for (const item of incoming) { if (!Array.isArray(item.messages)) continue; chats.value.unshift({ ...item, id: `chat-${uid()}`, title: String(item.title || "导入会话"), createdAt: Number(item.createdAt) || now, updatedAt: now }); }
    activeId.value = chats.value[0].id; save(); await notify(`已导入 ${incoming.length} 个会话`);
  } catch (e) { await notify(e instanceof Error ? e.message : "导入失败", "danger"); }
}

async function shareChat() {
  const chat = activeChat.value; if (!chat) return;
  try {
    const result = await api<{ id: string }>("shares", { method: "POST", body: JSON.stringify({ title: chat.title, messages: chat.messages }) });
    await navigator.clipboard.writeText(`${location.origin}/app/ai-workspace/shared/${result.id}`);
    await notify("分享链接已复制");
  } catch (e) { await notify(e instanceof Error ? e.message : "分享失败", "danger"); }
}

async function loadRemote() {
  try {
    const result = await api<{ chats: Array<{ id: string; title: string; messages: Message[]; model_id?: string; archived?: number; favorite?: number; folder?: string; created_at: number; updated_at: number }> }>(`chats?user_id=${encodeURIComponent(userId.value)}`);
    if (!result.chats.length) return;
    chats.value = result.chats.map((item) => ({ id: item.id, title: item.title, messages: item.messages || [], modelId: item.model_id || "", favorite: Boolean(item.favorite), archived: Boolean(item.archived), folder: item.folder || "", createdAt: item.created_at * 1000, updatedAt: item.updated_at * 1000 }));
    activeId.value = chats.value.find((c) => !c.archived)?.id || chats.value[0].id;
    restoreModel(); await scrollBottom(0);
  } catch {}
}

async function loadOptions() {
  try {
    const [m, k, s, t] = await Promise.all([api<{ models: Option[] }>("models"), api<{ knowledge: Option[] }>("knowledge"), api<{ skills: Option[] }>("skills"), api<{ tools: Option[] }>("tools")]);
    models.value = (m.models || []).filter((item) => item.enabled !== 0 && item.hidden !== 1);
    knowledge.value = k.knowledge || []; skills.value = s.skills || []; tools.value = t.tools || [];
    selectedAudioModelId.value = audioModels.value[0]?.id || "";
    restoreModel();
  } catch {}
}

function restoreModel() {
  const remembered = activeChat.value?.modelId || localStorage.getItem(`${storageKey.value}:selected-model`) || "";
  selectedModelId.value = models.value.some((m) => m.id === remembered) ? remembered : models.value[0]?.id || "";
}

watch(activeId, () => { restoreModel(); void scrollBottom(0); });
watch(selectedModelId, (id) => {
  localStorage.setItem(`${storageKey.value}:selected-model`, id);
  if (activeChat.value && activeChat.value.modelId !== id) { activeChat.value.modelId = id; save(); }
  const model = models.value.find((m) => m.id === id); if (!model) return;
  imageMode.value = model.model_type === "image";
  selectedKnowledgeId.value = model.knowledge_id || "";
  try { selectedSkillIds.value = JSON.parse(model.skill_ids || "[]"); } catch { selectedSkillIds.value = []; }
  try { selectedToolIds.value = JSON.parse(model.tool_ids || "[]"); } catch { selectedToolIds.value = []; }
});

async function scrollBottom(duration = 200) { await nextTick(); await contentRef.value?.$el?.scrollToBottom?.(duration); }

async function send(text = prompt.value) {
  const question = text.trim(); const chat = activeChat.value;
  if (!question || !chat || sending.value) return;
  const attachedImages = [...pendingImages.value]; pendingImages.value = []; prompt.value = "";
  chat.messages.push({ id: `user-${uid()}`, role: "user", content: question, imageUrls: attachedImages });
  if (chat.messages.length === 1) chat.title = question.slice(0, 20);
  sending.value = true; save(); await scrollBottom();
  toolsOpen.value = false;
  try {
    if (imageMode.value) {
      const assistant: Message = { id: `assistant-${uid()}`, role: "assistant", content: "正在生成图片…" };
      chat.messages.push(assistant);
      const result = await api<{ url: string }>("images/generations", { method: "POST", body: JSON.stringify({ prompt: question, model_id: selectedModelId.value || undefined, size: imageSize.value }) });
      assistant.content = ""; assistant.imageUrl = result.url; return;
    }
    let documents: unknown[] = [];
    const searchAbort = new AbortController();
    activeRequest.value = searchAbort;
    if (useKnowledge.value) {
      const result = await api<{ documents: unknown[] }>("search", { method: "POST", body: JSON.stringify({ query: question, limit: 5, knowledge_id: selectedKnowledgeId.value || undefined }) });
      documents = result.documents || [];
    }
    if (useWebSearch.value) {
      try { const result = await api<{ documents: unknown[] }>("web-search", { method: "POST", body: JSON.stringify({ query: question, limit: 5 }) }); documents.push(...(result.documents || [])); } catch {}
    }
    const assistant: Message = { id: `assistant-${uid()}`, role: "assistant", content: "" };
    chat.messages.push(assistant);
    activeRequest.value = new AbortController();
    const response = await fetch("/ai-api/chat/stream", {
      method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json", "X-Workspace-User": userId.value, "X-Workspace-Role": session.user?.role || "user" },
      signal: activeRequest.value.signal,
      body: JSON.stringify({ question, image_urls: attachedImages, documents, model_id: selectedModelId.value || undefined, skill_ids: selectedSkillIds.value, tool_ids: selectedToolIds.value }),
    });
    if (!response.ok) { const d = await response.json().catch(() => ({})); throw new Error(d.error || `请求失败（${response.status}）`); }
    const reader = response.body?.getReader(); const decoder = new TextDecoder(); let buffer = "";
    while (reader) {
      const { value, done } = await reader.read(); if (done) break;
      buffer += decoder.decode(value, { stream: true }); const lines = buffer.split("\n"); buffer = lines.pop() || "";
      for (const line of lines) if (line.trim()) assistant.content += JSON.parse(line).content || "";
      await scrollBottom();
    }
    if (!assistant.content) assistant.content = "模型没有返回内容";
  } catch (error) {
    if ((error as Error).name !== "AbortError") { const last = chat.messages.at(-1); if (last?.role === "assistant" && (!last.content || last.content === "正在生成图片…")) last.content = `${imageMode.value ? "图片生成失败" : "暂时无法回答"}：${error instanceof Error ? error.message : "请求失败"}`; }
  } finally { chat.updatedAt = Date.now(); sending.value = false; activeRequest.value = null; save(); await scrollBottom(); }
}

function stopGeneration() { activeRequest.value?.abort(); }

function editMessage(msg: Message) {
  const chat = activeChat.value; if (!chat) return;
  const idx = chat.messages.findIndex((m) => m.id === msg.id);
  const content = window.prompt("编辑消息", msg.content)?.trim();
  if (idx < 0 || !content) return; chat.messages.splice(idx); prompt.value = content; save();
}

function regenerate(msg: Message) {
  const chat = activeChat.value; if (!chat) return;
  const idx = chat.messages.findIndex((m) => m.id === msg.id);
  const userIdx = [...chat.messages.slice(0, idx)].map((m) => m.role).lastIndexOf("user");
  if (userIdx < 0) return;
  const question = chat.messages[userIdx].content; chat.messages.splice(userIdx); save(); void send(question);
}

function branchFrom(msg: Message) {
  const src = activeChat.value; if (!src) return;
  const idx = src.messages.findIndex((m) => m.id === msg.id); const now = Date.now();
  chats.value.unshift({ id: `chat-${uid()}`, title: `${src.title} · 分支`, messages: structuredClone(src.messages.slice(0, idx + 1)), modelId: src.modelId, createdAt: now, updatedAt: now });
  activeId.value = chats.value[0].id; save();
}

async function copy(content: string) {
  try { await navigator.clipboard.writeText(content); await notify("已复制"); }
  catch { await notify("复制失败，请长按选择", "warning"); }
}

async function saveAsNote(msg: Message) {
  const title = window.prompt("笔记标题", activeChat.value?.title || "AI 回答")?.trim(); if (!title) return;
  try { await api("notes", { method: "POST", body: JSON.stringify({ title, content: msg.content }) }); await notify("已保存到 Notes"); }
  catch (e) { await notify(e instanceof Error ? e.message : "保存失败", "danger"); }
}

async function exportAnswer(msg: Message, format: "docx" | "xlsx" | "pdf") {
  try {
    const result = await api<{ filename: string; mime: string; data: string }>("files/generate", { method: "POST", body: JSON.stringify({ title: activeChat.value?.title || "AI 输出", content: msg.content, format }) });
    const link = document.createElement("a"); link.href = `data:${result.mime};base64,${result.data}`; link.download = result.filename; link.click();
  } catch (e) { await notify(e instanceof Error ? e.message : "导出失败", "danger"); }
}

async function speak(msg: Message) {
  try {
    const result = await api<{ mime: string; data: string }>("audio/speech", { method: "POST", body: JSON.stringify({ text: msg.content, model_id: selectedAudioModelId.value || undefined, voice: voice.value }) });
    await new Audio(`data:${result.mime};base64,${result.data}`).play();
  } catch (e) { await notify(e instanceof Error ? e.message : "朗读失败", "danger"); }
}

async function toggleRecording() {
  if (recording.value) { mediaRecorder?.stop(); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true }); const chunks: Blob[] = [];
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
    mediaRecorder.onstop = async () => {
      recording.value = false; stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(chunks, { type: mediaRecorder?.mimeType || "audio/webm" });
      const data = await new Promise<string>((resolve, reject) => { const r = new FileReader(); r.onload = () => resolve(String(r.result || "").split(",", 2)[1] || ""); r.onerror = () => reject(new Error("读取失败")); r.readAsDataURL(blob); });
      try { const result = await api<{ text: string }>("audio/transcriptions", { method: "POST", body: JSON.stringify({ filename: "recording.webm", data, model_id: selectedAudioModelId.value || undefined }) }); prompt.value = [prompt.value, result.text].filter(Boolean).join(" "); }
      catch (e) { await notify(e instanceof Error ? e.message : "语音转写失败", "danger"); }
    };
    mediaRecorder.start(); recording.value = true;
  } catch (e) { await notify(e instanceof Error ? e.message : "无法使用麦克风", "danger"); }
}

async function importFiles(event: Event) {
  const input = event.target as HTMLInputElement; const files = [...(input.files || [])]; input.value = "";
  if (!files.length) return;
  const imageFiles = files.filter((f) => /^image\/(png|jpeg|webp)$/.test(f.type));
  if (imageFiles.length === files.length) {
    pendingImages.value = await Promise.all(imageFiles.slice(0, 4).map((f) => new Promise<string>((resolve, reject) => { const r = new FileReader(); r.onload = () => resolve(String(r.result || "")); r.onerror = () => reject(new Error(`${f.name} 读取失败`)); r.readAsDataURL(f); })));
    await notify(`已添加 ${pendingImages.value.length} 张图片`); return;
  }
  uploading.value = true;
  try {
    for (const file of files) {
      if (file.size > 15_000_000) throw new Error(`${file.name} 超过 15MB`);
      const data = await new Promise<string>((resolve, reject) => { const r = new FileReader(); r.onload = () => resolve(String(r.result || "").split(",", 2)[1] || ""); r.onerror = () => reject(new Error(`${file.name} 读取失败`)); r.readAsDataURL(file); });
      await api("documents/import-file", { method: "POST", body: JSON.stringify({ title: file.name.replace(/\.[^.]+$/, ""), filename: file.name, data }) });
    }
    useKnowledge.value = true; await notify(`已导入 ${files.length} 个文件`);
  } catch (e) { await notify(e instanceof Error ? e.message : "文件导入失败", "danger"); }
  finally { uploading.value = false; }
}

function downloadGallery() {
  galleryImages.value.forEach((item, i) => window.setTimeout(() => { const link = document.createElement("a"); link.href = item.url; link.download = `AI-image-${i + 1}.png`; link.click(); }, i * 180));
}
function regenerateImage(item: { prompt: string }) { galleryOpen.value = false; imageMode.value = true; prompt.value = item.prompt; }

onMounted(() => { load(); void scrollBottom(0); void loadRemote(); void loadOptions(); });
onIonViewDidEnter(() => { window.setTimeout(() => void scrollBottom(0), 0); });
</script>

<template>
  <IonPage class="ai-page">
    <PageHeader title="AI 工作台" subtitle="智能助理" back />

    <nav class="chat-toolbar">
      <button aria-label="打开对话记录" @click="drawerOpen = true"><IonIcon :icon="menuOutline" /><small v-if="chats.length">{{ chats.length }}</small></button>
      <strong>{{ activeChat?.title || '新对话' }}</strong>
      <button aria-label="新对话" @click="createChat"><IonIcon :icon="addOutline" /></button>
    </nav>

    <div v-if="drawerOpen" class="history-mask" @click.self="drawerOpen = false">
      <aside class="history-drawer">
        <header><div><strong>对话记录</strong><small>{{ chats.length }} 个会话</small></div><button aria-label="新对话" @click="createChat"><IonIcon :icon="addOutline" /></button></header>
        <label class="history-search"><IonIcon :icon="chatbubblesOutline" /><input v-model="chatSearch" placeholder="搜索对话记录" /></label>
        <div class="chat-filter">
          <button :class="{ on: !showArchived }" @click="showArchived = false">最近</button>
          <button :class="{ on: showArchived }" @click="showArchived = true">已归档</button>
        </div>
        <section class="compact-list">
          <div v-for="chat in visibleChats" :key="chat.id" class="compact-row chat-row" :class="{ on: chat.id === activeId }">
            <span class="chat-dot"><IonIcon :icon="chat.favorite ? starOutline : chatbubblesOutline" /></span>
            <div @click="openChat(chat.id)">
              <h3>{{ chat.title }}</h3>
              <p>{{ chat.messages.length }} 条 · {{ new Date(chat.updatedAt).toLocaleDateString("zh-CN") }}</p>
            </div>
            <button class="row-del" aria-label="删除对话" @click.stop="removeChat(chat.id)">
              <IonIcon :icon="trashOutline" />
            </button>
          </div>
        </section>
        <div v-if="!visibleChats.length" class="empty-state">暂无对话记录</div>

        <!-- current chat actions -->
        <div v-if="activeChat" class="chat-ops">
          <h2>当前对话</h2>
          <div class="ops-grid">
            <button @click="toggleFavorite"><IonIcon :icon="starOutline" />{{ activeChat.favorite ? '取消收藏' : '收藏' }}</button>
            <button @click="renameChat"><IonIcon :icon="createOutline" />重命名</button>
            <button @click="archiveChat"><IonIcon :icon="downloadOutline" />{{ activeChat.archived ? '恢复' : '归档' }}</button>
            <button @click="branchChat"><IonIcon :icon="gitBranchOutline" />分支</button>
            <button @click="shareChat"><IonIcon :icon="shareSocialOutline" />分享</button>
            <button @click="exportChat"><IonIcon :icon="downloadOutline" />导出</button>
            <button @click="chatImportInput?.click()"><IonIcon :icon="attachOutline" />导入</button>
          </div>
        </div>
        <input ref="chatImportInput" class="hidden-input" type="file" accept="application/json,.json" @change="importChats" />
      </aside>
    </div>

    <IonContent ref="contentRef">
      <main class="page-pad chat-pad">

        <!-- ── 欢迎页：全屏居中，无卡片容器 ── -->
        <div v-if="!activeChat?.messages.length" class="welcome-full">
          <div class="welcome-orb"><IonIcon :icon="sparklesOutline" /></div>
          <h1>今天需要分析什么？</h1>
          <p>结合内部知识库回答店铺运营与规则问题</p>
          <div class="welcome-chips">
            <button v-for="item in starters" :key="item.label" @click="send(item.text)">
              {{ item.label }}
            </button>
          </div>
        </div>

        <!-- pending images -->
        <div v-if="pendingImages.length" class="pending-imgs">
          <button v-for="(url, i) in pendingImages" :key="i" @click="pendingImages.splice(i, 1)">
            <img :src="url" alt="" /><span>×</span>
          </button>
        </div>

        <!-- ── 消息：用户气泡右，AI 卡片左侧竖线 ── -->
        <div v-for="msg in activeChat?.messages || []" :key="msg.id" class="turn" :class="msg.role">
          <div class="turn-body">
            <div v-if="msg.imageUrls?.length" class="chat-imgs">
              <img v-for="url in msg.imageUrls" :key="url.slice(-20)" :src="url" alt="" />
            </div>
            <div v-if="msg.imageUrl" class="generated-img">
              <img :src="msg.imageUrl" alt="生成图片" /><a :href="msg.imageUrl" download target="_blank">下载图片</a>
            </div>
            <div v-else-if="msg.role === 'assistant'" class="ai-card">
              <div class="md" v-html="renderMarkdown(msg.content)"></div>
              <div class="turn-actions">
                <button @click="copy(msg.content)"><IonIcon :icon="copyOutline" />复制</button>
                <button @click="saveAsNote(msg)"><IonIcon :icon="documentOutline" />Notes</button>
                <button @click="regenerate(msg)"><IonIcon :icon="refreshOutline" />重生成</button>
                <button @click="speak(msg)"><IonIcon :icon="volumeHighOutline" />朗读</button>
                <button @click="branchFrom(msg)"><IonIcon :icon="gitBranchOutline" />分支</button>
                <details class="export-menu"><summary>导出</summary><div><button @click="exportAnswer(msg, 'docx')">Word</button><button @click="exportAnswer(msg, 'xlsx')">Excel</button><button @click="exportAnswer(msg, 'pdf')">PDF</button></div></details>
              </div>
            </div>
            <div v-else class="user-bubble">
              <p>{{ msg.content }}</p>
            </div>
            <div v-if="msg.role === 'user'" class="turn-actions user-actions"><button @click="editMessage(msg)"><IonIcon :icon="createOutline" />编辑</button><button @click="branchFrom(msg)"><IonIcon :icon="gitBranchOutline" />分支</button></div>
          </div>
        </div>

        <div v-if="sending" class="turn assistant">
          <div class="turn-body">
            <div class="ai-card generating"><IonSpinner name="dots" /><span>正在生成回答…</span></div>
          </div>
        </div>
      </main>
    </IonContent>

    <!-- ── Composer：只露输入行，工具藏在 + 里 ── -->
    <IonFooter v-if="tab === 'chat'" class="ai-composer">
      <div v-if="toolsOpen" class="tools-panel">
        <div class="tools-grid">
          <button :class="{ on: imageMode }" @click="imageMode = !imageMode"><IonIcon :icon="imageOutline" /><span>生图</span></button>
          <button @click="galleryOpen = true"><IonIcon :icon="imageOutline" /><span>图库</span></button>
          <button v-if="!imageMode" :class="{ on: useKnowledge }" @click="useKnowledge = !useKnowledge"><IonIcon :icon="libraryOutline" /><span>知识</span></button>
          <button v-if="!imageMode" :class="{ on: useWebSearch }" @click="useWebSearch = !useWebSearch"><IonIcon :icon="globeOutline" /><span>联网</span></button>
          <button :disabled="uploading" @click="fileInput?.click()"><IonSpinner v-if="uploading" name="dots" /><IonIcon v-else :icon="attachOutline" /><span>附件</span></button>
          <button :class="{ on: recording }" @click="toggleRecording"><IonIcon :icon="recording ? stopOutline : micOutline" /><span>{{ recording ? '停止' : '语音' }}</span></button>
          <button :class="{ on: selectedSkillIds.length || selectedToolIds.length }" @click="optionsOpen = true"><IonIcon :icon="optionsOutline" /><span>能力</span></button>
          <button @click="toolsOpen = false"><IonIcon :icon="stopOutline" /><span>收起</span></button>
        </div>
        <div v-if="imageMode" class="tools-sub">
          <span>图片尺寸</span>
          <label><input v-model="imageSize" type="radio" value="1024x1024" />方图</label>
          <label><input v-model="imageSize" type="radio" value="1536x1024" />横图</label>
          <label><input v-model="imageSize" type="radio" value="1024x1536" />竖图</label>
        </div>
        <div v-if="pendingImages.length" class="pending-imgs-bar">
          <button v-for="(url, i) in pendingImages" :key="i" @click="pendingImages.splice(i, 1)">
            <img :src="url" alt="" /><span>×</span>
          </button>
        </div>
      </div>
      <div class="composer-box">
        <IonTextarea v-model="prompt" :auto-grow="true" :rows="1" :maxlength="2000" enterkeyhint="send"
          :placeholder="recording ? '正在录音…' : imageMode ? '描述要生成的图片' : '给 AI 发消息…'"
          @keydown.enter.exact.prevent="send()" />
        <div class="composer-controls">
          <div class="composer-left">
            <button class="plus-btn" :class="{ on: toolsOpen }" aria-label="工具" @click="toolsOpen = !toolsOpen"><IonIcon :icon="addOutline" /></button>
            <button class="model-chip" @click="optionsOpen = true">{{ currentModelName }}</button>
            <span v-if="useKnowledge" class="meta-badge">知识库</span>
            <span v-if="useWebSearch" class="meta-badge">联网</span>
            <span v-if="imageMode" class="meta-badge">生图</span>
          </div>
          <button v-if="sending" class="voice-send is-stop" aria-label="停止生成" @click="stopGeneration"><IonIcon :icon="stopOutline" /><span>停止</span></button>
          <button v-else-if="prompt.trim()" class="voice-send is-send" aria-label="发送" @click="send()"><IonIcon :icon="arrowUpOutline" /><span>发送</span></button>
          <button v-else class="voice-send" :class="{ recording }" @click="toggleRecording"><IonIcon :icon="recording ? stopOutline : micOutline" /><span>{{ recording ? '结束录音' : '开始说话' }}</span></button>
        </div>
      </div>
      <input ref="fileInput" class="hidden-input" type="file" multiple accept=".pdf,.docx,.txt,.md,.csv,.json,.png,.jpg,.jpeg,.webp" @change="importFiles" />
    </IonFooter>

    <!-- ── Options bottom sheet ── -->
    <div v-if="optionsOpen" class="sheet-mask" @click.self="optionsOpen = false">
      <aside class="bottom-sheet">
        <header><b>对话能力</b><button @click="optionsOpen = false">完成</button></header>
        <div class="sheet-links">
          <button @click="optionsOpen = false; router.push('/tabs/module/ai-models')">模型管理</button>
          <button @click="optionsOpen = false; router.push('/tabs/module/ai-knowledge')">知识库</button>
          <button @click="optionsOpen = false; router.push('/tabs/module/ai-operations')">运行与治理</button>
          <button @click="optionsOpen = false; router.push('/tabs/module/ai-capabilities')">能力库</button>
        </div>
        <section class="model-picker"><b>选择模型</b><div class="model-options">
          <button :class="{ on: !selectedModelId }" @click="selectedModelId = ''"><span>基础模型</span><IonIcon v-if="!selectedModelId" :icon="checkmarkOutline" /></button>
          <button v-for="item in models.filter(m => m.model_type !== 'audio')" :key="item.id" :class="{ on: selectedModelId === item.id }" @click="selectedModelId = item.id"><span>{{ item.name }}</span><IonIcon v-if="selectedModelId === item.id" :icon="checkmarkOutline" /></button>
        </div></section>
        <section v-if="audioModels.length" class="model-picker"><b>语音模型</b><div class="model-options compact">
          <button v-for="item in audioModels" :key="item.id" :class="{ on: selectedAudioModelId === item.id }" @click="selectedAudioModelId = item.id"><span>{{ item.name }}</span><IonIcon v-if="selectedAudioModelId === item.id" :icon="checkmarkOutline" /></button>
        </div></section>
        <section v-if="audioModels.length" class="voice-picker"><b>音色</b><div><button v-for="item in ['alloy','echo','nova','shimmer']" :key="item" :class="{ on: voice === item }" @click="voice = item">{{ item }}</button></div></section>
        <section v-if="useKnowledge" class="model-picker"><b>知识集合</b><div class="model-options compact">
          <button :class="{ on: !selectedKnowledgeId }" @click="selectedKnowledgeId = ''"><span>全部知识</span><IonIcon v-if="!selectedKnowledgeId" :icon="checkmarkOutline" /></button>
          <button v-for="item in knowledge" :key="item.id" :class="{ on: selectedKnowledgeId === item.id }" @click="selectedKnowledgeId = item.id"><span>{{ item.name }}</span><IonIcon v-if="selectedKnowledgeId === item.id" :icon="checkmarkOutline" /></button>
        </div></section>
        <section v-if="skills.length"><b>Skills</b>
          <label v-for="item in skills" :key="item.id"><input v-model="selectedSkillIds" type="checkbox" :value="item.id" />{{ item.name }}</label>
        </section>
        <section v-if="tools.length"><b>Tools</b>
          <label v-for="item in tools" :key="item.id"><input v-model="selectedToolIds" type="checkbox" :value="item.id" />{{ item.name }}</label>
        </section>
      </aside>
    </div>

    <!-- ── Gallery bottom sheet ── -->
    <div v-if="galleryOpen" class="sheet-mask" @click.self="galleryOpen = false">
      <aside class="bottom-sheet gallery-sheet">
        <header><b>生成图片历史</b><span><button v-if="galleryImages.length" @click="downloadGallery">全部下载</button><button @click="galleryOpen = false">关闭</button></span></header>
        <div class="gallery-grid">
          <article v-for="item in galleryImages" :key="item.url">
            <img :src="item.url" :alt="item.title" /><span>{{ item.title }}</span>
            <footer>
              <a :href="item.url" download target="_blank">下载</a>
              <button :disabled="!item.prompt" @click="regenerateImage(item)">再次生成</button>
            </footer>
          </article>
          <p v-if="!galleryImages.length">暂无生成图片</p>
        </div>
      </aside>
    </div>
  </IonPage>
</template>

<style scoped>
.hidden-input { display: none; }

.chat-toolbar{height:44px;padding:0 10px;display:grid;grid-template-columns:40px minmax(0,1fr) 40px;align-items:center;border-bottom:1px solid var(--app-line);background:var(--app-card)}
.chat-toolbar>button{position:relative;width:36px;height:36px;padding:0;border:0;display:grid;place-items:center;color:var(--app-text);background:transparent;font-size:21px}
.chat-toolbar>button:last-child{color:var(--app-blue)}
.chat-toolbar>button small{position:absolute;top:1px;right:0;min-width:15px;height:15px;padding:0 3px;border-radius:999px;display:grid;place-items:center;color:#fff;background:var(--app-blue);font-size:8px}
.chat-toolbar>strong{overflow:hidden;text-align:center;text-overflow:ellipsis;white-space:nowrap;font-size:13px;font-weight:600}
.history-mask{position:fixed;z-index:1100;inset:0;background:rgba(15,23,42,.4)}
.history-drawer{width:min(86vw,340px);height:100%;padding:calc(12px + env(safe-area-inset-top)) 12px calc(16px + env(safe-area-inset-bottom));overflow-y:auto;background:var(--ion-background-color);box-shadow:10px 0 35px rgba(15,23,42,.18);animation:drawer-in .22s ease-out both}
.history-drawer>header{height:48px;display:flex;align-items:center;justify-content:space-between}
.history-drawer>header strong,.history-drawer>header small{display:block}.history-drawer>header strong{font-size:17px}.history-drawer>header small{margin-top:2px;color:var(--app-muted);font-size:10px}
.history-drawer>header button{width:36px;height:36px;padding:0;border:0;border-radius:9px;display:grid;place-items:center;color:var(--app-blue);background:var(--app-card);font-size:21px}
.history-search{height:40px;margin:8px 0 12px;padding:0 11px;border:1px solid var(--app-line);border-radius:10px;display:flex;align-items:center;gap:8px;color:var(--app-muted);background:var(--app-card)}
.history-search input{min-width:0;flex:1;border:0;outline:0;color:var(--app-text);background:transparent;font-size:13px}
.history-search ion-icon{font-size:16px}.history-drawer .compact-list{max-height:46vh;overflow-y:auto}.history-drawer .chat-ops h2{margin:18px 2px 8px;font-size:13px}
@keyframes drawer-in{from{transform:translateX(-100%)}to{transform:none}}

/* ── Chat area ── */
.chat-pad { width: min(100%, 720px); margin: 0 auto; padding-bottom: 20px; }

/* ── Welcome: full-height centered, no card ── */
.welcome-full { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 60vh; padding: 32px 24px; text-align: center; }
.welcome-orb { width: 72px; height: 72px; margin-bottom: 20px; display: grid; place-items: center; border-radius: 26px; color: #fff; background: linear-gradient(135deg, var(--app-blue) 0%, #7c3aed 100%); font-size: 34px; box-shadow: 0 10px 30px rgba(25,145,255,.28); }
.welcome-full h1 { margin: 0 0 8px; font-size: 22px; font-weight: 700; }
.welcome-full p { margin: 0 0 28px; color: var(--app-muted); font-size: 13px; line-height: 1.65; }
.welcome-chips { display: flex; flex-wrap: wrap; justify-content: center; gap: 9px; }
.welcome-chips button { padding: 10px 16px; border: 1px solid var(--app-line); border-radius: 999px; color: var(--app-text); background: var(--app-card); font-size: 13px; box-shadow: 0 1px 4px rgba(15,23,42,.05); }
.welcome-chips button:active { background: color-mix(in srgb, var(--app-blue) 6%, var(--app-card)); }

.pending-imgs { display: flex; gap: 6px; margin: 8px 0; overflow-x: auto; }
.pending-imgs button { position: relative; width: 52px; height: 52px; flex-shrink: 0; padding: 0; overflow: hidden; border: 1px solid var(--app-line); border-radius: 10px; }
.pending-imgs img { width: 100%; height: 100%; object-fit: cover; }
.pending-imgs span { position: absolute; top: 1px; right: 3px; color: #fff; font-size: 14px; }

/* ── Messages ── */
.turn { margin: 14px 0; }
.turn.user { display: flex; justify-content: flex-end; }

/* AI card: full-width, left blue stripe */
.ai-card { padding: 14px 14px 10px 18px; border-left: 3px solid var(--app-blue); border-radius: 0 12px 12px 0; background: var(--app-card); box-shadow: 0 2px 8px rgba(15,23,42,.04); }
.ai-card.generating { display: flex; align-items: center; gap: 8px; color: var(--app-muted); font-size: 13px; }

/* user bubble: pill on the right */
.user-bubble { max-width: 80%; padding: 12px 16px; border-radius: 18px 18px 4px 18px; background: var(--app-blue); color: #fff; }
.user-bubble p { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 14px; line-height: 1.72; }

.chat-imgs { display: flex; gap: 6px; overflow-x: auto; margin-bottom: 8px; }
.chat-imgs img { width: 88px; height: 88px; border-radius: 10px; object-fit: cover; flex-shrink: 0; }
.generated-img { display: grid; gap: 6px; }
.generated-img img { max-width: 100%; max-height: 52vh; border-radius: 10px; }
.generated-img a { color: var(--app-blue); font-size: 11px; text-decoration: none; }

.turn-actions { display: flex; flex-wrap: wrap; gap: 2px 10px; margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--app-line); }
.turn-actions button { display: flex; align-items: center; gap: 3px; padding: 4px 0; border: 0; color: var(--app-muted); background: transparent; font-size: 10px; }
.turn-actions ion-icon { font-size: 13px; }
.user-actions { border-top-color: rgba(255,255,255,.2); }
.user-actions button { color: rgba(255,255,255,.8); }

.md :deep(p) { margin: 0 0 8px; font-size: 14px; line-height: 1.75; }
.md :deep(p:last-child) { margin-bottom: 0; }
.md :deep(ul), .md :deep(ol) { margin: 7px 0; padding-left: 20px; font-size: 14px; }
.md :deep(pre) { overflow: auto; margin: 9px 0; padding: 11px; border-radius: 10px; background: #111827; color: #e5e7eb; font: 11px/1.6 monospace; }
.md :deep(code) { padding: 1px 4px; border-radius: 4px; background: color-mix(in srgb, var(--app-blue) 9%, var(--app-card)); font: 11px monospace; }
.md :deep(pre code) { padding: 0; background: transparent; }
.md :deep(table) { display: block; overflow: auto; border-collapse: collapse; font-size: 11px; }
.md :deep(th), .md :deep(td) { padding: 6px; border: 1px solid var(--app-line); }

/* ── History ── */
.link-action { display: flex; align-items: center; gap: 3px; border: 0; color: var(--app-blue); background: transparent; font-size: 11px; }
.link-action ion-icon { font-size: 14px; }
.chat-filter { display: flex; gap: 4px; margin-bottom: 10px; }
.chat-filter button { height: 28px; padding: 0 12px; border: 1px solid var(--app-line); border-radius: 999px; color: var(--app-muted); background: transparent; font-size: 11px; }
.chat-filter button.on { color: var(--app-blue); border-color: var(--app-blue); background: color-mix(in srgb, var(--app-blue) 8%, transparent); }
.chat-row { cursor: pointer; }
.chat-row.on { background: color-mix(in srgb, var(--app-blue) 7%, transparent); }
.chat-row > div { min-width: 0; }
.chat-dot { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 11px; color: var(--app-blue); background: color-mix(in srgb, var(--app-blue) 12%, var(--app-card)); font-size: 17px; }
.row-del { width: 32px; height: 32px; display: grid; place-items: center; border: 0; border-radius: 9px; color: var(--app-muted); background: transparent; font-size: 16px; }
.ops-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.ops-grid button { height: 40px; display: flex; align-items: center; justify-content: center; gap: 4px; border: 0; border-radius: 12px; color: var(--app-muted); background: var(--app-card); font-size: 11px; }
.ops-grid ion-icon { font-size: 15px; }

/* ── Composer: clean single row + expandable tools ── */
.ai-composer { padding: 8px 12px calc(7px + env(safe-area-inset-bottom)); border-top: 1px solid var(--app-line); background: color-mix(in srgb, var(--app-card) 97%, transparent); box-shadow: 0 -5px 22px rgba(15,23,42,.05); backdrop-filter: blur(20px); }
.composer-box{padding:6px 8px 7px;border:1px solid var(--app-line);border-radius:18px;background:var(--ion-background-color);box-shadow:0 4px 18px rgba(15,23,42,.06)}
.composer-box ion-textarea{min-height:38px;max-height:120px;overflow:auto;--padding-start:4px;--padding-end:4px;--padding-top:7px;--padding-bottom:5px;--background:transparent;font-size:16px}
.composer-controls{min-width:0;display:flex;align-items:center;justify-content:space-between;gap:7px}
.composer-left{min-width:0;display:flex;align-items:center;gap:5px;overflow-x:auto;scrollbar-width:none}.composer-left::-webkit-scrollbar{display:none}
.plus-btn { flex:none;width:30px;height:30px;display:grid;place-items:center;border:1px solid var(--app-line);border-radius:50%;color:var(--app-text);background:var(--app-card);font-size:20px;transition:transform .15s; }
.plus-btn.on { transform: rotate(45deg); color: var(--app-blue); border-color: var(--app-blue); }
.model-chip { flex-shrink: 0;max-width:100px;height:28px;padding:0 9px;overflow:hidden;border:0;border-radius:999px;text-overflow:ellipsis;white-space:nowrap;color:var(--app-text);background:var(--app-card);font-size:10px;font-weight:600; }
.meta-badge { flex-shrink: 0; height: 20px; padding: 0 8px; border-radius: 999px; color: var(--app-blue); background: color-mix(in srgb, var(--app-blue) 12%, transparent); font-size: 10px; line-height: 20px; }
.voice-send{flex:none;height:32px;padding:0 12px;border:0;border-radius:999px;display:flex;align-items:center;gap:5px;color:#fff;background:var(--app-blue);box-shadow:0 3px 10px color-mix(in srgb,var(--app-blue) 28%,transparent);font-size:11px;font-weight:600}.voice-send ion-icon{font-size:15px}.voice-send.recording,.voice-send.is-stop{background:#ef4444;box-shadow:none}.voice-send.is-send{width:34px;padding:0;justify-content:center;background:var(--app-blue)}.voice-send.is-send span{display:none}

/* ── Tools panel (expands above composer-row) ── */
.tools-panel { padding-bottom: 9px; border-bottom: 1px solid var(--app-line); margin-bottom: 8px; }
.tools-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 7px; }
.tools-grid button { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 5px; height: 58px; border: 0; border-radius: 14px; color: var(--app-muted); background: var(--ion-background-color); font-size: 10px; }
.tools-grid button ion-icon { font-size: 22px; }
.tools-grid button.on { color: var(--app-blue); background: color-mix(in srgb, var(--app-blue) 11%, var(--app-card)); }
.tools-sub { display: flex; align-items: center; gap: 12px; margin-top: 7px; font-size: 11px; color: var(--app-muted); }
.tools-sub label { display: flex; align-items: center; gap: 4px; color: var(--app-text); }
.pending-imgs-bar { display: flex; gap: 6px; margin-top: 8px; overflow-x: auto; }
.pending-imgs-bar button { position: relative; width: 48px; height: 48px; flex-shrink: 0; padding: 0; overflow: hidden; border: 1px solid var(--app-line); border-radius: 10px; }
.pending-imgs-bar img { width: 100%; height: 100%; object-fit: cover; }
.pending-imgs-bar span { position: absolute; top: 1px; right: 3px; color: #fff; font-size: 14px; }

/* ── Bottom sheets ── */
.sheet-mask { position: fixed; z-index: 1000; inset: 0; display: flex; align-items: flex-end; background: rgba(15,23,42,.4); backdrop-filter: blur(2px); }
.bottom-sheet { width: 100%; max-height: 78vh; overflow-y: auto; padding: 10px 14px calc(20px + env(safe-area-inset-bottom)); border-radius: 14px 14px 0 0; background: var(--ion-background-color); }
.bottom-sheet header { display: flex; justify-content: space-between; align-items: center; min-height: 48px; }
.bottom-sheet header b { font-size: 16px; }
.bottom-sheet header button, .bottom-sheet header span button { border: 0; color: var(--app-blue); background: transparent; font-size: 13px; }
.bottom-sheet header span { display: flex; gap: 8px; }
.bottom-sheet > label { display: grid; gap: 6px; margin-top: 12px; padding: 12px; border-radius: 12px; background: var(--app-card); color: var(--app-muted); font-size: 11px; }
.bottom-sheet > label select { height: 40px; padding: 0 10px; border: 0; border-radius: 10px; color: var(--app-text); background: var(--ion-background-color); }
.bottom-sheet section { margin-top: 12px; padding: 12px; border-radius: 12px; background: var(--app-card); }
.bottom-sheet section b { display: block; margin-bottom: 8px; color: var(--app-muted); font-size: 11px; }
.bottom-sheet section label { display: flex; align-items: center; gap: 8px; min-height: 34px; font-size: 13px; color: var(--app-text); }
.bottom-sheet section input[type="checkbox"] { width: 17px; height: 17px; }
.bottom-sheet .model-picker{padding:10px 8px 8px}.bottom-sheet .model-picker>b{padding:2px 5px 8px;font-size:12px}.model-options{max-height:240px;overflow-y:auto;border-radius:9px;background:var(--ion-background-color)}.model-options button{width:100%;min-height:42px;padding:8px 11px;border:0;border-bottom:1px solid var(--app-line);display:flex;align-items:center;justify-content:space-between;gap:10px;text-align:left;color:var(--app-text);background:transparent;font-size:13px}.model-options button:last-child{border-bottom:0}.model-options button span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.model-options button ion-icon{flex:none;color:var(--app-blue);font-size:18px}.model-options button.on{color:var(--app-blue);background:color-mix(in srgb,var(--app-blue) 9%,var(--app-card));font-weight:600}
.model-options.compact{max-height:168px}.bottom-sheet .voice-picker{padding:10px}.voice-picker>div{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px}.voice-picker>div button{height:32px;padding:0 4px;border:1px solid var(--app-line);border-radius:8px;color:var(--app-muted);background:var(--ion-background-color);font-size:10px;text-transform:capitalize}.voice-picker>div button.on{border-color:var(--app-blue);color:#fff;background:var(--app-blue)}
.sheet-links { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 6px; }
.sheet-links button { min-height: 42px; border: 0; border-radius: 12px; color: var(--app-blue); background: var(--app-card); font-size: 13px; }

.gallery-sheet { max-height: 82vh; }
.gallery-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.gallery-grid article { display: grid; overflow: hidden; border: 1px solid var(--app-line); border-radius: 12px; }
.gallery-grid img { width: 100%; aspect-ratio: 1; object-fit: cover; }
.gallery-grid span { padding: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 10px; }
.gallery-grid footer { display: grid; grid-template-columns: 1fr 1fr; }
.gallery-grid footer a, .gallery-grid footer button { padding: 7px; border: 0; border-top: 1px solid var(--app-line); text-align: center; color: var(--app-blue); background: transparent; font-size: 10px; text-decoration: none; }
.gallery-grid footer button:disabled { color: var(--app-muted); }
.gallery-grid p { grid-column: 1/-1; padding: 40px; text-align: center; color: var(--app-muted); }

.ion-palette-dark .welcome-orb { box-shadow: 0 10px 30px rgba(25,145,255,.15); }
.ion-palette-dark .welcome-chips button, .ion-palette-dark .ai-composer { box-shadow: none; }
.ion-palette-dark .ai-card { background: var(--app-card); box-shadow: none; }

/* Mobile chat message layout. Kept after the legacy rules to resolve their duplicate selectors. */
.chat-pad{padding-right:12px;padding-left:12px}
.turn{margin:18px 0!important}
.turn-body{max-width:100%}
.assistant .turn-body{width:100%}
.ai-card{padding:0!important;border:0!important;border-radius:0!important;background:transparent!important;box-shadow:none!important}
.user .turn-body{max-width:82%!important;padding:0!important;border-radius:0!important;color:inherit!important;background:transparent!important}
.user-bubble{width:max-content;max-width:100%!important;margin-left:auto;padding:9px 13px!important;border-radius:14px 14px 4px 14px!important;background:var(--app-blue)!important;color:#fff!important}
.user-bubble p{font-size:14px;line-height:1.55!important}
.turn-actions{gap:2px 14px!important;margin-top:9px!important;padding-top:8px!important}
.assistant .turn-actions{border-top:1px solid var(--app-line)!important}
.user-actions{justify-content:flex-end;margin-top:5px!important;padding-top:0!important;border-top:0!important}
.user-actions button{color:var(--app-muted)!important}
.turn-actions button{min-height:28px;padding:4px 0!important;font-size:11px!important}
.export-menu{position:relative;color:var(--app-muted);font-size:11px}
.export-menu summary{min-height:28px;display:flex;align-items:center;cursor:pointer;list-style:none}
.export-menu summary::-webkit-details-marker{display:none}
.export-menu[open] summary{color:var(--app-blue)}
.export-menu div{position:absolute;z-index:4;right:0;bottom:32px;min-width:92px;padding:5px;border:1px solid var(--app-line);border-radius:8px;background:var(--app-card);box-shadow:0 8px 24px #0f172a1a}
.export-menu div button{width:100%;padding:7px 9px!important;border-radius:5px;text-align:left}
.export-menu div button:active{background:var(--app-soft)}

/* ── Chat area ── */
.chat-pad { width: min(100%, 720px); margin: 0 auto; padding-bottom: 20px; }

.starter { padding: 26px 0 0; text-align: center; }
.starter-icon { width: 52px; height: 52px; margin: 0 auto; display: grid; place-items: center; border-radius: 16px; color: #fff; background: linear-gradient(135deg, var(--app-blue), #7c3aed); font-size: 26px; }
.starter h1 { margin: 14px 0 5px; font-size: 19px; }
.starter p { margin: 0 0 20px; padding: 0 20px; color: var(--app-muted); font-size: 12px; line-height: 1.6; }
.starter button { width: 100%; display: grid; grid-template-columns: 34px 1fr auto; align-items: center; gap: 8px; min-height: 52px; padding: 0 14px; border: 0; border-top: 1px solid var(--app-line); text-align: left; color: var(--app-text); background: transparent; }
.starter button ion-icon { color: var(--app-blue); font-size: 19px; }
.starter button b { font-size: 14px; font-weight: 500; }
.starter button i { color: var(--app-muted); font-size: 19px; font-style: normal; }

.pending-imgs { display: flex; gap: 6px; margin: 8px 0; overflow-x: auto; }
.pending-imgs button { position: relative; width: 52px; height: 52px; flex-shrink: 0; padding: 0; overflow: hidden; border: 1px solid var(--app-line); border-radius: 10px; }
.pending-imgs img { width: 100%; height: 100%; object-fit: cover; }
.pending-imgs span { position: absolute; top: 1px; right: 3px; color: #fff; font-size: 14px; }

.turn { display: flex; gap: 9px; margin: 16px 0; }
.turn.user { justify-content: flex-end; }
.turn-avatar { flex-shrink: 0; width: 30px; height: 30px; display: grid; place-items: center; border-radius: 50%; color: #fff; background: linear-gradient(135deg, var(--app-blue), #7c3aed); font-size: 15px; }
.turn-body { min-width: 0; }
.assistant .turn-body { flex: 1; font-size: 14px; line-height: 1.75; }
.user .turn-body { max-width: 84%; padding: 11px 14px; border-radius: 14px 14px 5px 14px; color: #fff; background: var(--app-blue); }
.user .turn-body p { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 14px; line-height: 1.72; }
.waiting { display: flex; align-items: center; gap: 7px; color: var(--app-muted); font-size: 13px; }

.chat-imgs { display: flex; gap: 6px; overflow-x: auto; margin-bottom: 8px; }
.chat-imgs img { width: 88px; height: 88px; border-radius: 10px; object-fit: cover; flex-shrink: 0; }
.generated-img { display: grid; gap: 6px; }
.generated-img img { max-width: 100%; max-height: 52vh; border-radius: 10px; }
.generated-img a { color: var(--app-blue); font-size: 11px; text-decoration: none; }

.turn-actions { display: flex; flex-wrap: wrap; gap: 4px 12px; margin-top: 7px; padding-top: 7px; border-top: 1px solid var(--app-line); }
.turn-actions button { display: flex; align-items: center; gap: 3px; padding: 3px 0; border: 0; color: var(--app-muted); background: transparent; font-size: 10px; }
.turn-actions ion-icon { font-size: 13px; }
.user .turn-actions { border-top-color: rgba(255,255,255,.22); }
.user .turn-actions button { color: rgba(255,255,255,.82); }

.md :deep(p) { margin: 0 0 8px; line-height: 1.75; }
.md :deep(p:last-child) { margin-bottom: 0; }
.md :deep(ul), .md :deep(ol) { margin: 7px 0; padding-left: 20px; }
.md :deep(pre) { overflow: auto; margin: 9px 0; padding: 11px; border-radius: 10px; background: #111827; color: #e5e7eb; font: 11px/1.6 monospace; }
.md :deep(code) { padding: 1px 4px; border-radius: 4px; background: var(--app-card); font: 11px monospace; }
.md :deep(pre code) { padding: 0; background: transparent; }
.md :deep(table) { display: block; overflow: auto; border-collapse: collapse; font-size: 11px; }
.md :deep(th), .md :deep(td) { padding: 6px; border: 1px solid var(--app-line); }

/* ── History ── */
.link-action { display: flex; align-items: center; gap: 3px; border: 0; color: var(--app-blue); background: transparent; font-size: 11px; }
.link-action ion-icon { font-size: 14px; }
.chat-filter { display: flex; gap: 4px; margin-bottom: 10px; }
.chat-filter button { height: 28px; padding: 0 12px; border: 1px solid var(--app-line); border-radius: 999px; color: var(--app-muted); background: transparent; font-size: 11px; }
.chat-filter button.on { color: var(--app-blue); border-color: var(--app-blue); background: color-mix(in srgb, var(--app-blue) 8%, transparent); }
.chat-row { cursor: pointer; }
.chat-row.on { background: color-mix(in srgb, var(--app-blue) 7%, transparent); }
.chat-row > div { min-width: 0; cursor: pointer; }
.chat-dot { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 11px; color: var(--app-blue); background: color-mix(in srgb, var(--app-blue) 12%, var(--app-card)); font-size: 17px; }
.row-del { width: 32px; height: 32px; display: grid; place-items: center; border: 0; border-radius: 9px; color: var(--app-muted); background: transparent; font-size: 16px; }
.ops-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.ops-grid button { height: 40px; display: flex; align-items: center; justify-content: center; gap: 4px; border: 0; border-radius: 12px; color: var(--app-muted); background: var(--app-card); font-size: 11px; }
.ops-grid ion-icon { font-size: 15px; }

/* ── Composer ── */
.ai-composer { padding: 8px 12px calc(7px + env(safe-area-inset-bottom)); border-top: 1px solid var(--app-line); background: color-mix(in srgb, var(--app-card) 97%, transparent); box-shadow: 0 -5px 22px rgba(15,23,42,.05); backdrop-filter: blur(20px); }
.composer-tools { display: flex; gap: 5px; padding-bottom: 7px; overflow-x: auto; scrollbar-width: none; }
.composer-tools::-webkit-scrollbar { display: none; }
.composer-tools select, .composer-tools button { flex-shrink: 0; height: 30px; padding: 0 9px; border: 0; border-radius: 10px; color: var(--app-muted); background: var(--ion-background-color); font-size: 10px; }
.composer-tools button { display: flex; align-items: center; gap: 3px; }
.composer-tools button.on { color: var(--app-blue); background: color-mix(in srgb, var(--app-blue) 11%, var(--app-card)); }
.composer-tools ion-icon { font-size: 14px; }
.composer-input { display: grid; grid-template-columns: minmax(0,1fr) 40px; gap: 7px; align-items: end; padding: 4px 4px 4px 12px; border: 1px solid var(--app-line); border-radius: 14px; background: var(--ion-background-color); }
.composer-input ion-textarea { min-height: 40px; max-height: 120px; overflow: auto; margin: 0; --padding-start: 0; --padding-end: 0; --padding-top: 10px; --padding-bottom: 8px; --background: transparent; font-size: 16px; }
.composer-input ion-button { width: 40px; height: 40px; margin: 0; --border-radius: 11px; }
.ai-composer > small { display: block; margin-top: 5px; text-align: center; color: var(--app-muted); font-size: 10px; }

/* ── Bottom sheets ── */
.sheet-mask { position: fixed; z-index: 1000; inset: 0; display: flex; align-items: flex-end; background: rgba(15,23,42,.4); backdrop-filter: blur(2px); }
.bottom-sheet { width: 100%; max-height: 78vh; overflow-y: auto; padding: 10px 14px calc(20px + env(safe-area-inset-bottom)); border-radius: 14px 14px 0 0; background: var(--ion-background-color); }
.bottom-sheet header { display: flex; justify-content: space-between; align-items: center; min-height: 48px; }
.bottom-sheet header b { font-size: 16px; }
.bottom-sheet header button, .bottom-sheet header span button { border: 0; color: var(--app-blue); background: transparent; font-size: 13px; }
.bottom-sheet header span { display: flex; gap: 8px; }
.bottom-sheet > label { display: grid; gap: 6px; margin-top: 12px; padding: 12px; border-radius: 12px; background: var(--app-card); color: var(--app-muted); font-size: 11px; }
.bottom-sheet > label select { height: 40px; padding: 0 10px; border: 0; border-radius: 10px; color: var(--app-text); background: var(--ion-background-color); }
.bottom-sheet section { margin-top: 12px; padding: 12px; border-radius: 12px; background: var(--app-card); }
.bottom-sheet section b { display: block; margin-bottom: 8px; color: var(--app-muted); font-size: 11px; }
.bottom-sheet section label { display: flex; align-items: center; gap: 8px; min-height: 34px; font-size: 13px; color: var(--app-text); }
.bottom-sheet section input[type="checkbox"] { width: 17px; height: 17px; }
.sheet-links { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 6px; }
.sheet-links button { min-height: 42px; border: 0; border-radius: 12px; color: var(--app-blue); background: var(--app-card); font-size: 13px; }

.gallery-sheet { max-height: 82vh; }
.gallery-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.gallery-grid article { display: grid; overflow: hidden; border: 1px solid var(--app-line); border-radius: 12px; }
.gallery-grid img { width: 100%; aspect-ratio: 1; object-fit: cover; }
.gallery-grid span { padding: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 10px; }
.gallery-grid footer { display: grid; grid-template-columns: 1fr 1fr; }
.gallery-grid footer a, .gallery-grid footer button { padding: 7px; border: 0; border-top: 1px solid var(--app-line); text-align: center; color: var(--app-blue); background: transparent; font-size: 10px; text-decoration: none; }
.gallery-grid footer button:disabled { color: var(--app-muted); }
.gallery-grid p { grid-column: 1/-1; padding: 40px; text-align: center; color: var(--app-muted); }

.ion-palette-dark .starter, .ion-palette-dark .ai-composer { box-shadow: none; }
</style>
