<script setup lang="ts">
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { computed, reactive, ref, watch } from 'vue'
import { confirmTotp, disableTotp, setupTotp } from '../api'
import { useAuthStore } from '../stores/auth'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
const authStore = useAuthStore()
const loading = ref(false)
const setupData = reactive({ secret: '', qr_image_data: '' })
const form = reactive({ password: '', code: '' })
const enabled = computed(() => Boolean(authStore.currentUser?.totp_enabled))

watch(() => props.modelValue, (visible) => {
  if (!visible) return
  form.password = ''
  form.code = ''
  setupData.secret = ''
  setupData.qr_image_data = ''
})

function errorText(error: unknown) {
  if (axios.isAxiosError(error)) return String(error.response?.data?.detail ?? '操作失败')
  return '操作失败'
}

async function beginSetup() {
  if (!form.password) return ElMessage.warning('请输入当前密码')
  loading.value = true
  try {
    const data = await setupTotp(form.password)
    setupData.secret = data.secret
    setupData.qr_image_data = data.qr_image_data
    form.code = ''
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    loading.value = false
  }
}

async function enable() {
  if (!form.code) return ElMessage.warning('请输入6位动态验证码')
  loading.value = true
  try {
    authStore.currentUser = await confirmTotp(setupData.secret, form.code)
    ElMessage.success('二次验证已启用')
    emit('update:modelValue', false)
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    loading.value = false
  }
}

async function disable() {
  if (!form.password || !form.code) return ElMessage.warning('请输入当前密码和动态验证码')
  loading.value = true
  try {
    authStore.currentUser = await disableTotp(form.password, form.code)
    ElMessage.success('二次验证已关闭')
    emit('update:modelValue', false)
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-dialog :model-value="modelValue" title="登录二次验证" width="460px" @close="emit('update:modelValue', false)">
    <template v-if="enabled">
      <el-alert title="二次验证已启用" type="success" :closable="false" show-icon />
      <el-form label-position="top" class="security-form">
        <el-form-item label="当前密码"><el-input v-model="form.password" type="password" show-password /></el-form-item>
        <el-form-item label="动态验证码"><el-input v-model="form.code" maxlength="6" inputmode="numeric" /></el-form-item>
      </el-form>
    </template>
    <template v-else>
      <el-form v-if="!setupData.secret" label-position="top">
        <el-form-item label="当前密码"><el-input v-model="form.password" type="password" show-password /></el-form-item>
      </el-form>
      <div v-else class="totp-setup">
        <img :src="setupData.qr_image_data" alt="身份验证器二维码" />
        <p>使用身份验证器扫描二维码，然后输入生成的6位验证码。</p>
        <el-input v-model="form.code" maxlength="6" inputmode="numeric" placeholder="6位动态验证码" />
      </div>
    </template>
    <template #footer>
      <el-button v-if="enabled" type="danger" :loading="loading" @click="disable">关闭二次验证</el-button>
      <el-button v-else-if="!setupData.secret" type="primary" :loading="loading" @click="beginSetup">下一步</el-button>
      <el-button v-else type="primary" :loading="loading" @click="enable">确认启用</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.security-form { margin-top: 18px; }
.totp-setup { display: grid; justify-items: center; gap: 14px; text-align: center; }
.totp-setup img { width: 220px; height: 220px; }
.totp-setup p { margin: 0; color: var(--text-secondary); }
</style>
