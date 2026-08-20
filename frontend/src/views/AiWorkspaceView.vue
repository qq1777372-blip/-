<script setup lang="ts">
import {
  ChatDotRound,
  Collection,
  Delete,
  Download,
  EditPen,
  Picture,
  Plus,
  Search,
  Setting,
  Switch,
  Top,
  TrendCharts,
  Upload,
} from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import MarkdownIt from "markdown-it";
import { useAuthStore } from "../stores/auth";
import {
  modelProviderPreset,
  providerLogoBackground,
} from "../utils/aiProviders";

type KnowledgeDocument = {
  id: string;
  title: string;
  category?: string;
  source?: string;
  updated?: string;
  content?: string;
  score?: number;
  url?: string;
  chunk_id?: string;
};
type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  imageUrl?: string;
  imageUrls?: string[];
  fileIds?: string[];
  sources?: KnowledgeDocument[];
  createdAt: number;
};
type Conversation = {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
  archived?: boolean;
  favorite?: boolean;
  parentChatId?: string;
  folder?: string;
  modelId?: string;
};
type AiConfig = {
  base_url: string;
  model: string;
  embedding_model?: string;
  has_key: boolean;
};

const authStore = useAuthStore();
const router = useRouter();
const conversations = ref<Conversation[]>([]);
const activeId = ref("");
const showArchived = ref(false);
const folders = ref<string[]>([]);
const folderFilter = ref("");
const prompt = ref("");
const sending = ref(false);
const activeRequest = ref<AbortController | null>(null);
const sidebarSearch = ref("");
const globalSearchVisible = ref(false);
const globalSearch = ref("");
const globalSearchResults = ref<Record<string, unknown>[]>([]);
const globalSearching = ref(false);
const useKnowledge = ref(
  localStorage.getItem("ruoshop-ai-use-knowledge") === "true",
);
const useWebSearch = ref(false);
const imageMode = ref(false);
const imageSize = ref("1024x1024");
const pendingImages = ref<string[]>([]);
const pendingFileIds = ref<string[]>([]);
const recording = ref(false);
const speakingMessageId = ref("");
let mediaRecorder: MediaRecorder | null = null;
let speechAudio: HTMLAudioElement | null = null;
let speechResolve: (() => void) | null = null;
const config = ref<AiConfig>({ base_url: "", model: "", has_key: false });
const settingsVisible = ref(false);
const settingsSaving = ref(false);
const settingsTesting = ref(false);
const settingsResult = ref("");
const settingsForm = ref({
  base_url: "",
  model: "",
  embedding_model: "",
  api_key: "",
});
const connectionId = ref("");
const connectionName = ref("OpenAI 接口");
const providerConnections = ref<
  Array<{
    id: string;
    name: string;
    base_url: string;
    has_key: boolean;
    enabled: number;
  }>
>([]);
const messagePane = ref<HTMLElement | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const chatImportInput = ref<HTMLInputElement | null>(null);
const uploading = ref(false);
const workspaceModels = ref<Record<string, unknown>[]>([]);
const workspaceKnowledge = ref<Record<string, unknown>[]>([]);
const workspacePrompts = ref<Record<string, unknown>[]>([]);
const workspaceSkills = ref<Record<string, unknown>[]>([]);
const workspaceTools = ref<Record<string, unknown>[]>([]);
const syncingModels = ref(false);
const selectedModelId = ref("");
const selectedKnowledgeId = ref("");
const selectedSkillIds = ref<string[]>([]);
const selectedToolIds = ref<string[]>([]);

function filterWorkspaceModel(query: string, option: any) {
  const model = workspaceModels.value.find((item) => String(item.id) === String(option?.value));
  if (!model) return false;
  return `${model.name || ""} ${model.base_model || ""} ${model.provider_id || ""} ${model.connection_name || ""}`
    .toLowerCase()
    .includes(String(query || "").trim().toLowerCase());
}

function speechChunks(value: string, maxLength = 3600) {
  const parts = value.match(/[^。！？.!?\n]+[。！？.!?\n]?/g) || [value];
  const chunks: string[] = []; let current = "";
  for (const part of parts) {
    if (current && current.length + part.length > maxLength) { chunks.push(current); current = ""; }
    if (part.length > maxLength) {
      for (let index = 0; index < part.length; index += maxLength) chunks.push(part.slice(index, index + maxLength));
    } else current += part;
  }
  if (current) chunks.push(current);
  return chunks.filter(Boolean);
}

function recordingMime() {
  const candidates = ["audio/mp4", "audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"];
  return candidates.find((type) => MediaRecorder.isTypeSupported?.(type)) || "";
}

function recordingExtension(mime: string) {
  if (mime.includes("mp4")) return "m4a";
  if (mime.includes("ogg")) return "ogg";
  return "webm";
}

const storageKey = computed(
  () => `ruoshop-ai-workspace:${authStore.currentUser?.id || "local"}`,
);
const workspaceUserId = computed(() =>
  String(authStore.currentUser?.id || "local"),
);
const activeConversation = computed(
  () => conversations.value.find((item) => item.id === activeId.value) || null,
);
const filteredConversations = computed(() => {
  const keyword = sidebarSearch.value.trim().toLowerCase();
  const visible = conversations.value.filter(
    (item) =>
      Boolean(item.archived) === showArchived.value &&
      (!folderFilter.value || item.folder === folderFilter.value),
  );
  return keyword
    ? visible.filter((item) => item.title.toLowerCase().includes(keyword))
    : visible;
});
const markdown = new MarkdownIt({ html: false, breaks: true, linkify: true });
const promptMatches = computed(() => {
  if (!prompt.value.startsWith("/")) return [];
  const keyword = prompt.value.slice(1).trim().toLowerCase();
  return workspacePrompts.value
    .filter(
      (item) =>
        !keyword ||
        String(item.command || "")
          .toLowerCase()
          .includes(keyword) ||
        String(item.title || "")
          .toLowerCase()
          .includes(keyword),
    )
    .slice(0, 6);
});
watch(useKnowledge, (value) =>
  localStorage.setItem("ruoshop-ai-use-knowledge", String(value)),
);

function renderMessage(content: string) {
  return markdown.render(content || "");
}
function insertPromptTemplate(item: Record<string, unknown>) {
  prompt.value = String(item.content || "");
  void nextTick(() =>
    document
      .querySelector<HTMLTextAreaElement>(".composer-box textarea")
      ?.focus(),
  );
}

function uid(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}
function focusConversationSearch() {
  globalSearch.value = "";
  globalSearchResults.value = [];
  globalSearchVisible.value = true;
  void nextTick(() => document.querySelector<HTMLInputElement>(".global-chat-search input")?.focus());
}

async function searchAllConversations() {
  if (!globalSearch.value.trim()) return;
  globalSearching.value = true;
  try {
    globalSearchResults.value = (await knowledgeApi<{ results: Record<string, unknown>[] }>("chats/search", { method: "POST", body: JSON.stringify({ query: globalSearch.value.trim() }) })).results || [];
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "搜索失败"); }
  finally { globalSearching.value = false; }
}

function openSearchConversation(item: Record<string, unknown>) {
  const id = String(item.id || "");
  if (conversations.value.some(chat => chat.id === id)) activeId.value = id;
  globalSearchVisible.value = false;
}

function saveConversations() {
  localStorage.setItem(
    storageKey.value,
    JSON.stringify(conversations.value.slice(0, 100)),
  );
  void syncConversations();
}

async function syncConversations() {
  await Promise.all(
    conversations.value.slice(0, 100).map((chat) =>
      knowledgeApi("chats/save", {
        method: "POST",
        body: JSON.stringify({
          id: chat.id,
          user_id: workspaceUserId.value,
          title: chat.title,
          messages: chat.messages,
          folder: chat.folder || "",
          archived: Boolean(chat.archived),
          favorite: Boolean(chat.favorite),
          parent_chat_id: chat.parentChatId || "",
          model_id: chat.modelId || "",
          created_at: Math.floor(chat.createdAt / 1000),
        }),
      }).catch(() => null),
    ),
  );
}

async function loadServerConversations() {
  try {
    const result = await knowledgeApi<{
      chats: Array<{
        id: string;
        title: string;
        messages: Message[];
        folder?: string;
        archived?: number;
        favorite?: number;
        parent_chat_id?: string;
        model_id?: string;
        created_at: number;
        updated_at: number;
      }>;
    }>(`chats?user_id=${encodeURIComponent(workspaceUserId.value)}`);
    if (result.chats?.length) {
      conversations.value = result.chats.map((chat) => ({
        id: chat.id,
        title: chat.title,
        messages: chat.messages || [],
        folder: chat.folder || "",
        archived: chat.archived === 1,
        favorite: chat.favorite === 1,
        parentChatId: chat.parent_chat_id || "",
        modelId: chat.model_id || "",
        createdAt: chat.created_at * 1000,
        updatedAt: chat.updated_at * 1000,
      }));
      activeId.value = conversations.value[0].id;
      localStorage.setItem(
        storageKey.value,
        JSON.stringify(conversations.value),
      );
    } else {
      await syncConversations();
    }
  } catch {}
}

function loadConversations() {
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey.value) || "[]");
    conversations.value = Array.isArray(saved) ? saved : [];
  } catch {
    conversations.value = [];
  }
  if (conversations.value.length) activeId.value = conversations.value[0].id;
  else createConversation();
}

function createConversation() {
  const now = Date.now();
  const conversation: Conversation = {
    id: uid("chat"),
    title: "新对话",
    messages: [],
    createdAt: now,
    updatedAt: now,
  };
  conversation.modelId = selectedModelId.value;
  conversations.value.unshift(conversation);
  activeId.value = conversation.id;
  prompt.value = "";
  saveConversations();
}
function exportConversations() {
  const blob = new Blob(
    [
      JSON.stringify(
        {
          version: 1,
          exported_at: new Date().toISOString(),
          chats: conversations.value,
        },
        null,
        2,
      ),
    ],
    { type: "application/json" },
  );
  const url = URL.createObjectURL(blob),
    link = document.createElement("a");
  link.href = url;
  link.download = `ai-workspace-chats-${new Date().toISOString().slice(0, 10)}.json`;
  link.click();
  URL.revokeObjectURL(url);
}
function exportConversation(conversation: Conversation) {
  const blob = new Blob(
    [JSON.stringify({ version: 1, chats: [conversation] }, null, 2)],
    { type: "application/json" },
  );
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `chat-${conversation.id}.json`;
  link.click();
  URL.revokeObjectURL(url);
}
async function shareConversation() {
  if (!activeConversation.value) return;
  const result = await knowledgeApi<{ id: string }>("shares", {
    method: "POST",
    body: JSON.stringify({
      title: activeConversation.value.title,
      messages: activeConversation.value.messages,
    }),
  });
  const url = `${location.origin}${location.pathname.replace(/\/ai-workspace.*$/, "")}/ai-workspace/shared/${result.id}`;
  await navigator.clipboard.writeText(url).catch(() => null);
  ElMessage.success("只读分享链接已复制");
}
async function importConversations(event: Event) {
  const input = event.target as HTMLInputElement,
    file = input.files?.[0];
  input.value = "";
  if (!file) return;
  try {
    const payload = JSON.parse(await file.text()),
      incoming = Array.isArray(payload) ? payload : payload.chats;
    if (!Array.isArray(incoming)) throw new Error("文件中没有会话数据");
    const valid = incoming
      .filter((item) => item?.id && item?.title && Array.isArray(item.messages))
      .map((item) => ({
        ...item,
        createdAt: Number(item.createdAt || Date.now()),
        updatedAt: Number(item.updatedAt || Date.now()),
      })) as Conversation[];
    const byId = new Map(conversations.value.map((item) => [item.id, item]));
    valid.forEach((item) => byId.set(item.id, item));
    conversations.value = [...byId.values()]
      .sort((a, b) => b.updatedAt - a.updatedAt)
      .slice(0, 100);
    activeId.value = conversations.value[0]?.id || "";
    saveConversations();
    ElMessage.success(`已导入 ${valid.length} 个会话`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "会话导入失败");
  }
}

