import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { ref } from 'vue'

interface ProtectedRevealOptions {
  promptMessage?: string
  promptTitle?: string
  inputPlaceholder?: string
  confirmButtonText?: string
  cancelButtonText?: string
  successMessage?: string
  errorMessage?: string
}

type RevealLoader = (currentPassword: string) => Promise<string | null | undefined>

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    return String(error.response?.data?.detail ?? error.message ?? fallback)
  }

  if (error instanceof Error && error.message) {
    return error.message
  }

  return fallback
}

export function useProtectedReveal(options: ProtectedRevealOptions = {}) {
  const loading = ref(false)
  const visible = ref(false)
  const revealedValue = ref<string | null>(null)

  function reset() {
    visible.value = false
    revealedValue.value = null
  }

  function hide() {
    reset()
  }

  async function reveal(loadValue: RevealLoader) {
    try {
      const { value } = await ElMessageBox.prompt(
        options.promptMessage ?? '请输入当前登录管理员密码，验证通过后才能查看敏感信息。',
        options.promptTitle ?? '验证查看',
        {
          inputType: 'password',
          inputPlaceholder: options.inputPlaceholder ?? '请输入当前登录密码',
          confirmButtonText: options.confirmButtonText ?? '验证查看',
          cancelButtonText: options.cancelButtonText ?? '取消',
          inputValidator: (inputValue) => {
            if (!inputValue.trim()) {
              return '请输入当前登录密码'
            }

            return true
          },
        },
      )

      loading.value = true
      revealedValue.value = (await loadValue(value)) ?? null
      visible.value = true
      ElMessage.success(options.successMessage ?? '敏感信息验证通过')
    } catch (error) {
      if (error === 'cancel' || error === 'close') {
        return
      }

      ElMessage.error(getErrorMessage(error, options.errorMessage ?? '敏感信息验证失败'))
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    visible,
    revealedValue,
    reveal,
    hide,
    reset,
  }
}
