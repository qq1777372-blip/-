<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
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
  arrowDownOutline,
  arrowUpOutline,
  createOutline,
  playOutline,
  refreshOutline,
  trashOutline,
} from "ionicons/icons";
import PageHeader from "../components/PageHeader.vue";
import { session } from "../session";

type Row = Record<string, any>;
const tab = ref<"usage" | "memory" | "workflow" | "jobs" | "shares">("usage");
const usage = ref<Row[]>([]),
  summary = ref<Row>({}),
  memories = ref<Row[]>([]),
  workflows = ref<Row[]>([]),
  jobs = ref<Row[]>([]), shares=ref<Row[]>([]), tools=ref<Row[]>([]), models=ref<Row[]>([]);
const page=ref(1),pageSize=ref(10);
const usageQuery=ref(""),operationFilter=ref(""),modelFilter=ref(""),statusFilter=ref(""),budget=ref(Number(localStorage.getItem("ai-monthly-budget")||0));
const filteredUsage=computed(()=>{const q=usageQuery.value.trim().toLowerCase();return usage.value.filter(row=>(!operationFilter.value||row.operation===operationFilter.value)&&(!modelFilter.value||row.model_id===modelFilter.value)&&(!statusFilter.value||row.status===statusFilter.value)&&(!q||`${row.operation||""} ${row.model_id||""} ${row.detail||""}`.toLowerCase().includes(q)))});
const pagedUsage=computed(()=>filteredUsage.value.slice((page.value-1)*pageSize.value,page.value*pageSize.value));
const pagedMemories=computed(()=>memories.value.slice((page.value-1)*pageSize.value,page.value*pageSize.value));
const pagedWorkflows=computed(()=>workflows.value.slice((page.value-1)*pageSize.value,page.value*pageSize.value));
const pagedJobs=computed(()=>jobs.value.slice((page.value-1)*pageSize.value,page.value*pageSize.value));
const pagedShares=computed(()=>shares.value.slice((page.value-1)*pageSize.value,page.value*pageSize.value));
const currentTotal=computed(()=>tab.value==='usage'?filteredUsage.value.length:tab.value==='memory'?memories.value.length:tab.value==='workflow'?workflows.value.length:tab.value==='jobs'?jobs.value.length:shares.value.length);
watch([tab,pageSize,usageQuery,operationFilter,modelFilter,statusFilter],()=>{page.value=1});
watch(currentTotal,total=>{page.value=Math.min(page.value,Math.max(1,Math.ceil(total/pageSize.value)))});
const operations=computed(()=>[...new Set(usage.value.map(row=>row.operation).filter(Boolean))]),usageModels=computed(()=>[...new Set(usage.value.map(row=>row.model_id).filter(Boolean))]);
const budgetPercent=computed(()=>budget.value?Math.min(100,Number(summary.value.cost||0)/budget.value*100):0);
function saveBudget(){localStorage.setItem("ai-monthly-budget",String(Math.max(0,budget.value)));void notify("预算阈值已保存")}
const loading = ref(false);
const workflowOpen = ref(false),
  workflowForm = ref<{
    id?: string;
    name: string;
    description: string;
    steps: Row[];
    enabled?: boolean;
  }>({ name: "", description: "", steps: [], enabled: true });
