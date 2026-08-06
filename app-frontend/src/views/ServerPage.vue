<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { IonContent, IonPage, IonRefresher, IonRefresherContent, toastController } from '@ionic/vue'
import PageHeader from '../components/PageHeader.vue'
import { api, ApiError } from '../api'

type Service = { name:string; display_name:string; active_state:string; sub_state:string; is_active:boolean }
type Status = { health:string; hostname:string; operating_system:string; architecture:string; cpu_count:number; cpu_percent:number|null; memory_used_bytes:number; memory_total_bytes:number; memory_percent:number; disk_used_bytes:number; disk_total_bytes:number; disk_percent:number; process_uptime_seconds:number; database_count:number; database_total_size_bytes:number; database_connection_status:string; database_latency_ms:number|null; services:Service[] }
const status = ref<Partial<Status>>({ services: [] })
const loading = ref(true)
const size = (value = 0) => value >= 1024 ** 3 ? `${(value / 1024 ** 3).toFixed(1)} GB` : `${(value / 1024 ** 2).toFixed(0)} MB`
const uptime = computed(() => { const seconds = status.value.process_uptime_seconds || 0; const days = Math.floor(seconds / 86400); const hours = Math.floor(seconds % 86400 / 3600); return days ? `${days} 天 ${hours} 小时` : `${hours} 小时` })
async function load(event?: { target:{ complete:()=>void } }) { try { status.value = await api<Status>(`/dashboard/server-status${event ? '?refresh=true' : ''}`) } catch(error) { const toast=await toastController.create({message:error instanceof ApiError?error.detail:'服务器状态加载失败',duration:2200,color:'danger'});await toast.present() } finally { loading.value=false;event?.target.complete() } }
onMounted(() => load())
</script>

<template><IonPage><PageHeader title="服务器运行" subtitle="实时资源与服务状态" back /><IonContent><IonRefresher slot="fixed" @ion-refresh="load"><IonRefresherContent /></IonRefresher><main class="page-pad server-page">
  <section class="server-state"><span :class="status.health">{{ status.health === 'healthy' ? '运行正常' : status.health === 'warning' ? '需要关注' : '存在异常' }}</span><div><h1>{{ status.hostname || '服务器' }}</h1><p>{{ status.operating_system }} · {{ status.architecture }}</p></div></section>
  <section class="metric-strip server-metrics"><div><small>CPU</small><strong>{{ status.cpu_percent ?? 0 }}%</strong><span>{{ status.cpu_count || 0 }} 核</span></div><div><small>内存</small><strong>{{ status.memory_percent ?? 0 }}%</strong><span>{{ size(status.memory_used_bytes) }} / {{ size(status.memory_total_bytes) }}</span></div><div><small>磁盘</small><strong>{{ status.disk_percent ?? 0 }}%</strong><span>{{ size(status.disk_used_bytes) }} / {{ size(status.disk_total_bytes) }}</span></div></section>
  <section class="compact-list server-info"><div class="compact-row"><div><h3>数据库</h3><p>{{ status.database_count || 0 }} 个库 · {{ size(status.database_total_size_bytes) }}</p></div><strong>{{ status.database_connection_status === 'available' ? '正常' : '异常' }}</strong></div><div class="compact-row"><div><h3>接口延迟</h3><p>主数据库连接响应</p></div><strong>{{ status.database_latency_ms ?? 0 }} ms</strong></div><div class="compact-row"><div><h3>应用运行</h3><p>当前后台进程持续时间</p></div><strong>{{ uptime }}</strong></div></section>
  <div class="section-title"><h2>服务状态</h2><span>{{ status.services?.length || 0 }} 项</span></div><section class="compact-list"><div v-for="service in status.services" :key="service.name" class="compact-row service-row"><i :class="{active:service.is_active}"></i><div><h3>{{ service.display_name }}</h3><p>{{ service.active_state }} · {{ service.sub_state }}</p></div><strong>{{ service.is_active ? '正常' : '停止' }}</strong></div></section>
  <div v-if="!loading && !status.hostname" class="empty-state">暂无服务器状态</div>
</main></IonContent></IonPage></template>

<style scoped>.server-page{display:grid;gap:12px}.server-state{display:flex;align-items:center;gap:12px;padding:5px 2px 10px}.server-state>span{padding:5px 9px;border-radius:999px;color:#15803d;background:#dcfce7;font-size:11px}.server-state>span.warning{color:#b45309;background:#fef3c7}.server-state>span.critical{color:#dc2626;background:#fee2e2}.server-state h1,.server-state p{margin:0}.server-state h1{font-size:19px}.server-state p{margin-top:4px;color:var(--app-muted);font-size:11px}.server-metrics span{display:block;margin-top:5px;color:var(--app-muted);font-size:9px}.server-info strong,.service-row strong{color:var(--app-muted);font-size:11px}.service-row{grid-template-columns:8px 1fr auto}.service-row i{width:7px;height:7px;border-radius:50%;background:#ef4444}.service-row i.active{background:#22c55e}</style>
