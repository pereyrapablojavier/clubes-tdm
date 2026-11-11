/* Service worker de cada club: permite instalar la app y usarla sin conexión.
   Varios clubes comparten el dominio: cada uno usa sus propias cachés ("<slug>-<versión>") y solo borra las suyas.
   - Archivos del sitio (HTML, CSS, JS, íconos): se sirven rápido desde la caché y se actualizan en segundo plano.
   - Datos (data/*.json): primero se buscan en la red para mostrar siempre lo último; si no hay conexión, se usa la caché. */
const PREFIX = "{{slug}}-";
const VERSION = PREFIX + "{{version}}";
const CORE = [
  "./",
  "index.html",
  "manifest.webmanifest",
  "assets/styles.css?v={{version}}",
  "assets/app.js?v={{version}}",
  "assets/escudo.png",
  "assets/icons/icon-192.png",
  "assets/icons/icon-512.png",
  "assets/icons/apple-touch-icon.png",
  "data/club.json",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(CORE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith(PREFIX) && k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

const networkFirst = async (req) => {
  const cache = await caches.open(VERSION);
  try {
    const res = await fetch(req, { cache: "no-store" });
    if (res.ok) cache.put(req, res.clone());
    return res;
  } catch (err) {
    const hit = await cache.match(req, { ignoreSearch: true });
    if (hit) return hit;
    throw err;
  }
};

const staleWhileRevalidate = async (req) => {
  const cache = await caches.open(VERSION);
  const hit = await cache.match(req);
  const net = fetch(req).then((res) => { if (res.ok) cache.put(req, res.clone()); return res; }).catch(() => hit);
  return hit || net;
};

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin === location.origin) {
    if (url.pathname.includes("/data/")) return e.respondWith(networkFirst(req));
    if (req.mode === "navigate") return e.respondWith(networkFirst(req).catch(() => caches.match("index.html")));
    return e.respondWith(staleWhileRevalidate(req));
  }
  if (url.hostname.endsWith("fonts.googleapis.com") || url.hostname.endsWith("fonts.gstatic.com")) {
    e.respondWith(staleWhileRevalidate(req));
  }
});
