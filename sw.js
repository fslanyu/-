// 考勤日历 PWA Service Worker — 自毁版
// 此版本会清除所有缓存并注销 SW，解决 iOS 15 缓存死锁
const CACHE = 'kaoqin-destroy';

self.addEventListener('install', e => {
  self.skipWaiting(); // 立即激活
});

self.addEventListener('activate', e => {
  // 删除所有缓存
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.map(k => caches.delete(k))))
      .then(() => {
        // 注销所有 SW 注册
        return self.registration.unregister();
      })
      .then(() => {
        console.log('SW 已自毁，缓存已清空');
      })
  );
  // 不调用 clients.claim() —— 让当前页面保持不变
  // 下次加载页面时将没有 SW 拦截
});

// 不拦截任何请求（此 SW 在激活后立即自毁）
self.addEventListener('fetch', e => {
  e.respondWith(fetch(e.request));
});
