<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { IonContent, IonIcon, IonPage, alertController, toastController } from '@ionic/vue'
import { copyOutline, createOutline, openOutline, trashOutline } from 'ionicons/icons'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import { api, ApiError } from '../api'
import { session } from '../session'
import type { SavedLink } from './LinkPlazaPage.vue'
// The editor preview uses this same parser, so preview and reader stay identical.
import { normalizePath, parseContent } from '../markdown'

const route=useRoute()
const router=useRouter()
const item=ref<SavedLink|null>(null)
const loading=ref(true)
const canEdit=computed(()=>session.user?.role==='superadmin'||item.value?.author_user_id===session.user?.id)
const contentBlocks=computed(()=>parseContent(item.value?.description,item.value?.title||'帖子图片'))
const referencedImages=computed(()=>new Set(contentBlocks.value.filter(block=>block.type==='image').map(block=>normalizePath(block.src))))
const remainingImages=computed(()=>item.value?.images?.filter(image=>!referencedImages.value.has(normalizePath(image.url)))||[])

async function load(){try{const rows=await api<SavedLink[]>('/saved-links');item.value=rows.find(row=>row.id===Number(route.params.id))||null}catch(error){const toast=await toastController.create({message:error instanceof ApiError?error.detail:'帖子加载失败',duration:2200,color:'danger'});await toast.present()}finally{loading.value=false}}
async function copyLink(){if(!item.value?.url)return;try{await navigator.clipboard.writeText(item.value.url);const toast=await toastController.create({message:'链接已复制',duration:1500});await toast.present()}catch{}}
function openLink(){if(item.value?.url)window.open(item.value.url,'_blank','noopener,noreferrer')}
function editItem(){if(!item.value)return;if(item.value.category?.toLowerCase().startsWith('tutorial:'))void router.push(`/tabs/form/articles/${item.value.id}`);else void router.push(`/tabs/form/links/${item.value.id}`)}
async function remove(){if(!item.value)return;const current=item.value;const alert=await alertController.create({header:'删除帖子',message:`确定删除“${current.title}”吗？`,buttons:[{text:'取消',role:'cancel'},{text:'删除',role:'destructive',handler:async()=>{try{await api(`/saved-links/${current.id}`,{method:'DELETE'});router.replace('/tabs/links')}catch(error){const toast=await toastController.create({message:error instanceof ApiError?error.detail:'删除失败',duration:2000,color:'danger'});await toast.present()}}}]});await alert.present()}
function host(url?:string){try{return url?new URL(url).hostname:''}catch{return ''}}
function time(value:string){return String(value||'').replace('T',' ').slice(0,16)}
function category(value?:string){const text=String(value||'').trim();return !text||text.toLowerCase().startsWith('tutorial:')?'未分类':text}
function pushLabel(value?:string){return value==='scheduled'?'已定时':value==='sending'?'推送中':value==='sent'?'已推送':value==='failed'?'推送失败':''}
onMounted(load)
</script>

<template>
  <IonPage>
    <PageHeader title="帖子详情" subtitle="链接广场" back />
    <IonContent>
      <main v-if="item" class="link-reader-page">
        <article class="link-reader-post">
          <header class="link-reader-author">
            <div class="link-reader-identity">
              <div><strong>{{ item.author_username }}</strong><span>{{ category(item.category) }}</span><em v-if="pushLabel(item.push_status)" :class="`status-${item.push_status}`">{{ pushLabel(item.push_status) }}</em></div>
              <small>{{ time(item.updated_at||item.created_at) }}<template v-if="item.url"> · {{ host(item.url) }}</template><template v-if="item.images?.length"> · {{ item.images.length }} 张图</template></small>
            </div>
          </header>

          <h1>{{ item.title }}</h1>
          <div v-if="contentBlocks.length" class="link-reader-content">
            <template v-for="(block,index) in contentBlocks" :key="index">
              <p v-if="block.type==='paragraph'" :class="`align-${block.align}`"><template v-for="(segment,segmentIndex) in block.segments" :key="segmentIndex"><a v-if="segment.type==='link'" :href="segment.value" target="_blank" rel="noopener noreferrer">{{ segment.label }}</a><span v-else>{{ segment.value }}</span></template></p>
              <figure v-else :class="`align-${block.align}`"><img :src="block.src" :alt="block.alt"></figure>
            </template>
          </div>

          <button v-if="item.url" class="link-reader-url" @click="openLink"><strong>{{ host(item.url) }}</strong><span>{{ item.url }}</span><IonIcon :icon="openOutline" /></button>
          <section v-if="remainingImages.length" class="link-reader-gallery"><img v-for="image in remainingImages" :key="image.storage_name" :src="image.url" :alt="image.name||item.title"></section>

          <footer class="link-reader-footer">
            <span>帖子 #{{ item.id }}</span>
            <div><button v-if="item.url" @click="copyLink"><IonIcon :icon="copyOutline" />复制链接</button><button v-if="canEdit" @click="editItem"><IonIcon :icon="createOutline" />编辑</button><button v-if="canEdit" class="danger" @click="remove"><IonIcon :icon="trashOutline" />删除</button></div>
          </footer>
        </article>
      </main>
      <div v-else-if="!loading" class="empty-state">帖子不存在或已删除</div>
    </IonContent>
  </IonPage>
