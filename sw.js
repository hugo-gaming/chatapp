const CACHE = 'chatapp-v1';
const FILES = ['./index_online.html', './manifest.json'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)));
});

self.addEventListener('fetch', e => {
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request))
  );
});

self.addEventListener('push', e => {
  const data = e.data ? e.data.json() : { title: 'ChatApp', body: 'Nouveau message !' };
  e.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: './icon.png',
      badge: './icon.png',
      vibrate: [200, 100, 200]
    })
  );
});
