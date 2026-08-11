<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import MarkdownIt from "markdown-it";
import {
  IonButton,
  IonContent,
  IonFooter,
  IonIcon,
  IonPage,
  IonSpinner,
  IonTextarea,
  onIonViewDidEnter,
  toastController,
} from "@ionic/vue";
import {
  addOutline,
  arrowUpOutline,
  archiveOutline,
  attachOutline,
  chatbubblesOutline,
  copyOutline,
  createOutline,
  documentOutline,
  downloadOutline,
  gitBranchOutline,
  globeOutline,
  imageOutline,
  libraryOutline,
  menuOutline,
  micOutline,
  optionsOutline,
  refreshOutline,
  searchOutline,
  shareSocialOutline,
  starOutline,
  stopOutline,
  trashOutline,
  volumeHighOutline,
} from "ionicons/icons";
import PageHeader from "../components/PageHeader.vue";
import { session } from "../session";

type Source = {
  id: string;
  title: string;
  category?: string;
  updated?: string;
  content?: string;
  url?: string;
  chunk_id?: string;
};
type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  imageUrl?: string;
  imageUrls?: string[];
  sources?: Source[];
};
type Chat = {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
  modelId?: string;
  favorite?: boolean;
  parentChatId?: string;
  archived?: boolean;
  folder?: string;
};
type Option = {
  id: string;
  name: string;
  title?: string;
  command?: string;
  content?: string;
  description?: string;
  knowledge_id?: string;
  skill_ids?: string;
  tool_ids?: string;
  model_type?: string;
  enabled?: number;
  hidden?: number;
};

const router = useRouter();
const chats = ref<Chat[]>([]);
const activeId = ref("");
const prompt = ref("");
const sending = ref(false);
const drawerOpen = ref(false);
const chatSearch = ref(""),
  showArchived = ref(false),
  selectedFolder = ref("");
const remoteSearchResults = ref<Array<{ id: string; title: string; snippet?: string }>>([]);
const searchingChats = ref(false);
const useKnowledge = ref(localStorage.getItem("ruoshop-app-ai-use-knowledge") === "true");
const useWebSearch = ref(false);
const imageMode = ref(false),
  imageSize = ref("1024x1024"),
  pendingImages = ref<string[]>([]);
const galleryOpen = ref(false),
  selectedAudioModelId = ref(""),
  voice = ref("alloy");
const optionsOpen = ref(false);
const models = ref<Option[]>([]),
  knowledge = ref<Option[]>([]),
  skills = ref<Option[]>([]),
  tools = ref<Option[]>([]),
  prompts = ref<Option[]>([]);
const selectedModelId = ref(""),
  selectedKnowledgeId = ref(""),
  selectedSkillIds = ref<string[]>([]),
  selectedToolIds = ref<string[]>([]);
const activeRequest = ref<AbortController | null>(null);
const uploading = ref(false);
const recording = ref(false);
let mediaRecorder: MediaRecorder | null = null;
const fileInput = ref<HTMLInputElement | null>(null);
const chatImportInput = ref<HTMLInputElement | null>(null);
const contentRef = ref<InstanceType<typeof IonContent> | null>(null);
const storageKey = computed(
  () => `ruoshop-ai-workspace:${session.user?.id || "local"}`,
);
const activeChat = computed(
  () => chats.value.find((item) => item.id === activeId.value) || null,
);
const visibleChats = computed(() => {
  const query = chatSearch.value.trim().toLowerCase();
  return [...chats.value]
    .filter(
      (chat) =>
        (showArchived.value ? chat.archived : !chat.archived) &&
        (!selectedFolder.value || chat.folder === selectedFolder.value) &&
        (!query ||
          `${chat.title} ${chat.messages.map((message) => message.content).join(" ")}`
            .toLowerCase()
            .includes(query)),
    )
    .sort(
      (a, b) =>
        Number(b.favorite) - Number(a.favorite) || b.updatedAt - a.updatedAt,
    );
});
const folders = computed(
  () =>
    [
      ...new Set(chats.value.map((chat) => chat.folder).filter(Boolean)),
    ] as string[],
);
const promptMatches = computed(() =>
  prompt.value.startsWith("/")
    ? prompts.value
        .filter((item) =>
          `/${item.command} ${item.title}`
            .toLowerCase()
            .includes(prompt.value.toLowerCase()),
        )
        .slice(0, 6)
    : [],
);
const galleryImages = computed(() =>
  chats.value.flatMap((chat) =>
    chat.messages.flatMap((message, index) =>
      message.imageUrl
        ? [
            {
              url: message.imageUrl,
              title: chat.title,
              prompt:
                [...chat.messages.slice(0, index)]
                  .reverse()
                  .find((item) => item.role === "user")?.content || "",
            },
          ]
        : [],
    ),
  ),
);
const audioModels = computed(() =>
  models.value.filter((model) => model.model_type === "audio"),
);
const userId = computed(() => String(session.user?.id || "local"));
const markdown = new MarkdownIt({ html: false, breaks: true, linkify: true });
watch(useKnowledge, value => localStorage.setItem("ruoshop-app-ai-use-knowledge", String(value)));
function renderMarkdown(value: string) {
  return markdown.render(value || "");
}

