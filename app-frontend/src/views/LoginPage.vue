<script setup lang="ts">
import { ref } from 'vue'
import { IonButton, IonContent, IonInput, IonItem, IonLabel, IonPage, IonSpinner, toastController } from '@ionic/vue'
import { useRoute, useRouter } from 'vue-router'
import type { CurrentUser } from '../api'
import { session, setSessionUser } from '../session'

type Captcha = { captcha_id: string; image_data: string; expires_in_seconds: number }
const route = useRoute(); const router = useRouter()
const username = ref(''); const password = ref(''); const totpCode = ref(''); const captchaCode = ref('')
const captcha = ref<Captcha | null>(null); const needsTotp = ref(false); const submitting = ref(false)

const loadCaptcha = async () => {
  try {
    const response = await fetch('/auth/captcha', { credentials: 'include', cache: 'no-store' })
    if (!response.ok) throw new Error('captcha request failed')
    captcha.value = await response.json() as Captcha
    captchaCode.value = ''
  } catch {
    captcha.value = null
    const toast = await toastController.create({ message: '验证码加载失败，请检查网络后重试', duration: 2300, color: 'danger' })
    await toast.present()
  }
}

const submit = async () => {
  if (!username.value.trim() || !password.value) {
    const toast = await toastController.create({ message: '请输入账号和密码', duration: 1800, color: 'warning' }); await toast.present(); return
  }
  submitting.value = true
  try {
    const response = await fetch('/auth/login', {
      method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.value, password: password.value, totp_code: totpCode.value || null, captcha_id: captcha.value?.captcha_id || null, captcha_code: captchaCode.value || null }),
    })
    if (response.ok) {
      setSessionUser(await response.json() as CurrentUser)
      session.loaded = true
      await router.replace(String(route.query.redirect || '/tabs/home'))
      return
    }
    const body = await response.json().catch(() => ({})) as { detail?: string }
    if (response.headers.get('X-TOTP-Required') === 'true') needsTotp.value = true
    if (response.headers.get('X-Captcha-Required') === 'true' || response.status === 428 && !needsTotp.value) await loadCaptcha()
    const toast = await toastController.create({ message: body.detail || '登录失败', duration: 2300, color: 'danger' }); await toast.present()
  } catch {
    const toast = await toastController.create({ message: '无法连接服务器，请检查网络后重试', duration: 2300, color: 'danger' })
    await toast.present()
  } finally { submitting.value = false }
}
</script>

<template><IonPage><IonContent><main class="login-page">
  <section class="login-brand"><div>RS</div><h1>内部管理 App</h1><p>使用电脑后台相同的账号登录</p></section>
  <form class="login-card" @submit.prevent="submit">
    <IonItem lines="full"><IonLabel position="stacked">账号</IonLabel><IonInput v-model="username" autocomplete="username" placeholder="请输入管理员账号" /></IonItem>
    <IonItem lines="full"><IonLabel position="stacked">密码</IonLabel><IonInput v-model="password" type="password" autocomplete="current-password" placeholder="请输入登录密码" /></IonItem>
    <IonItem v-if="needsTotp" lines="full"><IonLabel position="stacked">动态验证码</IonLabel><IonInput v-model="totpCode" inputmode="numeric" :maxlength="8" placeholder="请输入身份验证器验证码" /></IonItem>
    <div v-if="captcha" class="captcha-row"><IonItem lines="none"><IonLabel position="stacked">图形验证码</IonLabel><IonInput v-model="captchaCode" :maxlength="16" placeholder="请输入验证码" /></IonItem><button type="button" @click="loadCaptcha"><img :src="captcha.image_data" alt="登录验证码"></button></div>
    <IonButton type="submit" expand="block" :disabled="submitting"><IonSpinner v-if="submitting" name="crescent" />{{ submitting ? '登录中' : '登录 App' }}</IonButton>
  </form>
  <p class="login-tip">App 与电脑端支持同时在线，登录不会退出电脑端。</p>
</main></IonContent></IonPage></template>

<style scoped>.login-page{min-height:100%;display:grid;align-content:center;gap:18px;padding:28px 22px calc(28px + env(safe-area-inset-bottom));background:radial-gradient(circle at 50% 5%,rgba(37,99,235,.18),transparent 38%)}.login-brand{text-align:center}.login-brand div{width:68px;height:68px;margin:auto;border-radius:22px;display:grid;place-items:center;color:#fff;font-size:25px;font-weight:800;background:linear-gradient(135deg,#2563eb,#8b5cf6);box-shadow:0 15px 35px rgba(37,99,235,.25)}.login-brand h1{margin:14px 0 4px;font-size:25px}.login-brand p,.login-tip{margin:0;color:var(--app-muted);font-size:12px}.login-card{padding:8px 16px 18px;border:1px solid var(--app-line);border-radius:22px;background:var(--app-card);box-shadow:0 18px 45px rgba(15,23,42,.08)}.login-card ion-item{--background:transparent;--padding-start:0;--inner-padding-end:0;--min-height:76px}.login-card ion-input{font-size:16px}.login-card ion-button{height:50px;margin-top:18px;--border-radius:14px}.captcha-row{display:grid;grid-template-columns:1fr 124px;gap:10px;align-items:end}.captcha-row button{height:50px;padding:0;border:1px solid var(--app-line);border-radius:12px;overflow:hidden;background:#fff}.captcha-row img{width:100%;height:100%;object-fit:cover}.login-tip{text-align:center;line-height:1.6}</style>
