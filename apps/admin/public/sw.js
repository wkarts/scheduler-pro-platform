const CACHE = 'scheduler-pro-admin-brand-v1.0.1'
const STATIC_ASSETS = ['/', '/index.html', '/offline.html', '/manifest.webmanifest', '/favicon-dark.svg', '/favicon.svg', '/icons/icon.svg', '/icons/maskable.svg']
self.addEventListener('install', event => { self.skipWaiting(); event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(STATIC_ASSETS))) })
self.addEventListener('activate', event => { event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim())) })
self.addEventListener('fetch', event => { const request=event.request; if(request.method!=='GET')return; event.respondWith(fetch(request).then(response=>{const copy=response.clone();caches.open(CACHE).then(cache=>cache.put(request,copy)).catch(()=>undefined);return response}).catch(()=>caches.match(request).then(cached=>cached||caches.match('/offline.html')))) })
