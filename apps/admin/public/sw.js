const CACHE_PREFIX = 'scheduler-pro-admin-'
const CACHE = `${CACHE_PREFIX}avb-2.3.2-interactionfix-v3`
const STATIC_ASSETS = [
  '/', '/index.html', '/offline.html', '/manifest.webmanifest',
  '/favicon-dark.svg', '/favicon.svg', '/icons/icon.svg', '/icons/maskable.svg',
]

self.addEventListener('install', event => {
  self.skipWaiting()
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(STATIC_ASSETS)))
})

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key.startsWith(CACHE_PREFIX) && key !== CACHE).map(key => caches.delete(key))))
      .then(() => self.clients.claim()),
  )
})

function immutableAsset(url) {
  return url.pathname.startsWith('/assets/') && /-[A-Za-z0-9_-]{8,}\.(?:js|css|woff2?|png|jpe?g|webp|svg)$/i.test(url.pathname)
}

async function networkFirst(request, fallback) {
  try {
    const response = await fetch(request, { cache: 'no-store' })
    if (response && response.ok) {
      const copy = response.clone()
      caches.open(CACHE).then(cache => cache.put(request, copy)).catch(() => undefined)
    }
    return response
  } catch {
    return (await caches.match(request)) || (fallback ? await caches.match(fallback) : undefined) || Response.error()
  }
}

self.addEventListener('fetch', event => {
  const request = event.request
  if (request.method !== 'GET') return
  const url = new URL(request.url)
  if (url.origin !== self.location.origin) return

  if (url.pathname.startsWith('/api/')) {
    event.respondWith(fetch(request, { cache: 'no-store' }))
    return
  }
  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request, '/offline.html'))
    return
  }
  if (immutableAsset(url)) {
    event.respondWith(caches.match(request).then(cached => cached || fetch(request).then(response => {
      if (response && response.ok) {
        const copy = response.clone()
        caches.open(CACHE).then(cache => cache.put(request, copy)).catch(() => undefined)
      }
      return response
    })))
    return
  }
  event.respondWith(networkFirst(request))
})

self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') self.skipWaiting()
})
