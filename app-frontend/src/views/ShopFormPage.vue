<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { IonButton, IonContent, IonFooter, IonInput, IonItem, IonLabel, IonPage, IonSpinner, IonTextarea, IonToolbar, toastController } from '@ionic/vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import { api, ApiError } from '../api'
import { session } from '../session'
import type { FieldDefinition, ShopRecord } from '../shopRecords'

const route = useRoute(); const router = useRouter()
const editing = computed(() => Boolean(route.params.id))
const fields = ref<FieldDefinition[]>([])
const form = reactive<Record<string, string>>({})
const originalValues = ref<Record<string, unknown>>({})
const loading = ref(true); const saving = ref(false)
const canWrite = computed(() => ['editor', 'superadmin'].includes(session.user?.role || ''))
const isTextarea = (field: FieldDefinition) => field.field_name === 'remark' || field.label.includes('备注') || field.label.includes('说明')

const load = async () => {
  if (!canWrite.value) {
    const toast = await toastController.create({ message: '当前账号只有查看权限', duration: 2000, color: 'warning' })
    await toast.present(); router.back(); return
  }
  try {
    const allFields = await api<FieldDefinition[]>('/custom-fields')
    fields.value = allFields.filter((field) => field.is_visible).sort((a, b) => a.sort_order - b.sort_order)
    if (editing.value) {
      const record = await api<ShopRecord>(`/shop-records/${route.params.id}`)
      originalValues.value = { ...record.values }
      for (const field of fields.value) form[field.field_name] = String(record.values[field.field_name] ?? '')
    } else {
      for (const field of fields.value) form[field.field_name] = ''
    }
  } catch (error) {
    const toast = await toastController.create({ message: error instanceof ApiError ? error.detail : '表单加载失败', duration: 2200, color: 'danger' })
    await toast.present()
  } finally { loading.value = false }
}

const save = async () => {
  for (const field of fields.value) {
    if (field.required && (form[field.field_name] === '' || form[field.field_name] === undefined)) {
      const toast = await toastController.create({ message: `请填写${field.label}`, duration: 1800, color: 'warning' }); await toast.present(); return
    }
  }
  saving.value = true
  try {
    const values: Record<string, unknown> = { ...originalValues.value }
    for (const field of fields.value) {
      const value = form[field.field_name]
      values[field.field_name] = field.field_type === 'number' && value !== '' ? Number(value) : value
    }
    const path = editing.value ? `/shop-records/${route.params.id}` : '/shop-records'
    await api<ShopRecord>(path, { method: editing.value ? 'PUT' : 'POST', body: JSON.stringify({ values }) })
    const toast = await toastController.create({ message: editing.value ? '店铺资料已保存' : '店铺记录已新增', duration: 1600, color: 'success' })
    await toast.present(); router.back()
  } catch (error) {
    const toast = await toastController.create({ message: error instanceof ApiError ? error.detail : '保存失败', duration: 2400, color: 'danger' })
    await toast.present()
  } finally { saving.value = false }
}
onMounted(load)
</script>

<template><IonPage><PageHeader :title="editing ? '编辑店铺资料' : '新增店铺记录'" subtitle="动态表头表单" back /><IonContent><main class="page-pad shop-form">
  <div v-if="loading" class="loading"><IonSpinner name="crescent" />正在加载表头</div>
  <section v-else class="panel form-panel">
    <IonItem v-for="field in fields" :key="field.id" lines="full">
      <IonLabel position="stacked">{{ field.label }}<em v-if="field.required"> *</em></IonLabel>
      <IonTextarea v-if="isTextarea(field)" v-model="form[field.field_name]" :auto-grow="true" :placeholder="`请输入${field.label}`" />
      <IonInput v-else v-model="form[field.field_name]" :type="field.field_type === 'number' ? 'number' : field.field_type === 'date' ? 'date' : 'text'" :inputmode="field.field_type === 'number' ? 'decimal' : 'text'" :placeholder="field.field_type === 'date' ? '' : `请输入${field.label}`" />
    </IonItem>
  </section>
  <p v-if="!loading" class="form-note">表单自动读取电脑端表头设置，新增字段后 App 无需重新改页面。</p>
</main></IonContent><IonFooter class="save-footer"><IonToolbar><div><IonButton fill="outline" :disabled="saving" @click="router.back()">取消</IonButton><IonButton :disabled="saving || loading" @click="save"><IonSpinner v-if="saving" name="crescent" />{{ saving ? '保存中' : editing ? '保存修改' : '确认新增' }}</IonButton></div></IonToolbar></IonFooter></IonPage></template>

<style scoped>.shop-form{padding-bottom:24px}.loading{display:flex;justify-content:center;align-items:center;gap:10px;padding:70px 0;color:var(--app-muted)}.form-panel ion-item{--background:var(--app-card);--padding-start:16px;--inner-padding-end:16px;--min-height:78px}.form-panel ion-label{font-size:14px}.form-panel em{color:#ef4444;font-style:normal}.form-panel ion-input,.form-panel ion-textarea{font-size:16px}.form-note{padding:0 4px;color:var(--app-muted);font-size:12px;line-height:1.6}.save-footer ion-toolbar{--background:var(--app-card);--border-color:var(--app-line)}.save-footer div{display:grid;grid-template-columns:1fr 2fr;gap:10px;padding:10px 16px calc(10px + env(safe-area-inset-bottom))}.save-footer ion-button{height:48px;--border-radius:13px}</style>
