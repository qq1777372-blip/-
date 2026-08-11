const nativeProtocols = new Set(['capacitor:', 'ionic:'])

export const isNativeApp = import.meta.env.MODE === 'native' || (typeof window !== 'undefined' && nativeProtocols.has(window.location.protocol))
export const apiOrigin = String(import.meta.env.VITE_NATIVE_API_ORIGIN || 'https://xiaoxu666.asia').replace(/\/$/, '')

export function apiUrl(path: string) {
  if (!isNativeApp || !path.startsWith('/')) return path
  return `${apiOrigin}${path}`
}

export function installNativeFetchBridge() {
  if (!isNativeApp) return
  const originalFetch = window.fetch.bind(window)
  window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    if (typeof input === 'string') return originalFetch(apiUrl(input), init)
    if (input instanceof URL) return originalFetch(new URL(apiUrl(input.pathname + input.search + input.hash)), init)
    if (input.url.startsWith(window.location.origin)) {
      const localUrl = new URL(input.url)
      return originalFetch(new Request(apiUrl(localUrl.pathname + localUrl.search + localUrl.hash), input), init)
    }
    return originalFetch(input, init)
  }
}
