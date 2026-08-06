<script setup lang="ts">
import { computed } from 'vue'
import { IonIcon, IonLabel, IonPage, IonRouterOutlet, IonTabBar, IonTabButton, IonTabs } from '@ionic/vue'
import { calculatorOutline, homeOutline, linkOutline, personOutline, walletOutline } from 'ionicons/icons'
import { useRoute } from 'vue-router'
import { canSwipeBack } from '../navigation'
// Tab roots are the bottom of their stack; leaving the swipe enabled there drags
// the user out of the shell to whatever happened to be in history.
const route = useRoute()
const swipe = computed(() => canSwipeBack(route.path))
</script>

<template>
  <IonPage>
    <IonTabs>
      <IonRouterOutlet :swipe-gesture="swipe" />
      <IonTabBar slot="bottom" class="app-tabbar">
      <IonTabButton tab="home" href="/tabs/home"><IonIcon :icon="homeOutline" /><IonLabel>首页</IonLabel></IonTabButton>
      <IonTabButton tab="tasks" href="/tabs/tasks"><IonIcon :icon="calculatorOutline" /><IonLabel>任务</IonLabel></IonTabButton>
      <IonTabButton tab="ledger" href="/tabs/ledger"><IonIcon :icon="walletOutline" /><IonLabel>记账</IonLabel></IonTabButton>
      <IonTabButton tab="links" href="/tabs/links"><IonIcon :icon="linkOutline" /><IonLabel>链接</IonLabel></IonTabButton>
      <IonTabButton tab="mine" href="/tabs/mine"><IonIcon :icon="personOutline" /><IonLabel>我的</IonLabel></IonTabButton>
      </IonTabBar>
    </IonTabs>
  </IonPage>
</template>
