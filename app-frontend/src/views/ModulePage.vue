<script setup lang="ts">
import { computed } from 'vue'
import { IonContent, IonIcon, IonPage } from '@ionic/vue'
import { chatbubbleEllipsesOutline, cubeOutline, serverOutline } from 'ionicons/icons'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
const route = useRoute(); const router = useRouter()
const config = computed(() => ({
  warehouse: { title: '仓储管理', note: '库存、出入库和基础资料', icon: cubeOutline, actions: [['库存总览','/tabs/list/inventory'],['入库管理','/tabs/list/inbound'],['出库发货','/tabs/list/outbound'],['库存流水','/tabs/list/stock-movements']] },
  server: { title: '服务器运行', note: '服务器资源与运行状态', icon: serverOutline, actions: [['运行状态','/tabs/module/server']] },
  knowledge: { title: '知识问答', note: '知识问答、知识管理与数据质量', icon: chatbubbleEllipsesOutline, actions: [['知识问答','/tabs/module/knowledge']] },
  approvals: { title: '审批中心', note: '集中处理待审批事项', icon: chatbubbleEllipsesOutline, actions: [['公司消费审批','/tabs/list/company-expenses']] },
}[String(route.params.moduleKey)] || { title: '功能模块', note: '移动端页面', icon: cubeOutline, actions: [] as string[][] }))
const open = (path: string) => router.push(path)
</script>
<template><IonPage><PageHeader :title="config.title" :subtitle="config.note" back /><IonContent><main class="page-pad"><section class="module-hero panel"><span class="module-icon"><IonIcon :icon="config.icon" /></span><h1>{{ config.title }}</h1><p>{{ config.note }}</p></section><div class="section-title"><h2>功能入口</h2><span>{{ config.actions.length }} 项</span></div><section class="compact-list"><button v-for="action in config.actions" :key="action[0]" class="compact-row action" @click="open(action[1])"><div><h3>{{ action[0] }}</h3><p>点击进入功能页面</p></div><b>›</b></button></section></main></IonContent></IonPage></template>
<style scoped>.module-hero{text-align:center;padding:30px}.module-hero .module-icon{background:#e8f1ff;color:#2563eb}.module-hero h1{margin:12px 0 5px}.module-hero p{margin:0;color:var(--app-muted)}.action{grid-template-columns:1fr auto;width:100%;border:0;background:none;text-align:left;color:inherit}.action b{font-size:24px;color:var(--app-muted)}</style>
