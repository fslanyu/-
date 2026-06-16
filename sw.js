// 考勤日历 PWA Service Worker
const CACHE = 'kaoqin-v2';  // v2: 清除旧缓存 + 网络优先策略
const ASSETS = ['/', '/index.html'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(ASSETS))
  );
  self.skipWaiting(); // 立即激活新版 SW
});

self.addEventListener('activate', e => {
  // 清除旧版本缓存
  e.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k.startsWith('kaoqin-') && k !== CACHE)
          .map(k => caches.delete(k))
    ))
  );
  clients.claim(); // 立即接管所有页面
});

self.addEventListener('fetch', e => {
  // 网络优先：先请求网络，失败时用缓存兜底
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});