async function renameConversation(conversation: Conversation) {
  const result = await ElMessageBox.prompt("输入新的会话名称", "重命名会话", {
    inputValue: conversation.title,
    inputValidator: (value) => (value.trim() ? true : "名称不能为空"),
    confirmButtonText: "保存",
    cancelButtonText: "取消",
  }).catch(() => null);
  if (!result) return;
  conversation.title = result.value.trim().slice(0, 60);
  saveConversations();
}

async function deleteConversation(conversation: Conversation) {
  await ElMessageBox.confirm(
    `确定删除“${conversation.title}”吗？`,
    "删除会话",
    { type: "warning" },
  ).catch(() => null);
  const index = conversations.value.findIndex(
    (item) => item.id === conversation.id,
  );
  if (index < 0) return;
  conversations.value.splice(index, 1);
  void knowledgeApi("chats/delete", {
    method: "POST",
    body: JSON.stringify({
      id: conversation.id,
      user_id: workspaceUserId.value,
    }),
  }).catch(() => null);
  if (activeId.value === conversation.id)
    activeId.value = conversations.value[0]?.id || "";
  if (!conversations.value.length) createConversation();
  saveConversations();
}
function archiveConversation(conversation: Conversation) {
  conversation.archived = !conversation.archived;
  saveConversations();
  ElMessage.success(conversation.archived ? "会话已归档" : "会话已恢复");
}
async function createFolder() {
  const result = await ElMessageBox.prompt("输入文件夹名称", "新建文件夹", {
    confirmButtonText: "创建",
    cancelButtonText: "取消",
  }).catch(() => null);
  if (!result?.value?.trim()) return;
  const name = result.value.trim();
  if (!folders.value.includes(name)) folders.value.push(name);
  folderFilter.value = name;
  localStorage.setItem(
    `${storageKey.value}:folders`,
    JSON.stringify(folders.value),
  );
}
function assignActiveFolder() {
  if (!activeConversation.value || !folders.value.length) return;
  activeConversation.value.folder = folderFilter.value || folders.value[0];
  saveConversations();
  ElMessage.success("会话已归类");
}

function toggleFavorite() {
  if (!activeConversation.value) return;
  activeConversation.value.favorite = !activeConversation.value.favorite;
  saveConversations();
  ElMessage.success(
    activeConversation.value.favorite ? "会话已收藏" : "已取消收藏",
  );
}
function branchConversation() {
  const source = activeConversation.value;
  if (!source) return;
  const now = Date.now();
  const branch: Conversation = {
    id: uid("chat"),
    title: `${source.title} - 分支`,
    messages: JSON.parse(JSON.stringify(source.messages)),
    parentChatId: source.id,
    modelId: source.modelId,
    createdAt: now,
    updatedAt: now,
  };
  conversations.value.unshift(branch);
  activeId.value = branch.id;
  saveConversations();
  ElMessage.success("已创建会话分支");
}