let timer: number | undefined;

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
    const [u, m, w, j, s, t, mo] = await Promise.all([
      api("usage"),
      api("memories"),
      api("workflows"),
      api("jobs"),
      api("shares"),
      api("tools?all=1"),
      api("models"),
    ]);
    usage.value = u.usage || [];
    summary.value = u.summary || {};
    memories.value = m.memories || [];
    workflows.value = w.workflows || [];
    jobs.value = j.jobs || [];
    shares.value=s.shares||[];
    tools.value=t.tools||[];
    models.value=mo.models||[];
  } catch (error) {
    await notify(error instanceof Error ? error.message : "加载失败");
  } finally {
    loading.value = false;
  }
}
async function addMemory() {
  const content = prompt("输入需要 AI 长期记住的内容")?.trim();
  if (!content) return;
  await api("memories", { method: "POST", body: JSON.stringify({ content }) });
  await load();
}
async function editMemory(row:Row){const content=prompt("编辑长期记忆",row.content)?.trim();if(!content)return;await api("memories",{method:"POST",body:JSON.stringify({...row,content,enabled:Boolean(row.enabled)})});await load();await notify("记忆已保存")}
async function toggleMemory(row:Row){await api("memories",{method:"POST",body:JSON.stringify({...row,enabled:!row.enabled})});await load()}
async function removeMemory(id: string) {
  if (!confirm("删除这条长期记忆？")) return;
  await api("memories/delete", {
    method: "POST",
    body: JSON.stringify({ id }),
  });
  await load();
}
function editWorkflow(row?: Row) {
  let steps: Row[] = [];
  try {
    steps = JSON.parse(row?.steps || "[]");
  } catch {}
  workflowForm.value = row
    ? { id: row.id, name: row.name, description: row.description || "", steps, enabled: Boolean(row.enabled) }
    : {
        name: "",
        description: "",
        steps: [
          { type: "prompt", content: "请根据以下输入完成任务：{{input}}" },
        ],
        enabled: true,
      };
  workflowOpen.value = true;
}
function addStep() {
  workflowForm.value.steps.push({ type: "prompt", content: "" });
}
function moveStep(index: number, direction: number) {
  const target = index + direction;
  if (target < 0 || target >= workflowForm.value.steps.length) return;
  const [step] = workflowForm.value.steps.splice(index, 1);
  workflowForm.value.steps.splice(target, 0, step);
}
async function saveWorkflow() {
  const value = workflowForm.value;
  if (!value.name.trim() || !value.steps.length)
    return void notify("请填写名称并至少添加一个步骤");
  await api("workflows", { method: "POST", body: JSON.stringify(value) });
  workflowOpen.value = false;
  await load();
  await notify("工作流已保存");
}
async function runWorkflow(row: Row) {
  const input = prompt("输入本次运行参数") ?? "";
  await api("workflows/run", {
    method: "POST",
    body: JSON.stringify({ id: row.id, input }),
  });
  tab.value = "jobs";
  await load();
  await notify("任务已进入后台执行");
}
async function removeWorkflow(id: string) {
  if (!confirm("删除这个工作流？")) return;
  await api("workflows/delete", {
    method: "POST",
    body: JSON.stringify({ id }),
  });
  await load();
}
async function toggleWorkflow(row:Row){await api("workflows",{method:"POST",body:JSON.stringify({id:row.id,name:row.name,description:row.description||"",steps:JSON.parse(row.steps||"[]"),enabled:!row.enabled})});await load()}
async function jobAction(row:Row,action:"cancel"|"retry"|"delete"){await api(`jobs/${action}`,{method:"POST",body:JSON.stringify({id:row.id})});await load();await notify(action==="cancel"?"任务已取消":action==="retry"?"任务已重试":"任务已删除")}
function showUsage(row:Row){alert(`操作：${row.operation}\n模型：${row.model_id||"默认模型"}\n状态：${row.status}\nToken：${row.input_tokens+row.output_tokens}\n耗时：${row.latency_ms} ms\n\n${row.detail||"无错误详情"}`)}
async function revokeShare(id:string){if(!confirm("撤销后分享链接将立即失效，是否继续？"))return;await api("shares/revoke",{method:"POST",body:JSON.stringify({id})});await load();await notify("分享已撤销")}
function steps(row: Row) {
  try {
    return JSON.parse(row.steps || "[]").length;
  } catch {
    return 0;
  }
}
function result(row: Row) {
  try {
    return JSON.parse(row.output || "{}").result || row.error || "暂无结果";
  } catch {
    return row.error || row.output || "暂无结果";
  }
}
onMounted(() => {
  load();
  timer = window.setInterval(() => {
    if (tab.value === "jobs") load();
  }, 3000);
});
onBeforeUnmount(() => timer && clearInterval(timer));
</script>

