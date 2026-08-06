import { appModules, canOpenModule, type AppModule } from './modules'

// Which shortcuts show under 常用功能 on the home tab. Persisted locally per
// device so each user keeps their own set without a backend field.
const STORAGE_KEY = 'app-home-modules'
const MAX_ITEMS = 11

export const defaultHomeKeys = [
  'company-expenses',
  'tasks',
  'profits',
  'shops',
  'sycm',
  'warehouse-stock',
  'links',
  'knowledge',
]

export function readHomeKeys() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return [...defaultHomeKeys]
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return [...defaultHomeKeys]
    const keys = parsed.filter((key): key is string => typeof key === 'string')
    return keys.length ? keys.slice(0, MAX_ITEMS) : [...defaultHomeKeys]
  } catch {
    return [...defaultHomeKeys]
  }
}

export function writeHomeKeys(keys: string[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(keys.slice(0, MAX_ITEMS)))
}

export function resetHomeKeys() {
  localStorage.removeItem(STORAGE_KEY)
}

// A stored key can outlive its module (renamed, or permission revoked), so
// always resolve against what this user may actually open.
export function resolveHomeModules(
  keys: string[],
  role: string | undefined,
  can: (permission?: string) => boolean,
) {
  const allowed = new Map<string, AppModule>()
  for (const item of appModules) {
    if (canOpenModule(item, role, can)) allowed.set(item.key, item)
  }
  return keys.map((key) => allowed.get(key)).filter((item): item is AppModule => Boolean(item))
}

export { MAX_ITEMS as maxHomeModules }