async function knowledgeApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/ai-api/${path.replace(/^\//, "")}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Workspace-User": workspaceUserId.value,
      "X-Workspace-Role": String(authStore.currentUser?.role || "user"),
      ...(init?.headers || {}),
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

async function loadConfig() {
  try {
    config.value = await knowledgeApi<AiConfig>("config");
  } catch (error) {
    ElMessage.warning(
      error instanceof Error ? error.message : "AI 配置读取失败",
    );
  }
}

async function loadModels() {
  try {
    workspaceModels.value = (
      (await knowledgeApi<{ models: Record<string, unknown>[] }>("models"))
        .models || []
    )
      .filter((item) => item.enabled !== 0 && item.hidden !== 1)
      .sort(
        (a, b) =>
          Number(b.pinned || 0) - Number(a.pinned || 0) ||
          Number(a.sort_order || 0) - Number(b.sort_order || 0),
      )
      .map((item) => {
        const connectionIndex = providerConnections.value.findIndex(
          (connection) => connection.id === String(item.connection_id || ""),
        );
        const connection = providerConnections.value[connectionIndex];
        return connection
          ? {
              ...item,
              name: `${String(item.name)} · ${connection.name}（连接 ${connectionIndex + 1}）`,
            }
          : item;
      });
    const rememberedId =
      activeConversation.value?.modelId ||
      localStorage.getItem(`${storageKey.value}:selected-model`) ||
      "";
    if (!selectedModelId.value && rememberedId)
      selectedModelId.value = rememberedId;
    const selected = workspaceModels.value.find(
      (item) => String(item.id) === selectedModelId.value,
    );
    if (!selected) {
      selectedModelId.value = "";
    }
    if (!selectedModelId.value) {
      const preferred =
        workspaceModels.value.find((item) => item.is_default === 1) ||
        workspaceModels.value[0];
      if (preferred) selectedModelId.value = String(preferred.id);
    }
  } catch {}
}
async function loadKnowledgeCollections() {
  try {
    workspaceKnowledge.value =
      (
        await knowledgeApi<{ knowledge: Record<string, unknown>[] }>(
          "knowledge",
        )
      ).knowledge || [];
  } catch {}
}
async function loadSkills() {
  try {
    workspaceSkills.value =
      (await knowledgeApi<{ skills: Record<string, unknown>[] }>("skills"))
        .skills || [];
  } catch {}
}
async function loadTools() {
  try {
    workspaceTools.value =
      (await knowledgeApi<{ tools: Record<string, unknown>[] }>("tools"))
        .tools || [];
  } catch {}
}
async function loadPrompts() {
  try {
    workspacePrompts.value =
      (await knowledgeApi<{ prompts: Record<string, unknown>[] }>("prompts"))
        .prompts || [];
  } catch {}
}
async function loadConnections() {
  try {
    const result = await knowledgeApi<{
      connections: Array<{
        id: string;
        name: string;
        base_url: string;
        has_key: boolean;
        enabled?: number;
      }>;
    }>("connections");
    providerConnections.value = (result.connections || []).map((item) => ({
      ...item,
      enabled: item.enabled ?? 1,
    }));
  } catch {}
}
async function openSettings() {
  await loadConfig();
  await loadConnections();
  const first = providerConnections.value[0];
  if (first) {
    connectionId.value = first.id;
    connectionName.value = first.name;
    config.value.base_url = first.base_url;
    config.value.has_key = first.has_key;
  }
  settingsForm.value = {
    base_url: config.value.base_url,
    model: config.value.model,
    embedding_model: config.value.embedding_model || "",
    api_key: "",
  };
  settingsResult.value = "";
  settingsVisible.value = true;
}

function selectConnection(item: {
  id: string;
  name: string;
  base_url: string;
  has_key: boolean;
}) {
  connectionId.value = item.id;
  connectionName.value = item.name;
  settingsForm.value.base_url = item.base_url;
  settingsForm.value.api_key = "";
  config.value.has_key = item.has_key;
}
function newConnection() {
  connectionId.value = "";
  connectionName.value = "";
  settingsForm.value = {
    base_url: "",
    model: "",
    embedding_model: "",
    api_key: "",
  };
  config.value.has_key = false;
}
async function toggleConnection(item: { id: string; enabled: number }) {
  const enabled = !item.enabled;
  await knowledgeApi("connections/toggle", {
    method: "POST",
    body: JSON.stringify({ id: item.id, enabled }),
  });
  item.enabled = enabled ? 1 : 0;
  await loadModels();
  ElMessage.success(enabled ? "连接已启用" : "连接已停用");
}

function applyPreset(provider: "openai" | "deepseek" | "qwen") {
  const presets = {
    openai: { base_url: "https://api.openai.com/v1", model: "gpt-4.1-mini" },
    deepseek: {
      base_url: "https://api.deepseek.com/v1",
      model: "deepseek-chat",
    },
    qwen: {
      base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
      model: "qwen-plus",
    },
  };
  Object.assign(settingsForm.value, presets[provider]);
}

async function saveSettings(closeAfter = true) {
  settingsSaving.value = true;
  settingsResult.value = "";
  try {
    await knowledgeApi("connections/save", {
      method: "POST",
      body: JSON.stringify({
        id: connectionId.value,
        name: connectionName.value,
        base_url: settingsForm.value.base_url,
        api_key: settingsForm.value.api_key,
        enabled: true,
      }),
    });
    config.value = await knowledgeApi<AiConfig>("config");
    await loadModels();
    await openSettings();
    settingsForm.value.api_key = "";
    settingsResult.value = "设置已保存";
    ElMessage.success("AI 设置已保存");
    if (closeAfter) settingsVisible.value = false;
    return true;
  } catch (error) {
    settingsResult.value = error instanceof Error ? error.message : "保存失败";
    return false;
  } finally {
    settingsSaving.value = false;
  }
}

async function syncCurrentConnection() {
  if (!connectionId.value) return;
  syncingModels.value = true;
  try {
    const result = await knowledgeApi<{
      total: number;
      added: number;
      removed: number;
    }>("connections/sync", {
      method: "POST",
      body: JSON.stringify({ id: connectionId.value }),
    });
    await loadModels();
    ElMessage.success(`同步完成：${result.total} 个模型`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "同步失败");
  } finally {
    syncingModels.value = false;
  }
}
async function deleteCurrentConnection() {
  if (!connectionId.value) return;
  await ElMessageBox.confirm(
    `删除连接“${connectionName.value}”及其同步模型？`,
    "删除连接",
    { type: "warning" },
  );
  await knowledgeApi("connections/delete", {
    method: "POST",
    body: JSON.stringify({ id: connectionId.value }),
  });
  await loadModels();
  connectionId.value = "";
  await openSettings();
  ElMessage.success("连接已删除");
}

async function testSettings() {
  settingsTesting.value = true;
  settingsResult.value = "正在连接模型...";
  try {
    if (!(await saveSettings(false))) return;
    if (!connectionId.value) throw new Error("请先保存连接");
    const result = await knowledgeApi<{ message: string }>("connections/test", {
      method: "POST",
      body: JSON.stringify({ id: connectionId.value }),
    });
    settingsResult.value = result.message;
  } catch (error) {
    settingsResult.value = error instanceof Error ? error.message : "连接失败";
  } finally {
    settingsTesting.value = false;
  }
}

async function scrollBottom(smooth = true) {
  await nextTick();
  messagePane.value?.scrollTo({
    top: messagePane.value.scrollHeight,
    behavior: smooth ? "smooth" : "auto",
  });
}

async function sendPrompt(text = prompt.value) {
  const question = text.trim();
  const conversation = activeConversation.value;
  if (!question || !conversation || sending.value) return;
  prompt.value = "";
  const attachedImages = [...pendingImages.value];
  pendingImages.value = [];
  const attachedFileIds = [...pendingFileIds.value];
  pendingFileIds.value = [];
  const now = Date.now();
  conversation.messages.push({
    id: uid("user"),
    role: "user",
    content: question,
    imageUrls: attachedImages,
    fileIds: attachedFileIds,
    createdAt: now,
  });
  if (conversation.messages.length === 1)
    conversation.title = question.slice(0, 24);
  conversation.updatedAt = now;
  sending.value = true;
  saveConversations();
  await scrollBottom();
  try {
    if (imageMode.value) {
      const assistant: Message = {
        id: uid("assistant"),
        role: "assistant",
        content: "正在生成图片...",
        createdAt: Date.now(),
      };
      conversation.messages.push(assistant);
      const activeModel = workspaceModels.value.find(
        (item) => String(item.id) === selectedModelId.value,
      );
      const result = await knowledgeApi<{ url: string }>("images/generations", {
        method: "POST",
        body: JSON.stringify({
          prompt: question,
          model_id: activeModel ? selectedModelId.value : undefined,
          size: imageSize.value,
          image_urls: attachedImages.slice(0, 1),
        }),
      });
      assistant.content = "";
      assistant.imageUrl = result.url;
      return;
    }
    let sources: KnowledgeDocument[] = [];
    if (useKnowledge.value) {
      const search = await knowledgeApi<{ documents: KnowledgeDocument[] }>(
        "search",
        {
          method: "POST",
          body: JSON.stringify({
            query: question,
            limit: 5,
            knowledge_id: selectedKnowledgeId.value || undefined,
          }),
        },
      );
      sources = Array.isArray(search.documents) ? search.documents : [];
    }
    if (useWebSearch.value) {
      try {
        const web = await knowledgeApi<{ documents: KnowledgeDocument[] }>(
          "web-search",
          {
            method: "POST",
            body: JSON.stringify({ query: question, limit: 6 }),
          },
        );
        sources.push(...(web.documents || []));
      } catch (error) {
        ElMessage.warning(
          error instanceof Error
            ? `联网搜索失败：${error.message}`
            : "联网搜索失败",
        );
      }
    }
    const pageUrl = question.match(/https?:\/\/[^\s<>]+/i)?.[0]?.replace(/[),.;!?]+$/, "");
    if (pageUrl) {
      try {
        const page = await knowledgeApi<{ page: KnowledgeDocument }>("web-pages/read", {
          method: "POST",
          body: JSON.stringify({ url: pageUrl }),
        });
        if (page.page?.content) sources.push(page.page);
      } catch (error) {
        ElMessage.warning(error instanceof Error ? `网页读取失败：${error.message}` : "网页读取失败");
      }
    }
    const assistant: Message = {
      id: uid("assistant"),
      role: "assistant",
      content: "",
      sources,
      createdAt: Date.now(),
    };
    conversation.messages.push(assistant);
    activeRequest.value = new AbortController();
    const activeModel = workspaceModels.value.find(
      (item) => String(item.id) === selectedModelId.value,
    );
    const safeModelId = activeModel ? selectedModelId.value : undefined;
    const response = await fetch("/ai-api/chat/stream", {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-Workspace-User": workspaceUserId.value,
        "X-Workspace-Role": String(authStore.currentUser?.role || "user"),
      },
      signal: activeRequest.value.signal,
      body: JSON.stringify({
        chat_id: conversation.id,
        messages: conversation.messages.slice(0, -1).map(({ role, content, imageUrls, fileIds }) => ({
          role,
          content,
          imageUrls,
          fileIds,
        })),
        question,
        image_urls: attachedImages,
        file_ids: attachedFileIds,
        documents: sources,
        model_id: safeModelId,
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
      for (const line of lines) {
        if (!line.trim()) continue;
        assistant.content += JSON.parse(line).content || "";
      }
      await scrollBottom();
    }
    if (!assistant.content) {
      const model = workspaceModels.value.find(
        (item) => item.id === selectedModelId.value,
      );
      assistant.content = `模型返回了空内容。当前模型：${String(model?.base_model || config.value.model || "未选择")}。请检查该模型是否支持 Chat Completions 流式接口。`;
    }
  } catch (error) {
    if ((error as Error).name !== "AbortError") {
      const last = conversation.messages.at(-1);
      if (
        last?.role === "assistant" &&
        (!last.content || last.content === "正在生成图片...")
      )
        last.content = `${imageMode.value ? "图片生成失败" : "暂时无法回答"}：${error instanceof Error ? error.message : "请求失败"}`;
    }
  } finally {
    conversation.updatedAt = Date.now();
    sending.value = false;
    activeRequest.value = null;
    saveConversations();
    await scrollBottom();
  }
}

function stopGeneration() {
  activeRequest.value?.abort();
}

function copyMessage(content: string) {
  navigator.clipboard
    .writeText(content)
    .then(() => ElMessage.success("已复制"))
    .catch(() => ElMessage.error("复制失败"));
}

async function saveMessageAsNote(message: Message) {
  const defaultTitle = `${activeConversation.value?.title || "AI 会话"} · ${message.role === "assistant" ? "AI 回答" : "用户消息"}`;
  const result = await ElMessageBox.prompt("设置笔记标题", "保存到 Notes", { inputValue: defaultTitle, confirmButtonText: "保存", cancelButtonText: "取消" }).catch(() => null);
  if (!result?.value?.trim()) return;
  try {
    await knowledgeApi("notes", { method: "POST", body: JSON.stringify({ title: result.value.trim(), content: message.content }) });
    ElMessage.success("已保存到 Notes");
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "保存失败"); }
}

function openKnowledgeSource(source: KnowledgeDocument) {
  if (source.url) { window.open(source.url, "_blank", "noopener,noreferrer"); return; }
  void router.push({ path: "/ai-workspace/knowledge", query: { file: source.id, chunk: source.chunk_id || "" } });
}

async function exportAnswer(format: "docx" | "xlsx" | "pdf", target?: Message) {
  const message =
    target ||
    [...(activeConversation.value?.messages || [])]
      .reverse()
      .find((item) => item.role === "assistant" && item.content);
  if (!message) return ElMessage.warning("当前会话还没有可导出的回答");
  try {
    const result = await knowledgeApi<{
      filename: string;
      mime: string;
      data: string;
    }>("files/generate", {
      method: "POST",
      body: JSON.stringify({
        title: activeConversation.value?.title || "AI 输出",
        content: message.content,
        format,
      }),
    });
    const raw = atob(result.data);
    const bytes = new Uint8Array(raw.length);
    for (let index = 0; index < raw.length; index++)
      bytes[index] = raw.charCodeAt(index);
    const url = URL.createObjectURL(new Blob([bytes], { type: result.mime }));
    const link = document.createElement("a");
    link.href = url;
    link.download = result.filename;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "文件生成失败");
  }
}

function stopSpeech() {
  speakingMessageId.value = "";
  speechAudio?.pause(); speechAudio = null;
  speechResolve?.(); speechResolve = null;
}

async function speakLastAnswer(target?: Message) {
  const message =
    target ||
    [...(activeConversation.value?.messages || [])]
      .reverse()
      .find((item) => item.role === "assistant" && item.content);
  if (!message) return ElMessage.warning("当前会话还没有可朗读的回答");
  if (speakingMessageId.value === message.id) { stopSpeech(); return; }
  stopSpeech(); speakingMessageId.value = message.id;
  try {
    for (const chunk of speechChunks(message.content)) {
      if (speakingMessageId.value !== message.id) return;
      const result = await knowledgeApi<{ mime: string; data: string }>(
        "audio/speech",
        { method: "POST", body: JSON.stringify({ text: chunk }) },
      );
      if (speakingMessageId.value !== message.id) return;
      const audio = new Audio(`data:${result.mime};base64,${result.data}`); speechAudio = audio;
      await new Promise<void>((resolve, reject) => {
        speechResolve = resolve;
        audio.onended = () => { speechResolve = null; resolve(); };
        audio.onerror = () => { speechResolve = null; reject(new Error("音频播放失败")); };
        void audio.play().catch(reject);
      });
    }
  } catch (error) {
    if (speakingMessageId.value === message.id) ElMessage.error(error instanceof Error ? error.message : "语音生成失败");
  } finally {
    if (speakingMessageId.value === message.id) stopSpeech();
  }
}

async function toggleRecording() {
  if (recording.value && mediaRecorder) {
    mediaRecorder.stop();
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const chunks: BlobPart[] = [];
    const mime = recordingMime();
    mediaRecorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
    mediaRecorder.ondataavailable = (event) => chunks.push(event.data);
    mediaRecorder.onstop = async () => {
      recording.value = false;
      stream.getTracks().forEach((track) => track.stop());
      const actualMime = mediaRecorder?.mimeType || mime || "audio/webm";
      const blob = new Blob(chunks, { type: actualMime });
      const data = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () =>
          resolve(String(reader.result || "").split(",", 2)[1] || "");
        reader.onerror = () => reject(new Error("录音读取失败"));
        reader.readAsDataURL(blob);
      });
      try {
        const result = await knowledgeApi<{ text: string }>(
          "audio/transcriptions",
          {
            method: "POST",
            body: JSON.stringify({ filename: `recording.${recordingExtension(actualMime)}`, data }),
          },
        );
        prompt.value = [prompt.value, result.text].filter(Boolean).join(" ");
      } catch (error) {
        ElMessage.error(
          error instanceof Error ? error.message : "语音转写失败",
        );
      }
    };
    mediaRecorder.start();
    recording.value = true;
  } catch {
    ElMessage.error("无法访问麦克风，请检查浏览器权限");
  }
}

function editMessage(index: number) {
  const conversation = activeConversation.value,
    message = conversation?.messages[index];
  if (!conversation || !message || message.role !== "user" || sending.value)
    return;
  prompt.value = message.content;
  conversation.messages.splice(index);
  conversation.updatedAt = Date.now();
  saveConversations();
}

async function regenerateMessage(index: number) {
  const conversation = activeConversation.value;
  if (!conversation || sending.value) return;
  const userIndex = [...conversation.messages.slice(0, index)]
    .map((item) => item.role)
    .lastIndexOf("user");
  if (userIndex < 0) return;
  const question = conversation.messages[userIndex].content;
  conversation.messages.splice(userIndex);
  saveConversations();
  await sendPrompt(question);
}

async function addImageFiles(files: File[]) {
  const available = Math.max(0, 4 - pendingImages.value.length);
  if (!available) {
    ElMessage.warning("最多添加 4 张图片");
    return;
  }
  const selected = files.slice(0, available);
  const urls = await Promise.all(
    selected.map(
      (file) =>
        new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(String(reader.result || ""));
          reader.onerror = () => reject(new Error(`${file.name} 读取失败`));
          reader.readAsDataURL(file);
        }),
    ),
  );
  pendingImages.value.push(...urls);
  if (files.length > available) ElMessage.warning("最多添加 4 张图片");
  else ElMessage.success(`已添加 ${urls.length} 张图片`);
}

async function pasteImages(event: ClipboardEvent) {
  const files = [...(event.clipboardData?.files || [])].filter((file) =>
    /^image\/(png|jpeg|webp)$/.test(file.type),
  );
  if (!files.length) return;
  event.preventDefault();
  try {
    await addImageFiles(files);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "图片粘贴失败");
  }
}