<template>
  <IonPage
    ><PageHeader
      title="AI 运行与治理"
      subtitle="用量、记忆、工作流与后台任务"
      back
    /><IonContent
      ><main>
        <nav>
          <button
            v-for="item in [
              { v: 'usage', l: '用量' },
              { v: 'memory', l: '记忆' },
              { v: 'workflow', l: '工作流' },
              { v: 'jobs', l: '任务' },
              { v: 'shares', l: '分享' },
            ]"
            :key="item.v"
            :class="{ active: tab === item.v }"
            @click="tab = item.v as typeof tab"
          >
            {{ item.l }}
          </button>
        </nav>
        <div class="bar">
          <span>{{ loading ? "正在刷新" : "数据实时同步" }}</span
          ><IonButton
            size="small"
            fill="clear"
            :disabled="loading"
            @click="load"
            ><IonSpinner v-if="loading" name="dots" /><IonIcon
              v-else
              :icon="refreshOutline"
            />刷新</IonButton
          >
        </div>
        <template v-if="tab === 'usage'"
          ><section class="metrics">
            <article>
              <small>调用次数</small><b>{{ summary.calls || 0 }}</b>
            </article>
            <article>
              <small>输入 Token</small><b>{{ summary.input_tokens || 0 }}</b>
            </article>
            <article>
              <small>输出 Token</small><b>{{ summary.output_tokens || 0 }}</b>
            </article>
            <article>
              <small>累计费用</small
              ><b>¥{{ Number(summary.cost || 0).toFixed(4) }}</b>
            </article>
          </section>
          <section class="usage-controls"><input v-model="usageQuery" placeholder="搜索操作、模型或错误"><select v-model="operationFilter"><option value="">全部操作</option><option v-for="item in operations" :key="item" :value="item">{{item}}</option></select><select v-model="modelFilter"><option value="">全部模型</option><option v-for="item in usageModels" :key="item" :value="item">{{item}}</option></select><select v-model="statusFilter"><option value="">全部状态</option><option value="ok">成功</option><option value="error">失败</option></select><div><input v-model.number="budget" type="number" min="0" step="10" placeholder="月预算"><button @click="saveBudget">保存预算</button></div><small v-if="budget">已使用 {{budgetPercent.toFixed(1)}}%，预算 ¥{{budget}}</small></section>
          <section class="list">
            <article v-for="row in pagedUsage" :key="row.id" @click="showUsage(row)">
              <div>
                <b>{{ row.operation }}</b
                ><small
                  >{{ new Date(row.created_at * 1000).toLocaleString() }} ·
                  {{ row.model_id || "默认模型" }}</small
                >
              </div>
              <span
                >{{ row.input_tokens + row.output_tokens }} Token<br />{{
                  row.latency_ms
                }}
                ms</span
              >
            </article>
            <p v-if="!filteredUsage.length" class="empty">暂无匹配记录</p>
          </section></template
        >
        <template v-else-if="tab === 'memory'"
          ><div class="actions">
            <span>记忆会自动加入聊天上下文</span
            ><IonButton size="small" @click="addMemory"
              ><IonIcon :icon="addOutline" />新增</IonButton
            >
          </div>
          <section class="list">
            <article v-for="row in pagedMemories" :key="row.id">
              <div>
                <b>{{ row.content }}</b
                ><small>{{ row.source_chat_id ? `来源会话 ${row.source_chat_id} · ` : "手动添加 · " }}{{ new Date(row.updated_at * 1000).toLocaleString() }}</small>
              </div>
              <label class="mini-switch"><input :checked="Boolean(row.enabled)" type="checkbox" @change="toggleMemory(row)"><span></span></label><button @click="editMemory(row)"><IonIcon :icon="createOutline"/></button><button class="danger" @click="removeMemory(row.id)">
                <IonIcon :icon="trashOutline" />
              </button>
            </article>
            <p v-if="!memories.length" class="empty">暂无长期记忆</p>
          </section></template
        >
        <template v-else-if="tab === 'workflow'"
          ><div class="actions">
            <span>按顺序执行自动化步骤</span
            ><IonButton size="small" @click="editWorkflow()"
              ><IonIcon :icon="addOutline" />新建</IonButton
            >
          </div>
          <section class="list">
            <article v-for="row in pagedWorkflows" :key="row.id">
              <div>
                <b>{{ row.name }}</b
                ><small>{{ steps(row) }} 个步骤</small>
              </div>
              <label class="mini-switch"><input :checked="Boolean(row.enabled)" type="checkbox" @change="toggleWorkflow(row)"><span></span></label><button @click="editWorkflow(row)">
                <IonIcon :icon="createOutline" /></button
              ><button :disabled="!row.enabled" @click="runWorkflow(row)">
                <IonIcon :icon="playOutline" /></button
              ><button class="danger" @click="removeWorkflow(row.id)">
                <IonIcon :icon="trashOutline" />
              </button>
            </article>
            <p v-if="!workflows.length" class="empty">暂无工作流</p>
          </section></template
        >
        <template v-else-if="tab === 'jobs'"
          ><section class="list jobs">
            <article v-for="row in pagedJobs" :key="row.id">
              <div>
                <b>{{ row.kind }} · {{ row.status }}</b
                ><small>{{ result(row) }}</small>
              </div>
              <span>{{ new Date(row.updated_at * 1000).toLocaleTimeString() }}</span><button v-if="['queued','running'].includes(row.status)" @click="jobAction(row,'cancel')">取消</button><button v-if="['completed','failed','cancelled'].includes(row.status)" @click="jobAction(row,'retry')">重试</button><button v-if="['completed','failed','cancelled'].includes(row.status)" class="danger" @click="jobAction(row,'delete')"><IonIcon :icon="trashOutline"/></button>
            </article>
            <p v-if="!jobs.length" class="empty">暂无后台任务</p>
          </section></template
        ><template v-else><section class="list"><article v-for="row in pagedShares" :key="row.id"><div><b>{{row.title}}</b><small>{{row.revoked?'已撤销':row.expires_at&&row.expires_at<Math.floor(Date.now()/1000)?'已过期':`有效至 ${new Date(row.expires_at*1000).toLocaleString()}`}}</small></div><button v-if="!row.revoked" class="danger" @click="revokeShare(row.id)"><IonIcon :icon="trashOutline"/></button></article><p v-if="!shares.length" class="empty">暂无分享记录</p></section></template
        >
        <div class="pager"><span>共 {{currentTotal}} 条</span><select v-model.number="pageSize"><option :value="10">10/页</option><option :value="20">20/页</option><option :value="50">50/页</option></select><button :disabled="page<=1" @click="page--">上一页</button><b>{{page}}/{{Math.max(1,Math.ceil(currentTotal/pageSize))}}</b><button :disabled="page>=Math.ceil(currentTotal/pageSize)" @click="page++">下一页</button></div>
      </main></IonContent
    >
    <div v-if="workflowOpen" class="mask" @click.self="workflowOpen = false">
      <section class="editor">
        <header>
          <b>{{ workflowForm.id ? "编辑" : "新建" }}工作流</b
          ><button @click="workflowOpen = false">关闭</button>
        </header>
        <label>名称<input v-model="workflowForm.name" /></label
        ><label>说明<input v-model="workflowForm.description" /></label><label class="enabled-row"><input v-model="workflowForm.enabled" type="checkbox">启用工作流</label>
        <div class="steps">
          <article v-for="(step, index) in workflowForm.steps" :key="index">
            <header>
              <select v-model="step.type">
                <option value="prompt">Prompt</option>
                <option value="search">知识搜索</option>
                <option value="tool">工具</option></select
              ><button :disabled="index === 0" @click="moveStep(index, -1)">
                <IonIcon :icon="arrowUpOutline" /></button
              ><button
                :disabled="index === workflowForm.steps.length - 1"
                @click="moveStep(index, 1)"
              >
                <IonIcon :icon="arrowDownOutline" /></button
              ><button
                class="danger"
                @click="workflowForm.steps.splice(index, 1)"
              >
                <IonIcon :icon="trashOutline" />
              </button>
            </header>
            <template v-if="step.type === 'prompt'"><select v-model="step.model_id"><option value="">默认模型</option><option v-for="model in models.filter(item=>item.model_type==='chat')" :key="model.id" :value="model.id">{{model.name}}</option></select><textarea v-model="step.content" rows="4" placeholder="支持 {{input}} 和 {{previous}}"></textarea></template>
            <template v-else-if="step.type === 'search'"><input v-model="step.query" placeholder="搜索词，支持 {{input}} 和 {{previous}}"><label>返回数量<input v-model.number="step.limit" type="number" min="1" max="10"></label></template>
            <template v-else><select v-model="step.tool_id"><option value="">选择工具</option><option v-for="tool in tools" :key="tool.id" :value="tool.id">{{tool.name}}</option></select><textarea :value="JSON.stringify(step.arguments||{},null,2)" rows="3" placeholder="参数 JSON" @change="(event)=>{try{step.arguments=JSON.parse((event.target as HTMLTextAreaElement).value)}catch{notify('工具参数必须是有效 JSON')}}"></textarea></template>
          </article>
        </div>
        <IonButton fill="outline" expand="block" @click="addStep"
          ><IonIcon :icon="addOutline" />添加步骤</IonButton
        ><IonButton expand="block" @click="saveWorkflow">保存工作流</IonButton>
      </section>
    </div></IonPage
  >
