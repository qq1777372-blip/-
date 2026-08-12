<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { IonContent, IonIcon, IonPage, IonRefresher, IonRefresherContent, IonSearchbar, alertController, toastController } from '@ionic/vue'
import { addOutline, refreshOutline } from 'ionicons/icons'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import { api, ApiError } from '../api'
import { amount } from '../expenses'
import { session } from '../session'

type Row = Record<string, any>
type Tab = 'stocks' | 'warehouses' | 'products' | 'inbound' | 'outbound' | 'movements'
const router = useRouter()
const route = useRoute()
const summary = ref<Record<string, number>>({})
const data = ref<Record<Tab, Row[]>>({ stocks: [], warehouses: [], products: [], inbound: [], outbound: [], movements: [] })
const tab = ref<Tab>('stocks')
const query = ref('')
const warehouseFilter = ref('')
const statusFilter = ref('')
const labels: Record<Tab, string> = { stocks: '库存', warehouses: '仓库', products: '商品', inbound: '入库', outbound: '出库', movements: '流水' }
const statusLabels: Record<string, string> = { pending: '待拣货', picking: '拣货中', checked: '已复核', packed: '已打包', shipped: '已发货', cancelled: '已取消', completed: '已完成' }
// movement_type / source_type come back as backend enums (inbound, purchase...),
// so they get mapped here rather than rendered raw as English.
const movementLabels: Record<string, string> = { inbound: '入库', outbound: '出库', inbound_correction: '入库纠正' }
const sourceLabels: Record<string, string> = { purchase: '采购', return: '退货', other: '其他' }
const nextStatus: Record<string, string> = { pending: 'picking', picking: 'checked', checked: 'packed', packed: 'shipped' }
const rows = computed(() => data.value[tab.value].filter((row) => { const keyword=query.value.trim().toLowerCase(); return (!keyword||Object.values(row).join(' ').toLowerCase().includes(keyword))&&(!warehouseFilter.value||String(row.warehouse_id)===warehouseFilter.value)&&(!statusFilter.value||row.status===statusFilter.value) }))
const canWrite = computed(() => ['superadmin', 'admin', 'super_admin', 'editor'].includes(session.user?.role || ''))
const canCreate = computed(() => canWrite.value && ['warehouses', 'products', 'inbound', 'outbound'].includes(tab.value))
const validTabs = new Set<Tab>(['stocks', 'warehouses', 'products', 'inbound', 'outbound', 'movements'])
watch(() => route.query.tab, (value) => { const requested = String(value || 'stocks') as Tab; tab.value = validTabs.has(requested) ? requested : 'stocks' }, { immediate: true })

async function load(event?: { target: { complete: () => void } }) {
  try {
    const [summaryResult, warehouses, products, stocks, inbound, outbound, movements] = await Promise.all([
      api<Record<string, number>>('/warehouse/summary'),
      api<Row[]>('/warehouse/warehouses'), api<Row[]>('/warehouse/products'),
      api<Row[]>('/warehouse/stocks'), api<Row[]>('/warehouse/inbound-orders'), api<Row[]>('/warehouse/outbound-orders'), api<Row[]>('/warehouse/movements'),
    ])
    summary.value = summaryResult
    data.value = { warehouses, products, stocks, inbound, outbound, movements }
  } catch (error) {
    const toast = await toastController.create({ message: error instanceof ApiError ? error.detail : '仓储数据加载失败', duration: 2200, color: 'danger' })
    await toast.present()
  } finally { event?.target.complete() }
}