async function importFiles(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = [...(input.files || [])];
  input.value = "";
  if (!files.length) return;
  const imageFiles = files.filter((file) =>
    /^image\/(png|jpeg|webp)$/.test(file.type),
  );
  if (imageFiles.length === files.length) {
    await addImageFiles(imageFiles);
    return;
  }
  const selected = workspaceModels.value.find(
    (item) => String(item.id) === selectedModelId.value,
  );
  if (
    selected &&
    !String(selected.capabilities || "").includes("file_upload") &&
    files.some((file) => /\.(png|jpg|jpeg|webp)$/i.test(file.name))
  ) {
    ElMessage.warning(
      "当前模型未声明图片/文件能力，请先在模型编辑器中启用相关能力",
    );
    return;
  }
  uploading.value = true;
  let imported = 0;
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
      const importedFile = await knowledgeApi<{ file?: { id?: string } }>("documents/import-file", {
        method: "POST",
        body: JSON.stringify({
          title: file.name.replace(/\.[^.]+$/, ""),
          filename: file.name,
          data,
        }),
      });
      if (importedFile.file?.id) pendingFileIds.value.push(String(importedFile.file.id));
      imported += 1;
    }
    ElMessage.success(`已导入 ${imported} 个文件`);
    useKnowledge.value = true;
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "文件导入失败");
  } finally {
    uploading.value = false;
  }
}

watch(activeId, () => {
  pendingImages.value = [];
  pendingFileIds.value = [];
  const rememberedId = activeConversation.value?.modelId;
  if (
    rememberedId &&
    workspaceModels.value.some((item) => String(item.id) === rememberedId)
  )
    selectedModelId.value = rememberedId;
  void scrollBottom(false);
});
watch(selectedModelId, (id) => {
  localStorage.setItem(`${storageKey.value}:selected-model`, id);
  if (activeConversation.value && activeConversation.value.modelId !== id) {
    activeConversation.value.modelId = id;
    saveConversations();
  }
  const model = workspaceModels.value.find((item) => item.id === id);
  if (!model) return;
  imageMode.value = String(model.model_type || "") === "image";
  selectedKnowledgeId.value = String(model.knowledge_id || "");
  try {
    selectedSkillIds.value = JSON.parse(String(model.skill_ids || "[]"));
  } catch {
    selectedSkillIds.value = [];
  }
  try {
    selectedToolIds.value = JSON.parse(String(model.tool_ids || "[]"));
  } catch {
    selectedToolIds.value = [];
  }
});
onMounted(async () => {
  try {
    folders.value = JSON.parse(
      localStorage.getItem(`${storageKey.value}:folders`) || "[]",
    );
  } catch {}
  loadConversations();
  void loadServerConversations();
  await loadConfig();
  await loadConnections();
  await loadModels();
  void loadKnowledgeCollections();
  void loadPrompts();
  void loadSkills();
  void loadTools();
});
</script>

