const nativeProtocols = new Set(['capacitor:', 'ionic:'])

export const isNativeApp = import.meta.env.MODE === 'native' || (typeof window !== 'undefined' && nativeProtocols.has(window.location.protocol))
export const apiOrigin = String(import.meta.env.VITE_NATIVE_API_ORIGIN || 'https://xiaoxu666.asia').replace(/\/$/, '')
export const nativeImageCacheName = 'ruoshop-native-images-v1'

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
  const memoryUrls = new Map<string, string>()
  const pending = new Map<string, Promise<string>>()
  const loading = new WeakSet<HTMLImageElement>()
  const maxMemoryImages = 100
  const evictMemoryImage = () => {
    while (memoryUrls.size > maxMemoryImages) {
      const oldest = memoryUrls.keys().next().value as string | undefined
      if (!oldest) return
      const objectUrl = memoryUrls.get(oldest)
      memoryUrls.delete(oldest)
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }
  const cachedObjectUrl = async (remote: string) => {
    const memoryUrl = memoryUrls.get(remote)
    if (memoryUrl) {
      // Refresh insertion order so the map acts as a small LRU cache.
      memoryUrls.delete(remote)
      memoryUrls.set(remote, memoryUrl)
      return memoryUrl
    }
    const existing = pending.get(remote)
    if (existing) return existing
    const request = (async () => {
      const cache = 'caches' in window ? await caches.open(nativeImageCacheName) : null
      let response = await cache?.match(remote)
      if (!response) {
        response = await fetch(remote, { credentials: 'include' })
        if (!response.ok) throw new Error(`Image request failed: ${response.status}`)
        await cache?.put(remote, response.clone())
      }
      const objectUrl = URL.createObjectURL(await response.blob())
      memoryUrls.set(remote, objectUrl)
      evictMemoryImage()
      return objectUrl
    })().finally(() => pending.delete(remote))
    pending.set(remote, request)
    return request
  }
  const loadImage = async (image: HTMLImageElement) => {
    const source = image.getAttribute('src')?.trim() || ''
    if (!source || source.startsWith('blob:') || source.startsWith('data:') || loading.has(image)) return
    const remote = source.startsWith('/') ? apiUrl(source) : source
    if (!remote.startsWith(apiOrigin)) return
    loading.add(image)
    try {
      const objectUrl = await cachedObjectUrl(remote)
      const previous = objectUrls.get(image)
      if (previous && !memoryUrls.has(remote)) URL.revokeObjectURL(previous)
      objectUrls.set(image, objectUrl)
      image.src = objectUrl
    } catch {
      // Leave the normal broken-image state in place while offline.
    } finally {
      loading.delete(image)
    }
  }
  const observer = 'IntersectionObserver' in window
    ? new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const image = entry.target as HTMLImageElement
            observer?.unobserve(image)
            void loadImage(image)
          }
        })
      }, { rootMargin: '240px' })
    : null
  const watch = (image: HTMLImageElement) => {
    if (image.src.startsWith('blob:') || image.src.startsWith('data:')) return
    if (observer) observer.observe(image)
    else void loadImage(image)
  }
  const scan = (root: ParentNode) => {
    if (root instanceof HTMLImageElement) watch(root)
    root.querySelectorAll?.('img[src]').forEach((node) => watch(node as HTMLImageElement))
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
