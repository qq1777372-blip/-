<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { IonContent, IonPage, alertController, onIonViewWillEnter, toastController } from '@ionic/vue'
import PageHeader from '../components/PageHeader.vue'
import { api, ApiError } from '../api'
import {
  cachedExpenseCategories,
  getExpenseCategories,
  maxCategoryCount,
  replaceExpenseCategories,
  resetExpenseCategories,
  type ExpenseCategoryConfig,
  validateCategories,
} from '../expenseCategories'
import { network } from '../network'
import { session } from '../session'

const form = reactive({
  system_name: '内部管理系统',
  system_subtitle: '任务记账与店铺后台',
  system_logo: '',
  license_expiry_days: 30,
  stale_task_days: 3,
  login_failure_threshold: 3,
  session_duration_hours: 168,
  low_stock_alert_enabled: true,
  pending_outbound_alert_enabled: true,
  task_alert_enabled: true,
  security_alert_enabled: true,
  data_alert_enabled: true,
  profit_stale_days: 3,
})
const saving = ref(false)
const categorySaving = ref(false)
const categories = ref<string[]>([])
const categoryUsage = ref<Record<string, number>>({})
const orphanCategories = ref<string[]>([])
const savedCategories = ref<string[]>([])
const categorySource = ref('')
const canEditCategories = computed(() => ['editor', 'superadmin'].includes(session.user?.role || ''))
const categoriesDirty = computed(() => JSON.stringify(categories.value) !== JSON.stringify(savedCategories.value))
function selectLogo(event:Event){const file=(event.target as HTMLInputElement).files?.[0];if(!file)return;if(file.size>500_000)return void toast('Logo 图片不能超过 500KB','warning');const reader=new FileReader();reader.onload=()=>{form.system_logo=String(reader.result||'')};reader.onerror=()=>void toast('Logo 读取失败','danger');reader.readAsDataURL(file)}

async function toast(message: string, color: string, duration = 2200) {
  const element = await toastController.create({ message, duration, color })
  await element.present()
}

function applyCategoryConfig(config: ExpenseCategoryConfig) {
  categories.value = [...config.categories]
  savedCategories.value = [...config.categories]
  categoryUsage.value = { ...config.usage }
  orphanCategories.value = [...config.orphan_categories]
}

async function loadSettings() {
  try {
    Object.assign(form, await api<typeof form>('/system-settings'))
  } catch (error) {
    await toast(error instanceof ApiError ? error.detail : '设置加载失败', 'danger')
  }
}

async function loadCategories() {
  const cached = cachedExpenseCategories(session.user?.id)
  if (cached) {
    applyCategoryConfig(cached.config)
    categorySource.value = '显示上次同步结果'
  }
  try {
    applyCategoryConfig(await getExpenseCategories(session.user?.id))
    categorySource.value = ''
  } catch (error) {
    if (!cached) await toast(error instanceof ApiError ? error.detail : '分类加载失败', 'danger')
  }
}

async function load() {
  await Promise.all([loadSettings(), loadCategories()])
}

async function saveSettings() {
  if (!network.online) return toast('当前离线，无法保存设置', 'warning')
  saving.value = true
  try {
    Object.assign(form, await api<typeof form>('/system-settings', { method: 'PUT', body: JSON.stringify(form) }))
    await toast('系统设置已保存', 'success', 1600)
  } catch (error) {
    await toast(error instanceof ApiError ? error.detail : '保存失败', 'danger')
  } finally {
    saving.value = false
  }
}

async function addCategory() {
  if (categories.value.length >= maxCategoryCount) return toast(`最多 ${maxCategoryCount} 个分类`, 'warning')
  const dialog = await alertController.create({
    header: '新增消费分类',
    inputs: [{ name: 'name', placeholder: '例如：房租水电', attributes: { maxlength: 50 } }],
    buttons: ['取消', { text: '新增', role: 'confirm' }],
  })
  await dialog.present()
  const result = await dialog.onDidDismiss()
  if (result.role !== 'confirm') return
  const name = String(result.data?.values?.name || '').trim()
  if (!name) return toast('分类名称不能为空', 'warning')
  if (categories.value.includes(name)) return toast('分类名称重复', 'warning')
  categories.value.push(name)
}

async function renameCategory(index: number) {
  const oldName = categories.value[index]
  const used = categoryUsage.value[oldName] || 0
  const dialog = await alertController.create({
    header: '修改分类名称',
    message: used ? `有 ${used} 条历史记录使用此分类；改名只影响以后记账，历史记录仍保留“${oldName}”。` : undefined,
    inputs: [{ name: 'name', value: oldName, attributes: { maxlength: 50 } }],
    buttons: ['取消', { text: '确定', role: 'confirm' }],
  })
  await dialog.present()
  const result = await dialog.onDidDismiss()
  if (result.role !== 'confirm') return
  const name = String(result.data?.values?.name || '').trim()
  if (!name) return toast('分类名称不能为空', 'warning')
  if (categories.value.some((item, itemIndex) => item === name && itemIndex !== index)) return toast('分类名称重复', 'warning')
  categories.value[index] = name
}