<template>
  <section class="ai-shell compact">
    <aside class="chat-sidebar">
      <button class="new-chat" type="button" @click="createConversation">
        <el-icon><Plus /></el-icon><span>新建对话</span>
      </button>
      <nav class="workspace-links">
        <button type="button" @click="focusConversationSearch">
          <el-icon><Search /></el-icon><span>搜索</span></button
        ><button type="button" @click="$router.push('/ai-workspace/knowledge')">
          <el-icon><Collection /></el-icon><span>知识库</span></button
        ><button type="button" @click="$router.push('/ai-workspace/models')">
          <el-icon><Setting /></el-icon><span>工作空间</span>
        </button><button type="button" @click="$router.push('/ai-workspace/operations')">
          <el-icon><TrendCharts /></el-icon><span>运行治理</span>
        </button>
      </nav>
      <label class="chat-search"
        ><el-icon><Search /></el-icon
        ><input v-model="sidebarSearch" placeholder="搜索会话"
      /></label>
      <div class="folder-bar">
        <el-select
          v-model="folderFilter"
          clearable
          size="small"
          placeholder="全部文件夹"
          ><el-option
            v-for="folder in folders"
            :key="folder"
            :label="folder"
            :value="folder" /></el-select
        ><el-button size="small" @click="createFolder">新建文件夹</el-button
        ><el-button v-if="folderFilter" size="small" @click="assignActiveFolder"
          >归类当前</el-button
        >
      </div>
      <div class="conversation-label">
        <button type="button" @click="showArchived = !showArchived">
          {{ showArchived ? "已归档" : "会话" }}</button
        ><small>{{ filteredConversations.length }}</small>
      </div>
      <div class="chat-list">
        <button
          v-for="chat in filteredConversations"
          :key="chat.id"
          type="button"
          :class="{ active: activeId === chat.id }"
          @click="activeId = chat.id"
        >
          <el-icon><ChatDotRound /></el-icon
          ><span
            ><b>{{ chat.title }}</b
            ><small>{{ chat.messages.length }} 条消息</small></span
          >
          <i class="chat-actions"
            ><span
              :title="chat.archived ? '恢复' : '归档'"
              @click.stop="archiveConversation(chat)"
              >{{ chat.archived ? "复" : "归" }}</span
            ><el-icon title="导出会话" @click.stop="exportConversation(chat)"
              ><Download /></el-icon
            ><el-icon title="重命名" @click.stop="renameConversation(chat)"
              ><EditPen /></el-icon
            ><el-icon title="删除" @click.stop="deleteConversation(chat)"
              ><Delete /></el-icon
          ></i>
        </button>
      </div>
      <input
        ref="chatImportInput"
        class="file-input"
        type="file"
        accept="application/json,.json"
        @change="importConversations"
      />
      <div class="chat-transfer">
        <el-tooltip content="导入会话"
          ><el-button
            :icon="Upload"
            circle
            @click="chatImportInput?.click()" /></el-tooltip
        ><el-tooltip content="导出全部会话"
          ><el-button :icon="Download" circle @click="exportConversations"
        /></el-tooltip>
      </div>
    </aside>

    <main class="chat-main">
      <header class="chat-toolbar">
        <div>
          <strong>{{ activeConversation?.title || "AI 工作台" }}</strong
          ><span>{{ config.model || "尚未配置模型" }}</span>
        </div>
        <div class="toolbar-controls">
          <input
            ref="fileInput"
            class="file-input"
            type="file"
            multiple
            accept=".pdf,.docx,.txt,.md,.markdown,.csv,.json,.png,.jpg,.jpeg,.webp"
            @change="importFiles"
          />
          <el-tooltip content="收藏会话" placement="bottom"
            ><el-button circle @click="toggleFavorite">{{
              activeConversation?.favorite ? "★" : "☆"
            }}</el-button></el-tooltip
          >
          <el-tooltip content="创建分支" placement="bottom"
            ><el-button circle @click="branchConversation"
              >⑂</el-button
            ></el-tooltip
          >
          <el-tooltip content="分享会话" placement="bottom"
            ><el-button
              :icon="Upload"
              circle
              aria-label="分享会话"
              @click="shareConversation"
          /></el-tooltip>
        </div>
      </header>

      <section ref="messagePane" class="message-pane">
        <div v-if="!activeConversation?.messages.length" class="chat-welcome">
          <span
            ><el-icon><ChatDotRound /></el-icon
          ></span>
          <h2>今天需要分析什么？</h2>
          <p>可结合内部知识库回答店铺运营、规则和推广问题。</p>
          <div class="prompt-grid">
            <button
              type="button"
              @click="sendPrompt('分析店铺推广数据时应该重点看哪些指标？')"
            >
              推广数据诊断
            </button>
            <button
              type="button"
              @click="sendPrompt('商品发布失败应该按照什么顺序排查？')"
            >
              发布失败排查
            </button>
            <button
              type="button"
              @click="sendPrompt('整理一份今天的店铺运营检查清单')"
            >
              运营检查清单
            </button>
          </div>
        </div>
        <article
          v-for="(message, messageIndex) in activeConversation?.messages || []"
          :key="message.id"
          class="message"
          :class="message.role"
        >
          <div class="message-avatar">
            {{ message.role === "user" ? "我" : "AI" }}
          </div>
          <div class="message-body">
            <div v-if="message.imageUrls?.length" class="message-images">
              <a
                v-for="(url, imageIndex) in message.imageUrls"
                :key="`${message.id}-${imageIndex}`"
                :href="url"
                target="_blank"
                rel="noopener"
                title="点击查看原图"
              >
                <img :src="url" alt="用户上传的图片" loading="lazy" />
              </a>
            </div>
            <div v-if="message.imageUrl" class="generated-image">
              <a
                class="generated-image-preview"
                :href="message.imageUrl"
                target="_blank"
                rel="noopener"
                title="点击查看原图"
                ><img
                  :src="message.imageUrl"
                  alt="生成的图片"
                  loading="lazy" /></a
              ><a
                :href="message.imageUrl"
                download
                target="_blank"
                rel="noopener"
                >下载原图</a
              >
            </div>
            <div
              v-else-if="message.role === 'assistant'"
              class="message-content markdown-body"
              v-html="renderMessage(message.content)"
            ></div>
            <div v-else class="message-content">{{ message.content }}</div>
            <div v-if="message.sources?.length" class="message-sources">
              <b>引用来源</b
              ><button
                v-for="(source, index) in message.sources"
                :key="source.chunk_id || source.id"
                type="button"
                @click="openKnowledgeSource(source)"
                ><span>[{{ index + 1 }}] {{ source.title }}</span><small v-if="source.url">{{ source.url }}</small></button
              >
            </div>
            <div class="message-actions">
              <button
                v-if="message.role === 'user'"
                type="button"
                @click="editMessage(messageIndex)"
              >
                编辑</button
              ><button
                v-if="message.role === 'assistant'"
                type="button"
                @click="copyMessage(message.content)"
              >
                复制</button
              ><button
                v-if="message.role === 'assistant'"
                type="button"
                @click="regenerateMessage(messageIndex)"
              >
                重新生成</button
              ><button
                v-if="message.role === 'assistant' && message.content"
                type="button"
                @click="speakLastAnswer(message)"
              >
                {{ speakingMessageId === message.id ? "停止" : "朗读" }}</button
              ><button v-if="message.content" type="button" @click="saveMessageAsNote(message)">保存笔记</button
              ><el-dropdown
                v-if="message.role === 'assistant' && message.content"
                @command="
                  (format: 'docx' | 'xlsx' | 'pdf') =>
                    exportAnswer(format, message)
                "
                ><button type="button">导出</button
                ><template #dropdown
                  ><el-dropdown-menu
                    ><el-dropdown-item command="docx"
                      >Word 文档</el-dropdown-item
                    ><el-dropdown-item command="xlsx"
                      >Excel 工作簿</el-dropdown-item
                    ><el-dropdown-item command="pdf"
                      >PDF 文档</el-dropdown-item
                    ></el-dropdown-menu
                  ></template
                ></el-dropdown
              >
            </div>
          </div>
        </article>
        <article v-if="sending" class="message assistant">
          <div class="message-avatar">AI</div>
          <div class="message-body typing"><i></i><i></i><i></i></div>
        </article>
      </section>
    </main>

    <footer class="chat-composer">
      <div v-if="pendingImages.length" class="pending-reference">
        <div class="pending-images">
          <button
            v-for="(url, index) in pendingImages"
            :key="index"
            type="button"
            title="移除图片"
            @click="pendingImages.splice(index, 1)"
          >
            <img :src="url" alt="待发送图片" /><span>×</span>
          </button>
        </div>
        <small v-if="imageMode">已添加参考图，将使用图生图</small>
      </div>
      <div class="composer-box">
        <div v-if="promptMatches.length" class="prompt-suggestions">
          <button
            v-for="item in promptMatches"
            :key="String(item.id)"
            type="button"
            @click="insertPromptTemplate(item)"
          >
            <b>/{{ item.command }}</b
            ><span>{{ item.title }}</span>
          </button>
        </div>
        <textarea
          v-model="prompt"
          rows="1"
          placeholder="输入消息，Enter 发送，Shift + Enter 换行"
          @keydown.enter.exact.prevent="sendPrompt()"
          @paste="pasteImages"
        ></textarea>
        <div class="composer-actions">
          <div class="composer-tools">
            <el-tooltip content="添加文件"
              ><el-button
                :icon="Plus"
                :loading="uploading"
                circle
                @click="fileInput?.click()" /></el-tooltip
            ><el-tooltip :content="recording ? '停止录音' : '语音输入'"
              ><el-button
                :type="recording ? 'danger' : 'default'"
                round
                @click="toggleRecording"
                >{{ recording ? "停止" : "语音" }}</el-button
              ></el-tooltip
            ><el-button
              :class="{ active: imageMode }"
              round
              @click="imageMode = !imageMode"
              ><el-icon><Picture /></el-icon>生图</el-button
            ><el-select
              v-if="imageMode"
              v-model="imageSize"
              size="small"
              class="image-size-select"
              ><el-option label="方图" value="1024x1024" /><el-option
                label="横图"
                value="1536x1024" /><el-option
                label="竖图"
                value="1024x1536" /></el-select
            ><el-button
              :class="{ active: useKnowledge }"
              round
              @click="useKnowledge = !useKnowledge"
              ><el-icon><Switch /></el-icon>知识</el-button
            ><el-button
              :class="{ active: useWebSearch }"
              round
              @click="useWebSearch = !useWebSearch"
              ><el-icon><Search /></el-icon>联网</el-button
            ><el-select
              v-if="useKnowledge"
              v-model="selectedKnowledgeId"
              clearable
              placeholder="全部知识"
              style="width: 120px"
              ><el-option
                v-for="item in workspaceKnowledge"
                :key="String(item.id)"
                :label="String(item.name)"
                :value="String(item.id)" /></el-select
            ><el-popover trigger="click" width="240"
              ><el-checkbox-group
                v-model="selectedSkillIds"
                class="capability-list"
                ><el-checkbox
                  v-for="skill in workspaceSkills"
                  :key="String(skill.id)"
                  :value="String(skill.id)"
                  >{{ skill.name }}</el-checkbox
                ></el-checkbox-group
              ><template #reference
                ><el-button :class="{ active: selectedSkillIds.length }" round
                  >Skills{{
                    selectedSkillIds.length ? ` ${selectedSkillIds.length}` : ""
                  }}</el-button
                ></template
              ></el-popover
            ><el-popover trigger="click" width="240"
              ><el-checkbox-group
                v-model="selectedToolIds"
                class="capability-list"
                ><el-checkbox
                  v-for="tool in workspaceTools"
                  :key="String(tool.id)"
                  :value="String(tool.id)"
                  >{{ tool.name }}</el-checkbox
                ></el-checkbox-group
              ><template #reference
                ><el-button :class="{ active: selectedToolIds.length }" round
                  >工具{{
                    selectedToolIds.length ? ` ${selectedToolIds.length}` : ""
                  }}</el-button
                ></template
              ></el-popover
            ><el-select
              v-model="selectedModelId"
              class="composer-model-select"
              clearable
              filterable
              :filter-method="filterWorkspaceModel"
              placement="top-end"
              popper-class="workspace-model-popper"
              placeholder="基础模型"
              ><el-option
                v-for="model in workspaceModels"
                :key="String(model.id)"
                :label="String(model.name)"
                :value="String(model.id)"
                ><span class="model-option"
                  ><i
                    :style="{
                      background: providerLogoBackground(
                        modelProviderPreset(
                          String(model.base_model),
                          String(model.provider_id || 'custom'),
                        ),
                      ),
                    }"
                    ><img
                      v-if="
                        modelProviderPreset(
                          String(model.base_model),
                          String(model.provider_id || 'custom'),
                        ).logo
                      "
                      :src="`/ui/ai-providers/${modelProviderPreset(String(model.base_model), String(model.provider_id || 'custom')).logo}`"
                      alt=""
                    /><span v-else>{{
                      modelProviderPreset(
                        String(model.base_model),
                        String(model.provider_id || "custom"),
                      ).short
                    }}</span></i
                  >{{ model.name }}</span
                ></el-option
              ></el-select
            ><el-button round @click="prompt = '/'">/ Prompt</el-button>
          </div>
          <button
            v-if="sending"
            class="send-button stop-button"
            type="button"
            aria-label="停止生成"
            @click="stopGeneration"
          >
            ■</button
          ><button
            v-else
            class="send-button"
            type="button"
            :disabled="!prompt.trim()"
            aria-label="发送"
            @click="sendPrompt()"
          >
            <el-icon><Top /></el-icon>
          </button>
        </div>
      </div>
      <small
        >{{
          useKnowledge
            ? selectedKnowledgeId
              ? "已限定知识集合"
              : "检索全部知识"
            : "普通对话"
        }}
        ·
        {{
          selectedModelId ? "使用自定义模型" : config.model || "基础模型"
        }}</small
      >
    </footer>
    <el-dialog v-model="globalSearchVisible" title="搜索全部会话" width="min(720px, 94vw)" append-to-body>
      <el-input v-model="globalSearch" class="global-chat-search" clearable :prefix-icon="Search" placeholder="搜索会话标题和消息内容" @keyup.enter="searchAllConversations"><template #append><el-button :loading="globalSearching" @click="searchAllConversations">搜索</el-button></template></el-input>
      <div class="global-search-results"><button v-for="item in globalSearchResults" :key="String(item.id)" type="button" @click="openSearchConversation(item)"><b>{{ item.title }}</b><p>{{ item.snippet || '标题匹配' }}</p><small>{{ new Date(Number(item.updated_at || 0) * 1000).toLocaleString() }}</small></button><el-empty v-if="globalSearch.trim() && !globalSearching && !globalSearchResults.length" description="没有匹配的会话"/></div>
    </el-dialog>
    <el-dialog
      v-model="settingsVisible"
      title="AI 模型中心"
      fullscreen
      append-to-body
      class="model-center-dialog"
    >
      <div class="model-center-layout">
        <aside class="connection-rail">
          <div class="rail-heading">
            <div>
              <b>连接</b
              ><small>{{ providerConnections.length }} 个提供商</small>
            </div>
            <el-button type="primary" link @click="newConnection"
              >+ 新增</el-button
            >
          </div>
          <button
            v-for="item in providerConnections"
            :key="item.id"
            type="button"
            class="connection-item"
            :class="{
              active: item.id === connectionId,
              disabled: !item.enabled,
            }"
            @click="selectConnection(item)"
          >
            <span
              class="connection-dot"
              :class="{ online: item.has_key && item.enabled }"
            ></span
            ><span
              ><b>{{ item.name }}</b
              ><small>{{
                item.enabled ? item.base_url : "已停用"
              }}</small></span
            ><el-switch
              :model-value="Boolean(item.enabled)"
              size="small"
              @click.stop
              @change="toggleConnection(item)"
            />
          </button>
          <div v-if="!providerConnections.length" class="rail-empty">
            还没有连接<br />从右侧开始配置
          </div>
        </aside>
        <section class="connection-editor">
          <div class="editor-heading">
            <div>
              <span class="eyebrow">PROVIDER CONNECTION</span>
              <h2>{{ connectionName || "新建连接" }}</h2>
              <p>配置 OpenAI 兼容接口，保存后自动发现模型。</p>
            </div>
            <div class="editor-actions">
              <el-button
                v-if="connectionId"
                type="danger"
                plain
                @click="deleteCurrentConnection"
                >删除</el-button
              ><el-button
                v-if="connectionId"
                :loading="syncingModels"
                @click="syncCurrentConnection"
                >同步模型</el-button
              ><el-button @click="testSettings">测试连接</el-button
              ><el-button
                type="primary"
                :loading="settingsSaving"
                @click="saveSettings(true)"
                >保存连接</el-button
              >
            </div>
          </div>
          <div class="editor-grid">
            <div class="editor-panel">
              <div class="panel-title">连接信息</div>
              <div class="provider-presets">
                <button type="button" @click="applyPreset('openai')">
                  OpenAI</button
                ><button type="button" @click="applyPreset('deepseek')">
                  DeepSeek</button
                ><button type="button" @click="applyPreset('qwen')">
                  通义千问
                </button>
              </div>
              <el-form class="settings-provider-form" label-position="top">
                <el-form-item label="连接名称"
                  ><el-input
                    v-model="connectionName"
                    placeholder="例如：OpenAI、DeepSeek、内部中转"
                /></el-form-item>
                <el-form-item label="接口地址"
                  ><el-input
                    v-model="settingsForm.base_url"
                    placeholder="https://api.openai.com/v1"
                /></el-form-item>
                <el-form-item label="模型名称"
                  ><el-input
                    v-model="settingsForm.model"
                    placeholder="gpt-4.1-mini" /></el-form-item
                ><el-form-item label="Embedding 模型"
                  ><el-input
                    v-model="settingsForm.embedding_model"
                    placeholder="可选，例如 text-embedding-3-small"
                /></el-form-item>
                <el-form-item label="API Key"
                  ><el-input
                    v-model="settingsForm.api_key"
                    type="password"
                    show-password
                    :placeholder="
                      config.has_key
                        ? '已保存密钥，留空表示不修改'
                        : '请输入 API Key'
                    "
                /></el-form-item>
              </el-form>
            </div>
            <div class="editor-panel model-panel">
              <div class="panel-title">
                <span>已发现模型</span
                ><el-button
                  link
                  :loading="syncingModels"
                  @click="syncCurrentConnection"
                  >重新同步</el-button
                >
              </div>
              <div class="connection-model-list">
                <div
                  v-for="model in workspaceModels.filter(
                    (item) => item.connection_id === connectionId,
                  )"
                  :key="String(model.id)"
                  class="connection-model-row"
                >
                  <span
                    class="model-mark"
                    :style="{
                      background: providerLogoBackground(
                        modelProviderPreset(
                          String(model.base_model),
                          String(model.provider_id || 'custom'),
                        ),
                      ),
                    }"
                    ><img
                      v-if="
                        modelProviderPreset(
                          String(model.base_model),
                          String(model.provider_id || 'custom'),
                        ).logo
                      "
                      :src="`/ui/ai-providers/${modelProviderPreset(String(model.base_model), String(model.provider_id || 'custom')).logo}`"
                      alt=""
                    /><span v-else>{{
                      modelProviderPreset(
                        String(model.base_model),
                        String(model.provider_id || "custom"),
                      ).short
                    }}</span></span
                  >
                  <div>
                    <b>{{ model.name }}</b
                    ><small>{{ model.base_model }}</small>
                  </div>
                </div>
                <div
                  v-if="
                    !workspaceModels.some(
                      (item) => item.connection_id === connectionId,
                    )
                  "
                  class="workspace-empty"
                >
                  保存连接后自动发现模型
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
      <p v-if="settingsResult" class="settings-result">{{ settingsResult }}</p>
      <template #footer
        ><el-button :loading="settingsTesting" @click="testSettings"
          >测试连接</el-button
        ><el-button
          type="primary"
          :loading="settingsSaving"
          @click="saveSettings(true)"
          >保存</el-button
        ></template
      >
    </el-dialog>
  </section>
