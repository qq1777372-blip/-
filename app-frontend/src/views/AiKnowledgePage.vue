<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
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
  attachOutline,
  documentTextOutline,
  eyeOutline,
  refreshOutline,
  trashOutline,
} from "ionicons/icons";
import PageHeader from "../components/PageHeader.vue";
import { session } from "../session";
import { apiUrl } from "../runtime";

type Collection = { id: string; name: string; description?: string };
type KnowledgeFile = {
  id: string;
  name: string;
  knowledge_id?: string;
  status?: string;
  created_at?: number;
  metadata?: { images?: Array<{ path: string }>; blocks?: Array<Record<string, any>> };
  content?: string;
};

const route = useRoute();
const collections = ref<Collection[]>([]);
const files = ref<KnowledgeFile[]>([]);
const name = ref("");
const loading = ref(false);
const uploading = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);
const detailOpen=ref(false),detail=ref<{file?:KnowledgeFile;chunks?:Array<{id:string;chunk_index:number;content:string}>}>({}),selectedCollection=ref(""),fileQuery=ref(""),searchQuery=ref(""),searchResults=ref<Array<{id:string;title:string;content?:string;chunk_id?:string}>>([]),searching=ref(false),page=ref(1),pageSize=ref(10);
const filteredFiles=computed(()=>{const q=fileQuery.value.trim().toLowerCase();return files.value.filter(file=>(!selectedCollection.value||file.knowledge_id===selectedCollection.value)&&(!q||`${file.name} ${(file as any).source||""}`.toLowerCase().includes(q)))});
const visibleFiles=computed(()=>filteredFiles.value.slice((page.value-1)*pageSize.value,page.value*pageSize.value));
watch([pageSize,selectedCollection,fileQuery],()=>{page.value=1});
watch(()=>filteredFiles.value.length,total=>{page.value=Math.min(page.value,Math.max(1,Math.ceil(total/pageSize.value)))});

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/ai-api/${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Workspace-User": String(session.user?.id || "local"),
      "X-Workspace-Role": session.user?.role || "user",
    },
    ...init,
  });
  const data = (await response.json().catch(() => ({}))) as T & {
    error?: string;
    detail?: string;
  };
  if (!response.ok)
    throw new Error(
      data.error || data.detail || `请求失败（${response.status}）`,
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
    const [knowledge, fileResult] = await Promise.all([
      api<{ knowledge: Collection[] }>("knowledge"),
      api<{ files: KnowledgeFile[] }>("files"),
    ]);
    collections.value = knowledge.knowledge || [];
    files.value = fileResult.files || [];
    const requested=String(route.query.file||"");
    if(requested&&!detailOpen.value){const file=files.value.find(item=>item.id===requested);if(file)await preview(file,String(route.query.chunk||""))}
  } catch (error) {
    await notify(error instanceof Error ? error.message : "知识库读取失败");
  } finally {
    loading.value = false;
  }
}
async function createCollection() {
  const value = name.value.trim();
  if (!value) return;
  try {
    await api("knowledge", {
      method: "POST",
      body: JSON.stringify({ name: value }),
    });
    name.value = "";
    await load();
    await notify("知识集合已创建");
  } catch (error) {
    await notify(error instanceof Error ? error.message : "创建失败");
  }
}
async function assign(file: KnowledgeFile, knowledgeId: string) {
  try {
    await api("files/assign", {
      method: "POST",
      body: JSON.stringify({ file_id: file.id, knowledge_id: knowledgeId }),
    });
    file.knowledge_id = knowledgeId;
    await notify("文件归属已更新");
  } catch (error) {
    await notify(error instanceof Error ? error.message : "更新失败");
  }
}
async function reprocess(file: KnowledgeFile) {
  try {
    await api("files/reprocess", {
      method: "POST",
      body: JSON.stringify({ id: file.id }),
    });
    await load();
    await notify("文件已重新解析");
  } catch (error) {
    await notify(error instanceof Error ? error.message : "重新解析失败");
  }
}
async function preview(file:KnowledgeFile,chunkId=""){try{detail.value=await api(`files/detail?id=${encodeURIComponent(file.id)}`);detailOpen.value=true;await nextTick();if(chunkId)document.getElementById(`app-chunk-${chunkId}`)?.scrollIntoView({block:"center"})}catch(error){await notify(error instanceof Error?error.message:"读取详情失败")}}
async function openSearchResult(item:{id:string;chunk_id?:string}){const file=files.value.find(row=>row.id===item.id);if(file)await preview(file,item.chunk_id||"")}
function assetUrl(path:string){return apiUrl(`/ai-api/files/asset?path=${encodeURIComponent(path)}`)}
async function testSearch(){const query=searchQuery.value.trim();if(!query)return;searching.value=true;try{const result=await api<{documents:Array<{id:string;title:string;content?:string}>}>("search",{method:"POST",body:JSON.stringify({query,knowledge_id:selectedCollection.value||undefined,limit:10})});searchResults.value=result.documents||[]}catch(error){await notify(error instanceof Error?error.message:"检索失败")}finally{searching.value=false}}
async function remove(kind: "files" | "knowledge", id: string) {
  if (
    !confirm(
      kind === "files"
        ? "确定删除这个文件？"
        : "确定删除这个知识集合？集合内文件不会被删除。",
    )
  )
    return;
  try {
    await api(`${kind}/delete`, {
      method: "POST",
      body: JSON.stringify({ id }),
    });
    await load();
    await notify("已删除");
  } catch (error) {
    await notify(error instanceof Error ? error.message : "删除失败");
  }
}
async function importFiles(event: Event) {
  const input = event.target as HTMLInputElement,
    selected = [...(input.files || [])];
  input.value = "";
  if (!selected.length) return;
  uploading.value = true;
  try {
    for (const file of selected) {
      if (file.size > 15_000_000) throw new Error(`${file.name} 超过 15MB`);
      const data = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () =>
          resolve(String(reader.result || "").split(",", 2)[1] || "");
        reader.onerror = () => reject(new Error(`${file.name} 读取失败`));
        reader.readAsDataURL(file);
      });
      const result=await api<{file:KnowledgeFile}>("documents/import-file", {
        method: "POST",
        body: JSON.stringify({
          title: file.name.replace(/\.[^.]+$/, ""),
          filename: file.name,
          data,
        }),
      });
      if(selectedCollection.value&&result.file?.id)await api("files/assign",{method:"POST",body:JSON.stringify({file_id:result.file.id,knowledge_id:selectedCollection.value})});
    }
    await load();
    await notify(`已导入 ${selected.length} 个文件`);
  } catch (error) {
    await notify(error instanceof Error ? error.message : "导入失败");
  } finally {
    uploading.value = false;
  }
}
onMounted(load);
</script>

