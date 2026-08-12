<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { IonAvatar, IonButton, IonButtons, IonHeader, IonIcon, IonTitle, IonToolbar, useIonRouter } from '@ionic/vue'
import { chevronBackOutline, moonOutline, notifications, notificationsOutline, searchOutline, sunnyOutline } from 'ionicons/icons'
import { useRouter } from 'vue-router'
import { cleanOptionalUrl, session } from '../session'
import { alerts, refreshAlertCounts } from '../alerts'
import { fallbackPath } from '../navigation'
const props = withDefaults(defineProps<{ title: string; subtitle?: string; back?: boolean; hideAvatar?: boolean }>(), { back: false, hideAvatar: false })
const router = useRouter();const dark=ref(document.documentElement.classList.contains('ion-palette-dark'))
const ionRouter=useIonRouter()
const avatarUrl=computed(()=>cleanOptionalUrl(session.user?.avatar_url))
// Two cases only: Ionic has a real page stack to pop, or we arrived cold (deep
// link, reload, WebView entry) and have to synthesise the parent from the route.
// Both use the global 320ms nav animation so back matches forward.
function goBack(){
  (document.activeElement as HTMLElement|null)?.blur()
  if(ionRouter.canGoBack())ionRouter.back()
  else ionRouter.navigate(fallbackPath(router.currentRoute.value.fullPath),'back','replace')
}
function toggleTheme(){dark.value=!dark.value;document.documentElement.classList.toggle('ion-palette-dark',dark.value);localStorage.setItem('app-theme',dark.value?'dark':'light')}
// Only root pages render the bell, so only they pay for the count. The store
// dedupes concurrent calls, so several headers mounting at once is still one request.
const hasAlerts=computed(()=>alerts.openCount>0)
const badgeLabel=computed(()=>alerts.openCount>99?'99+':String(alerts.openCount))
onMounted(()=>{if(!props.back)void refreshAlertCounts()})
</script>
<template><IonHeader class="app-header" :class="{'is-subpage':back}"><IonToolbar>
  <IonButtons v-if="back" slot="start"><button class="app-native-back" type="button" aria-label="返回上一级" @click="goBack"><IonIcon :icon="chevronBackOutline" /></button></IonButtons>
  <IonTitle><strong>{{ title }}</strong><small v-if="subtitle">{{ subtitle }}</small></IonTitle>
<IonButtons v-if="!back" slot="end" class="root-actions"><IonButton aria-label="夜览模式" @click="toggleTheme"><IonIcon :icon="dark?sunnyOutline:moonOutline" /></IonButton><IonButton class="alert-button" :class="{'has-alerts':hasAlerts}" :aria-label="hasAlerts?`通知，${alerts.openCount} 条待处理`:'通知'" @click="router.push('/tabs/alerts')"><IonIcon :icon="hasAlerts?notifications:notificationsOutline" /><i v-if="hasAlerts" class="alert-badge">{{ badgeLabel }}</i></IonButton><IonButton aria-label="搜索" @click="router.push('/tabs/search')"><IonIcon :icon="searchOutline" /></IonButton><IonButton v-if="!hideAvatar" class="avatar-button" aria-label="我的" @click="router.push('/tabs/mine')"><IonAvatar><img v-if="avatarUrl" :src="avatarUrl" alt="头像" loading="lazy" decoding="async"><span v-else>{{ (session.user?.display_name||session.user?.username||'我').slice(0,1) }}</span></IonAvatar></IonButton></IonButtons>
</IonToolbar></IonHeader></template>