function title(row: Row) {
  return row.product_name || row.name || row.order_no || row.sku || row.warehouse_name || movementLabels[row.movement_type] || row.movement_type || '仓储记录'
}
function subtitle(row: Row) {
  return [row.sku, row.code, row.warehouse_name, row.supplier, row.recipient_name, row.reference_no].filter(Boolean).join(' · ') || row.remark || '—'
}
function value(row: Row) {
  if (tab.value === 'stocks') return `${row.available_quantity ?? 0} ${row.unit || '件'}`
  if (tab.value === 'movements') return `${Number(row.quantity_change) > 0 ? '+' : ''}${row.quantity_change ?? 0}`
  if (tab.value === 'outbound' || tab.value === 'inbound') return statusLabels[row.status] || row.status
  if (tab.value === 'products') return amount(row.cost_price || 0)
  return row.is_active === false ? '停用' : '启用'
}
// The numbers that used to sit in the metric strip, now shown one tab at a time
// so each row of chrome earns its height. Counts come straight off the loaded
// arrays where possible; the rest reuse /warehouse/summary, which is the same
// source the strip used, so nothing here can drift from the backend's own totals.
const tabDetail = computed(() => {
  const s = summary.value
  const list = data.value
  if (tab.value === 'stocks') {
    return `共 ${s.total_quantity ?? 0} 件 · 成本 ${amount(s.total_cost || 0)} · 预警 ${s.low_stock_count ?? 0} 项`
  }
  if (tab.value === 'warehouses') {
    const active = list.warehouses.filter((row) => row.is_active !== false).length
    return `启用 ${active} 个 · 停用 ${list.warehouses.length - active} 个`
  }
  if (tab.value === 'products') {
    const active = list.products.filter((row) => row.is_active !== false).length
    return `启用 ${active} 款 · 停用 ${list.products.length - active} 款`
  }
  if (tab.value === 'inbound') {
    const done = list.inbound.filter((row) => row.status === 'completed').length
    return `已完成 ${done} 单 · 进行中 ${list.inbound.length - done} 单 · 今日入库 ${s.today_inbound_quantity ?? 0} 件`
  }
  if (tab.value === 'outbound') {
    return `待出库 ${s.pending_outbound_count ?? 0} 单 · 今日出库 ${s.today_outbound_quantity ?? 0} 件`
  }
  const plus = list.movements.filter((row) => Number(row.quantity_change) > 0).length
  return `入库 ${plus} 条 · 出库 ${list.movements.length - plus} 条 · 今日 +${s.today_inbound_quantity ?? 0} / -${s.today_outbound_quantity ?? 0} 件`
})

// Second meta line per card. Every field here was checked against the response
// schema, so an empty string means the record really has nothing to add rather
// than a typo silently rendering blank.
function cardDetail(row: Row) {
  const parts: string[] = []
  if (tab.value === 'stocks') {
    const unit = row.unit || '件'
    parts.push(`成本 ${amount(row.cost_price || 0)}/${unit}`)
    parts.push(`库存值 ${amount((row.cost_price || 0) * (row.quantity || 0))}`)
    if (row.specification) parts.push(row.specification)
  } else if (tab.value === 'products') {
    if (row.specification) parts.push(row.specification)
    if (row.barcode) parts.push(`条码 ${row.barcode}`)
    if (row.unit) parts.push(`单位 ${row.unit}`)
    if (row.warning_quantity != null) parts.push(`预警 ${row.warning_quantity}`)
  } else if (tab.value === 'warehouses') {
    if (row.contact_name) parts.push(row.contact_name)
    if (row.contact_phone) parts.push(row.contact_phone)
    if (row.address) parts.push(row.address)
  } else if (tab.value === 'inbound') {
    if (row.source_type) parts.push(`来源 ${sourceLabels[row.source_type] || row.source_type}`)
    if (row.operator_username) parts.push(`操作 ${row.operator_username}`)
    if (row.completed_at) parts.push(`完成 ${String(row.completed_at).replace('T', ' ').slice(0, 16)}`)
  } else if (tab.value === 'outbound') {
    parts.push(row.delivery_method === 'pickup' ? '自提' : '快递')
    if (row.carrier) parts.push(row.carrier)
    if (row.tracking_no) parts.push(row.tracking_no)
    if (row.recipient_phone) parts.push(row.recipient_phone)
  } else {
    if (row.movement_type) parts.push(movementLabels[row.movement_type] || row.movement_type)
    if (row.quantity_after != null) parts.push(`变动后 ${row.quantity_after}`)
    if (row.operator_username) parts.push(`操作 ${row.operator_username}`)
  }
  return parts.join(' · ')
}
function openCreate() { router.push(`/tabs/warehouse/form/${tab.value === 'warehouses' ? 'warehouse' : tab.value === 'products' ? 'product' : tab.value}`) }
function openRow(row: Row) {
  if (!canWrite.value) return
  if (tab.value === 'warehouses') router.push(`/tabs/warehouse/form/warehouse/${row.id}`)
  if (tab.value === 'products') router.push(`/tabs/warehouse/form/product/${row.id}`)
  if (tab.value === 'inbound' && row.status === 'completed') router.push(`/tabs/warehouse/form/inbound/${row.id}`)
}

async function cancelInbound(row: Row) { const alert=await alertController.create({header:'撤销入库单',message:`撤销 ${row.order_no} 后会冲回库存，确定继续吗？`,buttons:['取消',{text:'确认撤销',role:'destructive',handler:async()=>{try{await api(`/warehouse/inbound-orders/${row.id}`,{method:'DELETE'});await load()}catch(error){const toast=await toastController.create({message:error instanceof ApiError?error.detail:'撤销失败',duration:2200,color:'danger'});await toast.present()}}}]});await alert.present() }