</template>

<style scoped>
.settings-provider-form .el-form-item:nth-child(2) {
  display: none;
}
.ai-shell {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  overflow: hidden;
  height: calc(100vh - 104px);
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  background: #fff;
}
.chat-sidebar {
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 12px;
  border-right: 1px solid var(--panel-border);
  background: #f8fafc;
}
.global-search-results{max-height:56vh;overflow:auto;margin-top:14px}.global-search-results>button{width:100%;display:grid;grid-template-columns:minmax(0,1fr) 150px;gap:5px 12px;padding:12px;border:0;border-bottom:1px solid var(--panel-border);text-align:left;background:transparent}.global-search-results>button:hover{background:#f8fafc}.global-search-results b{font-size:13px}.global-search-results p{grid-column:1/-1;overflow:hidden;margin:0;color:var(--text-secondary);text-overflow:ellipsis;white-space:nowrap}.global-search-results small{grid-column:2;grid-row:1;text-align:right;color:var(--text-muted)}
.new-chat {
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 0;
  border-radius: 6px;
  color: #fff;
  background: var(--brand-primary);
  font-weight: 600;
}
.chat-search {
  height: 36px;
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 10px 0;
  padding: 0 10px;
  border: 1px solid var(--panel-border);
  border-radius: 6px;
  background: #fff;
  color: var(--text-secondary);
}
.chat-search input {
  min-width: 0;
  flex: 1;
  border: 0;
  outline: 0;
  background: transparent;
  font-size: 13px;
}
.chat-list {
  min-height: 0;
  overflow: auto;
}
.chat-list > button {
  width: 100%;
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  padding: 9px 8px;
  border: 0;
  border-radius: 6px;
  text-align: left;
  color: var(--text-main);
  background: transparent;
}
.chat-list > button:hover,
.chat-list > button.active {
  background: #e9eef7;
}
.chat-list span,
.chat-list b,
.chat-list small {
  display: block;
  min-width: 0;
}
.chat-list b {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}
.chat-list small {
  margin-top: 3px;
  color: var(--text-secondary);
  font-size: 10px;
}
.chat-actions {
  display: none;
  gap: 6px;
  color: var(--text-secondary);
  font-style: normal;
}
.chat-list > button:hover .chat-actions,
.chat-list > button.active .chat-actions {
  display: flex;
}
.chat-actions .el-icon:hover {
  color: var(--brand-primary);
}
.chat-main {
  display: grid;
  grid-template-rows: 56px minmax(0, 1fr) auto;
  min-width: 0;
  min-height: 0;
}
.chat-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 16px;
  border-bottom: 1px solid var(--panel-border);
}
.chat-toolbar strong,
.chat-toolbar span {
  display: block;
}
.chat-toolbar strong {
  font-size: 15px;
}
.chat-toolbar > div:first-child span {
  margin-top: 3px;
  color: var(--text-secondary);
  font-size: 11px;
}
.toolbar-controls,
.knowledge-switch {
  display: flex;
  align-items: center;
  gap: 8px;
}
.knowledge-switch {
  font-size: 12px;
  color: var(--text-secondary);
}
.file-input {
  display: none;
}
.message-pane {
  min-height: 0;
  overflow: auto;
  padding: 24px clamp(20px, 6vw, 88px);
}
.chat-welcome {
  max-width: 660px;
  margin: 9vh auto 0;
  text-align: center;
}
.chat-welcome > span {
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
  margin: auto;
  border-radius: 8px;
  color: #fff;
  background: var(--brand-primary);
  font-size: 25px;
}
.chat-welcome h2 {
  margin: 18px 0 7px;
  font-size: 23px;
}
.chat-welcome p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
}
.prompt-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 26px;
}
.prompt-grid button {
  min-height: 64px;
  padding: 12px;
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  color: var(--text-main);
  background: #fff;
  font-size: 13px;
}
.prompt-grid button:hover {
  border-color: var(--brand-primary);
  color: var(--brand-primary);
  background: #f6f8ff;
}
.message {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: 11px;
  max-width: 900px;
  margin: 0 auto 22px;
}
.message.user {
  margin-top: 6px;
}
.message-avatar {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: 6px;
  color: #fff;
  background: #64748b;
  font-size: 11px;
  font-weight: 700;
}
.assistant .message-avatar {
  background: var(--brand-primary);
}
.message-body {
  min-width: 0;
}
.message-images {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 180px));
  gap: 8px;
  width: fit-content;
  max-width: 100%;
  margin-bottom: 8px;
}
.message-images a {
  display: block;
  overflow: hidden;
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  background: #f8fafc;
}
.message-images img {
  display: block;
  width: 100%;
  height: 150px;
  object-fit: cover;
}
.message-content {
  padding-top: 5px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 14px;
  line-height: 1.75;
}
.message.user .message-content {
  display: inline-block;
  padding: 9px 12px;
  border-radius: 8px;
  background: #f1f5f9;
}
@media (max-width: 640px) {
  .message-images {
    grid-template-columns: repeat(2, minmax(0, 120px));
  }
  .message-images img {
    height: 120px;
  }
}
.message-sources {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--panel-border);
}
.message-sources b {
  width: 100%;
  font-size: 11px;
}
.message-sources span {
  font-size: 11px;
}
.message-sources small {
  overflow-wrap: anywhere;
  color: var(--text-secondary);
  font-size: 10px;
}
.copy-message {
  margin-top: 8px;
  padding: 3px 0;
  border: 0;
  color: var(--text-secondary);
  background: transparent;
  font-size: 11px;
}
.typing {
  display: flex;
  gap: 4px;
  padding-top: 11px;
}
.typing i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #94a3b8;
  animation: pulse 1.1s infinite;
}
.typing i:nth-child(2) {
  animation-delay: 0.15s;
}
.typing i:nth-child(3) {
  animation-delay: 0.3s;
}
@keyframes pulse {
  0%,
  70%,
  100% {
    opacity: 0.3;
  }
  35% {
    opacity: 1;
  }
}
.chat-composer {
  padding: 10px clamp(20px, 6vw, 88px) 14px;
  background: #fff;
}
.composer-box {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 38px;
  gap: 8px;
  align-items: end;
  max-width: 900px;
  margin: auto;
  padding: 8px;
  border: 1px solid #cfd5df;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
}
.composer-box:focus-within {
  border-color: var(--brand-primary);
}
.composer-box textarea {
  max-height: 130px;
  resize: none;
  border: 0;
  outline: 0;
  padding: 7px;
  background: transparent;
  font: 14px/1.5 inherit;
}
.composer-box button {
  width: 36px;
  height: 36px;
  border: 0;
  border-radius: 6px;
  color: #fff;
  background: var(--brand-primary);
  font-size: 18px;
}
.composer-box button:disabled {
  background: #cbd5e1;
}
.chat-composer > small {
  display: block;
  max-width: 900px;
  margin: 7px auto 0;
  text-align: center;
  color: var(--text-secondary);
  font-size: 10px;
}
.provider-presets {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}
.provider-presets button {
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--panel-border);
  border-radius: 6px;
  color: var(--text-main);
  background: #fff;
}
.provider-presets button:hover {
  border-color: var(--brand-primary);
  color: var(--brand-primary);
}
.settings-result {
  margin: 0;
  padding: 9px 10px;
  border-radius: 6px;
  background: #f1f5f9;
  color: var(--text-secondary);
  font-size: 12px;
}
@media (max-width: 900px) {
  .ai-shell {
    grid-template-columns: 210px minmax(0, 1fr);
  }
  .message-pane,
  .chat-composer {
    padding-left: 20px;
    padding-right: 20px;
  }
  .prompt-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 700px) {
  .ai-shell {
    grid-template-columns: 1fr;
    height: calc(100vh - 80px);
    border: 0;
  }
  .chat-sidebar {
    display: none;
  }
}
.composer-box {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
  max-width: 820px;
  padding: 10px 12px;
  border-color: #d8dee8;
  box-shadow: 0 5px 18px rgba(15, 23, 42, 0.07);
}
.composer-box textarea {
  width: 100%;
  min-height: 44px;
  box-sizing: border-box;
  padding: 5px 3px;
  font-family: inherit;
}
.composer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 34px;
}
.composer-tools {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  overflow: hidden;
}
.composer-tools .el-button {
  width: auto;
  height: 32px;
  margin-left: 0;
  padding: 0 11px;
  border-color: #d9dee7;
  color: #475569;
  background: #fff;
  font-size: 12px;
}
.composer-tools .el-button:first-child {
  width: 32px;
  padding: 0;
}
.composer-tools .el-button:hover {
  border-color: #aab4c4;
  color: var(--brand-primary);
  background: #f8fafc;
}
.composer-tools .el-button.active {
  border-color: #a9b4ff;
  color: var(--brand-primary);
  background: #f1f3ff;
}
.composer-box .send-button {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  color: #fff;
  background: var(--brand-primary);
  font-size: 17px;
}
.composer-box .send-button:disabled {
  background: #cbd5e1;
}
.composer-tools :deep(.el-select__wrapper) {
  min-height: 32px;
  border-radius: 16px;
  box-shadow: 0 0 0 1px #d9dee7 inset;
}
.composer-model-select {
  width: 180px;
  flex: 0 1 180px;
}
.composer-tools :deep(.el-select__placeholder) {
  font-size: 12px;
}
.chat-composer > small {
  margin-top: 6px;
  color: #94a3b8;
}
.message-actions {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}
.message-actions button {
  padding: 2px 0;
  border: 0;
  color: #94a3b8;
  background: transparent;
  font-size: 11px;
}
.message-actions button:hover {
  color: var(--brand-primary);
}
.workspace-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
  padding: 9px 10px;
  border-bottom: 1px solid #edf0f4;
  color: #64748b;
  font-size: 12px;
}
.workspace-create {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  margin-bottom: 16px;
}
.model-create,
.prompt-create {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 18px;
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}
.model-create .el-textarea,
.prompt-create .el-textarea,
.model-create .el-button,
.prompt-create .el-button {
  grid-column: 1/-1;
}
.workspace-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 48px;
  padding: 9px 10px;
  border-bottom: 1px solid #edf0f4;
}
.workspace-row > b,
.workspace-row > div {
  min-width: 0;
}
.workspace-row b,
.workspace-row span {
  display: block;
}
.workspace-row b {
  font-size: 13px;
}
.workspace-row span {
  margin-top: 3px;
  overflow: hidden;
  color: #64748b;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.workspace-empty {
  padding: 28px 12px;
  text-align: center;
  color: #94a3b8;
  font-size: 12px;
}
.file-row > div {
  flex: 1;
}
.markdown-body :deep(p) {
  margin: 0 0 10px;
}
.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 8px 0;
  padding-left: 22px;
}
.markdown-body :deep(pre) {
  overflow: auto;
  margin: 10px 0;
  padding: 12px;
  border: 1px solid #263244;
  border-radius: 6px;
  background: #111827;
  color: #e5e7eb;
  font:
    12px/1.65 Consolas,
    monospace;
}
.markdown-body :deep(code) {
  padding: 2px 4px;
  border-radius: 4px;
  background: #f1f5f9;
  font:
    12px Consolas,
    monospace;
}
.markdown-body :deep(pre code) {
  padding: 0;
  background: transparent;
  color: inherit;
}
.markdown-body :deep(blockquote) {
  margin: 10px 0;
  padding: 7px 12px;
  border-left: 3px solid #94a3b8;
  background: #f8fafc;
  color: #64748b;
}
.markdown-body :deep(table) {
  width: 100%;
  margin: 10px 0;
  border-collapse: collapse;
  font-size: 12px;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 7px 9px;
  border: 1px solid #dfe5ec;
  text-align: left;
}
.markdown-body :deep(th) {
  background: #f8fafc;
}
.markdown-body :deep(a) {
  color: var(--brand-primary);
}
.prompt-suggestions {
  position: absolute;
  right: 0;
  bottom: calc(100% + 8px);
  left: 0;
  z-index: 5;
  overflow: auto;
  max-height: 250px;
  padding: 6px;
  border: 1px solid #dfe5ec;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.15);
}
.prompt-suggestions button {
  width: 100%;
  height: auto;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 9px 10px;
  border: 0;
  border-radius: 5px;
  text-align: left;
  color: #334155;
  background: #fff;
  font-size: 12px;
}
.prompt-suggestions button:hover {
  background: #f1f5f9;
}
.prompt-suggestions b {
  min-width: 120px;
  color: var(--brand-primary);
}
.prompt-suggestions span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.composer-box {
  position: relative;
}
.message-sources a,
.message-sources button {
  display: grid;
  gap: 2px;
  text-align: left;
  padding: 5px 8px;
  border-radius: 5px;
  background: #f1f5f9;
  color: #64748b;
  text-decoration: none;
  font-size: 11px;
  border: 0;
}
.message-sources a:hover,
.message-sources button:hover {
  color: var(--brand-primary);
  background: #eef2ff;
}
:global(.capability-list) {
  display: grid;
  gap: 8px;
}
:global(.capability-list .el-checkbox) {
  margin-right: 0;
}
.model-field {
  display: grid;
  gap: 5px;
  color: #64748b;
  font-size: 11px;
}
.model-field .el-input-number {
  width: 100%;
}
.model-form-actions {
  grid-column: 1/-1;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.row-actions {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
}
.chat-transfer {
  display: flex;
  gap: 7px;
  padding-top: 9px;
  border-top: 1px solid #e2e8f0;
}
.chat-transfer .el-button {
  margin-left: 0;
}
.workspace-panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
  border-left: 1px solid var(--panel-border);
  background: #fff;
}
.workspace-panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 20px 18px 14px;
  border-bottom: 1px solid #edf0f4;
}
.workspace-panel-head h3 {
  margin: 6px 0 0;
  font-size: 18px;
  color: #0f172a;
}
.workspace-nav {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  border-bottom: 1px solid #edf0f4;
}
.workspace-nav button {
  padding: 11px 4px;
  border: 0;
  background: #fff;
  color: #64748b;
  font-size: 11px;
  cursor: pointer;
}
.workspace-nav button.active {
  color: #4f46e5;
  box-shadow: inset 0 -2px #6366f1;
}
.workspace-nav b {
  display: block;
  margin-top: 3px;
  font-size: 10px;
}
.panel-content {
  min-height: 0;
  overflow: auto;
  padding: 12px;
}
.panel-content-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 3px 3px 10px;
  color: #475569;
  font-size: 12px;
  font-weight: 700;
}
.panel-content-head button {
  border: 0;
  background: transparent;
  color: #6366f1;
  font-size: 11px;
  cursor: pointer;
}
.model-option,
.plain-option {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 10px 8px;
  border: 1px solid transparent;
  border-radius: 7px;
  text-align: left;
  background: transparent;
  cursor: pointer;
}
.model-option:hover,
.plain-option:hover {
  background: #f8fafc;
}
.model-option.selected {
  border-color: #c7d2fe;
  background: #eef2ff;
}
.model-mark {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 7px;
  color: #fff;
  background: #6366f1;
  font-size: 9px;
  font-weight: 700;
}
.model-mark img,
.model-option i img {
  width: 72%;
  height: 72%;
  object-fit: contain;
}
:global(.workspace-model-popper .el-select-dropdown__item) {
  position: relative;
  display: flex !important;
  justify-content: flex-start !important;
  padding: 0 10px !important;
  text-align: left !important;
}
:global(.workspace-model-popper) {
  width: 320px !important;
  max-width: calc(100vw - 24px) !important;
}
:global(.workspace-model-popper .model-option) {
  position: absolute;
  inset: 0 10px;
  display: flex !important;
  width: auto !important;
  align-items: center;
  justify-content: flex-start !important;
  margin: 0 !important;
  text-align: left !important;
  white-space: nowrap;
}
:global(.workspace-model-popper .model-option i) {
  margin-left: 0 !important;
}
.model-option {
  display: flex;
  align-items: center;
  gap: 8px;
}
.model-option i {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  border: 1px solid #e2e8f0;
  border-radius: 7px;
  color: #fff;
  font-size: 7px;
  font-style: normal;
  font-weight: 800;
  letter-spacing: 0;
}
.model-option b,
.model-option small,
.plain-option,
.plain-option small {
  display: block;
}
.model-option b {
  font-size: 12px;
  color: #1e293b;
}
.model-option small,
.plain-option small {
  margin-top: 3px;
  color: #94a3b8;
  font-size: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.model-option i {
  margin-left: auto;
  color: #6366f1;
  font-style: normal;
  font-size: 10px;
}
.panel-empty {
  padding: 34px 12px;
  text-align: center;
  color: #94a3b8;
  font-size: 11px;
  line-height: 1.7;
}
.check-option {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 10px 8px;
  color: #334155;
  font-size: 12px;
}
.check-option input {
  accent-color: #6366f1;
}
@media (max-width: 1100px) {
  .ai-shell {
    grid-template-columns: 230px minmax(0, 1fr);
  }
  .workspace-panel {
    display: none;
  }
}
.provider-presets {
  flex-wrap: wrap;
}
.provider-presets button {
  cursor: pointer;
  transition: 0.15s;
}
.provider-presets button:hover {
  border-color: var(--brand-primary);
  color: var(--brand-primary);
  background: #f5f7ff;
}
.settings-provider-form {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2px 18px;
}
.settings-provider-form .el-form-item:first-child,
.settings-provider-form .el-form-item:nth-child(2),
.settings-provider-form .el-form-item:nth-child(5) {
  grid-column: 1/-1;
}
.workspace-row {
  transition: background 0.15s;
}
.workspace-row:hover {
  background: #f8fafc;
}
.model-center-dialog .el-dialog__body {
  padding: 0;
  background: #f5f7fb;
}
.model-center-dialog .el-dialog__footer {
  display: none;
}
.model-center-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  min-height: calc(100vh - 110px);
}
.connection-rail {
  padding: 24px 14px;
  background: #0f172a;
  color: #dbe4f0;
}
.rail-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px 18px;
}
.rail-heading b {
  display: block;
  font-size: 16px;
  color: #fff;
}
.rail-heading small {
  display: block;
  margin-top: 4px;
  color: #94a3b8;
  font-size: 11px;
}
.connection-item {
  width: 100%;
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr);
  gap: 10px;
  padding: 12px 10px;
  border: 0;
  border-radius: 8px;
  text-align: left;
  background: transparent;
  color: #cbd5e1;
  cursor: pointer;
}
.connection-item:hover,
.connection-item.active {
  background: #1e293b;
  color: #fff;
}
.connection-item b,
.connection-item small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.connection-item b {
  font-size: 13px;
}
.connection-item small {
  margin-top: 5px;
  color: #94a3b8;
  font-size: 10px;
}
.connection-dot {
  width: 8px;
  height: 8px;
  margin-top: 4px;
  border-radius: 50%;
  background: #64748b;
}
.connection-dot.online {
  background: #34d399;
  box-shadow: 0 0 0 3px rgba(52, 211, 153, 0.14);
}
.rail-empty {
  padding: 45px 12px;
  text-align: center;
  color: #64748b;
  font-size: 12px;
  line-height: 1.8;
}
.connection-editor {
  padding: 42px clamp(24px, 5vw, 72px);
  overflow: auto;
}
.editor-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
  max-width: 1000px;
  margin: 0 auto 32px;
}
.eyebrow {
  color: #6366f1;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
}
.editor-heading h2 {
  margin: 8px 0 6px;
  color: #0f172a;
  font-size: 26px;
}
.editor-heading p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}
.editor-actions {
  display: flex;
  gap: 8px;
}
.editor-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 0.75fr);
  gap: 18px;
  max-width: 1000px;
  margin: auto;
}
.editor-panel {
  padding: 22px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 4px 18px rgba(15, 23, 42, 0.04);
}
.panel-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
  color: #0f172a;
  font-size: 14px;
  font-weight: 700;
}
.model-panel {
  min-height: 260px;
}
@media (max-width: 800px) {
  .model-center-layout {
    grid-template-columns: 1fr;
  }
  .connection-rail {
    min-height: auto;
  }
  .editor-heading,
  .editor-grid {
    display: block;
  }
  .editor-actions {
    margin-top: 18px;
  }
  .editor-panel {
    margin-bottom: 14px;
  }
}
.ai-shell {
  grid-template-columns: 260px minmax(0, 1fr) 300px !important;
}
@media (max-width: 1100px) {
  .ai-shell {
    grid-template-columns: 230px minmax(0, 1fr) !important;
  }
  .workspace-panel {
    display: none;
  }
}
.connection-model-list {
  display: grid;
  gap: 4px;
  max-height: 520px;
  overflow: auto;
}
.connection-model-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 7px;
  border-bottom: 1px solid #edf0f4;
}
.connection-model-row b,
.connection-model-row small {
  display: block;
}
.connection-model-row b {
  color: #1e293b;
  font-size: 12px;
}
.connection-model-row small {
  margin-top: 3px;
  color: #94a3b8;
  font-size: 10px;
}
.chat-sidebar {
  padding: 10px !important;
}
.new-chat {
  justify-content: flex-start !important;
  padding: 0 12px !important;
  font-weight: 500 !important;
}
.chat-list > button {
  min-height: 48px !important;
  border-radius: 7px !important;
}
.chat-toolbar {
  height: 52px !important;
  padding: 0 18px !important;
}
.chat-toolbar strong {
  font-size: 14px !important;
  font-weight: 600;
}
.message-pane {
  padding-top: 32px !important;
}
.message {
  max-width: 760px !important;
  margin-bottom: 26px !important;
}
.message-avatar {
  border-radius: 8px !important;
}
.message-content {
  font-size: 14px !important;
  line-height: 1.8 !important;
}
.chat-composer {
  padding-bottom: 18px !important;
}
.composer-box {
  max-width: 760px !important;
  border-radius: 12px !important;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.06) !important;
}
.composer-box .send-button {
  border-radius: 9px !important;
}
.workspace-panel-head {
  padding: 18px 16px 13px !important;
}
.workspace-panel-head h3 {
  font-size: 16px !important;
}
.ai-shell.compact {
  grid-template-columns: 260px minmax(0, 1fr) !important;
}
.workspace-links {
  display: grid;
  gap: 2px;
  margin: 8px 0;
}
.workspace-links button {
  height: 36px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 10px;
  border: 0;
  border-radius: 6px;
  color: var(--text-main);
  background: transparent;
  text-align: left;
  cursor: pointer;
}
.workspace-links button:hover {
  background: #e9eef7;
  color: var(--brand-primary);
}
.workspace-links .el-icon {
  font-size: 15px;
}
.conversation-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 8px 5px;
  color: var(--text-secondary);
  font-size: 11px;
}
.conversation-label small {
  font-size: 10px;
}
.chat-search {
  margin: 2px 0 !important;
}
.chat-main {
  position: relative;
}
.message-pane {
  padding-bottom: 170px !important;
}
.chat-composer {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 4;
  padding-top: 28px !important;
  background: linear-gradient(
    to bottom,
    rgba(255, 255, 255, 0),
    #fff 24px,
    #fff
  );
}
.chat-transfer {
  margin-top: auto;
}
.conversation-label button {
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
}
.conversation-label button:hover {
  color: var(--brand-primary);
}
.chat-actions > span {
  font-size: 11px;
  font-style: normal;
  cursor: pointer;
}
.chat-actions > span:hover {
  color: var(--brand-primary);
}
.folder-bar {
  display: flex;
  gap: 6px;
  margin: 4px 0 6px;
}
.folder-bar .el-select {
  min-width: 0;
  flex: 1;
}
.folder-bar .el-button {
  padding: 0 7px;
}
.generated-image {
  display: grid;
  justify-items: start;
  gap: 8px;
  width: min(100%, 520px);
}
.generated-image-preview {
  display: flex;
  width: 100%;
  max-height: 520px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}