function uid(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}
function save() {
  localStorage.setItem(
    storageKey.value,
    JSON.stringify(chats.value.slice(0, 60)),
  );
  void Promise.all(
    chats.value
      .slice(0, 60)
      .map((chat) =>
        api("chats/save", {
          method: "POST",
          body: JSON.stringify({
            id: chat.id,
            user_id: userId.value,
            title: chat.title,
            messages: chat.messages,
            model_id: chat.modelId || "",
            favorite: chat.favorite,
            archived: chat.archived,
            folder: chat.folder || "",
            parent_chat_id: chat.parentChatId || "",
            created_at: Math.floor(chat.createdAt / 1000),
          }),
        }).catch(() => null),
      ),
  );
}
function createChat() {
  const now = Date.now(),
    chat: Chat = {
      id: uid("chat"),
      title: "新对话",
      messages: [],
      modelId: selectedModelId.value,
      createdAt: now,
      updatedAt: now,
    };
  chats.value.unshift(chat);
  activeId.value = chat.id;
  drawerOpen.value = false;
  save();
}
function load() {
  try {
    const value = JSON.parse(localStorage.getItem(storageKey.value) || "[]");
    chats.value = Array.isArray(value) ? value : [];
  } catch {
    chats.value = [];
  }
  if (chats.value.length) activeId.value = chats.value[0].id;
  else createChat();
}
function selectChat(id: string) {
  activeId.value = id;
  drawerOpen.value = false;
  void scrollBottom();
}
async function searchChats() {
  const query = chatSearch.value.trim();
  if (!query) { remoteSearchResults.value = []; return; }
  searchingChats.value = true;
  try {
    const result = await api<{ results: Array<{ id: string; title: string; snippet?: string }> }>("chats/search", { method: "POST", body: JSON.stringify({ query }) });
    remoteSearchResults.value = result.results || [];
  } catch (error) {
    const toast = await toastController.create({ message: error instanceof Error ? error.message : "搜索失败", duration: 1800 });
    await toast.present();
  } finally { searchingChats.value = false; }
}
async function openSearchResult(item: { id: string }) {
  if (!chats.value.some(chat => chat.id === item.id)) await loadRemote();
  if (chats.value.some(chat => chat.id === item.id)) selectChat(item.id);
  remoteSearchResults.value = [];
}
function removeChat(id: string) {
  chats.value = chats.value.filter((item) => item.id !== id);
  void api("chats/delete", {
    method: "POST",
    body: JSON.stringify({ id, user_id: userId.value }),
  }).catch(() => null);
  if (activeId.value === id) activeId.value = chats.value[0]?.id || "";
  if (!chats.value.length) createChat();
  save();
}
function toggleFavorite() {
  if (!activeChat.value) return;
  activeChat.value.favorite = !activeChat.value.favorite;
  save();
}
function renameChat() {
  const chat = activeChat.value;
  if (!chat) return;
  const title = window.prompt("输入新的会话名称", chat.title)?.trim();
  if (!title) return;
  chat.title = title;
  chat.updatedAt = Date.now();
  save();
}
function archiveChat() {
  const chat = activeChat.value;
  if (!chat) return;
  chat.archived = !chat.archived;
  chat.updatedAt = Date.now();
  showArchived.value = Boolean(chat.archived);
  save();
}
function moveToFolder() {
  const chat = activeChat.value;
  if (!chat) return;
  const folder =
    window
      .prompt("输入文件夹名称，留空移出文件夹", chat.folder || "")
      ?.trim() || "";
  chat.folder = folder;
  selectedFolder.value = folder;
  save();
}
function branchChat() {
  const source = activeChat.value;
  if (!source) return;
  const now = Date.now(),
    chat: Chat = {
      id: uid("chat"),
      title: `${source.title} · 分支`,
      messages: structuredClone(source.messages),
      modelId: source.modelId,
      parentChatId: source.id,
      createdAt: now,
      updatedAt: now,
    };
  chats.value.unshift(chat);
  activeId.value = chat.id;
  drawerOpen.value = false;
  save();
}
function exportChat() {
  const chat = activeChat.value;
  if (!chat) return;
  const blob = new Blob(
      [
        JSON.stringify(
          { version: 1, exported_at: new Date().toISOString(), chat },
          null,
          2,
        ),
      ],
      { type: "application/json" },
    ),
    url = URL.createObjectURL(blob),
    link = document.createElement("a");
  link.href = url;
  link.download = `${chat.title.replace(/[\\/:*?"<>|]+/g, "_")}.json`;
  link.click();
  URL.revokeObjectURL(url);
}
async function importChats(event: Event) {
  const input = event.target as HTMLInputElement,
    file = input.files?.[0];
  input.value = "";
  if (!file) return;
  try {
    const parsed = JSON.parse(await file.text()),
      incoming = Array.isArray(parsed.chats)
        ? parsed.chats
        : parsed.chat
          ? [parsed.chat]
          : [];
    if (!incoming.length) throw new Error("文件中没有会话");
    const now = Date.now();
    for (const item of incoming) {
      if (!Array.isArray(item.messages)) continue;
      const chat: Chat = {
        ...item,
        id: uid("chat"),
        title: String(item.title || "导入会话"),
        createdAt: Number(item.createdAt) || now,
        updatedAt: now,
      };
      chats.value.unshift(chat);
    }
    activeId.value = chats.value[0].id;
    save();
    const toast = await toastController.create({
      message: `已导入 ${incoming.length} 个会话`,
      duration: 1500,
    });
    await toast.present();
  } catch (error) {
    const toast = await toastController.create({
      message: error instanceof Error ? error.message : "导入失败",
      duration: 1800,
    });
    await toast.present();
  }
}
async function shareChat() {
  const chat = activeChat.value;
  if (!chat) return;
  try {
    const result = await api<{ id: string }>("shares", {
      method: "POST",
      body: JSON.stringify({ title: chat.title, messages: chat.messages }),
    });
    const url = `${location.origin}/app/ai-workspace/shared/${result.id}`;
    await navigator.clipboard.writeText(url);
    const toast = await toastController.create({
      message: "分享链接已复制",
      duration: 1600,
    });
    await toast.present();
  } catch (error) {
    const toast = await toastController.create({
      message: error instanceof Error ? error.message : "分享失败",
      duration: 1800,
    });
    await toast.present();
  }
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/ai-api/${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Workspace-User": userId.value,
      "X-Workspace-Role": session.user?.role || "user",
    },
    ...init,
  });
  const data = (await response.json().catch(() => ({}))) as T & {
    detail?: string;
    error?: string;
  };
  if (!response.ok)
    throw new Error(
      data.detail || data.error || `请求失败（${response.status}）`,
    );
  return data;
}
async function loadRemote() {
  try {
    const result = await api<{
      chats: Array<{
        id: string;
        title: string;
        messages: Message[];
        model_id?: string;
        favorite?: number;
        archived?: number;
        folder?: string;
        parent_chat_id?: string;
        created_at: number;
        updated_at: number;
      }>;
    }>(`chats?user_id=${encodeURIComponent(userId.value)}`);
    if (result.chats.length) {
      chats.value = result.chats.map((item) => ({
        id: item.id,
        title: item.title,
        messages: item.messages || [],
        modelId: item.model_id || "",
        favorite: Boolean(item.favorite),
        archived: Boolean(item.archived),
        folder: item.folder || "",
        parentChatId: item.parent_chat_id || "",
        createdAt: item.created_at * 1000,
        updatedAt: item.updated_at * 1000,
      }));
      activeId.value =
        chats.value.find((chat) => !chat.archived)?.id || chats.value[0].id;
      restoreChatModel();
      await scrollBottom(0);
    }
  } catch {}
}
async function loadOptions() {
  try {
    const [m, k, s, t, p] = await Promise.all([
      api<{ models: Option[] }>("models"),
      api<{ knowledge: Option[] }>("knowledge"),
      api<{ skills: Option[] }>("skills"),
      api<{ tools: Option[] }>("tools"),
      api<{ prompts: Option[] }>("prompts"),
    ]);
    models.value = (m.models || []).filter(
      (item) => item.enabled !== 0 && item.hidden !== 1,
    );
    knowledge.value = k.knowledge || [];
    skills.value = s.skills || [];
    tools.value = t.tools || [];
    prompts.value = p.prompts || [];
    selectedAudioModelId.value = audioModels.value[0]?.id || "";
    restoreChatModel();
  } catch {}
}
async function scrollBottom(duration = 200) {
  await nextTick();
  await contentRef.value?.$el?.scrollToBottom?.(duration);
}
async function send(text = prompt.value) {
  const question = text.trim(),
    chat = activeChat.value;
  if (!question || !chat || sending.value) return;
  const attachedImages = [...pendingImages.value];
  pendingImages.value = [];
  prompt.value = "";
  chat.messages.push({
    id: uid("user"),
    role: "user",
    content: question,
    imageUrls: attachedImages,
  });
  if (chat.messages.length === 1) chat.title = question.slice(0, 20);
  sending.value = true;
  save();
  await scrollBottom();
  try {
    if (imageMode.value) {
      const assistant: Message = {
        id: uid("assistant"),
        role: "assistant",
        content: "正在生成图片…",
      };
      chat.messages.push(assistant);
      const result = await api<{ url: string }>("images/generations", {
        method: "POST",
        body: JSON.stringify({
          prompt: question,
          model_id: selectedModelId.value || undefined,
          size: imageSize.value,
        }),
      });
      assistant.content = "";
      assistant.imageUrl = result.url;
      return;
    }
    let sources: Source[] = [];
    if (useKnowledge.value) {
      const result = await api<{ documents: Source[] }>("search", {
        method: "POST",
        body: JSON.stringify({
          query: question,
          limit: 5,
          knowledge_id: selectedKnowledgeId.value || undefined,
        }),
      });
      sources = result.documents || [];
    }
    if (useWebSearch.value) {
      try {
        const result = await api<{ documents: Source[] }>("web-search", {
          method: "POST",
          body: JSON.stringify({ query: question, limit: 5 }),
        });
        sources.push(...(result.documents || []));
      } catch {}
    }
    const assistant: Message = {
      id: uid("assistant"),
      role: "assistant",
      content: "",
      sources,
    };
    chat.messages.push(assistant);
    activeRequest.value = new AbortController();
    const response = await fetch("/ai-api/chat/stream", {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-Workspace-User": userId.value,
        "X-Workspace-Role": session.user?.role || "user",
      },
      signal: activeRequest.value.signal,
      body: JSON.stringify({
        question,
        image_urls: attachedImages,
        documents: sources,
        model_id: selectedModelId.value || undefined,
        skill_ids: selectedSkillIds.value,
        tool_ids: selectedToolIds.value,
      }),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.error || `请求失败（${response.status}）`);
    }
    const reader = response.body?.getReader(),
      decoder = new TextDecoder();
    let buffer = "";
    while (reader) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines)
        if (line.trim()) assistant.content += JSON.parse(line).content || "";
      await scrollBottom();
    }
    if (!assistant.content) assistant.content = "模型没有返回内容";
  } catch (error) {
    if ((error as Error).name !== "AbortError") {
      const last = chat.messages.at(-1);
      if (last?.role === "assistant" && (!last.content || last.content === "正在生成图片…"))
        last.content = `${imageMode.value ? "图片生成失败" : "暂时无法回答"}：${error instanceof Error ? error.message : "请求失败"}`;
    }
  } finally {
    chat.updatedAt = Date.now();
    sending.value = false;
    activeRequest.value = null;
    save();
    await scrollBottom();
  }
}
function stopGeneration() {
  activeRequest.value?.abort();
}
function usePrompt(item: Option) {
  prompt.value = item.content || "";
}
function editMessage(message: Message) {
  const chat = activeChat.value;
  if (!chat) return;
  const index = chat.messages.findIndex((item) => item.id === message.id),
    content = window.prompt("编辑消息", message.content)?.trim();
  if (index < 0 || !content) return;
  chat.messages.splice(index);
  prompt.value = content;
  save();
}
function regenerate(message: Message) {
  const chat = activeChat.value;
  if (!chat) return;
  const index = chat.messages.findIndex((item) => item.id === message.id),
    userIndex = [...chat.messages.slice(0, index)]
      .map((item) => item.role)
      .lastIndexOf("user");
  if (userIndex < 0) return;
  const question = chat.messages[userIndex].content;
  chat.messages.splice(userIndex);
  save();
  void send(question);
}
function branchFrom(message: Message) {
  const source = activeChat.value;
  if (!source) return;
  const index = source.messages.findIndex((item) => item.id === message.id),
    now = Date.now(),
    chat: Chat = {
      id: uid("chat"),
      title: `${source.title} · 分支`,
      messages: structuredClone(source.messages.slice(0, index + 1)),
      modelId: source.modelId,
      parentChatId: source.id,
      createdAt: now,
      updatedAt: now,
    };
  chats.value.unshift(chat);
  activeId.value = chat.id;
  save();
}
function restoreChatModel() {
  const remembered =
    activeChat.value?.modelId ||
    localStorage.getItem(`${storageKey.value}:selected-model`) ||
    "";
  selectedModelId.value = models.value.some((item) => item.id === remembered)
    ? remembered
    : models.value[0]?.id || "";
}
watch(activeId, () => {
  restoreChatModel();
  void scrollBottom(0);
});
watch(selectedModelId, (id) => {
  localStorage.setItem(`${storageKey.value}:selected-model`, id);
  if (activeChat.value && activeChat.value.modelId !== id) {
    activeChat.value.modelId = id;
    save();
  }
  const model = models.value.find((item) => item.id === id);
  if (!model) return;
  imageMode.value = model.model_type === "image";
  selectedKnowledgeId.value = model.knowledge_id || "";
  try {
    selectedSkillIds.value = JSON.parse(model.skill_ids || "[]");
  } catch {
    selectedSkillIds.value = [];
  }
  try {
    selectedToolIds.value = JSON.parse(model.tool_ids || "[]");
  } catch {
    selectedToolIds.value = [];
  }
});
async function copy(content: string) {
  try {
    await navigator.clipboard.writeText(content);
    const toast = await toastController.create({
      message: "已复制",
      duration: 1200,
    });
    await toast.present();
  } catch {}
}
async function saveAsNote(message: Message) {
  const title = window.prompt("笔记标题", activeChat.value?.title || "AI 回答")?.trim();
  if (!title) return;
  try {
    await api("notes", { method: "POST", body: JSON.stringify({ title, content: message.content }) });
    const toast = await toastController.create({ message: "已保存到 Notes", duration: 1500 });
    await toast.present();
  } catch (error) {
    const toast = await toastController.create({ message: error instanceof Error ? error.message : "保存失败", duration: 1800 });
    await toast.present();
  }
}
function openSource(source: Source) {
  if (source.url) { window.open(source.url, "_blank", "noopener"); return; }
  void router.push({ path: "/tabs/module/ai-knowledge", query: { file: source.id, chunk: source.chunk_id || "" } });
}
function downloadBase64(filename: string, mime: string, data: string) {
  const link = document.createElement("a");
  link.href = `data:${mime};base64,${data}`;
  link.download = filename;
  link.click();
}
function downloadGallery() {
  galleryImages.value.forEach((item, index) =>
    window.setTimeout(() => {
      const link = document.createElement("a");
      link.href = item.url;
      link.download = `AI-image-${index + 1}.png`;
      link.click();
    }, index * 180),
  );
}
function regenerateImage(item: { prompt: string }) {
  galleryOpen.value = false;
  imageMode.value = true;
  prompt.value = item.prompt;
}
async function exportAnswer(message: Message, format: "docx" | "xlsx" | "pdf") {
  try {
    const result = await api<{ filename: string; mime: string; data: string }>(
      "files/generate",
      {
        method: "POST",
        body: JSON.stringify({
          title: activeChat.value?.title || "AI 输出",
          content: message.content,
          format,
        }),
      },
    );
    downloadBase64(result.filename, result.mime, result.data);
  } catch (error) {
    const toast = await toastController.create({
      message: error instanceof Error ? error.message : "导出失败",
      duration: 1800,
    });
    await toast.present();
  }
}
async function speak(message: Message) {
  try {
    const result = await api<{ mime: string; data: string }>("audio/speech", {
      method: "POST",
      body: JSON.stringify({
        text: message.content,
        model_id: selectedAudioModelId.value || undefined,
        voice: voice.value,
      }),
    });
    await new Audio(`data:${result.mime};base64,${result.data}`).play();
  } catch (error) {
    const toast = await toastController.create({
      message: error instanceof Error ? error.message : "朗读失败",
      duration: 1800,
    });
    await toast.present();
  }
}
async function toggleRecording() {
  if (recording.value) {
    mediaRecorder?.stop();
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true }),
      chunks: Blob[] = [];
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = (event) => chunks.push(event.data);
    mediaRecorder.onstop = async () => {
      recording.value = false;
      stream.getTracks().forEach((track) => track.stop());
      const blob = new Blob(chunks, {
        type: mediaRecorder?.mimeType || "audio/webm",
      });
      const data = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () =>
          resolve(String(reader.result || "").split(",", 2)[1] || "");
        reader.onerror = () => reject(new Error("录音读取失败"));
        reader.readAsDataURL(blob);
      });
      try {
        const result = await api<{ text: string }>("audio/transcriptions", {
          method: "POST",
          body: JSON.stringify({
            filename: "recording.webm",
            data,
            model_id: selectedAudioModelId.value || undefined,
          }),
        });
        prompt.value = [prompt.value, result.text].filter(Boolean).join(" ");
      } catch (error) {
        const toast = await toastController.create({
          message: error instanceof Error ? error.message : "语音转写失败",
          duration: 1800,
        });
        await toast.present();
      }
    };
    mediaRecorder.start();
    recording.value = true;
  } catch (error) {
    const toast = await toastController.create({
      message: error instanceof Error ? error.message : "无法使用麦克风",
      duration: 1800,
    });
    await toast.present();
  }
}
async function importFiles(event: Event) {
  const input = event.target as HTMLInputElement,
    files = [...(input.files || [])];
  input.value = "";
  if (!files.length) return;
  const imageFiles = files.filter((file) =>
    /^image\/(png|jpeg|webp)$/.test(file.type),
  );
  if (imageFiles.length === files.length) {
    pendingImages.value = await Promise.all(
      imageFiles.slice(0, 4).map(
        (file) =>
          new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result || ""));
            reader.onerror = () => reject(new Error(`${file.name} 读取失败`));
            reader.readAsDataURL(file);
          }),
      ),
    );
    const toast = await toastController.create({
      message: `已添加 ${pendingImages.value.length} 张图片`,
      duration: 1400,
    });
    await toast.present();
    return;
  }
  uploading.value = true;
  try {
    for (const file of files) {
      if (file.size > 15_000_000) throw new Error(`${file.name} 超过 15MB`);
      const data = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () =>
          resolve(String(reader.result || "").split(",", 2)[1] || "");
        reader.onerror = () => reject(new Error(`${file.name} 读取失败`));
        reader.readAsDataURL(file);
      });
      await api("documents/import-file", {
        method: "POST",
        body: JSON.stringify({
          title: file.name.replace(/\.[^.]+$/, ""),
          filename: file.name,
          data,
        }),
      });
    }
    useKnowledge.value = true;
    const toast = await toastController.create({
      message: `已导入 ${files.length} 个文件`,
      duration: 1600,
    });
    await toast.present();
  } catch (error) {
    const toast = await toastController.create({
      message: error instanceof Error ? error.message : "文件导入失败",
      duration: 2200,
    });
    await toast.present();
  } finally {
    uploading.value = false;
  }
}
onMounted(() => {
  load();
  void scrollBottom(0);
  void loadRemote();
  void loadOptions();
});
onIonViewDidEnter(() => {
  window.setTimeout(() => void scrollBottom(0), 0);
});
</script>

