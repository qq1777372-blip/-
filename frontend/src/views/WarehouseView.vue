<script setup lang="ts">
import { Goods, Plus, Refresh, Search, Ship } from '@element-plus/icons-vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import ListPaginationFooter from '../components/ListPaginationFooter.vue'
import {
  createWarehouse,
  createWarehouseInboundOrder,
  updateWarehouseInboundOrder,
  cancelWarehouseInboundOrder,
  createWarehouseOutboundOrder,
  createWarehouseProduct,
  fetchWarehouseInboundOrders,
  fetchWarehouseMovements,
  fetchWarehouseOutboundOrders,
  fetchWarehouseProducts,
  fetchWarehouseStocks,
  fetchWarehouseSummary,
  fetchWarehouses,
  updateWarehouse,
  updateWarehouseOutboundStatus,
  updateWarehouseProduct,
  uploadWarehouseProductImage,
} from '../api'
import { useAuthStore } from '../stores/auth'
import type {
  Warehouse,
  WarehouseInboundOrder,
  WarehouseOrderLinePayload,
  WarehouseOutboundOrder,
  WarehouseOutboundStatus,
  WarehouseProduct,
  WarehouseStock,
  WarehouseStockMovement,
  WarehouseSummary,
} from '../types/api'
import { formatDateTime } from '../utils/format'

const authStore = useAuthStore()
type WarehouseMode = 'stock' | 'inbound' | 'outbound' | 'movement' | 'products' | 'warehouses' | 'master'
const props = withDefaults(defineProps<{ mode?: WarehouseMode }>(), { mode: 'stock' })
const loading = ref(false)
const saving = ref(false)
const masterDataTab = ref<'products' | 'warehouses'>('products')
const activeTab = computed(() => props.mode === 'master' ? masterDataTab.value : props.mode)
const keyword = ref('')
const selectedWarehouseId = ref(0)
const selectedOutboundStatus = ref<'all' | WarehouseOutboundStatus>('all')
const pageSize = 20
const pages = reactive({ stock: 1, outbound: 1, inbound: 1, movement: 1, warehouses: 1, products: 1 })
const warehouses = ref<Warehouse[]>([])
const products = ref<WarehouseProduct[]>([])
const stocks = ref<WarehouseStock[]>([])
const inboundOrders = ref<WarehouseInboundOrder[]>([])
const outboundOrders = ref<WarehouseOutboundOrder[]>([])
const movements = ref<WarehouseStockMovement[]>([])
const summary = ref<WarehouseSummary>({
  warehouse_count: 0, product_count: 0, total_quantity: 0, total_cost: 0, low_stock_count: 0,
  pending_outbound_count: 0, today_inbound_quantity: 0, today_outbound_quantity: 0,
})

const warehouseDialogVisible = ref(false)
const productDialogVisible = ref(false)
const inboundDialogVisible = ref(false)
const outboundDialogVisible = ref(false)
const shippingDialogVisible = ref(false)
const editingWarehouseId = ref<number | null>(null)
const editingProductId = ref<number | null>(null)
const shippingOrder = ref<WarehouseOutboundOrder | null>(null)
const editingInboundId = ref<number | null>(null)

const warehouseForm = reactive({ code: '', name: '', address: '', contact_name: '', contact_phone: '', is_active: true, remark: '' })
const productForm = reactive({ sku: '', name: '', barcode: '', specification: '', unit: '件', cost_price: 0, warning_quantity: 0, is_active: true, remark: '' })
const productImageFile = ref<File | null>(null)
const productImagePreview = ref('')
let productImageObjectUrl = ''
const inboundForm = reactive({ warehouse_id: 0, source_type: 'purchase' as 'purchase' | 'return' | 'other', supplier: '', remark: '', items: [] as WarehouseOrderLinePayload[] })
const outboundForm = reactive({ warehouse_id: 0, external_order_no: '', delivery_method: 'shipping' as 'shipping' | 'pickup', recipient_name: '', recipient_phone: '', recipient_address: '', carrier: '', tracking_no: '', remark: '', items: [] as WarehouseOrderLinePayload[] })
const shippingForm = reactive({ carrier: '', tracking_no: '' })