async function updateOutbound(order: Row, status: string) {
  const payload: Record<string, string> = { status }
  if (status === 'shipped' && order.delivery_method === 'shipping') {
    const alert = await alertController.create({
      header: '确认发货',
      inputs: [
        { name: 'carrier', placeholder: '快递公司', value: order.carrier || '' },
        { name: 'tracking_no', placeholder: '物流单号', value: order.tracking_no || '' },
      ],
      buttons: [{ text: '取消', role: 'cancel' }, { text: '确认发货', role: 'confirm' }],
    })
    await alert.present()
    const result = await alert.onDidDismiss()
    if (result.role !== 'confirm') return
    payload.carrier = result.data.values.carrier
    payload.tracking_no = result.data.values.tracking_no
  }
  try {
    await api(`/warehouse/outbound-orders/${order.id}/status`, { method: 'PATCH', body: JSON.stringify(payload) })
    await load()
  } catch (error) {
    const toast = await toastController.create({ message: error instanceof ApiError ? error.detail : '状态更新失败', duration: 2200, color: 'danger' })
    await toast.present()
  }
}

onMounted(load)
</script>

<template>
  <IonPage><PageHeader title="仓储管理" subtitle="库存、出入库和流水" back />
    <IonContent><IonRefresher slot="fixed" @ion-refresh="load"><IonRefresherContent /></IonRefresher>
      <main class="page-pad warehouse-page">
        <nav class="wh-tabs">
          <button v-for="key in (Object.keys(labels) as Tab[])" :key="key" :class="{ active: tab === key }" @click="tab = key">
            {{ labels[key] }}<em>{{ data[key].length }}</em>
          </button>
        </nav>
        <p class="wh-detail">{{ tabDetail }}</p>
        <IonSearchbar v-model="query" placeholder="搜索商品、单号、仓库或物流" mode="ios" />
        <div class="wh-controls">
          <label class="wh-pick"><select v-model="warehouseFilter"><option value="">全部仓库</option><option v-for="item in data.warehouses" :key="item.id" :value="String(item.id)">{{ item.name }}</option></select></label>
          <label v-if="tab==='outbound'||tab==='inbound'" class="wh-pick"><select v-model="statusFilter"><option value="">全部状态</option><option v-for="(label,key) in statusLabels" :key="key" :value="key">{{ label }}</option></select></label>
          <button v-if="canCreate" class="wh-primary" @click="openCreate"><IonIcon :icon="addOutline" />新增</button>
          <button v-else class="wh-ghost" @click="() => load()"><IonIcon :icon="refreshOutline" />刷新</button>
        </div>
        <section class="wh-list">
          <article v-for="(row, index) in rows" :key="String(row.id || index)" class="wh-card" :class="{ 'is-low': tab === 'stocks' && row.is_low_stock }">
            <div class="wh-top">
              <span class="wh-thumb"><img v-if="row.image_url" :src="`${row.image_url}${String(row.image_url).includes('?') ? '&' : '?'}thumb=1`" alt="" loading="lazy" decoding="async" /><template v-else>{{ title(row).slice(0, 1) }}</template></span>
              <div class="wh-body">
                <h2>{{ title(row) }}</h2>
                <p class="wh-meta">{{ subtitle(row) }}</p>
                <p v-if="tab==='stocks'" class="wh-nums">实际 {{ row.quantity??0 }}<i>·</i>锁定 {{ row.locked_quantity??0 }}<i>·</i>可用 {{ row.available_quantity??0 }}<i>·</i>预警 {{ row.warning_quantity??0 }}</p>
                <p v-if="(tab==='inbound'||tab==='outbound')&&row.items?.length" class="wh-nums">{{ row.items.map((item:Row)=>`${item.sku||item.product_name} × ${item.quantity}`).join('；') }}</p>
                <p v-if="cardDetail(row)" class="wh-sub">{{ cardDetail(row) }}</p>
                <div class="wh-price">
                  <strong>{{ value(row) }}</strong>
                  <span v-if="tab === 'stocks' && row.is_low_stock" class="low-flag">低于预警</span>
                  <small v-if="row.created_at">{{ String(row.created_at).replace('T', ' ').slice(0, 16) }}</small>
                </div>
              </div>
            </div>
            <footer v-if="canWrite && ['warehouses','products'].includes(tab)">
              <button class="wh-act" @click="openRow(row)">编辑</button>
            </footer>
            <footer v-else-if="tab==='inbound'&&canWrite&&row.status==='completed'">
              <button class="wh-act" @click="openRow(row)">纠正</button>
              <button class="wh-act danger" @click="cancelInbound(row)">撤销</button>
            </footer>
            <footer v-else-if="tab === 'outbound' && canWrite && !['shipped','cancelled'].includes(row.status)">
              <button v-if="nextStatus[row.status]" class="wh-act" @click="updateOutbound(row, nextStatus[row.status])">{{ statusLabels[nextStatus[row.status]] }}</button>
              <button class="wh-act danger" @click="updateOutbound(row, 'cancelled')">取消</button>
            </footer>
          </article>
          <div v-if="!rows.length" class="empty-state">暂无{{ labels[tab] }}数据</div>
        </section>
      </main>
    </IonContent>
  </IonPage>
