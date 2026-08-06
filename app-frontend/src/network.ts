import { reactive } from 'vue'

// navigator.onLine only proves the device has *a* network, not that the server is
// reachable, so it seeds the initial value and failed requests correct it later.
export const network = reactive({
  online: typeof navigator === 'undefined' ? true : navigator.onLine !== false,
  updateReady: false,
})

let updateHandler: (() => Promise<void>) | null = null

export function setOnline(online: boolean) {
  network.online = online
}

export function markUpdateReady(handler: () => Promise<void>) {
  updateHandler = handler
  network.updateReady = true
}

export async function applyUpdate() {
  if (updateHandler) await updateHandler()
  else window.location.reload()
}

export function watchConnectivity() {
  if (typeof window === 'undefined') return
  window.addEventListener('online', () => setOnline(true))
  window.addEventListener('offline', () => setOnline(false))
}
