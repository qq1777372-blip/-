<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import {
  IonButton,
  IonContent,
  IonIcon,
  IonPage,
  IonSpinner,
  toastController,
} from "@ionic/vue";
import {
  addOutline,
  cloudDownloadOutline,
  createOutline,
  downloadOutline,
  powerOutline,
  searchOutline,
} from "ionicons/icons";
import PageHeader from "../components/PageHeader.vue";
import { session } from "../session";
import {
  aiProviderPresets,
  modelProviderPreset,
  providerLogoBackground,
  providerPreset,
} from "../utils/aiProviders";

const providerAssetBase = "/app/ai-providers/";
type Connection = {
  id: string;
  name: string;
  base_url: string;
  provider_type?: string;
  provider_id?: string;
  enabled: number;
  has_key?: boolean;
  purpose?: string;
};
type Resource = { id: string; name: string };
type Model = {
  id: string;
  name: string;
  base_model: string;
  description?: string;
  connection_id?: string;
  provider_id?: string;
  enabled: number;
  hidden?: number;
  pinned?: number;
  is_default?: number;
  temperature?: number;
  top_p?: number;
  max_tokens?: number;
  system_prompt?: string;
  model_type?: "chat" | "image" | "embedding" | "audio";
  input_price?: number;
  output_price?: number;
  access?: string;
  access_grants?: string | string[];
  knowledge_id?: string;
  skill_ids?: string | string[];
  tool_ids?: string | string[];
  filters?: string | string[];
  actions?: string | string[];
  tags?: string | string[];
  capabilities?: string | string[];
  sort_order?: number;
};
const tab = ref<"models" | "connections">("models"),
  loading = ref(false),
  search = ref(""),
  models = ref<Model[]>([]),
  connections = ref<Connection[]>([]),
  knowledge = ref<Resource[]>([]),
  skills = ref<Resource[]>([]),
  tools = ref<Resource[]>([]),
  connectionOpen = ref(false),
  modelOpen = ref(false),
  saving = ref(false),
  page = ref(1),
  pageSize = ref(10),
  importInput = ref<HTMLInputElement | null>(null);