const canWrite = computed(() => authStore.canWrite('warehouse'))
const viewMeta = computed(() => ({
  stock: { title: '库存总览', description: '查看各仓库商品的实际库存、锁定库存、可用库存和成本' },
  inbound: { title: '入库管理', description: '办理采购、退货及其他入库，完成后实时增加库存' },
  outbound: { title: '出库发货', description: '处理拣货、验货、打包、物流和最终出库' },
  movement: { title: '库存流水', description: '追溯每一次库存增减、关联单据和操作人员' },
  products: { title: '商品档案', description: '维护 SKU、图片、规格、成本价和库存预警值' },
  warehouses: { title: '仓库管理', description: '维护仓库编码、地址、联系人和启用状态' },
})[activeTab.value])
const activeWarehouses = computed(() => warehouses.value.filter((item) => item.is_active))
const activeProducts = computed(() => products.value.filter((item) => item.is_active))
const normalizedKeyword = computed(() => keyword.value.trim().toLowerCase())
function matches(values: unknown[]) { return !normalizedKeyword.value || values.join(' ').toLowerCase().includes(normalizedKeyword.value) }
const warehouseMatches = (warehouseId: number) => !selectedWarehouseId.value || warehouseId === selectedWarehouseId.value
const filteredStocks = computed(() => stocks.value.filter((item) => warehouseMatches(item.warehouse_id) && matches([item.warehouse_name, item.sku, item.product_name, item.barcode ?? '', item.specification ?? ''])))
const filteredWarehouses = computed(() => warehouses.value.filter((item) => matches([item.code, item.name, item.address ?? '', item.contact_name ?? ''])))
const filteredProducts = computed(() => products.value.filter((item) => matches([item.sku, item.name, item.barcode ?? '', item.specification ?? ''])))
const filteredInbound = computed(() => inboundOrders.value.filter((item) => warehouseMatches(item.warehouse_id) && matches([item.order_no, item.warehouse_name, item.supplier ?? '', item.items.map((line) => line.sku).join(' ')])))
const filteredOutbound = computed(() => outboundOrders.value.filter((item) => warehouseMatches(item.warehouse_id) && (selectedOutboundStatus.value === 'all' || item.status === selectedOutboundStatus.value) && matches([item.order_no, item.external_order_no ?? '', item.warehouse_name, item.recipient_name ?? '', item.tracking_no ?? '', item.items.map((line) => line.sku).join(' ')])))
const filteredMovements = computed(() => movements.value.filter((item) => warehouseMatches(item.warehouse_id) && matches([item.reference_no, item.warehouse_name, item.sku, item.product_name, item.operator_username ?? ''])))
function paginate<T>(items: T[], page: number) { return items.slice((page - 1) * pageSize, page * pageSize) }
function pageCount(total: number) { return Math.max(1, Math.ceil(total / pageSize)) }
const paginatedStocks = computed(() => paginate(filteredStocks.value, pages.stock))
const paginatedOutbound = computed(() => paginate(filteredOutbound.value, pages.outbound))
const paginatedInbound = computed(() => paginate(filteredInbound.value, pages.inbound))
const paginatedMovements = computed(() => paginate(filteredMovements.value, pages.movement))
const paginatedWarehouses = computed(() => paginate(filteredWarehouses.value, pages.warehouses))
const paginatedProducts = computed(() => paginate(filteredProducts.value, pages.products))
watch(keyword, () => Object.assign(pages, { stock: 1, outbound: 1, inbound: 1, movement: 1, warehouses: 1, products: 1 }))
watch([selectedWarehouseId, selectedOutboundStatus], () => Object.assign(pages, { stock: 1, outbound: 1, inbound: 1, movement: 1 }))

const statusMeta: Record<WarehouseOutboundStatus, { label: string; type: 'info' | 'primary' | 'warning' | 'success' | 'danger' }> = {
  pending: { label: '待拣货', type: 'info' }, picking: { label: '拣货中', type: 'primary' },
  checked: { label: '已验货', type: 'warning' }, packed: { label: '已打包', type: 'warning' },
  shipped: { label: '已出库', type: 'success' }, cancelled: { label: '已取消', type: 'danger' },
}
const nextStatus: Partial<Record<WarehouseOutboundStatus, WarehouseOutboundStatus>> = { pending: 'picking', picking: 'checked', checked: 'packed' }
const nextLabel: Partial<Record<WarehouseOutboundStatus, string>> = { pending: '开始拣货', picking: '确认验货', checked: '确认打包' }
function outboundStatusMeta(value: WarehouseOutboundStatus) { return statusMeta[value] }
function outboundNextStatus(value: WarehouseOutboundStatus) { return nextStatus[value] }
function outboundNextLabel(value: WarehouseOutboundStatus) { return nextLabel[value] }
function inboundSourceLabel(value: WarehouseInboundOrder['source_type']) { return { purchase: '采购入库', return: '退货入库', other: '其他入库' }[value] }

function errorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) return String(error.response?.data?.detail ?? error.message ?? fallback)
  return error instanceof Error ? error.message : fallback
}

async function loadData() {
  loading.value = true
  try {
    const result = await Promise.all([
      fetchWarehouseSummary(), fetchWarehouses(), fetchWarehouseProducts(), fetchWarehouseStocks(),
      fetchWarehouseInboundOrders(), fetchWarehouseOutboundOrders(), fetchWarehouseMovements(),
    ])
    ;[summary.value, warehouses.value, products.value, stocks.value, inboundOrders.value, outboundOrders.value, movements.value] = result
  } catch (error) { ElMessage.error(errorMessage(error, '加载仓储数据失败')) }
  finally { loading.value = false }
}

function resetWarehouseForm(record?: Warehouse) {
  editingWarehouseId.value = record?.id ?? null
  Object.assign(warehouseForm, record ? { ...record } : { code: '', name: '', address: '', contact_name: '', contact_phone: '', is_active: true, remark: '' })
  warehouseDialogVisible.value = true
}
function resetProductForm(record?: WarehouseProduct) {
  editingProductId.value = record?.id ?? null
  if (productImageObjectUrl) URL.revokeObjectURL(productImageObjectUrl)
  productImageObjectUrl = ''
  productImageFile.value = null
  productImagePreview.value = record?.image_url ?? ''
  Object.assign(productForm, record ? { ...record } : { sku: '', name: '', barcode: '', specification: '', unit: '件', cost_price: 0, warning_quantity: 0, is_active: true, remark: '' })
  productDialogVisible.value = true
}
function selectProductImage(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 15 * 1024 * 1024) {
    ElMessage.error('请选择 15MB 以内的 JPG、PNG 或 WebP 图片')
    ;(event.target as HTMLInputElement).value = ''
    return
  }
  if (productImageObjectUrl) URL.revokeObjectURL(productImageObjectUrl)
  productImageFile.value = file
  productImageObjectUrl = URL.createObjectURL(file)
  productImagePreview.value = productImageObjectUrl
}
function clean(value: string | null | undefined) { return value?.trim() || null }
async function saveWarehouse() {
  if (!warehouseForm.code.trim() || !warehouseForm.name.trim()) return ElMessage.warning('请填写仓库编码和名称')
  saving.value = true
  try {
    const payload = { code: warehouseForm.code.trim(), name: warehouseForm.name.trim(), address: clean(warehouseForm.address), contact_name: clean(warehouseForm.contact_name), contact_phone: clean(warehouseForm.contact_phone), is_active: warehouseForm.is_active, remark: clean(warehouseForm.remark) }
    if (editingWarehouseId.value) await updateWarehouse(editingWarehouseId.value, payload); else await createWarehouse(payload)
    warehouseDialogVisible.value = false; ElMessage.success('仓库已保存'); await loadData()
  } catch (error) { ElMessage.error(errorMessage(error, '保存仓库失败')) } finally { saving.value = false }
}
async function saveProduct() {
  if (!productForm.sku.trim() || !productForm.name.trim()) return ElMessage.warning('请填写 SKU 和商品名称')
  saving.value = true
  try {
    const payload = { sku: productForm.sku.trim(), name: productForm.name.trim(), barcode: clean(productForm.barcode), specification: clean(productForm.specification), unit: productForm.unit.trim() || '件', cost_price: Number(productForm.cost_price || 0), warning_quantity: Number(productForm.warning_quantity || 0), is_active: productForm.is_active, remark: clean(productForm.remark) }
    const saved = editingProductId.value ? await updateWarehouseProduct(editingProductId.value, payload) : await createWarehouseProduct(payload)
    if (productImageFile.value) await uploadWarehouseProductImage(saved.id, productImageFile.value)
    productDialogVisible.value = false; ElMessage.success('商品已保存'); await loadData()
  } catch (error) { ElMessage.error(errorMessage(error, '保存商品失败')) } finally { saving.value = false }
}

