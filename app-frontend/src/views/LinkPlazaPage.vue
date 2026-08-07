<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { IonContent, IonIcon, IonPage, IonRefresher, IonRefresherContent, actionSheetController, alertController, toastController } from '@ionic/vue'
import { addCircleOutline, chatbubbleEllipsesOutline, documentTextOutline, imageOutline, searchOutline } from 'ionicons/icons'
import { useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import { api, ApiError } from '../api'
import { plainText } from '../markdown'
import { session } from '../session'

export type SavedLink = {
  id:number
  title:string
  url?:string
  category?:string
  description?:string
  is_pinned:boolean
  sort_order?:number
  author_user_id:number
  author_username:string
  author_avatar_url?:string
  push_status?:'idle'|'scheduled'|'sending'|'sent'|'failed'
  push_scheduled_at?:string
  push_sent_at?:string
  push_error?:string
  images:Array<{url:string;name?:string;storage_name:string}>
  created_at:string
  updated_at:string
}

type Tab = 'latest'|'with-images'|'mine'
const urlPattern=/https?:\/\/[^\s<]+/g
const router=useRouter()
const records=ref<SavedLink[]>([])
const query=ref('')
const tab=ref<Tab>('latest')
const loading=ref(true)
const feedScroll=ref<HTMLElement|null>(null)
const tabs=computed(()=>[
  {key:'latest' as Tab,label:'最新',count:records.value.length},
  {key:'with-images' as Tab,label:'带图',count:records.value.filter(item=>item.images?.length).length},
  {key:'mine' as Tab,label:'我发布的',count:records.value.filter(item=>item.author_user_id===session.user?.id).length},
])
const filtered=computed(()=>records.value.filter(item=>{
  if(tab.value==='with-images'&&!item.images?.length)return false
  if(tab.value==='mine'&&item.author_user_id!==session.user?.id)return false
  const keyword=query.value.trim().toLowerCase()
  return !keyword||`${item.title}${item.url||''}${item.category||''}${item.description||''}${item.author_username}`.toLowerCase().includes(keyword)
}).sort((left,right)=>Number(right.is_pinned)-Number(left.is_pinned)||(left.sort_order||0)-(right.sort_order||0)||new Date(right.updated_at).getTime()-new Date(left.updated_at).getTime()))
const imageCount=computed(()=>filtered.value.reduce((total,item)=>total+(item.images?.length||0),0))
const categoryCount=computed(()=>new Set(filtered.value.map(item=>category(item)).filter(value=>value!=='未分类')).size)

async function load(event?:{target:{complete:()=>void}}){
  loading.value=true
  try{records.value=await api('/saved-links')}
  catch(error){
    const toast=await toastController.create({message:error instanceof ApiError?error.detail:'链接广场加载失败',duration:2200,color:'danger'})
    await toast.present()
  }finally{
    loading.value=false
    event?.target.complete()
  }
}
function canEdit(item:SavedLink){return session.user?.role==='superadmin'||item.author_user_id===session.user?.id}
async function openPublishMenu(){
  const sheet=await actionSheetController.create({
    header:'选择发布方式',
    buttons:[
      {text:'发布帖子',icon:chatbubbleEllipsesOutline,handler:()=>{void router.push('/tabs/form/links')}},
      {text:'发布文章',icon:documentTextOutline,handler:()=>{void router.push('/tabs/form/articles')}},
      {text:'取消',role:'cancel'},
    ],
  })
  await sheet.present()
}
async function remove(item:SavedLink){
  const alert=await alertController.create({
    header:'删除帖子',
    message:`确定删除“${item.title}”吗？`,
    buttons:[
      {text:'取消',role:'cancel'},
      {text:'删除',role:'destructive',handler:async()=>{
        try{await api(`/saved-links/${item.id}`,{method:'DELETE'});records.value=records.value.filter(row=>row.id!==item.id)}
        catch(error){const toast=await toastController.create({message:error instanceof ApiError?error.detail:'删除失败',duration:2000,color:'danger'});await toast.present()}
      }},
    ],
  })
  await alert.present()
}
function host(url?:string){try{return url?new URL(url).hostname:''}catch{return ''}}
function time(value:string){return String(value||'').replace('T',' ').slice(0,16)}
function category(item:SavedLink){const value=String(item.category||'').trim();return !value||value.toLowerCase().startsWith('tutorial:')?'未分类':value}
function pushLabel(item:SavedLink){return item.push_status==='scheduled'?'已定时':item.push_status==='sending'?'推送中':item.push_status==='sent'?'已推送':item.push_status==='failed'?'推送失败':''}
function pushClass(item:SavedLink){return item.push_status?`saved-link-post__badge--${item.push_status}`:''}
function galleryClass(item:SavedLink){return item.images.length===1?'saved-link-gallery--single':item.images.length===2?'saved-link-gallery--double':''}
function descriptionHasUrl(value?:string){urlPattern.lastIndex=0;return urlPattern.test(value||'')}
function selectTab(key:Tab){tab.value=key;query.value='';nextTick(()=>feedScroll.value?.scrollTo({top:0,behavior:'auto'}))}
onMounted(load)
</script>

<template>
  <IonPage>
    <PageHeader title="链接广场" subtitle="内部文章与工作资料" hide-avatar />
    <IonContent>
      <IonRefresher slot="fixed" @ion-refresh="load"><IonRefresherContent /></IonRefresher>
      <main class="saved-links-app-page">
        <section class="saved-links-board">
          <div class="saved-links-topbar">
            <nav class="saved-links-tabs" aria-label="帖子筛选">
              <button v-for="item in tabs" :key="item.key" class="saved-links-tab" :class="{'saved-links-tab--active':tab===item.key}" @click="selectTab(item.key)">
                <span>{{ item.label }}</span><em>{{ item.count }}</em>
              </button>
            </nav>
            <div class="saved-links-topbar__actions">
              <label class="saved-links-search saved-links-native-search">
                <IonIcon :icon="searchOutline" />
                <input v-model="query" inputmode="search" placeholder="搜索标题、用户、分类、链接地址或正文">
              </label>
            </div>
          </div>

          <div class="saved-links-subbar">
            <div class="saved-links-subbar__main">
              <strong class="saved-links-subbar__title">链接广场</strong>
              <span class="saved-links-subbar__summary">当前显示 {{ filtered.length }} / {{ records.length }} 帖 · {{ imageCount }} 张配图 · {{ categoryCount }} 个分类</span>
            </div>
          </div>

          <div class="saved-link-feed-shell">
            <div ref="feedScroll" class="saved-link-feed-scroll">
              <section class="saved-link-feed">
                <article v-for="item in filtered" :key="item.id" class="saved-link-post">
                  <header class="saved-link-post__header">
                    <div class="saved-link-post__user">
                      <div class="saved-link-post__avatar"><img v-if="item.author_avatar_url" class="saved-link-post__avatar-image" :src="item.author_avatar_url" alt=""><span v-else>{{ item.author_username.slice(0, 1).toUpperCase() }}</span></div>
                      <div class="saved-link-post__identity">
                        <div class="saved-link-post__author-row">
                          <strong class="saved-link-post__author">{{ item.author_username }}</strong>
                          <span v-if="item.is_pinned" class="saved-link-post__badge saved-link-post__badge--pinned">置顶</span>
                          <span class="saved-link-post__category">{{ category(item) }}</span>
                          <span v-if="pushLabel(item)" class="saved-link-post__badge" :class="pushClass(item)">{{ pushLabel(item) }}</span>
                        </div>
                        <div class="saved-link-post__meta">
                          <span>{{ time(item.updated_at||item.created_at) }}</span>
                          <span v-if="item.url">{{ host(item.url) }}</span>
                          <span v-if="item.images?.length">{{ item.images.length }} 张图</span>
                          <span v-if="item.sort_order">排序 {{ item.sort_order }}</span>
                        </div>
                      </div>
                    </div>
                  </header>

                  <div class="saved-link-post__body">
                    <button class="saved-link-post__title" @click="router.push(`/tabs/detail/links/${item.id}`)">{{ item.title }}</button>
                    <div v-if="plainText(item.description)" class="saved-link-post__description">{{ plainText(item.description) }}</div>
                  </div>
                  <button v-if="item.url&&!descriptionHasUrl(item.description)" class="saved-link-post__url saved-link-native-url" @click="router.push(`/tabs/detail/links/${item.id}`)">
                    <strong class="saved-link-post__url-host">{{ host(item.url) }}</strong>
                    <span class="saved-link-post__url-text">{{ item.url }}</span>
                  </button>
                  <div v-if="item.images?.length" class="saved-link-gallery" :class="galleryClass(item)">
                    <button v-for="(image,index) in item.images.slice(0,3)" :key="image.storage_name" class="saved-link-gallery__item" @click="router.push(`/tabs/detail/links/${item.id}`)">
                      <img :src="image.url" :alt="`${item.title}配图${index+1}`">
                      <span v-if="index===2&&item.images.length>3" class="saved-link-gallery__more">+{{ item.images.length-3 }}</span>
                    </button>
                  </div>
                  <footer class="saved-link-post__footer">
                    <span class="saved-link-post__footer-note">帖子 #{{ item.id }}</span>
                    <div class="saved-link-post__actions">
                      <button @click="router.push(`/tabs/detail/links/${item.id}`)">阅读全文</button>
                      <button v-if="canEdit(item)" @click="router.push(`/tabs/form/links/${item.id}`)">编辑</button>
                      <button v-if="canEdit(item)" class="danger" @click="remove(item)">删除</button>
                    </div>
                  </footer>
                </article>

                <div v-if="!loading&&!filtered.length" class="saved-links-empty">
                  <IonIcon :icon="imageOutline" />
                  <strong>暂无符合条件的帖子</strong>
                  <span>换个关键词或发布第一篇帖子</span>
                </div>
              </section>
            </div>
          </div>
        </section>
        <button class="saved-links-compose" aria-label="选择发布方式" @click="openPublishMenu">
          <IonIcon :icon="addCircleOutline" />
          <span>发布</span>
        </button>
      </main>
    </IonContent>
  </IonPage>
</template>

<style src="../link-plaza-old.css"></style>
