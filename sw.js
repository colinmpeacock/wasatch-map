/* Wasatch Backcountry Planner service worker.
   Caches the page shell and the MapLibre library so the app opens without signal.
   Map tiles are NOT cached here: the page keeps them in IndexedDB (Offline maps section). */
const VERSION = 'wbp-shell-v1';
const SHELL = ['./', './index.html', './manifest.webmanifest', './icon-192.png', './icon-512.png'];
const CDN = [
  'https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js',
  'https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css'
];

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(VERSION);
    // Add files one by one so a single missing file (for example no icons uploaded) does not block install.
    for (const url of SHELL) {
      try { const r = await fetch(new Request(url, {cache: 'reload'})); if (r.ok) await cache.put(url, r); } catch (e) {}
    }
    for (const url of CDN) {
      try { const r = await fetch(new Request(url, {mode: 'cors'})); if (r.ok) await cache.put(url, r); } catch (e) {}
    }
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) if (key !== VERSION) await caches.delete(key);
    await self.clients.claim();
  })());
});

const isFont = u => u.hostname === 'fonts.googleapis.com' || u.hostname === 'fonts.gstatic.com';

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // The page itself: network first so updates arrive, cached copy when offline.
  if (req.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const r = await fetch(req);
        if (r.ok) { const c = await caches.open(VERSION); c.put('./index.html', r.clone()); }
        return r;
      } catch (e) {
        const c = await caches.open(VERSION);
        return (await c.match('./index.html')) || (await c.match('./')) ||
          new Response('Offline, and the app has not been cached yet. Open it once with signal.', {status: 503, headers: {'Content-Type': 'text/plain'}});
      }
    })());
    return;
  }

  // MapLibre from unpkg, fonts, and same-origin shell files: cache first, then network (and store).
  // Forecast data under /data/ always goes to the network; the page keeps its own last copy.
  const cacheable = CDN.includes(req.url) || isFont(url) || (url.origin === self.location.origin && !url.pathname.endsWith('sw.js') && !url.pathname.includes('/data/'));
  if (!cacheable) return;   // tiles and APIs go straight to the network; the page handles tile caching itself
  event.respondWith((async () => {
    const c = await caches.open(VERSION);
    const hit = await c.match(req);
    if (hit) return hit;
    try {
      const r = await fetch(req);
      if (r.ok || r.type === 'opaque') c.put(req, r.clone());
      return r;
    } catch (e) {
      return new Response('', {status: 504});
    }
  })());
});
