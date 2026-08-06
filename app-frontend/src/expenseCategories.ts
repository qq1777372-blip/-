import { api } from './api'
import { readCache, writeCache } from './dataCache'

// Single owner of the /expense-categories contract. The backend stores an ordered
// list in AppSetting; the expense records themselves keep a free-text category, so
// renaming or removing an entry only changes future choices and never rewrites
// historical bookkeeping.

export const CATEGORY_CACHE_KEY = 'expense-categories'
// Mirrors the backend contract exactly: ExpenseCategoryUpdateRequest allows 1-30
// entries, each trimmed, non-empty, unique and at most 50 characters. Keeping these
// in sync means the form rejects the same input the API would.
export const maxCategoryNameLength = 50
export const maxCategoryCount = 30

export type ExpenseCategoryConfig = {
  categories: string[]
  is_default: boolean
  usage: Record<string, number>
  orphan_categories: string[]
}

// Matches the list the app shipped with, used when the request fails and nothing
// has been cached yet, so the keypad is never left without categories.
export const fallbackCategories = ['办公用品', '快递物流', '餐饮招待', '差旅交通', '软件服务', '广告推广', '采购货款', '其他消费']

export function fallbackConfig(): ExpenseCategoryConfig {
  return { categories: [...fallbackCategories], is_default: true, usage: {}, orphan_categories: [] }
}

/** Trim, drop blanks, and de-duplicate while keeping the caller's order. */
export function normalizeCategories(values: string[]) {
  const seen = new Set<string>()
  const result: string[] = []
  for (const value of values) {
    const name = (value ?? '').trim()
    if (!name || seen.has(name)) continue
    seen.add(name)
    result.push(name)
  }
  return result
}

export function validateCategories(values: string[]) {
  const normalized = normalizeCategories(values)
  if (!normalized.length) return { ok: false as const, error: '至少需要保留一个分类' }
  if (normalized.length > maxCategoryCount) return { ok: false as const, error: `最多 ${maxCategoryCount} 个分类` }
  const tooLong = normalized.find((item) => item.length > maxCategoryNameLength)
  if (tooLong) return { ok: false as const, error: `分类名称不能超过 ${maxCategoryNameLength} 个字符` }
  const trimmed = values.map((item) => (item ?? '').trim()).filter(Boolean)
  if (trimmed.length !== normalized.length) return { ok: false as const, error: '分类名称重复' }
  return { ok: true as const, categories: normalized }
}

function coerce(payload: Partial<ExpenseCategoryConfig> | null | undefined): ExpenseCategoryConfig {
  const categories = normalizeCategories(Array.isArray(payload?.categories) ? payload!.categories : [])
  // An empty list from the server would leave the form unusable, so fall back.
  if (!categories.length) return fallbackConfig()
  return {
    categories,
    is_default: Boolean(payload?.is_default),
    usage: (payload?.usage && typeof payload.usage === 'object') ? payload.usage : {},
    orphan_categories: Array.isArray(payload?.orphan_categories) ? payload!.orphan_categories : [],
  }
}

export function cachedExpenseCategories(userId: number | null | undefined) {
  const entry = readCache<ExpenseCategoryConfig>(userId, CATEGORY_CACHE_KEY)
  return entry ? { config: coerce(entry.data), savedAt: entry.savedAt } : null
}

export async function getExpenseCategories(userId?: number | null) {
  const config = coerce(await api<ExpenseCategoryConfig>('/expense-categories'))
  writeCache(userId, CATEGORY_CACHE_KEY, config)
  return config
}

export async function replaceExpenseCategories(categories: string[], userId?: number | null) {
  const config = coerce(await api<ExpenseCategoryConfig>('/expense-categories', {
    method: 'PUT',
    body: JSON.stringify({ categories }),
  }))
  writeCache(userId, CATEGORY_CACHE_KEY, config)
  return config
}

export async function resetExpenseCategories(userId?: number | null) {
  const config = coerce(await api<ExpenseCategoryConfig>('/expense-categories', { method: 'DELETE' }))
  writeCache(userId, CATEGORY_CACHE_KEY, config)
  return config
}

/**
 * Choices to show in the form. A record being edited may carry a category that has
 * since been renamed or removed; it is appended so the record keeps its own value
 * instead of being silently reassigned on save.
 */
export function choicesWithLegacy(categories: string[], current?: string | null) {
  const name = (current ?? '').trim()
  if (!name || categories.includes(name)) return categories
  return [...categories, name]
}

export function isLegacyCategory(categories: string[], name?: string | null) {
  const value = (name ?? '').trim()
  return Boolean(value) && !categories.includes(value)
}
