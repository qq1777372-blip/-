import { setOnline } from './network'
import { apiUrl } from './runtime'

export type CurrentUser = {
  id: number
  username: string
  display_name: string | null
  role: string
  account_type: string
  avatar_url?: string | null
  avatar_name?: string | null
  permissions: Record<string, 'none' | 'read' | 'write'>
}

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export class ApiNetworkError extends Error {
  constructor(message = '当前网络不可用，请联网后重试') {
    super(message)
    this.name = 'ApiNetworkError'
  }
}

export function isNetworkError(error: unknown): error is ApiNetworkError {
  return error instanceof ApiNetworkError
}

function normalizeBackendUrls(value: unknown, key = ''): unknown {
  if (typeof value === 'string') {
    return value.startsWith('/') && /(?:url|src|image|avatar|attachment)/i.test(key) ? apiUrl(value) : value
  }
  if (Array.isArray(value)) return value.map((item) => normalizeBackendUrls(item, key))
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([childKey, childValue]) => [childKey, normalizeBackendUrls(childValue, childKey)]),
    )
  }
  return value
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
      ...init,
    })
    setOnline(true)
  } catch (error) {
    setOnline(false)
    throw new ApiNetworkError(error instanceof Error ? error.message : undefined)
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { detail?: string }
    throw new ApiError(response.status, body.detail || `请求失败（${response.status}）`)
  }
  if (response.status === 204) return undefined as T
  return normalizeBackendUrls(await response.json()) as T
}
