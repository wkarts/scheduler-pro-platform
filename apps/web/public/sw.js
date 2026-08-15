const CACHE = 'scheduler-pro-web-v1'
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(['/','/offline.html']))))
self.addEventListener('fetch', event => event.respondWith(fetch(event.request).catch(() => caches.match(event.request).then(r => r || caches.match('/offline.html')))))
