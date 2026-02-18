const CACHE_NAME = 'lift-tracker-v4';
const STATIC_ASSETS = [
  './',
  './index.html',
  './style.css',
  './app.js',
  './lifts.js',
  './firebase-config.js',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png'
];

// Install: cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch: network-first for app files (so updates are instant),
// cache-first for icons (they never change).
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Let Firebase/Google auth requests go straight to network
  if (url.hostname.includes('googleapis.com') ||
      url.hostname.includes('gstatic.com') ||
      url.hostname.includes('firebaseio.com') ||
      url.hostname.includes('google.com')) {
    return;
  }

  // Cache-first for icons
  if (url.pathname.includes('/icons/')) {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
    return;
  }

  // Network-first for everything else; fall back to cache when offline
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
