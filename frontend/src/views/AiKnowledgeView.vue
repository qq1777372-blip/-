<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { Delete, Plus, RefreshRight, Search, Upload, View } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import { useRoute } from 'vue-router'

type Row = Record<string, any>
defineProps<{ embedded?: boolean }>()
const auth = useAuthStore()
const route = useRoute()
const collections = ref<Row[]>([])
const files = ref<Row[]>([])
const selected = ref('')
const loading = ref(false)
const uploadInput = ref<HTMLInputElement | null>(null)
const detailVisible = ref(false)
const detailFile = ref<Row | null>(null)
const detailChunks = ref<Row[]>([])
const query = ref('')
const searchQuery = ref('')
const searchResults = ref<Row[]>([])
const searching = ref(false)
const page = ref(1)
const pageSize = ref(10)
const filteredFiles = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  return files.value.filter(item => (!selected.value || item.knowledge_id === selected.value) && (!keyword || `${item.name} ${item.source || ''}`.toLowerCase().includes(keyword)))
})
const visibleFiles = computed(() => filteredFiles.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
watch([selected, query, pageSize], () => { page.value = 1 })

async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/ai-api/${path}`, { credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-Workspace-User': String(auth.currentUser?.id || 'local'), 'X-Workspace-Role': String(auth.currentUser?.role || 'user') }, ...init })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.error || `请求失败 (${response.status})`)
  return data
}

async function load() {
  loading.value = true
  try {
    const [knowledge, documents] = await Promise.all([api<{ knowledge: Row[] }>('knowledge'), api<{ files: Row[] }>('files')])
    collections.value = knowledge.knowledge || []
    files.value = documents.files || []
    const requestedFile = String(route.query.file || '')
    if (requestedFile && !detailVisible.value) {
      const file = files.value.find(item => item.id === requestedFile)
      if (file) await openDetail(file)
    }
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '知识库加载失败') }
  finally { loading.value = false }
}

async function createCollection() {
  const result = await ElMessageBox.prompt('输入知识库名称', '新建知识库', { confirmButtonText: '创建', cancelButtonText: '取消' }).catch(() => null)
  if (!result?.value?.trim()) return
  await api('knowledge', { method: 'POST', body: JSON.stringify({ name: result.value.trim() }) })
  await load(); ElMessage.success('知识库已创建')
}

async function upload(event: Event) {
  const input = event.target as HTMLInputElement; const selectedFiles = [...(input.files || [])]; input.value = ''
  if (!selectedFiles.length) return
  loading.value = true
  try {
    for (const file of selectedFiles) {
      if (file.size > 15_000_000) throw new Error(`${file.name} 超过 15MB`)
      const encoded = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result || '').split(',', 2)[1] || ''); reader.onerror = () => reject(new Error(`${file.name} 读取失败`)); reader.readAsDataURL(file) })
      const result = await api<{ file: Row }>('documents/import-file', { method: 'POST', body: JSON.stringify({ filename: file.name, data: encoded }) })
      if (selected.value) await api('files/assign', { method: 'POST', body: JSON.stringify({ file_id: result.file.id, knowledge_id: selected.value }) })
    }
    await load(); ElMessage.success(`已导入 ${selectedFiles.length} 个文件`)
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '文件导入失败') }
  finally { loading.value = false }
}

async function assign(file: Row, knowledgeId: string) { await api('files/assign', { method: 'POST', body: JSON.stringify({ file_id: file.id, knowledge_id: knowledgeId }) }); file.knowledge_id = knowledgeId; ElMessage.success('归属已更新') }
async function openDetail(file: Row) { const result = await api<{file:Row;chunks:Row[]}>(`files/detail?id=${encodeURIComponent(file.id)}`); detailFile.value = result.file; detailChunks.value = result.chunks || []; detailVisible.value = true; await nextTick(); const chunk = String(route.query.chunk || ''); if (chunk) document.getElementById(`chunk-${chunk}`)?.scrollIntoView({ block: 'center' }) }
function assetUrl(path:string) { return `/ai-api/files/asset?path=${encodeURIComponent(path)}` }
async function reprocess(file: Row) { loading.value = true; try { await api('files/reprocess', { method: 'POST', body: JSON.stringify({ id: file.id }) }); await load(); ElMessage.success(file.status === 'pending-ocr' ? 'OCR 已完成' : '文件已重新解析') } catch (error) { ElMessage.error(error instanceof Error ? error.message : '重新处理失败') } finally { loading.value = false } }
async function testSearch() { if (!searchQuery.value.trim()) return; searching.value = true; try { const result = await api<{documents:Row[]}>('search', { method: 'POST', body: JSON.stringify({ query: searchQuery.value.trim(), knowledge_id: selected.value || undefined, limit: 10 }) }); searchResults.value = result.documents || [] } catch (error) { ElMessage.error(error instanceof Error ? error.message : '检索失败') } finally { searching.value = false } }
async function openSearchResult(result: Row) { const file = files.value.find(item => item.id === result.id); if (file) await openDetail(file) }
async function removeFile(file: Row) { await ElMessageBox.confirm(`删除“${file.name}”？`, '删除文件', { type: 'warning' }); await api('files/delete', { method: 'POST', body: JSON.stringify({ id: file.id }) }); await load() }
async function removeCollection(item: Row) { await ElMessageBox.confirm(`删除知识库“${item.name}”？文件将保留但解除归属。`, '删除知识库', { type: 'warning' }); await api('knowledge/delete', { method: 'POST', body: JSON.stringify({ id: item.id }) }); if (selected.value === item.id) selected.value = ''; await load() }
onMounted(load)
</script>

<template>
  <section class="knowledge-page" :class="{ embedded }">
    <header v-if="!embedded"><div><small>AI WORKSPACE</small><h1>知识库</h1><p>管理用于 AI 检索与引用的资料集合</p></div><div><el-button @click="$router.push('/ai-workspace')">返回聊天</el-button><el-button :icon="Plus" @click="createCollection">新建知识库</el-button><el-button type="primary" :icon="Upload" :loading="loading" @click="uploadInput?.click()">导入文件</el-button></div></header>
    <div v-if="embedded" class="embedded-toolbar"><el-button :icon="Plus" @click="createCollection">新建知识库</el-button><el-button type="primary" :icon="Upload" :loading="loading" @click="uploadInput?.click()">导入文件</el-button></div>
    <input ref="uploadInput" hidden multiple type="file" accept=".pdf,.docx,.txt,.md,.markdown,.csv,.json,.png,.jpg,.jpeg,.webp" @change="upload">
    <div class="layout">
      <aside><button :class="{active:!selected}" @click="selected=''">全部文件 <b>{{files.length}}</b></button><button v-for="item in collections" :key="item.id" :class="{active:selected===item.id}" @click="selected=item.id"><span><strong>{{item.name}}</strong><small>{{files.filter(file=>file.knowledge_id===item.id).length}} 个文件</small></span><el-icon @click.stop="removeCollection(item)"><Delete/></el-icon></button></aside>
      <main>
        <div class="list-toolbar"><el-input v-model="query" clearable :prefix-icon="Search" placeholder="搜索文件名称或来源"/><el-input v-model="searchQuery" clearable placeholder="测试知识检索" @keyup.enter="testSearch"/><el-button :loading="searching" @click="testSearch">检索测试</el-button><span>共 <b>{{filteredFiles.length}}</b> 条</span></div>
        <div v-if="searchResults.length" class="search-results"><button v-for="result in searchResults" :key="result.chunk_id || result.id" @click="openSearchResult(result)"><b>{{result.title}}</b><span>{{result.content}}</span><small>匹配度 {{Math.round(Number(result.score || 0) * 100)}}%</small></button><el-button text @click="searchResults=[]">清除结果</el-button></div>
        <div class="table-head"><span>文件</span><span>状态</span><span>知识库</span><span>操作</span></div>
        <div class="file-list"><div v-for="file in visibleFiles" :key="file.id" class="file-row"><div class="file-name" @click="openDetail(file)"><strong>{{file.name}}</strong><small>{{new Date(file.created_at*1000).toLocaleString()}}<template v-if="file.image_count"> · {{file.image_count}} 张图片</template></small></div><el-tag :type="file.status==='ready'?'success':file.status==='pending-ocr'?'warning':'info'">{{file.status==='ready'?'可检索':file.status==='pending-ocr'?'等待 OCR':file.status}}</el-tag><el-select :model-value="file.knowledge_id||''" clearable placeholder="未归类" @change="(value:string)=>assign(file,value)"><el-option v-for="item in collections" :key="item.id" :label="item.name" :value="item.id"/></el-select><div class="file-actions"><el-button :icon="RefreshRight" circle text :title="file.status==='pending-ocr'?'执行 OCR':'重新解析'" @click="reprocess(file)"/><el-button :icon="View" circle text title="查看" @click="openDetail(file)"/><el-button :icon="Delete" circle text type="danger" title="删除" @click="removeFile(file)"/></div></div><div v-if="!visibleFiles.length" class="empty">没有符合条件的文件</div></div>
        <div class="pagination-bar"><span>共 {{filteredFiles.length}} 条 · 第 {{page}} / {{Math.max(1,Math.ceil(filteredFiles.length/pageSize))}} 页</span><el-pagination v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[10,20,50,100]" :total="filteredFiles.length" layout="sizes, prev, pager, next" background/></div>
      </main>
    </div>
    <el-dialog v-model="detailVisible" :title="detailFile?.name||'文档详情'" width="min(920px,92vw)" top="5vh" class="knowledge-detail"><div v-if="detailFile" class="detail-body"><a v-if="detailFile.source" :href="detailFile.source" target="_blank" rel="noopener">查看原始来源</a><div v-if="detailFile.metadata?.blocks?.length" class="document-flow"><template v-for="(block,index) in detailFile.metadata.blocks" :key="index"><p v-if="block.type==='text'">{{block.text}}</p><el-image v-else-if="block.type==='image'" :src="assetUrl(block.path)" :preview-src-list="detailFile.metadata.images.map((item:Row)=>assetUrl(item.path))" fit="contain" lazy/></template></div><template v-else><div v-if="detailFile.metadata?.images?.length" class="image-gallery"><el-image v-for="image in detailFile.metadata.images" :key="image.path" :src="assetUrl(image.path)" :preview-src-list="detailFile.metadata.images.map((item:Row)=>assetUrl(item.path))" fit="cover" lazy/></div><pre>{{detailFile.content}}</pre></template><details v-if="detailChunks.length" class="chunk-list"><summary>检索分块（{{detailChunks.length}}）</summary><article v-for="chunk in detailChunks" :id="`chunk-${chunk.id}`" :key="chunk.id"><b>分块 {{chunk.chunk_index+1}}</b><p>{{chunk.content}}</p></article></details></div></el-dialog>
  </section>
</template>

<style scoped>
.knowledge-page{display:flex;flex-direction:column;width:100%;height:calc(100vh - 104px);min-height:0;overflow:hidden;padding:18px 10px;background:#fff}.knowledge-page>header{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;width:100%;max-width:none;margin:0 0 18px}.knowledge-page header>div:last-child{display:flex;gap:8px}.knowledge-page small{color:var(--brand-primary);font-size:10px;font-weight:700}.knowledge-page h1{margin:5px 0;font-size:26px}.knowledge-page p{margin:0;color:#64748b;font-size:12px}.layout{display:grid;grid-template-columns:230px minmax(0,1fr);width:100%;max-width:none;min-height:0;flex:1;margin:0;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden}.layout aside{min-height:0;overflow:auto;padding:10px;border-right:1px solid #e2e8f0;background:#f8fafc}.layout aside button{width:100%;display:flex;align-items:center;justify-content:space-between;padding:11px 10px;border:0;border-radius:6px;text-align:left;background:transparent}.layout aside button.active,.layout aside button:hover{background:#e9eef7}.layout aside strong,.layout aside small{display:block}.layout aside small{margin-top:3px;color:#94a3b8}.layout main{min-width:0;min-height:0}.table-head,.file-row{display:grid;grid-template-columns:minmax(260px,1fr) 100px 190px 120px;gap:12px;align-items:center;padding:12px 16px}.table-head{background:#f8fafc;color:#64748b;font-size:11px;font-weight:700}.file-row{border-top:1px solid #edf0f4}.file-row strong,.file-row small{display:block}.file-row small{margin-top:4px;color:#94a3b8;font-size:10px}.empty{padding:70px;text-align:center;color:#94a3b8}@media(max-width:800px){.knowledge-page{height:calc(100vh - 80px);padding:12px}.knowledge-page>header{display:block}.knowledge-page header>div:last-child{margin-top:14px;flex-wrap:wrap}.layout{grid-template-columns:1fr;overflow:auto}.layout aside{display:flex;min-height:auto;overflow:auto;border-right:0;border-bottom:1px solid #e2e8f0}.layout aside button{min-width:150px}.table-head{display:none}.file-row{grid-template-columns:minmax(0,1fr) 90px}.file-row .el-select{grid-column:1/-1}}
.knowledge-page.embedded{height:auto;min-height:0;flex:1;padding:14px 0 0;background:transparent}.embedded-toolbar{display:flex;justify-content:flex-end;gap:8px;margin-bottom:12px}
.file-name{min-width:0;cursor:pointer}.file-name:hover strong{color:var(--brand-primary)}.file-actions{display:flex}.image-gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px;margin:16px 0}.image-gallery .el-image{width:100%;aspect-ratio:4/3;border:1px solid #e2e8f0;border-radius:6px;background:#f8fafc}.detail-body>a{color:var(--brand-primary);font-size:12px}.detail-body pre{max-height:46vh;overflow:auto;padding:16px;border:1px solid #e2e8f0;border-radius:6px;white-space:pre-wrap;overflow-wrap:anywhere;background:#f8fafc;font:13px/1.7 inherit}
.document-flow{max-width:820px;margin:16px auto}.document-flow p{margin:0 0 14px;white-space:pre-wrap;overflow-wrap:anywhere;color:#334155;font-size:14px;line-height:1.8}.document-flow .el-image{display:block;max-width:100%;margin:10px auto 20px;border:1px solid #e2e8f0;border-radius:6px;background:#f8fafc}.document-flow .el-image :deep(img){width:auto;max-width:100%;height:auto;max-height:70vh}
.layout main{overflow:hidden}.file-list{min-height:0;flex:1;overflow:auto}.list-toolbar,.pagination-bar{flex:none}
.search-results{max-height:210px;overflow:auto;border-bottom:1px solid #e2e8f0;background:#f8fafc}.search-results button{width:100%;display:grid;grid-template-columns:180px minmax(0,1fr) 80px;gap:12px;padding:9px 16px;border:0;border-bottom:1px solid #edf0f4;text-align:left;background:transparent}.search-results span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.chunk-list{margin-top:20px}.chunk-list summary{cursor:pointer;font-weight:700}.chunk-list article{margin-top:10px;padding:12px;border-left:3px solid var(--brand-primary);background:#f8fafc}.chunk-list p{white-space:pre-wrap}.file-actions{min-width:108px}
.layout main{display:flex;flex-direction:column}.list-toolbar{display:flex;align-items:center;gap:16px;padding:14px 16px;border-bottom:1px solid #e2e8f0;background:#fff}.list-toolbar .el-input{max-width:460px}.list-toolbar>span{margin-left:auto;color:#64748b;font-size:12px}.list-toolbar b{color:var(--brand-primary)}.pagination-bar{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:auto;padding:14px 16px;border-top:1px solid #e2e8f0;background:#fff}.pagination-bar>span{color:#64748b;font-size:11px}:deep(.knowledge-detail){height:90vh;display:flex;flex-direction:column;margin-bottom:0}:deep(.knowledge-detail .el-dialog__header){flex:none;margin:0;padding:18px 22px;border-bottom:1px solid #e2e8f0}:deep(.knowledge-detail .el-dialog__body){min-height:0;flex:1;overflow:auto;padding:18px 22px}.detail-body{min-height:100%}
@media(max-width:800px){.list-toolbar{align-items:stretch;flex-direction:column}.list-toolbar .el-input{max-width:none}.list-toolbar>span{margin-left:0}.pagination-bar{align-items:flex-start;flex-direction:column}:deep(.knowledge-detail){height:94vh;width:96vw!important}.pagination-bar .el-pagination{max-width:100%;overflow:auto}}
</style>
