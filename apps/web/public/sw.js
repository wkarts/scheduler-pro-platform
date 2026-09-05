const CACHE_PREFIX = 'scheduler-pro-web-'
const CACHE = `${CACHE_PREFIX}tenant-runtime-recovery-v7-resilience-20260905`
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/offline.html',
  '/manifest.webmanifest',
  '/favicon.svg',
  '/icons/icon.svg',
  '/icons/maskable.svg',
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

function isImmutableAsset(url) {
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

  if (
    url.pathname.startsWith('/api/') ||
    url.pathname.startsWith('/a/') ||
    url.pathname.startsWith('/agendar')
  ) {
    event.respondWith(fetch(request, { cache: 'no-store' }))
    return
  }

  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request, '/offline.html'))
    return
  }

  if (isImmutableAsset(url)) {
    event.respondWith(
      caches.match(request).then(cached => cached || fetch(request).then(response => {
        if (response && response.ok) {
          const copy = response.clone()
          caches.open(CACHE).then(cache => cache.put(request, copy)).catch(() => undefined)
        }
        return response
      })),
    )
    return
  }

  event.respondWith(networkFirst(request))
})

self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') self.skipWaiting()
})

self.addEventListener('push', event => {
  let payload = {}
  try {
    payload = event.data ? event.data.json() : {}
  } catch {
    payload = { body: event.data ? event.data.text() : 'Sua agenda foi atualizada.' }
  }

  const title = payload.title || 'Scheduler Pro'
  const options = {
    body: payload.body || 'Sua agenda foi atualizada.',
    icon: '/icons/icon.svg',
    badge: '/icons/maskable.svg',
    tag: payload.tag || 'scheduler-pro-agenda',
    renotify: true,
    data: {
      url: payload.url || '/#agenda',
      event_type: payload.event_type || '',
      appointment_id: payload.appointment_id || '',
      sequence: payload.sequence || 0,
    },
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', event => {
  event.notification.close()
  const target = new URL(event.notification.data?.url || '/#agenda', self.location.origin).href
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clients => {
      for (const client of clients) {
        if ('navigate' in client && 'focus' in client) {
          return client.navigate(target).then(() => client.focus())
        }
      }
      return self.clients.openWindow(target)
    }),
  )
})
