const CACHE_NAME = 'scrumdeal-v1';
const urlsToCache = [
    '/',
    '/static/css/',
    '/static/js/',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'
];

// Install event - cache resources
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('Opened cache');
                return cache.addAll(urlsToCache);
            })
    );
});

// Fetch event - serve from cache when offline
self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                // Return cached version or fetch from network
                if (response) {
                    return response;
                }
                return fetch(event.request);
            }
        )
    );
});

// Background sync for offline actions
self.addEventListener('sync', event => {
    if (event.tag === 'background-sync') {
        event.waitUntil(doBackgroundSync());
    }
});

function doBackgroundSync() {
    // Sync offline data when connection is restored
    return new Promise((resolve) => {
        // Check for pending offline actions
        const pendingActions = JSON.parse(localStorage.getItem('pendingActions') || '[]');
        
        if (pendingActions.length > 0) {
            // Process pending actions
            pendingActions.forEach(action => {
                // Re-send WebSocket messages or HTTP requests
                console.log('Processing pending action:', action);
            });
            
            // Clear pending actions
            localStorage.removeItem('pendingActions');
        }
        
        resolve();
    });
} 