function newLine(): WarehouseOrderLinePayload { return { product_id: activeProducts.value[0]?.id ?? 0, quantity: 1 } }
function openInbound() { editingInboundId.value = null; Object.assign(inboundForm, { warehouse_id: activeWarehouses.value[0]?.id ?? 0, source_type: 'purchase', supplier: '', remark: '', items: [newLine()] }); inboundDialogVisible.value = true }
function editInbound(order: WarehouseInboundOrder) {
  if (order.status !== 'completed') return
  editingInboundId.value = order.id
  Object.assign(inboundForm, {
    warehouse_id: order.warehouse_id,
    source_type: order.source_type,
    supplier: order.supplier ?? '',
    remark: order.remark ?? '',
  })
  inboundForm.items.splice(0, inboundForm.items.length, ...order.items.map((item) => ({ product_id: item.product_id, quantity: Number(item.quantity) })))
  inboundDialogVisible.value = true
}
function openOutbound() { Object.assign(outboundForm, { warehouse_id: activeWarehouses.value[0]?.id ?? 0, external_order_no: '', delivery_method: 'shipping', recipient_name: '', recipient_phone: '', recipient_address: '', carrier: '', tracking_no: '', remark: '', items: [newLine()] }); outboundDialogVisible.value = true }
function addLine(items: WarehouseOrderLinePayload[]) { items.push(newLine()) }
function removeLine(items: WarehouseOrderLinePayload[], index: number) { if (items.length > 1) items.splice(index, 1) }
async function saveInbound() {
  if (!inboundForm.warehouse_id || inboundForm.items.some((item) => !item.product_id || item.quantity < 1)) return ElMessage.warning('请选择仓库并填写有效商品数量')
  saving.value = true
  try {
    const payload = { ...inboundForm, supplier: clean(inboundForm.supplier), remark: clean(inboundForm.remark), items: inboundForm.items.map((item) => ({ ...item })) }
    if (editingInboundId.value) await updateWarehouseInboundOrder(editingInboundId.value, payload)
    else await createWarehouseInboundOrder(payload)
    inboundDialogVisible.value = false
    ElMessage.success(editingInboundId.value ? '入库单已纠正，库存已同步更新' : '入库完成，库存已更新')
    editingInboundId.value = null
    await loadData()
  }
  catch (error) { ElMessage.error(errorMessage(error, '入库失败')) } finally { saving.value = false }
}
async function cancelInbound(order: WarehouseInboundOrder) {
  try {
    await ElMessageBox.confirm(`确认撤销入库单 ${order.order_no}？系统会扣回本次入库库存并保留纠错流水。`, '撤销入库单', { type: 'warning' })
    await cancelWarehouseInboundOrder(order.id)
    ElMessage.success('入库单已撤销，库存已同步扣回')
    await loadData()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(errorMessage(error, '撤销入库单失败'))
  }
}
async function saveOutbound() {
  if (!outboundForm.warehouse_id || outboundForm.items.some((item) => !item.product_id || item.quantity < 1)) return ElMessage.warning('请选择仓库并填写有效商品数量')
  if (!outboundForm.recipient_name.trim() || !outboundForm.recipient_phone.trim()) return ElMessage.warning(outboundForm.delivery_method === 'pickup' ? '请填写提货人和联系电话' : '请填写收件人和联系电话')
  if (outboundForm.delivery_method === 'shipping' && !outboundForm.recipient_address.trim()) return ElMessage.warning('请填写收货地址')
  saving.value = true
  try {
    await createWarehouseOutboundOrder({ warehouse_id: outboundForm.warehouse_id, external_order_no: clean(outboundForm.external_order_no), delivery_method: outboundForm.delivery_method, recipient_name: clean(outboundForm.recipient_name), recipient_phone: clean(outboundForm.recipient_phone), recipient_address: outboundForm.delivery_method === 'shipping' ? clean(outboundForm.recipient_address) : null, carrier: clean(outboundForm.carrier), tracking_no: clean(outboundForm.tracking_no), remark: clean(outboundForm.remark), items: outboundForm.items.map((item) => ({ ...item })) })
    outboundDialogVisible.value = false; ElMessage.success('出库单已创建，库存已锁定'); await loadData()
  } catch (error) { ElMessage.error(errorMessage(error, '创建出库单失败')) } finally { saving.value = false }
}
async function advance(order: WarehouseOutboundOrder) {
  const target = nextStatus[order.status]
  if (!target) return
  try { await updateWarehouseOutboundStatus(order.id, { status: target }); ElMessage.success('出库状态已更新'); await loadData() }
  catch (error) { ElMessage.error(errorMessage(error, '更新状态失败')) }
}
function openShipping(order: WarehouseOutboundOrder) { shippingOrder.value = order; shippingForm.carrier = order.carrier ?? ''; shippingForm.tracking_no = order.tracking_no ?? ''; shippingDialogVisible.value = true }
async function shipOrder() {
  if (!shippingOrder.value) return
  if (shippingOrder.value.delivery_method === 'shipping' && (!shippingForm.carrier.trim() || !shippingForm.tracking_no.trim())) return ElMessage.warning('请填写快递公司和物流单号')
  saving.value = true
  try { await updateWarehouseOutboundStatus(shippingOrder.value.id, { status: 'shipped', carrier: shippingForm.carrier.trim(), tracking_no: shippingForm.tracking_no.trim() }); shippingDialogVisible.value = false; ElMessage.success('出库完成，库存已扣减'); await loadData() }
  catch (error) { ElMessage.error(errorMessage(error, '确认出库失败')) } finally { saving.value = false }
}
async function cancelOrder(order: WarehouseOutboundOrder) {
  try { await ElMessageBox.confirm(`取消出库单 ${order.order_no}？锁定库存会自动释放。`, '取消出库单', { type: 'warning' }); await updateWarehouseOutboundStatus(order.id, { status: 'cancelled' }); ElMessage.success('出库单已取消'); await loadData() }
  catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(errorMessage(error, '取消失败')) }
}
function itemSummary(items: WarehouseInboundOrder['items']) { return items.map((item) => `${item.sku} × ${item.quantity}`).join('；') }
onMounted(loadData)
</script>

