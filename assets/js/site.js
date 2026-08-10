// Theme switching, the mobile nav drawer, and the post filter.
(function () {
  'use strict';

  var root = document.documentElement;

  // ─── Light / dark ──────────────────────────────────────────
  function currentTheme() {
    var set = root.getAttribute('data-theme');
    if (set) return set;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function toggleTheme() {
    var next = currentTheme() === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('theme', next); } catch (e) {}
  }

  ['theme-toggle', 'theme-toggle-mobile'].forEach(function (id) {
    var button = document.getElementById(id);
    if (button) button.addEventListener('click', toggleTheme);
  });

  // ─── Mobile drawer ─────────────────────────────────────────
  var sidebar = document.getElementById('sidebar');
  var scrim = document.getElementById('scrim');
  var menuButton = document.getElementById('menu-toggle');

  function setDrawer(open) {
    if (!sidebar) return;
    sidebar.classList.toggle('open', open);
    if (scrim) scrim.hidden = !open;
    if (menuButton) menuButton.setAttribute('aria-expanded', String(open));
    document.body.style.overflow = open ? 'hidden' : '';
  }

  if (menuButton) {
    menuButton.addEventListener('click', function () {
      setDrawer(!sidebar.classList.contains('open'));
    });
  }
  if (scrim) scrim.addEventListener('click', function () { setDrawer(false); });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') setDrawer(false);
  });

  // Tapping a link inside the drawer should close it.
  if (sidebar) {
    sidebar.addEventListener('click', function (event) {
      if (event.target.closest('a')) setDrawer(false);
    });
  }

  // Reset the drawer when resizing up to the desktop layout.
  window.addEventListener('resize', function () {
    if (window.innerWidth > 900) setDrawer(false);
  });

  // ─── Filter the post list in the sidebar ───────────────────
  var filter = document.getElementById('nav-filter');
  var noResults = document.getElementById('nav-no-results');

  if (filter) {
    filter.addEventListener('input', function () {
      var query = filter.value.trim().toLowerCase();
      var items = document.querySelectorAll('.nav-posts li');
      var shown = 0;

      items.forEach(function (item) {
        var match = item.textContent.toLowerCase().indexOf(query) !== -1;
        item.hidden = !match;
        if (match) shown++;
      });

      // Hide a folder group (heading + list) when none of its posts match,
      // so you don't see empty "C", "Python"… headings while searching.
      document.querySelectorAll('.nav-group').forEach(function (grp) {
        var anyVisible = grp.querySelector('.nav-posts li:not([hidden])');
        grp.hidden = !anyVisible;
      });

      if (noResults) noResults.hidden = shown !== 0;
    });
  }

  // Keep the active post visible in a long sidebar list.
  var current = document.querySelector('.nav-posts .current');
  if (current && window.innerWidth > 900) {
    var box = current.getBoundingClientRect();
    if (box.top < 0 || box.bottom > window.innerHeight) {
      current.scrollIntoView({ block: 'center' });
    }
  }

  // ─── Table-of-contents popup (mobile only) ─────────────────
  // No-ops on pages without a TOC (home, about, short posts). The wide-screen
  // rail needs no JS — these handlers only drive the bottom-left popup.
  var toc = document.getElementById('toc-panel') ? document.querySelector('.toc') : null;
  var tocFab = document.querySelector('.toc-fab');

  if (toc && tocFab) {
    var closeToc = function () {
      toc.classList.remove('open');
      tocFab.setAttribute('aria-expanded', 'false');
    };

    tocFab.addEventListener('click', function (event) {
      event.stopPropagation();
      var open = toc.classList.toggle('open');
      tocFab.setAttribute('aria-expanded', String(open));
    });

    // Close after picking a heading, on an outside tap, or on Escape.
    toc.addEventListener('click', function (event) {
      if (event.target.closest('a')) closeToc();
    });
    document.addEventListener('click', function (event) {
      if (toc.classList.contains('open') && !event.target.closest('.toc')) closeToc();
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') closeToc();
    });
  }
})();
