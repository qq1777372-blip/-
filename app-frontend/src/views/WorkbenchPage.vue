<script setup lang="ts">
import { computed, ref } from 'vue'
import { IonContent, IonIcon, IonPage, onIonViewWillEnter } from '@ionic/vue'
import { searchOutline } from 'ionicons/icons'
import { useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import { appModules, canOpenModule } from '../modules'
import { can, session } from '../session'
const router = useRouter(); const query = ref('')
const content = ref<InstanceType<typeof IonContent> | null>(null)
onIonViewWillEnter(() => content.value?.$el.scrollToTop(0))
const groups = computed(() => {
  const result: Record<string, typeof appModules> = {}
  for (const item of appModules) {
    if (!canOpenModule(item, session.user?.role, can)) continue
    if (query.value && !`${item.title}${item.subtitle}${item.group}`.toLowerCase().includes(query.value.toLowerCase())) continue
    ;(result[item.group] ||= []).push(item)
  }
  return result
})
</script>
<template><IonPage><PageHeader title="全部功能" subtitle="按分组查看全部模块" back /><IonContent ref="content"><main class="workbench-page">
  <label class="workbench-search"><IonIcon :icon="searchOutline" /><input v-model="query" placeholder="搜索功能"></label>
  <section v-for="(items,group) in groups" :key="group" class="feature-section"><h2>{{ group }}</h2><div class="feature-grid"><button v-for="item in items" :key="item.key" @click="router.push(item.route)"><span :style="{background:`${item.color}15`,color:item.color}"><IonIcon :icon="item.icon" /></span><b>{{ item.title }}</b><small>{{ item.subtitle }}</small></button></div></section>
  <div v-if="!Object.keys(groups).length" class="empty-state">没有匹配的功能</div>
</main></IonContent></IonPage></template>
<style scoped>.workbench-page{padding:12px 16px 40px}.workbench-search{height:44px;display:flex;align-items:center;gap:8px;padding:0 13px;border-radius:14px;background:var(--app-card);box-shadow:0 4px 18px rgba(15,23,42,.05)}.workbench-search input{min-width:0;flex:1;border:0;outline:0;color:var(--app-text);background:transparent;font-size:16px}.feature-section{padding:20px 0 4px}.feature-section h2{margin:0 0 13px 2px;font-size:16px}.feature-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:20px 8px}.feature-grid button{min-width:0;padding:0;border:0;text-align:center;color:var(--app-text);background:transparent}.feature-grid span{width:50px;height:50px;margin:0 auto 7px;display:grid;place-items:center;border-radius:16px}.feature-grid ion-icon{font-size:25px}.feature-grid b,.feature-grid small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.feature-grid b{font-size:12px}.feature-grid small{display:none;color:var(--app-muted);font-size:10px}@media(min-width:600px){.feature-grid{grid-template-columns:repeat(auto-fill,minmax(88px,112px));justify-content:start;gap:20px 12px}.feature-grid small{display:block;margin-top:3px}}</style>
