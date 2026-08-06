<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { IonContent, IonPage, IonRefresher, IonRefresherContent, toastController } from '@ionic/vue'
import { useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import { api, ApiError } from '../api'
type Alert={key:string;category:string;severity:string;title:string;description:string;route:string;occurred_at?:string;acknowledged:boolean}
const router=useRouter();const data=ref<{open_count:number;critical_count:number;items:Alert[]}>({open_count:0,critical_count:0,items:[]})
async function load(event?:{target:{complete:()=>void}}){try{data.value=await api('/system-alerts')}catch(error){const toast=await toastController.create({message:error instanceof ApiError?error.detail:'通知加载失败',duration:2200,color:'danger'});await toast.present()}finally{event?.target.complete()}}
function open(alert:Alert){const map:Record<string,string>={inventory:'/tabs/module/warehouse',outbound:'/tabs/module/warehouse',license:'/tabs/list/licenses',task:'/tabs/list/tasks',security:'/tabs/list/audit-logs'};router.push(map[alert.category]||'/tabs/home')}
async function toggle(alert:Alert){try{await api(`/system-alerts/${encodeURIComponent(alert.key)}`,{method:'PATCH',body:JSON.stringify({acknowledged:!alert.acknowledged})});await load()}catch(error){const toast=await toastController.create({message:error instanceof ApiError?error.detail:'操作失败',duration:2000,color:'danger'});await toast.present()}}
// The backend sends utcnow() as a naive ISO string, so it has to be tagged as
// UTC before display -- otherwise the browser reads it as local time and every
// alert shows 8 hours early.
function occurredAt(value?:string){
  if(!value)return ''
  const iso=/(?:Z|[+-]\d{2}:\d{2})$/.test(value)?value:`${value}Z`
  const parsed=new Date(iso)
  if(Number.isNaN(parsed.getTime()))return value.replace('T',' ').slice(0,16)
  return new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(parsed).replaceAll('/','-')
}
onMounted(load)
</script>
<template><IonPage><PageHeader title="通知中心" :subtitle="`${data.open_count} 条待处理提醒`" back /><IonContent><IonRefresher slot="fixed" @ion-refresh="load"><IonRefresherContent /></IonRefresher><main class="page-pad alerts-page"><section class="alert-summary"><div><b>{{ data.open_count }}</b><span>待处理</span></div><div><b class="critical">{{ data.critical_count }}</b><span>紧急提醒</span></div></section><article v-for="item in data.items" :key="item.key" class="alert-row" :class="[item.severity,{done:item.acknowledged}]"><button class="alert-main" @click="open(item)"><i></i><div><b>{{ item.title }}</b><p>{{ item.description }}</p><small>{{ occurredAt(item.occurred_at) }}</small></div><em>›</em></button><button class="alert-status" @click="toggle(item)">{{ item.acknowledged?'重新打开':'标记已处理' }}</button></article><div v-if="!data.items.length" class="empty-state">当前没有系统提醒</div></main></IonContent></IonPage></template>
<style scoped>.alert-summary{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px}.alert-summary div{padding:16px;border:1px solid var(--app-line);border-radius:15px;background:var(--app-card)}.alert-summary b,.alert-summary span{display:block}.alert-summary b{font-size:25px}.alert-summary b.critical{color:#ef4444}.alert-summary span{margin-top:5px;color:var(--app-muted);font-size:12px}.alert-row{margin-bottom:10px;overflow:hidden;border:1px solid var(--app-line);border-radius:15px;background:var(--app-card)}.alert-main{width:100%;display:grid;grid-template-columns:8px 1fr auto;gap:10px;padding:14px;border:0;text-align:left;color:var(--app-text);background:transparent}.alert-main i{width:8px;height:8px;margin-top:5px;border-radius:50%;background:#f59e0b}.critical .alert-main i{background:#ef4444}.done{opacity:.58}.alert-main b{font-size:14px}.alert-main p{margin:5px 0;color:var(--app-muted);font-size:12px;line-height:1.55}.alert-main small{color:var(--app-muted)}.alert-main em{font-size:22px;font-style:normal;color:var(--app-muted)}.alert-status{width:100%;padding:9px;border:0;border-top:1px solid var(--app-line);color:#2563eb;background:transparent}</style>