<template>
  <IonPage>
    <PageHeader title="AI 知识库" subtitle="管理聊天检索使用的资料" back />
    <IonContent>
      <main class="knowledge-page">
        <section class="create-row">
          <input
            v-model="name"
            placeholder="新建知识集合"
            @keyup.enter="createCollection"
          /><IonButton :disabled="!name.trim()" @click="createCollection"
            ><IonIcon :icon="addOutline" />创建</IonButton
          >
        </section>
        <section>
          <header><div><b>检索测试</b><small>{{searchResults.length}} 条结果</small></div></header>
          <select v-model="selectedCollection" class="collection-filter"><option value="">全部知识集合</option><option v-for="item in collections" :key="item.id" :value="item.id">{{item.name}}</option></select>
          <div class="search-test"><input v-model="searchQuery" placeholder="输入关键词验证知识库召回" @keyup.enter="testSearch"><IonButton :disabled="searching||!searchQuery.trim()" @click="testSearch"><IonSpinner v-if="searching" name="dots"/>检索</IonButton></div>
          <article v-for="item in searchResults" :key="item.chunk_id||item.id" class="search-result" @click="openSearchResult(item)"><div><b>{{item.title}}</b><small>{{item.content||'暂无摘要'}}</small></div></article>
        </section>
        <section>
          <header>
            <div>
              <b>知识集合</b><small>{{ collections.length }}</small>
            </div>
          </header>
          <input v-model="fileQuery" class="file-search" placeholder="搜索文件名称或来源">
          <div v-if="!collections.length && !loading" class="empty">
            暂无知识集合
          </div>
          <article v-for="item in collections" :key="item.id">
            <div>
              <b>{{ item.name }}</b
              ><small>{{ item.description || "用于限定聊天检索范围" }}</small>
            </div>
            <button aria-label="删除集合" @click="remove('knowledge', item.id)">
              <IonIcon :icon="trashOutline" />
            </button>
          </article>
        </section>
        <section>
          <header>
            <div>
              <b>资料文件</b><small>{{ files.length }}</small>
            </div>
            <input
              ref="fileInput"
              hidden
              type="file"
              multiple
              accept=".pdf,.docx,.txt,.md,.markdown,.csv,.json,.png,.jpg,.jpeg,.webp"
              @change="importFiles"
            /><IonButton
              size="small"
              fill="outline"
              :disabled="uploading"
              @click="fileInput?.click()"
              ><IonSpinner v-if="uploading" name="dots" /><IonIcon
                v-else
                :icon="attachOutline"
              />上传</IonButton
            >
          </header>
          <div v-if="loading" class="empty"><IonSpinner name="dots" /></div>
          <div v-else-if="!filteredFiles.length" class="empty">没有符合条件的资料文件</div>
          <article v-for="file in visibleFiles" :key="file.id" class="file">
            <span><IonIcon :icon="documentTextOutline" /></span>
            <div>
              <b>{{ file.name }}</b
              ><small>{{
                file.status === "ready" ? "解析完成" : "等待解析"
              }}</small
              ><select
                :value="file.knowledge_id || ''"
                @change="
                  assign(file, ($event.target as HTMLSelectElement).value)
                "
              >
                <option value="">未分组</option>
                <option
                  v-for="item in collections"
                  :key="item.id"
                  :value="item.id"
                >
                  {{ item.name }}
                </option>
              </select>
            </div>
            <button aria-label="预览文件" @click="preview(file)"><IonIcon :icon="eyeOutline"/></button>
            <button aria-label="重新解析" @click="reprocess(file)">
              <IonIcon :icon="refreshOutline" /></button
            ><button
              aria-label="删除文件"
              class="danger"
              @click="remove('files', file.id)"
            >
              <IonIcon :icon="trashOutline" />
            </button>
          </article>
          <div class="pager"><span>共 {{filteredFiles.length}} 个文件</span><select v-model.number="pageSize"><option :value="10">10/页</option><option :value="20">20/页</option><option :value="50">50/页</option></select><button :disabled="page<=1" @click="page--">上一页</button><b>{{page}}/{{Math.max(1,Math.ceil(filteredFiles.length/pageSize))}}</b><button :disabled="page>=Math.ceil(filteredFiles.length/pageSize)" @click="page++">下一页</button></div>
        </section>
      </main>
    </IonContent>
    <div v-if="detailOpen" class="mask" @click.self="detailOpen=false"><section class="detail"><header><b>{{detail.file?.name}}</b><button @click="detailOpen=false">关闭</button></header><nav v-if="detail.file?.metadata?.images?.length"><b>文档图片（{{detail.file.metadata.images.length}}）</b><div class="detail-images"><a v-for="image in detail.file.metadata.images" :key="image.path" :href="assetUrl(image.path)" target="_blank"><img :src="assetUrl(image.path)" alt="文档图片"></a></div></nav><nav><b>解析原文</b><pre>{{detail.file?.content||'暂无可预览文本；图片文件可点击重新解析执行 OCR。'}}</pre></nav><nav><b>分块（{{detail.chunks?.length||0}}）</b><article v-for="chunk in detail.chunks||[]" :id="`app-chunk-${chunk.id}`" :key="chunk.id"><small>#{{chunk.chunk_index+1}}</small><p>{{chunk.content}}</p></article></nav></section></div>
  </IonPage>
