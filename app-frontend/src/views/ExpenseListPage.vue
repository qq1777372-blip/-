<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  IonContent, IonFab, IonFabButton, IonIcon, IonItem, IonItemOption, IonItemOptions,
  IonItemSliding, IonList, IonPage, IonRefresher, IonRefresherContent, IonSearchbar,
  alertController, toastController,
} from '@ionic/vue'
import { addOutline, createOutline, trashOutline } from 'ionicons/icons'
import { useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import { api, ApiError } from '../api'
import { session } from '../session'
import { amount, type CompanyExpense } from '../expenses'

const router = useRouter()
const records = ref<CompanyExpense[]>([])
const summary = ref<Record<string, number>>({})
const query = ref('')
const filter = ref('')
const loading = ref(true)
const canWrite = computed(() => ['editor', 'superadmin'].includes(session.user?.role || ''))

const filtered = computed(() => records.value.filter((record) => {
  const text = `${record.expense_no} ${record.category} ${record.payment_account} ${record.description} ${record.expense_scope} ${record.submitter_name}`.toLowerCase()
  if (query.value && !text.includes(query.value.toLowerCase())) return false
  return !filter.value || record.payment_type === filter.value
}))

// Group by day so the ledger reads like a statement instead of a flat feed.
const days = computed(() => {
  const buckets = new Map<string, CompanyExpense[]>()
  for (const record of [...filtered.value].sort((a, b) => b.expense_date.localeCompare(a.expense_date))) {
    const list = buckets.get(record.expense_date) || []
    list.push(record)
    buckets.set(record.expense_date, list)
  }
  return [...buckets].map(([date, items]) => ({
    date,
    items,
    total: items.reduce((sum, item) => sum + Number(item.amount || 0), 0),
  }))
})

function localDateKey(value = new Date()) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}
function dayLabel(date: string) {
  if (date === localDateKey()) return '今天'
  const [, month, day] = date.split('-')
  return `${Number(month)}月${Number(day)}日`
}

