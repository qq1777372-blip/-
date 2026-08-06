<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { IonContent, IonIcon, IonPage, IonSearchbar } from '@ionic/vue'
import { documentTextOutline, refreshOutline } from 'ionicons/icons'
import { useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import { api, ApiError } from '../api'

type Item={id:number;category:string;title:string;subtitle?:string;detail?:string}
const router=useRouter()
const query=ref('')
const loading=ref(false)
const error=ref('')
const groups=ref<Record<string,Item[]>>({})
let timer=0
let requestId=0
const items=computed(()=>Object.values(groups.value).flat())
const names:Record<string,string>={shop_record:'店铺账号',license_record:'执照档案',account_usage_record:'账号使用',task_bookkeeping_record:'任务记录'}

function open(item:Item){
  const routes:Record<string,string>={shop_record:`/tabs/detail/shops/${item.id}`,license_record:`/tabs/detail/licenses/${item.id}`,account_usage_record:`/tabs/detail/account-usage/${item.id}`,task_bookkeeping_record:`/tabs/detail/tasks/${item.id}`}
  router.push(routes[item.category]||'/tabs/home')
}

async function search(value:string){
  const current=++requestId
  loading.value=true
  error.value=''
  try{
    const data=await api<Record<string,unknown>>(`/global-search?q=${encodeURIComponent(value)}`)
    if(current!==requestId)return
    groups.value={shop_record:data.shop_records as Item[]||[],license_record:data.license_records as Item[]||[],account_usage_record:data.account_usage_records as Item[]||[],task_bookkeeping_record:data.task_bookkeeping_records as Item[]||[]}
  }catch(reason){
    if(current!==requestId)return
    groups.value={}
    error.value=reason instanceof ApiError?reason.detail:'搜索服务暂时不可用'
  }finally{
    if(current===requestId)loading.value=false
  }
}

watch(query,value=>{
  clearTimeout(timer)
  const keyword=value.trim()
  if(!keyword){requestId++;groups.value={};error.value='';loading.value=false;return}
  timer=window.setTimeout(()=>void search(keyword),280)
})
onBeforeUnmount(()=>{clearTimeout(timer);requestId++})
</script>

<template><IonPage><PageHeader title="全局搜索" subtitle="搜索店铺、任务、档案和账号" back /><IonContent><main class="page-pad search-page">
  <IonSearchbar v-model="query" :debounce="0" mode="ios" inputmode="search" placeholder="输入名称、账号、订单号或手机号" autofocus />
  <p v-if="loading" class="search-state">正在搜索…</p>
  <div v-else-if="error" class="search-error"><p>{{ error }}</p><button @click="search(query.trim())"><IonIcon :icon="refreshOutline" />重新搜索</button></div>
  <section v-else-if="items.length" class="search-results"><button v-for="item in items" :key="`${item.category}-${item.id}`" @click="open(item)"><span><IonIcon :icon="documentTextOutline" /></span><div><b>{{ item.title }}</b><small>{{ names[item.category] }} · {{ item.subtitle || item.detail || '查看详情' }}</small></div><em>›</em></button></section>
  <div v-else class="empty-state">{{ query.trim() ? '没有找到匹配数据' : '输入关键词开始搜索' }}</div>
</main></IonContent></IonPage></template>

<style scoped>.search-page ion-searchbar{--background:var(--app-card);--box-shadow:none;--border-radius:14px;padding:0}.search-state{text-align:center;color:var(--app-muted)}.search-error{padding:46px 20px;text-align:center;color:var(--app-muted)}.search-error p{margin:0 0 14px}.search-error button{display:inline-flex;align-items:center;gap:6px;padding:9px 14px;border:1px solid var(--app-line);border-radius:8px;color:var(--app-blue);background:var(--app-card)}.search-results button{width:100%;display:grid;grid-template-columns:38px minmax(0,1fr) auto;gap:10px;align-items:center;padding:13px 2px;border:0;border-bottom:1px solid var(--app-line);text-align:left;color:var(--app-text);background:transparent}.search-results button>span{width:36px;height:36px;display:grid;place-items:center;border-radius:8px;color:#2563eb;background:#eaf2ff}.search-results b,.search-results small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.search-results small{margin-top:4px;color:var(--app-muted)}.search-results em{font-size:24px;font-style:normal;color:var(--app-muted)}</style>