const connectionForm = ref({
  id: "",
  name: "",
  base_url: "",
  provider_type: "openai",
  provider_id: "openai",
  api_key: "",
  purpose: "general",
});
function connectionProvider(c: Connection) {
  const configured = providerPreset(c.provider_id);
  if (configured.id !== "custom") return configured;
  const counts = new Map<string, number>();
  for (const model of models.value.filter((m) => m.connection_id === c.id)) {
    const detected = modelProviderPreset(model.base_model, c.provider_id);
    counts.set(detected.id, (counts.get(detected.id) || 0) + 1);
  }
  const dominant = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
  return providerPreset(dominant || c.provider_id);
}
function list(value?: string | string[]) {
  if (Array.isArray(value)) return value;
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return value
      .split(/[\n,]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
}
function setList(
  field: "skill_ids" | "tool_ids" | "filters" | "actions",
  event: Event,
) {
  modelForm.value[field] = [
    ...(event.target as HTMLSelectElement).selectedOptions,
  ].map((option) => option.value);
}
const modelForm = ref<Model>({
  id: "",
  name: "",
  base_model: "",
  enabled: 1,
  temperature: 0.7,
  top_p: 1,
  max_tokens: 2048,
  system_prompt: "",
  model_type: "chat",
  input_price: 0,
  output_price: 0,
  access: "private",
});
const filtered = computed(() => {
  const q = search.value.trim().toLowerCase();
  return q
    ? models.value.filter((m) =>
        `${m.name} ${m.base_model}`.toLowerCase().includes(q),
      )
    : models.value;
});
watch([search, pageSize, tab], () => {
  page.value = 1;
});
async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`/ai-api/${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Workspace-User": String(session.user?.id || "local"),
      "X-Workspace-Role": session.user?.role || "user",
    },
    ...init,
  });
  const d = (await r.json().catch(() => ({}))) as T & {
    error?: string;
    detail?: string;
  };
  if (!r.ok) throw new Error(d.error || d.detail || `请求失败（${r.status}）`);
  return d;
}
async function notify(message: string) {
  const t = await toastController.create({ message, duration: 1800 });
  await t.present();
}
async function load() {
  loading.value = true;
  try {
    const [m, c, k, s, t] = await Promise.all([
      api<{ models: Model[] }>("models"),
      api<{ connections: Connection[] }>("connections"),
      api<{ knowledge: Resource[] }>("knowledge"),
      api<{ skills: Resource[] }>("skills"),
      api<{ tools: Resource[] }>("tools?all=1"),
    ]);
    models.value = m.models || [];
    connections.value = c.connections || [];
    knowledge.value = k.knowledge || [];
    skills.value = s.skills || [];
    tools.value = t.tools || [];
  } catch (e) {
    await notify(e instanceof Error ? e.message : "加载失败");
  } finally {
    loading.value = false;
  }
}
async function sync(id = "") {
  loading.value = true;
  try {
    const r = await api<{ total: number }>(
      id ? "connections/sync" : "models/sync",
      { method: "POST", body: id ? JSON.stringify({ id }) : "{}" },
    );
    await load();
    await notify(`同步完成：${r.total} 个模型`);
  } catch (e) {
    await notify(e instanceof Error ? e.message : "同步失败");
  } finally {
    loading.value = false;
  }
}
async function toggleModel(m: Model) {
  try {
    await api("models/update", {
      method: "POST",
      body: JSON.stringify({ ...m, enabled: m.enabled ? 0 : 1 }),
    });
    m.enabled = m.enabled ? 0 : 1;
  } catch (e) {
    await notify(e instanceof Error ? e.message : "更新失败");
  }
}
function editModel(m: Model) {
  modelForm.value = {
    ...m,
    temperature: Number(m.temperature ?? 0.7),
    top_p: Number(m.top_p ?? 1),
    max_tokens: Number(m.max_tokens ?? 2048),
    model_type: m.model_type || "chat",
    input_price: Number(m.input_price || 0),
    output_price: Number(m.output_price || 0),
    access: m.access || "private",
    skill_ids: list(m.skill_ids),
    tool_ids: list(m.tool_ids),
    filters: list(m.filters),
    actions: list(m.actions),
    access_grants: list(m.access_grants),
    tags: list(m.tags),
    capabilities: list(m.capabilities),
    sort_order: Number(m.sort_order || 0),
  };
  modelOpen.value = true;
}
function newModel() {
  modelForm.value = {
    id: "",
    name: "",
    base_model: "",
    connection_id: connections.value.find((item) => item.enabled)?.id || "",
    description: "",
    enabled: 1,
    hidden: 0,
    pinned: 0,
    is_default: 0,
    temperature: 0.7,
    top_p: 1,
    max_tokens: 2048,
    system_prompt: "",
    model_type: "chat",
    input_price: 0,
    output_price: 0,
    access: "private",
    skill_ids: [],
    tool_ids: [],
    filters: [],
    actions: [],
    access_grants: [],
    tags: [],
    capabilities: ["chat"],
    sort_order: 0,
  };
  modelOpen.value = true;
}
async function saveModel() {
  saving.value = true;
  try {
    await api(modelForm.value.id ? "models/update" : "models", {
      method: "POST",
      body: JSON.stringify(modelForm.value),
    });
    modelOpen.value = false;
    await load();
    await notify("模型设置已保存");
  } catch (e) {
    await notify(e instanceof Error ? e.message : "保存失败");
  } finally {
    saving.value = false;
  }
}
async function removeModel(m: Model) {
  if (!confirm(`删除模型“${m.name}”？`)) return false;
  try {
    await api("models/delete", {
      method: "POST",
      body: JSON.stringify({ id: m.id }),
    });
    await load();
    await notify("模型已删除");
    return true;
  } catch (e) {
    await notify(e instanceof Error ? e.message : "删除失败");
    return false;
  }
}
async function duplicateModel(m: Model) {
  const copy = { ...m, id: "", name: `${m.name} 副本`, is_default: 0 };
  try {
    await api("models", { method: "POST", body: JSON.stringify(copy) });
    await load();
    await notify("模型已复制");
  } catch (e) {
    await notify(e instanceof Error ? e.message : "复制失败");
  }
}
async function batchModels(action: string) {
  if (!action) return;
  const changes =
    action === "enable"
      ? { enabled: 1 }
      : action === "disable"
        ? { enabled: 0 }
        : action === "show"
          ? { hidden: 0 }
          : { hidden: 1 };
  try {
    await Promise.all(
      filtered.value.map((m) =>
        api("models/update", {
          method: "POST",
          body: JSON.stringify({ ...m, ...changes }),
        }),
      ),
    );
    await load();
    await notify("批量操作完成");
  } catch (e) {
    await notify(e instanceof Error ? e.message : "批量操作失败");
  }
}
function exportModels() {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify({ version: 1, models: models.value }, null, 2)], {
      type: "application/json",
    }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = `workspace-models-${new Date().toISOString().slice(0, 10)}.json`;
  link.click();
  URL.revokeObjectURL(url);
}
async function importModels(event: Event) {
  const input = event.target as HTMLInputElement,
    file = input.files?.[0];
  input.value = "";
  if (!file) return;
  try {
    const parsed = JSON.parse(await file.text()),
      incoming = Array.isArray(parsed) ? parsed : parsed.models;
    if (!Array.isArray(incoming)) throw new Error("文件格式不正确");
    await Promise.all(
      incoming.map((m: Model) =>
        api(m.id ? "models/update" : "models", {
          method: "POST",
          body: JSON.stringify(m),
        }),
      ),
    );
    await load();
    await notify(`已导入 ${incoming.length} 个模型`);
  } catch (e) {
    await notify(e instanceof Error ? e.message : "导入失败");
  }
}
function openConnection(c?: Connection) {
  connectionForm.value = c
    ? {
        id: c.id,
        name: c.name,
        base_url: c.base_url,
        provider_type: c.provider_type || "openai",
        provider_id: c.provider_id || "custom",
        api_key: "",
        purpose: c.purpose || "general",
      }
    : {
        id: "",
        name: "OpenAI",
        base_url: "https://api.openai.com/v1",
        provider_type: "openai",
        provider_id: "openai",
        api_key: "",
        purpose: "general",
      };
  connectionOpen.value = true;
}
function selectProvider(id: string) {
  const preset = providerPreset(id);
  connectionForm.value.provider_id = preset.id;
  connectionForm.value.provider_type = preset.protocol;
  connectionForm.value.name = preset.name;
  if (preset.baseUrl) connectionForm.value.base_url = preset.baseUrl;
}
async function saveConnection() {
  saving.value = true;
  try {
    await api("connections/save", {
      method: "POST",
      body: JSON.stringify({ ...connectionForm.value, enabled: true }),
    });
    connectionOpen.value = false;
    await load();
    await notify("连接已保存并同步");
  } catch (e) {
    await notify(e instanceof Error ? e.message : "保存失败");
  } finally {
    saving.value = false;
  }
}
async function toggleConnection(c: Connection) {
  try {
    await api("connections/toggle", {
      method: "POST",
      body: JSON.stringify({ id: c.id, enabled: !c.enabled }),
    });
    await load();
  } catch (e) {
    await notify(e instanceof Error ? e.message : "更新失败");
  }
}
async function testConnection(c: Connection) {
  try {
    const result = await api<{ message?: string }>("connections/test", {
      method: "POST",
      body: JSON.stringify({ id: c.id }),
    });
    await notify(result.message || "连接测试成功");
  } catch (e) {
    await notify(e instanceof Error ? e.message : "连接测试失败");
  }
}
async function removeConnection(c: Connection) {
  if (!confirm(`删除连接“${c.name}”及其同步模型？`)) return false;
  try {
    await api("connections/delete", {
      method: "POST",
      body: JSON.stringify({ id: c.id }),
    });
    await load();
    await notify("连接已删除");
    return true;
  } catch (e) {
    await notify(e instanceof Error ? e.message : "删除失败");
    return false;
  }
}
async function syncCurrentConnection() {
  if (connectionForm.value.id) await sync(connectionForm.value.id);
}
async function testCurrentConnection() {
  const current = connections.value.find(
    (item) => item.id === connectionForm.value.id,
  );
  if (current) await testConnection(current);
}
async function removeCurrentConnection() {
  const current = connections.value.find(
    (item) => item.id === connectionForm.value.id,
  );
  if (!current) return;
  if (await removeConnection(current)) connectionOpen.value = false;
}
async function duplicateCurrentModel() {
  await duplicateModel(modelForm.value);
  modelOpen.value = false;
}
async function removeCurrentModel() {
  if (await removeModel(modelForm.value)) modelOpen.value = false;
}
onMounted(load);
</script>
<template>
  <IonPage
    ><PageHeader
      title="AI 模型中心"
      subtitle="管理模型与接口连接"
      back
    /><IonContent
      ><main>
        <div class="native-redesign">
          <section class="app-overview">
            <div>
              <small>AI WORKSPACE</small>
              <h1>模型中心</h1>
              <p>管理模型与平台连接</p>
            </div>
            <span
              ><b>{{ models.filter((item) => item.enabled).length }}</b
              ><small>已启用</small></span
            >
          </section>

          <section class="app-action-grid">
            <button @click="openConnection()">
              <i><IonIcon :icon="addOutline" /></i><b>新增连接</b>
            </button>
            <button :disabled="!connections.length" @click="newModel">
              <i><IonIcon :icon="createOutline" /></i><b>创建模型</b>
            </button>
            <button :disabled="loading || !connections.length" @click="sync()">
              <i
                ><IonSpinner v-if="loading" name="dots" /><IonIcon
                  v-else
                  :icon="cloudDownloadOutline" /></i
              ><b>同步模型</b>
            </button>
            <button @click="importInput?.click()">
              <i><IonIcon :icon="cloudDownloadOutline" /></i><b>导入配置</b>
            </button>
            <input
              ref="importInput"
              hidden
              type="file"
              accept="application/json,.json"
              @change="importModels"
            />
          </section>

          <nav class="app-segments">
            <button
              :class="{ active: tab === 'models' }"
              @click="tab = 'models'"
            >
              模型 <span>{{ models.length }}</span>
            </button>
            <button
              :class="{ active: tab === 'connections' }"
              @click="tab = 'connections'"
            >
              连接 <span>{{ connections.length }}</span>
            </button>
          </nav>

          <template v-if="tab === 'models'">
            <div class="app-search">
              <IonIcon :icon="searchOutline" />
              <input v-model="search" placeholder="搜索模型名称或型号" />
              <button aria-label="导出模型" @click="exportModels">
                <IonIcon :icon="downloadOutline" />
              </button>
            </div>
            <div class="app-section-title">
              <div>
                <h2>全部模型</h2>
                <small>点击模型查看详细设置</small>
              </div>
              <button @click="newModel">
                <IonIcon :icon="addOutline" />新增
              </button>
            </div>
            <section v-if="filtered.length" class="app-list">
              <article
                v-for="m in filtered"
                :key="m.id"
                class="app-list-row"
                :class="{ disabled: !m.enabled }"
                @click="editModel(m)"
              >
                <i
                  class="provider-mark"
                  :style="{
                    background: providerLogoBackground(
                      modelProviderPreset(m.base_model, m.provider_id),
                    ),
                  }"
                  ><img
                    v-if="modelProviderPreset(m.base_model, m.provider_id).logo"
                    :src="
                      providerAssetBase +
                      modelProviderPreset(m.base_model, m.provider_id).logo
                    "
                    alt=""
                  /><span v-else>{{
                    modelProviderPreset(m.base_model, m.provider_id).short
                  }}</span></i
                >
                <span class="row-content"
                  ><strong>{{ m.name }}</strong
                  ><small>{{ m.base_model }}</small
                  ><em>{{
                    connections.find((c) => c.id === m.connection_id)?.name ||
                    "历史模型"
                  }}</em></span
                >
                <span v-if="m.is_default" class="default-badge">默认</span>
                <button
                  class="state-button"
                  :class="{ on: m.enabled }"
                  aria-label="切换模型状态"
                  @click.stop="toggleModel(m)"
                >
                  <IonIcon :icon="powerOutline" />
                </button>
                <span class="native-chevron">›</span>
              </article>
            </section>
            <section v-else-if="!loading" class="app-empty">
              <IonIcon :icon="createOutline" /><b>还没有可用模型</b>
              <p>先新增平台连接，再同步或创建模型</p>
              <button @click="openConnection()">新增连接</button>
            </section>
          </template>

          <template v-else>
            <div class="app-section-title">
              <div>
                <h2>平台连接</h2>
                <small>管理 API 地址与密钥</small>
              </div>
              <button @click="openConnection()">
                <IonIcon :icon="addOutline" />新增
              </button>
            </div>
            <section v-if="connections.length" class="app-list">
              <article
                v-for="c in connections"
                :key="c.id"
                class="app-list-row"
                :class="{ disabled: !c.enabled }"
                @click="openConnection(c)"
              >
                <i
                  class="provider-mark"
                  :style="{
                    background: providerLogoBackground(connectionProvider(c)),
                  }"
                  ><img
                    v-if="connectionProvider(c).logo"
                    :src="providerAssetBase + connectionProvider(c).logo"
                    alt=""
                  /><span v-else>{{ connectionProvider(c).short }}</span></i
                >
                <span class="row-content"
                  ><strong>{{ c.name }}</strong
                  ><small>{{ c.base_url }}</small
                  ><em>{{
                    c.provider_type === "ollama" ? "Ollama" : "OpenAI 兼容"
                  }}</em></span
                >
                <button
                  class="state-button"
                  :class="{ on: c.enabled }"
                  aria-label="切换连接状态"
                  @click.stop="toggleConnection(c)"
                >
                  <IonIcon :icon="powerOutline" />
                </button>
                <span class="native-chevron">›</span>
              </article>
            </section>
            <section v-else class="app-empty">
              <IonIcon :icon="addOutline" /><b>还没有平台连接</b>
              <p>添加 AI 平台后即可同步模型</p>
              <button @click="openConnection()">新增连接</button>
            </section>
          </template>
        </div>
        <div class="tabs">
          <button :class="{ active: tab === 'models' }" @click="tab = 'models'">
            模型 {{ models.length }}</button
          ><button
            :class="{ active: tab === 'connections' }"
            @click="tab = 'connections'"
          >
            连接 {{ connections.length }}
          </button>
        </div>
        <section class="model-quick-actions panel">
          <button
            @click="
              tab = 'connections';
              openConnection();
            "
          >
            <IonIcon :icon="addOutline" />
            <span><b>新增连接</b><small>配置平台 API</small></span>
          </button>
          <button :disabled="!connections.length" @click="newModel">
            <IonIcon :icon="createOutline" />
            <span
              ><b>创建模型</b
              ><small>{{
                connections.length ? "设置工作区模型" : "请先新增连接"
              }}</small></span
            >
          </button>
          <button :disabled="loading || !connections.length" @click="sync()">
            <IonSpinner v-if="loading" name="dots" />
            <IonIcon v-else :icon="cloudDownloadOutline" />
            <span><b>同步模型</b><small>读取平台模型列表</small></span>
          </button>
        </section>
        <template v-if="tab === 'models'"
          ><div class="toolbar">
            <IonButton size="small" fill="outline" @click="newModel"
              ><IonIcon :icon="addOutline" />新建</IonButton
            >
            <label
              ><IonIcon :icon="searchOutline" /><input
                v-model="search"
                placeholder="搜索模型" /></label
            ><select
              aria-label="批量操作"
              @change="
                batchModels(($event.target as HTMLSelectElement).value);
                ($event.target as HTMLSelectElement).value = '';
              "
            >
              <option value="">批量</option>
              <option value="enable">全部启用</option>
              <option value="disable">全部停用</option>
              <option value="show">全部显示</option>
              <option value="hide">全部隐藏</option></select
            ><button
              class="tool-icon"
              aria-label="导出模型"
              @click="exportModels"
            >
              <IonIcon :icon="downloadOutline" /></button
            ><button
              class="tool-icon"
              aria-label="导入模型"
              @click="importInput?.click()"
            >
              <IonIcon :icon="cloudDownloadOutline" /></button
            ><input
              ref="importInput"
              hidden
              type="file"
              accept="application/json,.json"
              @change="importModels"
            /><IonButton size="small" :disabled="loading" @click="sync()"
              ><IonSpinner v-if="loading" name="dots" /><IonIcon
                v-else
                :icon="cloudDownloadOutline"
              />同步</IonButton
            >
          </div>
          <div v-if="!filtered.length && !loading" class="empty">
            暂无模型，请先配置连接
          </div>
          <article
            v-for="m in filtered"
            :key="m.id"
            :class="{ disabled: !m.enabled }"
            @click="editModel(m)"
          >
            <span
              class="mark"
              :style="{
                background: providerLogoBackground(
                  modelProviderPreset(m.base_model, m.provider_id),
                ),
              }"
              ><img
                v-if="modelProviderPreset(m.base_model, m.provider_id).logo"
                :src="`${providerAssetBase}${modelProviderPreset(m.base_model, m.provider_id).logo}`"
                alt=""
              /><span v-else>{{
                modelProviderPreset(m.base_model, m.provider_id).short
              }}</span></span
            >
            <div>
              <b>{{ m.name }} <em v-if="m.is_default">默认</em></b
              ><small>{{ m.base_model }}</small
              ><small>{{
                connections.find((c) => c.id === m.connection_id)?.name ||
                "历史模型"
              }}</small>
            </div>
            <button aria-label="切换模型状态" @click.stop="toggleModel(m)">
              <IonIcon :icon="powerOutline" /></button
            ><span class="row-arrow">›</span>
          </article>
          <div class="pager">
            <span>共 {{ filtered.length }} 条</span
            ><select v-model.number="pageSize">
              <option :value="10">10/页</option>
              <option :value="20">20/页</option>
              <option :value="50">50/页</option></select
            ><button :disabled="page <= 1" @click="page--">上一页</button
            ><b
              >{{ page }}/{{
                Math.max(1, Math.ceil(filtered.length / pageSize))
              }}</b
            ><button
              :disabled="page >= Math.ceil(filtered.length / pageSize)"
              @click="page++"
            >
              下一页
            </button>
          </div></template
        ><template v-else
          ><div class="toolbar">
            <b>模型接口</b
            ><IonButton size="small" @click="openConnection()"
              ><IonIcon :icon="addOutline" />新增</IonButton
            >
          </div>
          <div v-if="!connections.length" class="empty">还没有模型连接</div>
          <article
            v-for="c in connections"
            :key="c.id"
            class="connection"
            :class="{ disabled: !c.enabled }"
            @click="openConnection(c)"
          >
            <span
              class="mark"
              :style="{
                background: providerLogoBackground(connectionProvider(c)),
              }"
              ><img
                v-if="connectionProvider(c).logo"
                :src="`${providerAssetBase}${connectionProvider(c).logo}`"
                alt=""
              /><span v-else>{{ connectionProvider(c).short }}</span></span
            >
            <div>
              <b>{{ c.name }}</b
              ><small>{{ c.base_url }}</small
              ><small>{{
                c.provider_type === "ollama" ? "Ollama" : "OpenAI 兼容"
              }}</small>
            </div>
            <button aria-label="切换连接状态" @click.stop="toggleConnection(c)">
              <IonIcon :icon="powerOutline" /></button
            ><span class="row-arrow">›</span>
          </article>
          <div class="pager">
            <span>共 {{ connections.length }} 条</span
            ><select v-model.number="pageSize">
              <option :value="10">10/页</option>
              <option :value="20">20/页</option>
              <option :value="50">50/页</option></select
            ><button :disabled="page <= 1" @click="page--">上一页</button
            ><b
              >{{ page }}/{{
                Math.max(1, Math.ceil(connections.length / pageSize))
              }}</b
            ><button
              :disabled="page >= Math.ceil(connections.length / pageSize)"
              @click="page++"
            >
              下一页
            </button>
          </div></template
        >
      </main></IonContent
    >
    <div
      v-if="connectionOpen"
      class="mask"
      @click.self="connectionOpen = false"
    >
      <section>
        <header>
          <b>{{ connectionForm.id ? "编辑连接" : "新增连接" }}</b
          ><button @click="connectionOpen = false">关闭</button>
        </header>
        <div class="provider-picker">
          <button
            v-for="preset in aiProviderPresets"
            :key="preset.id"
            type="button"
            :class="{ active: connectionForm.provider_id === preset.id }"
            @click="selectProvider(preset.id)"
          >
            <i :style="{ background: providerLogoBackground(preset) }"
              ><img
                v-if="preset.logo"
                :src="`${providerAssetBase}${preset.logo}`"
                alt=""
              /><span v-else>{{ preset.short }}</span></i
            ><span>{{ preset.name }}</span>
          </button>
        </div>
        <label>名称<input v-model="connectionForm.name" /></label
        ><label
          >API 地址<input
            v-model="connectionForm.base_url"
            placeholder="https://api.openai.com/v1" /></label
        ><label
          >API Key<input
            v-model="connectionForm.api_key"
            type="password"
            :placeholder="
              connectionForm.id ? '留空表示不修改' : '请输入 API Key'
            " /></label
        ><label
          >连接用途<select v-model="connectionForm.purpose">
            <option value="general">通用</option>
            <option value="chat">对话</option>
            <option value="image">生图</option>
            <option value="audio">音频</option>
          </select></label
        >
        <div v-if="connectionForm.id" class="sheet-actions">
          <IonButton fill="outline" @click="testCurrentConnection"
            >测试</IonButton
          >
          <IonButton fill="outline" @click="syncCurrentConnection"
            >同步</IonButton
          >
          <IonButton
            color="danger"
            fill="outline"
            @click="removeCurrentConnection"
            >删除</IonButton
          >
        </div>
        <IonButton
          expand="block"
          :disabled="saving || !connectionForm.name || !connectionForm.base_url"
          @click="saveConnection"
          >保存并同步</IonButton
        >
      </section>
    </div>
    <div v-if="modelOpen" class="mask" @click.self="modelOpen = false">
      <section>
        <header>
          <b>模型设置</b><button @click="modelOpen = false">关闭</button>
        </header>
        <label
          >模型连接<select
            v-model="modelForm.connection_id"
            :disabled="Boolean(modelForm.id)"
          >
            <option value="">请选择连接</option>
            <option
              v-for="item in connections.filter((row) => row.enabled)"
              :key="item.id"
              :value="item.id"
            >
              {{ item.name }}
            </option>
          </select></label
        >
        <label>显示名称<input v-model="modelForm.name" /></label>
        <label
          >模型描述<textarea
            v-model="modelForm.description"
            rows="3"
            placeholder="说明模型用途与适用场景"
          ></textarea>
        </label>
        <label
          >标签（每行一个）<textarea
            :value="list(modelForm.tags).join('\n')"
            rows="3"
            placeholder="例如：推理、低成本"
            @input="
              modelForm.tags = ($event.target as HTMLTextAreaElement).value
                .split('\n')
                .map((v) => v.trim())
                .filter(Boolean)
            "
          ></textarea>
        </label>
        <label
          >基础模型<input
            v-model="modelForm.base_model"
            :disabled="Boolean(modelForm.id)" /></label
        ><label
          >模型类型<select v-model="modelForm.model_type">
            <option value="chat">对话</option>
            <option value="image">生图</option>
            <option value="embedding">嵌入</option>
            <option value="audio">音频</option>
          </select></label
        >
        <div class="grid">
          <label
            >输入价 / 百万 Token<input
              v-model.number="modelForm.input_price"
              type="number"
              min="0"
              step=".01" /></label
          ><label
            >输出价 / 百万 Token<input
              v-model.number="modelForm.output_price"
              type="number"
              min="0"
              step=".01"
          /></label>
        </div>
        <div v-if="modelForm.model_type === 'chat'" class="grid">
          <label
            >温度<input
              v-model.number="modelForm.temperature"
              type="number"
              min="0"
              max="2"
              step=".1" /></label
          ><label
            >Top P<input
              v-model.number="modelForm.top_p"
              type="number"
              min="0"
              max="1"
              step=".1"
          /></label>
        </div>
        <label v-if="modelForm.model_type === 'chat'"
          >最大输出<input
            v-model.number="modelForm.max_tokens"
            type="number" /></label
        ><label v-if="modelForm.model_type === 'chat'"
          >系统提示词<textarea
            v-model="modelForm.system_prompt"
            rows="5"
          ></textarea>
        </label>
        <label
          >排序<input v-model.number="modelForm.sort_order" type="number"
        /></label>
        <fieldset class="capability-picker">
          <legend>模型能力</legend>
          <label
            v-for="item in [
              { id: 'chat', name: '对话' },
              { id: 'vision', name: '视觉' },
              { id: 'tools', name: '工具调用' },
              { id: 'json', name: '结构化输出' },
              { id: 'reasoning', name: '推理' },
            ]"
            :key="item.id"
          >
            <input
              v-model="modelForm.capabilities"
              type="checkbox"
              :value="item.id"
            />{{ item.name }}
          </label>
        </fieldset>
        <label
          >访问范围<select v-model="modelForm.access">
            <option value="private">仅自己</option>
            <option value="shared">指定用户</option>
            <option value="public">工作区公开</option>
          </select></label
        >
        <label v-if="modelForm.access === 'shared'"
          >授权用户 ID（逗号分隔）<input
            :value="
              Array.isArray(modelForm.access_grants)
                ? modelForm.access_grants.join(', ')
                : modelForm.access_grants || ''
            "
            @input="
              modelForm.access_grants = (
                $event.target as HTMLInputElement
              ).value
                .split(',')
                .map((v) => v.trim())
                .filter(Boolean)
            "
        /></label>
        <label
          >Filters（每行一个）<textarea
            :value="list(modelForm.filters).join('\n')"
            rows="3"
            placeholder="请求前后处理器名称"
            @input="
              modelForm.filters = ($event.target as HTMLTextAreaElement).value
                .split('\n')
                .map((v) => v.trim())
                .filter(Boolean)
            "
          ></textarea>
        </label>
        <label
          >Actions（每行一个）<textarea
            :value="list(modelForm.actions).join('\n')"
            rows="3"
            placeholder="模型动作名称"
            @input="
              modelForm.actions = ($event.target as HTMLTextAreaElement).value
                .split('\n')
                .map((v) => v.trim())
                .filter(Boolean)
            "
          ></textarea>
        </label>
        <label
          >绑定知识库<select v-model="modelForm.knowledge_id">
            <option value="">不绑定</option>
            <option v-for="item in knowledge" :key="item.id" :value="item.id">
              {{ item.name }}
            </option>
          </select></label
        >
        <label
          >Skills<select
            multiple
            :value="list(modelForm.skill_ids)"
            @change="setList('skill_ids', $event)"
          >
            <option v-for="item in skills" :key="item.id" :value="item.id">
              {{ item.name }}
            </option>
          </select></label
        >
        <label
          >Tools<select
            multiple
            :value="list(modelForm.tool_ids)"
            @change="setList('tool_ids', $event)"
          >
            <option v-for="item in tools" :key="item.id" :value="item.id">
              {{ item.name }}
            </option>
          </select></label
        >
        <div class="checks">
          <label
            ><input
              v-model="modelForm.enabled"
              type="checkbox"
              :true-value="1"
              :false-value="0"
            />启用</label
          ><label
            ><input
              v-model="modelForm.pinned"
              type="checkbox"
              :true-value="1"
              :false-value="0"
            />置顶</label
          ><label
            ><input
              v-model="modelForm.is_default"
              type="checkbox"
              :true-value="1"
              :false-value="0"
            />默认</label
          ><label
            ><input
              v-model="modelForm.hidden"
              type="checkbox"
              :true-value="1"
              :false-value="0"
            />隐藏</label
          >
        </div>
        <div v-if="modelForm.id" class="sheet-actions model-sheet-actions">
          <IonButton fill="outline" @click="duplicateCurrentModel"
            >复制模型</IonButton
          >
          <IonButton color="danger" fill="outline" @click="removeCurrentModel"
            >删除模型</IonButton
          >
        </div>
        <IonButton
          expand="block"
          :disabled="
            saving ||
            !modelForm.name.trim() ||
            !modelForm.base_model.trim() ||
            !modelForm.connection_id
          "
          @click="saveModel"
          >保存设置</IonButton
        >
      </section>
    </div></IonPage
  >
</template>
<style scoped>
main {
  padding: 12px 12px 28px;
}
.pager {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 7px;
  margin-top: 10px;
  color: var(--app-muted);
  font-size: 11px;
}
.pager span {
  margin-right: auto;
}
.pager select,
.pager button,
.toolbar > select,
.tool-icon {
  height: 34px;
  border: 1px solid var(--app-line);
  border-radius: 6px;
  color: var(--app-text);
  background: var(--app-card);
}
.pager button:disabled {
  opacity: 0.35;
}
.tool-icon {
  width: 34px;
  display: grid;
  place-items: center;
  color: #1677ff;
}
.tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  padding: 3px;
  border-radius: 7px;
  background: var(--ion-background-color);
}
.tabs button {
  height: 36px;
  border: 0;
  border-radius: 5px;
  color: var(--app-muted);
  background: transparent;
}
.tabs .active {
  color: #1677ff;
  background: var(--app-card);
  box-shadow: 0 1px 5px #0001;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  margin: 12px 0;
}
.toolbar label {
  height: 40px;
  display: flex;
  flex: 1 0 100%;
  order: -1;
  align-items: center;
  gap: 7px;
  padding: 0 10px;
  border: 1px solid var(--app-line);
  border-radius: 7px;
  background: var(--app-card);
}
.toolbar > select {
  width: auto;
  min-width: 94px;
  height: 36px;
}
.toolbar ion-button {
  margin: 0;
  white-space: nowrap;
}
input,
select,
textarea {
  width: 100%;
  border: 1px solid var(--app-line);
  border-radius: 6px;
  color: var(--app-text);
  background: var(--ion-background-color);
  font: inherit;
}
.toolbar input {
  height: 36px;
  border: 0;
  background: transparent;
  outline: 0;
}
article {
  min-height: 68px;
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr) repeat(4, 30px);
  align-items: center;
  gap: 7px;
  margin-bottom: 8px;
  padding: 9px;
  border: 1px solid var(--app-line);
  border-radius: 8px;
  background: var(--app-card);
}
article.connection {
  grid-template-columns: 36px minmax(0, 1fr) repeat(5, 28px);
}
article.disabled {
  opacity: 0.5;
}
.mark {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 6px;
  color: #fff;
  background: #1677ff;
  font-size: 11px;
  font-weight: 700;
}
.mark img,
.provider-picker i img {
  width: 72%;
  height: 72%;
  object-fit: contain;
}
article > div {
  display: grid;
  min-width: 0;
}
article b,
article small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
article b {
  font-size: 13px;
}
article em {
  color: #1677ff;
  font-size: 9px;
  font-style: normal;
}
article small {
  margin-top: 3px;
  color: var(--app-muted);
  font-size: 9px;
}
article > button {
  width: 30px;
  height: 32px;
  border: 0;
  color: var(--app-muted);
  background: transparent;
  font-size: 16px;
}
.danger {
  color: #ef4444 !important;
}
.empty {
  padding: 48px;
  text-align: center;
  color: var(--app-muted);
}
.mask {
  position: fixed;
  z-index: 1100;
  inset: 0;
  display: flex;
  align-items: flex-end;
  background: #0f172a66;
}
.mask > section {
  width: 100%;
  max-height: 86vh;
  overflow: auto;
  padding: 14px 14px calc(20px + env(safe-area-inset-bottom));
  border-radius: 8px 8px 0 0;
  background: var(--app-card);
}
section header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}
section header button {
  border: 0;
  color: var(--app-muted);
  background: transparent;
}
section > label,
.grid label {
  display: grid;
  gap: 6px;
  margin-bottom: 11px;
  color: var(--app-muted);
  font-size: 11px;
}
section input,
section select {
  height: 40px;
  padding: 0 10px;
}
section textarea {
  padding: 9px;
}
section select[multiple] {
  height: auto;
  min-height: 104px;
  padding: 6px;
}
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.checks {
  display: flex;
  gap: 15px;
  margin: 10px 0 16px;
}
.checks label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
}
.checks input {
  width: 17px;
  height: 17px;
}
.provider-picker {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px;
  max-height: 220px;
  overflow: auto;
  margin-bottom: 14px;
  padding: 2px;
}
.provider-picker button {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  height: 44px;
  padding: 5px 7px;
  border: 1px solid var(--app-line);
  border-radius: 7px;
  background: var(--ion-background-color);
  color: var(--app-text);
  text-align: left;
}
.provider-picker button.active {
  border-color: #1677ff;
  background: #eff6ff;
}
.provider-picker i {
  display: grid;
  place-items: center;
  width: 27px;
  height: 27px;
  flex: 0 0 27px;
  border-radius: 6px;
  color: #fff;
  font-size: 8px;
  font-style: normal;
  font-weight: 800;
  letter-spacing: 0;
}
.provider-picker span {
  overflow: hidden;
  font-size: 10px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
<style scoped>
.model-quick-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-top: 12px;
}
.model-quick-actions button {
  min-width: 0;
  min-height: 74px;
  display: grid;
  grid-template-rows: 24px auto;
  place-items: center;
  gap: 5px;
  padding: 10px 5px;
  border: 0;
  border-right: 1px solid var(--app-line);
  color: var(--app-blue);
  background: transparent;
}
.model-quick-actions button:last-child {
  border-right: 0;
}
.model-quick-actions button:disabled {
  opacity: 0.45;
}
.model-quick-actions ion-icon,
.model-quick-actions ion-spinner {
  font-size: 22px;
}
.model-quick-actions span,
.model-quick-actions b,
.model-quick-actions small {
  min-width: 0;
  display: block;
  text-align: center;
}
.model-quick-actions b {
  color: var(--app-text);
  font-size: 12px;
}
.model-quick-actions small {
  margin-top: 3px;
  overflow: hidden;
  color: var(--app-muted);
  font-size: 9px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.capability-picker {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 4px 0 12px;
  padding: 12px;
  border: 1px solid var(--app-line);
  border-radius: 12px;
}
.capability-picker legend {
  padding: 0 5px;
  color: var(--app-muted);
  font-size: 11px;
}
.capability-picker label {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 7px;
  min-height: 34px;
  color: var(--app-text);
  font-size: 12px;
}
.capability-picker input {
  width: 18px;
  height: 18px;
  flex: none;
}

main {
  padding: 12px 14px 92px;
}
.tabs {
  padding: 3px;
  border-radius: 12px;
  background: var(--app-card);
}
.tabs button {
  height: 40px;
  border-radius: 10px;
}
.tabs .active {
  color: var(--app-blue);
  background: color-mix(in srgb, var(--app-blue) 10%, var(--app-card));
  box-shadow: none;
}
.toolbar {
  gap: 7px;
  margin: 12px 0;
  padding: 10px;
  border-radius: 14px;
  background: var(--app-card);
}
.toolbar label {
  height: 42px;
  border: 0;
  border-radius: 12px;
  background: var(--ion-background-color);
}
.toolbar > ion-button {
  display: none;
}
.toolbar > select,
.tool-icon {
  height: 38px;
  border: 0;
  border-radius: 10px;
  background: var(--ion-background-color);
}
.tool-icon {
  width: 38px;
  color: var(--app-blue);
}
article,
article.connection {
  min-height: 66px;
  grid-template-columns: 42px minmax(0, 1fr) 38px 16px;
  gap: 9px;
  margin: 0;
  padding: 10px 12px;
  border: 0;
  border-bottom: 1px solid var(--app-line);
  border-radius: 0;
  background: var(--app-card);
  cursor: pointer;
}
article:first-of-type {
  border-radius: 14px 14px 0 0;
}
article:last-of-type {
  border-bottom: 0;
  border-radius: 0 0 14px 14px;
}
article.disabled {
  opacity: 0.58;
}
.mark {
  width: 40px;
  height: 40px;
  border-radius: 11px;
}
article > button {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  color: var(--app-blue);
  background: color-mix(in srgb, var(--app-blue) 9%, var(--app-card));
}
.row-arrow {
  color: var(--app-muted);
  font-size: 22px;
}
.pager {
  display: none;
}
.mask > section {
  max-height: 92vh;
  padding: 14px 14px calc(22px + env(safe-area-inset-bottom));
  border-radius: 14px 14px 0 0;
  background: var(--ion-background-color);
}
.mask section > header {
  position: sticky;
  top: -14px;
  z-index: 2;
  min-height: 52px;
  align-items: center;
  margin: -14px -14px 12px;
  padding: 8px 14px;
  border-bottom: 1px solid var(--app-line);
  background: var(--app-card);
}
.mask section > header b {
  font-size: 17px;
}
.mask section > header button {
  min-height: 38px;
  color: var(--app-blue);
}
.mask section > label,
.mask .grid,
.mask .checks,
.mask .capability-picker {
  padding: 12px;
  border: 0;
  border-radius: 12px;
  background: var(--app-card);
}
.mask section > label,
.grid label {
  margin-bottom: 8px;
}
.mask section input,
.mask section select,
.mask section textarea {
  border: 0;
  border-radius: 10px;
  background: var(--ion-background-color);
}
.provider-picker {
  border-radius: 14px;
  background: var(--app-card);
}
.sheet-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin: 12px 0;
}
.model-sheet-actions {
  grid-template-columns: 1fr 1fr;
}
.sheet-actions ion-button {
  min-width: 0;
  height: 48px;
  margin: 0;
  --border-radius: 12px;
}

/* Match the native App touch rhythm: large targets, quiet labels, and a clear primary action. */
main {
  padding: 14px 14px 96px;
}
.tabs {
  min-height: 48px;
  padding: 4px;
}
.tabs button {
  min-height: 40px;
  padding: 0 14px;
  font-size: 13px;
}
.model-quick-actions {
  min-height: 96px;
  margin-top: 14px;
  border-radius: 14px;
  box-shadow: 0 5px 18px rgba(15, 23, 42, 0.04);
}
.model-quick-actions button {
  min-height: 96px;
  grid-template-rows: 32px auto;
  gap: 7px;
  padding: 14px 8px;
  font-size: 12px;
}
.model-quick-actions ion-icon,
.model-quick-actions ion-spinner {
  width: 28px;
  height: 28px;
  font-size: 28px;
}
.model-quick-actions b {
  font-size: 13px;
  font-weight: 700;
}
.model-quick-actions small {
  font-size: 10px;
}
.toolbar {
  min-height: 52px;
  margin: 14px 0 10px;
  padding: 4px 8px 4px 14px;
  border-radius: 14px;
}
.toolbar > ion-button {
  display: inline-flex;
  min-height: 44px;
  margin: 0;
  --border-radius: 12px;
}
article,
article.connection {
  min-height: 76px;
  grid-template-columns: 44px minmax(0, 1fr) 44px 22px;
  gap: 11px;
  padding: 12px 14px;
}
.mark {
  width: 44px;
  height: 44px;
  border-radius: 13px;
}
article > button {
  width: 44px;
  height: 44px;
  font-size: 19px;
}
.row-arrow {
  display: grid;
  width: 22px;
  height: 44px;
  place-items: center;
  font-size: 25px;
}
.mask > section {
  padding: 16px 14px calc(24px + env(safe-area-inset-bottom));
}
.mask section > header {
  min-height: 56px;
  margin: -16px -14px 14px;
  padding: 8px 14px;
}
.mask section > header b {
  font-size: 18px;
}
.mask section > header button {
  min-width: 72px;
  min-height: 42px;
  padding: 0 12px;
  border: 1px solid var(--app-line);
  border-radius: 12px;
  background: var(--app-card);
  font-size: 13px;
}
.mask section input,
.mask section select {
  min-height: 46px;
  padding-inline: 13px;
  font-size: 14px;
}
.mask section textarea {
  min-height: 88px;
  padding: 12px 13px;
  font-size: 14px;
}
.provider-picker button {
  min-height: 52px;
  padding: 7px 9px;
  border-radius: 12px;
  font-size: 12px;
}
.provider-picker i {
  width: 32px;
  height: 32px;
  flex-basis: 32px;
  border-radius: 9px;
  font-size: 9px;
}
.sheet-actions {
  gap: 9px;
  margin: 14px 0;
}
.sheet-actions ion-button {
  height: 50px;
  --border-radius: 13px;
  font-size: 13px;
}
.mask section > ion-button[expand="block"] {
  min-height: 50px;
  margin-top: 14px;
  --border-radius: 13px;
  font-size: 14px;
  font-weight: 700;
}

/* New native App surface. The legacy desktop controls remain only for compatibility
   with the existing editor state and are removed from the mobile layout. */
main > .tabs,
main > .model-quick-actions,
main > .toolbar,
main > article,
main > .pager,
main > .empty {
  display: none !important;
}
.native-redesign {
  display: grid;
  gap: 14px;
}
.app-overview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 92px;
  padding: 18px;
  border-radius: 16px;
  color: var(--app-text);
  background: var(--app-card);
}
.app-overview small {
  color: var(--app-muted);
  font-size: 10px;
}
.app-overview h1 {
  margin: 5px 0 3px;
  font-size: 22px;
}
.app-overview p {
  margin: 0;
  color: var(--app-muted);
  font-size: 11px;
}
.app-overview > span {
  display: grid;
  place-items: center;
  min-width: 66px;
  min-height: 66px;
  border-radius: 18px;
  color: var(--app-blue);
  background: color-mix(in srgb, var(--app-blue) 10%, var(--app-card));
}
.app-overview > span b {
  font-size: 23px;
}
.app-overview > span small {
  color: inherit;
}
.app-action-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  padding: 14px 8px;
  border-radius: 16px;
  background: var(--app-card);
}
.app-action-grid button {
  display: grid;
  justify-items: center;
  gap: 7px;
  min-width: 0;
  min-height: 76px;
  padding: 6px 2px;
  border: 0;
  color: var(--app-text);
  background: transparent;
}
.app-action-grid button:disabled {
  opacity: 0.4;
}
.app-action-grid i {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  border-radius: 14px;
  color: var(--app-blue);
  background: color-mix(in srgb, var(--app-blue) 11%, var(--app-card));
  font-style: normal;
}
.app-action-grid ion-icon,
.app-action-grid ion-spinner {
  font-size: 23px;
}
.app-action-grid b {
  overflow: hidden;
  max-width: 100%;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.app-segments {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  padding: 4px;
  border-radius: 13px;
  background: color-mix(in srgb, var(--app-line) 52%, var(--app-card));
}
.app-segments button {
  min-height: 42px;
  border: 0;
  border-radius: 10px;
  color: var(--app-muted);
  background: transparent;
  font-size: 13px;
}
.app-segments button.active {
  color: var(--app-blue);
  background: var(--app-card);
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
  font-weight: 700;
}
.app-segments span {
  margin-left: 3px;
  font-size: 11px;
}
.app-search {
  display: flex;
  align-items: center;
  gap: 9px;
  min-height: 48px;
  padding: 0 10px 0 14px;
  border-radius: 14px;
  background: var(--app-card);
}
.app-search > ion-icon {
  color: var(--app-muted);
  font-size: 20px;
}
.app-search input {
  min-width: 0;
  flex: 1;
  border: 0;
  outline: 0;
  color: var(--app-text);
  background: transparent;
  font-size: 13px;
}
.app-search button,
.app-section-title button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: 40px;
  padding: 0 12px;
  border: 0;
  border-radius: 11px;
  color: var(--app-blue);
  background: color-mix(in srgb, var(--app-blue) 10%, var(--app-card));
  font-size: 12px;
  font-weight: 700;
}
.app-search button {
  width: 40px;
  padding: 0;
}
.app-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 2px 2px -3px;
}
.app-section-title h2 {
  margin: 0;
  font-size: 16px;
}
.app-section-title small {
  display: block;
  margin-top: 3px;
  color: var(--app-muted);
  font-size: 10px;
}
.app-list {
  overflow: hidden;
  border-radius: 16px;
  background: var(--app-card);
}
.app-list-row {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr) auto 42px 16px;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 78px;
  padding: 12px 13px;
  border: 0;
  border-bottom: 1px solid var(--app-line);
  color: var(--app-text);
  background: transparent;
  text-align: left;
}
.app-list-row:last-child {
  border-bottom: 0;
}
.app-list-row:active,
.app-action-grid button:active,
.app-section-title button:active {
  background: var(--app-soft);
  transform: scale(0.985);
}
.app-list-row.disabled {
  opacity: 0.58;
}
.provider-mark {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  overflow: hidden;
  border-radius: 13px;
  color: #fff;
  font-size: 10px;
  font-style: normal;
  font-weight: 800;
}
.provider-mark img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.row-content {
  display: grid;
  min-width: 0;
  gap: 3px;
}
.row-content strong,
.row-content small,
.row-content em {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row-content strong {
  font-size: 13px;
}
.row-content small,
.row-content em {
  color: var(--app-muted);
  font-size: 10px;
  font-style: normal;
}
.default-badge {
  padding: 4px 6px;
  border-radius: 6px;
  color: var(--app-blue);
  background: #eaf3ff;
  font-size: 9px;
}
.state-button {
  display: grid;
  place-items: center;
  width: 42px;
  height: 30px;
  border: 0;
  border-radius: 99px;
  color: #94a3b8;
  background: #e2e8f0;
}
.state-button.on {
  color: #fff;
  background: var(--app-blue);
}
.state-button ion-icon {
  font-size: 17px;
}
.native-chevron {
  color: var(--app-muted);
  font-size: 24px;
  text-align: right;
}
.app-empty {
  display: grid;
  justify-items: center;
  gap: 8px;
  padding: 42px 20px;
  border-radius: 16px;
  color: var(--app-muted);
  background: var(--app-card);
  text-align: center;
}
.app-empty > ion-icon {
  color: var(--app-blue);
  font-size: 30px;
}
.app-empty b {
  color: var(--app-text);
  font-size: 14px;
}
.app-empty p {
  margin: 0;
  font-size: 11px;
}
.app-empty button {
  min-height: 44px;
  margin-top: 5px;
  padding: 0 18px;
  border: 0;
  border-radius: 12px;
  color: #fff;
  background: var(--app-blue);
  font-size: 13px;
  font-weight: 700;
}
</style>
