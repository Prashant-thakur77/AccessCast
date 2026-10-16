/* AccessCast motion: reveal on scroll, colour worlds per section, gentle parallax, pausable marquee.
 * No scroll hijacking and no libraries. With prefers-reduced-motion, nothing moves: content is shown at once,
 * colours still follow the section in view (without easing), and parallax is off. */
(function () {
  "use strict";
  var mq = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
  var reduce = function () { return !!(mq && mq.matches); };
  var hasIO = "IntersectionObserver" in window;
  document.documentElement.classList.add("js");

  /* ---------- reveal ---------- */
  function reveal(root) {
    var scope = root || document;
    scope.querySelectorAll("[data-stagger]").forEach(function (group) {
      Array.prototype.forEach.call(group.querySelectorAll("[data-reveal]"), function (n, i) {
        if (!n.style.getPropertyValue("--i")) n.style.setProperty("--i", String(i % 8));
      });
    });
    var items = scope.querySelectorAll("[data-reveal]:not(.is-in)");
    if (!hasIO || reduce()) { items.forEach(function (n) { n.classList.add("is-in"); }); return; }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("is-in"); io.unobserve(e.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    items.forEach(function (n) { io.observe(n); });
  }
  /* Anything that gets keyboard focus is shown at once, even before it scrolls into view. */
  document.addEventListener("focusin", function (e) {
    var n = e.target && e.target.closest ? e.target.closest("[data-reveal]") : null;
    if (n) n.classList.add("is-in");
  });

  /* ---------- colour worlds ---------- */
  function worlds() {
    if (!document.body.hasAttribute("data-scroll-worlds") || !hasIO) return;
    var secs = document.querySelectorAll("[data-section-world]");
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) document.body.setAttribute("data-world", e.target.getAttribute("data-section-world"));
      });
    }, { rootMargin: "-50% 0px -50% 0px", threshold: 0 });
    secs.forEach(function (s) { io.observe(s); });
  }

  /* ---------- parallax ---------- */
  function parallax() {
    var els = Array.prototype.slice.call(document.querySelectorAll("[data-speed]"));
    if (!els.length) return;
    var base = [];
    function measure() {
      base = els.map(function (n) {
        var top = 0, cur = n;
        while (cur) { top += cur.offsetTop; cur = cur.offsetParent; }
        return { top: top, h: n.offsetHeight, speed: parseFloat(n.getAttribute("data-speed")) || 0 };
      });
    }
    var ticking = false;
    function apply() {
      ticking = false;
      if (reduce()) { els.forEach(function (n) { n.style.transform = ""; }); return; }
      var vh = window.innerHeight, sy = window.scrollY;
      els.forEach(function (n, i) {
        var b = base[i];
        if (!b) return;
        var d = (b.top + b.h / 2) - (sy + vh / 2);
        if (Math.abs(d) > vh * 1.6) return;
        n.style.transform = "translate3d(0," + (d * -b.speed).toFixed(1) + "px,0)";
      });
    }
    function onScroll() { if (!ticking) { ticking = true; window.requestAnimationFrame(apply); } }
    measure(); apply();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", function () { measure(); onScroll(); });
    window.addEventListener("load", function () { measure(); onScroll(); });
    if (mq && mq.addEventListener) mq.addEventListener("change", onScroll);
  }

  /* ---------- marquee (WCAG 2.2.2: a visible pause button) ---------- */
  function marquee() {
    var m = document.getElementById("marquee"), b = document.getElementById("marquee-toggle");
    if (!m || !b) return;
    b.addEventListener("click", function () {
      var paused = m.classList.toggle("paused");
      b.textContent = paused ? "Play moving text" : "Pause moving text";
    });
  }

  reveal();
  worlds();
  parallax();
  marquee();
  window.ACMotion = { reveal: reveal, reduce: reduce };
})();
