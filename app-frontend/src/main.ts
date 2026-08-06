import { createApp } from 'vue'
import { IonicVue } from '@ionic/vue'
import { iosTransitionAnimation } from '@ionic/core'
import type { AnimationBuilder } from '@ionic/core'
import { registerSW } from 'virtual:pwa-register'
import '@ionic/vue/css/core.css'
import '@ionic/vue/css/normalize.css'
import '@ionic/vue/css/structure.css'
import '@ionic/vue/css/typography.css'
import '@ionic/vue/css/padding.css'
import '@ionic/vue/css/display.css'
import App from './App.vue'
import { markUpdateReady, watchConnectivity } from './network'
import router from './router'
import './theme.css'

document.documentElement.classList.toggle('ion-palette-dark', localStorage.getItem('app-theme') === 'dark')
watchConnectivity()
const updateSW = registerSW({
  immediate: true,
  onNeedRefresh() { markUpdateReady(() => updateSW(true)) },
})
const appNavigationAnimation:AnimationBuilder=(baseEl,opts)=>iosTransitionAnimation(baseEl,opts).duration(320)
createApp(App).use(IonicVue, { mode: 'ios', animated: true, navAnimation: appNavigationAnimation }).use(router).mount('#app')
