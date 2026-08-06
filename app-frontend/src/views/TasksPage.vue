<script setup lang="ts">
import { computed } from 'vue'
import { IonContent, IonIcon, IonPage } from '@ionic/vue'
import { useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import { appModules, canOpenModule } from '../modules'
import { can, session } from '../session'

const router = useRouter()
const items = computed(() => appModules.filter((item) => item.group === '任务记账' && canOpenModule(item, session.user?.role, can)))
</script>

<template><IonPage><PageHeader title="任务" subtitle="任务、利润与记账" hide-avatar /><IonContent><main class="page-pad task-page"><section class="compact-list"><button v-for="item in items" :key="item.key" class="compact-row task-row" @click="router.push(item.route)"><span class="module-icon mini" :style="{background:`${item.color}18`,color:item.color}"><IonIcon :icon="item.icon" /></span><div><h3>{{ item.title }}</h3><p>{{ item.subtitle }}</p></div><b>›</b></button></section></main></IonContent></IonPage></template>

<style scoped>.task-page{padding-top:10px}.task-row{width:100%;border:0;background:none;text-align:left;color:inherit}.mini{width:42px;height:42px;margin:0}.task-row b{color:var(--app-muted);font-size:24px}</style>
