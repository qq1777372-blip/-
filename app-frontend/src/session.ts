import { reactive } from 'vue'
import { api, ApiError, ApiNetworkError, type CurrentUser } from './api'
import { clearUserCache } from './dataCache'

const USER_SNAPSHOT_KEY = 'expense-app:v1:session-user'

export const session = reactive({
  loading: false,
  loaded: false,
  offline: false,
  user: null as CurrentUser | null,
})

export function cleanOptionalUrl(value: string | null | undefined) {
  const url = typeof value === 'string' ? value.trim() : ''
  return url && !['undefined', 'null'].includes(url.toLowerCase()) ? url : null
}

function readUserSnapshot() {
  if (typeof localStorage === 'undefined') return null
  try {
    const user = JSON.parse(localStorage.getItem(USER_SNAPSHOT_KEY) || 'null') as CurrentUser | null
    return user?.id && user.username ? user : null
  } catch {
    return null
  }
}

function writeUserSnapshot(user: CurrentUser | null) {
  if (typeof localStorage === 'undefined') return
  try {
    if (user) localStorage.setItem(USER_SNAPSHOT_KEY, JSON.stringify(user))
    else localStorage.removeItem(USER_SNAPSHOT_KEY)
  } catch {
    // Storage is only an offline convenience; authentication still uses cookies.
  }
}

export function setSessionUser(user: CurrentUser | null, persist = true) {
  if (user) user.avatar_url = cleanOptionalUrl(user.avatar_url)
  session.user = user
  session.offline = false
  if (persist) writeUserSnapshot(user)
  return user
}

function clearConfirmedSession() {
  const userId = session.user?.id ?? readUserSnapshot()?.id
  clearUserCache(userId)
  writeUserSnapshot(null)
  session.user = null
  session.offline = false
}

export async function loadSession(force = false) {
  if (session.loading || (session.loaded && !force)) return session.user
  session.loading = true
  try {
    setSessionUser(await api<CurrentUser>('/auth/me'))
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      clearConfirmedSession()
    } else if (error instanceof ApiNetworkError) {
      // A transport failure is not a logout. Restore only the minimal last-known
      // user identity; the cookie remains the actual credential when online again.
      if (!session.user) session.user = readUserSnapshot()
      session.offline = Boolean(session.user)
    }
    // 403/5xx do not destroy an already loaded identity; the next request may work.
  } finally {
    session.loading = false
    session.loaded = true
  }
  return session.user
}

export function can(permission?: string) {
  if (!permission || session.user?.role === 'superadmin') return true
  const level = session.user?.permissions?.[permission]
  return level === 'read' || level === 'write'
}

export async function logout() {
  const userId = session.user?.id
  try {
    await fetch('/auth/logout', { method: 'POST', credentials: 'include' })
  } finally {
    clearUserCache(userId)
    writeUserSnapshot(null)
    session.user = null
    session.offline = false
    session.loaded = true
  }
}
