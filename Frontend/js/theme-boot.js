// Applies the saved theme before the page paints (avoids a light/dark flash).
(function () {
  var root = document.documentElement;
  function read(key, fallback) {
    try { return localStorage.getItem(key) || fallback; } catch (e) { return fallback; }
  }
  var media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  function apply() {
    var mode = read('ce.theme', 'system');
    var dark = mode === 'dark' || (mode === 'system' && media && media.matches);
    root.dataset.theme = dark ? 'dark' : 'light';
    root.dataset.accent = read('ce.accent', 'teal');
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', dark ? '#0E1513' : '#F4FBF8');
  }
  apply();
  if (media && media.addEventListener) media.addEventListener('change', apply);
  window.__applyTheme = apply;
})();
