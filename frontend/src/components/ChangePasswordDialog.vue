<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { changePassword } from '../api'
import { useAuthStore } from '../stores/auth'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const authStore = useAuthStore()
const loading = ref(false)

const form = reactive({
  currentPassword: '',
  newPassword: '',
  confirmPassword: '',
})

function resetForm() {
  form.currentPassword = ''
  form.newPassword = ''
  form.confirmPassword = ''
}

function closeDialog() {
  emit('update:modelValue', false)
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

async function submit() {
  if (!form.currentPassword || !form.newPassword || !form.confirmPassword) {
    ElMessage.warning('请完整填写密码信息')
    return
  }

  if (form.newPassword.length < 8) {
    ElMessage.warning('新密码至少 8 位')
    return
  }

  if (form.newPassword !== form.confirmPassword) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }

  loading.value = true

  try {
    const currentUser = await changePassword({
      current_password: form.currentPassword,
      new_password: form.newPassword,
    })

    authStore.currentUser = currentUser
    ElMessage.success('密码修改成功')
    closeDialog()
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '修改密码失败'))
  } finally {
    loading.value = false
  }
}

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) {
      resetForm()
    }
  },
)
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="修改密码"
    width="520px"
    destroy-on-close
    @close="closeDialog"
  >
    <el-form label-position="top">
      <el-form-item label="当前密码" required>
        <el-input v-model="form.currentPassword" type="password" show-password placeholder="请输入当前密码" />
      </el-form-item>

      <el-form-item label="新密码" required>
        <el-input v-model="form.newPassword" type="password" show-password placeholder="至少 8 位密码" />
      </el-form-item>

      <el-form-item label="确认新密码" required>
        <el-input v-model="form.confirmPassword" type="password" show-password placeholder="请再次输入新密码" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="closeDialog">取消</el-button>
      <el-button type="primary" :loading="loading" @click="submit">保存新密码</el-button>
    </template>
  </el-dialog>
</template>
