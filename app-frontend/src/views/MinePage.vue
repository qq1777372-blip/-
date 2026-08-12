<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { IonContent, IonIcon, IonModal, IonPage, toastController } from '@ionic/vue'
import { cameraOutline, chevronForwardOutline, closeOutline, moonOutline, notifications, notificationsOutline, settingsOutline, sunnyOutline, trashOutline } from 'ionicons/icons'
import { useRouter } from 'vue-router'
import { appModules, canOpenModule } from '../modules'
import { api, ApiError, type CurrentUser } from '../api'
import { can, cleanOptionalUrl, session, setSessionUser } from '../session'
import { alerts, refreshAlertCounts } from '../alerts'

const router=useRouter()
const dark=ref(document.documentElement.classList.contains('ion-palette-dark'))
const permittedModules=computed(()=>appModules.filter(item=>canOpenModule(item,session.user?.role,can)))
const accountKeys=new Set(['users','license-keys','software-users','audit-logs','settings'])
const accountItems=computed(()=>permittedModules.value.filter(item=>accountKeys.has(item.key)))
const permissionCount=computed(()=>Object.values(session.user?.permissions||{}).filter(level=>level==='read'||level==='write').length)
const displayName=computed(()=>session.user?.display_name||session.user?.username||'当前账号')
const avatarUrl=computed(()=>cleanOptionalUrl(session.user?.avatar_url))
const roleLabel=computed(()=>session.user?.role==='superadmin'?'超级管理员':'当前账号')
const profileOpen=ref(false)
const profileName=ref('')
const profileFile=ref<File|null>(null)
const profilePreview=ref<string|null>(null)
const removeAvatarRequested=ref(false)
const profileSaving=ref(false)
const profileAvatar=computed(()=>removeAvatarRequested.value?null:profilePreview.value||avatarUrl.value)
function toggleTheme(){dark.value=!dark.value;document.documentElement.classList.toggle('ion-palette-dark',dark.value);localStorage.setItem('app-theme',dark.value?'dark':'light')}
function releaseProfilePreview(){if(profilePreview.value?.startsWith('blob:'))URL.revokeObjectURL(profilePreview.value);profilePreview.value=null}
function openProfile(){profileName.value=session.user?.display_name||'';profileFile.value=null;removeAvatarRequested.value=false;releaseProfilePreview();profileOpen.value=true}
function closeProfile(){if(profileSaving.value)return;profileOpen.value=false;profileFile.value=null;removeAvatarRequested.value=false;releaseProfilePreview()}
async function notify(message:string,color:'success'|'warning'|'danger'='danger'){const toast=await toastController.create({message,duration:2200,color});await toast.present()}
function selectAvatar(event:Event){
  const input=event.target as HTMLInputElement
  const file=input.files?.[0]
  input.value=''
  if(!file)return
  if(!['image/jpeg','image/png','image/webp'].includes(file.type)){void notify('仅支持 JPG、PNG、WebP 图片','warning');return}
  if(file.size>5*1024*1024){void notify('头像大小不能超过 5MB','warning');return}
  releaseProfilePreview();profileFile.value=file;removeAvatarRequested.value=false;profilePreview.value=URL.createObjectURL(file)
}
function removeProfileAvatar(){profileFile.value=null;releaseProfilePreview();removeAvatarRequested.value=true}
async function saveProfile(){
  const name=profileName.value.trim()
  if(name.length>50){await notify('显示姓名不能超过 50 个字符','warning');return}
  if(!session.user)return
  profileSaving.value=true
  try{
    let user=await api<CurrentUser>('/auth/profile',{method:'PATCH',body:JSON.stringify({username:session.user.username,display_name:name||null})})
    if(profileFile.value){
      const data=new FormData();data.append('image',profileFile.value)
      const response=await fetch('/auth/avatar',{method:'POST',credentials:'include',body:data})
      if(!response.ok){const body=await response.json().catch(()=>({}));throw new ApiError(response.status,String(body.detail||'头像上传失败'))}
      user=await response.json() as CurrentUser
    }else if(removeAvatarRequested.value&&avatarUrl.value){
      user=await api<CurrentUser>('/auth/avatar',{method:'DELETE'})
    }
    setSessionUser(user);profileOpen.value=false;releaseProfilePreview();await notify('个人资料已更新','success')
  }catch(error){await notify(error instanceof ApiError?error.detail:'个人资料保存失败')}
  finally{profileSaving.value=false}
}
// This tab has its own toolbar instead of PageHeader, so the bell state is wired
// up here as well rather than inherited.
const hasAlerts=computed(()=>alerts.openCount>0)
const badgeLabel=computed(()=>alerts.openCount>99?'99+':String(alerts.openCount))
onMounted(()=>{void refreshAlertCounts()})
</script>

