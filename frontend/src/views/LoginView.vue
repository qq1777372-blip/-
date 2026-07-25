<script setup lang="ts">
import { User, Lock, RefreshRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchLoginCaptcha } from '../api'
import { useAuthStore } from '../stores/auth'

const REMEMBER_LOGIN_KEY = 'ruoshop-remembered-login'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const loading = ref(false)
const captchaLoading = ref(false)
const rememberLogin = ref(false)
const form = reactive({
  username: '',
  password: '',
  captcha_code: '',
})
const captcha = reactive({
  captcha_id: '',
  image_data: '',
})

function loadRememberedLogin() {
  try {
    const rawValue = window.localStorage.getItem(REMEMBER_LOGIN_KEY)
    if (!rawValue) {
      return
    }

    const parsed = JSON.parse(rawValue) as { username?: string }
    form.username = String(parsed.username ?? '')
    form.password = ''
    rememberLogin.value = Boolean(form.username)
  } catch {
    window.localStorage.removeItem(REMEMBER_LOGIN_KEY)
  }
}

function persistRememberedLogin() {
  if (!rememberLogin.value) {
    window.localStorage.removeItem(REMEMBER_LOGIN_KEY)
    return
  }

  window.localStorage.setItem(
    REMEMBER_LOGIN_KEY,
    JSON.stringify({
      username: form.username.trim(),
    }),
  )
}

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    return String(error.response?.data?.detail ?? error.message ?? fallback)
  }

  if (error instanceof Error && error.message) {
    return error.message
  }

  return fallback
}

async function loadCaptcha(showError = false) {
  captchaLoading.value = true

  try {
    const data = await fetchLoginCaptcha()
    captcha.captcha_id = data.captcha_id
    captcha.image_data = data.image_data
    form.captcha_code = ''
  } catch (error) {
    if (showError) {
      ElMessage.error(getErrorMessage(error, '加载验证码失败'))
    }
  } finally {
    captchaLoading.value = false
  }
}

async function submit() {
  if (!form.username.trim() || !form.password) {
    ElMessage.warning('请输入账号和密码')
    return
  }

  if (!captcha.captcha_id || !form.captcha_code.trim()) {
    ElMessage.warning('请输入验证码')
    return
  }

  loading.value = true

  try {
    await authStore.signIn({
      username: form.username.trim(),
      password: form.password,
      captcha_id: captcha.captcha_id,
      captcha_code: form.captcha_code.trim(),
    })
    persistRememberedLogin()

    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/dashboard"
    if (redirect.startsWith('/tutorials')) {
      window.location.assign(redirect)
      return
    }
    await router.replace(redirect)
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '登录失败'))
    await loadCaptcha()
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadRememberedLogin()
  void loadCaptcha(true)
})
</script>

<template>
  <div class="auth-shell">
    <div class="auth-card">
      <div class="auth-brand">
        <span class="soft-tag">企业后台升级版</span>
        <h1>RuoShop 管理后台</h1>
        <p>新的前端将基于 Vue 3 + Element Plus 持续替换旧静态页面，先统一后台框架，再逐步细化业务模块。</p>
      </div>

      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="账号">
          <el-input
            v-model="form.username"
            placeholder="请输入管理员账号"
            :prefix-icon="User"
            autocomplete="username"
          />
        </el-form-item>

        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="请输入登录密码"
            :prefix-icon="Lock"
            autocomplete="current-password"
            @keyup.enter="submit"
          />
        </el-form-item>

        <el-form-item label="验证码">
          <div class="auth-captcha-row">
            <el-input
              v-model="form.captcha_code"
              placeholder="请输入验证码"
              maxlength="6"
              @keyup.enter="submit"
            />
            <button
              type="button"
              class="auth-captcha-card"
              :disabled="captchaLoading"
              @click="loadCaptcha(true)"
            >
              <img v-if="captcha.image_data" :src="captcha.image_data" alt="验证码" />
              <span v-else>{{ captchaLoading ? '加载中...' : '点击获取' }}</span>
            </button>
            <el-button text :icon="RefreshRight" :loading="captchaLoading" @click="loadCaptcha(true)">
              刷新
            </el-button>
          </div>
        </el-form-item>

        <div class="auth-remember-row">
          <el-checkbox v-model="rememberLogin">记住账号密码</el-checkbox>
          <span class="auth-remember-tip">仅保存在当前浏览器</span>
        </div>

        <el-button type="primary" size="large" :loading="loading" style="width: 100%" @click="submit">
          登录后台
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.auth-captcha-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 136px auto;
  gap: 10px;
  align-items: center;
}

.auth-captcha-card {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 136px;
  height: 44px;
  padding: 0;
  border: 1px solid rgba(203, 213, 225, 0.9);
  border-radius: 10px;
  background: #f8fafc;
  overflow: hidden;
  cursor: pointer;
}

.auth-captcha-card:disabled {
  cursor: wait;
  opacity: 0.72;
}

.auth-captcha-card img {
  display: block;
  width: 100%;
  height: 100%;
}

.auth-captcha-card span {
  color: var(--text-secondary);
  font-size: 12px;
}

.auth-remember-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: -4px 0 16px;
}

.auth-remember-tip {
  color: var(--text-secondary);
  font-size: 12px;
}

@media (max-width: 640px) {
  .auth-captcha-row {
    grid-template-columns: minmax(0, 1fr);
  }

  .auth-captcha-card {
    width: 100%;
  }
}
</style>
