<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { IonContent, IonInput, IonItem, IonLabel, IonPage, IonSpinner, onIonViewWillEnter, toastController, useIonRouter } from '@ionic/vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import { api, ApiError } from '../api'
import { cachedExpenseCategories, choicesWithLegacy, fallbackCategories, getExpenseCategories, isLegacyCategory } from '../expenseCategories'
import { network } from '../network'
import { session } from '../session'
import { fallbackPath } from '../navigation'
import type { CompanyExpense } from '../expenses'

const route = useRoute()
const router = useRouter()
const ionRouter = useIonRouter()
// The ledger tab is a pure entry pad: no back button, and saving keeps you here
// with a cleared form so several records can be logged in a row. Reached as a
// child page instead (from the ledger list), it behaves like a normal form.
const quick = computed(() => route.path === '/tabs/ledger')
const editing = computed(() => Boolean(route.params.id))
const saving = ref(false)
const loading = ref(true)
const file = ref<File | null>(null)
const detailsOpen = ref(false)
const today = () => {
  const value = new Date()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${value.getFullYear()}-${month}-${day}`
}
const form = reactive({
  date: today(),
  amount: '0',
  category: '办公用品',
  payment_type: 'company',
  payment_account: '公司卡',
  expense_scope: '公共费用',
  description: '',
})
const configuredCategories = ref([...fallbackCategories])
const categories = computed(() => choicesWithLegacy(configuredCategories.value, editing.value ? form.category : null))
const categoryStatus = ref('')
const legacyCategory = computed(() => editing.value && isLegacyCategory(configuredCategories.value, form.category))
// Calculator input stays local; the server is contacted only on final save.
const amountValue = computed(() => {
  const value = Number(form.amount)
  return Number.isFinite(value) ? value : 0
})

function defaultCategory() {
  return configuredCategories.value[0] || fallbackCategories[0]
}

function digit(value: string) {
  if (!/^[0-9.]$/.test(value)) return
  if (value === '.' && form.amount.includes('.')) return
  if (form.amount.includes('.') && form.amount.split('.')[1].length >= 2) return
  if (form.amount.replace('.', '').length >= 9) return
  form.amount = form.amount === '0' && value !== '.' ? value : form.amount + value
}
function backspace() {
  form.amount = form.amount.length > 1 ? form.amount.slice(0, -1) : '0'
}
function clearForm() {
  form.date = today()
  form.amount = '0'
  form.category = defaultCategory()
  form.payment_type = 'company'
  form.payment_account = '公司卡'
  form.expense_scope = '公共费用'
  form.description = ''
  file.value = null
  detailsOpen.value = false
}
function leave() {
  if (ionRouter.canGoBack()) ionRouter.back()
  else ionRouter.navigate(fallbackPath(route.fullPath), 'back', 'replace')
}
async function toast(message: string, color: string, duration = 2000) {
  const element = await toastController.create({ message, duration, color })
  await element.present()
}
async function load() {
  if (!editing.value) return
  try {
    const record = await api<CompanyExpense>(`/company-expenses/${route.params.id}`)
    form.date = record.expense_date
    form.amount = String(record.amount)
    form.category = record.category
    form.payment_type = record.payment_type
    form.payment_account = record.payment_account
    form.expense_scope = record.expense_scope
    form.description = record.description
  } catch (error) {
    await toast(error instanceof ApiError ? error.detail : '记录加载失败', 'danger', 2200)
  }
}
async function loadCategories() {
  const cached = cachedExpenseCategories(session.user?.id)
  if (cached) {
    configuredCategories.value = cached.config.categories
    categoryStatus.value = '已显示上次同步的分类'
  }
  try {
    const config = await getExpenseCategories(session.user?.id)
    configuredCategories.value = config.categories
    categoryStatus.value = ''
  } catch {
    if (!cached) {
      configuredCategories.value = [...fallbackCategories]
      categoryStatus.value = '分类暂未同步，使用默认分类'
    }
  }
  if (!editing.value && !configuredCategories.value.includes(form.category)) {
    form.category = defaultCategory()
  }
}

async function enterPage() {
  // The quick-entry ledger should be usable immediately from the cached/default
  // categories. A slow category request must not leave the whole keypad blocked.
  loading.value = editing.value
  if (!editing.value) {
    const cached = cachedExpenseCategories(session.user?.id)
    if (cached) configuredCategories.value = cached.config.categories
  }
  const categoryTask = loadCategories()
  const recordTask = editing.value ? load() : Promise.resolve()
  if (editing.value) {
    await Promise.allSettled([categoryTask, recordTask])
    loading.value = false
  } else {
    // New records do not need any remote data to render. Keep syncing categories
    // in the background so a delayed API cannot block entering an expense.
    loading.value = false
    void categoryTask.catch(() => undefined)
  }
}

async function save() {
  if (!network.online) return toast('当前离线，记账需要联网后提交', 'warning', 2200)
  if (Number(form.amount) <= 0) return toast('请输入金额', 'warning', 1900)
  if (!form.category.trim()) return toast('请选择消费分类', 'warning', 1900)
  saving.value = true
  try {
    const payload = {
      expense_date: form.date,
      amount: amountValue.value,
      category: form.category,
      payment_type: form.payment_type,
      payment_account: form.payment_account.trim() || '公司卡',
      expense_scope: form.expense_scope.trim() || '公共费用',
      description: form.description.trim() || form.category.trim(),
    }
    const saved = await api<{ id: number }>(
      editing.value ? `/company-expenses/${route.params.id}` : '/company-expenses',
      { method: editing.value ? 'PUT' : 'POST', body: JSON.stringify(payload) },
    )
    if (file.value) {
      const data = new FormData()
      data.append('attachment', file.value)
      const response = await fetch(`/company-expenses/${saved.id}/attachment`, { method: 'POST', credentials: 'include', body: data })
      if (!response.ok) throw new Error('票据上传失败')
    }
    await toast(editing.value ? '记录已保存' : '记账成功', 'success', 1400)
    if (quick.value) clearForm()
    else leave()
  } catch (error) {
    await toast(error instanceof ApiError ? error.detail : error instanceof Error ? error.message : '保存失败', 'danger', 2300)
  } finally {
    saving.value = false
  }
}
onIonViewWillEnter(enterPage)
</script>

<template>
  <IonPage>
    <PageHeader :title="editing ? '编辑记账' : '记一笔'" subtitle="公司账本" :back="!quick" hide-avatar />
    <IonContent>
      <div v-if="loading" class="entry-loading"><IonSpinner />正在加载</div>
      <main v-else class="entry">
        <section class="amount-card">
          <header>
            <small>公司消费</small>
            <div>
              <button type="button" @click="clearForm">清空</button>
              <button v-if="quick" type="button" @click="router.push('/tabs/list/company-expenses')">流水 ›</button>
            </div>
          </header>
          <strong>¥ {{ form.amount }}</strong>
        </section>

        <section class="categories">
          <button
            v-for="item in categories"
            :key="item"
            type="button"
            :class="{ active: form.category === item, legacy: isLegacyCategory(configuredCategories, item) }"
            @click="form.category = item"
          >{{ item }}<small v-if="isLegacyCategory(configuredCategories, item)">历史</small></button>
        </section>
        <p v-if="categoryStatus || legacyCategory" class="category-status">{{ legacyCategory ? '当前记录使用已停用的历史分类，保存时会保留原值' : categoryStatus }}</p>

        <IonItem class="note" lines="none">
          <IonInput v-model="form.description" placeholder="写一句消费说明（选填）" />
        </IonItem>

        <button class="more" type="button" @click="detailsOpen = !detailsOpen">
          {{ detailsOpen ? '收起补充信息' : '补充日期、账户或票据' }}
          <span>{{ detailsOpen ? '⌃' : '⌄' }}</span>
        </button>

        <section v-if="detailsOpen" class="extra">
          <IonItem><IonLabel position="stacked">日期</IonLabel><IonInput v-model="form.date" type="date" /></IonItem>
          <div class="pay-switch">
            <button type="button" :class="{ active: form.payment_type === 'company' }" @click="form.payment_type = 'company'">公司支付</button>
            <button type="button" :class="{ active: form.payment_type === 'employee' }" @click="form.payment_type = 'employee'">员工垫付</button>
          </div>
          <IonItem><IonLabel position="stacked">支付账户</IonLabel><IonInput v-model="form.payment_account" placeholder="公司卡、微信、支付宝或现金" /></IonItem>
          <IonItem><IonLabel position="stacked">费用归属</IonLabel><IonInput v-model="form.expense_scope" placeholder="公共费用、部门或项目" /></IonItem>
          <label class="file">
            <span>票据 / 小票 / 截图</span>
            <input type="file" accept="image/*,.pdf" @change="file = ($event.target as HTMLInputElement).files?.[0] || null">
            <em>{{ file?.name || '选择文件' }}</em>
          </label>
        </section>

        <section class="keypad">
          <button type="button" @click="digit('1')">1</button>
          <button type="button" @click="digit('2')">2</button>
          <button type="button" @click="digit('3')">3</button>
          <button type="button" class="fn" @click="backspace">⌫</button>
          <button type="button" @click="digit('4')">4</button>
          <button type="button" @click="digit('5')">5</button>
          <button type="button" @click="digit('6')">6</button>
          <button type="button" class="fn" @click="form.amount = '0'">C</button>
          <button type="button" @click="digit('7')">7</button>
          <button type="button" @click="digit('8')">8</button>
          <button type="button" @click="digit('9')">9</button>
          <button type="button" class="confirm" :disabled="saving" @click="save">
            <IonSpinner v-if="saving" name="crescent" />
            <template v-else>{{ editing ? '保存' : '记账' }}</template>
          </button>
          <button type="button" class="zero" @click="digit('0')">0</button>
          <button type="button" @click="digit('.')">.</button>
        </section>
      </main>
    </IonContent>
  </IonPage>
</template>

<style scoped>
.entry-loading{display:flex;justify-content:center;align-items:center;gap:8px;padding:80px;color:var(--app-muted)}
.entry{min-height:100%;display:flex;flex-direction:column;gap:10px;padding:10px 12px 14px}
.amount-card{padding:14px 16px 16px;border-radius:16px;color:#fff;background:linear-gradient(135deg,#2563eb,#7c3aed)}
.amount-card header{display:flex;align-items:center;justify-content:space-between;gap:10px}
.amount-card small{opacity:.85;font-size:11px}
.amount-card header div{display:flex;gap:7px}
.amount-card header button{padding:6px 10px;border:1px solid #ffffff55;border-radius:9px;color:#fff;background:#ffffff1a;font:inherit;font-size:11px}
.amount-card strong{display:block;margin-top:6px;font-size:34px;font-weight:700;letter-spacing:.5px}
.categories{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px}
.categories button{min-width:0;height:36px;padding:0 2px;overflow:hidden;border:1px solid var(--app-line);border-radius:10px;color:var(--app-muted);background:var(--app-card);text-overflow:ellipsis;white-space:nowrap;font:inherit;font-size:11px}
.categories .active{color:#2563eb;border-color:#8fb3ff;background:#eff5ff;font-weight:650}.categories button.legacy{height:42px}.categories button small{display:block;color:#d97706;font-size:8px}.category-status{margin:-4px 2px 0;color:#b45309;font-size:10px}
.note{--min-height:46px;--background:var(--app-card);--border-radius:12px;--padding-start:12px;--inner-padding-end:10px;border-radius:12px;overflow:hidden}
.note ion-input{font-size:14px}
.more{height:34px;border:0;color:var(--app-muted);background:transparent;font:inherit;font-size:11px}
.more span{margin-left:4px}
.extra{padding:4px 12px 10px;border-radius:14px;background:var(--app-card)}
.extra ion-item{--background:transparent;--padding-start:2px;--inner-padding-end:2px;--min-height:60px}
.extra ion-input{font-size:15px}
.pay-switch{display:grid;grid-template-columns:1fr 1fr;margin:8px 0 2px}
.pay-switch button{height:36px;border:1px solid var(--app-line);color:var(--app-muted);background:transparent;font:inherit;font-size:12px}
.pay-switch button:first-child{border-radius:10px 0 0 10px}
.pay-switch button:last-child{border-radius:0 10px 10px 0}
.pay-switch .active{color:#fff;border-color:#2563eb;background:#2563eb}
.file{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:12px 2px 4px;color:var(--app-muted);font-size:12px}
.file input{display:none}
.file em{max-width:48%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#2563eb;font-style:normal}
/* Keypad sits at the bottom of the page: entry stays reachable with one thumb
   and the confirm key is part of the pad instead of a separate footer bar. */
.keypad{margin-top:auto;display:grid;grid-template-columns:repeat(4,1fr);grid-auto-rows:minmax(46px,auto);gap:7px}
.keypad button{min-width:0;border:1px solid var(--app-line);border-radius:12px;color:var(--app-text);background:var(--app-card);font:inherit;font-size:20px;font-weight:600}
.keypad button:active{background:var(--app-line)}
.keypad .fn{color:var(--app-muted);font-size:17px}
.keypad .zero{grid-column:span 2}
.keypad .confirm{grid-row:span 2;display:grid;place-items:center;border:0;color:#fff;background:#1677ff;font-size:16px;font-weight:700}
.keypad .confirm:disabled{opacity:.6}
.keypad .confirm ion-spinner{width:22px;height:22px}
.ion-palette-dark .categories .active{background:#12233d;border-color:#2f5f9e}
</style>
