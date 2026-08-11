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
  createOutline,
  refreshOutline,
  searchOutline,
  trashOutline,
} from "ionicons/icons";
import PageHeader from "../components/PageHeader.vue";
import { session } from "../session";
type Kind = "prompts" | "skills" | "tools" | "notes";
type Item = {
  id: string;
  title?: string;
  command?: string;
  name?: string;
  description?: string;
  content?: string;
  kind?: string;
  enabled?: number;
  config?: Record<string, any> | string;
  headersText?: string;
  argumentsText?: string;
};
const tab = ref<Kind>("prompts"),
  items = ref<Record<Kind, Item[]>>({ prompts: [], skills: [], tools: [], notes: [] }),
  loading = ref(false),
  editorOpen = ref(false),
  saving = ref(false), search = ref(""), page = ref(1), pageSize = ref(10);
const form = ref<Item>({
  id: "",
  title: "",
  command: "",
  name: "",
  description: "",
  content: "",
  kind: "custom",
  enabled: 1,
});
const current = computed(() => items.value[tab.value]);
const filteredItems = computed(() => { const q=search.value.trim().toLowerCase(); return q ? current.value.filter(item => `${item.title||""} ${item.command||""} ${item.name||""} ${item.description||""} ${item.content||""}`.toLowerCase().includes(q)) : current.value; });
const visibleItems = computed(() => filteredItems.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value));
watch([tab, pageSize, search], () => { page.value = 1; });
watch(() => filteredItems.value.length, total => { page.value = Math.min(page.value, Math.max(1, Math.ceil(total / pageSize.value))); });
async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/ai-api/${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Workspace-User": String(session.user?.id || "local"),
      "X-Workspace-Role": session.user?.role || "user",
    },
    ...init,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(
      data.error || data.detail || `请求失败 (${response.status})`,
    );
  return data;
}
async function notify(message: string) {
  const toast = await toastController.create({ message, duration: 1800 });
  await toast.present();
}
async function load() {
  loading.value = true;
  try {
    const [p, s, t, n] = await Promise.all([
      api("prompts"),
      api("skills"),
      api("tools?all=1"),
      api("notes"),
    ]);
    items.value = {
      prompts: p.prompts || [],
      skills: s.skills || [],
      tools: t.tools || [],
      notes: n.notes || [],
    };
  } catch (error) {
    await notify(error instanceof Error ? error.message : "加载失败");
  } finally {
    loading.value = false;
  }
}
function openEditor(item?: Item) {
  let config: Record<string, any> = {
    method: "POST",
    url: "",
    headers: {},
    timeout: 15,
  };
  if (item?.config)
    try {
      config =
        typeof item.config === "string" ? JSON.parse(item.config) : item.config;
    } catch {}
  form.value = item
    ? {
        ...item,
        config,
        headersText: JSON.stringify(config.headers || {}, null, 2),
        argumentsText: "{}",
        enabled: item.enabled ?? 1,
      }
    : {
        id: "",
        title: "",
        command: "",
        name: "",
        description: "",
        content: "",
        kind: "custom",
        enabled: 1,
        config,
        headersText: "{}",
        argumentsText: "{}",
      };
  editorOpen.value = true;
}
function payload() {
  const value = { ...form.value };
  if (tab.value === "tools") {
    const config = { ...((value.config as Record<string, any>) || {}) };
    config.headers = JSON.parse(value.headersText || "{}");
    value.config = config;
  }
  delete value.headersText;
  delete value.argumentsText;
  return value;
}
async function saveItem() {
  saving.value = true;
  try {
    await api(form.value.id ? `${tab.value}/update` : tab.value, {
      method: "POST",
      body: JSON.stringify(payload()),
    });
    editorOpen.value = false;
    await load();
    await notify("已保存");
  } catch (error) {
    await notify(error instanceof Error ? error.message : "保存失败");
  } finally {
    saving.value = false;
  }
}
async function testTool() {
  try {
    const value = payload();
    const result = await api<{ result: string }>("tools/test", {
      method: "POST",
      body: JSON.stringify({
        ...value,
        arguments: JSON.parse(form.value.argumentsText || "{}"),
      }),
    });
    await notify(`测试成功：${result.result.slice(0, 120)}`);
  } catch (error) {
    await notify(error instanceof Error ? error.message : "测试失败");
  }
}
async function remove(item: Item) {
  if (item.id.startsWith("builtin-")) return void notify("内置工具不能删除");
  if (!confirm("确定删除这项能力？")) return;
  try {
    await api(`${tab.value}/delete`, {
      method: "POST",
      body: JSON.stringify({ id: item.id }),
    });
    await load();
    await notify("已删除");
  } catch (error) {
    await notify(error instanceof Error ? error.message : "删除失败");
  }
}
onMounted(load);
</script>
<template>
  <IonPage
    ><PageHeader
      title="AI 能力库"
      subtitle="Prompt、Skills 与 Tools"
      back
    /><IonContent
      ><main>
        <nav>
          <button
            v-for="item in [
              { v: 'prompts', l: 'Prompts' },
              { v: 'skills', l: 'Skills' },
              { v: 'tools', l: 'Tools' },
              { v: 'notes', l: 'Notes' },
            ]"
            :key="item.v"
            :class="{ active: tab === item.v }"
            @click="tab = item.v as Kind"
          >
            {{ item.l }}
          </button>
        </nav>
        <label class="search"><IonIcon :icon="searchOutline"/><input v-model="search" :placeholder="`搜索 ${tab === 'prompts' ? 'Prompts' : tab === 'skills' ? 'Skills' : tab === 'tools' ? 'Tools' : 'Notes'}`"></label>
        <div class="bar">
          <span>{{ filteredItems.length }} 项能力</span>
          <div>
            <IonButton
              size="small"
              fill="clear"
              :disabled="loading"
              @click="load"
              ><IonSpinner v-if="loading" name="dots" /><IonIcon
                v-else
                :icon="refreshOutline" /></IonButton
            ><IonButton size="small" @click="openEditor()"
              ><IonIcon :icon="addOutline" />新增</IonButton
            >
          </div>
        </div>
        <section>
          <article v-for="item in visibleItems" :key="item.id">
            <span>{{
              tab === "prompts" ? "/" : tab === "skills" ? "S" : tab === "tools" ? "T" : "N"
            }}</span>
            <div>
              <b>{{ item.title || item.name }}</b
              ><small v-if="tab === 'prompts'">/{{ item.command }}</small
              ><small v-else-if="tab === 'notes'">{{ item.content }}</small
              ><small v-else>{{
                item.description || item.kind || "自定义能力"
              }}</small>
            </div>
            <button @click="openEditor(item)">
              <IonIcon :icon="createOutline" /></button
            ><button
              class="danger"
              :disabled="item.id.startsWith('builtin-')"
              @click="remove(item)"
            >
              <IonIcon :icon="trashOutline" />
            </button>
          </article>
          <p v-if="!filteredItems.length && !loading" class="empty">暂无匹配内容</p>
        </section><div class="pager"><span>共 {{filteredItems.length}} 项</span><select v-model.number="pageSize"><option :value="10">10/页</option><option :value="20">20/页</option><option :value="50">50/页</option></select><button :disabled="page<=1" @click="page--">上一页</button><b>{{page}}/{{Math.max(1,Math.ceil(filteredItems.length/pageSize))}}</b><button :disabled="page>=Math.ceil(filteredItems.length/pageSize)" @click="page++">下一页</button></div>
      </main></IonContent
    >
    <div v-if="editorOpen" class="mask" @click.self="editorOpen = false">
      <section class="editor">
        <header>
          <b
            >{{ form.id ? "编辑" : "新增" }}
            {{
              tab === "prompts" ? "Prompt" : tab === "skills" ? "Skill" : tab === "tools" ? "Tool" : "Note"
            }}</b
          ><button @click="editorOpen = false">关闭</button>
        </header>
        <template v-if="tab === 'prompts'"
          ><label>标题<input v-model="form.title" /></label
          ><label
            >斜杠命令<input
              v-model="form.command"
              placeholder="summary" /></label
          ><label
            >Prompt 内容<textarea
              v-model="form.content"
              rows="8"
            ></textarea></label></template
        ><template v-else-if="tab === 'notes'"
          ><label>标题<input v-model="form.title" /></label><label>笔记内容<textarea v-model="form.content" rows="10"></textarea></label></template
        ><template v-else
          ><label>名称<input v-model="form.name" /></label
          ><label>说明<input v-model="form.description" /></label
          ><label v-if="tab === 'skills'"
            >技能指令<textarea
              v-model="form.content"
              rows="8"
            ></textarea></label
          ><template v-else
            ><label
              >工具类型<select v-model="form.kind">
                <option value="custom">自定义</option>
                <option value="http">HTTP</option>
                <option value="function">函数</option>
              </select></label
            ><template v-if="form.kind === 'http'"
              ><label>请求地址<input v-model="(form.config as any).url" placeholder="https://api.example.com/action" /></label
              ><label>请求方法<select v-model="(form.config as any).method"><option>GET</option><option>POST</option><option>PUT</option><option>PATCH</option><option>DELETE</option></select></label
              ><label>请求头 JSON<textarea v-model="form.headersText" rows="4"></textarea></label
              ><label>测试参数 JSON<textarea v-model="form.argumentsText" rows="4"></textarea></label
              ><IonButton fill="outline" expand="block" @click="testTool">测试 HTTP 工具</IonButton></template
            ><label class="check"
              ><input
                v-model="form.enabled"
                type="checkbox"
                :true-value="1"
                :false-value="0"
              />启用</label
            ></template
          ></template
        ><IonButton expand="block" :disabled="saving" @click="saveItem"
          >保存</IonButton
        >
      </section>
    </div></IonPage
  >