</template>

<style scoped>
main {
  padding: 12px 12px 30px;
}
nav {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
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
.bar,
.actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 48px;
  color: var(--app-muted);
  font-size: 11px;
}
.metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  overflow: hidden;
  margin-bottom: 12px;
  border: 1px solid var(--app-line);
  border-radius: 8px;
  background: var(--app-card);
}
.metrics article {
  display: grid;
  gap: 6px;
  padding: 14px;
  border-right: 1px solid var(--app-line);
  border-bottom: 1px solid var(--app-line);
}
.metrics article:nth-child(2n) {
  border-right: 0;
}
.metrics article:nth-last-child(-n + 2) {
  border-bottom: 0;
}
.metrics small {
  color: var(--app-muted);
}
.metrics b {
  font-size: 20px;
}
.list {
  overflow: hidden;
  border: 1px solid var(--app-line);
  border-radius: 8px;
  background: var(--app-card);
}
.list article {
  min-height: 62px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--app-line);
}
.list article:last-child {
  border-bottom: 0;
}
.list article > div {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 4px;
}
.list b,
.list small {
  overflow: hidden;
  text-overflow: ellipsis;
}
.list b {
  font-size: 12px;
}
.list small {
  color: var(--app-muted);
  font-size: 10px;
  white-space: nowrap;
}
.list span {
  color: var(--app-muted);
  font-size: 9px;
  text-align: right;
}
.list button {
  width: 34px;
  height: 34px;
  border: 0;
  color: #1677ff;
  background: transparent;
  font-size: 17px;
}
.list button.danger {
  color: #ef4444;
}
.empty {
  padding: 30px;
  text-align: center;
  color: var(--app-muted);
  font-size: 12px;
}
.jobs small {
  white-space: normal;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
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
  max-height: 88vh;
  overflow: auto;
  padding: 14px 14px calc(20px + env(safe-area-inset-bottom));
  border-radius: 8px 8px 0 0;
  background: var(--app-card);
}
.editor > header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}
.editor > header button {
  border: 0;
  color: var(--app-muted);
  background: transparent;
}
.editor > label {
  display: grid;
  gap: 5px;
  margin-bottom: 10px;
  color: var(--app-muted);
  font-size: 11px;
}
.editor input,
.editor select,
.editor textarea {
  width: 100%;
  padding: 9px;
  border: 1px solid var(--app-line);
  border-radius: 6px;
  color: var(--app-text);
  background: var(--ion-background-color);
  font: inherit;
}
.editor input,
.editor select {
  height: 39px;
}
.steps {
  display: grid;
  gap: 8px;
  margin: 12px 0;
}
.steps > article {
  padding: 9px;
  border: 1px solid var(--app-line);
  border-radius: 7px;
}
.steps header {
  display: grid;
  grid-template-columns: 1fr 32px 32px 32px;
  gap: 5px;
  margin-bottom: 7px;
}
.steps header button {
  border: 0;
  color: #1677ff;
  background: transparent;
}
.steps header button.danger {
  color: #ef4444;
}
.steps header button:disabled {
  opacity: 0.25;
}
.usage-controls{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:0 0 12px}.usage-controls select,.usage-controls input{min-width:0;height:36px;padding:0 7px;border:1px solid var(--app-line);border-radius:6px;color:var(--app-text);background:var(--app-card);font-size:10px}.usage-controls>div{grid-column:1/-1;display:grid;grid-template-columns:1fr auto;gap:6px}.usage-controls button{border:0;border-radius:6px;color:#fff;background:#1677ff}.usage-controls small{grid-column:1/-1;color:var(--app-muted)}
.pager{display:flex;align-items:center;gap:6px;margin-top:10px;color:var(--app-muted);font-size:10px}.pager span{margin-right:auto}.pager select,.pager button{height:32px;border:1px solid var(--app-line);border-radius:6px;color:var(--app-text);background:var(--app-card)}.pager button:disabled{opacity:.35}.mini-switch{position:relative;width:38px;height:22px;flex:none}.mini-switch input{position:absolute;opacity:0}.mini-switch span{display:block;width:38px;height:22px;border-radius:11px;background:#cbd5e1}.mini-switch span:after{content:"";position:absolute;top:3px;left:3px;width:16px;height:16px;border-radius:50%;background:#fff;transition:.15s}.mini-switch input:checked+span{background:#1677ff}.mini-switch input:checked+span:after{left:19px}.enabled-row{display:flex!important;align-items:center;gap:8px}.enabled-row input{width:18px!important;height:18px!important}
</style>
