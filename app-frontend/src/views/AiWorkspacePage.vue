<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import MarkdownIt from "markdown-it";
import {
  IonButton, IonContent, IonFooter, IonIcon, IonPage, IonSpinner, IonTextarea,
  onIonViewDidEnter, toastController,
} from "@ionic/vue";
import {
  addOutline, arrowUpOutline, attachOutline, chatbubblesOutline, copyOutline,
  createOutline, documentOutline, downloadOutline, gitBranchOutline, globeOutline,
  imageOutline, libraryOutline, micOutline, optionsOutline, refreshOutline,
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

    <nav class="ai-switch">
      <button :class="{ on: tab === 'chat' }" @click="tab = 'chat'">对话</button>
      <button :class="{ on: tab === 'history' }" @click="tab = 'history'">
        记录<small v-if="chats.length">{{ chats.length }}</small>
      </button>
      <button class="new-chat-btn" aria-label="新对话" @click="createChat">
        <IonIcon :icon="addOutline" />
      </button>
    </nav>

    <!-- ── History tab ── -->
    <IonContent v-if="tab === 'history'">
      <main class="page-pad">
        <div class="section-title">
          <h2>历史对话</h2>
          <button class="link-action" @click="createChat"><IonIcon :icon="addOutline" />新对话</button>
        </div>
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
          <div class="section-title" style="margin-top:22px"><h2>当前对话操作</h2></div>
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
      </main>
    </IonContent>

    <!-- ── Chat tab ── -->
    <IonContent v-else ref="contentRef">
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
                <button @click="exportAnswer(msg, 'docx')">Word</button>
                <button @click="exportAnswer(msg, 'xlsx')">Excel</button>
                <button @click="exportAnswer(msg, 'pdf')">PDF</button>
                <button @click="branchFrom(msg)"><IonIcon :icon="gitBranchOutline" />分支</button>
              </div>
            </div>
            <div v-else class="user-bubble">
              <p>{{ msg.content }}</p>
              <div class="turn-actions user-actions">
                <button @click="editMessage(msg)"><IonIcon :icon="createOutline" />编辑</button>
                <button @click="branchFrom(msg)"><IonIcon :icon="gitBranchOutline" />分支</button>
              </div>
            </div>
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
      <div class="composer-row">
        <button class="plus-btn" :class="{ on: toolsOpen }" aria-label="工具" @click="toolsOpen = !toolsOpen">
          <IonIcon :icon="addOutline" />
        </button>
        <IonTextarea v-model="prompt" :auto-grow="true" :rows="1" :maxlength="2000" enterkeyhint="send"
          :placeholder="recording ? '正在录音…' : imageMode ? '描述要生成的图片' : '给 AI 发消息…'"
          @keydown.enter.exact.prevent="send()" />
        <IonButton v-if="sending" color="medium" aria-label="停止" @click="stopGeneration"><IonIcon :icon="stopOutline" /></IonButton>
        <IonButton v-else :disabled="!prompt.trim()" aria-label="发送" @click="send()"><IonIcon :icon="arrowUpOutline" /></IonButton>
      </div>
      <div class="composer-meta">
        <button class="model-chip" @click="optionsOpen = true">{{ currentModelName }}</button>
        <span v-if="useKnowledge" class="meta-badge">知识库</span>
        <span v-if="useWebSearch" class="meta-badge">联网</span>
        <span v-if="imageMode" class="meta-badge">生图</span>
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
        <label>模型
          <select v-model="selectedModelId">
            <option value="">基础模型</option>
            <option v-for="item in models.filter(m => m.model_type !== 'audio')" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
        </label>
        <label v-if="audioModels.length">语音模型
          <select v-model="selectedAudioModelId">
            <option v-for="item in audioModels" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
        </label>
        <label v-if="audioModels.length">音色
          <select v-model="voice">
            <option value="alloy">Alloy</option><option value="echo">Echo</option>
            <option value="nova">Nova</option><option value="shimmer">Shimmer</option>
          </select>
        </label>
        <label v-if="useKnowledge">知识集合
          <select v-model="selectedKnowledgeId">
            <option value="">全部知识</option>
            <option v-for="item in knowledge" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
        </label>
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

/* ── Tab switch ── */
.ai-switch { display: grid; grid-template-columns: 1fr 1fr 40px; padding: 8px 14px 0; background: var(--ion-background-color); gap: 0; }
.ai-switch button { height: 36px; border: 0; border-bottom: 2px solid transparent; color: var(--app-muted); background: transparent; font-size: 14px; font-weight: 600; }
.ai-switch button.on { color: var(--app-blue); border-bottom-color: var(--app-blue); }
.ai-switch small { margin-left: 4px; padding: 1px 5px; border-radius: 999px; background: color-mix(in srgb, var(--app-blue) 14%, transparent); font-size: 10px; }
.new-chat-btn { width: 36px; height: 36px; display: grid; place-items: center; border: 0 !important; border-bottom: none !important; color: var(--app-blue) !important; font-size: 22px; }

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
.composer-row { display: grid; grid-template-columns: 36px minmax(0,1fr) 40px; gap: 8px; align-items: end; }
.plus-btn { width: 36px; height: 36px; display: grid; place-items: center; border: 1px solid var(--app-line); border-radius: 12px; color: var(--app-muted); background: transparent; font-size: 22px; transition: transform .15s; }
.plus-btn.on { transform: rotate(45deg); color: var(--app-blue); border-color: var(--app-blue); }
.composer-row ion-textarea { min-height: 36px; max-height: 120px; overflow: auto; border: 1px solid var(--app-line); border-radius: 14px; --padding-start: 12px; --padding-end: 12px; --padding-top: 8px; --padding-bottom: 8px; --background: var(--ion-background-color); font-size: 16px; }
.composer-row ion-button { width: 40px; height: 40px; margin: 0; --border-radius: 13px; }

.composer-meta { display: flex; align-items: center; gap: 6px; margin-top: 5px; overflow-x: auto; scrollbar-width: none; }
.composer-meta::-webkit-scrollbar { display: none; }
.model-chip { flex-shrink: 0; height: 22px; padding: 0 9px; border: 0; border-radius: 999px; color: var(--app-muted); background: var(--ion-background-color); font-size: 10px; }
.meta-badge { flex-shrink: 0; height: 20px; padding: 0 8px; border-radius: 999px; color: var(--app-blue); background: color-mix(in srgb, var(--app-blue) 12%, transparent); font-size: 10px; line-height: 20px; }

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
