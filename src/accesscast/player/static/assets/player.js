/* AccessCast player page (PLAN §13.1–13.3). Every line and number shown comes from the exported data files. */
(function () {
  "use strict";
  var AC = window.AC, el = AC.el;
  var PREFS_KEY = "accesscast.player.v1";
  var LANGS = ["hi", "it", "es", "fr", "pt"];  // one language at a time
  var PROFILES = ["blind", "deaf", "easy"].concat(LANGS);
  var LANG_NAMES = { hi: "Hindi", it: "Italian", es: "Spanish", fr: "French", pt: "Portuguese" };
  function firstLang() { for (var i = 0; i < LANGS.length; i++) if (has(LANGS[i])) return LANGS[i]; return null; }
  /* Reading speed used for "Give me time to read" (PLAN §13.2). An export may override it with
   * index.json "read_words_per_second"; the value in use is shown to the viewer next to the checkbox. */
  var DEFAULT_READ_WPS = 2.2;

  var $ = function (id) { return document.getElementById(id); };
  var video = $("video");

  var state = {
    profiles: [], blindMode: "standard", hold: true, showCaptions: true, descText: false,
    cap: { size: "m", bg: "semi", pos: "bottom" }, filter: "all", keys: true
  };
  var data = { index: null, base: "", project: null, catalog: [], rows: {}, decisions: null, decisionsError: null };
  var current = { key: null, tracks: {}, showName: null, notes: [] };
  var hold = { held: {}, raf: null, timer: null, tick: null, cue: null };
  var judge = false;

  /* ---------- prefs ---------- */
  function loadPrefs() {
    var p = AC.store.get(PREFS_KEY);
    if (!p || typeof p !== "object") return;
    if (Array.isArray(p.profiles)) state.profiles = p.profiles.filter(function (x) { return PROFILES.indexOf(x) >= 0; });
    if (p.blindMode === "extended" || p.blindMode === "standard") state.blindMode = p.blindMode;
    if (typeof p.hold === "boolean") state.hold = p.hold;
    if (typeof p.showCaptions === "boolean") state.showCaptions = p.showCaptions;
    if (typeof p.descText === "boolean") state.descText = p.descText;
    if (typeof p.keys === "boolean") state.keys = p.keys;
    if (p.cap && typeof p.cap === "object") {
      if (["s", "m", "l", "xl"].indexOf(p.cap.size) >= 0) state.cap.size = p.cap.size;
      if (["none", "semi", "solid"].indexOf(p.cap.bg) >= 0) state.cap.bg = p.cap.bg;
      if (["bottom", "top"].indexOf(p.cap.pos) >= 0) state.cap.pos = p.cap.pos;
    }
  }
  function savePrefs() {
    AC.store.set(PREFS_KEY, {
      profiles: state.profiles, blindMode: state.blindMode, hold: state.hold,
      showCaptions: state.showCaptions, descText: state.descText, cap: state.cap, keys: state.keys
    });
  }
  function readAudienceParam() {
    var raw = AC.params().get("audience");
    if (!raw) return;
    var parts = raw.split(",").map(function (s) { return s.trim().toLowerCase(); }).filter(Boolean);
    if (parts.indexOf("judge") >= 0) judge = true;
    var picked = [];
    parts.forEach(function (x) {
      if (x === "extended" || x === "blind_ext") { picked.push("blind"); state.blindMode = "extended"; }
      else if (PROFILES.indexOf(x) >= 0) picked.push(x);
    });
    if (picked.length) {
      state.profiles = picked.filter(function (x, i) { return picked.indexOf(x) === i; });
      var keep = null;  // one language at a time: the first one named wins
      state.profiles = state.profiles.filter(function (x) {
        if (LANGS.indexOf(x) < 0) return true;
        if (keep) return false;
        keep = x; return true;
      });
    }
  }
  function has(p) { return state.profiles.indexOf(p) >= 0; }

  /* ---------- status announcements ---------- */
  function announce(msg) {
    var s = $("status");
    s.textContent = "";
    window.setTimeout(function () { s.textContent = msg; }, 30);
  }

  /* ---------- availability ---------- */
  function hasVersion(k) { return !!(data.index && data.index.versions && data.index.versions[k]); }
  function available(profile) {
    switch (profile) {
      case "blind": return hasVersion("blind.en") || hasVersion("blind_ext.en") || hasVersion("blind.hi") || hasVersion("blind.it");
      case "deaf": return hasVersion("deaf.en");
      case "easy": return hasVersion("easy.en");
    }
    if (LANGS.indexOf(profile) >= 0) return hasVersion(profile) || hasVersion("blind." + profile);
    return false;
  }
  function renderAvailability() {
    PROFILES.forEach(function (p) {
      var b = $("t-" + p), n = $("n-" + p);
      if (available(p)) { b.disabled = false; n.textContent = ""; }
      else {
        b.disabled = true;
        // a video with no speech has no words to simplify or translate: say why, not "yet"
        n.textContent = !data.noSpeech ? "Not available for this video yet."
          : p === "easy" ? "This video has no speech to simplify."
          : LANGS.indexOf(p) >= 0 ? "This video has no speech to translate." : "Not available for this video yet.";
        state.profiles = state.profiles.filter(function (x) { return x !== p; });
      }
    });
    var ext = $("r-extended");
    if (hasVersion("blind_ext.en")) { ext.disabled = false; $("n-extended").textContent = ""; }
    else {
      ext.disabled = true;
      $("n-extended").textContent = "Extended description is not available for this video yet.";
      state.blindMode = "standard";
    }
  }

  /* ---------- picker UI ---------- */
  /* The page takes on the colour world of the main audience picked (language first, then description). */
  function worldFor() {
    var l = firstLang();
    if (l) return l;
    if (has("blind")) return "blind";
    if (has("easy")) return "easy";
    if (has("deaf")) return "deaf";
    return "paper";
  }
  function syncPickerUI() {
    PROFILES.forEach(function (p) { $("t-" + p).setAttribute("aria-pressed", has(p) ? "true" : "false"); });
    document.body.setAttribute("data-world", worldFor());
    $("sub-blind").hidden = !has("blind");
    $("sub-easy").hidden = !has("easy");
    document.querySelectorAll('input[name="blindmode"]').forEach(function (r) { r.checked = r.value === state.blindMode; });
    $("c-hold").checked = state.hold;
    var wps = readWps();
    $("hold-rate").textContent = "If you don't press Continue, the video goes on by itself after 1 second for every " + wps + " words in the caption.";
    $("c-captions").checked = state.showCaptions;
    $("c-desctext").checked = state.descText;
    document.querySelectorAll('input[name="capsize"]').forEach(function (r) { r.checked = r.value === state.cap.size; });
    document.querySelectorAll('input[name="capbg"]').forEach(function (r) { r.checked = r.value === state.cap.bg; });
    document.querySelectorAll('input[name="cappos"]').forEach(function (r) { r.checked = r.value === state.cap.pos; });
  }
  function readWps() {
    var v = data.index && Number(data.index.read_words_per_second);
    return v && v > 0 ? v : DEFAULT_READ_WPS;
  }

  /* ---------- profile -> version ---------- */
  function computeVersion() {
    var notes = [], key = null, showRole = null;
    var lang = firstLang();
    if (lang) {
      var name = LANG_NAMES[lang];
      if (has("blind")) {
        if (hasVersion("blind." + lang)) key = "blind." + lang;
        else { key = lang; notes.push(name + " description not ready yet."); }
        if (state.blindMode === "extended") notes.push("Extended description is only in English for now.");
        showRole = key.indexOf("blind.") === 0 && !has("deaf") ? null : "subs";
      } else {
        key = lang; showRole = "subs";
      }
      if (has("easy")) notes.push("Simpler words are only in English for now.");
      if (!hasVersion(key)) { notes.push(name + " version is not available yet."); key = null; }
    } else if (has("blind")) {
      key = state.blindMode === "extended" ? "blind_ext.en" : "blind.en";
      if (!hasVersion(key) && hasVersion("blind.en")) { notes.push("Extended description is not ready yet."); key = "blind.en"; }
      if (!hasVersion(key) && hasVersion("blind_ext.en")) key = "blind_ext.en";
      showRole = has("deaf") ? "sdh" : null;
      if (has("easy")) notes.push("Easy-read captions are not part of the description version yet.");
    } else if (has("easy")) {
      key = "easy.en"; showRole = "easy";
    } else if (has("deaf")) {
      key = "deaf.en"; showRole = "sdh";
    } else {
      notes.push("Nobody picked yet. Pick who's watching above.");
    }
    if (!key || !hasVersion(key)) {
      var order = ["deaf.en", "easy.en", "blind.en", "blind_ext.en"].concat(LANGS, ["blind.hi", "blind.it"]);
      var all = order.filter(hasVersion).concat(Object.keys(data.index.versions));
      key = all[0];
      if (key === "deaf.en") showRole = "sdh";
      else if (key === "easy.en") showRole = "easy";
      else if (LANGS.indexOf(key) >= 0) showRole = "subs";
      else showRole = null;
    }
    return { key: key, notes: notes, showRole: showRole };
  }

  /* ---------- tracks ---------- */
  function applyTrackModes() {
    Object.keys(current.tracks).forEach(function (name) {
      var tr = current.tracks[name].track;
      tr.mode = name === current.showName && state.showCaptions ? "showing" : "hidden";
    });
    applyCuePosition();
    var hasDesc = !!AC.findTrack(data.index.versions[current.key], "desc");
    $("desc-visible").hidden = !(state.descText && hasDesc);
  }
  function applyCuePosition() {
    Object.keys(current.tracks).forEach(function (name) {
      var tr = current.tracks[name].track;
      var cues = tr.cues;
      if (!cues) return;
      var want = state.cap.pos === "top" ? 0 : "auto";
      var changed = false;
      for (var i = 0; i < cues.length; i++) {
        try { if (cues[i].line !== want) { cues[i].line = want; changed = true; } } catch (e) { /* non-VTT cue */ }
      }
      /* Chrome keeps the old layout of a cue already on screen; flip the mode to redraw it. */
      if (changed && tr.mode === "showing") { tr.mode = "hidden"; tr.mode = "showing"; }
    });
  }
  function applyCaptionClasses() {
    video.className = "cap-" + state.cap.size + " bg-" + state.cap.bg;
  }

  var lastDesc = "";
  function onDescCue(ev) {
    var cues = ev.target.activeCues;
    if (!cues || !cues.length) return;
    var text = AC.cueText(cues[cues.length - 1]);
    if (!text || text === lastDesc) return;
    lastDesc = text;
    $("desc-visible").textContent = text;
    if (current.key && current.key.indexOf("blind") === 0) {
      var live = $("desc-live");
      live.textContent = "";
      window.setTimeout(function () { live.textContent = text; }, 30);
    }
  }

  /* ---------- version switching ---------- */
  function ensureRows(key) {
    var v = data.index.versions[key];
    if (!v || !v.source_to_output) return Promise.resolve(null);
    if (data.rows[key]) return Promise.resolve(data.rows[key]);
    return AC.fetchJSON(data.base + v.source_to_output).then(function (rows) {
      if (!Array.isArray(rows)) throw new Error("timing map is not a list");
      data.rows[key] = rows;
      return rows;
    });
  }
  function rowsFor(key) { return data.rows[key] || null; }
  function isExtended(key) { var v = data.index.versions[key]; return !!(v && (v.extended || v.source_to_output)); }

  function currentSourceMs() {
    if (!current.key) return 0;
    var outMs = (video.currentTime || 0) * 1000;
    if (isExtended(current.key)) {
      var rows = rowsFor(current.key);
      return rows ? AC.outputToSource(rows, outMs) : 0;
    }
    return outMs;
  }

  function update(opts) {
    opts = opts || {};
    if (!data.index) return Promise.resolve();
    var plan = computeVersion();
    var showName = null;
    var vObj = data.index.versions[plan.key];
    if (plan.showRole) { var t = AC.findTrack(vObj, plan.showRole); showName = t ? t.name : null; }
    current.notes = plan.notes;
    $("version-note").textContent = plan.notes.join(" ");
    if (plan.key === current.key) {
      current.showName = showName;
      applyTrackModes();
      updateHoldLoop();
      if (opts.announce) announce("Now playing: " + AC.versionName(plan.key, data.index) + ". " + plan.notes.join(" "));
      return Promise.resolve();
    }
    return switchTo(plan.key, showName, plan.notes);
  }

  function switchTo(key, showName, notes) {
    var prevKey = current.key;
    var wasPlaying = !!prevKey && !video.paused && !video.ended;
    var srcMs = currentSourceMs();
    var v = data.index.versions[key];
    var extra = [];
    return ensureRows(key).catch(function () {
      extra.push("Could not load the timing map for this version, so it starts from the beginning.");
      return null;
    }).then(function (rows) {
      hideHold(); hold.held = {}; lastDesc = "";
      $("desc-visible").textContent = "";
      video.pause();
      current.key = key;
      current.showName = showName;
      video.setAttribute("src", data.base + v.file);
      current.tracks = AC.setTracks(video, data.base, v);
      Object.keys(current.tracks).forEach(function (name) {
        var trEl = current.tracks[name];
        trEl.addEventListener("load", applyCuePosition);
        if (trEl.kind === "descriptions") trEl.track.addEventListener("cuechange", onDescCue);
      });
      applyTrackModes();
      var targetMs = srcMs;
      if (isExtended(key)) targetMs = rows ? AC.sourceToOutput(rows, srcMs) : 0;
      video.addEventListener("loadedmetadata", function () {
        if (targetMs > 0) { try { video.currentTime = targetMs / 1000; } catch (e) { /* not seekable */ } }
        if (wasPlaying) { var p = video.play(); if (p && p.catch) p.catch(function () {}); }
      }, { once: true });
      updateHoldLoop();
      renderDrawer();
      // other parts of the page (the text version) follow the version being played
      document.dispatchEvent(new CustomEvent("ac:version", { detail: { key: key, version: v, base: data.base, name: AC.versionName(key, data.index) } }));
      announce("Now playing: " + AC.versionName(key, data.index) + ". " + (notes || []).concat(extra).join(" "));
    });
  }

  /* ---------- Give me time to read ---------- */
  function holdEnabled() {
    return state.hold && has("easy") && current.key === "easy.en";
  }
  function easyTrack() {
    var t = AC.findTrack(data.index.versions[current.key], "easy");
    return t && current.tracks[t.name] ? current.tracks[t.name].track : null;
  }
  function updateHoldLoop() {
    if (!holdEnabled()) { hideHold(); stopLoop(); return; }
    if (!video.paused) startLoop();
  }
  function startLoop() { if (hold.raf === null) hold.raf = window.requestAnimationFrame(holdTick); }
  function stopLoop() { if (hold.raf !== null) { window.cancelAnimationFrame(hold.raf); hold.raf = null; } }
  function holdTick() {
    hold.raf = null;
    if (video.paused || !holdEnabled()) return;
    var tr = easyTrack();
    var needs = (data.index.needs_pause_cues || []);
    if (tr && tr.cues) {
      var t = video.currentTime;
      for (var i = 0; i < tr.cues.length; i++) {
        var c = tr.cues[i];
        if (needs.indexOf(c.id) < 0 || hold.held[c.id]) continue;
        if (t >= c.startTime && t >= c.endTime - 0.12 && t < c.endTime + 0.3) {
          hold.held[c.id] = true;
          video.pause();
          if (t >= c.endTime) { try { video.currentTime = Math.max(c.startTime, c.endTime - 0.05); } catch (e) { /* ignore */ } }
          showHold(c);
          return;
        }
      }
    }
    startLoop();
  }
  function showHold(cue) {
    var words = AC.wordCount(AC.cueText(cue));
    var secs = Math.max(1, Math.ceil(words / readWps()));
    var left = secs;
    var msg = $("hold-msg");
    var setMsg = function () { msg.textContent = "Paused so you can read. It goes on by itself in " + left + (left === 1 ? " second." : " seconds."); };
    setMsg();
    $("hold").hidden = false;
    hold.cue = cue;
    $("b-continue").focus();
    announce("Paused so you can read. Press Continue when you are ready.");
    hold.tick = window.setInterval(function () { left = Math.max(0, left - 1); setMsg(); }, 1000);
    hold.timer = window.setTimeout(function () { continuePlay(false); }, secs * 1000);
  }
  function hideHold() {
    if (hold.timer) { window.clearTimeout(hold.timer); hold.timer = null; }
    if (hold.tick) { window.clearInterval(hold.tick); hold.tick = null; }
    var wasShown = !$("hold").hidden;
    $("hold").hidden = true;
    hold.cue = null;
    return wasShown;
  }
  function continuePlay(byUser) {
    var hadFocus = document.activeElement === $("b-continue");
    hideHold();
    if (hadFocus || byUser) video.focus();
    var p = video.play(); if (p && p.catch) p.catch(function () {});
  }

  /* ---------- drawer ---------- */
  var STATUS_TEXT = {
    approved: "Approved by a person.",
    auto_approved: "Passed every check. Not yet approved by a person.",
    pending: "Waiting for a person to check it.",
    rejected: "Rejected by a person.",
    needs_revision: "Blocked by our checks. A person must fix it before anyone hears it."
  };
  var STOP_TEXT = {
    safe_initial_proposal: "The first draft passed the checks.",
    repair_limit_reached: "Stopped after the most repair tries we allow."
  };
  var KIND_TEXT = {
    ad: "Description", ad_translation: "Translated description", sdh: "Caption", easy: "Easy-read caption",
    subtitle: "Subtitle", voiceover: "Voice-over"
  };

  function itemsForVersion(key) {
    var items = (data.decisions && data.decisions.items) || [];
    var m;
    var pick = function (kinds, lang) {
      return items.filter(function (it) { return kinds.indexOf(it.kind) >= 0 && (!lang || it.lang === lang); });
    };
    if (key === "blind.en" || key === "blind_ext.en") return pick(["ad"], "en");
    if ((m = /^blind\.(\w+)$/.exec(key))) return pick(["ad_translation"], m[1]);
    if (key === "deaf.en") return pick(["sdh"], "en");
    if (key === "easy.en") return pick(["easy"], "en");
    if (LANGS.indexOf(key) >= 0) return pick(["subtitle", "voiceover"], key);
    return [];
  }
  function matchesFilter(it) {
    var fired = (it.rules_fired || []).length > 0;
    var repaired = (it.repairs || []).filter(function (r) { return r.attempt > 0; }).length > 0;
    switch (state.filter) {
      case "first": return !fired && !repaired;
      case "caught": return fired;
      case "person": return !!it.changed_by_person;
    }
    return true;
  }
  function byGemma(it) { return !!(it.model && /gemma/i.test(it.model.name || "")); }

  function framesBlock(it) {
    var facts = it.facts || [];
    var box = el("div", { class: "frames" });
    (it.frames || []).forEach(function (fr, i) {
      var texts = facts.filter(function (f) { return Array.isArray(f.frames) && f.frames.indexOf(i) >= 0; }).map(function (f) { return f.text; });
      if (!texts.length) texts = facts.map(function (f) { return f.text; });
      var alt = texts.length ? texts.join(" ") : "A still frame from the video that this line is based on.";
      box.appendChild(el("img", { src: data.base + fr, alt: alt, loading: "lazy", width: "160", height: "90" }));
    });
    return box;
  }

  var svgSeq = 0;
  function timelineBlock(it) {
    var NS = "http://www.w3.org/2000/svg";
    var slot = it.slot || { start_ms: it.anchor_ms, end_ms: it.anchor_ms };
    var spanStart = it.anchor_ms;
    var spanEnd = it.tts && it.tts.duration_ms ? it.anchor_ms + it.tts.duration_ms : slot.end_ms;
    var spoken = !!(it.tts && it.tts.duration_ms);
    var slotName = (it.kind === "ad" || it.kind === "ad_translation") ? "Pause in the speech"
      : it.kind === "voiceover" ? "Time of the original speech" : "Time of the original words";
    var spanName = spoken ? "Spoken line" : "Line on screen";
    var lo = Math.max(0, Math.min(slot.start_ms, spanStart) - 500);
    var hi = Math.max(slot.end_ms, spanEnd) + 500;
    var W = 520, pad = 8, x = function (ms) { return pad + (ms - lo) / (hi - lo) * (W - 2 * pad); };
    var secs = function (a, b) { return ((b - a) / 1000).toFixed(1); };
    var label = "Timeline. " + slotName + ": " + AC.fmtTime(slot.start_ms, true) + " to " + AC.fmtTime(slot.end_ms, true) +
      ", " + secs(slot.start_ms, slot.end_ms) + " seconds. " + spanName + ": " + AC.fmtTime(spanStart, true) + " to " +
      AC.fmtTime(spanEnd, true) + ", " + secs(spanStart, spanEnd) + " seconds.";
    if (it.extended) label += " This is an extended line: the video stops while it plays.";
    var id = "pat" + (++svgSeq);
    var svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 " + W + " 76");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", label);
    var mk = function (tag, attrs) {
      var n = document.createElementNS(NS, tag);
      Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); });
      return n;
    };
    var title = mk("title", {}); title.textContent = label; svg.appendChild(title);
    var defs = mk("defs", {});
    var pat = mk("pattern", { id: id, width: "6", height: "6", patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" });
    pat.appendChild(mk("rect", { width: "3", height: "6", style: "fill: var(--span)" }));
    defs.appendChild(pat); svg.appendChild(defs);
    svg.appendChild(mk("line", { x1: pad, x2: W - pad, y1: "54", y2: "54", style: "stroke: var(--border)", "stroke-width": "1" }));
    var sw = Math.max(2, x(slot.end_ms) - x(slot.start_ms));
    svg.appendChild(mk("rect", { x: x(slot.start_ms), y: "6", width: sw, height: "18", style: "fill: var(--slot)" }));
    var pw = Math.max(2, x(spanEnd) - x(spanStart));
    svg.appendChild(mk("rect", { x: x(spanStart), y: "30", width: pw, height: "18", fill: "url(#" + id + ")", style: "stroke: var(--span)", "stroke-width": "1.5" }));
    var t1 = mk("text", { x: pad, y: "72", style: "fill: var(--fg); font-size: 13px" }); t1.textContent = AC.fmtTime(lo, true);
    var t2 = mk("text", { x: W - pad, y: "72", "text-anchor": "end", style: "fill: var(--fg); font-size: 13px" }); t2.textContent = AC.fmtTime(hi, true);
    svg.appendChild(t1); svg.appendChild(t2);
    return el("div", { class: "timeline" }, [
      svg,
      el("p", { class: "legend", "aria-hidden": "true" }, [
        el("span", null, [el("span", { class: "swatch slot" }), slotName]),
        el("span", null, [el("span", { class: "swatch span" }), spanName])
      ])
    ]);
  }

  function budgetText(it) {
    var words = AC.wordCount(it.final_text);
    var dur = it.tts && it.tts.duration_ms ? it.tts.duration_ms / 1000 : null;
    if (it.budget) {
      var s = words + " of " + it.budget.words_max + " words";
      if (dur !== null && it.budget.seconds_max) s += ", " + dur.toFixed(1) + " of " + Number(it.budget.seconds_max).toFixed(1) + " s";
      else if (it.budget.seconds_max) s += "; spoken length not measured yet (limit " + Number(it.budget.seconds_max).toFixed(1) + " s)";
      return s + ".";
    }
    if (dur !== null && it.slot) {
      return "Spoken for " + dur.toFixed(1) + " s in a " + ((it.slot.end_ms - it.slot.start_ms) / 1000).toFixed(1) + " s slot.";
    }
    return "No word budget for this kind of line.";
  }

  function rulesBlock(it) {
    var fired = it.rules_fired || [];
    if (!fired.length) return document.createTextNode("None. Every check passed.");
    var ul = el("ul", { class: "rules" });
    var viols = it.violations || [];
    fired.forEach(function (rid) {
      var vs = viols.filter(function (v) { return v.rule === rid; });
      if (vs.length) {
        vs.forEach(function (v) {
          ul.appendChild(el("li", null, [
            el("strong", { text: v.rule }), ": " + (v.message || "") +
            " Measured: " + v.observed + ". Limit: " + v.threshold + ". Still failing on the final text."
          ]));
        });
      } else {
        ul.appendChild(el("li", null, [el("strong", { text: rid }), ": passes on the final text."]));
      }
    });
    return ul;
  }

  function attemptsBlock(it) {
    var reps = it.repairs || [];
    if (!reps.length) return document.createTextNode("No tries recorded.");
    var ol = el("ol", { class: "attempts" });
    reps.forEach(function (r) {
      var who = r.attempt === 0 ? "First draft" : "Repair " + r.attempt;
      var rules = (r.rules || []).length ? "Checks failed: " + r.rules.join(", ") + "." : "Passed every check.";
      ol.appendChild(el("li", null, [
        el("strong", { text: who + ": " }),
        el("span", { lang: it.lang || null, text: r.text || "" }),
        " ", el("span", { class: "muted", text: rules })
      ]));
    });
    return ol;
  }

  function lineItem(it, n) {
    var seekLabel = "Play from " + AC.fmtTime(it.anchor_ms);
    var dl = el("dl");
    var add = function (term, node) {
      dl.appendChild(el("dt", { text: term }));
      dl.appendChild(el("dd", null, [typeof node === "string" ? document.createTextNode(node) : node]));
    };
    add("Final text", el("span", { lang: it.lang || null, text: it.final_text || "" }));
    var good = it.status === "approved" || it.status === "auto_approved";
    add("Status", el("span", { class: good ? "status-ok" : "status-bad",
      text: (STATUS_TEXT[it.status] || it.status || "Unknown") + (STOP_TEXT[it.stop_reason] ? " " + STOP_TEXT[it.stop_reason] : "") }));
    if ((it.frames || []).length) add("Evidence frames", framesBlock(it));
    add("Timing", timelineBlock(it));
    add("Budget", budgetText(it));
    add(byGemma(it) ? "Gemma's first draft" : "First draft", el("span", { lang: it.lang || null, text: it.first_draft || "" }));
    add("Checks that fired", rulesBlock(it));
    add("Every try", attemptsBlock(it));
    if ((it.warnings || []).length) {
      var wl = el("ul", { class: "rules" });
      it.warnings.forEach(function (w) {
        wl.appendChild(el("li", null, [el("strong", { text: w.rule }), ": " + (w.message || "") + " Measured: " + w.observed + ". Limit: " + w.threshold + "."]));
      });
      add("Warnings", wl);
    }
    if (it.source_text) add("Original English", el("span", { lang: "en", text: it.source_text }));
    if (it.back_translation) add("Back-translation", el("span", { lang: "en", text: it.back_translation }));
    if (it.confidence !== null && it.confidence !== undefined) add("Confidence (computed by code)", String(it.confidence));
    add("Reviewed by", it.reviewer ? it.reviewer + (it.reviewed_at ? " on " + AC.dateOnly(it.reviewed_at) : "") +
      (it.changed_by_person ? ". The person changed the text." : ".") : "Not checked by a person yet.");
    var hid = "line-h-" + n;
    return el("li", { class: "line" }, [
      el("article", { "aria-labelledby": hid }, [
        el("h3", { id: hid, text: (KIND_TEXT[it.kind] || it.kind) + " " + n + " at " + AC.fmtTime(it.anchor_ms) }),
        el("p", { class: "muted", text: "Line id: " + it.id + (it.extended ? ". Extended: the video stops for this line." : "") }),
        el("button", { type: "button", class: "seek btn-plain", "data-id": it.id, "aria-describedby": hid, text: seekLabel,
          onclick: function () { seekTo(it); } }),
        dl
      ])
    ]);
  }

  function renderDrawer() {
    var list = $("lines");
    list.textContent = "";
    if (data.decisionsError) {
      $("drawer-count").textContent = "Could not load the decisions file: " + data.decisionsError;
      return;
    }
    if (!data.decisions || !current.key) return;
    var all = itemsForVersion(current.key);
    var shown = all.filter(matchesFilter);
    shown.forEach(function (it, i) { list.appendChild(lineItem(it, i + 1)); });
    var vname = AC.versionName(current.key, data.index);
    $("drawer-count").textContent = all.length
      ? "Showing " + shown.length + " of " + all.length + " lines in: " + vname + "."
      : "No lines recorded for: " + vname + ".";
  }

  function seekTo(it) {
    var ms = it.anchor_ms || 0;
    if (isExtended(current.key)) {
      var rows = rowsFor(current.key);
      var ins = rows ? AC.insertionStart(rows, it.id) : null;
      ms = ins !== null ? ins : (rows ? AC.sourceToOutput(rows, ms) : ms);
    }
    hideHold();
    try { video.currentTime = ms / 1000; } catch (e) { /* not seekable yet */ }
    video.focus();
    announce("Moved to " + AC.fmtTime(ms) + " in the video. Press Space to play.");
  }

  function setDrawer(open) {
    $("drawer-toggle").setAttribute("aria-expanded", open ? "true" : "false");
    $("drawer-body").hidden = !open;
  }

  /* ---------- wiring ---------- */
  function wire() {
    PROFILES.forEach(function (p) {
      $("t-" + p).addEventListener("click", function () {
        if (has(p)) state.profiles = state.profiles.filter(function (x) { return x !== p; });
        else {
          state.profiles.push(p);
          if (LANGS.indexOf(p) >= 0) state.profiles = state.profiles.filter(function (x) { return x === p || LANGS.indexOf(x) < 0; });
        }
        savePrefs(); syncPickerUI(); update({ announce: true });
      });
    });
    document.querySelectorAll('input[name="blindmode"]').forEach(function (r) {
      r.addEventListener("change", function () { if (r.checked) { state.blindMode = r.value; savePrefs(); update({ announce: true }); } });
    });
    $("c-hold").addEventListener("change", function () { state.hold = this.checked; savePrefs(); updateHoldLoop(); });
    $("c-captions").addEventListener("change", function () { state.showCaptions = this.checked; savePrefs(); applyTrackModes(); });
    $("c-desctext").addEventListener("change", function () { state.descText = this.checked; savePrefs(); applyTrackModes(); });
    ["capsize", "capbg", "cappos"].forEach(function (name) {
      document.querySelectorAll('input[name="' + name + '"]').forEach(function (r) {
        r.addEventListener("change", function () {
          if (!r.checked) return;
          if (name === "capsize") state.cap.size = r.value;
          if (name === "capbg") state.cap.bg = r.value;
          if (name === "cappos") state.cap.pos = r.value;
          savePrefs(); applyCaptionClasses(); applyCuePosition();
        });
      });
    });
    document.querySelectorAll('input[name="filter"]').forEach(function (r) {
      r.addEventListener("change", function () { if (r.checked) { state.filter = r.value; renderDrawer(); } });
    });
    $("drawer-toggle").addEventListener("click", function () {
      setDrawer(this.getAttribute("aria-expanded") !== "true");
    });
    $("b-continue").addEventListener("click", function () { continuePlay(true); });
    video.addEventListener("play", function () { hideHold(); updateHoldLoop(); });
    video.addEventListener("pause", stopLoop);
    video.addEventListener("seeking", function () {
      var t = video.currentTime;
      var tr = holdEnabled() ? easyTrack() : null;
      if (tr && tr.cues) {
        for (var i = 0; i < tr.cues.length; i++) if (tr.cues[i].endTime > t + 0.2) delete hold.held[tr.cues[i].id];
      }
      if (!video.paused) hideHold();
    });
    video.addEventListener("error", function () {
      announce("This browser could not play the video file for: " + AC.versionName(current.key, data.index) + ".");
    });
    $("b-share").addEventListener("click", share);
    $("b-keys").addEventListener("click", function () { openKeys(this); });
    $("b-keys-close").addEventListener("click", closeKeys);
    $("keys-dialog").addEventListener("close", function () {
      if (keysOpener && document.body.contains(keysOpener) && keysOpener.focus) keysOpener.focus();
      keysOpener = null;
    });
    $("c-keys").addEventListener("change", function () { state.keys = this.checked; savePrefs(); });
    document.addEventListener("keydown", onKey);
    $("project-select").addEventListener("change", function () {
      var u = new URL(window.location.href);
      u.searchParams.set("p", this.value);
      window.location.href = u.toString();
    });
  }

  /* ---------- share this view ---------- */
  function shareUrl() {
    var u = new URL(window.location.href);
    u.hash = "";
    u.search = "";
    u.pathname = u.pathname.replace(/[^/]*$/, "watch.html");
    var parts = state.profiles.map(function (p) { return p === "blind" && state.blindMode === "extended" ? "extended" : p; });
    if (judge) parts.unshift("judge");
    if (parts.length) u.searchParams.set("audience", parts.join(","));
    if (data.project && (data.catalog.length > 1 || AC.params().get("p"))) u.searchParams.set("p", data.project.sha12);
    return u.toString().replace(/%2C/gi, ",");
  }
  function share() {
    var url = shareUrl();
    var who = state.profiles.map(function (p) { return $("t-" + p).querySelector(".t").textContent; });
    var what = who.length ? "It opens this page for: " + who.join(", ") + "." : "Nobody is picked, so it opens the picker.";
    var shown = function (msg) {
      $("share-url").value = url;
      $("share-out").hidden = false;
      say($("share-status"), msg);
    };
    var done = function () { $("share-out").hidden = true; say($("share-status"), "Link copied. " + what); };
    var fail = function () { shown("Could not copy by itself. The link is in the box below; select it and copy. " + what); $("share-url").select(); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done, fail);
    else fail();
  }
  function say(node, msg) {
    node.textContent = "";
    window.setTimeout(function () { node.textContent = msg; }, 30);
  }

  /* ---------- keyboard shortcuts (WCAG 2.1.4: they can be turned off) ---------- */
  var keysOpener = null;
  function openKeys(opener) {
    var d = $("keys-dialog");
    if (d.open) return;
    keysOpener = opener || document.activeElement;
    $("c-keys").checked = state.keys;
    if (typeof d.showModal === "function") d.showModal(); else d.setAttribute("open", "");
    $("b-keys-close").focus();
  }
  function closeKeys() {
    var d = $("keys-dialog");
    if (typeof d.close === "function") d.close(); else d.removeAttribute("open");
  }
  function typing(t) {
    if (!t || !t.tagName) return false;
    var tag = t.tagName.toLowerCase();
    if (tag === "textarea" || tag === "select" || t.isContentEditable) return true;
    if (tag === "input") return ["checkbox", "radio", "button", "submit"].indexOf((t.type || "").toLowerCase()) < 0;
    return false;
  }
  function onKey(e) {
    if (!state.keys || e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented) return;
    if ($("keys-dialog").open || typing(e.target)) return;
    var k = e.key;
    var t = video.currentTime || 0;
    if (k === "?") { e.preventDefault(); openKeys(document.activeElement); return; }
    if (k === "k" || k === "K") {
      e.preventDefault();
      if (video.paused) { var p = video.play(); if (p && p.catch) p.catch(function () {}); announce("Playing."); }
      else { video.pause(); announce("Paused."); }
    } else if (k === "j" || k === "J") {
      e.preventDefault(); try { video.currentTime = Math.max(0, t - 5); } catch (x) { /* not seekable */ }
      announce("Back to " + AC.fmtTime(video.currentTime * 1000) + ".");
    } else if (k === "l" || k === "L") {
      e.preventDefault(); try { video.currentTime = Math.min(video.duration || t + 5, t + 5); } catch (x) { /* not seekable */ }
      announce("Forward to " + AC.fmtTime(video.currentTime * 1000) + ".");
    } else if (k === "c" || k === "C") {
      e.preventDefault(); $("c-captions").click(); announce(state.showCaptions ? "Captions on." : "Captions off.");
    } else if (k === "d" || k === "D") {
      e.preventDefault(); $("c-desctext").click(); announce(state.descText ? "Description text on." : "Description text off.");
    } else if (/^[1-8]$/.test(k)) {
      var b = $("t-" + PROFILES[Number(k) - 1]);
      if (b && !b.disabled) { e.preventDefault(); b.click(); }
    }
  }

  function showError(msg) {
    var e = $("load-error");
    e.textContent = msg;
    e.hidden = false;
  }

  function init() {
    AC.renderFooter($("footer"));
    loadPrefs();
    readAudienceParam();
    if (judge) { $("judge-banner").hidden = false; setDrawer(true); }
    applyCaptionClasses();
    wire();
    syncPickerUI();
    AC.loadProject().then(function (res) {
      data.index = res.index; data.base = res.base; data.project = res.project; data.catalog = res.catalog;
      if (!data.index.versions || !Object.keys(data.index.versions).length) throw new Error("This video has no versions yet.");
      $("video-h").textContent = "Video: " + (data.index.title || data.project.title || data.project.sha12);
      $("video-credit").textContent = data.index.credit ? "Source: " + data.index.credit : "";
      $("video-credit").hidden = !data.index.credit;
      AC.renderDisclosure($("disclosure"), data.index);
      $("report-link").setAttribute("href", data.base + "report.json");
      if (data.catalog.length > 1) {
        var sel = $("project-select");
        data.catalog.forEach(function (p) {
          sel.appendChild(el("option", { value: p.sha12, selected: p.sha12 === data.project.sha12, text: (p.title || p.sha12) + (p.human_reviewed ? "" : " (unreviewed draft)") }));
        });
        $("project-pick").hidden = false;
      }
      renderAvailability();
      syncPickerUI();
      AC.fetchOptionalJSON(data.base + "analysis.json").then(function (an) {
        data.noSpeech = !!(an && Array.isArray(an.speech) && !an.speech.length);
        if (data.noSpeech) renderAvailability();
      }, function () { /* the notes keep their plain "not yet" */ });
      return AC.fetchJSON(data.base + "decisions.json").then(function (d) { data.decisions = d; }, function (err) {
        data.decisionsError = err.message;
      });
    }).then(function () {
      return update({ announce: true });
    }).catch(function (err) {
      showError("Could not load the video. " + (err && err.message ? err.message : ""));
    });
  }

  init();
})();
