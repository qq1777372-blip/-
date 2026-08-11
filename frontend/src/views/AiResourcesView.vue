<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { Delete, EditPen, Plus, Refresh, Search, VideoPlay } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

type Row = Record<string, any>
type ResourceKind = 'prompts' | 'skills' | 'tools' | 'notes' | 'shares'
const props = defineProps<{ embedded?: boolean; initialKind?: ResourceKind }>()

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const resourceKinds: ResourceKind[] = ['prompts', 'skills', 'tools', 'notes', 'shares']
const active = ref<ResourceKind>(props.initialKind || (resourceKinds.includes(String(route.query.tab) as ResourceKind) ? String(route.query.tab) as ResourceKind : 'prompts'))
const loading = ref(false)
const query = ref('')
const page = ref(1)
const pageSize = ref(10)
const rows = reactive<Record<ResourceKind, Row[]>>({ prompts: [], skills: [], tools: [], notes: [], shares: [] })
const editorVisible = ref(false)
const editing = ref<Row | null>(null)
const form = reactive({ command: '', title: '', name: '', description: '', content: '', kind: 'custom', enabled: true, url: '', method: 'POST', headers: '{}' })

const tabs: Array<{ value: ResourceKind; label: string }> = [
  { value: 'prompts', label: 'Prompts' }, { value: 'skills', label: 'Skills' },
  { value: 'tools', label: 'Tools' }, { value: 'notes', label: 'Notes' }, { value: 'shares', label: '分享管理' },
]
const filtered = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  return rows[active.value].filter(item => !keyword || `${item.command || ''} ${item.title || ''} ${item.name || ''} ${item.description || ''} ${item.content || ''}`.toLowerCase().includes(keyword))
})
const visibleRows = computed(() => filtered.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
const resourceTitle = computed(() => tabs.find(item => item.value === active.value)?.label || '')
watch(() => route.query.tab, value => { if (resourceKinds.includes(String(value) as ResourceKind)) active.value = String(value) as ResourceKind })
watch(() => props.initialKind, value => { if (value) { active.value = value; query.value = '' } })
watch([query, active, pageSize], () => { page.value = 1 })
watch(() => filtered.value.length, total => { page.value = Math.min(page.value, Math.max(1, Math.ceil(total / pageSize.value))) })
function selectResource(value: ResourceKind) { active.value = value; query.value = ''; page.value = 1; if (!props.embedded) void router.replace({ query: { ...route.query, tab: value } }) }

async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/ai-api/${path}`, { credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-Workspace-User': String(auth.currentUser?.id || 'local'), 'X-Workspace-Role': String(auth.currentUser?.role || 'user') }, ...init })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.error || `请求失败 (${response.status})`)
  return data
}

async function load() {
  loading.value = true
  try {
    const [prompts, skills, tools, notes, shares] = await Promise.all([
      api<{ prompts: Row[] }>('prompts'), api<{ skills: Row[] }>('skills'), api<{ tools: Row[] }>('tools?all=1'),
      api<{ notes: Row[] }>('notes'), api<{ shares: Row[] }>('shares'),
    ])
    rows.prompts = prompts.prompts || []; rows.skills = skills.skills || []; rows.tools = tools.tools || []
    rows.notes = notes.notes || []; rows.shares = shares.shares || []
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '工作空间加载失败') }
  finally { loading.value = false }
}

function resetForm() {
  Object.assign(form, { command: '', title: '', name: '', description: '', content: '', kind: 'custom', enabled: true, url: '', method: 'POST', headers: '{}' })
}
function openEditor(row?: Row) {
  resetForm(); editing.value = row || null
  if (row) {
    let config: Row = {}; try { config = JSON.parse(row.config || '{}') } catch { config = {} }
    Object.assign(form, row, { enabled: Boolean(row.enabled), url: config.url || '', method: config.method || 'POST', headers: JSON.stringify(config.headers || {}, null, 2) })
  }
  editorVisible.value = true
}
async function save() {
  const kind = active.value
  if (kind === 'shares') return
  try {
    const payload: Row = { id: editing.value?.id }
    if (kind === 'prompts') Object.assign(payload, { command: form.command, title: form.title, content: form.content })
    if (kind === 'skills') Object.assign(payload, { name: form.name, description: form.description, content: form.content })
    if (kind === 'notes') Object.assign(payload, { title: form.title, content: form.content })
    if (kind === 'tools') {
      let headers: Row = {}; try { headers = JSON.parse(form.headers || '{}') } catch { throw new Error('请求头必须是有效 JSON') }
      Object.assign(payload, { name: form.name, description: form.description, kind: form.kind, enabled: form.enabled, config: form.kind === 'http' ? { url: form.url, method: form.method, headers } : {} })
    }
    await api(editing.value ? `${kind}/update` : kind, { method: 'POST', body: JSON.stringify(payload) })
    editorVisible.value = false; await load(); ElMessage.success(editing.value ? '已保存' : '已创建')
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '保存失败') }
}
async function remove(row: Row) {
  const label = row.title || row.name || row.command || row.id
  await ElMessageBox.confirm(`删除“${label}”？`, '确认删除', { type: 'warning' })
  await api(`${active.value}/delete`, { method: 'POST', body: JSON.stringify({ id: row.id }) }); await load()
}
async function testTool(row: Row) {
  try { const result = await api<Row>('tools/test', { method: 'POST', body: JSON.stringify({ id: row.id, arguments: row.kind === 'calculator' ? { expression: '6*7' } : {} }) }); ElMessageBox.alert(String(result.result || '执行成功'), '工具测试') }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : '测试失败') }
}
async function revoke(row: Row) {
  await ElMessageBox.confirm(`撤销分享“${row.title}”？`, '撤销分享', { type: 'warning' })
  await api('shares/revoke', { method: 'POST', body: JSON.stringify({ id: row.id }) }); await load()
}
onMounted(load)
</script>

<template>
  <section class="resource-page" :class="{ embedded }">
    <header v-if="!embedded"><div><small>AI WORKSPACE</small><h1>工作空间</h1></div><div><el-button @click="router.push('/ai-workspace')">返回聊天</el-button><el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button></div></header>
    <nav v-if="!embedded" class="primary-nav"><button @click="router.push('/ai-workspace/models')">模型</button><button v-for="tab in tabs" :key="tab.value" :class="{ active: active === tab.value }" @click="selectResource(tab.value)">{{ tab.label }}</button></nav>
    <div class="toolbar"><el-input v-model="query" clearable :prefix-icon="Search" :placeholder="`搜索 ${resourceTitle}`"/><span>共 {{ filtered.length }} 项</span><el-button v-if="active !== 'shares'" type="primary" :icon="Plus" @click="openEditor()">新建</el-button></div>
    <div class="table-head"><span>名称</span><span>说明 / 内容</span><span>状态</span><span>更新时间</span><span>操作</span></div>
    <div class="resource-list">
      <article v-for="row in visibleRows" :key="row.id">
        <div><b>{{ row.title || row.name || row.command || '未命名' }}</b><small v-if="row.command">/{{ row.command }}</small></div>
        <p>{{ row.description || row.content || (row.revoked ? '该分享已撤销' : '共享会话') }}</p>
        <el-tag :type="row.revoked || row.enabled === 0 ? 'info' : 'success'">{{ row.revoked ? '已撤销' : row.enabled === 0 ? '已停用' : '可用' }}</el-tag>
        <small>{{ new Date((row.updated_at || row.created_at || 0) * 1000).toLocaleString() }}</small>
        <div class="actions"><el-button v-if="active === 'tools'" :icon="VideoPlay" circle text title="测试" @click="testTool(row)"/><el-button v-if="active !== 'shares' && !String(row.id).startsWith('builtin-')" :icon="EditPen" circle text title="编辑" @click="openEditor(row)"/><el-button v-if="active === 'shares' && !row.revoked" type="danger" text @click="revoke(row)">撤销</el-button><el-button v-else-if="active !== 'shares' && !String(row.id).startsWith('builtin-')" :icon="Delete" circle text type="danger" title="删除" @click="remove(row)"/></div>
      </article>
      <el-empty v-if="!filtered.length" description="暂无内容"/>
    </div>
    <div class="pagination-bar"><span>共 {{ filtered.length }} 项 · 第 {{ page }} / {{ Math.max(1, Math.ceil(filtered.length / pageSize)) }} 页</span><el-pagination v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[10,20,50]" :total="filtered.length" layout="sizes, prev, pager, next" background/></div>
    <el-dialog v-model="editorVisible" :title="`${editing ? '编辑' : '新建'} ${resourceTitle}`" width="min(680px, 94vw)" destroy-on-close>
      <el-form label-position="top">
        <template v-if="active === 'prompts'"><el-form-item label="命令"><el-input v-model="form.command"><template #prepend>/</template></el-input></el-form-item><el-form-item label="标题"><el-input v-model="form.title"/></el-form-item></template>
        <template v-if="active === 'skills' || active === 'tools'"><el-form-item label="名称"><el-input v-model="form.name"/></el-form-item><el-form-item label="说明"><el-input v-model="form.description"/></el-form-item></template>
        <template v-if="active === 'notes'"><el-form-item label="标题"><el-input v-model="form.title"/></el-form-item></template>
        <template v-if="active === 'tools'"><el-form-item label="类型"><el-select v-model="form.kind"><el-option label="自定义说明" value="custom"/><el-option label="HTTP API" value="http"/><el-option label="计算器" value="calculator"/><el-option label="当前时间" value="current_time"/></el-select></el-form-item><template v-if="form.kind === 'http'"><el-form-item label="接口地址"><el-input v-model="form.url" placeholder="https://api.example.com/tool"/></el-form-item><el-form-item label="请求方法"><el-select v-model="form.method"><el-option label="POST" value="POST"/><el-option label="GET" value="GET"/></el-select></el-form-item><el-form-item label="请求头 JSON"><el-input v-model="form.headers" type="textarea" :rows="4"/></el-form-item></template><el-form-item><el-switch v-model="form.enabled" active-text="启用"/></el-form-item></template>
        <el-form-item v-if="active !== 'tools'" label="内容"><el-input v-model="form.content" type="textarea" :rows="12"/></el-form-item>
      </el-form><template #footer><el-button @click="editorVisible = false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>
.resource-page{height:calc(100vh - 104px);min-height:0;display:flex;flex-direction:column;padding:18px 10px;background:#fff}.resource-page>header{display:flex;align-items:center;justify-content:space-between}.resource-page header>div:last-child,.actions{display:flex;gap:8px}.resource-page small{color:#64748b;font-size:11px}.resource-page h1{margin:5px 0;font-size:26px}.primary-nav{display:flex;gap:20px;margin-top:18px;border-bottom:1px solid #e2e8f0;overflow:auto}.primary-nav button{flex:none;padding:11px 2px;border:0;border-bottom:2px solid transparent;background:none}.primary-nav button.active{border-color:var(--brand-primary);color:var(--brand-primary)}.toolbar{display:flex;align-items:center;gap:12px;padding:14px 0}.toolbar .el-input{max-width:420px}.toolbar>span{margin-left:auto;color:#64748b;font-size:12px}.table-head,.resource-list article{display:grid;grid-template-columns:220px minmax(260px,1fr) 80px 170px 120px;gap:14px;align-items:center;padding:12px 16px}.table-head{background:#f8fafc;color:#64748b;font-size:11px;font-weight:700}.resource-list{min-height:0;flex:1;overflow:auto}.resource-list article{border-bottom:1px solid #edf0f4}.resource-list b,.resource-list article>div:first-child small{display:block}.resource-list p{overflow:hidden;margin:0;color:#475569;text-overflow:ellipsis;white-space:nowrap}.actions{justify-content:flex-end}.pagination-bar{display:flex;flex:none;align-items:center;justify-content:space-between;gap:16px;padding:14px 16px;border-top:1px solid #e2e8f0}.pagination-bar>span{color:#64748b;font-size:11px}@media(max-width:800px){.resource-page{height:calc(100vh - 80px);padding:12px}.resource-page>header{align-items:flex-start}.table-head{display:none}.resource-list article{grid-template-columns:minmax(0,1fr) auto}.resource-list article>p,.resource-list article>small{grid-column:1/-1}.toolbar{flex-wrap:wrap}.toolbar .el-input{max-width:none;flex-basis:100%}.toolbar>span{margin-left:0}.actions{grid-column:2;grid-row:1/3}.pagination-bar{align-items:flex-start;flex-direction:column}.pagination-bar .el-pagination{max-width:100%;overflow:auto}}
.resource-page.embedded{height:auto;min-height:0;flex:1;padding:0;background:transparent}
</style>