</template>

<style scoped>
.knowledge-page {
  display: grid;
  gap: 14px;
  padding: 14px 12px 28px;
}
.collection-filter,.file-search{width:calc(100% - 24px);height:40px;margin:10px 12px 0;padding:0 10px;border:1px solid var(--app-line);border-radius:7px;color:var(--app-text);background:var(--app-card)}
.create-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--app-line);
  border-radius: 8px;
  background: var(--app-card);
}
input,
select {
  height: 40px;
  padding: 0 10px;
  border: 1px solid var(--app-line);
  border-radius: 6px;
  color: var(--app-text);
  background: var(--ion-background-color);
  font: inherit;
}
.create-row ion-button {
  height: 40px;
  margin: 0;
  --border-radius: 6px;
}
section {
  overflow: hidden;
  border: 1px solid var(--app-line);
  border-radius: 8px;
  background: var(--app-card);
}
section > header {
  min-height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--app-line);
}
header div {
  display: flex;
  align-items: center;
  gap: 7px;
}
header small {
  color: var(--app-muted);
}
article {
  min-height: 62px;
  display: grid;
  grid-template-columns: 1fr 34px;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  border-bottom: 1px solid var(--app-line);
}
article:last-child {
  border-bottom: 0;
}
article > div {
  display: grid;
  min-width: 0;
}
article b {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}
article small {
  margin-top: 4px;
  color: var(--app-muted);
  font-size: 10px;
}
article > button {
  width: 34px;
  height: 34px;
  border: 0;
  color: #ef4444;
  background: transparent;
  font-size: 18px;
}
.file {
  grid-template-columns: 34px 1fr 34px 34px 34px;
}
.file > span {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: 6px;
  color: #1677ff;
  background: color-mix(in srgb, #1677ff 10%, var(--app-card));
  font-size: 18px;
}
.file select {
  height: 34px;
  margin-top: 7px;
  font-size: 11px;
}
.file > button {
  color: #1677ff;
}
.file > button.danger {
  color: #ef4444;
}
.empty {
  padding: 28px;
  text-align: center;
  color: var(--app-muted);
  font-size: 12px;
}
.search-test{display:grid;grid-template-columns:1fr auto;gap:7px;padding:9px}.search-test ion-button{height:40px;margin:0}.search-result{cursor:pointer}.pager{display:flex;align-items:center;gap:6px;padding:10px}.pager span{margin-right:auto;color:var(--app-muted);font-size:10px}.pager select,.pager button{height:32px;border:1px solid var(--app-line);border-radius:6px;color:var(--app-text);background:var(--app-card);font-size:10px}.pager button:disabled{opacity:.35}.mask{position:fixed;z-index:1100;inset:0;display:flex;align-items:flex-end;background:#0f172a66}.detail{width:100%;max-height:88vh;overflow:auto;padding:14px 14px calc(20px + env(safe-area-inset-bottom));border-radius:8px 8px 0 0;background:var(--app-card)}.detail>header{display:flex;justify-content:space-between;margin-bottom:12px}.detail>header button{border:0;color:var(--app-muted);background:transparent}.detail nav{display:grid;gap:7px;margin-top:14px}.detail pre{max-height:230px;overflow:auto;margin:0;padding:10px;border-radius:6px;white-space:pre-wrap;overflow-wrap:anywhere;background:var(--ion-background-color);font:11px/1.6 monospace}.detail nav article{display:block;margin:0;padding:9px;border:1px solid var(--app-line);border-radius:6px}.detail nav p{margin:4px 0;white-space:pre-wrap;font-size:11px;line-height:1.55}.detail nav small{color:#1677ff}.detail-images{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}.detail-images img{display:block;width:100%;aspect-ratio:4/3;object-fit:contain;border:1px solid var(--app-line);border-radius:6px;background:var(--ion-background-color)}
</style>
