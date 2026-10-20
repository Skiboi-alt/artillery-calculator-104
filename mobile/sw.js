// Офлайн-режим: все файлы приложения кэшируются при первом открытии.
// При изменении любого файла увеличьте VERSION — телефоны получат обновление.
const VERSION = "calc104-v2.2.0";
const FILES = [
  "./",
  "index.html",
  "styles.css",
  "app.js",
  "ballistics.js",
  "field_rules.js",
  "data.js",
  "manifest.webmanifest",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "icons/maskable-512.png",
  "icons/apple-touch-icon.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((cache) => cache.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== VERSION).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

// Сначала кэш (мгновенно и без сети), затем сеть
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    caches.match(event.request, { ignoreSearch: true }).then((cached) => cached || fetch(event.request))
  );
});
