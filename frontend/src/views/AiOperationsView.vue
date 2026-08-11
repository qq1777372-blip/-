<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Close, Delete, EditPen, Plus, Refresh, RefreshRight, VideoPause, VideoPlay } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '../stores/auth'

type Row = Record<string, any>
defineProps<{ embedded?: boolean }>()
const auth = useAuthStore()
const tab = ref('usage')
const usage = ref<Row[]>([]), summary = ref<Row>({}), memories = ref<Row[]>([]), workflows = ref<Row[]>([]), jobs = ref<Row[]>([])
const models = ref<Row[]>([]), tools = ref<Row[]>([]), loading = ref(false)
const usageQuery = ref(''), usageStatus = ref(''), usagePage = ref(1), usagePageSize = 20
const listPageSize = ref(10), memoryPage = ref(1), workflowPage = ref(1), jobPage = ref(1)
const workflowVisible = ref(false), editingWorkflow = ref<Row | null>(null)
const workflowForm = reactive<{ name: string; description: string; enabled: boolean; steps: Row[] }>({ name: '', description: '', enabled: true, steps: [] })
let timer: number | undefined

const filteredUsage = computed(() => usage.value.filter(row => (!usageStatus.value || row.status === usageStatus.value) && (!usageQuery.value.trim() || `${row.operation} ${row.model_id} ${row.detail}`.toLowerCase().includes(usageQuery.value.trim().toLowerCase()))))
const visibleUsage = computed(() => filteredUsage.value.slice((usagePage.value - 1) * usagePageSize, usagePage.value * usagePageSize))
const visibleMemories = computed(() => memories.value.slice((memoryPage.value - 1) * listPageSize.value, memoryPage.value * listPageSize.value))
const visibleWorkflows = computed(() => workflows.value.slice((workflowPage.value - 1) * listPageSize.value, workflowPage.value * listPageSize.value))
const visibleJobs = computed(() => jobs.value.slice((jobPage.value - 1) * listPageSize.value, jobPage.value * listPageSize.value))
watch(listPageSize, () => { memoryPage.value = 1; workflowPage.value = 1; jobPage.value = 1 })
watch([usageQuery, usageStatus], () => { usagePage.value = 1 })
watch(() => filteredUsage.value.length, total => { usagePage.value = Math.min(usagePage.value, Math.max(1, Math.ceil(total / usagePageSize))) })
watch(() => memories.value.length, total => { memoryPage.value = Math.min(memoryPage.value, Math.max(1, Math.ceil(total / listPageSize.value))) })
watch(() => workflows.value.length, total => { workflowPage.value = Math.min(workflowPage.value, Math.max(1, Math.ceil(total / listPageSize.value))) })
watch(() => jobs.value.length, total => { jobPage.value = Math.min(jobPage.value, Math.max(1, Math.ceil(total / listPageSize.value))) })

