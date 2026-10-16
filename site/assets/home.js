/* AccessCast landing page. Everything shown comes from the exported data files:
 *   p/<sha12>/index.json, analysis.json, decisions.json  -> "Close your eyes"
 *   data/rule_examples.json                              -> "Gemma proposes. Code decides."
 *   data/claims.json                                     -> results and law rows ("Measuring" when a claim is missing)
 * This file holds no results and no numbers of its own. */
(function () {
  "use strict";
  var AC = window.AC, el = AC.el;
  var $ = function (id) { return document.getElementById(id); };

  function say(node, msg) {
    node.textContent = "";
    window.setTimeout(function () { node.textContent = msg; }, 30);
  }

  /* =================== Close your eyes =================== */
  var L = {
    dur: 0, speech: [], descs: [], words: [], mode: "orig", playing: false, raf: null,
    audio: { orig: null, desc: null }, files: { orig: null, desc: null }
  };

  function mergeSpans(spans, joinMs) {
    var out = [];
    spans.slice().sort(function (a, b) { return a[0] - b[0]; }).forEach(function (s) {
      var last = out[out.length - 1];
      if (last && s[0] - last[1] <= joinMs) last[1] = Math.max(last[1], s[1]);
      else out.push([s[0], s[1]]);
    });
    return out;
  }

  function drawBlocks(track, spans) {
    track.textContent = "";
    return spans.map(function (s) {
      var b = el("span", { class: "tl-block" });
      b.style.left = (s[0] / L.dur * 100) + "%";
      b.style.width = Math.max(0.6, (s[1] - s[0]) / L.dur * 100) + "%";
      track.appendChild(b);
      return b;
    });
  }

  function setupListen(res, analysis, decisions) {
    var idx = res.index, base = res.base;
    AC.renderDisclosure($("l-disclosure"), idx);
    var vOrig = idx.versions && idx.versions["deaf.en"];
    var vDesc = idx.versions && idx.versions["blind.en"];
    L.dur = Number((analysis && analysis.duration_ms) || idx.duration_ms) || 0;
    var items = (decisions && decisions.items) || [];
    var sdh = items.filter(function (it) { return it.kind === "sdh" && it.lang === "en" && it.slot; });
    var ads = items.filter(function (it) { return it.kind === "ad" && it.lang === "en" && !it.extended; });
    var speechRaw = analysis && Array.isArray(analysis.speech) && analysis.speech.length
      ? analysis.speech : sdh.map(function (it) { return [it.slot.start_ms, it.slot.end_ms]; });
    L.speech = mergeSpans(speechRaw, 400);
    L.words = sdh.map(function (it) { return { s: it.slot.start_ms, e: it.slot.end_ms, text: it.final_text }; });
    L.descs = ads.map(function (it) {
      var end = it.tts && it.tts.duration_ms ? it.anchor_ms + it.tts.duration_ms : (it.slot ? it.slot.end_ms : it.anchor_ms);
      return { s: it.anchor_ms, e: end, text: it.final_text };
    });
    if (!L.dur || !vOrig || !vDesc) {
      $("l-status").textContent = "This demo needs the original and the described version of the clip, and this site does not have both yet.";
      return;
    }
    L.files.orig = base + vOrig.file;
    L.files.desc = base + vDesc.file;
    L.speechEls = drawBlocks($("l-speech"), L.speech);
    L.descEls = drawBlocks($("l-descs"), L.descs.map(function (d) { return [d.s, d.e]; }));
    $("l-t0").textContent = AC.fmtTime(0);
    $("l-t1").textContent = AC.fmtTime(L.dur);
    var inPauses = L.descs.filter(function (d) {
      return !L.speech.some(function (s) { return d.s < s[1] && d.e > s[0]; });
    }).length;
    $("l-lanes").setAttribute("aria-label", "Timeline of the clip, " + AC.fmtTime(0) + " to " + AC.fmtTime(L.dur) + ". Speech comes in " +
      L.speech.length + " parts. Description comes in " + L.descs.length + " parts, and " + inPauses + " of " + L.descs.length +
      " sit fully inside pauses in the speech.");
    ["l-orig", "l-desc", "l-play"].forEach(function (id) { $(id).disabled = false; });
    $("l-orig").addEventListener("click", function () { choose("orig"); });
    $("l-desc").addEventListener("click", function () { choose("desc"); });
    $("l-play").addEventListener("click", togglePlay);
    document.addEventListener("visibilitychange", function () { if (document.hidden && L.playing) pause(true); });
  }

  function audioFor(mode) {
    if (!L.audio[mode]) {
      var a = new Audio();
      a.preload = "auto";
      a.src = L.files[mode];
      a.addEventListener("ended", function () { if (L.mode === mode) finished(); });
      a.addEventListener("error", function () {
        if (L.mode === mode) { stopLoop(); L.playing = false; syncUI(); say($("l-status"), "This browser could not play the sound for this clip."); }
      });
      L.audio[mode] = a;
    }
    return L.audio[mode];
  }

  function modeName(m) { return m === "desc" ? "with AccessCast description" : "the original sound"; }

  function startAt(mode, t) {
    var a = audioFor(mode);
    var go = function () {
      try { a.currentTime = t; } catch (e) { /* not seekable yet */ }
      var p = a.play();
      if (p && p.catch) p.catch(function () { L.playing = false; syncUI(); say($("l-status"), "The browser blocked the sound. Press Play to try again."); });
    };
    if (a.readyState >= 1) go(); else a.addEventListener("loadedmetadata", go, { once: true });
    L.playing = true;
    startLoop();
  }

  function choose(mode) {
    var cur = L.audio[L.mode];
    var t = cur ? cur.currentTime : 0;
    if (cur && cur.ended) t = 0;
    if (mode === L.mode && L.playing) return;
    if (cur) cur.pause();
    L.mode = mode;
    startAt(mode, t);
    syncUI();
    say($("l-status"), "Playing " + modeName(mode) + ".");
  }

  function togglePlay() {
    if (L.playing) { pause(false); return; }
    var a = audioFor(L.mode);
    startAt(L.mode, a.ended ? 0 : a.currentTime);
    syncUI();
    say($("l-status"), "Playing " + modeName(L.mode) + ".");
  }

  function pause(quiet) {
    var a = L.audio[L.mode];
    if (a) a.pause();
    L.playing = false;
    stopLoop();
    syncUI();
    if (!quiet) say($("l-status"), "Paused.");
  }

  function finished() {
    L.playing = false;
    stopLoop();
    syncUI();
    paint(L.dur);
    say($("l-status"), L.mode === "orig"
      ? "Finished. Now press “With AccessCast description” to hear the difference."
      : "Finished. Press Play to hear it again, or switch back to the original sound.");
  }

  function syncUI() {
    $("l-orig").setAttribute("aria-pressed", L.mode === "orig" ? "true" : "false");
    $("l-desc").setAttribute("aria-pressed", L.mode === "desc" ? "true" : "false");
    $("l-desc-lane").classList.toggle("is-off", L.mode !== "desc");
    $("l-play-label").textContent = L.playing ? "Pause" : "Play";
    $("l-icon").innerHTML = L.playing
      ? '<rect x="11" y="9" width="6" height="22" rx="1.5" fill="currentColor"/><rect x="23" y="9" width="6" height="22" rx="1.5" fill="currentColor"/>'
      : '<path d="M13 9l18 11-18 11z" fill="currentColor"/>';
    document.getElementById("listen").classList.toggle("is-playing", L.playing);
  }

  function startLoop() { if (L.raf === null) L.raf = window.requestAnimationFrame(tick); }
  function stopLoop() { if (L.raf !== null) { window.cancelAnimationFrame(L.raf); L.raf = null; } }
  function tick() {
    L.raf = null;
    var a = L.audio[L.mode];
    if (!a) return;
    paint(a.currentTime * 1000);
    if (L.playing) startLoop();
  }

  var lastNow = "";
  function paint(ms) {
    var p = Math.max(0, Math.min(1, ms / L.dur));
    var track = $("l-speech");
    $("l-head").style.transform = "translateX(" + (p * track.offsetWidth).toFixed(1) + "px)";
    $("l-ring").setAttribute("stroke-dashoffset", String(100 - p * 100));
    var inSpan = function (s) { return ms >= s[0] && ms < s[1]; };
    (L.speechEls || []).forEach(function (b, i) { b.classList.toggle("on", inSpan(L.speech[i])); });
    var descOn = L.mode === "desc";
    (L.descEls || []).forEach(function (b, i) { b.classList.toggle("on", descOn && ms >= L.descs[i].s && ms < L.descs[i].e); });
    var now = null;
    var d = descOn ? L.descs.filter(function (x) { return ms >= x.s && ms < x.e; })[0] : null;
    if (d) now = ["desc", "Description", d.text];
    else {
      var w = L.words.filter(function (x) { return ms >= x.s && ms < x.e; })[0];
      if (w) now = ["speech", "Speech", w.text];
      else if (L.playing) now = ["gap", "Pause", ""];
    }
    var key = now ? now.join("|") : "";
    if (key === lastNow) return;
    lastNow = key;
    var box = $("l-now");
    box.textContent = "";
    if (!now) { box.textContent = ms >= L.dur ? "That was the whole clip." : "Press play, then close your eyes."; return; }
    box.appendChild(el("span", { class: "eq", "aria-hidden": "true" }, [el("i"), el("i"), el("i")]));
    box.appendChild(el("span", { class: "tag" + (now[0] === "desc" ? " desc" : "") , text: now[1] }));
    if (now[2]) box.appendChild(document.createTextNode(now[2].replace(/\s+/g, " ")));
    else box.appendChild(document.createTextNode(descOn ? "Nothing to describe here." : "Silence on screen."));
  }

  function initListen() {
    AC.loadProject().then(function (res) {
      return Promise.all([
        AC.fetchOptionalJSON(res.base + "analysis.json"),
        AC.fetchOptionalJSON(res.base + "decisions.json")
      ]).then(function (r) { setupListen(res, r[0], r[1]); });
    }).catch(function (err) {
      $("l-status").textContent = "Could not load the demo clip. " + (err && err.message ? err.message : "");
    });
  }

  /* =================== How it works (orbit) =================== */
  function initOrbit() {
    var steps = Array.prototype.slice.call(document.querySelectorAll("#steps-list .step"));
    var dots = Array.prototype.slice.call(document.querySelectorAll("#orbit-ring .orbit-dot"));
    var orbit = $("orbit"), center = $("orbit-center");
    var active = -1;
    function setActive(i) {
      if (i === active) return;
      active = i;
      steps.forEach(function (li, j) {
        li.classList.toggle("is-active", j === i);
        li.querySelector(".step-btn").setAttribute("aria-pressed", j === i ? "true" : "false");
      });
      dots.forEach(function (d, j) { d.classList.toggle("on", j === i); });
      orbit.style.setProperty("--rot", (-60 * i) + "deg");
      var li = steps[i];
      $("orbit-num").textContent = (i < 9 ? "0" : "") + (i + 1);
      $("orbit-name").textContent = li.querySelector(".name").textContent;
      $("orbit-who").textContent = li.getAttribute("data-who") || "";
      center.classList.remove("swap");
      void center.offsetWidth; /* restart the swap animation */
      center.classList.add("swap");
    }
    steps.forEach(function (li, i) {
      var b = li.querySelector(".step-btn");
      b.addEventListener("click", function () { setActive(i); });
      b.addEventListener("focus", function () { setActive(i); });
    });
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) { if (e.isIntersecting) setActive(steps.indexOf(e.target)); });
      }, { rootMargin: "-45% 0px -45% 0px", threshold: 0 });
      steps.forEach(function (li) { io.observe(li); });
    }
    active = 0;
  }

  /* =================== Gemma proposes. Code decides. =================== */
  function initRules() {
    AC.fetchJSON("data/rule_examples.json").then(function (data) {
      var ctx = data.context || {}, ex = data.examples || [];
      if (!ex.length) throw new Error("no examples in the file");
      var card = $("scene-card");
      card.textContent = "";
      card.appendChild(el("p", { class: "micro", text: "The scene" }));
      var stats = el("div", { class: "scene-stats" });
      if (ctx.pause_seconds !== undefined) {
        stats.appendChild(el("p", null, [el("span", { class: "stat-n", text: Number(ctx.pause_seconds).toFixed(2) + " s" }), el("span", { class: "stat-l", text: "Pause to fill" })]));
      }
      if (ctx.words_max !== undefined) {
        stats.appendChild(el("p", null, [el("span", { class: "stat-n", text: String(ctx.words_max) }), el("span", { class: "stat-l", text: "Words that fit" })]));
      }
      card.appendChild(stats);
      if ((ctx.facts || []).length) {
        card.appendChild(el("h3", { text: "What Gemma saw in the frames" }));
        card.appendChild(el("ul", { class: "facts" }, ctx.facts.map(function (f) { return el("li", { text: f }); })));
      }
      if (ctx.dialogue_after) {
        card.appendChild(el("h3", { text: "What is said next" }));
        card.appendChild(el("blockquote", { text: ctx.dialogue_after }));
      }
      if (ctx.note) $("rules-note").textContent = ctx.note + " The checks are the same code that runs on every line.";

      var opts = $("ex-options");
      ex.forEach(function (e, i) {
        var id = "ex-" + i;
        var input = el("input", { type: "radio", name: "example", id: id, value: String(i) });
        input.addEventListener("change", function () { if (input.checked) show(i, true); });
        opts.appendChild(el("label", { class: "pill-radio", for: id }, [input, el("span", { text: e.label })]));
      });
      $("ex-picker").hidden = false;
      var first = 0;
      for (var k = 0; k < ex.length; k++) { if (!ex[k].ok) { first = k; break; } }
      $("ex-" + first).checked = true;
      show(first, false);

      function show(i, announce) {
        var e = ex[i], f = e.findings || [];
        var box = $("ex-result");
        box.textContent = "";
        var blocked = !e.ok;
        var stamp = el("p", { class: "stamp pop" + (blocked ? "" : " pass"), "aria-hidden": "true",
          text: blocked ? "Blocked" : "Passes" });
        box.appendChild(el("div", { class: "card verdict" }, [
          el("div", { class: "verdict-row" }, [
            el("div", null, [el("p", { class: "micro", text: "Gemma's line" }), el("p", { class: "cand", text: e.text })]),
            stamp
          ]),
          el("p", { class: "verdict-text", text: blocked
            ? "Blocked by " + f.length + (f.length === 1 ? " check" : " checks") + ". A viewer never hears it; Gemma gets the reasons and tries again."
            : "Passes every check. It can go to a person for approval." }),
          f.length ? el("ul", { class: "chips" }, f.map(function (x, j) {
            var li = el("li", null, [
              el("span", { class: "rid", text: x.rule }),
              el("span", { class: "msg", text: x.message || "" }),
              el("span", { class: "obs", text: "Measured: " + x.observed + ". Limit: " + x.threshold + "." })
            ]);
            li.style.setProperty("--i", String(j));
            return li;
          })) : el("ul", { class: "chips" }, [el("li", null, [el("span", { class: "ok", text: "No check fired." })])])
        ]));
        if (announce) say($("ex-status"), e.label + ": " + (blocked ? "blocked by " + f.length + (f.length === 1 ? " check." : " checks.") : "passes every check."));
      }
    }).catch(function (err) {
      var card = $("scene-card");
      card.textContent = "";
      card.appendChild(el("p", { text: "Could not load the rule examples (" + (err && err.message ? err.message : "error") + ")." }));
    });
  }

  /* =================== Results and law rows (data/claims.json) =================== */
  var RESULTS = [
    { label: "Lines that fit their pause", sub: "Gemma 4 with our checks and Gemma repair.", of: ["e1.fit_c", "e1.lines_planned"] },
    { label: "Gemma 4 alone", sub: "The baseline: the same plan, with no checks and no repair.", of: ["e1.fit_a", "e1.lines_planned"] },
    { label: "Attacks that reached a viewer", sub: "Hard cases we gave Gemma on purpose, asked many times.", one: "e11.total_leaks" },
    { label: "GPU cost per finished minute", sub: "All five versions on one MI300X. GPU time only; a person's review time comes on top.", one: "e14.bundle_usd_per_minute" },
    { label: "Accessibility tests passed", sub: "Player pages, keyboard and axe-core checks.", of: ["e16.player_passed", "e16.player_total"] }
  ];
  var LAW = [
    { label: "European Accessibility Act", ids: ["cited.law.eaa_apply_date"] },
    { label: "India: OTT accessibility rules", ids: ["cited.law.india_mib_ott_date"] },
    { label: "US ADA Title II, large public bodies", ids: ["cited.law.ada_title2_large_date"] },
    { label: "US ADA Title II, smaller public bodies", ids: ["cited.law.ada_title2_small_date"] },
    { label: "Italy: fines under its EAA law", ids: ["cited.law.italy_dlgs82_fine_min", "cited.law.italy_dlgs82_fine_max"], join: " to " }
  ];
  var SPLIT_TEXT = { test: "Data: the test set, never used for tuning.", dev: "Data: the dev set." };

  function measuring() { return el("span", { class: "measuring", text: "Measuring" }); }

  function row(label, valueNode, subNodes) {
    return el("div", { class: "big-row", "data-reveal": "" }, [
      el("dt", { text: label }),
      el("dd", null, [valueNode]),
      el("dd", { class: "sub" }, subNodes)
    ]);
  }

  function renderClaims(claims) {
    var get = function (id) { var c = claims[id]; return c && c.display ? c : null; };
    var dl = $("results-rows");
    dl.textContent = "";
    var missing = 0;
    RESULTS.forEach(function (r) {
      var cs = r.of ? r.of.map(get) : [get(r.one)];
      var ok = cs.every(Boolean);
      if (!ok) missing++;
      var value = ok ? document.createTextNode(r.of ? cs[0].display + " of " + cs[1].display : cs[0].display) : measuring();
      var sub = [r.sub];
      if (ok) {
        if (SPLIT_TEXT[cs[0].split]) sub.push(" " + SPLIT_TEXT[cs[0].split]);
        var ev = cs[0].evidence && cs[0].evidence[0];
        if (ev) { sub.push(" Evidence: "); sub.push(el("a", { href: AC.REPO + "/blob/main/" + ev, text: ev })); sub.push("."); }
      } else {
        sub.push(" Not measured yet.");
      }
      dl.appendChild(row(r.label, value, sub));
    });
    $("results-note").textContent = missing
      ? missing + " of " + RESULTS.length + " rows are still measuring. They fill in when the experiment runs; we never put a guess here."
      : "";

    var law = $("law-rows");
    law.textContent = "";
    LAW.forEach(function (r) {
      var cs = r.ids.map(get);
      var ok = cs.every(Boolean);
      var value = ok ? document.createTextNode(cs.map(function (c) { return c.display; }).join(r.join || " ")) : measuring();
      var sub = [];
      var c0 = claims[r.ids[0]];
      if (c0 && c0.text) sub.push(c0.text + " ");
      if (c0 && c0.source_url) sub.push(el("a", { href: c0.source_url }, ["Source", el("span", { class: "visually-hidden", text: ": " + r.label })]));
      if (!ok) sub.push(" Not loaded.");
      law.appendChild(row(r.label, value, sub));
    });
    if (window.ACMotion) window.ACMotion.reveal(document);
  }

  function initClaims() {
    AC.fetchOptionalJSON("data/claims.json").then(function (d) {
      renderClaims((d && d.claims) || {});
    }).catch(function () { renderClaims({}); });
  }

  AC.renderFooter($("footer"));
  initListen();
  initOrbit();
  initRules();
  initClaims();
})();