.generated-image img {
  display: block;
  width: 100%;
  height: auto;
  max-height: 520px;
  object-fit: contain;
}
.generated-image > a:last-child {
  color: #64748b;
  font-size: 12px;
  text-decoration: none;
}
.generated-image > a:last-child:hover {
  color: #4f46e5;
}

/* Keep the workspace fluid after the later desktop overrides above. */
.ai-shell {
  container-type: inline-size;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  flex: 1 1 auto;
  height: 100%;
  max-height: 100%;
  min-height: 0;
  min-height: 0;
  grid-template-columns: clamp(190px, 21vw, 260px) minmax(0, 1fr) clamp(
      240px,
      24vw,
      300px
    ) !important;
}
.chat-main,
.message-pane,
.chat-composer,
.composer-box {
  min-width: 0;
  max-width: 100%;
}
.chat-main {
  grid-template-rows: 52px minmax(0, 1fr) max-content;
  overflow: hidden;
}
.message-pane {
  padding-bottom: 24px !important;
}
.chat-composer {
  position: relative;
  left: auto;
  right: auto;
  bottom: auto;
  z-index: 4;
  flex: none;
  overflow: visible;
  padding-top: 10px !important;
  background: #fff;
}
.composer-box {
  width: 100%;
  max-width: 100% !important;
  box-sizing: border-box;
}
.composer-actions {
  flex-wrap: wrap;
}
.composer-tools {
  flex: 1 1 520px;
  flex-wrap: wrap;
  overflow: visible;
}
.composer-box .send-button {
  margin-left: auto;
}
.message-body,
.message-content,
.markdown-body {
  max-width: 100%;
  min-width: 0;
}
.message-sources a,
.message-sources button {
  max-width: 100%;
  box-sizing: border-box;
  overflow-wrap: anywhere;
}
.markdown-body :deep(table) {
  display: block;
  max-width: 100%;
  overflow-x: auto;
  white-space: nowrap;
}
@media (max-width: 1200px) {
  .ai-shell,
  .ai-shell.compact {
    grid-template-columns: clamp(190px, 23vw, 230px) minmax(0, 1fr) !important;
  }
  .workspace-panel {
    display: none;
  }
  .message-pane,
  .chat-composer {
    padding-left: clamp(12px, 3vw, 28px) !important;
    padding-right: clamp(12px, 3vw, 28px) !important;
  }
}
@media (max-width: 860px) {
  .ai-shell,
  .ai-shell.compact {
    grid-template-columns: minmax(0, 1fr) !important;
    height: 100%;
    max-height: 100%;
    min-height: 0;
    border-radius: 0;
  }
  .chat-sidebar {
    display: none;
  }
  .chat-toolbar {
    padding: 0 12px !important;
  }
  .message-pane {
    padding: 20px 14px 24px !important;
  }
  .chat-composer {
    padding: 10px 12px 12px !important;
  }
  .composer-actions {
    align-items: flex-end;
  }
  .composer-tools {
    gap: 5px;
  }
}
/* The workspace sits beside the admin navigation, so its own width is the
   useful responsive signal rather than the browser viewport width. */
