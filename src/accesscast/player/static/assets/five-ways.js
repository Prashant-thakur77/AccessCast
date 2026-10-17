/* "Same clip, every viewer" (PLAN §13.4): play one segment once per audience version. */
(function () {
  "use strict";
  var AC = window.AC, el = AC.el;
  var $ = function (id) { return document.getElementById(id); };
  var video = $("video");

  var STEPS = [
    { key: "blind.en", who: "For someone who can't see the screen", role: null, world: "blind" },
    { key: "deaf.en", who: "For someone who can't hear", role: "sdh", world: "deaf" },
    { key: "easy.en", who: "For someone who wants simpler words", role: "easy", world: "easy" },
    { key: "hi", who: "For someone who speaks Hindi", local: "हिन्दी बोलने वालों के लिए", lang: "hi", role: "subs", world: "hi" },
    { key: "it", who: "For someone who speaks Italian", local: "Per chi parla italiano", lang: "it", role: "subs", world: "it" },
    { key: "es", who: "For someone who speaks Spanish", local: "Para quien habla español", lang: "es", role: "subs", world: "es" },
    { key: "fr", who: "For someone who speaks French", local: "Pour qui parle français", lang: "fr", role: "subs", world: "fr" },
    { key: "pt", who: "For someone who speaks Portuguese", local: "Para quem fala português", lang: "pt", role: "subs", world: "pt" }
  ];
  var DEFAULT_SEGMENT_MS = 20000; /* PLAN §13.4: a 20-second segment; index.json "segment_ms" overrides it. */

  var data = { index: null, base: "" };
  var seg = { start: 0, end: DEFAULT_SEGMENT_MS };
  var run = { i: -1, active: false };
  var tracks = {};

  function announce(msg) {
    var s = $("status");
    s.textContent = "";
    window.setTimeout(function () { s.textContent = msg; }, 30);
  }

  function readSegment(idx) {
    var dur = Number(idx.duration_ms) || DEFAULT_SEGMENT_MS;
    var s = idx.segment_ms;
    var start = 0, end = Math.min(DEFAULT_SEGMENT_MS, dur);
    if (Array.isArray(s) && s.length === 2) { start = Number(s[0]); end = Number(s[1]); }
    else if (s && typeof s === "object") { start = Number(s.start_ms); end = Number(s.end_ms); }
    if (!(start >= 0) || !(end > start)) { start = 0; end = Math.min(DEFAULT_SEGMENT_MS, dur); }
    return { start: start, end: Math.min(end, dur) };
  }

  function renderSteps() {
    var ol = $("steps");
    ol.textContent = "";
    STEPS.forEach(function (st, i) {
      var ok = !!data.index.versions[st.key];
      var li = el("li", { id: "step-" + i }, [
        st.who + ": " + AC.versionName(st.key, data.index) + (ok ? "" : " (not available yet, skipped)")
      ]);
      if (i === run.i && run.active) li.setAttribute("aria-current", "step");
      ol.appendChild(li);
    });
  }

  function setButtons() {
    $("b-start").disabled = run.active;
    $("b-skip").disabled = !run.active;
    $("b-stop").disabled = !run.active;
  }

  function playStep(i) {
    while (i < STEPS.length && !data.index.versions[STEPS[i].key]) i++;
    if (i >= STEPS.length) { finish(true); return; }
    run.i = i;
    var st = STEPS[i];
    var v = data.index.versions[st.key];
    video.pause();
    video.setAttribute("src", data.base + v.file);
    tracks = AC.setTracks(video, data.base, v);
    var show = st.role ? AC.findTrack(v, st.role) : null;
    Object.keys(tracks).forEach(function (n) { tracks[n].track.mode = show && n === show.name ? "showing" : "hidden"; });
    $("who").textContent = st.who;
    document.body.setAttribute("data-world", st.world);
    var loc = $("who-local");
    loc.textContent = st.local || "";
    if (st.lang) loc.setAttribute("lang", st.lang); else loc.removeAttribute("lang");
    renderSteps();
    setButtons();
    video.addEventListener("loadedmetadata", function () {
      try { video.currentTime = seg.start / 1000; } catch (e) { /* ignore */ }
      var p = video.play();
      if (p && p.catch) p.catch(function () { announce("The browser blocked playback. Press Start again."); });
    }, { once: true });
  }

  function next() { if (run.active) playStep(run.i + 1); }

  function finish(done) {
    run.active = false;
    video.pause();
    setButtons();
    renderSteps();
    $("who").textContent = done ? "That was every viewer." : "Stopped.";
    document.body.setAttribute("data-world", "paper");
    $("who-local").textContent = "";
    $("b-start").focus();
  }

  function init() {
    AC.renderFooter($("footer"));
    setButtons();
    AC.loadProject().then(function (res) {
      data.index = res.index; data.base = res.base;
      AC.renderDisclosure($("disclosure"), data.index);
      seg = readSegment(data.index);
      $("segment").textContent = "Clip: " + (data.index.title || res.project.sha12) + ", from " + AC.fmtTime(seg.start) + " to " + AC.fmtTime(seg.end) + ".";
      renderSteps();
    }).catch(function (err) {
      var e = $("load-error");
      e.textContent = "Could not load the video. " + (err && err.message ? err.message : "");
      e.hidden = false;
      $("b-start").disabled = true;
    });

    $("b-start").addEventListener("click", function () {
      if (!data.index) return;
      run.active = true;
      playStep(0);
    });
    $("b-skip").addEventListener("click", next);
    $("b-stop").addEventListener("click", function () { finish(false); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && run.active) { e.preventDefault(); finish(false); }
    });
    video.addEventListener("timeupdate", function () {
      if (run.active && video.currentTime * 1000 >= seg.end) next();
    });
    video.addEventListener("ended", next);
    video.addEventListener("error", function () {
      if (!run.active) return;
      announce("This browser could not play this version. Press Skip to go to the next one.");
    });
  }

  init();
})();
