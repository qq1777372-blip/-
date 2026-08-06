<script setup lang="ts">
import { computed, ref } from 'vue'
import { IonContent, IonIcon, IonPage } from '@ionic/vue'
import { chevronForwardOutline, moonOutline, notificationsOutline, settingsOutline, sunnyOutline } from 'ionicons/icons'
import { useRouter } from 'vue-router'
import { appModules, canOpenModule } from '../modules'
import { can, cleanOptionalUrl, session } from '../session'
import { APP_VERSION } from '../version'

const router=useRouter()
const dark=ref(document.documentElement.classList.contains('ion-palette-dark'))
const permittedModules=computed(()=>appModules.filter(item=>canOpenModule(item,session.user?.role,can)))
const accountKeys=new Set(['users','license-keys','software-users','audit-logs','settings'])
const accountItems=computed(()=>permittedModules.value.filter(item=>accountKeys.has(item.key)))
const permissionCount=computed(()=>Object.values(session.user?.permissions||{}).filter(level=>level==='read'||level==='write').length)
const displayName=computed(()=>session.user?.display_name||session.user?.username||'当前账号')
const avatarUrl=computed(()=>cleanOptionalUrl(session.user?.avatar_url))
const roleLabel=computed(()=>session.user?.role==='superadmin'?'超级管理员':'当前账号')
function toggleTheme(){dark.value=!dark.value;document.documentElement.classList.toggle('ion-palette-dark',dark.value);localStorage.setItem('app-theme',dark.value?'dark':'light')}
</script>

<template><IonPage><IonContent :fullscreen="true"><main class="mine-page">
  <section class="mine-hero">
    <div class="mine-toolbar"><strong>个人中心</strong><div><button aria-label="夜览模式" @click="toggleTheme"><IonIcon :icon="dark?sunnyOutline:moonOutline" /></button><button aria-label="通知" @click="router.push('/tabs/alerts')"><IonIcon :icon="notificationsOutline" /></button><button aria-label="设置" @click="router.push('/tabs/app-settings')"><IonIcon :icon="settingsOutline" /></button></div></div>
    <div class="mine-identity"><div class="mine-avatar"><img v-if="avatarUrl" :src="avatarUrl" alt="头像"><span v-else>{{ displayName.slice(0,2) }}</span></div><div><h1>{{ displayName }}</h1><em>{{ roleLabel }}</em><p>{{ session.user?.username||'已登录账号' }}</p></div></div>
    <div class="mine-stats"><div><strong>{{ permittedModules.length }}</strong><span>可用功能</span></div><div><strong>{{ permissionCount }}</strong><span>授权模块</span></div><div><strong>{{ session.user?.role==='superadmin'?'超级':'普通' }}</strong><span>账号身份</span></div></div>
  </section>
  <section class="mine-content"><div class="mine-section-title"><strong>账号与系统</strong><span>{{ accountItems.length }} 项</span></div><section v-if="accountItems.length" class="mine-menu"><button v-for="item in accountItems" :key="item.key" @click="router.push(item.route)"><span :style="{background:`${item.color}18`,color:item.color}"><IonIcon :icon="item.icon" /></span><b>{{ item.title }}</b><IonIcon :icon="chevronForwardOutline" /></button></section><p class="version">App 版本 {{ APP_VERSION }}</p></section>
</main></IonContent></IonPage></template>

<style scoped>.mine-page{min-height:100%;padding-bottom:88px;background:var(--ion-background-color)}.mine-hero{min-height:300px;padding:calc(env(safe-area-inset-top,0px) + 18px) 20px 32px;color:#fff;background:linear-gradient(180deg,#168df4 0,#58b9fa 56%,#bfe5ff 100%)}.mine-toolbar{height:42px;display:flex;align-items:center;justify-content:space-between}.mine-toolbar>strong{font-size:16px}.mine-toolbar>div{display:flex;gap:8px}.mine-toolbar button{width:38px;height:38px;padding:0;border:0;border-radius:50%;display:grid;place-items:center;color:#fff;background:#ffffff2e}.mine-toolbar ion-icon{font-size:21px}.mine-identity{margin-top:20px;display:flex;align-items:center;gap:16px}.mine-avatar{position:relative;flex:none;width:82px;height:82px;overflow:hidden;border:3px solid #ffffffe0;border-radius:50%;display:grid;place-items:center;background:linear-gradient(145deg,#655cff,#22b8ef);box-shadow:0 8px 24px #00509638}.mine-avatar span{font-size:22px;font-weight:800}.mine-avatar img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}.mine-identity h1{margin:0;font-size:24px;line-height:1.2}.mine-identity em{display:inline-block;margin-top:7px;padding:3px 9px;border-radius:999px;background:#ffffff33;font-size:11px;font-style:normal}.mine-identity p{margin:7px 0 0;opacity:.82;font-size:11px}.mine-stats{margin-top:25px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));overflow:hidden;border:1px solid #ffffff38;border-radius:16px;background:#ffffff26}.mine-stats div{min-width:0;padding:12px 6px;text-align:center}.mine-stats div+div{border-left:1px solid #ffffff33}.mine-stats strong,.mine-stats span{display:block}.mine-stats strong{font-size:18px}.mine-stats span{margin-top:4px;opacity:.78;font-size:10px}.mine-content{position:relative;margin-top:-18px;padding:22px 14px 28px;border-radius:22px 22px 0 0;background:var(--ion-background-color)}.mine-section-title{display:flex;align-items:center;justify-content:space-between;margin:0 3px 9px}.mine-section-title strong{font-size:15px}.mine-section-title span{color:var(--app-muted);font-size:10px}.mine-menu{overflow:hidden;border:1px solid var(--app-line);border-radius:16px;background:var(--app-card)}.mine-menu button{width:100%;min-height:58px;display:grid;grid-template-columns:38px 1fr auto;gap:11px;align-items:center;padding:9px 13px;border:0;border-bottom:1px solid var(--app-line);text-align:left;color:var(--app-text);background:transparent}.mine-menu button:last-child{border-bottom:0}.mine-menu button>span{width:34px;height:34px;display:grid;place-items:center;border-radius:11px}.mine-menu button>span ion-icon{font-size:18px}.mine-menu b{font-size:13px}.mine-menu button>ion-icon{color:#a6b0bf;font-size:18px}.settings-entry{width:100%;min-height:62px;margin-top:14px;display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border:1px solid var(--app-line);border-radius:16px;text-align:left;color:var(--app-text);background:var(--app-card)}.settings-entry strong,.settings-entry small{display:block}.settings-entry strong{font-size:14px}.settings-entry small{margin-top:4px;color:var(--app-muted);font-size:10px}.settings-entry>ion-icon{color:#a6b0bf;font-size:20px}.version{margin:18px 0 0;color:var(--app-muted);font-size:10px;text-align:center}.ion-palette-dark .mine-hero{background:linear-gradient(180deg,#075a9f,#126fae 60%,#0f2740)}</style>

