<script setup lang="ts">
import { IonContent, IonIcon, IonPage, alertController } from '@ionic/vue'
import { chevronForwardOutline, cloudDownloadOutline, logOutOutline, refreshCircleOutline } from 'ionicons/icons'
import { useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import { logout } from '../session'
import { APP_VERSION } from '../version'
const router=useRouter()
const checkUpdate=async()=>{const alert=await alertController.create({header:'检查更新',message:`当前版本 ${APP_VERSION}，已是最新版本。`,buttons:['知道了']});await alert.present()}
const clearAppCache=async()=>{
  const alert=await alertController.create({
    header:'清理软件缓存',
    message:'将清除旧版界面文件并重新加载，不会删除登录状态和业务数据。',
    buttons:['取消',{text:'清理并重载',handler:async()=>{
      if('serviceWorker' in navigator){
        const registrations=await navigator.serviceWorker.getRegistrations()
        await Promise.all(registrations.filter(item=>item.scope.includes('/app/')).map(item=>item.unregister()))
      }
      if('caches' in window){
        const names=await caches.keys()
        await Promise.all(names.map(name=>caches.delete(name)))
      }
      location.replace(`/app/?cache-cleared=${Date.now()}`)
    }}],
  })
  await alert.present()
}
const signOut=async()=>{await logout();router.replace('/login')}
</script>
<template><IonPage><PageHeader title="设置" subtitle="App 设置" back /><IonContent><main class="page-pad"><section class="compact-list"><button class="compact-row setting" @click="checkUpdate"><IonIcon :icon="cloudDownloadOutline" /><div><h3>检查更新</h3><p>当前版本 {{ APP_VERSION }}</p></div><IonIcon :icon="chevronForwardOutline" /></button><button class="compact-row setting" @click="clearAppCache"><IonIcon :icon="refreshCircleOutline" /><div><h3>清理软件缓存</h3><p>清除旧版界面文件并重新加载</p></div><IonIcon :icon="chevronForwardOutline" /></button><button class="compact-row setting danger" @click="signOut"><IonIcon :icon="logOutOutline" /><div><h3>退出登录</h3><p>仅退出当前 App 会话</p></div></button></section></main></IonContent></IonPage></template>
<style scoped>.setting{width:100%;border:0;background:none;text-align:left;color:inherit}.setting>ion-icon{font-size:22px;color:#64748b}.setting>ion-icon:last-child{color:var(--app-muted)}.danger h3,.danger>ion-icon{color:#ef4444}</style>
