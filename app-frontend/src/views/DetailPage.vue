<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { IonContent, IonIcon, IonPage, toastController } from '@ionic/vue'
import { copyOutline } from 'ionicons/icons'
import { useRoute } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import { api, ApiError } from '../api'
import { copyText } from '../clipboard'

type Row = Record<string, unknown>
const route = useRoute(); const row = ref<Row>({}); const loading = ref(true)
const resource = computed(() => String(route.params.resource)); const id = computed(() => String(route.params.id))
const configs: Record<string, { title: string; endpoint: string; titleKeys: string[] }> = {
  links: { title: '链接详情', endpoint: '/saved-links', titleKeys: ['title'] }, peers: { title: '同行店铺详情', endpoint: '/peer-shops', titleKeys: ['shop_name'] },
  licenses: { title: '执照档案详情', endpoint: '/license-records', titleKeys: ['subject_name'] }, devices: { title: '手机设备详情', endpoint: '/mobile-devices', titleKeys: ['device_name'] },
  users: { title: '账号权限详情', endpoint: '/admin-users', titleKeys: ['display_name', 'username'] }, 'account-usage': { title: '账号使用详情', endpoint: '/account-usage-records', titleKeys: ['account_name'] },
  'license-keys': { title: '卡密详情', endpoint: '/license-admin/licenses', titleKeys: ['license_key', 'key'] }, 'software-users': { title: '软件账号详情', endpoint: '/software-admin/users', titleKeys: ['display_name', 'username'] },
  owners: { title: '负责人详情', endpoint: '/task-bookkeeping/owners', titleKeys: ['name'] },
  'audit-logs': { title: '安全日志详情', endpoint: '/audit-logs', titleKeys: ['action'] },
}
const config = computed(() => configs[resource.value] || { title: '记录详情', endpoint: `/${resource.value}`, titleKeys: ['name', 'title'] })
const labels: Record<string, string> = { id:'编号',title:'标题',name:'名称',category:'分类',description:'说明',url:'链接',shop_name:'店铺名称',shop_url:'店铺链接',subject_name:'主体名称',credit_code:'统一信用代码',legal_representative:'法人',issue_date:'签发日期',expiry_date:'到期日期',expire_at:'到期时间',expires_at:'到期时间',device_name:'设备名称',primary_card:'主卡',secondary_card:'副卡',username:'登录账号',display_name:'显示名称',role:'角色',account_type:'账号类型',account_name:'使用账号',phone_number:'手机号',usage_notes:'使用说明',license_key:'卡密',plan_name:'授权方案',license_status:'授权状态',status:'状态',activated_at:'激活时间',last_validated_at:'最后验证',action:'操作',actor_username:'操作人',resource_type:'资源类型',resource_id:'资源编号',ip_address:'IP 地址',user_agent:'设备信息',remark:'备注',created_at:'创建时间',updated_at:'更新时间',is_active:'是否启用',is_activated:'是否激活',is_banned:'是否封禁' }
const hidden = new Set(['password','password_hash','image_path','avatar_path'])
const fields = computed(() => Object.entries(row.value).filter(([key,value]) => !hidden.has(key) && value !== null && value !== '' && typeof value !== 'object').map(([key,value]) => [labels[key] || key, typeof value === 'boolean' ? (value ? '是' : '否') : String(value)]))
const headline = computed(() => config.value.titleKeys.map((key) => row.value[key]).find(Boolean) || `记录 #${id.value}`)
async function load() { try { const result = await api<Row[] | { items?: Row[] }>(config.value.endpoint); const items = Array.isArray(result) ? result : result.items || []; row.value = items.find((item) => String(item.id??item.license_key??item.key??item.username) === id.value) || {} } catch(error) { const toast=await toastController.create({message:error instanceof ApiError?error.detail:'详情加载失败',duration:2200,color:'danger'});await toast.present() } finally { loading.value=false } }
async function copyField(label:unknown,value:unknown){const text=String(value||'');if(!text||text==='—')return;const copied=await copyText(text);const toast=await toastController.create({message:copied?`已复制：${String(label)}`:'复制失败，请长按文字复制',duration:1500,color:copied?'success':'warning'});await toast.present()}
onMounted(load)
</script>
<template><IonPage><PageHeader :title="config.title" subtitle="完整资料" back /><IonContent><main class="page-pad"><section class="detail-head"><small>记录 #{{ id }}</small><h1>{{ headline }}</h1></section><section v-if="fields.length" class="detail-list"><div v-for="field in fields" :key="field[0]" class="copyable-field" @click="copyField(field[0],field[1])"><span>{{ field[0] }}</span><strong>{{ field[1] }}</strong><IonIcon :icon="copyOutline" /></div></section><div v-else-if="!loading" class="empty-state">记录不存在或已删除</div></main></IonContent></IonPage></template>
<style scoped>.detail-head{padding:12px 4px 16px}.detail-head small,.detail-head p{color:var(--app-muted)}.detail-head h1{margin:7px 0;font-size:22px}.detail-head p{margin:0;font-size:12px}.detail-list{overflow:hidden;border-top:1px solid var(--app-line);background:var(--app-card)}.detail-list div{display:grid;grid-template-columns:105px minmax(0,1fr) 18px;align-items:center;gap:10px;padding:14px 4px;border-bottom:1px solid var(--app-line)}.detail-list span{color:var(--app-muted);font-size:13px}.detail-list strong{overflow-wrap:anywhere;user-select:text;-webkit-user-select:text;font-size:14px;font-weight:500;text-align:right}.copyable-field{cursor:pointer}.copyable-field ion-icon{color:#94a3b8;font-size:15px}.copyable-field:active{background:var(--app-soft)}</style>
