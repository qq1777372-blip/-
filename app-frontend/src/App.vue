<script setup lang="ts">
import { IonApp, IonRouterOutlet } from '@ionic/vue'
import { applyUpdate, network } from './network'

async function reloadApp() {
  await applyUpdate()
}
</script>

<template>
  <IonApp>
    <div v-if="!network.online" class="network-banner offline">当前离线，显示上次同步数据；记账和设置修改暂不可用</div>
    <div v-else-if="network.updateReady" class="network-banner update">发现新版本 <button @click="reloadApp">立即更新</button></div>
    <!-- Only /login and the /tabs shell live in this outlet; there is nothing to
         swipe back to, so the gesture stays off here and is decided per page by
         the outlet inside AppTabs. -->
    <IonRouterOutlet :swipe-gesture="false" />
  </IonApp>
</template>

<style scoped>
.network-banner{position:fixed;z-index:10000;top:env(safe-area-inset-top,0);left:10px;right:10px;padding:7px 12px;border-radius:0 0 10px 10px;text-align:center;font-size:11px;box-shadow:0 2px 10px #0002}.offline{color:#854d0e;background:#fef3c7}.update{color:#1e40af;background:#dbeafe}.network-banner button{margin-left:6px;padding:2px 7px;border:1px solid currentColor;border-radius:6px;color:inherit;background:transparent;font:inherit}
</style>