</template>

<style scoped>
.link-reader-page{min-height:100%;padding:0 16px 44px;background:var(--app-card)}
.link-reader-post{max-width:720px;margin:0 auto;padding:16px 0}
.link-reader-author{display:flex;align-items:center;gap:9px;padding-bottom:12px;border-bottom:1px solid var(--app-line)}
.link-reader-avatar{width:30px;height:30px;flex:none;display:grid;place-items:center;overflow:hidden;border-radius:50%;color:#fff;background:linear-gradient(135deg,#2563eb,#0ea5e9);font-size:12px;font-weight:800}
.link-reader-avatar img{width:100%;height:100%;object-fit:cover}
.link-reader-identity{min-width:0;flex:1}.link-reader-identity>div{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.link-reader-identity strong{font-size:13px}.link-reader-identity span,.link-reader-identity em{padding:3px 7px;border-radius:999px;color:var(--app-muted);background:var(--app-soft);font-size:10px;font-style:normal}.link-reader-identity em.status-sent{color:#047857;background:#ecfdf5}.link-reader-identity em.status-failed{color:#b91c1c;background:#fef2f2}.link-reader-identity small{display:block;margin-top:3px;color:var(--app-muted);font-size:11px}
.link-reader-post h1{margin:16px 0 10px;color:var(--app-text);font-size:22px;line-height:1.4}
.link-reader-content{color:var(--app-text);overflow-wrap:anywhere;font-size:15px;line-height:1.75}.link-reader-content p{margin:0 0 13px;white-space:pre-wrap}.link-reader-content .align-left{text-align:left}.link-reader-content .align-center{text-align:center}.link-reader-content .align-right{text-align:right}.link-reader-content a{color:#1677ff;text-decoration:none}.link-reader-content figure{margin:12px 0}.link-reader-content figure img{display:block;max-width:100%;height:auto;border-radius:9px;background:var(--app-soft)}.link-reader-content figure.align-center img{margin-inline:auto}.link-reader-content figure.align-right img{margin-left:auto}
.link-reader-url{width:100%;margin-top:14px;padding:11px 38px 11px 12px;position:relative;display:grid;gap:3px;border:1px solid var(--app-line);border-radius:10px;text-align:left;color:var(--app-text);background:var(--app-soft);font:inherit}.link-reader-url strong{font-size:12px}.link-reader-url span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#1677ff;font-size:11px}.link-reader-url ion-icon{position:absolute;right:12px;top:50%;transform:translateY(-50%);color:#1677ff;font-size:18px}
.link-reader-gallery{display:grid;gap:8px;margin-top:14px}.link-reader-gallery img{display:block;width:100%;height:auto;border-radius:9px;background:var(--app-soft)}
.link-reader-footer{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:18px;padding-top:12px;border-top:1px solid var(--app-line);color:var(--app-muted);font-size:11px}.link-reader-footer>div{display:flex;gap:2px}.link-reader-footer button{display:inline-flex;align-items:center;gap:3px;padding:6px;border:0;color:#4f60e8;background:transparent;font:inherit;font-size:11px}.link-reader-footer button.danger{color:#ef4444}
.ion-palette-dark .link-reader-identity em.status-sent{color:#6ee7b7;background:#064e3b}.ion-palette-dark .link-reader-identity em.status-failed{color:#fca5a5;background:#450a0a}
</style>
