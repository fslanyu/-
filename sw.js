// 考勤日历 PWA Service Worker - v3
const CACHE = 'kaoqin-v3';  // v3: 强制清除所有旧缓存
const ASSETS = ['/', '/index.html'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(ASSETS))
  );
  self.skipWaiting(); // 立即激活，不等旧标签关闭
});

self.addEventListener('activate', e => {
  // 清除所有旧版本缓存
  e.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k.startsWith('kaoqin-')).map(k => caches.delete(k))
    ))
  );
  clients.claim(); // 立即接管所有打开的页面
});

self.addEventListener('fetch', e => {
  // 网络优先：绕过缓存，只在离线时用缓存兜底
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});
