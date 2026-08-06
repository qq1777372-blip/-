// Last-known-good copies of a few read-only GETs, so a cold offline launch shows
// real numbers instead of "--" everywhere.
//
// Deliberately narrow: only whitelisted GET responses are ever written here.
// Nothing from /auth/*, captcha, attachments, or any write request is stored, and
// writes are never queued for replay - a duplicated expense is worse than an
// unavailable one. Entries are keyed per user so a shared device cannot show one
// account's figures to another.

const PREFIX = 'expense-app:v1'
const SCHEMA = 1

export type CachedEntry<T> = { data: T; savedAt: number }

type StoredEntry<T> = { schemaVersion: number; userId: number; savedAt: number; data: T }

function keyFor(userId: number, name: string) {
  return `${PREFIX}:user:${userId}:${name}`
}

export function readCache<T>(userId: number | null | undefined, name: string): CachedEntry<T> | null {
  if (userId == null || typeof localStorage === 'undefined') return null
  try {
    const raw = localStorage.getItem(keyFor(userId, name))
    if (!raw) return null
    const parsed = JSON.parse(raw) as StoredEntry<T>
    // A stale schema or a key that somehow belongs to another user is discarded
    // rather than guessed at.
    if (parsed?.schemaVersion !== SCHEMA || parsed.userId !== userId) return null
    return { data: parsed.data, savedAt: parsed.savedAt }
  } catch {
    return null
  }
}

export function writeCache<T>(userId: number | null | undefined, name: string, data: T) {
  if (userId == null || typeof localStorage === 'undefined') return
  const entry: StoredEntry<T> = { schemaVersion: SCHEMA, userId, savedAt: Date.now(), data }
  try {
    localStorage.setItem(keyFor(userId, name), JSON.stringify(entry))
  } catch {
    // A full quota must never break the screen that was merely trying to cache.
  }
}

export function clearUserCache(userId: number | null | undefined) {
  if (typeof localStorage === 'undefined') return
  const scope = userId == null ? `${PREFIX}:user:` : `${PREFIX}:user:${userId}:`
  try {
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith(scope)) localStorage.removeItem(key)
    }
  } catch {
    // Ignore storage failures during cleanup.
  }
}

export function syncedLabel(savedAt?: number | null) {
  if (!savedAt) return ''
  const date = new Date(savedAt)
  const today = new Date()
  const sameDay = date.toDateString() === today.toDateString()
  const time = `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
  return sameDay ? `上次同步 ${time}` : `上次同步 ${date.getMonth() + 1}月${date.getDate()}日 ${time}`
}
