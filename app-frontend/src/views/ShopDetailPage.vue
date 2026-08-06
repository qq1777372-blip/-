<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { IonButton, IonContent, IonIcon, IonPage, alertController, toastController } from '@ionic/vue'
import { copyOutline, createOutline, trashOutline } from 'ionicons/icons'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import { api, ApiError } from '../api'
import { session } from '../session'
import { copyText } from '../clipboard'
import { displayValue, titleFor, type FieldDefinition, type ShopRecord } from '../shopRecords'

const route = useRoute(); const router = useRouter()
const fields = ref<FieldDefinition[]>([])
const record = ref<ShopRecord | null>(null)
const loading = ref(true)
const canWrite = computed(() => ['editor', 'superadmin'].includes(session.user?.role || ''))
const title = computed(() => record.value ? titleFor(record.value, fields.value) : '店铺详情')
const load = async () => {
  try {
    const [fieldData, recordData] = await Promise.all([
      api<FieldDefinition[]>('/custom-fields'),
      api<ShopRecord>(`/shop-records/${route.params.id}`),
    ])
    fields.value = fieldData.filter((field) => field.is_visible).sort((a, b) => a.sort_order - b.sort_order)
    record.value = recordData
  } catch (error) {
    const toast = await toastController.create({ message: error instanceof ApiError ? error.detail : '详情加载失败', duration: 2200, color: 'danger' })
    await toast.present()
  } finally { loading.value = false }
}
const remove = async () => {
  if (!record.value || !canWrite.value) return
  const alert = await alertController.create({ header: '删除店铺记录', message: `确定删除“${title.value}”吗？`, buttons: ['取消', { text: '删除', role: 'destructive', handler: async () => {
    try { await api<void>(`/shop-records/${record.value?.id}`, { method: 'DELETE' }); router.back() }
    catch (error) { const toast = await toastController.create({ message: error instanceof ApiError ? error.detail : '删除失败', duration: 2200, color: 'danger' }); await toast.present() }
  } }] })
  await alert.present()
}
const copyField = async (label:string, value:unknown) => {
  const text=displayValue(value)
  if(!text||text==='—')return
  const copied=await copyText(text)
  const toast=await toastController.create({message:copied?`已复制：${label}`:'复制失败，请长按文字复制',duration:1500,color:copied?'success':'warning'})
  await toast.present()
}
onMounted(load)
</script>

<template><IonPage><PageHeader :title="title" subtitle="完整店铺资料" back /><IonContent><main class="page-pad detail-page">
  <section v-if="record" class="shop-summary panel"><small>店铺记录 #{{ record.id }}</small><h1>{{ title }}</h1><p>所有字段集中在详情页查看，列表只保留重点数据。</p></section>
  <section v-if="record" class="field-list panel"><div v-for="field in fields" :key="field.id" class="copyable-field" @click="copyField(field.label,record.values[field.field_name])"><span>{{ field.label }}</span><strong>{{ displayValue(record.values[field.field_name]) }}</strong><IonIcon :icon="copyOutline" /></div></section>
  <div v-else-if="!loading" class="empty-state">记录不存在或当前账号无权查看</div>
  <div v-if="record && canWrite" class="detail-actions"><IonButton @click="router.push(`/tabs/form/shops/${record.id}`)"><IonIcon slot="start" :icon="createOutline" />编辑资料</IonButton><IonButton color="danger" fill="outline" @click="remove"><IonIcon slot="start" :icon="trashOutline" />删除</IonButton></div>
</main></IonContent></IonPage></template>

<style scoped>.detail-page{display:grid;gap:12px}.shop-summary{padding:20px}.shop-summary small,.shop-summary p{color:var(--app-muted)}.shop-summary h1{margin:7px 0;font-size:22px}.shop-summary p{margin:0;font-size:12px}.field-list div{display:grid;grid-template-columns:minmax(90px,35%) minmax(0,1fr) 18px;align-items:center;gap:10px;padding:14px 16px;border-bottom:1px solid var(--app-line)}.field-list div:last-child{border:0}.field-list span{color:var(--app-muted);font-size:13px}.field-list strong{text-align:right;overflow-wrap:anywhere;user-select:text;-webkit-user-select:text;font-size:14px}.copyable-field{cursor:pointer}.copyable-field ion-icon{color:#94a3b8;font-size:15px}.copyable-field:active{background:var(--app-soft)}.detail-actions{display:grid;grid-template-columns:2fr 1fr;gap:10px}.detail-actions ion-button{height:48px;--border-radius:13px}</style>