async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/ai-api/${path}`, { credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-Workspace-User': String(auth.currentUser?.id || 'local'), 'X-Workspace-Role': String(auth.currentUser?.role || 'user') }, ...init })
  const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error(data.error || `请求失败 (${response.status})`); return data
}
async function load() {
  loading.value = true
  try {
    const [u, m, w, j, modelData, toolData] = await Promise.all([api<Row>('usage'), api<Row>('memories'), api<Row>('workflows'), api<Row>('jobs'), api<Row>('models'), api<Row>('tools')])
    usage.value = u.usage || []; summary.value = u.summary || {}; memories.value = m.memories || []; workflows.value = w.workflows || []; jobs.value = j.jobs || []; models.value = modelData.models || []; tools.value = toolData.tools || []
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '加载失败') }
  finally { loading.value = false }
}
async function saveMemory(row?: Row) {
  const result = await ElMessageBox.prompt('输入需要 AI 长期记住的内容', row ? '编辑记忆' : '新增记忆', { inputValue: row?.content || '', inputType: 'textarea', confirmButtonText: '保存', cancelButtonText: '取消' }).catch(() => null)
  if (!result?.value?.trim()) return
  await api('memories', { method: 'POST', body: JSON.stringify({ id: row?.id, content: result.value.trim(), source_chat_id: row?.source_chat_id || '', enabled: row ? Boolean(row.enabled) : true }) }); await load()
}
async function toggleMemory(row: Row) { await api('memories', { method: 'POST', body: JSON.stringify({ id: row.id, content: row.content, source_chat_id: row.source_chat_id || '', enabled: !row.enabled }) }); await load() }
async function removeMemory(row: Row) { await api('memories/delete', { method: 'POST', body: JSON.stringify({ id: row.id }) }); await load() }

function blankStep(type = 'prompt'): Row { return type === 'tool' ? { type, tool_id: '', arguments: {} } : type === 'search' ? { type, query: '{{input}}', limit: 5 } : { type, content: '请根据以下输入完成任务：{{input}}', model_id: '' } }
function openWorkflow(row?: Row) {
  editingWorkflow.value = row || null; workflowForm.name = row?.name || ''; workflowForm.description = row?.description || ''; workflowForm.enabled = row ? Boolean(row.enabled) : true
  try { workflowForm.steps = row ? JSON.parse(row.steps || '[]') : [blankStep()] } catch { workflowForm.steps = [blankStep()] }
  workflowVisible.value = true
}
function changeStepType(step: Row, type: string) { Object.keys(step).forEach(key => delete step[key]); Object.assign(step, blankStep(type)) }
async function saveWorkflow() {
  if (!workflowForm.name.trim() || !workflowForm.steps.length) return ElMessage.warning('请填写名称并添加步骤')
  await api('workflows', { method: 'POST', body: JSON.stringify({ id: editingWorkflow.value?.id, ...workflowForm }) }); workflowVisible.value = false; await load(); ElMessage.success('工作流已保存')
}
async function toggleWorkflow(row: Row) { await api('workflows', { method: 'POST', body: JSON.stringify({ id: row.id, name: row.name, description: row.description, steps: JSON.parse(row.steps || '[]'), enabled: !row.enabled }) }); await load() }
async function runWorkflow(row: Row) { const input = await ElMessageBox.prompt('输入本次运行参数', '运行工作流', { confirmButtonText: '运行', cancelButtonText: '取消' }).catch(() => null); if (!input) return; await api('workflows/run', { method: 'POST', body: JSON.stringify({ id: row.id, input: input.value }) }); tab.value = 'jobs'; await load() }
async function removeWorkflow(row: Row) { await ElMessageBox.confirm(`删除“${row.name}”？`, '删除工作流', { type: 'warning' }); await api('workflows/delete', { method: 'POST', body: JSON.stringify({ id: row.id }) }); await load() }
async function jobAction(row: Row, action: 'cancel' | 'retry' | 'delete') { await api(`jobs/${action}`, { method: 'POST', body: JSON.stringify({ id: row.id }) }); await load() }
function jobResult(row: Row) { try { const output = JSON.parse(row.output || '{}'); return output.result || JSON.stringify(output.outputs || output) || row.error || '暂无结果' } catch { return row.error || row.output || '暂无结果' } }
function showUsage(row: Row) { ElMessageBox.alert(`<pre style="white-space:pre-wrap">${String(row.detail || '无错误详情').replaceAll('<', '&lt;')}</pre>`, '调用详情', { dangerouslyUseHTMLString: true }) }

onMounted(() => { load(); timer = window.setInterval(() => { if (tab.value === 'jobs') load() }, 3000) })
onBeforeUnmount(() => timer && clearInterval(timer))
</script>

<template>
  <section class="page" :class="{ embedded }">
    <header v-if="!embedded"><div><small>AI WORKSPACE</small><h1>运行与治理</h1><p>调用审计、费用、长期记忆和 Agent 工作流</p></div><div><el-button @click="$router.push('/ai-workspace')">返回聊天</el-button><el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button></div></header>
    <div v-if="embedded" class="embedded-actions"><el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button></div>
    <nav><button v-for="item in [{v:'usage',l:'调用记录'},{v:'memory',l:'长期记忆'},{v:'workflow',l:'工作流'},{v:'jobs',l:'后台任务'}]" :key="item.v" :class="{active:tab===item.v}" @click="tab=item.v">{{item.l}}</button></nav>
    <template v-if="tab==='usage'">
      <div class="metrics"><article><span>调用次数</span><b>{{summary.calls||0}}</b></article><article><span>输入 Token</span><b>{{summary.input_tokens||0}}</b></article><article><span>输出 Token</span><b>{{summary.output_tokens||0}}</b></article><article><span>累计费用</span><b>¥{{Number(summary.cost||0).toFixed(4)}}</b></article></div>
      <div class="filters"><el-input v-model="usageQuery" clearable placeholder="搜索操作、模型或错误"/><el-select v-model="usageStatus" clearable placeholder="全部状态"><el-option label="成功" value="ok"/><el-option label="失败" value="error"/></el-select></div>
      <div class="table"><button v-for="row in visibleUsage" :key="row.id" class="record" @click="showUsage(row)"><span>{{new Date(row.created_at*1000).toLocaleString()}}</span><b>{{row.operation}}</b><code>{{row.model_id||'-'}}</code><span>{{row.input_tokens+row.output_tokens}} Token</span><span>{{row.latency_ms}} ms</span><el-tag :type="row.status==='ok'?'success':'danger'">{{row.status}}</el-tag></button><el-empty v-if="!visibleUsage.length" description="暂无调用记录"/></div>
      <el-pagination v-model:current-page="usagePage" :page-size="usagePageSize" :total="filteredUsage.length" layout="prev, pager, next, total" background/>
    </template>
    <template v-else-if="tab==='memory'"><div class="bar"><b>启用的记忆会自动加入聊天上下文</b><el-button type="primary" :icon="Plus" @click="saveMemory()">新增记忆</el-button></div><div class="cards"><article v-for="row in visibleMemories" :key="row.id"><div><p>{{row.content}}</p><small>{{row.source_chat_id ? `来源会话 ${row.source_chat_id}` : '手动添加'}} · {{new Date(row.updated_at*1000).toLocaleString()}}</small></div><el-switch :model-value="Boolean(row.enabled)" @change="toggleMemory(row)"/><el-button :icon="EditPen" circle text @click="saveMemory(row)"/><el-button :icon="Delete" circle text type="danger" @click="removeMemory(row)"/></article><el-empty v-if="!memories.length" description="暂无长期记忆"/></div><el-pagination v-model:current-page="memoryPage" v-model:page-size="listPageSize" :page-sizes="[10,20,50]" :total="memories.length" layout="sizes, prev, pager, next, total" background/></template>
    <template v-else-if="tab==='workflow'"><div class="bar"><b>按顺序执行 Prompt、工具和联网搜索步骤</b><el-button type="primary" :icon="Plus" @click="openWorkflow()">新建工作流</el-button></div><div class="cards"><article v-for="row in visibleWorkflows" :key="row.id"><div><b>{{row.name}}</b><p>{{row.description || `${JSON.parse(row.steps||'[]').length} 个步骤`}}</p></div><el-switch :model-value="Boolean(row.enabled)" @change="toggleWorkflow(row)"/><el-button :icon="EditPen" circle text @click="openWorkflow(row)"/><el-button :icon="VideoPlay" circle text :disabled="!row.enabled" @click="runWorkflow(row)"/><el-button :icon="Delete" circle text type="danger" @click="removeWorkflow(row)"/></article><el-empty v-if="!workflows.length" description="暂无工作流"/></div><el-pagination v-model:current-page="workflowPage" v-model:page-size="listPageSize" :page-sizes="[10,20,50]" :total="workflows.length" layout="sizes, prev, pager, next, total" background/></template>
    <template v-else><div class="cards jobs"><article v-for="row in visibleJobs" :key="row.id"><div><b>{{row.kind}}</b><p>{{jobResult(row)}}</p></div><el-tag :type="row.status==='completed'?'success':row.status==='failed'?'danger':row.status==='cancelled'?'info':'warning'">{{row.status}}</el-tag><small>{{new Date(row.updated_at*1000).toLocaleString()}}</small><div class="job-actions"><el-button v-if="['queued','running'].includes(row.status)" :icon="VideoPause" circle text title="取消" @click="jobAction(row,'cancel')"/><el-button v-if="['completed','failed','cancelled'].includes(row.status)" :icon="RefreshRight" circle text title="重试" @click="jobAction(row,'retry')"/><el-button v-if="['completed','failed','cancelled'].includes(row.status)" :icon="Delete" circle text type="danger" title="删除" @click="jobAction(row,'delete')"/></div></article><el-empty v-if="!jobs.length" description="暂无后台任务"/></div><el-pagination v-model:current-page="jobPage" v-model:page-size="listPageSize" :page-sizes="[10,20,50]" :total="jobs.length" layout="sizes, prev, pager, next, total" background/></template>

    <el-dialog v-model="workflowVisible" :title="editingWorkflow?'编辑工作流':'新建工作流'" width="min(820px,95vw)" top="4vh">
      <el-form label-position="top"><div class="workflow-meta"><el-form-item label="名称"><el-input v-model="workflowForm.name"/></el-form-item><el-form-item label="说明"><el-input v-model="workflowForm.description"/></el-form-item></div><el-form-item><el-switch v-model="workflowForm.enabled" active-text="启用"/></el-form-item></el-form>
      <div class="step-list"><article v-for="(step,index) in workflowForm.steps" :key="index"><header><b>步骤 {{index+1}}</b><el-select :model-value="step.type" @change="(value:string)=>changeStepType(step,value)"><el-option label="Prompt" value="prompt"/><el-option label="工具" value="tool"/><el-option label="联网搜索" value="search"/></el-select><el-button :icon="Close" circle text type="danger" @click="workflowForm.steps.splice(index,1)"/></header><template v-if="step.type==='prompt'"><el-select v-model="step.model_id" clearable placeholder="默认模型"><el-option v-for="model in models.filter(item=>item.model_type==='chat')" :key="model.id" :label="model.name" :value="model.id"/></el-select><el-input v-model="step.content" type="textarea" :rows="4" placeholder="支持 {{input}} 和 {{previous}}"/></template><template v-else-if="step.type==='tool'"><el-select v-model="step.tool_id" placeholder="选择工具"><el-option v-for="tool in tools" :key="tool.id" :label="tool.name" :value="tool.id"/></el-select><el-input :model-value="JSON.stringify(step.arguments||{})" placeholder="参数 JSON" @change="(value:string)=>{try{step.arguments=JSON.parse(value)}catch{}}"/></template><template v-else><el-input v-model="step.query" placeholder="搜索词，支持 {{input}} 和 {{previous}}"/><el-input-number v-model="step.limit" :min="1" :max="10"/></template></article></div>
      <el-button :icon="Plus" @click="workflowForm.steps.push(blankStep())">添加步骤</el-button><template #footer><el-button @click="workflowVisible=false">取消</el-button><el-button type="primary" @click="saveWorkflow">保存</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>
.page{display:flex;flex-direction:column;width:100%;height:calc(100vh - 104px);min-height:0;overflow:hidden;padding:18px 10px;background:#fff}.page>header{display:flex;flex:none;align-items:flex-start;justify-content:space-between;gap:20px;width:100%;margin:0 0 18px}.page header>div:last-child{display:flex;gap:8px}.page small{color:var(--brand-primary);font-size:10px;font-weight:700}.page h1{margin:5px 0;font-size:26px}.page p{margin:0;color:#64748b;font-size:12px}.page nav{display:flex;flex:none;gap:24px;width:100%;margin:0 0 18px;border-bottom:1px solid #e2e8f0;overflow-x:auto}.page nav button{flex:none;padding:11px 2px;border:0;border-bottom:2px solid transparent;background:none}.page nav button.active{border-color:var(--brand-primary);color:var(--brand-primary)}.metrics{display:grid;flex:none;grid-template-columns:repeat(4,1fr);width:100%;margin:0;border:1px solid #e2e8f0;border-radius:8px}.metrics article{padding:18px;border-right:1px solid #e2e8f0}.metrics article:last-child{border:0}.metrics span,.metrics b{display:block}.metrics span{color:#64748b;font-size:11px}.metrics b{margin-top:8px;font-size:22px}.filters,.bar{flex:none;width:100%;margin:16px 0}.filters{display:flex;gap:10px}.filters .el-select{width:160px}.table,.cards{width:100%;min-height:0;flex:1;margin:0;border:1px solid #e2e8f0;border-radius:8px;overflow:auto}.page>.el-pagination{flex:none;width:100%;margin:0;padding:14px 16px;border:1px solid #e2e8f0;border-top:0;background:#fff}.record{width:100%;display:grid;grid-template-columns:170px 1fr 1.2fr 110px 90px 70px;gap:12px;align-items:center;padding:11px 14px;border:0;border-bottom:1px solid #edf0f4;text-align:left;background:none;font-size:12px}.record:hover{background:#f8fafc}.bar{display:flex;align-items:center;justify-content:space-between}.cards{display:grid;align-content:start;gap:0}.cards>article{display:grid;grid-template-columns:minmax(0,1fr) repeat(4,auto);align-items:center;gap:10px;padding:14px;border-bottom:1px solid #e2e8f0}.cards p{margin:4px 0;overflow:hidden;color:#475569;text-overflow:ellipsis;white-space:nowrap}.jobs>article{grid-template-columns:minmax(0,1fr) auto 150px auto}.job-actions{display:flex}.workflow-meta{display:grid;grid-template-columns:1fr 1fr;gap:12px}.step-list{display:grid;gap:10px;max-height:55vh;overflow:auto;margin-bottom:12px}.step-list>article{display:grid;gap:10px;padding:14px;border:1px solid #e2e8f0;border-radius:6px}.step-list header{display:grid;grid-template-columns:1fr 160px 32px;align-items:center;gap:10px}@media(max-width:760px){.page{height:calc(100vh - 80px);padding:12px}.page>header{display:block}.page header>div:last-child{margin-top:12px}.metrics{grid-template-columns:1fr 1fr}.record{grid-template-columns:1fr 1fr}.record code,.record span:nth-child(4){display:none}.cards>article,.jobs>article{grid-template-columns:minmax(0,1fr) auto}.cards>article>div:first-child{grid-column:1/-1}.workflow-meta{grid-template-columns:1fr}}
.page.embedded{height:auto;min-height:0;flex:1;padding:0;background:transparent}.embedded-actions{display:flex;justify-content:flex-end;max-width:1160px;margin:12px auto -8px}
</style>