<template>
  <IonPage class="ai-page">
    <PageHeader title="AI 工作台" subtitle="多模型对话与知识库" back />
    <div class="ai-subbar">
      <button type="button" aria-label="会话列表" @click="drawerOpen = true">
        <IonIcon :icon="menuOutline" /></button
      ><b
        >{{ activeChat?.title || "新对话"
        }}<small>{{
          models.find((item) => item.id === selectedModelId)?.name || "基础模型"
        }}</small></b
      ><button
        type="button"
        aria-label="知识库"
        @click="router.push('/tabs/module/ai-knowledge')"
      >
        <IonIcon :icon="libraryOutline" /></button
      ><button type="button" aria-label="新建对话" @click="createChat">
        <IonIcon :icon="addOutline" />
      </button>
    </div>
    <IonContent ref="contentRef" :scroll-y="true">
      <main class="messages">
        <section v-if="!activeChat?.messages.length" class="welcome">
          <span><IonIcon :icon="chatbubblesOutline" /></span>
          <h2>今天需要分析什么？</h2>
          <p>可结合内部知识库回答店铺运营与规则问题。</p>
          <button @click="send('分析店铺推广数据时应该重点看哪些指标？')">
            推广数据诊断</button
          ><button @click="send('整理一份今天的店铺运营检查清单')">
            运营检查清单
          </button>
        </section>
        <article
          v-for="message in activeChat?.messages || []"
          :key="message.id"
          :class="message.role"
        >
          <div class="bubble">
            <div v-if="message.imageUrls?.length" class="chat-images">
              <img
                v-for="url in message.imageUrls"
                :key="url.slice(-24)"
                :src="url"
                alt="上传图片"
              />
            </div>
            <div v-if="message.imageUrl" class="generated">
              <img :src="message.imageUrl" alt="生成图片" /><a
                :href="message.imageUrl"
                download
                target="_blank"
                >下载图片</a
              >
            </div>
            <div
              v-else-if="message.role === 'assistant'"
              class="mobile-markdown"
              v-html="renderMarkdown(message.content)"
            ></div>
            <p v-else>{{ message.content }}</p>
            <div v-if="message.sources?.length" class="sources">
              <b>引用来源</b
              ><button
                v-for="(source, index) in message.sources"
                :key="source.id"
                type="button"
                @click="openSource(source)"
                >[{{ index + 1 }}] {{ source.title }}</button
              >
            </div>
            <div class="message-actions">
              <button
                v-if="message.role === 'user'"
                @click="editMessage(message)"
              >
                <IonIcon :icon="createOutline" />编辑</button
              ><template v-else-if="!message.imageUrl"
                ><button @click="copy(message.content)">
                  <IonIcon :icon="copyOutline" />复制</button
                ><button @click="saveAsNote(message)">
                  <IonIcon :icon="documentOutline" />存 Notes</button
                ><button @click="regenerate(message)">
                  <IonIcon :icon="refreshOutline" />重生成</button
                ><button @click="speak(message)">
                  <IonIcon :icon="volumeHighOutline" />朗读</button
                ><button @click="exportAnswer(message, 'docx')">
                  <IonIcon :icon="documentOutline" />Word</button
                ><button @click="exportAnswer(message, 'xlsx')">
                  <IonIcon :icon="documentOutline" />Excel</button
                ><button @click="exportAnswer(message, 'pdf')">
                  <IonIcon :icon="documentOutline" />PDF
                </button></template
              ><button @click="branchFrom(message)">
                <IonIcon :icon="gitBranchOutline" />分支
              </button>
            </div>
          </div>
        </article>
        <article v-if="sending" class="assistant">
          <div class="bubble loading">
            <IonSpinner name="dots" /> 正在生成回答
          </div>
        </article>
      </main>
    </IonContent>
    <IonFooter class="composer"
      ><input
        ref="fileInput"
        class="file-input"
        type="file"
        multiple
        accept=".pdf,.docx,.txt,.md,.markdown,.csv,.json,.png,.jpg,.jpeg,.webp"
        @change="importFiles" />
      <div v-if="pendingImages.length" class="pending">
        <button
          v-for="(url, index) in pendingImages"
          :key="index"
          @click="pendingImages.splice(index, 1)"
        >
          <img :src="url" alt="待发送图片" /><span>×</span>
        </button>
      </div>
      <div v-if="promptMatches.length" class="prompt-picker">
        <button
          v-for="item in promptMatches"
          :key="item.id"
          @click="usePrompt(item)"
        >
          <b>/{{ item.command }}</b
          ><span>{{ item.title }}</span>
        </button>
      </div>
      <div class="mode">
        <button :class="{ active: imageMode }" @click="imageMode = !imageMode">
          <IonIcon :icon="imageOutline" />生图</button
        ><button @click="galleryOpen = true">
          <IonIcon :icon="imageOutline" />图库</button
        ><select v-if="imageMode" v-model="imageSize">
          <option value="1024x1024">方图</option>
          <option value="1536x1024">横图</option>
          <option value="1024x1536">竖图</option></select
        ><button
          v-if="!imageMode"
          :class="{ active: useKnowledge }"
          @click="useKnowledge = !useKnowledge"
        >
          <IonIcon :icon="libraryOutline" />知识</button
        ><button
          v-if="!imageMode"
          :class="{ active: useWebSearch }"
          @click="useWebSearch = !useWebSearch"
        >
          <IonIcon :icon="globeOutline" />联网</button
        ><button :disabled="uploading" @click="fileInput?.click()">
          <IonSpinner v-if="uploading" name="dots" /><IonIcon
            v-else
            :icon="attachOutline"
          />图片/文件</button
        ><button :class="{ active: recording }" @click="toggleRecording">
          <IonIcon :icon="recording ? stopOutline : micOutline" />{{
            recording ? "停止" : "语音"
          }}</button
        ><button
          :class="{
            active:
              selectedSkillIds.length ||
              selectedToolIds.length ||
              selectedModelId,
          }"
          @click="optionsOpen = true"
        >
          <IonIcon :icon="optionsOutline" />能力
        </button>
      </div>
      <div class="input">
        <IonTextarea
          v-model="prompt"
          :auto-grow="true"
          :rows="1"
          :placeholder="
            recording
              ? '正在录音…'
              : imageMode
                ? '描述要生成的图片'
                : '输入消息，输入 / 选择 Prompt'
          "
          @keydown.enter.exact.prevent="send()"
        /><IonButton v-if="sending" color="medium" @click="stopGeneration"
          ><IonIcon :icon="stopOutline" /></IonButton
        ><IonButton v-else :disabled="!prompt.trim()" @click="send()"
          ><IonIcon :icon="arrowUpOutline"
        /></IonButton></div
    ></IonFooter>
    <div v-if="drawerOpen" class="drawer-mask" @click.self="drawerOpen = false">
      <aside>
        <header>
          <b>会话</b><button @click="drawerOpen = false">关闭</button>
        </header>
        <div class="chat-search">
          <IonIcon :icon="searchOutline" /><input
            v-model="chatSearch"
            placeholder="搜索标题和消息"
            @keyup.enter="searchChats"
          />
          <button type="button" :disabled="searchingChats" @click="searchChats">{{ searchingChats ? "…" : "搜索" }}</button>
        </div>
        <div v-if="remoteSearchResults.length" class="remote-results"><button v-for="item in remoteSearchResults" :key="item.id" @click="openSearchResult(item)"><b>{{ item.title }}</b><small>{{ item.snippet || "匹配会话标题" }}</small></button></div>
        <div class="chat-tabs">
          <button
            :class="{ active: !showArchived }"
            @click="showArchived = false"
          >
            最近会话</button
          ><button
            :class="{ active: showArchived }"
            @click="showArchived = true"
          >
            已归档
          </button>
        </div>
        <select v-model="selectedFolder" class="folder-filter">
          <option value="">全部文件夹</option>
          <option v-for="item in folders" :key="item" :value="item">
            {{ item }}
          </option></select
        ><input
          ref="chatImportInput"
          class="file-input"
          type="file"
          accept="application/json,.json"
          @change="importChats"
        />
        <div class="chat-tools">
          <button
            :class="{ active: activeChat?.favorite }"
            @click="toggleFavorite"
          >
            <IonIcon :icon="starOutline" />收藏</button
          ><button @click="renameChat">
            <IonIcon :icon="createOutline" />改名</button
          ><button @click="moveToFolder">
            <IonIcon :icon="archiveOutline" />文件夹</button
          ><button @click="archiveChat">
            <IonIcon :icon="archiveOutline" />{{
              activeChat?.archived ? "恢复" : "归档"
            }}</button
          ><button @click="branchChat">
            <IonIcon :icon="gitBranchOutline" />分支</button
          ><button @click="shareChat">
            <IonIcon :icon="shareSocialOutline" />分享</button
          ><button @click="exportChat">
            <IonIcon :icon="downloadOutline" />导出</button
          ><button @click="chatImportInput?.click()">
            <IonIcon :icon="attachOutline" />导入
          </button>
        </div>
        <div
          v-for="chat in visibleChats"
          :key="chat.id"
          class="chat-row"
          :class="{ active: chat.id === activeId }"
          @click="selectChat(chat.id)"
        >
          <IonIcon
            class="favorite"
            :class="{ hidden: !chat.favorite }"
            :icon="starOutline"
          /><span
            >{{ chat.title }}{{ chat.folder ? ` · ${chat.folder}` : "" }}</span
          ><button aria-label="删除会话" @click.stop="removeChat(chat.id)">
            <IonIcon :icon="trashOutline" />
          </button>
        </div>
        <p v-if="!visibleChats.length" class="chat-empty">
          {{
            chatSearch
              ? "没有匹配会话"
              : showArchived
                ? "暂无归档会话"
                : "暂无会话"
          }}
        </p>
      </aside>
    </div>
    <div
      v-if="optionsOpen"
      class="drawer-mask options-mask"
      @click.self="optionsOpen = false"
    >
      <aside>
        <header>
          <b>对话能力</b><button @click="optionsOpen = false">完成</button>
        </header>
        <div class="manage-links">
          <button
            @click="
              optionsOpen = false;
              router.push('/tabs/module/ai-models');
            "
          >
            模型管理</button
          ><button
            @click="
              optionsOpen = false;
              router.push('/tabs/module/ai-knowledge');
            "
          >
            知识库管理</button
          ><button
            @click="
              optionsOpen = false;
              router.push('/tabs/module/ai-operations');
            "
          >
            运行与治理</button
          ><button
            @click="
              optionsOpen = false;
              router.push('/tabs/module/ai-capabilities');
            "
          >
            能力库管理
          </button>
        </div>
        <label
          >模型<select v-model="selectedModelId">
            <option value="">基础模型</option>
            <option
              v-for="item in models.filter(
                (model) => model.model_type !== 'audio',
              )"
              :key="item.id"
              :value="item.id"
            >
              {{ item.name }}
            </option>
          </select></label
        ><label v-if="audioModels.length"
          >语音模型<select v-model="selectedAudioModelId">
            <option v-for="item in audioModels" :key="item.id" :value="item.id">
              {{ item.name }}
            </option>
          </select></label
        ><label v-if="audioModels.length"
          >朗读音色<select v-model="voice">
            <option value="alloy">Alloy</option>
            <option value="echo">Echo</option>
            <option value="nova">Nova</option>
            <option value="shimmer">Shimmer</option>
          </select></label
        ><label v-if="useKnowledge"
          >知识集合<select v-model="selectedKnowledgeId">
            <option value="">全部知识</option>
            <option v-for="item in knowledge" :key="item.id" :value="item.id">
              {{ item.name }}
            </option>
          </select></label
        >
        <section>
          <b>Skills</b
          ><label v-for="item in skills" :key="item.id"
            ><input
              v-model="selectedSkillIds"
              type="checkbox"
              :value="item.id"
            />{{ item.name }}</label
          >
        </section>
        <section>
          <b>Tools</b
          ><label v-for="item in tools" :key="item.id"
            ><input
              v-model="selectedToolIds"
              type="checkbox"
              :value="item.id"
            />{{ item.name }}</label
          >
        </section>
      </aside>
    </div>
    <div
      v-if="galleryOpen"
      class="drawer-mask gallery-mask"
      @click.self="galleryOpen = false"
    >
      <aside>
        <header>
          <b>生成图片历史</b><span><button v-if="galleryImages.length" @click="downloadGallery">全部下载</button><button @click="galleryOpen = false">关闭</button></span>
        </header>
        <div class="gallery">
          <article
            v-for="item in galleryImages"
            :key="item.url"
            ><img :src="item.url" :alt="item.title" /><span>{{item.title}}</span><footer><a :href="item.url" download target="_blank">下载</a><button :disabled="!item.prompt" @click="regenerateImage(item)">再次生成</button></footer></article
          >
          <p v-if="!galleryImages.length">暂无生成图片</p>
        </div>
      </aside>
    </div>
  </IonPage>
