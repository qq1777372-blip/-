import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({
  baseURL: '/',
  timeout: 15000,
  withCredentials: true,
})

let handlingUnauthorized = false

http.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401 && !handlingUnauthorized) {
      const [{ useAuthStore }, { pinia }, { default: router }] = await Promise.all([
        import('../stores/auth'),
        import('../stores'),
        import('../router'),
      ])
      const authStore = useAuthStore(pinia)
      const detail = String(error.response?.data?.detail ?? '')
      const requestUrl = String(error.config?.url ?? '')
      const shouldHandle = authStore.currentUser !== null && !requestUrl.endsWith('/auth/login')

      if (shouldHandle) {
        handlingUnauthorized = true
        authStore.clearAuth()
        if (detail) {
          ElMessage.warning(detail)
        }
        if (router.currentRoute.value.name !== 'login') {
          await router.replace({ name: 'login' })
        }
        handlingUnauthorized = false
      }
    }

    return Promise.reject(error)
  },
)

export default http