<template><IonPage><IonContent :fullscreen="true"><main class="mine-page">
  <section class="mine-hero">
    <div class="mine-toolbar"><strong>个人中心</strong><div><button aria-label="夜览模式" @click="toggleTheme"><IonIcon :icon="dark?sunnyOutline:moonOutline" /></button><button class="mine-alert-button" :class="{'has-alerts':hasAlerts}" :aria-label="hasAlerts?`通知，${alerts.openCount} 条待处理`:'通知'" @click="router.push('/tabs/alerts')"><IonIcon :icon="hasAlerts?notifications:notificationsOutline" /><i v-if="hasAlerts" class="mine-alert-badge">{{ badgeLabel }}</i></button><button aria-label="设置" @click="router.push('/tabs/app-settings')"><IonIcon :icon="settingsOutline" /></button></div></div>
    <button class="mine-identity" type="button" aria-label="编辑个人资料" @click="openProfile">
      <span class="mine-avatar"><img v-if="avatarUrl" :src="avatarUrl" alt="头像"><span v-else class="mine-avatar-fallback">{{ displayName.slice(0,2) }}</span></span>
      <span class="mine-identity-copy"><span class="mine-name-row"><strong>{{ displayName }}</strong><em>{{ roleLabel }}</em></span><small>账号 {{ session.user?.username||'--' }}</small></span>
      <IonIcon class="mine-profile-arrow" :icon="chevronForwardOutline" />
    </button>
    <div class="mine-stats"><div><strong>{{ permittedModules.length }}</strong><span>可用功能</span></div><div><strong>{{ permissionCount }}</strong><span>授权模块</span></div><div><strong>{{ session.user?.role==='superadmin'?'超级':'普通' }}</strong><span>账号身份</span></div></div>
  </section>
  <section class="mine-content"><div class="mine-section-title"><strong>账号与系统</strong><span>{{ accountItems.length }} 项</span></div><section v-if="accountItems.length" class="mine-menu"><button v-for="item in accountItems" :key="item.key" @click="router.push(item.route)"><span :style="{background:`${item.color}18`,color:item.color}"><IonIcon :icon="item.icon" /></span><b>{{ item.title }}</b><IonIcon :icon="chevronForwardOutline" /></button></section></section>
</main></IonContent>
<IonModal :is-open="profileOpen" css-class="profile-editor-modal" @did-dismiss="closeProfile">
  <section class="profile-editor">
    <header><button type="button" aria-label="关闭" :disabled="profileSaving" @click="closeProfile"><IonIcon :icon="closeOutline" /></button><strong>编辑个人资料</strong><button class="profile-editor-save" type="button" :disabled="profileSaving" @click="saveProfile">{{ profileSaving?'保存中':'保存' }}</button></header>
    <main>
      <div class="profile-avatar-editor">
        <div class="profile-avatar-preview"><img v-if="profileAvatar" :src="profileAvatar" alt="头像预览"><span v-else>{{ (profileName||session.user?.username||'我').slice(0,2) }}</span></div>
        <label><IonIcon :icon="cameraOutline" /><span>{{ profileAvatar?'更换头像':'选择头像' }}</span><input type="file" accept="image/jpeg,image/png,image/webp" @change="selectAvatar"></label>
        <button v-if="profileAvatar" class="profile-avatar-remove" type="button" @click="removeProfileAvatar"><IonIcon :icon="trashOutline" />删除头像</button>
        <small>支持 JPG、PNG、WebP，最大 5MB</small>
      </div>
      <label class="profile-field"><span>显示姓名</span><input v-model="profileName" maxlength="50" placeholder="请输入显示姓名"></label>
      <label class="profile-field profile-field--readonly"><span>登录账号</span><input :value="session.user?.username||''" readonly><small>登录账号用于身份识别，不能在这里修改</small></label>
    </main>
  </section>
