// 電浴Go!! service worker
// オフラインキャッシュは行わず、すべてのリクエストを素通しするだけの最小構成。
// PWAの「ホーム画面に追加」を有効にするための登録用途のみ。
self.addEventListener('install', function (event) {
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', function () {
  // 何もしない（ネットワークにそのまま任せる）
});
