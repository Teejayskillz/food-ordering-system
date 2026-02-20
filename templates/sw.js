const CACHE_NAME = "foodorder-v1";
const ASSETS = ["/", "/menu/", "/static/manifest.json"];

self.addEventListener("install", (event) => {
    event.waitUntil(caches.open(CACHE_NAME).then((c) => c.addAll(ASSETS)));
});

self.addEventListener("fetch", (event) => {
    event.respondWith(caches.match(event.request).then((r) => r || fetch(event.request)));
});
