import { createApp, nextTick } from 'vue'
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

function nextFrame(){return new Promise<void>(resolve=>requestAnimationFrame(()=>resolve()))}
// The startup layer sits in index.html so it paints before any JS runs. It is
// removed here rather than by a Vue transition, because it has to outlive the
// mount: the first route's own content is what we are waiting for.
function dismissStartup(){
  const layer=document.getElementById('app-startup')
  if(!layer)return
  if(window.matchMedia('(prefers-reduced-motion: reduce)').matches){layer.remove();return}
  let removed=false
  const remove=()=>{if(removed)return;removed=true;layer.remove()}
  layer.addEventListener('transitionend',remove,{once:true})
  layer.classList.add('leaving')
  // transitionend can be skipped entirely (background tab, reduced GPU), so the
  // timeout guarantees the layer never gets stuck over the app.
  window.setTimeout(remove,450)
}

async function bootstrap(){
  const app=createApp(App).use(IonicVue,{mode:'ios',animated:true,navAnimation:appNavigationAnimation}).use(router)
  await router.isReady()
  app.mount('#app')
  await nextTick()
  await nextFrame()
  await nextFrame()
  dismissStartup()
}

void bootstrap()