@container (max-width:1000px) {
  .ai-shell,
  .ai-shell.compact {
    grid-template-columns: clamp(180px, 24cqw, 220px) minmax(0, 1fr) !important;
  }
  .workspace-panel {
    display: none;
  }
  .message-pane,
  .chat-composer {
    padding-left: 16px !important;
    padding-right: 16px !important;
  }
  .composer-tools {
    flex-basis: 100%;
    gap: 5px;
  }
}
@container (max-width:720px) {
  .ai-shell,
  .ai-shell.compact {
    grid-template-columns: minmax(0, 1fr) !important;
  }
  .chat-sidebar {
    display: none;
  }
  .chat-toolbar {
    padding: 0 10px !important;
  }
  .message-pane {
    padding: 18px 12px 22px !important;
  }
  .chat-composer {
    padding: 8px 10px 10px !important;
  }
  .toolbar-controls {
    gap: 5px;
  }
  .composer-actions {
    align-items: flex-end;
  }
  .composer-model-select {
    width: 150px;
    flex-basis: 150px;
  }
}

/* Keep the composer inside the visible chat viewport at every window height. */
.chat-main {
  position: relative;
  --composer-height: clamp(104px, 14dvh, 136px);
  grid-template-rows: 52px minmax(0, 1fr) !important;
}
.message-pane {
  padding-bottom: var(--composer-height) !important;
}
.chat-composer {
  position: absolute !important;
  right: 0 !important;
  bottom: 0 !important;
  left: 0 !important;
  z-index: 6;
  height: var(--composer-height) !important;
  min-height: 0 !important;
  box-sizing: border-box;
  max-height: 45%;
  overflow-y: auto;
  padding-top: 28px !important;
  background: linear-gradient(
    to bottom,
    rgba(255, 255, 255, 0),
    #fff 24px,
    #fff
  );
}
@container (max-width:720px) {
  .chat-main {
    --composer-height: clamp(116px, 18dvh, 156px);
  }
  .message-pane {
    padding-bottom: var(--composer-height) !important;
  }
  .chat-composer {
    height: var(--composer-height) !important;
    min-height: 0 !important;
    padding: 18px 10px 8px !important;
  }
}
@media (max-height: 700px) {
  .chat-main {
    --composer-height: 100px;
  }
  .chat-composer {
    padding-top: 10px !important;
    padding-bottom: 8px !important;
  }
  .composer-box {
    gap: 5px;
    padding-top: 7px;
    padding-bottom: 7px;
  }
  .composer-box textarea {
    min-height: 30px;
    padding-top: 2px;
    padding-bottom: 2px;
  }
  .chat-composer > small {
    display: none;
  }
}

/* Composer is a dedicated grid row, outside the scrolling message viewport. */
.ai-shell,
.ai-shell.compact {
  grid-template-rows: minmax(0, 1fr) auto;
}
.chat-sidebar {
  grid-row: 1 / -1;
}
.chat-main {
  grid-column: 2;
  grid-row: 1;
  grid-template-rows: 52px minmax(0, 1fr) !important;
}
.message-pane {
  padding-bottom: 24px !important;
}
.chat-composer {
  position: relative !important;
  grid-column: 2;
  grid-row: 2;
  right: auto !important;
  bottom: auto !important;
  left: auto !important;
  height: auto !important;
  min-height: 0 !important;
  max-height: none;
  overflow: visible;
  padding-top: 10px !important;
  background: #fff;
}
@container (max-width:720px) {
  .chat-main,
  .chat-composer {
    grid-column: 1;
  }
  .chat-composer {
    height: auto !important;
    padding: 8px 10px 10px !important;
  }
}
@media (max-height: 700px) {
  .chat-composer {
    height: auto !important;
    padding-top: 6px !important;
  }
}
.pending-images {
  display: flex;
  gap: 7px;
  margin: 0 auto 7px;
  max-width: 100%;
}
.pending-images button {
  position: relative;
  width: 54px;
  height: 54px;
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--panel-border);
  border-radius: 6px;
  background: #fff;
}
.pending-images img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.pending-images span {
  position: absolute;
  top: 2px;
  right: 3px;
  display: grid;
  place-items: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  color: #fff;
  background: rgba(15, 23, 42, 0.75);
}
.pending-reference {
  display: flex;
  align-items: center;
  gap: 10px;
  max-width: 760px;
  margin: 0 auto;
}
.pending-reference .pending-images {
  margin: 0 0 7px;
}
.pending-reference small {
  margin-bottom: 7px;
  color: #6366f1;
  font-size: 11px;
}
.image-mode-row,
.output-actions {
  display: flex;
  align-items: center;
  gap: 7px;
  max-width: 100%;
  margin: 0 auto 6px;
}
.output-actions {
  justify-content: flex-end;
}
.image-mode-row .el-button,
.output-actions .el-button {
  height: 28px;
  font-size: 11px;
}

/* Keep all input capabilities in one compact composer surface. */
.chat-composer {
  padding: 10px clamp(16px, 4vw, 48px) 14px !important;
  border-top: 1px solid #e5e7eb;
  background: #fff;
}
.message-pane {
  background: #f7f8fa;
}
.composer-box {
  width: 100%;
  max-width: 760px !important;
  margin: 0 auto;
  padding: 10px 12px;
  border-radius: 10px !important;
}
.composer-box textarea {
  min-height: 42px;
}
.composer-actions {
  flex-wrap: nowrap;
  gap: 10px;
}
.composer-tools {
  flex: 1 1 auto;
  flex-wrap: nowrap;
  gap: 6px;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
}
.composer-tools::-webkit-scrollbar {
  display: none;
}
.composer-tools .el-button {
  height: 30px;
  padding: 0 10px;
}
.composer-tools .el-button:first-child {
  width: 30px;
  padding: 0;
}
.image-size-select {
  width: 86px;
}
.chat-composer > small {
  max-width: 760px;
}
.message-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
}
.message-actions button {
  padding: 2px 0;
  border: 0;
  color: var(--text-secondary);
  background: transparent;
  font-size: 11px;
  cursor: pointer;
}
.message-actions button:hover {
  color: var(--brand-primary);
}
@container (max-width:720px) {
  .composer-actions {
    align-items: flex-end;
    flex-wrap: nowrap;
  }
}
</style>