</template>

<style scoped>
/* Modelled on the seller-app product list in the reference shot: underlined tabs
   carrying their own counts, plain-text pickers, and one card per row whose title
   is the loudest thing in it. No metric strip -- the counts live in the tabs. */
.warehouse-page{padding-inline:12px}

.wh-tabs{display:flex;gap:18px;overflow-x:auto;margin:2px 0 10px;border-bottom:1px solid var(--app-line)}
.wh-tabs button{flex:none;position:relative;padding:9px 0 11px;border:0;color:var(--app-muted);background:transparent;font-size:15px}
.wh-detail{margin:0 2px 10px;color:var(--app-muted);font-size:12px;line-height:1.5}
.wh-sub{margin:4px 0 0;color:var(--app-muted);font-size:11px;line-height:1.5;word-break:break-all}
.wh-card.is-low .wh-sub{color:#b45309}
.wh-tabs em{margin-left:4px;font-style:normal;font-size:12px}
.wh-tabs .active{color:var(--app-text);font-weight:700}
.wh-tabs .active::after{content:'';position:absolute;left:0;right:0;bottom:-1px;height:2px;border-radius:2px;background:#f97316}

.warehouse-page ion-searchbar{--background:var(--app-card);--box-shadow:none;--border-radius:12px;padding:0}

.wh-controls{display:flex;align-items:center;gap:14px;margin:10px 2px 12px}
/* Pickers read as text + caret like the reference, not as boxed selects. */
.wh-pick{position:relative;display:flex;align-items:center}
.wh-pick::after{content:'';margin-left:5px;width:0;height:0;border:4px solid transparent;border-top-color:var(--app-muted);translate:0 2px}
.wh-pick select{max-width:120px;padding:0;border:0;outline:0;color:var(--app-text);background:transparent;font-size:14px;appearance:none}
.wh-controls button{display:flex;align-items:center;gap:3px;margin-left:auto;padding:7px 13px;border:0;border-radius:9px;font-size:14px}
.wh-primary{color:#fff;background:#f97316}
.wh-ghost{color:var(--app-text);background:var(--app-card);border:1px solid var(--app-line)!important}

.wh-list{display:grid;gap:10px;padding-bottom:6px}
.wh-card{padding:13px;border:1px solid var(--app-line);border-radius:14px;background:var(--app-card)}
.wh-card.is-low{border-color:#fca5a5}

.wh-top{display:grid;grid-template-columns:60px minmax(0,1fr);gap:11px}
.wh-thumb{width:60px;height:60px;display:grid;place-items:center;overflow:hidden;border-radius:9px;color:#f97316;background:#fff0e6;font-size:20px;font-weight:700}
.wh-thumb img{width:100%;height:100%;object-fit:cover}
.wh-card.is-low .wh-thumb{color:#dc2626;background:#fee2e2}

.wh-body{min-width:0}
/* The title is the element you scan for, so it wraps to two lines instead of
   being clipped to one like every other field. */
.wh-body h2{margin:0;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;font-size:15px;line-height:1.4}
.wh-meta,.wh-nums{margin:5px 0 0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--app-muted);font-size:12px}
.wh-nums i{margin:0 6px;font-style:normal;opacity:.45}
.wh-price{display:flex;align-items:center;gap:7px;margin-top:7px}
.wh-price strong{color:#f97316;font-size:16px}
.wh-card.is-low .wh-price strong{color:#dc2626}
.wh-price small{margin-left:auto;color:var(--app-muted);font-size:10px}
.low-flag{padding:2px 6px;border-radius:6px;color:#dc2626;background:#fee2e2;font-size:10px;font-weight:600;white-space:nowrap}

/* Actions sit on their own line at the card's foot, right-aligned, so the same
   spot is tappable on every row. Only rendered where a real route backs it. */
.wh-card footer{display:flex;justify-content:flex-end;gap:8px;margin-top:11px;padding-top:10px;border-top:1px solid var(--app-line)}
.wh-act{padding:6px 15px;border:1px solid var(--app-line);border-radius:999px;color:var(--app-text);background:transparent;font-size:13px}
.wh-act.danger{color:#dc2626;border-color:#fca5a5}

.ion-palette-dark .wh-thumb{background:#3b2416}
.ion-palette-dark .wh-card.is-low .wh-thumb,.ion-palette-dark .low-flag{background:#451a1a}

@media(max-width:380px){
  .warehouse-page{padding-inline:8px}
  .wh-tabs{gap:13px}
  .wh-top{grid-template-columns:52px minmax(0,1fr);gap:9px}
  .wh-thumb{width:52px;height:52px;font-size:18px}
  .wh-nums{white-space:normal}
}
</style>
