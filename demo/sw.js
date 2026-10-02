/*
 * MiWay Transit Optimizer — offline shell service worker (T166).
 *
 * Hand-rolled (~60 lines) instead of vite-plugin-pwa/workbox: one precache
 * list plus two runtime strategies is all this app needs, and the review
 * surface stays small. Spec: docs/FRONTEND-PRODUCTION-ROADMAP.md §1.1.
 *
 * Strategies:
 *  - Navigation requests: network-first, cached index.html fallback — the
 *    offline shell (reload with no network still boots the app).
 *  - /api-snapshot/* and hashed build assets: stale-while-revalidate —
 *    instant from cache, refreshed in the background. The frozen snapshots
 *    ARE the demo's data; caching them is the feature.
 *  - Live /api/*: NEVER cached — measured data must not masquerade as
 *    fresh. A failed live request falls through to the app's existing
 *    snapshot-fallback behavior (static-patch / panel error states).
 *
 * Same-origin only. Bump CACHE_VERSION to invalidate all caches; old
 * caches are deleted on activate.
 */

const CACHE_VERSION = 'miway-shell-v1';
const SHELL = 'index.html';

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll([SHELL])).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // App navigations: network first, cached shell offline.
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE_VERSION).then((c) => c.put(SHELL, copy));
          return resp;
        })
        .catch(() => caches.match(SHELL))
    );
    return;
  }

  // Live measured API: never cached.
  if (url.pathname.startsWith('/api/') && !url.pathname.startsWith('/api-snapshot/')) {
    return; // default network handling; app layers handle failure honestly
  }

  // Frozen snapshots + hashed build assets: stale-while-revalidate.
  const cacheable =
    url.pathname.startsWith('/api-snapshot/') ||
    url.pathname.startsWith('/assets/') ||
    /\.(?:css|js|woff2?|png|svg|webmanifest|geojson)$/.test(url.pathname);
  if (cacheable) {
    event.respondWith(
      caches.open(CACHE_VERSION).then(async (cache) => {
        const cached = await cache.match(req);
        const refresh = fetch(req)
          .then((resp) => {
            if (resp.ok) cache.put(req, resp.clone());
            return resp;
          })
          .catch(() => cached); // offline refresh attempt: keep serving cache
        return cached || refresh;
      })
    );
  }
});
