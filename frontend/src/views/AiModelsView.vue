<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import AiResourcesView from "./AiResourcesView.vue";
import {
  aiProviderPresets,
  modelProviderPreset,
  providerLogoBackground,
  providerPreset,
} from "../utils/aiProviders";

type Item = Record<string, any>;
const router = useRouter();
const authStore = useAuthStore();
const tab = ref("models");
type WorkspaceSection = "core" | "prompts" | "skills" | "tools" | "notes" | "shares";
const workspaceSection = ref<WorkspaceSection>("core");
const resourceSections = ["prompts", "skills", "tools", "notes", "shares"] as const;
function selectCoreTab(value: "models" | "connections") {
  workspaceSection.value = "core";
  tab.value = value;
}
const loading = ref(false);
const models = ref<Item[]>([]);
const connections = ref<Item[]>([]);
const knowledge = ref<Item[]>([]);
const skills = ref<Item[]>([]);
const tools = ref<Item[]>([]);
const search = ref("");
const filter = ref("");
const connectionDialog = ref(false);
const editingConnection = ref<Item | null>(null);
const modelDialog = ref(false);
const modelForm = ref<Item>({});
const view = ref("all");
const page = ref(1);
const pageSize = ref(10);
const connectionPage = ref(1);
const connectionPageSize = ref(10);
const importInput = ref<HTMLInputElement | null>(null);
const form = ref({
  id: "",
  name: "OpenAI",
  base_url: "https://api.openai.com/v1",
  api_key: "",
  provider_type: "openai",
  provider_id: "openai",
  purpose: "general",
  enabled: true,
});
const purposeLabels: Record<string, string> = {
  general: "通用",
  chat: "对话",
  image: "图片生成",
  audio: "语音",
};
function connectionProvider(c: Item) {
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
const api = async <T = any,>(path: string, init?: RequestInit) => {
  const r = await fetch(`/ai-api/${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Workspace-User": String(authStore.currentUser?.id || "local"),
      "X-Workspace-Role": String(authStore.currentUser?.role || "user"),
    },
    ...init,
  });
  const d = await r.json();
  if (!r.ok) throw new Error(d.error || `请求失败 (${r.status})`);
  return d as T;
};
async function load() {
  loading.value = true;
  try {
    const [m, c, k, s, t] = await Promise.all([
      api<{ models: Item[] }>("models"),
      api<{ connections: Item[] }>("connections"),
      api<{ knowledge: Item[] }>("knowledge"),
      api<{ skills: Item[] }>("skills"),
      api<{ tools: Item[] }>("tools"),
    ]);
    models.value = m.models || [];
    connections.value = c.connections || [];
    knowledge.value = k.knowledge || [];
    skills.value = s.skills || [];
    tools.value = t.tools || [];
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "加载失败");
  } finally {
    loading.value = false;
  }
}
const filtered = computed(() =>
  models.value
    .filter(
      (m) =>
        (!search.value ||
          `${m.name} ${m.base_model} ${m.tags}`
            .toLowerCase()
            .includes(search.value.toLowerCase())) &&
        (!filter.value || m.connection_id === filter.value) &&
        (view.value === "all" ||
          (view.value === "enabled" && m.enabled !== 0) ||
          (view.value === "disabled" && m.enabled === 0) ||
          (view.value === "hidden" && m.hidden !== 0) ||
          (view.value === "pinned" && m.pinned !== 0) ||
          (view.value === "default" && m.is_default !== 0)),
    )
    .sort(
      (a, b) =>
        (b.pinned || 0) - (a.pinned || 0) ||
        (a.sort_order || 0) - (b.sort_order || 0),
    ),
);
const paginatedModels = computed(() =>
  filtered.value.slice(
    (page.value - 1) * pageSize.value,
    page.value * pageSize.value,
  ),
);
watch([search, filter, view, pageSize], () => {
  page.value = 1;
});
watch(
  () => filtered.value.length,
  (total) => {
    page.value = Math.min(
      page.value,
      Math.max(1, Math.ceil(total / pageSize.value)),
    );
  },
);
const paginatedConnections = computed(() =>
  connections.value.slice(
    (connectionPage.value - 1) * connectionPageSize.value,
    connectionPage.value * connectionPageSize.value,
  ),
);
watch(connectionPageSize, () => {
  connectionPage.value = 1;
});
watch(
  () => connections.value.length,
  (total) => {
    connectionPage.value = Math.min(
      connectionPage.value,
      Math.max(1, Math.ceil(total / connectionPageSize.value)),
    );
  },
);
async function toggle(m: Item) {
  const old = m.enabled;
  m.enabled = old === 0 ? 1 : 0;
  try {
    await api("models/update", {
      method: "POST",
      body: JSON.stringify({ ...m, enabled: m.enabled }),
    });
  } catch {
    m.enabled = old;
    ElMessage.error("更新失败");
  }
}
function openModel(m: Item) {
  const parse = (v: any) => (Array.isArray(v) ? v : JSON.parse(v || "[]"));
  modelForm.value = {
    ...m,
    tags: parse(m.tags),
    capabilities: parse(m.capabilities),
    skill_ids: parse(m.skill_ids),
    tool_ids: parse(m.tool_ids),
    access_grants_text: parse(m.access_grants).join(", "),
    filters_text: parse(m.filters).join("\n"),
    actions_text: parse(m.actions).join("\n"),
  };
  modelDialog.value = true;
}
function newModel() {
  modelForm.value = {
    name: "",
    base_model: "",
    model_type: "chat",
    description: "",
    system_prompt: "",
    temperature: 0.7,
    top_p: 1,
    max_tokens: 2048,
    input_price: 0,
    output_price: 0,
    knowledge_id: "",
    skill_ids: [],
    tool_ids: [],
    tags: [],
    capabilities: ["chat"],
    enabled: 1,
    hidden: 0,
    pinned: 0,
    is_default: 0,
    access: "private",
    access_grants_text: "",
    filters_text: "",
    actions_text: "",
    sort_order: 0,
  };
  modelDialog.value = true;
}
function duplicateModel() {
  const source = { ...modelForm.value };
  delete source.id;
  source.name = `${source.name} 副本`;
  source.is_default = 0;
  modelForm.value = source;
  ElMessage.info("已创建副本草稿，保存后生效");
}
function selectBaseModel(baseModel: string) {
  const source = models.value.find(
    (m) => m.base_model === baseModel && m.connection_id,
  );
  modelForm.value.connection_id = source?.connection_id || "";
  if (!modelForm.value.name) modelForm.value.name = baseModel;
}
async function saveModel() {
  try {
    const payload = {
      ...modelForm.value,
      access_grants: String(modelForm.value.access_grants_text || "")
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean),
      filters: String(modelForm.value.filters_text || "")
        .split("\n")
        .map((v) => v.trim())
        .filter(Boolean),
      actions: String(modelForm.value.actions_text || "")
        .split("\n")
        .map((v) => v.trim())
        .filter(Boolean),
    };
    await api(modelForm.value.id ? "models/update" : "models", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    modelDialog.value = false;
    await load();
    ElMessage.success(
      modelForm.value.id ? "模型设置已保存" : "工作区模型已创建",
    );
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "保存失败");
  }
}
async function deleteModel() {
  const m = modelForm.value;
  const confirmed = await ElMessageBox.confirm(
    `确定删除“${m.name}”吗？同步供应商时可能再次发现这个基础模型。`,
    "删除模型",
    { type: "warning" },
  )
    .then(() => true)
    .catch(() => false);
  if (!confirmed) return;
  try {
    await api("models/delete", {
      method: "POST",
      body: JSON.stringify({ id: m.id }),
    });
    modelDialog.value = false;
    await load();
    ElMessage.success("模型已删除");
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "删除失败");
  }
}
async function removeModel(m: Item) {
  const confirmed = await ElMessageBox.confirm(
    `确定删除“${m.name}”吗？供应商同步时可能再次出现。`,
    "删除模型",
    { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" },
  )
    .then(() => true)
    .catch(() => false);
  if (!confirmed) return;
  try {
    await api("models/delete", {
      method: "POST",
      body: JSON.stringify({ id: m.id }),
    });
    await load();
    ElMessage.success("模型已删除");
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "删除失败");
  }
}
async function updateMany(changes: Item, message: string) {
  loading.value = true;
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
    ElMessage.success(message);
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "批量更新失败");
  } finally {
    loading.value = false;
  }
}
function exportModels() {
  const blob = new Blob(
    [JSON.stringify({ version: 1, models: models.value }, null, 2)],
    { type: "application/json" },
  );
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `workspace-models-${new Date().toISOString().slice(0, 10)}.json`;
  link.click();
  URL.revokeObjectURL(url);
}
async function importModels(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  try {
    const payload = JSON.parse(await file.text());
    const items = Array.isArray(payload) ? payload : payload.models;
    if (!Array.isArray(items)) throw new Error("文件中没有模型数据");
    for (const item of items) {
      const current = models.value.find(
        (m) =>
          m.id === item.id ||
          (m.base_model === item.base_model &&
            m.connection_id === item.connection_id),
      );
      if (current)
        await api("models/update", {
          method: "POST",
          body: JSON.stringify({ ...current, ...item, id: current.id }),
        });
      else await api("models", { method: "POST", body: JSON.stringify(item) });
    }
    await load();
    ElMessage.success(`已导入 ${items.length} 个模型`);
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "导入失败");
  }
}
function selectProvider(id: string) {
  const preset = providerPreset(id);
  form.value.provider_id = preset.id;
  form.value.provider_type = preset.protocol;
  if (!editingConnection.value || !form.value.name)
    form.value.name = preset.name;
  if (preset.baseUrl) form.value.base_url = preset.baseUrl;
}
function openConnection(c?: Item) {
  editingConnection.value = c || null;
  form.value = {
    id: c?.id || "",
    name: c?.name || "OpenAI",
    base_url: c?.base_url || "https://api.openai.com/v1",
    api_key: "",
    provider_type: c?.provider_type || "openai",
    provider_id: c?.provider_id || "custom",
    purpose: c?.purpose || "general",
    enabled: c?.enabled !== 0,
  };
  connectionDialog.value = true;
}
async function saveConnection() {
  try {
    await api("connections/save", {
      method: "POST",
      body: JSON.stringify(form.value),
    });
    connectionDialog.value = false;
    await load();
    ElMessage.success("连接已保存并同步模型");
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "保存失败");
  }
}
async function testConnection(c: Item) {
  try {
    const d = await api("connections/test", {
      method: "POST",
      body: JSON.stringify({ id: c.id }),
    });
    ElMessage.success(d.message || "连接成功");
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "连接失败");
  }
}
async function removeConnection(c: Item) {
  await ElMessageBox.confirm(
    `确定删除“${c.name}”及其同步模型吗？`,
    "删除连接",
    { type: "warning" },
  ).catch(() => null);
  try {
    await api("connections/delete", {
      method: "POST",
      body: JSON.stringify({ id: c.id }),
    });
    await load();
    ElMessage.success("连接已删除");
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "删除失败");
  }
}
onMounted(load);
</script>
<template>
  <section class="models-page">
    <header class="page-header">
      <div>
        <span class="eyebrow">AI WORKSPACE</span>
        <h1>模型中心</h1>
        <p>连接供应商、同步模型并控制工作区可用模型</p>
      </div>
      <div class="actions">
        <el-button @click="router.push('/ai-workspace')">返回聊天</el-button
        ><template v-if="workspaceSection === 'core' && tab === 'models'"
          ><el-dropdown
            @command="
              (command: string) =>
                command === 'enable'
                  ? updateMany({ enabled: 1 }, '已批量启用模型')
                  : command === 'disable'
                    ? updateMany({ enabled: 0 }, '已批量禁用模型')
                    : command === 'show'
                      ? updateMany({ hidden: 0 }, '模型已显示')
                      : updateMany({ hidden: 1 }, '模型已隐藏')
            "
            ><el-button>批量操作</el-button
            ><template #dropdown
              ><el-dropdown-menu
                ><el-dropdown-item command="enable"
                  >启用当前筛选结果</el-dropdown-item
                ><el-dropdown-item command="disable"
                  >禁用当前筛选结果</el-dropdown-item
                ><el-dropdown-item command="show"
                  >显示当前筛选结果</el-dropdown-item
                ><el-dropdown-item command="hide"
                  >隐藏当前筛选结果</el-dropdown-item
                ></el-dropdown-menu
              ></template
            ></el-dropdown
          ><el-button @click="exportModels">导出</el-button
          ><el-button @click="importInput?.click()">导入</el-button
          ><input
            ref="importInput"
            hidden
            type="file"
            accept="application/json"
            @change="importModels"
          /><el-button type="primary" @click="newModel"
            >创建工作区模型</el-button
          ></template
        ><el-button v-else-if="workspaceSection === 'core'" type="primary" @click="openConnection()"
          >新增连接</el-button
        >
      </div>
    </header>
    <div class="tabs">
      <button :class="{ active: workspaceSection === 'core' && tab === 'models' }" @click="selectCoreTab('models')">
        模型 <b>{{ models.length }}</b></button
      ><button
        :class="{ active: workspaceSection === 'core' && tab === 'connections' }"
        @click="selectCoreTab('connections')"
      >
        连接 <b>{{ connections.length }}</b></button
      ><button :class="{ active: workspaceSection === 'prompts' }" @click="workspaceSection = 'prompts'">Prompts</button
      ><button :class="{ active: workspaceSection === 'skills' }" @click="workspaceSection = 'skills'">Skills</button
      ><button :class="{ active: workspaceSection === 'tools' }" @click="workspaceSection = 'tools'">Tools</button
      ><button :class="{ active: workspaceSection === 'notes' }" @click="workspaceSection = 'notes'">Notes</button
      ><button :class="{ active: workspaceSection === 'shares' }" @click="workspaceSection = 'shares'">分享管理</button>
    </div>
    <template v-if="workspaceSection === 'core' && tab === 'models'"
      ><div class="toolbar">
        <el-input
          v-model="search"
          clearable
          placeholder="搜索模型或标签"
        /><el-select v-model="filter" clearable placeholder="全部连接"
          ><el-option
            v-for="c in connections"
            :key="c.id"
            :label="c.name"
            :value="c.id" /></el-select
        ><el-select v-model="view"
          ><el-option label="全部模型" value="all" /><el-option
            label="已启用"
            value="enabled" /><el-option
            label="已禁用"
            value="disabled" /><el-option
            label="已隐藏"
            value="hidden" /><el-option
            label="已置顶"
            value="pinned" /><el-option
            label="默认模型"
            value="default" /></el-select
        ><el-button @click="load">刷新</el-button>
      </div>
      <div class="table">
        <div class="thead">
          <span>模型</span><span>连接</span><span>基础模型</span
          ><span>操作</span>
        </div>
        <div v-for="m in paginatedModels" :key="m.id" class="row">
          <div class="name">
            <i
              class="provider-logo"
              :style="{
                background: providerLogoBackground(
                  modelProviderPreset(
                    m.base_model,
                    connections.find((c) => c.id === m.connection_id)
                      ?.provider_id,
                  ),
                ),
              }"
              ><img
                v-if="
                  modelProviderPreset(
                    m.base_model,
                    connections.find((c) => c.id === m.connection_id)
                      ?.provider_id,
                  ).logo
                "
                :src="`/ui/ai-providers/${modelProviderPreset(m.base_model, connections.find((c) => c.id === m.connection_id)?.provider_id).logo}`"
                alt=""
              /><span v-else>{{
                modelProviderPreset(
                  m.base_model,
                  connections.find((c) => c.id === m.connection_id)
                    ?.provider_id,
                ).short
              }}</span></i
            ><span
              ><strong
                >{{ m.name }} <em v-if="m.is_default">默认</em
                ><em v-if="m.pinned">置顶</em
                ><em v-if="m.hidden">隐藏</em></strong
              ><small>{{ m.description || "同步模型" }}</small></span
            >
          </div>
          <span>{{
            connections.find((c) => c.id === m.connection_id)?.name ||
            "默认连接"
          }}</span
          ><code>{{ m.base_model }}</code>
          <div class="row-actions">
            <el-switch
              :model-value="m.enabled !== 0"
              @change="toggle(m)"
            /><el-button text @click="openModel(m)">编辑</el-button
            ><el-button text type="danger" @click="removeModel(m)"
              >删除</el-button
            >
          </div>
        </div>
        <div v-if="!filtered.length" class="empty">
          暂无模型，请先配置连接并同步
        </div>
        <div class="pagination-bar">
          <span>
            共 {{ filtered.length }} 条 · 第 {{ page }} /
            {{ Math.max(1, Math.ceil(filtered.length / pageSize)) }} 页
          </span>
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="filtered.length"
            layout="sizes, prev, pager, next"
            background
          />
        </div></div
    ></template>
    <template v-else-if="workspaceSection === 'core'"
      ><div class="connections">
        <article
          v-for="c in paginatedConnections"
          :key="c.id"
          class="connection"
        >
          <div
            class="provider-logo"
            :style="{
              background: providerLogoBackground(connectionProvider(c)),
            }"
          >
            <img
              v-if="connectionProvider(c).logo"
              :src="`/ui/ai-providers/${connectionProvider(c).logo}`"
              alt=""
            /><span v-else>{{ connectionProvider(c).short }}</span>
          </div>
          <div class="connection-main">
            <div class="connection-title">
              <strong>{{ c.name }}</strong
              ><span class="purpose-tag">{{
                purposeLabels[c.purpose] || "通用"
              }}</span
              ><span class="provider-tag">{{
                c.provider_type === "openai" ? "OpenAI 兼容" : c.provider_type
              }}</span>
            </div>
            <small>{{ c.base_url }}</small>
            <div class="connection-meta">
              <span
                >{{
                  models.filter((m) => m.connection_id === c.id).length
                }}
                个模型</span
              ><span v-if="c.key_fingerprint"
                >Key · {{ c.key_fingerprint }}</span
              ><span :class="['state-text', { off: c.enabled === 0 }]">{{
                c.enabled === 0 ? "已停用" : "已启用"
              }}</span>
            </div>
          </div>
          <el-switch
            :model-value="c.enabled !== 0"
            @change="
              async (v: boolean) => {
                await api('connections/toggle', {
                  method: 'POST',
                  body: JSON.stringify({ id: c.id, enabled: v }),
                });
                c.enabled = v ? 1 : 0;
                await load();
              }
            "
          /><el-button text @click="testConnection(c)">测试</el-button
          ><el-button text @click="openConnection(c)">编辑</el-button
          ><el-button text type="danger" @click="removeConnection(c)"
            >删除</el-button
          >
        </article>
        <div v-if="!connections.length" class="empty">暂无连接</div>
        <div class="pagination-bar">
          <span>
            共 {{ connections.length }} 条 · 第 {{ connectionPage }} /
            {{
              Math.max(1, Math.ceil(connections.length / connectionPageSize))
            }}
            页
          </span>
          <el-pagination
            v-model:current-page="connectionPage"
            v-model:page-size="connectionPageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="connections.length"
            layout="sizes, prev, pager, next"
            background
          />
        </div></div
    ></template>
    <AiResourcesView
      v-else
      embedded
      :initial-kind="workspaceSection as typeof resourceSections[number]"
    />
    <el-dialog
      v-model="connectionDialog"
      :title="editingConnection ? '编辑连接' : '新增连接'"
      width="660px"
      ><el-form label-position="top"
        ><el-form-item label="AI 平台"
          ><div class="provider-picker">
            <button
              v-for="preset in aiProviderPresets"
              :key="preset.id"
              type="button"
              :class="{ active: form.provider_id === preset.id }"
              @click="selectProvider(preset.id)"
            >
              <i :style="{ background: providerLogoBackground(preset) }"
                ><img
                  v-if="preset.logo"
                  :src="`/ui/ai-providers/${preset.logo}`"
                  alt=""
                /><span v-else>{{ preset.short }}</span></i
              ><span>{{ preset.name }}</span>
            </button>
          </div></el-form-item
        >
        <div class="form-grid">
          <el-form-item label="连接名称"
            ><el-input
              v-model="form.name"
              placeholder="例如：图片生成专用" /></el-form-item
          ><el-form-item label="主要用途"
            ><el-select v-model="form.purpose" style="width: 100%"
              ><el-option label="通用" value="general" /><el-option
                label="对话"
                value="chat" /><el-option
                label="图片生成"
                value="image" /><el-option
                label="语音"
                value="audio" /></el-select
          ></el-form-item>
        </div>
        <el-form-item label="API Base URL"
          ><el-input
            v-model="form.base_url"
            placeholder="https://api.openai.com/v1" /></el-form-item
        ><el-form-item label="API Key"
          ><el-input
            v-model="form.api_key"
            type="password"
            show-password
            placeholder="留空表示保持原密钥" /></el-form-item></el-form
      ><template #footer
        ><el-button @click="connectionDialog = false">取消</el-button
        ><el-button type="primary" @click="saveConnection"
          >保存并同步</el-button
        ></template
      ></el-dialog
    >
    <el-dialog v-model="modelDialog" title="编辑工作区模型" width="680px">
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="显示名称"
            ><el-input v-model="modelForm.name" /></el-form-item
          ><el-form-item label="基础模型"
            ><el-select
              v-if="!modelForm.id"
              v-model="modelForm.base_model"
              filterable
              placeholder="选择基础模型"
              style="width: 100%"
              @change="selectBaseModel"
              ><el-option
                v-for="item in models.filter((m) => m.connection_id)"
                :key="item.id"
                :label="`${item.name} · ${connections.find((c) => c.id === item.connection_id)?.name || ''}`"
                :value="item.base_model" /></el-select
            ><el-input v-else v-model="modelForm.base_model" disabled
          /></el-form-item>
        </div>
        <div class="form-grid">
          <el-form-item label="模型类型"
            ><el-select v-model="modelForm.model_type" style="width: 100%"
              ><el-option label="聊天 / Vision" value="chat" /><el-option
                label="图片生成"
                value="image" /><el-option
                label="Embedding"
                value="embedding" /><el-option
                label="语音"
                value="audio" /></el-select></el-form-item
          ><el-form-item label="计费单位"
            ><span class="price-note"
              >每百万 Token，图片和语音可留空</span
            ></el-form-item
          >
        </div>
        <div class="form-grid">
          <el-form-item label="输入价格"
            ><el-input-number
              v-model="modelForm.input_price"
              :min="0"
              :precision="6"
              :step="0.1" /></el-form-item
          ><el-form-item label="输出价格"
            ><el-input-number
              v-model="modelForm.output_price"
              :min="0"
              :precision="6"
              :step="0.1"
          /></el-form-item>
        </div>
        <el-form-item label="描述"
          ><el-input v-model="modelForm.description"
        /></el-form-item>
        <el-form-item label="系统提示词"
          ><el-input
            v-model="modelForm.system_prompt"
            type="textarea"
            :rows="5"
        /></el-form-item>
        <div class="form-grid three">
          <el-form-item label="Temperature"
            ><el-input-number
              v-model="modelForm.temperature"
              :min="0"
              :max="2"
              :step="0.1" /></el-form-item
          ><el-form-item label="Top P"
            ><el-input-number
              v-model="modelForm.top_p"
              :min="0"
              :max="1"
              :step="0.1" /></el-form-item
          ><el-form-item label="最大输出 Token"
            ><el-input-number
              v-model="modelForm.max_tokens"
              :min="1"
              :max="128000"
          /></el-form-item>
        </div>
        <el-form-item label="标签"
          ><el-select
            v-model="modelForm.tags"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入标签后回车"
            style="width: 100%"
        /></el-form-item>
        <div class="model-flags">
          <el-checkbox
            v-model="modelForm.enabled"
            :true-value="1"
            :false-value="0"
            >启用</el-checkbox
          ><el-checkbox
            v-model="modelForm.hidden"
            :true-value="1"
            :false-value="0"
            >从选择器隐藏</el-checkbox
          ><el-checkbox
            v-model="modelForm.pinned"
            :true-value="1"
            :false-value="0"
            >置顶</el-checkbox
          ><el-checkbox
            v-model="modelForm.is_default"
            :true-value="1"
            :false-value="0"
            >设为默认模型</el-checkbox
          >
        </div>
        <el-form-item label="模型能力"
          ><el-checkbox-group v-model="modelForm.capabilities"
            ><el-checkbox value="chat">对话</el-checkbox
            ><el-checkbox value="vision">图片理解</el-checkbox
            ><el-checkbox value="file_upload">文件上传</el-checkbox
            ><el-checkbox value="web_search">联网搜索</el-checkbox
            ><el-checkbox value="tool_calling">工具调用</el-checkbox
            ><el-checkbox value="code_interpreter"
              >代码执行</el-checkbox
            ></el-checkbox-group
          ></el-form-item
        >
        <div class="form-grid">
          <el-form-item label="访问范围"
            ><el-select v-model="modelForm.access" style="width: 100%"
              ><el-option label="私有" value="private" /><el-option
                label="公开"
                value="public" /><el-option
                label="指定用户"
                value="shared" /></el-select></el-form-item
          ><el-form-item label="排序"
            ><el-input-number
              v-model="modelForm.sort_order"
              :min="0"
              :max="9999"
          /></el-form-item>
        </div>
        <el-form-item
          v-if="modelForm.access === 'shared'"
          label="共享用户或角色"
          ><el-input
            v-model="modelForm.access_grants_text"
            placeholder="用逗号分隔用户 ID 或角色"
        /></el-form-item>
        <div class="form-grid">
          <el-form-item label="Filters（每行一个）"
            ><el-input
              v-model="modelForm.filters_text"
              type="textarea"
              :rows="3"
              placeholder="请求前后处理器名称" /></el-form-item
          ><el-form-item label="Actions（每行一个）"
            ><el-input
              v-model="modelForm.actions_text"
              type="textarea"
              :rows="3"
              placeholder="模型动作名称"
          /></el-form-item>
        </div>
        <el-divider content-position="left">模型能力</el-divider>
        <div class="form-grid">
          <el-form-item label="绑定知识库"
            ><el-select
              v-model="modelForm.knowledge_id"
              clearable
              placeholder="不绑定"
              style="width: 100%"
              ><el-option
                v-for="item in knowledge"
                :key="item.id"
                :label="item.name"
                :value="item.id" /></el-select></el-form-item
          ><el-form-item label="Skills"
            ><el-select
              v-model="modelForm.skill_ids"
              multiple
              collapse-tags
              placeholder="选择技能"
              style="width: 100%"
              ><el-option
                v-for="item in skills"
                :key="item.id"
                :label="item.name"
                :value="item.id" /></el-select
          ></el-form-item>
        </div>
        <el-form-item label="Tools"
          ><el-select
            v-model="modelForm.tool_ids"
            multiple
            collapse-tags
            placeholder="选择工具"
            style="width: 100%"
            ><el-option
              v-for="item in tools"
              :key="item.id"
              :label="item.name"
              :value="item.id" /></el-select
        ></el-form-item>
      </el-form>
      <template #footer
        ><el-button v-if="modelForm.id" type="danger" plain @click="deleteModel"
          >删除模型</el-button
        ><el-button v-if="modelForm.id" @click="duplicateModel"
          >复制模型</el-button
        ><el-button @click="modelDialog = false">取消</el-button
        ><el-button type="primary" @click="saveModel">{{
          modelForm.id ? "保存模型" : "创建模型"
        }}</el-button></template
      >
    </el-dialog>
  </section>
</template>
<style scoped>
.models-page {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: calc(100vh - 104px);
  min-height: 0;
  overflow: hidden;
  padding: 18px 10px;
  background: #fff;
}
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  width: 100%;
  margin: 0 0 18px;
}
.eyebrow {
  font-size: 10px;
  letter-spacing: 0.12em;
  color: var(--brand-primary);
  font-weight: 700;
}
.page-header h1 {
  margin: 7px 0 4px;
  font-size: 28px;
}
.page-header p {
  margin: 0;
  color: #64748b;
  font-size: 12px;
}
.actions {
  display: flex;
  gap: 8px;
}
.tabs {
  flex: none;
  width: 100%;
  margin: 0;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  overflow-x: auto;
  gap: 24px;
}
.tabs button {
  flex: none;
  padding: 12px 4px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: none;
  color: #64748b;
}
.tabs button.active {
  border-color: var(--brand-primary);
  color: var(--brand-primary);
}
.tabs b {
  margin-left: 5px;
  font-size: 10px;
}
.toolbar {
  flex: none;
  width: 100%;
  margin: 18px 0;
  display: flex;
  gap: 10px;
}
.toolbar .el-input {
  max-width: 420px;
}
.toolbar .el-select {
  width: 190px;
}
.table,
.connections {
  width: 100%;
  min-height: 0;
  margin: 0;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: auto;
}
.table {
  flex: 1;
}
.connections {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.connections .pagination-bar {
  margin-top: auto;
}
.thead {
  position: sticky;
  top: 0;
  z-index: 1;
}
.pagination-bar {
  position: sticky;
  bottom: 0;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border-top: 1px solid #e2e8f0;
  background: #fff;
}
.pagination-bar > span {
  color: #64748b;
  font-size: 11px;
}
.thead,
.row {
  display: grid;
  grid-template-columns: 2fr 1fr 1.5fr 130px;
  gap: 16px;
  align-items: center;
  padding: 13px 16px;
}
.thead {
  background: #f8fafc;
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
}
.row {
  min-height: 58px;
  border-top: 1px solid #edf0f4;
  font-size: 12px;
  color: #475569;
}
.name {
  display: flex;
  align-items: center;
  gap: 10px;
}
.name i {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 7px;
  background: var(--brand-primary);
  color: #fff;
  font-style: normal;
  font-size: 9px;
  font-weight: 700;
}
.name strong,
.name small {
  display: block;
}
.name em {
  margin-left: 5px;
  padding: 2px 4px;
  border-radius: 4px;
  background: #eef2ff;
  color: var(--brand-primary);
  font-size: 9px;
  font-style: normal;
}
.name small {
  margin-top: 3px;
  color: #94a3b8;
  font-size: 10px;
}
.row code {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #64748b;
}
.row-actions {
  display: flex;
  align-items: center;
  gap: 7px;
}
.connection {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  border-bottom: 1px solid #edf0f4;
}
.connection:last-child {
  border-bottom: 0;
}
.status {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #22c55e;
}
.status.off {
  background: #cbd5e1;
}
.connection-main {
  flex: 1;
}
.connection-main strong,
.connection-main small,
.connection-main span {
  display: block;
}
.connection-main small {
  margin: 4px 0;
  color: #64748b;
}
.connection-main span {
  color: #94a3b8;
  font-size: 11px;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.form-grid.three {
  grid-template-columns: repeat(3, 1fr);
}
.model-flags {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
}
.empty {
  padding: 60px;
  text-align: center;
  color: #94a3b8;
}
@media (max-width: 800px) {
  .models-page {
    height: calc(100vh - 80px);
    padding: 12px;
  }
  .page-header {
    display: block;
  }
  .actions {
    margin-top: 16px;
  }
  .toolbar {
    flex-wrap: wrap;
  }
  .pagination-bar {
    align-items: flex-start;
    flex-direction: column;
  }
  .pagination-bar .el-pagination {
    max-width: 100%;
    overflow: auto;
  }
  .thead {
    display: none;
  }
  .row {
    grid-template-columns: 1fr 110px;
  }
  .row > span,
  .row > code {
    display: none;
  }
  .connection {
    flex-wrap: wrap;
  }
  .form-grid,
  .form-grid.three {
    grid-template-columns: 1fr;
  }
}
.connection-index {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  border: 1px solid #dbe3ee;
  border-radius: 7px;
  background: #f8fafc;
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
}
.connection-main {
  min-width: 0;
}
.connection-title {
  display: flex;
  align-items: center;
  gap: 7px;
}
.connection-main .connection-title strong {
  font-size: 14px;
}
.connection-main > small {
  display: block;
  overflow: hidden;
  margin: 5px 0 7px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.purpose-tag,
.provider-tag {
  display: inline-flex !important;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px !important;
}
.purpose-tag {
  background: #eef2ff;
  color: #4f46e5 !important;
}
.provider-tag {
  background: #f1f5f9;
  color: #64748b !important;
  text-transform: capitalize;
}
.connection-meta {
  display: flex;
  gap: 14px;
}
.connection-main .connection-meta span {
  display: inline;
  color: #94a3b8;
  font-size: 11px;
}
.connection-main .connection-meta .state-text {
  color: #16a34a;
}
.connection-main .connection-meta .state-text.off {
  color: #94a3b8;
}
.provider-logo {
  display: grid !important;
  place-items: center;
  width: 38px !important;
  height: 38px !important;
  flex: 0 0 38px;
  border: 1px solid #e2e8f0 !important;
  border-radius: 7px !important;
  color: #fff !important;
  font-size: 10px !important;
  font-style: normal;
  font-weight: 800;
  letter-spacing: 0;
}
.provider-logo img,
.provider-picker i img {
  width: 72%;
  height: 72%;
  object-fit: contain;
}
.provider-picker {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 7px;
  max-height: 238px;
  overflow: auto;
  padding: 2px;
}
.provider-picker button {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  height: 45px;
  padding: 5px 7px;
  border: 1px solid #dbe3ee;
  border-radius: 7px;
  background: #fff;
  color: #334155;
  text-align: left;
  cursor: pointer;
}
.provider-picker button:hover {
  border-color: #818cf8;
  background: #f8faff;
}
.provider-picker button.active {
  border-color: #6366f1;
  background: #eef2ff;
  box-shadow: 0 0 0 1px #6366f1 inset;
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
  font-size: 11px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
@media (max-width: 720px) {
  .provider-picker {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
.thead,
.row {
  grid-template-columns: 2fr 1fr 1.5fr 180px;
}
</style>
