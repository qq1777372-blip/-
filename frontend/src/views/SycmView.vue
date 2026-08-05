<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

type Snapshot = { id: number; shopId: string; shopName: string; collectedAt: string; receivedAt: string; uv: number | null; pv: number | null; cartByrCnt: number | null; payByrCnt: number | null; payAmt: number | null; payRate: number | null }
const shops = ref<Snapshot[]>([])
const history = ref<Snapshot[]>([])
const selectedShop = ref('')
const loading = ref(false)
const selected = computed(() => shops.value.find((item) => item.shopId === selectedShop.value) || shops.value[0])
const number = (value: number | null) => value == null ? '--' : new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value)
const money = (value: number | null) => value == null ? '--' : `¥${number(value)}`
const percent = (value: number | null) => value == null ? '--' : `${(value * 100).toFixed(2)}%`
const time = (value: string) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '--'

async function request<T>(url: string): Promise<T> {
  const response = await fetch(url, { credentials: 'include' })
  if (!response.ok) throw new Error(`请求失败 (${response.status})`)
  return response.json() as Promise<T>
}
async function loadHistory() { history.value = selectedShop.value ? await request<Snapshot[]>(`/api/sycm/shops/${encodeURIComponent(selectedShop.value)}/snapshots?limit=100`) : [] }
async function load() {
  loading.value = true
  try {
    shops.value = await request<Snapshot[]>('/api/sycm/latest')
    if (!selectedShop.value && shops.value.length) selectedShop.value = shops.value[0].shopId
    await loadHistory()
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '生意参谋数据加载失败') }
  finally { loading.value = false }
}
onMounted(load)
</script>

<template><div v-loading="loading" class="sycm-page">
  <section class="toolbar"><div><h2>店铺经营数据</h2><p>查看采集软件上传的实时数据和历史记录</p></div><el-select v-model="selectedShop" placeholder="选择店铺" filterable @change="loadHistory"><el-option v-for="shop in shops" :key="shop.shopId" :label="shop.shopName" :value="shop.shopId" /></el-select><el-button @click="load">刷新</el-button></section>
  <section v-if="selected" class="metrics"><div><span>访客数</span><strong>{{ number(selected.uv) }}</strong></div><div><span>浏览量</span><strong>{{ number(selected.pv) }}</strong></div><div><span>加购人数</span><strong>{{ number(selected.cartByrCnt) }}</strong></div><div><span>支付买家数</span><strong>{{ number(selected.payByrCnt) }}</strong></div><div><span>支付金额</span><strong>{{ money(selected.payAmt) }}</strong></div><div><span>支付转化率</span><strong>{{ percent(selected.payRate) }}</strong></div></section>
  <section class="history"><header><h3>采集历史</h3><span>{{ selected ? `${selected.shopName} · 更新于 ${time(selected.collectedAt)}` : '暂无店铺数据' }}</span></header><el-table :data="history" stripe><el-table-column label="采集时间" min-width="180"><template #default="scope">{{ time(scope.row.collectedAt) }}</template></el-table-column><el-table-column prop="uv" label="访客" align="right" /><el-table-column prop="pv" label="浏览量" align="right" /><el-table-column prop="cartByrCnt" label="加购人数" align="right" /><el-table-column prop="payByrCnt" label="支付买家" align="right" /><el-table-column label="支付金额" align="right"><template #default="scope">{{ money(scope.row.payAmt) }}</template></el-table-column><el-table-column label="转化率" align="right"><template #default="scope">{{ percent(scope.row.payRate) }}</template></el-table-column></el-table></section>
</div></template>

<style scoped>
.sycm-page{display:grid;gap:16px}.toolbar{display:grid;grid-template-columns:1fr minmax(220px,320px) auto;gap:12px;align-items:center}.toolbar h2,.history h3{margin:0;color:var(--text-primary)}.toolbar h2{font-size:18px}.toolbar p{margin:6px 0 0;color:var(--text-secondary);font-size:13px}.metrics{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));border:1px solid var(--border-color);background:var(--surface-color)}.metrics div{min-width:0;padding:20px}.metrics div+div{border-left:1px solid var(--border-color)}.metrics span,.metrics strong{display:block}.metrics span{color:var(--text-secondary);font-size:13px}.metrics strong{margin-top:10px;font-size:24px;color:var(--text-primary)}.history{padding:18px;border:1px solid var(--border-color);background:var(--surface-color)}.history header{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}.history h3{font-size:16px}.history header span{color:var(--text-secondary);font-size:12px}@media(max-width:1100px){.metrics{grid-template-columns:repeat(3,1fr)}.metrics div:nth-child(4){border-left:0}}@media(max-width:720px){.toolbar{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,1fr)}.metrics div:nth-child(odd){border-left:0}}
</style>