<template>
  <div class="page-stack">
    <section class="page-block list-surface list-surface--fixed" v-loading="loading">
      <div class="filter-panel warehouse-filter-panel">
        <div class="query-grow">
          <div class="section-desc" style="margin-bottom: 8px">关键词查询</div>
          <el-input v-model="keyword" clearable size="large" placeholder="搜索 SKU、单号、仓库或物流" :prefix-icon="Search" />
        </div>
        <div v-if="!['products','warehouses'].includes(activeTab)" class="warehouse-filter-controls">
          <div><div class="section-desc" style="margin-bottom: 8px">仓库</div><el-select v-model="selectedWarehouseId" style="width:190px"><el-option label="全部仓库" :value="0" /><el-option v-for="item in activeWarehouses" :key="item.id" :label="item.name" :value="item.id" /></el-select></div>
          <div v-if="activeTab === 'outbound'"><div class="section-desc" style="margin-bottom: 8px">出库状态</div><el-select v-model="selectedOutboundStatus" style="width:150px"><el-option label="全部状态" value="all" /><el-option v-for="(meta,key) in statusMeta" :key="key" :label="meta.label" :value="key" /></el-select></div>
        </div>
      </div>
      <div class="toolbar-row">
        <div class="warehouse-toolbar-context">
          <p v-if="['products','warehouses'].includes(activeTab)" class="section-desc">{{ viewMeta.description }}</p>
          <div v-else class="compact-summary">
            <span>库存 <strong>{{ summary.total_quantity }}</strong> 件</span>
            <span>待出库 <strong>{{ summary.pending_outbound_count }}</strong> 单</span>
            <span :class="{ danger: summary.low_stock_count > 0 }">预警 <strong>{{ summary.low_stock_count }}</strong> 项</span>
            <span>今日入 / 出 <strong>{{ summary.today_inbound_quantity }} / {{ summary.today_outbound_quantity }}</strong> 件</span>
            <span>总成本 <strong class="cost">¥{{ Number(summary.total_cost).toFixed(2) }}</strong></span>
          </div>
        </div>
        <div class="toolbar-actions">
        <el-radio-group v-if="props.mode === 'master'" v-model="masterDataTab" class="master-data-switch">
          <el-radio-button label="products">商品档案</el-radio-button>
          <el-radio-button label="warehouses">仓库管理</el-radio-button>
        </el-radio-group>
        <el-button v-if="canWrite && activeTab === 'inbound'" type="primary" :icon="Plus" @click="openInbound">新建入库单</el-button>
        <el-button v-if="canWrite && activeTab === 'outbound'" type="success" :icon="Ship" @click="openOutbound">新建出库单</el-button>
        <el-button v-if="canWrite && activeTab === 'products'" type="primary" :icon="Plus" @click="resetProductForm()">新增商品</el-button>
        <el-button v-if="canWrite && activeTab === 'warehouses'" type="primary" :icon="Plus" @click="resetWarehouseForm()">新增仓库</el-button>
        <el-tooltip content="刷新仓储数据"><el-button :icon="Refresh" circle aria-label="刷新仓储数据" @click="loadData" /></el-tooltip>
        </div>
      </div>
      <div class="warehouse-workspace table-area fixed-list-shell">
        <div v-if="activeTab === 'stock'" class="warehouse-view-panel">
          <el-table :data="paginatedStocks" height="100%" stripe empty-text="暂无库存商品，请先在商品档案中建立商品并办理入库">
            <el-table-column label="图片" width="68"><template #default="{ row }"><el-image v-if="row.image_url" :src="row.image_url" fit="cover" class="product-thumb" :preview-src-list="[row.image_url]" preview-teleported /><div v-else class="product-thumb product-thumb--empty"><el-icon><Goods /></el-icon></div></template></el-table-column>
            <el-table-column prop="warehouse_name" label="仓库" min-width="130" sortable />
            <el-table-column prop="sku" label="SKU" min-width="140" sortable />
            <el-table-column prop="product_name" label="商品名称" min-width="180" show-overflow-tooltip />
            <el-table-column prop="specification" label="规格" min-width="130" show-overflow-tooltip />
            <el-table-column prop="quantity" label="实际库存" width="110" sortable />
            <el-table-column prop="locked_quantity" label="已锁定" width="100" sortable />
            <el-table-column prop="available_quantity" label="可用库存" width="110" sortable>
              <template #default="{ row }"><strong :class="{ 'stock-danger': row.is_low_stock }">{{ row.available_quantity }}</strong></template>
            </el-table-column>
            <el-table-column prop="warning_quantity" label="预警值" width="90" />
            <el-table-column prop="cost_price" label="成本价" width="100"><template #default="{ row }">¥{{ Number(row.cost_price).toFixed(2) }}</template></el-table-column>
            <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="row.is_low_stock ? 'danger' : 'success'" effect="plain">{{ row.is_low_stock ? '库存不足' : '正常' }}</el-tag></template></el-table-column>
          </el-table>
          <ListPaginationFooter v-model:current-page="pages.stock" :total-pages="pageCount(filteredStocks.length)" :page-size="pageSize" :total-items="filteredStocks.length" item-unit="条库存" />
        </div>
        <div v-else-if="activeTab === 'outbound'" class="warehouse-view-panel">
          <el-table :data="paginatedOutbound" height="100%" stripe empty-text="暂无符合条件的出库单">
            <el-table-column prop="order_no" label="出库单号" min-width="190" fixed />
            <el-table-column prop="external_order_no" label="平台订单号" min-width="150" />
            <el-table-column prop="warehouse_name" label="仓库" width="120" />
            <el-table-column label="商品明细" min-width="220" show-overflow-tooltip><template #default="{ row }">{{ itemSummary(row.items) }}</template></el-table-column>
            <el-table-column prop="recipient_name" label="收件人" width="100" />
            <el-table-column label="出库方式" width="100"><template #default="{ row }">{{ row.delivery_method === 'pickup' ? '到店自提' : '物流配送' }}</template></el-table-column>
            <el-table-column prop="tracking_no" label="物流单号" min-width="150"><template #default="{ row }">{{ row.delivery_method === 'pickup' ? '—' : (row.tracking_no || '—') }}</template></el-table-column>
            <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="outboundStatusMeta(row.status).type">{{ outboundStatusMeta(row.status).label }}</el-tag></template></el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="170"><template #default="{ row }">{{ formatDateTime(row.created_at) }}</template></el-table-column>
            <el-table-column v-if="canWrite" label="操作" width="190" fixed="right"><template #default="{ row }">
              <el-button v-if="outboundNextStatus(row.status)" link type="primary" @click="advance(row)">{{ outboundNextLabel(row.status) }}</el-button>
              <el-button v-if="row.status === 'packed'" link type="success" @click="openShipping(row)">确认出库</el-button>
              <el-button v-if="!['shipped','cancelled'].includes(row.status)" link type="danger" @click="cancelOrder(row)">取消</el-button>
            </template></el-table-column>
          </el-table>
          <ListPaginationFooter v-model:current-page="pages.outbound" :total-pages="pageCount(filteredOutbound.length)" :page-size="pageSize" :total-items="filteredOutbound.length" item-unit="张出库单" />
        </div>
        <div v-else-if="activeTab === 'inbound'" class="warehouse-view-panel">
          <el-table :data="paginatedInbound" height="100%" stripe empty-text="暂无入库记录">
            <el-table-column prop="order_no" label="入库单号" min-width="190" />
            <el-table-column prop="warehouse_name" label="仓库" width="130" />
            <el-table-column prop="source_type" label="类型" width="100"><template #default="{ row }">{{ inboundSourceLabel(row.source_type) }}</template></el-table-column>
            <el-table-column prop="supplier" label="供应商/来源" min-width="150" />
            <el-table-column label="商品明细" min-width="260" show-overflow-tooltip><template #default="{ row }">{{ itemSummary(row.items) }}</template></el-table-column>
            <el-table-column prop="operator_username" label="操作人" width="110" />
            <el-table-column prop="completed_at" label="入库时间" width="170"><template #default="{ row }">{{ formatDateTime(row.completed_at) }}</template></el-table-column>
            <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.status === 'completed' ? 'success' : 'info'" effect="plain">{{ row.status === 'completed' ? '已入库' : '已撤销' }}</el-tag></template></el-table-column>
            <el-table-column v-if="canWrite" label="操作" width="130" fixed="right"><template #default="{ row }"><template v-if="row.status === 'completed'"><el-button link type="primary" @click="editInbound(row)">纠错</el-button><el-button link type="danger" @click="cancelInbound(row)">撤销</el-button></template><span v-else class="section-desc">不可操作</span></template></el-table-column>
          </el-table>
          <ListPaginationFooter v-model:current-page="pages.inbound" :total-pages="pageCount(filteredInbound.length)" :page-size="pageSize" :total-items="filteredInbound.length" item-unit="张入库单" />
        </div>
        <div v-else-if="activeTab === 'movement'" class="warehouse-view-panel">
          <el-table :data="paginatedMovements" height="100%" stripe empty-text="暂无库存变动记录">
            <el-table-column prop="created_at" label="时间" width="170"><template #default="{ row }">{{ formatDateTime(row.created_at) }}</template></el-table-column>
            <el-table-column prop="warehouse_name" label="仓库" width="130" />
            <el-table-column prop="sku" label="SKU" min-width="140" />
            <el-table-column prop="product_name" label="商品" min-width="180" />
            <el-table-column prop="quantity_change" label="变动" width="100"><template #default="{ row }"><strong :class="row.quantity_change > 0 ? 'stock-in' : 'stock-out'">{{ row.quantity_change > 0 ? '+' : '' }}{{ row.quantity_change }}</strong></template></el-table-column>
            <el-table-column prop="quantity_after" label="结存" width="90" />
            <el-table-column prop="reference_no" label="关联单号" min-width="190" />
            <el-table-column prop="operator_username" label="操作人" width="110" />
          </el-table>
          <ListPaginationFooter v-model:current-page="pages.movement" :total-pages="pageCount(filteredMovements.length)" :page-size="pageSize" :total-items="filteredMovements.length" item-unit="条流水" />
        </div>
        <div v-else-if="activeTab === 'warehouses'" class="warehouse-view-panel master-data-panel">
            <div class="settings-panel"><div class="panel-head"><h3>仓库列表</h3><span class="section-desc">共 {{ filteredWarehouses.length }} 个仓库</span></div>
              <el-table :data="paginatedWarehouses" height="calc(100vh - 450px)" stripe><el-table-column prop="code" label="编码" width="110" /><el-table-column prop="name" label="名称" min-width="130" /><el-table-column prop="address" label="地址" min-width="160" show-overflow-tooltip /><el-table-column label="状态" width="80"><template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'" effect="plain">{{ row.is_active ? '启用' : '停用' }}</el-tag></template></el-table-column><el-table-column v-if="canWrite" label="操作" width="70"><template #default="{ row }"><el-button link type="primary" @click="resetWarehouseForm(row)">编辑</el-button></template></el-table-column></el-table>
              <ListPaginationFooter v-model:current-page="pages.warehouses" :total-pages="pageCount(filteredWarehouses.length)" :page-size="pageSize" :total-items="filteredWarehouses.length" item-unit="个仓库" />
            </div>
        </div>
        <div v-else class="warehouse-view-panel master-data-panel">
            <div class="settings-panel"><div class="panel-head"><h3>商品列表</h3><span class="section-desc">共 {{ filteredProducts.length }} 个商品</span></div>
              <el-table :data="paginatedProducts" height="calc(100vh - 450px)" stripe><el-table-column label="图片" width="62"><template #default="{ row }"><el-image v-if="row.image_url" :src="row.image_url" fit="cover" class="product-thumb" /></template></el-table-column><el-table-column prop="sku" label="SKU" min-width="120" /><el-table-column prop="name" label="商品名称" min-width="150" /><el-table-column prop="specification" label="规格" min-width="100" /><el-table-column prop="cost_price" label="成本价" width="90"><template #default="{ row }">¥{{ Number(row.cost_price).toFixed(2) }}</template></el-table-column><el-table-column prop="warning_quantity" label="预警" width="70" /><el-table-column v-if="canWrite" label="操作" width="70"><template #default="{ row }"><el-button link type="primary" @click="resetProductForm(row)">编辑</el-button></template></el-table-column></el-table>
              <ListPaginationFooter v-model:current-page="pages.products" :total-pages="pageCount(filteredProducts.length)" :page-size="pageSize" :total-items="filteredProducts.length" item-unit="个商品" />
            </div>
        </div>
      </div>
    </section>

    <el-dialog v-model="warehouseDialogVisible" :title="editingWarehouseId ? '编辑仓库' : '新增仓库'" width="560px"><el-form label-position="top"><div class="form-grid"><el-form-item label="仓库编码"><el-input v-model="warehouseForm.code" /></el-form-item><el-form-item label="仓库名称"><el-input v-model="warehouseForm.name" /></el-form-item><el-form-item label="联系人"><el-input v-model="warehouseForm.contact_name" /></el-form-item><el-form-item label="联系电话"><el-input v-model="warehouseForm.contact_phone" /></el-form-item></div><el-form-item label="地址"><el-input v-model="warehouseForm.address" /></el-form-item><el-form-item label="备注"><el-input v-model="warehouseForm.remark" type="textarea" :rows="2" /></el-form-item><el-switch v-model="warehouseForm.is_active" active-text="启用" /></el-form><template #footer><el-button @click="warehouseDialogVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="saveWarehouse">保存</el-button></template></el-dialog>
    <el-dialog v-model="productDialogVisible" :title="editingProductId ? '编辑商品' : '新增商品'" width="660px"><el-form label-position="top"><div class="product-image-editor"><div class="product-image-preview"><img v-if="productImagePreview" :src="productImagePreview" alt="商品图片预览" /><el-icon v-else><Goods /></el-icon></div><div><label class="image-picker"><input type="file" accept="image/jpeg,image/png,image/webp" @change="selectProductImage" /><span>{{ productImagePreview ? '更换商品图片' : '选择商品图片' }}</span></label><p>支持 JPG、PNG、WebP，最大 15MB</p></div></div><div class="form-grid"><el-form-item label="SKU"><el-input v-model="productForm.sku" /></el-form-item><el-form-item label="商品名称"><el-input v-model="productForm.name" /></el-form-item><el-form-item label="条码"><el-input v-model="productForm.barcode" /></el-form-item><el-form-item label="规格"><el-input v-model="productForm.specification" /></el-form-item><el-form-item label="单位"><el-input v-model="productForm.unit" /></el-form-item><el-form-item label="成本价（元）"><el-input-number v-model="productForm.cost_price" :min="0" :precision="2" :step="1" :value-on-clear="0" controls-position="right" class="product-number-input" /></el-form-item><el-form-item label="库存预警值（件）"><el-input-number v-model="productForm.warning_quantity" :min="0" :precision="0" :step="1" :value-on-clear="0" step-strictly controls-position="right" class="product-number-input" /></el-form-item></div><el-form-item label="备注"><el-input v-model="productForm.remark" type="textarea" :rows="2" /></el-form-item><el-switch v-model="productForm.is_active" active-text="启用" /></el-form><template #footer><el-button @click="productDialogVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="saveProduct">保存</el-button></template></el-dialog>

    <el-dialog v-model="inboundDialogVisible" :title="editingInboundId ? '纠错入库单' : '商品入库'" width="720px"><el-form label-position="top"><div class="form-grid"><el-form-item label="入库仓库"><el-select v-model="inboundForm.warehouse_id" style="width:100%"><el-option v-for="item in activeWarehouses" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item><el-form-item label="入库类型"><el-select v-model="inboundForm.source_type" style="width:100%"><el-option label="采购入库" value="purchase" /><el-option label="退货入库" value="return" /><el-option label="其他入库" value="other" /></el-select></el-form-item></div><el-form-item label="供应商/来源"><el-input v-model="inboundForm.supplier" /></el-form-item><div class="line-head"><span>入库商品</span><el-button :icon="Plus" @click="addLine(inboundForm.items)">添加商品</el-button></div><div v-for="(line,index) in inboundForm.items" :key="index" class="order-line"><el-select v-model="line.product_id" filterable style="flex:1"><el-option v-for="item in activeProducts" :key="item.id" :label="`${item.sku} · ${item.name}${item.specification ? ` · ${item.specification}` : ''}`" :value="item.id" /></el-select><el-input-number v-model="line.quantity" :min="1" /><el-button text type="danger" :disabled="inboundForm.items.length===1" @click="removeLine(inboundForm.items,index)">移除</el-button></div><el-form-item label="备注"><el-input v-model="inboundForm.remark" type="textarea" :rows="2" /></el-form-item></el-form><template #footer><el-button @click="inboundDialogVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="saveInbound">{{ editingInboundId ? '保存纠错' : '确认入库' }}</el-button></template></el-dialog>
    <el-dialog v-model="outboundDialogVisible" title="新建出库单" width="760px"><el-form label-position="top"><el-form-item label="出库方式"><el-radio-group v-model="outboundForm.delivery_method"><el-radio-button value="shipping">物流配送</el-radio-button><el-radio-button value="pickup">到店自提</el-radio-button></el-radio-group></el-form-item><div class="form-grid"><el-form-item label="出库仓库"><el-select v-model="outboundForm.warehouse_id" style="width:100%"><el-option v-for="item in activeWarehouses" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item><el-form-item label="平台订单号"><el-input v-model="outboundForm.external_order_no" /></el-form-item><el-form-item :label="outboundForm.delivery_method === 'pickup' ? '提货人' : '收件人'"><el-input v-model="outboundForm.recipient_name" /></el-form-item><el-form-item label="联系电话"><el-input v-model="outboundForm.recipient_phone" /></el-form-item></div><el-form-item v-if="outboundForm.delivery_method === 'shipping'" label="收货地址"><el-input v-model="outboundForm.recipient_address" /></el-form-item><div class="line-head"><span>出库商品</span><el-button :icon="Plus" @click="addLine(outboundForm.items)">添加商品</el-button></div><div v-for="(line,index) in outboundForm.items" :key="index" class="order-line"><el-select v-model="line.product_id" filterable style="flex:1"><el-option v-for="item in activeProducts" :key="item.id" :label="`${item.sku} · ${item.name}`" :value="item.id" /></el-select><el-input-number v-model="line.quantity" :min="1" /><el-button text type="danger" :disabled="outboundForm.items.length===1" @click="removeLine(outboundForm.items,index)">移除</el-button></div><el-form-item label="备注"><el-input v-model="outboundForm.remark" type="textarea" :rows="2" /></el-form-item></el-form><template #footer><el-button @click="outboundDialogVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="saveOutbound">创建并锁定库存</el-button></template></el-dialog>
    <el-dialog v-model="shippingDialogVisible" :title="shippingOrder?.delivery_method === 'pickup' ? '确认自提出库' : '确认发货出库'" width="520px"><el-alert :title="shippingOrder?.delivery_method === 'pickup' ? '确认客户已提货后，将扣减实际库存并生成出库流水。' : '确认后将扣减实际库存并生成出库流水，此操作不可撤销。'" type="warning" :closable="false" show-icon /><el-form v-if="shippingOrder?.delivery_method === 'shipping'" label-position="top" class="shipping-form"><el-form-item label="快递公司"><el-input v-model="shippingForm.carrier" /></el-form-item><el-form-item label="物流单号"><el-input v-model="shippingForm.tracking_no" /></el-form-item></el-form><template #footer><el-button @click="shippingDialogVisible=false">取消</el-button><el-button type="success" :loading="saving" @click="shipOrder">{{ shippingOrder?.delivery_method === 'pickup' ? '确认已提货' : '确认出库' }}</el-button></template></el-dialog>
  </div>
