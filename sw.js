const CACHE_NAME = 'clubes-map-v3';
const ASSETS_TO_CACHE = [
    '/',
    '/index.html',
    'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
    'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
    'https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css',
    'https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css',
    'https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js',
];

// Instalar y cachear assets
self.addEventListener('install', event => {
    console.log('Service Worker installing...');
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            console.log('Caching core assets');
            return cache.addAll(ASSETS_TO_CACHE.filter(url => !url.includes('basemaps')));
        }).then(() => self.skipWaiting())
    );
});

// Activar y limpiar caches antiguas
self.addEventListener('activate', event => {
    console.log('Service Worker activating...');
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// Estrategia: Network first para datos, cache first para assets
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Ignorar recursos de otro origen (excepto logos)
    if (url.origin !== self.location.origin && !url.href.includes('LOGOS')) {
        return;
    }
    
    // Para datos de clubs, usar network first
    if (request.url.includes('clubs_data.js')) {
        return event.respondWith(
            fetch(request)
                .then(response => {
                    const cache = caches.open(CACHE_NAME);
                    cache.then(c => c.put(request, response.clone()));
                    return response;
                })
                .catch(() => caches.match(request))
        );
    }
    
    // Para logos, usar cache first
    if (request.url.includes('LOGOS')) {
        return event.respondWith(
            caches.match(request)
                .then(response => {
                    if (response) return response;
                    
                    return fetch(request).then(response => {
                        if (!response || response.status !== 200) return response;
                        
                        const responseToCache = response.clone();
                        caches.open(CACHE_NAME).then(cache => {
                            cache.put(request, responseToCache);
                        });
                        return response;
                    });
                })
                .catch(() => {
                    // Return placeholder if offline
                    return new Response('', { status: 404 });
                })
        );
    }
    
    // Para otros recursos, cache first
    event.respondWith(
        caches.match(request)
            .then(response => {
                if (response) return response;
                return fetch(request);
            })
            .catch(() => {
                return caches.match('/index.html');
            })
    );
});