</template>

<style scoped>
.file-input {
  display: none;
}
.mode {
  display: flex;
  gap: 6px;
}
.ai-subbar {
  height: 42px;
  display: grid;
  grid-template-columns: 38px 1fr 38px;
  align-items: center;
  padding: 0 8px;
  border-bottom: 1px solid var(--app-line);
  background: var(--app-card);
}
.ai-subbar button {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border: 0;
  border-radius: 6px;
  color: var(--app-muted);
  background: transparent;
  font-size: 20px;
}
.ai-subbar b {
  overflow: hidden;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}
.messages {
  padding: 16px 12px 24px;
}
.welcome {
  padding: 44px 12px;
  text-align: center;
}
.welcome > span {
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
  margin: auto;
  border-radius: 8px;
  color: #fff;
  background: #1677ff;
  font-size: 26px;
}
.welcome h2 {
  margin: 16px 0 6px;
  font-size: 20px;
}
.welcome p {
  margin: 0 0 20px;
  color: var(--app-muted);
  font-size: 12px;
}
.welcome button {
  width: 100%;
  margin-top: 8px;
  padding: 12px;
  border: 1px solid var(--app-line);
  border-radius: 8px;
  text-align: left;
  color: var(--app-text);
  background: var(--app-card);
}
article {
  display: flex;
  margin: 12px 0;
}
.user {
  justify-content: flex-end;
}
.bubble {
  max-width: 88%;
  padding: 11px 12px;
  border: 1px solid var(--app-line);
  border-radius: 8px;
  background: var(--app-card);
}
.user .bubble {
  color: #fff;
  border-color: #1677ff;
  background: #1677ff;
}
.bubble p {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 14px;
  line-height: 1.7;
}
.bubble > button {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  padding: 3px 0;
  border: 0;
  color: var(--app-muted);
  background: transparent;
  font-size: 10px;
}
.sources {
  display: grid;
  gap: 5px;
  margin-top: 10px;
  padding-top: 9px;
  border-top: 1px solid var(--app-line);
  font-size: 10px;
}
.sources span {
  color: var(--app-muted);
}
.loading {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--app-muted);
}
.composer {
  padding: 7px 10px calc(7px + env(safe-area-inset-bottom));
  border-top: 1px solid var(--app-line);
  background: var(--app-card);
}
.mode button {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 6px;
  padding: 4px 7px;
  border: 0;
  border-radius: 5px;
  color: var(--app-muted);
  background: var(--ion-background-color);
  font-size: 10px;
}
.mode button.active {
  color: #1677ff;
}
.input {
  display: grid;
  grid-template-columns: 1fr 40px;
  gap: 7px;
  align-items: end;
}
.input ion-textarea {
  max-height: 110px;
  overflow: auto;
  border: 1px solid var(--app-line);
  border-radius: 8px;
  --padding-start: 10px;
  --padding-end: 10px;
  --padding-top: 9px;
  --padding-bottom: 9px;
  --background: var(--ion-background-color);
}
.input ion-button {
  width: 40px;
  height: 40px;
  margin: 0;
  --border-radius: 7px;
}
.drawer-mask {
  position: fixed;
  z-index: 1000;
  inset: 0;
  background: rgba(15, 23, 42, 0.38);
}
.drawer-mask aside {
  width: min(82vw, 310px);
  height: 100%;
  padding: calc(12px + env(safe-area-inset-top)) 10px 20px;
  background: var(--app-card);
  box-shadow: 8px 0 30px rgba(15, 23, 42, 0.18);
}
.drawer-mask header {
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 6px;
}
.drawer-mask header button {
  border: 0;
  color: var(--app-muted);
  background: transparent;
}
.chat-row {
  width: 100%;
  display: grid;
  grid-template-columns: 1fr 28px;
  align-items: center;
  padding: 10px;
  border: 0;
  border-radius: 6px;
  text-align: left;
  color: var(--app-text);
  background: transparent;
}
.chat-row.active {
  background: color-mix(in srgb, #1677ff 10%, var(--app-card));
  color: #1677ff;
}
.chat-row span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chat-row ion-icon {
  justify-self: end;
  color: var(--app-muted);
}
.mode {
  overflow-x: auto;
  scrollbar-width: none;
}
.mode::-webkit-scrollbar {
  display: none;
}
.sources a,
.sources button {
  color: var(--app-muted);
  text-decoration: none;
}
.sources button{border:0;text-align:left;background:transparent}
.remote-results{max-height:180px;overflow:auto;margin:0 0 8px;border:1px solid var(--app-line);border-radius:8px}.remote-results button{width:100%;display:grid;gap:3px;padding:9px 10px;border:0;border-bottom:1px solid var(--app-line);text-align:left;color:var(--app-text);background:var(--app-card)}.remote-results button:last-child{border-bottom:0}.remote-results small{overflow:hidden;color:var(--app-muted);font-size:10px;text-overflow:ellipsis;white-space:nowrap}
.mobile-markdown :deep(p) {
  margin: 0 0 8px;
  white-space: normal;
  line-height: 1.7;
}
.mobile-markdown :deep(p:last-child) {
  margin-bottom: 0;
}
.mobile-markdown :deep(ul),
.mobile-markdown :deep(ol) {
  margin: 7px 0;
  padding-left: 20px;
}
.mobile-markdown :deep(pre) {
  overflow: auto;
  margin: 8px 0;
  padding: 10px;
  border-radius: 6px;
  background: #111827;
  color: #e5e7eb;
  font: 11px/1.6 monospace;
}
.mobile-markdown :deep(code) {
  padding: 1px 3px;
  border-radius: 3px;
  background: var(--ion-background-color);
  font: 11px monospace;
}
.mobile-markdown :deep(pre code) {
  padding: 0;
  background: transparent;
}
.mobile-markdown :deep(table) {
  display: block;
  overflow: auto;
  border-collapse: collapse;
  font-size: 11px;
}
.mobile-markdown :deep(th),
.mobile-markdown :deep(td) {
  padding: 6px;
  border: 1px solid var(--app-line);
}
.options-mask {
  display: flex;
  align-items: flex-end;
}
.options-mask aside {
  width: 100%;
  height: auto;
  max-height: 72vh;
  overflow: auto;
  padding: 12px 14px calc(20px + env(safe-area-inset-bottom));
  border-radius: 8px 8px 0 0;
}
.options-mask > aside > label,
.options-mask section {
  display: grid;
  gap: 7px;
  margin-top: 14px;
  color: var(--app-muted);
  font-size: 11px;
}
.options-mask select {
  width: 100%;
  height: 40px;
  padding: 0 10px;
  border: 1px solid var(--app-line);
  border-radius: 7px;
  color: var(--app-text);
  background: var(--ion-background-color);
}
.options-mask section label {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  color: var(--app-text);
  font-size: 13px;
}
.options-mask input {
  width: 17px;
  height: 17px;
}
.ai-subbar {
  min-height: 46px;
  grid-template-columns: 38px 1fr 38px 38px;
}
.ai-subbar b {
  display: grid;
}
.ai-subbar b small {
  margin-top: 2px;
  color: var(--app-muted);
  font-size: 9px;
  font-weight: 400;
}
.manage-links {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin: 6px 0 14px;
}
.manage-links button {
  height: 38px;
  border: 1px solid var(--app-line);
  border-radius: 6px;
  color: #1677ff;
  background: var(--ion-background-color);
}
.pending,
.chat-images {
  display: flex;
  gap: 6px;
  overflow: auto;
}
.pending {
  margin-bottom: 6px;
}
.pending button {
  position: relative;
  width: 48px;
  height: 48px;
  flex: 0 0 48px;
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--app-line);
  border-radius: 6px;
}
.pending img,
.chat-images img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.pending span {
  position: absolute;
  top: 1px;
  right: 2px;
  color: #fff;
}
.chat-images img {
  width: 92px;
  height: 92px;
  border-radius: 6px;
}
.generated {
  display: grid;
  gap: 7px;
}
.generated img {
  max-width: 100%;
  max-height: 52vh;
  border-radius: 7px;
}
.generated a {
  color: #1677ff;
  font-size: 11px;
}
.mode select {
  height: 26px;
  border: 1px solid var(--app-line);
  border-radius: 5px;
  color: var(--app-text);
  background: var(--ion-background-color);
  font-size: 10px;
}
.message-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 8px;
}
.bubble .message-actions button {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 3px 0;
  border: 0;
  color: var(--app-muted);
  background: transparent;
  font-size: 10px;
}
.chat-tools {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 5px;
  margin: 4px 0 10px;
}
.chat-tools button {
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
  border: 1px solid var(--app-line);
  border-radius: 6px;
  color: var(--app-muted);
  background: transparent;
  font-size: 10px;
}
.chat-tools button.active {
  color: #f59e0b;
}
.drawer-mask .chat-row {
  grid-template-columns: 18px 1fr 28px;
  padding: 8px;
  border: 0;
}
.chat-row > .favorite {
  color: #f59e0b;
}
.chat-row > button {
  width: 28px;
  height: 28px;
  border: 0;
  color: var(--app-muted);
  background: transparent;
}
.chat-search {
  height: 38px;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 0 9px;
  border: 1px solid var(--app-line);
  border-radius: 6px;
  color: var(--app-muted);
}
.chat-search input {
  min-width: 0;
  flex: 1;
  border: 0;
  outline: 0;
  color: var(--app-text);
  background: transparent;
}
.chat-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  margin: 8px 0;
}
.chat-tabs button {
  height: 32px;
  border: 0;
  border-radius: 5px;
  color: var(--app-muted);
  background: var(--ion-background-color);
  font-size: 11px;
}
.chat-tabs button.active {
  color: #1677ff;
  background: color-mix(in srgb, #1677ff 9%, var(--app-card));
}
.chat-tools {
  grid-template-columns: repeat(4, 1fr);
}
.chat-row > .favorite.hidden {
  visibility: hidden;
}
.chat-empty {
  padding: 28px 5px;
  text-align: center;
  color: var(--app-muted);
  font-size: 11px;
}
.prompt-picker {
  display: grid;
  max-height: 190px;
  overflow: auto;
  margin-bottom: 6px;
  border: 1px solid var(--app-line);
  border-radius: 7px;
  background: var(--app-card);
  box-shadow: 0 -6px 20px #0f172a12;
}
.prompt-picker button {
  display: grid;
  grid-template-columns: 95px 1fr;
  gap: 8px;
  padding: 9px;
  border: 0;
  border-bottom: 1px solid var(--app-line);
  text-align: left;
  color: var(--app-text);
  background: transparent;
}
.prompt-picker button:last-child {
  border: 0;
}
.prompt-picker b {
  color: #1677ff;
}
.gallery-mask {
  display: flex;
  align-items: flex-end;
}
.gallery-mask aside {
  width: 100%;
  height: auto;
  max-height: 80vh;
  overflow: auto;
  border-radius: 8px 8px 0 0;
}
.gallery {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.gallery a {
  display: grid;
  overflow: hidden;
  border: 1px solid var(--app-line);
  border-radius: 7px;
  color: var(--app-text);
  text-decoration: none;
}
.gallery img {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
}
.gallery span {
  padding: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 10px;
}
.gallery p {
  grid-column: 1/-1;
  padding: 40px;
  text-align: center;
  color: var(--app-muted);
}
.folder-filter{width:100%;height:34px;margin-bottom:8px;padding:0 8px;border:1px solid var(--app-line);border-radius:6px;color:var(--app-text);background:var(--ion-background-color)}.gallery>article{display:grid;margin:0;overflow:hidden;border:1px solid var(--app-line);border-radius:7px}.gallery>article img{width:100%;aspect-ratio:1;object-fit:cover}.gallery>article>span{padding:6px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:10px}.gallery footer{display:grid;grid-template-columns:1fr 1fr}.gallery footer a,.gallery footer button{padding:7px;border:0;border-top:1px solid var(--app-line);text-align:center;color:#1677ff;background:transparent;font-size:10px;text-decoration:none}.gallery footer button:disabled{color:var(--app-muted)}.gallery-mask header>span{display:flex}
</style>