function moveCategory(index: number, direction: number) {
  const target = index + direction
  if (target < 0 || target >= categories.value.length) return
  const next = [...categories.value]
  ;[next[index], next[target]] = [next[target], next[index]]
  categories.value = next
}

async function removeCategory(index: number) {
  if (categories.value.length === 1) return toast('至少需要保留一个分类', 'warning')
  const name = categories.value[index]
  const used = categoryUsage.value[name] || 0
  const dialog = await alertController.create({
    header: '删除分类',
    message: used
      ? `“${name}”有 ${used} 条历史记录。删除后仅从以后记账选项中移除，历史记录不会删除。`
      : `确定删除“${name}”吗？`,
    buttons: ['取消', { text: '删除', role: 'destructive' }],
  })
  await dialog.present()
  const result = await dialog.onDidDismiss()
  if (result.role === 'destructive') categories.value.splice(index, 1)
}

async function saveCategories() {
  if (!network.online) return toast('当前离线，无法保存分类', 'warning')
  if (!canEditCategories.value) return toast('当前账号没有修改分类的权限', 'warning')
  const validation = validateCategories(categories.value)
  if (!validation.ok) return toast(validation.error, 'warning')
  categorySaving.value = true
  try {
    applyCategoryConfig(await replaceExpenseCategories(validation.categories, session.user?.id))
    await toast('消费分类已保存', 'success', 1600)
  } catch (error) {
    await toast(error instanceof ApiError ? error.detail : '分类保存失败', 'danger')
  } finally {
    categorySaving.value = false
  }
}

async function resetCategories() {
  if (!network.online) return toast('当前离线，无法恢复默认分类', 'warning')
  const dialog = await alertController.create({
    header: '恢复默认分类',
    message: '将恢复应用内置的 8 个分类。历史账目不会被修改。',
    buttons: ['取消', { text: '恢复默认', role: 'destructive' }],
  })
  await dialog.present()
  const result = await dialog.onDidDismiss()
  if (result.role !== 'destructive') return
  categorySaving.value = true
  try {
    applyCategoryConfig(await resetExpenseCategories(session.user?.id))
    await toast('已恢复默认分类', 'success', 1600)
  } catch (error) {
    await toast(error instanceof ApiError ? error.detail : '恢复失败', 'danger')
  } finally {
    categorySaving.value = false
  }
}

onIonViewWillEnter(load)
</script>

<template>
  <IonPage>
    <PageHeader title="系统设置" subtitle="后台规则、提醒与消费分类" back />
    <IonContent>
      <main class="page-pad system-settings">
        <section class="branding-panel"><h2>系统品牌</h2><div class="branding-preview"><img v-if="form.system_logo" :src="form.system_logo" alt="Logo 预览"><i v-else>{{form.system_name.trim().slice(0,2).toUpperCase()||'RS'}}</i><div><b>{{form.system_name||'系统名称'}}</b><small>{{form.system_subtitle||'系统副标题'}}</small></div></div><label>系统名称<input v-model="form.system_name" maxlength="40"></label><label>副标题<input v-model="form.system_subtitle" maxlength="60"></label><div class="logo-actions"><label>上传 Logo<input hidden type="file" accept="image/png,image/jpeg,image/webp" @change="selectLogo"></label><button v-if="form.system_logo" @click="form.system_logo=''">恢复文字标识</button></div><small>建议使用方形图片，最大 500KB</small></section>
        <section class="settings-group">
          <h2>规则参数</h2>
          <label><span><b>执照到期提醒</b><small>提前多少天提醒</small></span><input v-model.number="form.license_expiry_days" type="number"><em>天</em></label>
          <label><span><b>任务停滞提醒</b><small>超过天数未处理</small></span><input v-model.number="form.stale_task_days" type="number"><em>天</em></label>
          <label><span><b>利润断流提醒</b><small>超过天数没有上报</small></span><input v-model.number="form.profit_stale_days" type="number"><em>天</em></label>
          <label><span><b>登录失败阈值</b><small>达到次数触发安全提醒</small></span><input v-model.number="form.login_failure_threshold" type="number"><em>次</em></label>
          <label><span><b>会话有效时间</b><small>登录保持时长</small></span><input v-model.number="form.session_duration_hours" type="number"><em>小时</em></label>
        </section>
        <section class="settings-group">
          <h2>提醒开关</h2>
          <label class="switch-row"><span><b>库存预警</b><small>低库存时通知</small></span><input v-model="form.low_stock_alert_enabled" type="checkbox"></label>
          <label class="switch-row"><span><b>待出库提醒</b><small>存在待发货订单时通知</small></span><input v-model="form.pending_outbound_alert_enabled" type="checkbox"></label>
          <label class="switch-row"><span><b>任务提醒</b><small>任务超时或待结算时通知</small></span><input v-model="form.task_alert_enabled" type="checkbox"></label>
          <label class="switch-row"><span><b>数据自检</b><small>利润断流和库存成本异常</small></span><input v-model="form.data_alert_enabled" type="checkbox"></label>
          <label class="switch-row"><span><b>安全提醒</b><small>异常登录和敏感操作通知</small></span><input v-model="form.security_alert_enabled" type="checkbox"></label>
        </section>
        <button class="primary-action" :disabled="saving || !network.online" @click="saveSettings">{{ saving ? '保存中…' : '保存规则设置' }}</button>

        <section class="category-panel">
          <header>
            <div><h2>消费分类</h2><small>{{ categorySource || `${categories.length} 个分类，可改名和排序` }}</small></div>
            <button v-if="canEditCategories" :disabled="!network.online" @click="addCategory">新增</button>
          </header>
          <article v-for="(name, index) in categories" :key="`${name}-${index}`">
            <div><b>{{ name }}</b><small>{{ categoryUsage[name] ? `历史记录 ${categoryUsage[name]} 条` : '暂无历史记录' }}</small></div>
            <div v-if="canEditCategories" class="category-actions">
              <button @click="renameCategory(index)">改名</button>
              <button :disabled="index === 0" @click="moveCategory(index, -1)">上移</button>
              <button :disabled="index === categories.length - 1" @click="moveCategory(index, 1)">下移</button>
              <button class="danger" @click="removeCategory(index)">删除</button>
            </div>
          </article>
          <aside v-if="orphanCategories.length">历史账目中还有已停用分类：{{ orphanCategories.join('、') }}。它们只保留在历史记录中，不影响以后记账。</aside>
          <footer v-if="canEditCategories">
            <button :disabled="categorySaving || !network.online" @click="resetCategories">恢复默认</button>
            <button class="save-category" :disabled="categorySaving || !categoriesDirty || !network.online" @click="saveCategories">{{ categorySaving ? '保存中…' : '保存分类' }}</button>
          </footer>
        </section>
      </main>
    </IonContent>
  </IonPage>
