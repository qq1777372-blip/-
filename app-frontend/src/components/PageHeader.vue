<script setup lang="ts">
import { computed, ref } from 'vue'
import { IonAvatar, IonButton, IonButtons, IonHeader, IonIcon, IonTitle, IonToolbar, useIonRouter } from '@ionic/vue'
import { chevronBackOutline, moonOutline, notificationsOutline, searchOutline, sunnyOutline } from 'ionicons/icons'
import { useRouter } from 'vue-router'
import { cleanOptionalUrl, session } from '../session'
import { fallbackPath } from '../navigation'
withDefaults(defineProps<{ title: string; subtitle?: string; back?: boolean; hideAvatar?: boolean }>(), { back: false, hideAvatar: false })
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
</script>
<template><IonHeader class="app-header" :class="{'is-subpage':back}"><IonToolbar>
  <IonButtons v-if="back" slot="start"><button class="app-native-back" type="button" aria-label="返回上一级" @click="goBack"><IonIcon :icon="chevronBackOutline" /></button></IonButtons>
  <IonTitle><strong>{{ title }}</strong><small v-if="subtitle">{{ subtitle }}</small></IonTitle>
  <IonButtons v-if="!back" slot="end" class="root-actions"><IonButton aria-label="夜览模式" @click="toggleTheme"><IonIcon :icon="dark?sunnyOutline:moonOutline" /></IonButton><IonButton aria-label="通知" @click="router.push('/tabs/alerts')"><IonIcon :icon="notificationsOutline" /></IonButton><IonButton aria-label="搜索" @click="router.push('/tabs/search')"><IonIcon :icon="searchOutline" /></IonButton><IonButton v-if="!hideAvatar" class="avatar-button" aria-label="我的" @click="router.push('/tabs/mine')"><IonAvatar><img v-if="avatarUrl" :src="avatarUrl" alt="头像"><span v-else>{{ (session.user?.display_name||session.user?.username||'我').slice(0,1) }}</span></IonAvatar></IonButton></IonButtons>
</IonToolbar></IonHeader></template>