</template>

<style scoped>
.warehouse-page{display:flex;flex-direction:column;gap:12px;min-height:0}.warehouse-toolbar,.warehouse-workspace{background:#fff;border:1px solid #e5e9f0;border-radius:6px}.warehouse-toolbar{padding:14px 16px;display:flex;align-items:center;justify-content:space-between;gap:20px}.summary-strip{display:flex;align-items:center;gap:0;min-width:0}.summary-strip>div{padding:0 22px;border-right:1px solid #e7ebf0}.summary-strip>div:first-child{padding-left:0}.summary-strip>div:last-child{border-right:0}.summary-strip span{display:block;color:#6b7685;font-size:12px;white-space:nowrap}.summary-strip strong{display:block;margin-top:3px;font-size:22px;color:#172033}.summary-strip .alert strong{color:#d33b3b}.toolbar-actions{display:flex;align-items:center;gap:8px}.toolbar-actions .el-input{width:260px}.warehouse-workspace{padding:0 16px;min-height:0}.tab-label{display:inline-flex;align-items:center;gap:6px}.settings-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.35fr);gap:16px;padding-bottom:16px}.settings-panel{border:1px solid #e5e9f0;border-radius:6px;padding:12px}.panel-head,.line-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}.panel-head h3{font-size:15px;margin:0}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 16px}.order-line{display:flex;align-items:center;gap:10px;margin-bottom:10px}.shipping-form{margin-top:18px}.stock-danger,.stock-out{color:#d33b3b}.stock-in{color:#16865b}@media(max-width:1100px){.warehouse-toolbar{align-items:flex-start;flex-direction:column}.toolbar-actions{width:100%}.toolbar-actions .el-input{flex:1}.summary-strip{width:100%;overflow-x:auto}.settings-grid{grid-template-columns:1fr}}@media(max-width:700px){.summary-strip>div{padding:0 14px}.summary-strip strong{font-size:18px}.toolbar-actions{flex-wrap:wrap}.toolbar-actions .el-input{flex-basis:100%;width:100%}.form-grid{grid-template-columns:1fr}.order-line{align-items:stretch;flex-wrap:wrap}.order-line .el-select{flex-basis:100%!important}}
.product-thumb{width:38px;height:38px;border-radius:4px;border:1px solid #e3e8ef}.product-thumb--empty{display:flex;align-items:center;justify-content:center;color:#9aa6b2;background:#f4f6f8}.product-image-editor{display:flex;align-items:center;gap:16px;padding:12px;margin-bottom:16px;background:#f7f8fa;border:1px solid #e5e9f0;border-radius:6px}.product-image-preview{width:88px;height:88px;display:flex;align-items:center;justify-content:center;overflow:hidden;border:1px solid #dfe4ea;border-radius:6px;background:#fff;color:#9aa6b2;font-size:28px}.product-image-preview img{width:100%;height:100%;object-fit:cover}.image-picker{display:inline-flex;align-items:center;height:32px;padding:0 14px;border:1px solid #409eff;border-radius:4px;color:#1677c8;background:#fff;cursor:pointer}.image-picker input{display:none}.product-image-editor p{margin:7px 0 0;color:#7b8794;font-size:12px}
.product-number-input{width:100%}
.warehouse-filter-panel{align-items:flex-end}.warehouse-filter-panel .query-grow{min-width:280px}.warehouse-workspace{padding:18px 22px 22px;min-height:0;border:0;border-radius:0;background:transparent}.warehouse-workspace :deep(.el-tabs__header){margin-bottom:12px}.warehouse-workspace :deep(.el-tabs__content){overflow:visible}.settings-panel :deep(.list-pagination-footer){padding-bottom:0}.summary-cost{min-width:150px}.summary-cost strong{color:#1677c8}
.warehouse-filter-panel{grid-template-columns:minmax(320px,1fr) auto;padding-top:16px;padding-bottom:16px}.warehouse-filter-controls{display:flex;align-items:flex-end;justify-content:flex-end;gap:12px}.warehouse-kpis{display:grid;grid-template-columns:repeat(6,minmax(112px,1fr));min-width:0;border-bottom:1px solid var(--panel-border);background:#fbfcfe}.warehouse-kpis>div{position:relative;min-width:0;padding:14px 20px;border-right:1px solid var(--panel-border)}.warehouse-kpis>div:last-child{border-right:0}.warehouse-kpis span{display:block;color:var(--text-secondary);font-size:12px;white-space:nowrap}.warehouse-kpis strong{display:inline-block;margin-top:4px;color:var(--text-main);font-size:22px;line-height:1.15}.warehouse-kpis small{margin-left:5px;color:var(--text-secondary);font-size:12px}.warehouse-kpis .alert strong{color:var(--brand-danger)}.warehouse-kpis .summary-cost{background:#f5f9ff}.warehouse-kpis .summary-cost strong{color:var(--brand-primary);font-size:20px}.tab-label em{display:inline-flex;align-items:center;justify-content:center;min-width:22px;height:20px;padding:0 6px;border-radius:10px;background:#eef2f7;color:#6b7685;font-size:11px;font-style:normal}.warehouse-workspace{overflow:hidden}.warehouse-workspace :deep(.el-tabs__nav-wrap){padding:0 2px}.warehouse-workspace :deep(.el-tabs__item.is-active) .tab-label em{background:#e8f1ff;color:var(--brand-primary)}
@media(max-width:1200px){.warehouse-kpis{grid-template-columns:repeat(3,minmax(120px,1fr))}.warehouse-kpis>div:nth-child(3){border-right:0}.warehouse-kpis>div:nth-child(-n+3){border-bottom:1px solid var(--panel-border)}}
@media(max-width:900px){.warehouse-filter-panel{grid-template-columns:1fr}.warehouse-filter-controls{justify-content:flex-start}.warehouse-kpis{grid-template-columns:repeat(2,minmax(120px,1fr))}.warehouse-kpis>div:nth-child(3){border-right:1px solid var(--panel-border)}.warehouse-kpis>div:nth-child(2n){border-right:0}.warehouse-kpis>div{border-bottom:1px solid var(--panel-border)}}
@media(max-width:600px){.warehouse-filter-controls{align-items:stretch;flex-direction:column}.warehouse-filter-controls>div,.warehouse-filter-controls :deep(.el-select){width:100%!important}.warehouse-kpis>div{padding:12px 14px}.warehouse-kpis strong{font-size:19px}.warehouse-kpis .summary-cost strong{font-size:17px}}
.warehouse-view-panel{display:grid;grid-template-rows:minmax(0,1fr) auto;flex:1 1 auto;min-height:0;height:100%}.warehouse-view-panel>.el-table{min-height:0}.master-data-panel .settings-panel{display:flex;flex:1 1 auto;min-height:0;flex-direction:column;padding:0;border:0;border-radius:0}.master-data-panel .panel-head{padding:0 0 12px;margin:0}.master-data-panel .panel-head .section-desc{margin:0}.master-data-panel .settings-panel :deep(.el-table){flex:1 1 auto}
.warehouse-toolbar-context{min-width:0}.warehouse-toolbar-context>.section-desc{margin:0}.compact-summary{display:flex;align-items:center;gap:0;min-height:34px;flex-wrap:wrap;color:var(--text-secondary);font-size:13px}.compact-summary>span{display:inline-flex;align-items:baseline;white-space:nowrap}.compact-summary>span+span::before{content:'';width:1px;height:14px;margin:0 14px;background:var(--panel-border)}.compact-summary strong{margin:0 3px;color:var(--text-main);font-size:15px}.compact-summary .danger strong{color:var(--brand-danger)}.compact-summary .cost{color:var(--brand-primary)}
@media(max-width:768px){.compact-summary{gap:8px}.compact-summary>span{padding:4px 8px;border:1px solid var(--panel-border);border-radius:4px;background:#f8fafc}.compact-summary>span+span::before{display:none}}
</style>