</template>

<style scoped>
.system-settings{display:grid;gap:14px}.settings-group,.category-panel{overflow:hidden;background:var(--app-card);border-radius:14px}.settings-group h2{margin:0;padding:12px 14px 7px;color:var(--app-muted);font-size:11px;font-weight:500}.settings-group label{min-height:57px;display:grid;grid-template-columns:1fr 64px auto;gap:7px;align-items:center;padding:9px 14px;border-bottom:1px solid var(--app-line)}.settings-group label:last-child{border-bottom:0}.settings-group b,.settings-group small{display:block}.settings-group b{font-size:14px}.settings-group small{margin-top:3px;color:var(--app-muted);font-size:10px}.settings-group input[type=number]{width:64px;padding:7px;border:1px solid var(--app-line);border-radius:8px;text-align:right;color:var(--app-text);background:transparent}.settings-group em{color:var(--app-muted);font-size:11px;font-style:normal}.settings-group .switch-row{grid-template-columns:1fr auto}.switch-row input{width:42px;height:24px;accent-color:var(--app-blue)}.primary-action{height:48px;border:0;border-radius:13px;color:white;background:var(--app-blue);font-size:15px;font-weight:700}.primary-action:disabled{opacity:.5}.category-panel header{display:flex;align-items:center;justify-content:space-between;padding:13px 14px;border-bottom:1px solid var(--app-line)}.category-panel h2{margin:0;font-size:16px}.category-panel header small,.category-panel article small{display:block;margin-top:3px;color:var(--app-muted);font-size:10px}.category-panel button{padding:7px 9px;border:1px solid var(--app-line);border-radius:8px;color:#2563eb;background:transparent;font:inherit;font-size:11px}.category-panel button:disabled{opacity:.3}.category-panel article{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:center;padding:12px 14px;border-bottom:1px solid var(--app-line)}.category-actions{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:5px}.category-actions .danger{color:#dc2626}.category-panel aside{padding:10px 14px;color:#b45309;background:#fffbeb;font-size:10px;line-height:1.6}.category-panel footer{display:flex;justify-content:space-between;gap:10px;padding:12px 14px}.category-panel footer button{flex:1}.category-panel footer .save-category{color:#fff;border-color:#1677ff;background:#1677ff}
.branding-panel{padding:14px;background:var(--app-card);border-radius:14px}.branding-panel h2{margin:0 0 12px;font-size:16px}.branding-preview{display:flex;align-items:center;gap:10px;margin-bottom:13px;padding:12px;border:1px solid var(--app-line);border-radius:10px}.branding-preview img,.branding-preview i{width:44px;height:44px;display:grid;place-items:center;object-fit:contain;border-radius:8px;color:#fff;background:#1677ff;font-style:normal;font-weight:700}.branding-preview b,.branding-preview small{display:block}.branding-preview small,.branding-panel>small{margin-top:4px;color:var(--app-muted);font-size:10px}.branding-panel>label{display:grid;gap:5px;margin-bottom:10px;color:var(--app-muted);font-size:11px}.branding-panel>label input{height:40px;padding:0 10px;border:1px solid var(--app-line);border-radius:8px;color:var(--app-text);background:transparent}.logo-actions{display:flex;gap:8px;margin-bottom:8px}.logo-actions label,.logo-actions button{padding:8px 10px;border:1px solid var(--app-line);border-radius:8px;color:#1677ff;background:transparent;font-size:11px}
</style>
