const nativeProtocols = new Set(['capacitor:', 'ionic:'])

export const isNativeApp = import.meta.env.MODE === 'native' || (typeof window !== 'undefined' && nativeProtocols.has(window.location.protocol))
export const apiOrigin = String(import.meta.env.VITE_NATIVE_API_ORIGIN || 'https://xiaoxu666.asia').replace(/\/$/, '')

export function apiUrl(path: string) {
  if (!isNativeApp || !path.startsWith('/')) return path
  return `${apiOrigin}${path}`
}

export function assetUrl(value: unknown) {
  const path = typeof value === 'string' ? value.trim() : ''
  return path ? apiUrl(path) : ''
}

export function installNativeAssetBridge() {
  if (!isNativeApp) return
  const objectUrls = new WeakMap<HTMLImageElement, string>()
  const loading = new WeakSet<HTMLImageElement>()
  const loadImage = async (image: HTMLImageElement) => {
    const source = image.getAttribute('src')?.trim() || ''
    if (!source || source.startsWith('blob:') || source.startsWith('data:') || loading.has(image)) return
    const remote = source.startsWith('/') ? apiUrl(source) : source
    if (!remote.startsWith(apiOrigin)) return
    loading.add(image)
    try {
      const response = await fetch(remote, { credentials: 'include' })
      if (!response.ok) return
      const objectUrl = URL.createObjectURL(await response.blob())
      const previous = objectUrls.get(image)
      if (previous) URL.revokeObjectURL(previous)
      objectUrls.set(image, objectUrl)
      image.src = objectUrl
    } catch {
      // Leave the normal broken-image state in place while offline.
    } finally {
      loading.delete(image)
    }
  }
  const scan = (root: ParentNode) => {
    if (root instanceof HTMLImageElement) void loadImage(root)
    root.querySelectorAll?.('img[src]').forEach((node) => void loadImage(node as HTMLImageElement))
  }
  new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === 'attributes') scan(mutation.target as ParentNode)
      mutation.addedNodes.forEach((node) => { if (node instanceof Element) scan(node) })
    }
  }).observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['src'] })
  scan(document)
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