</IonModal>
</IonPage></template>

<style scoped>
.mine-avatar{padding:0;border:3px solid #ffffffe0;cursor:pointer}
.mine-avatar i{position:absolute;right:0;bottom:0;width:26px;height:26px;border:2px solid #fff;border-radius:50%;display:grid;place-items:center;color:#1677ff;background:#fff;font-style:normal;box-shadow:0 2px 7px #00509638}
.mine-avatar i ion-icon{font-size:14px}
.mine-account-meta{height:24px;display:flex;align-items:center;gap:7px;margin-top:7px}
.mine-account-meta em,.mine-account-meta span{height:24px;display:flex;align-items:center;justify-content:center;margin:0!important;padding:0 9px;border-radius:999px;background:#ffffff2b;font-family:"PingFang SC","Microsoft YaHei",sans-serif;font-size:10px;font-style:normal;font-weight:600;line-height:24px;white-space:nowrap;vertical-align:top}
.mine-account-meta em{margin:0}
.mine-account-meta span{height:auto;padding:0;background:transparent;opacity:.82;font-weight:500;transform:none}
.mine-account-meta span b{color:#e8f7ff;font-weight:700}
.mine-account-meta .mine-id-label{margin-right:4px;color:#ffd166;font-size:13px;font-weight:800;line-height:1;letter-spacing:.2px}
.mine-account-meta .mine-id-badge{height:24px;padding:0 9px 0 7px;border-radius:999px;background:linear-gradient(90deg,#ff9b35,#f56b25);color:#fff;gap:0;box-shadow:0 2px 7px #a9461c38}
.mine-account-meta .mine-id-badge .mine-id-label{height:24px;margin:0 0 0 -7px;padding:0 8px;border-radius:999px 0 0 999px;display:flex;align-items:center;color:#fff;background:#eab43f;font-size:13px}
.mine-account-meta .mine-id-badge b{color:#fff;font-size:10px;font-weight:800;letter-spacing:.2px}
.profile-editor{height:100%;color:var(--app-text);background:var(--ion-background-color)}
.profile-editor>header{height:calc(58px + env(safe-area-inset-top,0px));padding:env(safe-area-inset-top,0px) 14px 0;display:grid;grid-template-columns:64px 1fr 64px;align-items:center;border-bottom:1px solid var(--app-line);background:var(--app-card)}
.profile-editor>header strong{text-align:center;font-size:16px}
.profile-editor>header button{justify-self:start;width:38px;height:38px;padding:0;border:0;display:grid;place-items:center;color:var(--app-text);background:transparent}
.profile-editor>header button ion-icon{font-size:24px}
.profile-editor>header .profile-editor-save{justify-self:end;width:auto;color:#1677ff;font-size:14px;font-weight:700}
.profile-editor>header button:disabled{opacity:.5}
.profile-editor>main{max-width:520px;margin:0 auto;padding:28px 18px}
.profile-avatar-editor{display:flex;flex-direction:column;align-items:center}
.profile-avatar-preview{width:104px;height:104px;overflow:hidden;border:3px solid var(--app-card);border-radius:50%;display:grid;place-items:center;color:#fff;background:linear-gradient(145deg,#655cff,#22b8ef);box-shadow:0 6px 20px #0f172a1f;font-size:25px;font-weight:800}
.profile-avatar-preview img{width:100%;height:100%;object-fit:cover}
.profile-avatar-editor label,.profile-avatar-remove{height:34px;margin-top:12px;padding:0 12px;border:0;border-radius:7px;display:inline-flex;align-items:center;gap:6px;color:#1677ff;background:#eaf2ff;font-size:12px;font-weight:600;cursor:pointer}
.profile-avatar-editor label input{display:none}
.profile-avatar-remove{margin-top:7px;color:#ef4444;background:transparent}
.profile-avatar-editor small{margin-top:6px;color:var(--app-muted);font-size:10px}
.profile-field{display:block;margin-top:24px}
.profile-field>span{display:block;margin-bottom:7px;font-size:12px;font-weight:700}
.profile-field input{width:100%;height:44px;padding:0 12px;border:1px solid var(--app-line);border-radius:7px;color:var(--app-text);background:var(--app-card);font:inherit;font-size:14px;outline:none}
.profile-field input:focus{border-color:#1677ff;box-shadow:0 0 0 3px #1677ff18}
.profile-field--readonly input{color:var(--app-muted);background:var(--app-soft)}
.profile-field small{display:block;margin-top:6px;color:var(--app-muted);font-size:10px}
.ion-palette-dark .profile-avatar-editor label{background:#172c49}

/* Compact enterprise profile header: identity reads as one actionable row. */
.mine-hero{min-height:256px!important;padding-right:16px!important;padding-left:16px!important;color:#fff!important;background:linear-gradient(180deg,#168df4 0,#58b9fa 68%,#bfe5ff 100%)!important}
.mine-toolbar{color:#fff}
.mine-toolbar button{color:#fff!important;background:#ffffff2e!important;box-shadow:none}
.mine-toolbar .mine-alert-badge{color:#fff!important;background:#ef4444!important}
.mine-identity{width:100%;min-height:92px;margin-top:12px!important;padding:14px!important;border:1px solid #ffffff45!important;border-radius:12px!important;display:grid!important;grid-template-columns:58px minmax(0,1fr) 20px!important;gap:13px!important;align-items:center!important;text-align:left;color:#fff;background:#ffffff28!important;box-shadow:none!important;backdrop-filter:blur(12px)}
.mine-avatar{width:58px!important;height:58px!important;border:0!important;border-radius:10px!important;background:#e9f2ff!important;box-shadow:none!important;color:#1677ff}
.mine-avatar span{font-size:17px!important}
.mine-avatar i{right:-2px!important;bottom:-2px!important;width:21px!important;height:21px!important;border:2px solid #fff!important;color:#fff!important;background:#1677ff!important;box-shadow:none!important}
.mine-avatar i ion-icon{font-size:11px!important}
.mine-identity-copy{min-width:0;display:block}
.mine-name-row{display:flex;align-items:center;gap:8px;min-width:0}
.mine-name-row strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:19px;line-height:1.35}
.mine-name-row em{flex:none;padding:3px 7px;border-radius:4px;color:#fff;background:#ffffff2e;font-size:10px;font-style:normal;font-weight:600;line-height:1.2}
.mine-identity-copy small{display:block;margin-top:7px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#ffffffc7;font-size:11px}
.mine-profile-arrow{color:#ffffffb8;font-size:18px}
.mine-stats{margin-top:12px!important;border:1px solid #ffffff45!important;border-radius:10px!important;color:#fff;background:#ffffff28!important;backdrop-filter:blur(12px)}
.mine-stats div{padding:10px 6px!important}
.mine-stats div+div{border-left:1px solid #ffffff38!important}
.mine-stats strong{color:#fff;font-size:16px!important}
.mine-stats span{color:#ffffffc7;opacity:1!important}
.mine-content{margin-top:0!important;border-radius:0!important}
.ion-palette-dark .mine-hero{color:#fff!important;background:linear-gradient(180deg,#075a9f,#126fae 68%,#0f2740)!important}
.ion-palette-dark .mine-toolbar button,.ion-palette-dark .mine-identity,.ion-palette-dark .mine-stats{border-color:#2a3545!important;background:#17202d!important}
.ion-palette-dark .mine-stats div+div{border-color:#2a3545!important}
.ion-palette-dark .mine-stats strong{color:#f3f6fb}
</style>

<style scoped>
.mine-identity .mine-account-meta em,
.mine-identity .mine-account-meta span {
  display: flex;
  height: 24px;
  margin: 0 !important;
  padding: 0 9px;
  align-items: center;
  line-height: 24px;
  font-size: 10px;
}
.mine-identity .mine-account-meta span {
  height: auto;
  padding: 0;
  background: transparent;
  font-weight: 500;
  transform: none;
}
.mine-identity .mine-account-meta .mine-id-badge {
  height: 24px;
  padding: 0 9px 0 7px;
  background: #eab43f;
  color: #fff;
}
.mine-identity .mine-account-meta .mine-id-badge .mine-id-label {
  background: transparent;
  color: #fff;
}
.mine-identity .mine-account-meta .mine-id-badge b {
  color: #fff;
}
</style>

<style scoped>.mine-page{min-height:100%;padding-bottom:88px;background:var(--ion-background-color)}.mine-hero{min-height:300px;padding:calc(env(safe-area-inset-top,0px) + 18px) 20px 32px;color:#fff;background:linear-gradient(180deg,#168df4 0,#58b9fa 56%,#bfe5ff 100%)}.mine-toolbar{height:42px;display:flex;align-items:center;justify-content:space-between}.mine-toolbar>strong{font-size:16px}.mine-toolbar>div{display:flex;gap:8px}.mine-toolbar button{width:38px;height:38px;padding:0;border:0;border-radius:50%;display:grid;place-items:center;color:#fff;background:#ffffff2e}.mine-toolbar ion-icon{font-size:21px}.mine-alert-button{position:relative;overflow:visible}.mine-alert-button.has-alerts{background:#ffffff2e}.mine-alert-badge{position:absolute;top:-4px;right:-4px;min-width:18px;height:18px;padding:0 4px;border:2px solid #fff;border-radius:999px;display:grid;place-items:center;color:#fff;background:#ef4444;font-size:9px;font-style:normal;font-weight:700;line-height:1;pointer-events:none}.mine-identity{margin-top:20px;display:flex;align-items:center;gap:16px}.mine-avatar{position:relative;flex:none;width:82px;height:82px;overflow:hidden;border:3px solid #ffffffe0;border-radius:50%;display:grid;place-items:center;background:linear-gradient(145deg,#655cff,#22b8ef);box-shadow:0 8px 24px #00509638}.mine-avatar span{font-size:22px;font-weight:800}.mine-avatar img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}.mine-identity h1{margin:0;font-size:24px;line-height:1.2}.mine-identity em{display:inline-block;margin-top:7px;padding:3px 9px;border-radius:999px;background:#ffffff33;font-size:11px;font-style:normal}.mine-identity p{margin:7px 0 0;opacity:.82;font-size:11px}.mine-stats{margin-top:25px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));overflow:hidden;border:1px solid #ffffff38;border-radius:16px;background:#ffffff26}.mine-stats div{min-width:0;padding:12px 6px;text-align:center}.mine-stats div+div{border-left:1px solid #ffffff33}.mine-stats strong,.mine-stats span{display:block}.mine-stats strong{font-size:18px}.mine-stats span{margin-top:4px;opacity:.78;font-size:10px}.mine-content{position:relative;margin-top:-18px;padding:22px 14px 28px;border-radius:22px 22px 0 0;background:var(--ion-background-color)}.mine-section-title{display:flex;align-items:center;justify-content:space-between;margin:0 3px 9px}.mine-section-title strong{font-size:15px}.mine-section-title span{color:var(--app-muted);font-size:10px}.mine-menu{overflow:hidden;border:1px solid var(--app-line);border-radius:16px;background:var(--app-card)}.mine-menu button{width:100%;min-height:58px;display:grid;grid-template-columns:38px 1fr auto;gap:11px;align-items:center;padding:9px 13px;border:0;border-bottom:1px solid var(--app-line);text-align:left;color:var(--app-text);background:transparent}.mine-menu button:last-child{border-bottom:0}.mine-menu button>span{width:34px;height:34px;display:grid;place-items:center;border-radius:11px}.mine-menu button>span ion-icon{font-size:18px}.mine-menu b{font-size:13px}.mine-menu button>ion-icon{color:#a6b0bf;font-size:18px}.settings-entry{width:100%;min-height:62px;margin-top:14px;display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border:1px solid var(--app-line);border-radius:16px;text-align:left;color:var(--app-text);background:var(--app-card)}.settings-entry strong,.settings-entry small{display:block}.settings-entry strong{font-size:14px}.settings-entry small{margin-top:4px;color:var(--app-muted);font-size:10px}.settings-entry>ion-icon{color:#a6b0bf;font-size:20px}.settings-entry>ion-icon{color:#a6b0bf;font-size:20px}.ion-palette-dark .mine-hero{background:linear-gradient(180deg,#075a9f,#126fae 60%,#0f2740)}</style>