</template>
<style scoped>
main {
  padding: 12px 12px 28px;
}
.search{height:40px;display:flex;align-items:center;gap:8px;margin-top:10px;padding:0 11px;border:1px solid var(--app-line);border-radius:7px;background:var(--app-card);color:var(--app-muted)}.search input{min-width:0;flex:1;border:0;outline:0;background:transparent;color:var(--app-text)}
nav {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  padding: 3px;
  border-radius: 7px;
  background: var(--ion-background-color);
}
nav button {
  height: 36px;
  border: 0;
  border-radius: 5px;
  color: var(--app-muted);
  background: transparent;
}
nav button.active {
  color: #1677ff;
  background: var(--app-card);
  box-shadow: 0 1px 5px #0001;
}
.bar {
  min-height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--app-muted);
  font-size: 11px;
}
.bar > div {
  display: flex;
}
main > section {
  overflow: hidden;
  border: 1px solid var(--app-line);
  border-radius: 8px;
  background: var(--app-card);
}
article {
  min-height: 64px;
  display: grid;
  grid-template-columns: 34px 1fr 32px 32px;
  align-items: center;
  gap: 7px;
  padding: 9px 11px;
  border-bottom: 1px solid var(--app-line);
}
article:last-child {
  border: 0;
}
article > span {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: 6px;
  color: #fff;
  background: #1677ff;
  font-weight: 700;
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
article small {
  margin-top: 4px;
  color: var(--app-muted);
  font-size: 10px;
}
article > button {
  width: 32px;
  height: 32px;
  border: 0;
  color: #1677ff;
  background: transparent;
  font-size: 16px;
}
article > button.danger {
  color: #ef4444;
}
article > button:disabled {
  opacity: 0.25;
}
.empty {
  padding: 40px;
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
.editor {
  width: 100%;
  max-height: 86vh;
  overflow: auto;
  padding: 14px 14px calc(20px + env(safe-area-inset-bottom));
  border-radius: 8px 8px 0 0;
  background: var(--app-card);
}
.editor header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}
.editor header button {
  border: 0;
  color: var(--app-muted);
  background: transparent;
}
.editor label {
  display: grid;
  gap: 6px;
  margin-bottom: 11px;
  color: var(--app-muted);
  font-size: 11px;
}
.editor input,
.editor select,
.editor textarea {
  width: 100%;
  padding: 9px 10px;
  border: 1px solid var(--app-line);
  border-radius: 6px;
  color: var(--app-text);
  background: var(--ion-background-color);
  font: inherit;
}
.editor input,
.editor select {
  height: 40px;
}
.editor .check {
  display: flex;
  grid-template-columns: auto 1fr;
  align-items: center;
}
.editor .check input {
  width: 18px;
  height: 18px;
}
.pager{display:flex;align-items:center;gap:6px;margin-top:10px;color:var(--app-muted);font-size:10px}.pager span{margin-right:auto}.pager select,.pager button{height:32px;border:1px solid var(--app-line);border-radius:6px;color:var(--app-text);background:var(--app-card)}.pager button:disabled{opacity:.35}
</style>
