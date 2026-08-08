import { reactive } from 'vue'
import { api } from './api'

// The bell in the header needs to know whether anything is waiting, but the badge
// must not cost every page its own request. The counts live here; root pages ask
// for a refresh on mount and AlertsPage pushes the numbers it already fetched.
export const alerts = reactive({ openCount: 0, criticalCount: 0, loaded: false })

let inflight: Promise<void> | null = null

export function setAlertCounts(openCount: number, criticalCount: number) {
  alerts.openCount = Number.isFinite(openCount) ? openCount : 0
  alerts.criticalCount = Number.isFinite(criticalCount) ? criticalCount : 0
  alerts.loaded = true
}

// status_filter=open only trims the item list; open_count/critical_count are
// always counted over every alert, so the badge stays correct.
//
// A failure deliberately leaves the previous counts alone: a badge that blinks
// off on one dropped request is worse than a slightly stale one.
export function refreshAlertCounts() {
  if (inflight) return inflight
  inflight = api<{ open_count?: number; critical_count?: number }>('/system-alerts?status_filter=open')
    .then(payload => setAlertCounts(Number(payload?.open_count) || 0, Number(payload?.critical_count) || 0))
    .catch(() => {})
    .finally(() => { inflight = null })
  return inflight
}
