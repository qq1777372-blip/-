import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import { fetchCurrentUser, login, logout } from '../api'
import type { CurrentUser, LoginPayload } from '../types/api'

interface AuthState {
  initialized: boolean
  currentUser: CurrentUser | null
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    initialized: false,
    currentUser: null,
  }),
  getters: {
    displayName: (state) => {
      if (!state.currentUser) {
        return '未登录'
      }

      const roleMap: Record<string, string> = {
        viewer: '只读',
        editor: '编辑员',
        superadmin: '超级管理员',
      }

      const preferredName = state.currentUser.display_name?.trim() || state.currentUser.username
      return `${preferredName} · ${roleMap[state.currentUser.role] ?? state.currentUser.role}`
    },
  },
  actions: {
    async bootstrap() {
      try {
        this.currentUser = await fetchCurrentUser()
      } catch {
        this.currentUser = null
      } finally {
        this.initialized = true
      }
    },
    async signIn(payload: LoginPayload) {
      this.currentUser = await login(payload)
      this.initialized = true
      ElMessage.success('登录成功')
      return this.currentUser
    },
    async signOut() {
      try {
        await logout()
      } finally {
        this.clearAuth()
      }
    },
    clearAuth() {
      this.currentUser = null
      this.initialized = true
    },
  },
})