function recordTime(value: string) {
  if (!value) return '--:--'
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`
  const parsed = new Date(normalized)
  if (Number.isNaN(parsed.getTime())) return '--:--'
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(parsed)
}

function openRecord(record: CompanyExpense) {
  void router.push(`/tabs/detail/company-expenses/${record.id}`)
}

async function load(event?: { target: { complete: () => void } }) {
  try {
    const [items, stats] = await Promise.all([
      api<CompanyExpense[]>('/company-expenses'),
      api<Record<string, number>>('/company-expenses/summary'),
    ])
    records.value = items
    summary.value = stats
  } catch (error) {
    const toast = await toastController.create({
      message: error instanceof ApiError ? error.detail : '记账数据加载失败',
      duration: 2200, color: 'danger',
    })
    await toast.present()
  } finally {
    loading.value = false
    event?.target.complete()
  }
}

async function remove(record: CompanyExpense) {
  const alert = await alertController.create({
    header: '删除记账记录',
    message: `确定删除 ${record.expense_no} 吗？`,
    buttons: ['取消', { text: '删除', role: 'destructive', handler: async () => {
      try {
        await api<void>(`/company-expenses/${record.id}`, { method: 'DELETE' })
        records.value = records.value.filter((item) => item.id !== record.id)
        void load()
      } catch (error) {
        const toast = await toastController.create({
          message: error instanceof ApiError ? error.detail : '删除失败',
          duration: 2200, color: 'danger',
        })
        await toast.present()
        return false
      }
    } }],
  })
  await alert.present()
}
onMounted(load)
</script>

<template>
  <IonPage>
    <PageHeader title="公司记账" subtitle="采购、报销与经营消费" back />
    <IonContent>
      <IonRefresher slot="fixed" @ion-refresh="load"><IonRefresherContent /></IonRefresher>
      <main class="ledger-page">
        <section class="ledger-hero">
          <small>本月消费</small>
          <strong>{{ amount(summary.month_total || 0) }}</strong>
          <div class="hero-stats">
            <div><span>本月笔数</span><b>{{ summary.month_record_count || 0 }}</b></div>
            <div><span>待报销</span><b>{{ amount(summary.pending_reimbursement_total || 0) }}</b></div>
          </div>
        </section>

        <IonSearchbar v-model="query" placeholder="搜索分类、账户、说明或记账人" mode="ios" />
        <div class="filters">
          <button :class="{ active: !filter }" @click="filter = ''">全部</button>
          <button :class="{ active: filter === 'company' }" @click="filter = 'company'">公司支付</button>
          <button :class="{ active: filter === 'employee' }" @click="filter = 'employee'">员工垫付</button>
        </div>

        <section v-for="day in days" :key="day.date" class="day-group">
          <header><span>{{ dayLabel(day.date) }}</span><em>{{ amount(day.total) }}</em></header>
          <IonList class="day-list" lines="none">
            <IonItemSliding v-for="record in day.items" :key="record.id">
              <IonItem class="record-item" button :detail="false" @click.stop="openRecord(record)">
                <article class="record">
                  <div class="record-icon">{{ record.category.slice(0, 1) }}</div>
                  <div class="record-body">
                    <h2>{{ record.category }}</h2>
                    <p>{{ record.payment_account }}<template v-if="record.description"> · {{ record.description }}</template> · 记账人：{{ record.submitter_name || '未知' }} · {{ recordTime(record.created_at) }}</p>
                  </div>
                  <div class="record-right">
                    <strong>-{{ amount(record.amount) }}</strong>
                    <span :class="{ advance: record.payment_type === 'employee' }">{{ record.payment_type === 'company' ? '公司支付' : '员工垫付' }}</span>
                  </div>
                </article>
              </IonItem>
              <IonItemOptions v-if="canWrite" side="end">
                <IonItemOption color="primary" @click="router.push(`/tabs/form/company-expenses/${record.id}`)"><IonIcon slot="icon-only" :icon="createOutline" /></IonItemOption>
                <IonItemOption color="danger" @click="remove(record)"><IonIcon slot="icon-only" :icon="trashOutline" /></IonItemOption>
              </IonItemOptions>
            </IonItemSliding>
          </IonList>
        </section>

        <div v-if="!days.length && !loading" class="empty-state">
          {{ query || filter ? '没有符合条件的记录' : '还没有记账记录，点右下角记一笔' }}
        </div>
      </main>

      <IonFab v-if="canWrite" slot="fixed" vertical="bottom" horizontal="end" class="ledger-fab">
        <IonFabButton @click="router.push('/tabs/form/company-expenses')"><IonIcon :icon="addOutline" /></IonFabButton>
      </IonFab>
    </IonContent>
  </IonPage>
</template>

<style scoped>
.ledger-page{padding:12px 14px 96px}
.ledger-hero{padding:20px;border-radius:18px;color:#fff;background:linear-gradient(135deg,#1f6fe5,#4f9dff)}
.ledger-hero>small{opacity:.85;font-size:11px}
.ledger-hero>strong{display:block;margin-top:6px;font-size:33px;letter-spacing:-.5px}
.hero-stats{display:grid;grid-template-columns:1fr 1fr;margin-top:18px;border-top:1px solid #ffffff33;padding-top:14px}
.hero-stats div+div{border-left:1px solid #ffffff33;padding-left:14px}
.hero-stats span{display:block;opacity:.8;font-size:10px}
.hero-stats b{display:block;margin-top:4px;font-size:15px}
ion-searchbar{margin-top:14px}
.filters{display:flex;gap:7px;padding:11px 1px 4px;overflow-x:auto}
.filters button{flex:none;border:1px solid var(--app-line);border-radius:999px;padding:7px 14px;color:var(--app-muted);background:var(--app-card);font-size:12px}
.filters .active{color:#1f6fe5;border-color:#9dc0ff;background:#eff5ff}
.day-group{margin-top:16px}
.day-group header{display:flex;justify-content:space-between;align-items:baseline;padding:0 3px 8px}
.day-group header span{font-size:13px;font-weight:700}
.day-group header em{color:var(--app-muted);font-size:11px;font-style:normal}
.day-list{padding:0;overflow:hidden;border-radius:16px;background:var(--app-card);box-shadow:0 2px 10px rgba(15,23,42,.035)}
.record-item{--padding-start:0;--inner-padding-end:0;--background:var(--app-card);--border-width:0}
.record{width:100%;display:grid;grid-template-columns:40px minmax(0,1fr) auto;gap:11px;align-items:center;padding:13px 14px;border-bottom:1px solid var(--app-line)}
ion-item-sliding:last-child .record{border-bottom:0}
.record-icon{width:40px;height:40px;display:grid;place-items:center;border-radius:13px;color:#1f6fe5;background:#eaf2ff;font-weight:700}
.record-body h2{margin:0;font-size:15px}
.record-body p{margin:4px 0 0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--app-muted);font-size:11px}
.record-right{text-align:right}
.record-right strong{display:block;font-size:16px}
.record-right span{display:inline-block;margin-top:5px;color:var(--app-muted);font-size:10px}
.record-right .advance{color:#b45309}
.ledger-fab{margin:0 4px calc(12px + env(safe-area-inset-bottom))}
.ion-palette-dark .day-list{box-shadow:none}
.ion-palette-dark .record-icon{background:#172c49}
.ion-palette-dark .filters .active{background:#152a49}
</style>
