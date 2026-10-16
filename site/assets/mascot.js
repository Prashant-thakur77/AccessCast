/* "The listener": AccessCast's mascot. Original ink drawing, built here as one inline SVG (no images, no libraries).
 * Decorative only: every SVG is aria-hidden, and nothing it shows is information the page does not already give in text.
 *
 * Placement: <div class="mascot" data-mascot="hero|listen|mini"></div>. The box reserves its size in CSS (aspect-ratio).
 * State API:  ACMascot.set(target, {eyes: "open"|"closed", waves: "idle"|"dim"|"glow", phones: "on"|"faded",
 *                                     bubble: null | {text, lang, kind: "speech"|"caption"}})
 *             ACMascot.level(target, 0..1)   loudness while audio plays (drives the sound waves)
 * target: a .mascot element, or "all". */
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";

  /* ---------- geometry helpers ---------- */
  function r1(n) { return Math.round(n * 10) / 10; }
  /* Catmull-Rom through points -> smooth cubic path. */
  function smooth(pts, open) {
    var d = "M" + r1(pts[0][0]) + "," + r1(pts[0][1]);
    for (var i = 0; i < pts.length - 1; i++) {
      var p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
      var t = 6;
      d += "C" + r1(p1[0] + (p2[0] - p0[0]) / t) + "," + r1(p1[1] + (p2[1] - p0[1]) / t) + " " +
        r1(p2[0] - (p3[0] - p1[0]) / t) + "," + r1(p2[1] - (p3[1] - p1[1]) / t) + " " + r1(p2[0]) + "," + r1(p2[1]);
    }
    return open === false ? d + "Z" : d;
  }
  /* Resample a Catmull-Rom curve to n evenly spaced (by parameter) points. */
  function sample(pts, n) {
    var out = [];
    for (var k = 0; k < n; k++) {
      var u = k / (n - 1) * (pts.length - 1);
      var i = Math.min(pts.length - 2, Math.floor(u)), t = u - i;
      var p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
      var t2 = t * t, t3 = t2 * t;
      var f = function (a, b, c, e) {
        return 0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - e) * t2 + (-a + 3 * b - 3 * c + e) * t3);
      };
      out.push([f(p0[0], p1[0], p2[0], p3[0]), f(p0[1], p1[1], p2[1], p3[1])]);
    }
    return out;
  }
  function at(curve, s) {
    var u = Math.max(0, Math.min(1, s)) * (curve.length - 1), i = Math.min(curve.length - 2, Math.floor(u)), t = u - i;
    return [curve[i][0] + (curve[i + 1][0] - curve[i][0]) * t, curve[i][1] + (curve[i + 1][1] - curve[i][1]) * t];
  }
  /* Fixed pseudo-random sequence, so the drawing is the same on every visit. */
  var seed = 7;
  function rnd() { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; }

  /* ---------- the hair: flows back from the hairline and down the back, in loose waves ---------- */
  function wave(s) { var e = Math.max(0, s - 0.16); return Math.sin(e * Math.PI * 3.1) * 34 * Math.min(1, e * 3); }
  var OUTER = sample([[356, 150], [336, 114], [298, 95], [252, 97], [208, 116], [176, 152], [156, 204], [148, 262],
    [136, 320], [120, 376], [104, 434], [92, 492], [82, 550], [80, 606], [90, 654]], 90).map(function (q, i, arr) {
    return [q[0] - wave(i / (arr.length - 1)), q[1]];
  });
  var FRONT = sample([[356, 150], [344, 176], [334, 206], [326, 238], [322, 272], [318, 306], [308, 342], [296, 378],
    [284, 418], [274, 462], [264, 512], [254, 562], [244, 612], [236, 656]], 90).map(function (q, i, arr) {
    return [q[0] - wave(i / (arr.length - 1)) * 0.8, q[1]];
  });
  function hairPoint(s, d, wob, ph) {
    var o = at(OUTER, s), f = at(FRONT, s);
    var x = o[0] + (f[0] - o[0]) * d, y = o[1] + (f[1] - o[1]) * d;
    var o2 = at(OUTER, s + 0.01), f2 = at(FRONT, s + 0.01);
    var dx = (o2[0] + (f2[0] - o2[0]) * d) - x, dy = (o2[1] + (f2[1] - o2[1]) * d) - y;
    var len = Math.sqrt(dx * dx + dy * dy) || 1;
    var w = Math.sin(s * Math.PI * 2.6 + ph) * wob * Math.min(1, s * 2.2);
    return [x - dy / len * w, y + dx / len * w];
  }
  function strand(s0, s1, d0, d1, wob, ph, ext) {
    var pts = [], n = Math.max(3, Math.round((s1 - s0) * 22));
    for (var k = 0; k <= n; k++) {
      var s = s0 + (s1 - s0) * k / n;
      pts.push(hairPoint(s, d0 + (d1 - d0) * k / n, wob, ph));
    }
    if (ext) { var a = pts[pts.length - 2], b = pts[pts.length - 1]; pts.push([b[0] + (b[0] - a[0]) * ext + ext * 5, b[1] + (b[1] - a[1]) * ext]); }
    return pts;
  }
  /* A brush stroke: thin full line, plus thicker middle layers, so each strand tapers at both ends. */
  function brush(s0, s1, d0, d1, wob, ph, ext, w, delay, long) {
    var lay = [];
    var sub = function (a, b) {
      var ta = s0 + (s1 - s0) * a, tb = s0 + (s1 - s0) * b;
      return strand(ta, tb, d0 + (d1 - d0) * a, d0 + (d1 - d0) * b, wob, ph, b === 1 ? ext : 0);
    };
    lay.push({ pts: sub(0, 1), w: w * 0.42 });
    lay.push({ pts: sub(0.08, 0.8), w: w * 0.75 });
    lay.push({ pts: sub(0.2, 0.55), w: w });
    return { layers: lay, delay: delay, long: long, root: strand(s0, s0 + 0.001, d0, d0, wob, ph, 0)[0] };
  }
  function hairStrands() {
    var list = [];
    seed = 11;
    var LONG = 9;
    for (var i = 0; i < LONG; i++) {
      var d = 0.08 + (i / (LONG - 1)) * 0.84;
      list.push(brush(0.01 + rnd() * 0.04, 0.9 + rnd() * 0.1, d * 0.5, d, 8 + rnd() * 8, rnd() * 6.28, rnd() < 0.5 ? 0.5 : 0,
        2.6 + rnd() * 1.2, 1.8 + i * 0.08, true));
    }
    /* fur flicks in loose rows, like brush marks */
    for (var row = 0; row < 7; row++) {
      var sRow = 0.1 + row * 0.12;
      var count = 3 + (row % 2);
      for (var c = 0; c < count; c++) {
        var dd = (c + 0.5 + (rnd() - 0.5) * 0.6) / count;
        var ss = sRow + (rnd() - 0.5) * 0.06;
        list.push(brush(ss, Math.min(1, ss + 0.1 + rnd() * 0.12), dd, dd + (rnd() - 0.5) * 0.1, 5 + rnd() * 6, rnd() * 6.28, 0,
          2.2 + rnd() * 1.8, 2.4 + list.length * 0.025, false));
      }
    }
    /* combed-back marks at the hairline */
    [[0.02, 0.15, 0.82], [0.03, 0.14, 0.62], [0.0, 0.12, 0.4]].forEach(function (q, k) {
      list.push(brush(q[0], q[1], q[2], q[2] + 0.04, 3, k, 0, 2.6, 1.6 + k * 0.05, false));
    });
    /* wisps past the ends */
    [[0.88, 0.1], [0.9, 0.3], [0.93, 0.55], [0.9, 0.78], [0.94, 0.95]].forEach(function (q, k) {
      list.push(brush(q[0], 1, q[1], q[1] + 0.03, 9, k * 1.7, 1.2, 2.2, 3.1 + k * 0.06, false));
    });
    return list;
  }
  function hairMass() {
    var pts = [];
    for (var i = 0; i < OUTER.length; i += 5) pts.push(OUTER[i]);
    pts.push(OUTER[OUTER.length - 1]);
    var o = OUTER[OUTER.length - 1], f = FRONT[FRONT.length - 1];
    for (var k = 1; k < 9; k++) {
      var t = k / 9;
      pts.push([o[0] + (f[0] - o[0]) * t + (k % 2 ? -6 : 4), o[1] + (f[1] - o[1]) * t + (k % 2 ? 34 : 0)]);
    }
    pts.push(FRONT[FRONT.length - 1]);
    for (var j = FRONT.length - 1; j >= 0; j -= 5) pts.push(FRONT[j]);
    return smooth(pts, false);
  }

  /* ---------- cable routes (the one red accent) ---------- */
  var CABLES = {
    hero: [[302, 322], [306, 356], [313, 392], [328, 430], [350, 462], [380, 484], [396, 520], [380, 554], [344, 556], [326, 526], [344, 496], [384, 494], [414, 514], [430, 540], [452, 578], [480, 610], [512, 630], [540, 646], [560, 664]],
    listen: [[302, 322], [306, 356], [316, 394], [334, 428], [358, 456], [384, 486], [390, 524], [364, 552], [330, 546], [320, 514], [344, 490], [382, 496], [400, 530], [390, 570], [364, 608], [338, 642], [324, 676], [320, 702]],
    mini: [[302, 322], [304, 352], [310, 382], [322, 410]]
  };

  /* ---------- the drawing ---------- */
  var HAIR = null, MASS = null;
  function build(kind) {
    if (!HAIR) { HAIR = hairStrands(); MASS = hairMass(); }
    var cable = CABLES[kind] || CABLES.hero;
    var cd = smooth(cable);
    var end = cable[cable.length - 1], pre = cable[cable.length - 2];
    var ang = Math.atan2(end[1] - pre[1], end[0] - pre[0]) * 180 / Math.PI;
    var vb = kind === "mini" ? "120 20 460 460" : "40 40 560 720";
    var p = [];
    p.push('<svg class="mascot-svg" viewBox="' + vb + '" aria-hidden="true" focusable="false" xmlns="' + NS + '">');
    /* sound waves (sun) */
    p.push('<g class="m-waves">');
    [150, 184, 218, 252].forEach(function (rad, i) {
      var a0 = -60 * Math.PI / 180, a1 = -24 * Math.PI / 180, cx = 292, cy = 262;
      p.push('<path class="m-wave" style="--k:' + i + '" d="M' + r1(cx + rad * Math.cos(a0)) + "," + r1(cy + rad * Math.sin(a0)) +
        " A" + rad + "," + rad + " 0 0 1 " + r1(cx + rad * Math.cos(a1)) + "," + r1(cy + rad * Math.sin(a1)) + '"/>');
    });
    p.push("</g>");
    /* body (static) */
    p.push('<g class="m-body">');
    var bottom = kind !== "mini" ? "L536,690 C470,742 150,742 86,690" : "L540,760 L84,760";
    p.push('<path class="m-fill" d="M262,356 L336,350 C340,376 344,394 352,404 C404,414 460,440 492,486 C516,522 528,580 534,660 ' + bottom + ' C88,660 104,590 136,546 C166,506 206,480 244,466 Z"/>');
    p.push('<path class="m-ink" pathLength="1" style="--d:.15s;--w:3.2" d="M352,405 C404,414 460,440 492,486 C516,522 528,580 534,660 ' + (kind !== "mini" ? "C536,672 536,682 536,690" : "C537,700 538,730 539,760") + '"/>');
    if (kind !== "mini") p.push('<path class="m-ink" pathLength="1" style="--d:.5s;--w:2.4" d="M536,690 C470,742 150,742 86,690"/>');
    p.push('<path class="m-ink" pathLength="1" style="--d:.25s;--w:2.6" d="M286,421 C316,434 344,426 354,405"/>');
    p.push('<path class="m-ink" pathLength="1" style="--d:.3s;--w:1.5" d="M290,438 C324,448 358,438 372,413"/>');
    p.push('<path class="m-ink" pathLength="1" style="--d:.4s;--w:2.2" d="M432,548 C442,584 446,622 444,668"/>');
    p.push('<path class="m-ink" pathLength="1" style="--d:.45s;--w:1.5" d="M466,590 C472,626 474,664 472,700"/>');
    p.push('<path class="m-ink" pathLength="1" style="--d:.5s;--w:2.4" d="M136,546 C110,588 94,650 ' + (kind !== "mini" ? "86,690" : "88,740") + '"/>');
    p.push("</g>");
    /* upper body: follows the pointer (outer), breathes (inner) */
    p.push('<g class="m-look"><g class="m-breathe">');
    p.push('<path class="m-fill" d="M262,330 L330,322 C334,350 336,372 342,396 L346,430 L262,430 Z"/>');
    /* head and face */
    p.push('<path class="m-fill" d="M356,150 C368,172 374,196 372,212 C380,228 394,246 400,256 C398,264 390,266 384,266 C386,276 390,284 386,290 C388,296 386,300 380,306 C382,316 384,324 380,332 C372,344 356,350 330,352 L300,352 L300,170 Z"/>');
    /* hair strands */
    p.push('<g class="m-hair"><path class="m-fill m-hairfill" d="' + MASS + '"/>');
    HAIR.forEach(function (h) {
      var root = h.root;
      p.push('<g class="m-strand' + (h.long ? " long" : "") + '" style="--d:' + h.delay.toFixed(2) + "s;--ox:" + r1(root[0]) + "px;--oy:" + r1(root[1]) +
        "px;--sd:" + (-(h.delay * 1.7) % 5).toFixed(2) + 's">');
      h.layers.forEach(function (l) { p.push('<path class="m-hl" pathLength="1" style="--w:' + l.w.toFixed(2) + '" d="' + smooth(l.pts) + '"/>'); });
      p.push('<path class="m-ink m-crown" pathLength="1" style="--d:.2s;--w:2.6" d="' + smooth(OUTER.slice(0, 26).filter(function (q, i) { return i % 3 === 0; })) + '"/>');
    p.push("</g>");
    });
    p.push("</g>");
    p.push('<path class="m-ink m-face" pathLength="1" style="--d:.35s;--w:3.2" d="M352,146 C366,170 374,192 372,210 C372,220 381,230 391,243 C397,250 402,254 400,259 C397,265 389,266 384,266 C383,272 388,277 389,281 C389,285 386,287 383,288 C387,290 389,293 387,297 C384,301 379,303 380,310 C381,317 384,322 381,330 C375,342 360,348 342,350"/>');
    p.push('<path class="m-ink" pathLength="1" style="--d:.55s;--w:1.6" d="M344,349 C330,348 318,341 310,330"/>');
    p.push('<path class="m-ink" pathLength="1" style="--d:.6s;--w:3" d="M337,354 C339,374 342,392 351,404"/>');
    p.push('<path class="m-ink" pathLength="1" style="--d:.7s;--w:2.6" d="M332,202 C342,196 356,195 365,199"/>');
    p.push('<path class="m-ink" pathLength="1" style="--d:.75s;--w:1.8" d="M382,288 C377,290 373,290 369,288"/>');
    p.push('<path class="m-ink" pathLength="1" style="--d:.8s;--w:1.5" d="M387,262 C382,260 379,256 380,252"/>');
    /* eyes: open (blinks) and closed */
    p.push('<g class="m-eye-open"><path class="m-ink" pathLength="1" style="--d:.85s;--w:2.6" d="M338,221 C344,214 354,213 362,218"/>' +
      '<circle class="m-pupil" cx="353" cy="222" r="3.6"/><path class="m-ink" pathLength="1" style="--d:.9s;--w:1.4" d="M342,228 C348,230 354,230 359,227"/></g>');
    p.push('<g class="m-eye-closed"><path class="m-ink-static" style="--w:2.6" d="M337,221 C344,229 354,230 362,222"/>' +
      '<path class="m-ink-static" style="--w:1.6" d="M342,227 L339,233 M349,229 L348,235 M356,228 L357,234"/></g>');
    /* headphones */
    var band = "M286,212 C279,180 278,150 283,128 C286,116 291,108 298,103";
    p.push('<g class="m-phones">');
    p.push('<path class="m-band-o" pathLength="1" d="' + band + '"/>');
    p.push('<path class="m-band-i" pathLength="1" d="' + band + '"/>');
    p.push('<rect class="m-fill m-cup-ink" x="274" y="190" width="24" height="30" rx="7" transform="rotate(-8 286 205)"/>');
    p.push('<ellipse class="m-fill m-cup-ink" cx="292" cy="262" rx="44" ry="56" transform="rotate(-10 292 262)"/>');
    p.push('<ellipse class="m-cup-in" cx="298" cy="262" rx="28" ry="40" transform="rotate(-10 298 262)"/>');
    p.push('<path class="m-ink" pathLength="1" style="--d:1.2s;--w:2" d="M262,236 C258,256 260,280 268,298"/>');
    p.push('<rect class="m-jack" x="294" y="310" width="14" height="16" rx="3" transform="rotate(-10 301 318)"/>');
    p.push("</g>");
    /* bubbles (hover states on the landing page) */
    p.push('<g class="m-bubble" transform="translate(416 254)"><path class="m-bubble-shape" d="M14,0 H130 a14,14 0 0 1 14,14 V48 a14,14 0 0 1 -14,14 H34 L14,80 L18,62 H14 a14,14 0 0 1 -14,-14 V14 a14,14 0 0 1 14,-14 Z"/>' +
      '<text class="m-bubble-text" x="72" y="41" text-anchor="middle"></text></g>');
    p.push('<g class="m-caption" transform="translate(318 392)"><rect class="m-caption-box" width="168" height="46" rx="6"/>' +
      '<text class="m-caption-text" x="84" y="30" text-anchor="middle">[ music ]</text></g>');
    p.push("</g></g>");
    /* cable (red), in front of the body */
    p.push('<g class="m-cable" style="--ox:' + r1(end[0]) + 'px;--oy:' + r1(end[1]) + 'px"><path class="m-cable-line" pathLength="1" d="' + cd + '"/>');
    p.push('<path class="m-cable-flow" pathLength="1" d="' + cd + '"/>');
    if (kind !== "mini") {
      p.push('<g transform="translate(' + r1(end[0]) + "," + r1(end[1]) + ") rotate(" + r1(ang) + ')"><rect class="m-plug" x="-6" y="-7" width="24" height="14" rx="3"/>' +
        '<path class="m-plug-pin" d="M18,-3 h8 M18,3 h8"/></g>');
    }
    p.push("</g>");
    p.push("</svg>");
    return p.join("");
  }

  /* ---------- behaviour ---------- */
  var mq = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
  function reduce() { return !!(mq && mq.matches); }
  var all = [];

  function mount(box) {
    if (box.getAttribute("data-mounted")) return;
    box.setAttribute("data-mounted", "1");
    box.setAttribute("aria-hidden", "true");
    box.innerHTML = build(box.getAttribute("data-mascot") || "hero");
    box.dataset.eyes = box.dataset.eyes || "open";
    box.dataset.waves = box.dataset.waves || "idle";
    box.dataset.phones = "on";
    all.push(box);
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (es) {
        es.forEach(function (e) {
          box.classList.toggle("is-off", !e.isIntersecting);
          if (e.isIntersecting) box.classList.add("is-drawn");
        });
      }, { rootMargin: "60px" }).observe(box);
    } else box.classList.add("is-drawn");
  }

  function targets(t) { return t === "all" || !t ? all : [t]; }
  function set(t, st) {
    targets(t).forEach(function (box) {
      if (!box) return;
      if (st.eyes) box.dataset.eyes = st.eyes;
      if (st.waves) box.dataset.waves = st.waves;
      if (st.phones) box.dataset.phones = st.phones;
      if ("bubble" in st) {
        var b = st.bubble;
        box.dataset.bubble = b ? b.kind || "speech" : "";
        var txt = box.querySelector(".m-bubble-text");
        if (txt && b && b.kind !== "caption") {
          txt.textContent = b.text;
          if (b.lang) txt.setAttribute("lang", b.lang); else txt.removeAttribute("lang");
        }
      }
    });
  }
  function level(t, v) {
    targets(t).forEach(function (box) { box.style.setProperty("--lvl", String(Math.max(0, Math.min(1, v)).toFixed(3))); });
  }

  /* pointer parallax: the head turns a few degrees toward the pointer (desktop pointers only) */
  var fine = window.matchMedia && window.matchMedia("(pointer: fine)").matches;
  var px = 0, py = 0, pending = false;
  function onPointer(e) { px = e.clientX; py = e.clientY; if (!pending) { pending = true; window.requestAnimationFrame(look); } }
  function look() {
    pending = false;
    if (reduce()) return;
    all.forEach(function (box) {
      if (box.classList.contains("is-off")) return;
      var r = box.getBoundingClientRect();
      var cx = r.left + r.width * 0.5, cy = r.top + r.height * 0.35;
      var dx = Math.max(-1, Math.min(1, (px - cx) / (window.innerWidth * 0.5)));
      var dy = Math.max(-1, Math.min(1, (py - cy) / (window.innerHeight * 0.5)));
      box.style.setProperty("--look", (dy * 3 * (dx >= 0 ? 1 : -1) + dx * 1.5).toFixed(2) + "deg");
      box.style.setProperty("--lookx", (dx * 4).toFixed(1) + "px");
    });
  }
  /* scroll: the hero mascot drifts and tilts as the hero leaves */
  var ticking = false;
  function onScroll() { if (!ticking) { ticking = true; window.requestAnimationFrame(drift); } }
  function drift() {
    ticking = false;
    all.forEach(function (box) {
      if (box.getAttribute("data-mascot") !== "hero") return;
      if (reduce()) return;
      var host = box.closest(".hero-figure") || box;
      var p = Math.max(0, Math.min(1, window.scrollY / (window.innerHeight * 1.2)));
      host.style.setProperty("--drift", (p * -50).toFixed(1) + "px");
      host.style.setProperty("--tilt", (p * -3.5).toFixed(2) + "deg");
    });
  }

  function init() {
    document.querySelectorAll("[data-mascot]").forEach(mount);
    if (fine) window.addEventListener("pointermove", onPointer, { passive: true });
    window.addEventListener("scroll", onScroll, { passive: true });
    drift();
  }
  init();
  window.ACMascot = { set: set, level: level, mount: mount, build: build };
})();
