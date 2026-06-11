const CACHE_NAME = 'agentos-v1';
const ASSETS = ['/', '/css/wallpaper.css', '/js/app.js', '/js/websocket.js', '/js/agents-renderer.js'];

self.addEventListener('install', (e) => {
    e.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', (e) => {
    // Network-first for API calls, cache-first for assets
    if (e.request.url.includes('/api/') || e.request.url.includes('/ws')) {
        return;
    }
    e.respondWith(
        fetch(e.request).catch(() => caches.match(e.request))
    );
});
