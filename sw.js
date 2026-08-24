/* Service worker.

   The shell — markup, styles, fonts, icons, the database client — is cached
   on install and served cache-first, so the app opens instantly and keeps
   working in a client's home with no signal.

   Data is never cached: every Supabase call goes to the network, because a
   stale appointment list is worse than an honest error. When the network is
   gone, the page's own error state explains it.
*/

const VERSION = 'v29';
const SHELL = `shell-${VERSION}`;

const ASSETS = [
  './',
  './index.html',
  './admin.html',
  './manifest.webmanifest',
  './manifest-admin.webmanifest',
  './assets/theme.css',
  './assets/client-theme.css',
  './assets/fonts.css',
  './assets/icons.js',
  './assets/db.js',
  './assets/config.js',
  './assets/vendor/supabase.js',
  './assets/favicon.svg',
  './assets/favicon-admin.svg',
  './assets/icon-192.svg',
  './assets/icon-512.svg',
  './assets/icon-admin-192.svg',
  './assets/icon-admin-512.svg',
  './assets/fonts/amiri-arabic-400-normal.woff2',
  './assets/fonts/amiri-arabic-700-normal.woff2',
  './assets/fonts/amiri-latin-400-normal.woff2',
  './assets/fonts/amiri-latin-700-normal.woff2',
  './assets/fonts/tajawal-arabic-400-normal.woff2',
  './assets/fonts/tajawal-arabic-500-normal.woff2',
  './assets/fonts/tajawal-arabic-700-normal.woff2',
  './assets/fonts/tajawal-latin-400-normal.woff2',
  './assets/fonts/tajawal-latin-500-normal.woff2',
  './assets/fonts/tajawal-latin-700-normal.woff2',
  './assets/fonts/aref-ruqaa-arabic-400-normal.woff2',
  './assets/fonts/aref-ruqaa-latin-400-normal.woff2',

  // وسائط الواجهة الجديدة: الصور والفيديوهات جزء من القشرة، فبدونها
  // تفتح الصفحة بلا خلفيات في بيت العميلة حيث لا شبكة.
  './assets/brand/hero_still.jpg',
  './assets/brand/logo_dark.png',
  './assets/brand/logo_light.png',
  './assets/brand/dust_a.jpg',
  './assets/brand/dust_light.jpg',
  './assets/brand/riyal.png',
  './assets/brand/pst_bridal.jpg',
  './assets/brand/pst_evening.jpg',
  './assets/brand/thumb_bridal.jpg',
  './assets/brand/thumb_evening.jpg',
  './assets/brand/svc_bridal.mp4',
  './assets/brand/svc_evening.mp4',
];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(SHELL);
    // addAll rejects the whole install if any single file 404s; cache each
    // one on its own so a missing optional asset cannot break installation.
    await Promise.all(ASSETS.map((url) =>
      cache.add(url).catch((err) => console.warn('[sw] skipped', url, err))));
    self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k !== SHELL).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Anything that is not our own origin is data (Supabase) — always live.
  if (url.origin !== self.location.origin) return;

  event.respondWith((async () => {
    const cached = await caches.match(request, { ignoreSearch: url.pathname.endsWith('.html') });
    if (cached) {
      // Refresh in the background so the next open is current.
      event.waitUntil((async () => {
        try {
          const fresh = await fetch(request);
          if (fresh.ok) (await caches.open(SHELL)).put(request, fresh.clone());
        } catch { /* offline: the cached copy stands */ }
      })());
      return cached;
    }
    try {
      const fresh = await fetch(request);
      if (fresh.ok && url.origin === self.location.origin) {
        (await caches.open(SHELL)).put(request, fresh.clone());
      }
      return fresh;
    } catch {
      // A navigation with nothing cached still gets the app shell.
      if (request.mode === 'navigate') {
        const shell = await caches.match('./index.html');
        if (shell) return shell;
      }
      throw new Error('offline and not cached');
    }
  })());
});
