import { api } from './api'
import { appModules, canOpenModule, type AppModule } from './modules'

// Which shortcuts show under 常用功能 on the home tab.
//
// The shared setting on the server is the source of truth, so every account sees
// the same grid. localStorage is kept purely as a paint-fast cache: the grid can
// render on a cold start before the request lands, instead of flashing empty.
const STORAGE_KEY = 'app-home-modules'
const MAX_ITEMS = 11

// One shared row for everyone. GET is open to any viewer, PUT is restricted to
// superadmin by the backend, so the permission gate does not depend on the App
// hiding a button.
const SHARED_SETTING_PATH = '/ui-settings/home-modules'

// The five warehouse tiles collapsed into one entry, but a saved layout (shared
// setting or localStorage cache) can still name any of the old keys. Mapping them
// here means no migration has to run and no stored value has to be rewritten.
const KEY_ALIASES: Record<string, string> = {
  'warehouse-stock': 'warehouse',
  'warehouse-inbound': 'warehouse',
  'warehouse-outbound': 'warehouse',
  'warehouse-movements': 'warehouse',
  'warehouse-master': 'warehouse',
}

export const defaultHomeKeys = [
  'sycm',
  'company-expenses',
  'tasks',
  'profits',
  'shops',
  'warehouse',
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
    // sycm is the entry everyone opens daily, so it stays pinned even for a
    // device whose cached set predates it.
    if (!keys.includes('sycm')) keys.unshift('sycm')
    return keys.length ? keys.slice(0, MAX_ITEMS) : [...defaultHomeKeys]
  } catch {
    return [...defaultHomeKeys]
  }
}

export function writeHomeKeys(keys: string[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(keys.slice(0, MAX_ITEMS)))
}

function normalizeKeys(value: unknown) {
  if (!Array.isArray(value)) return null
  const keys = value.filter((key): key is string => typeof key === 'string')
  return keys.length ? keys.slice(0, MAX_ITEMS) : null
}

// undefined = the request failed (offline, or a role the endpoint rejects), so
// callers must leave the current layout alone. null = reachable but nothing has
// been published yet.
export async function fetchSharedHomeKeys(): Promise<string[] | null | undefined> {
  try {
    const payload = await api<{ value?: unknown }>(SHARED_SETTING_PATH)
    return normalizeKeys(payload?.value)
  } catch {
    return undefined
  }
}

// Failures are swallowed on purpose: an edit that reached localStorage should
// still show up locally even if publishing it did not go through.
export function publishSharedHomeKeys(keys: string[]) {
  return api(SHARED_SETTING_PATH, {
    method: 'PUT',
    body: JSON.stringify({ value: keys.slice(0, MAX_ITEMS) }),
  }).catch(() => {})
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
  // Dedupe after aliasing: a layout saved before the warehouse tiles merged can
  // name two old keys that now resolve to the same entry, which would otherwise
  // render the tile twice.
  const seen = new Set<string>()
  const resolved: AppModule[] = []
  for (const key of keys) {
    const item = allowed.get(KEY_ALIASES[key] || key)
    if (!item || seen.has(item.key)) continue
    seen.add(item.key)
    resolved.push(item)
  }
  return resolved
}

export { MAX_ITEMS as maxHomeModules }
