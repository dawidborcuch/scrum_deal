// Service Worker dla ScrumDeal
const CACHE_NAME = 'scrumdeal-v1';
const urlsToCache = [
    '/',
    '/static/css/',
    '/static/js/',
    '/static/images/'
];

self.addEventListener('install', function(event) {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(function(cache) {
                return cache.addAll(urlsToCache);
            })
    );
});

self.addEventListener('fetch', function(event) {
    event.respondWith(
        caches.match(event.request)
            .then(function(response) {
                // Zwróć z cache jeśli dostępne, w przeciwnym razie pobierz z sieci
                return response || fetch(event.request);
            })
    );
});

// Obsługa synchronizacji offline
self.addEventListener('sync', function(event) {
    if (event.tag === 'background-sync') {
        event.waitUntil(doBackgroundSync());
    }
});

function doBackgroundSync() {
    // Tutaj można dodać logikę synchronizacji danych
    return Promise.resolve();
}

// Obsługa powiadomień push
self.addEventListener('push', function(event) {
    if (event.data) {
        const data = event.data.json();
        const options = {
            body: data.body,
            icon: '/static/images/icon.png',
            badge: '/static/images/badge.png',
            vibrate: [100, 50, 100],
            data: {
                dateOfArrival: Date.now(),
                primaryKey: 1
            }
        };

        event.waitUntil(
            self.registration.showNotification(data.title, options)
        );
    }
});

// Obsługa kliknięć w powiadomienia
self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    event.waitUntil(
        clients.openWindow('/')
    );
}); 