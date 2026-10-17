/* AccessCast shared helpers (player, five-ways, proof). Plain browser JS, no dependencies.
 * Everything shown here comes from the exported data files; this file holds no results. */
(function () {
  "use strict";

  var REPO = "https://github.com/Prashant-thakur77/AccessCast";

  function el(tag, attrs, children) {
    var n = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        var v = attrs[k];
        if (v === null || v === undefined || v === false) return;
        if (k === "text") n.textContent = v;
        else if (k === "class") n.className = v;
        else if (k.slice(0, 2) === "on" && typeof v === "function") n.addEventListener(k.slice(2), v);
        else n.setAttribute(k, v === true ? "" : String(v));
      });
    }
    (children || []).forEach(function (c) {
      if (c === null || c === undefined || c === false) return;
      n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return n;
  }

  function fetchJSON(url) {
    return fetch(url, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error(url + ": HTTP " + r.status);
      return r.json();
    });
  }

  /* Returns null when the file is missing; throws on other errors (fail closed). */
  function fetchOptionalJSON(url) {
    return fetch(url, { cache: "no-cache" }).then(function (r) {
      if (r.status === 404) return null;
      if (!r.ok) throw new Error(url + ": HTTP " + r.status);
      return r.json();
    });
  }

  function params() { return new URLSearchParams(window.location.search); }

  var store = {
    get: function (key) {
      try {
        var raw = window.localStorage.getItem(key);
        return raw ? JSON.parse(raw) : null;
      } catch (e) { return null; }
    },
    set: function (key, value) {
      try { window.localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* storage blocked: fine */ }
    }
  };

  /* Load catalog + chosen project. */
  function loadProject() {
    return fetchJSON("data/catalog.json").then(function (cat) {
      var projects = (cat && cat.projects) || [];
      if (!projects.length) throw new Error("There are no videos on this site yet.");
      var want = params().get("p");
      var chosen = projects[0];
      if (want) {
        chosen = projects.filter(function (p) { return p.sha12 === want; })[0];
        if (!chosen) throw new Error("No video with the id \"" + want + "\" on this site.");
      }
      var base = "p/" + chosen.sha12 + "/";
      return fetchJSON(base + "index.json").then(function (idx) {
        return { catalog: projects, project: chosen, index: idx, base: base };
      });
    });
  }

  var VERSION_NAMES = {
    "blind.en": "English, with audio description",
    "blind_ext.en": "English, with extended audio description",
    "deaf.en": "English, with captions and sound labels",
    "easy.en": "English, with easy-read captions",
    "hi": "Hindi version",
    "it": "Italian version",
    "es": "Spanish version",
    "fr": "French version",
    "pt": "Portuguese version",
    "blind.hi": "Hindi version, with audio description",
    "blind.it": "Italian version, with audio description"
  };
  function versionName(key, idx) {
    if (VERSION_NAMES[key]) return VERSION_NAMES[key];
    var v = idx && idx.versions && idx.versions[key];
    return (v && v.label) || key;
  }

  function dateOnly(s) {
    if (!s) return "";
    var d = new Date(s);
    if (isNaN(d.getTime())) return String(s);
    return d.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
  }

  /* Disclosure: always visible. Red banner for drafts. */
  function renderDisclosure(container, idx) {
    container.textContent = "";
    if (idx.human_reviewed) {
      container.appendChild(el("p", { text: "Description voiced by synthetic speech. Reviewed by a person on " + dateOnly(idx.reviewed_at) + "." }));
    } else {
      container.appendChild(el("p", { class: "banner banner-danger", text: "UNREVIEWED DRAFT — made by machine, not yet approved by a person." }));
      container.appendChild(el("p", { text: "Description voiced by synthetic speech." }));
    }
    if (idx.synthetic_test_data) {
      container.appendChild(el("p", { class: "fixture", text: "Demo fixture: canned model outputs, not real model results." }));
    }
    if ((idx.tts_engines || []).indexOf("chatterbox-multilingual") !== -1) {
      container.appendChild(el("p", { text: "Some voices carry an inaudible watermark added by the speech engine (Chatterbox)." }));
    }
  }

  /* Shared footer: stacked wordmark, link columns, and a disclosure line read from the catalog. */
  function renderFooter(container) {
    container.textContent = "";
    var col = function (title, links) {
      return el("div", { class: "foot-col" }, [
        el("h2", { text: title }),
        el("ul", null, links.map(function (l) { return el("li", null, [el("a", { href: l[1], text: l[0] })]); }))
      ]);
    };
    var mark = el("p", { class: "wordmark" }, [
      el("span", { "aria-hidden": "true" }, [el("span", { text: "Access" }), el("span", null, ["Cast", el("span", { class: "sound-dot" })])]),
      el("span", { class: "visually-hidden", text: "AccessCast" })
    ]);
    container.appendChild(el("div", { class: "foot-grid" }, [
      mark,
      col("Pages", [["Home", "index.html"], ["Watch", "watch.html"], ["Five ways", "five-ways.html"], ["How it works", "how.html"], ["Proof", "proof.html"]]),
      col("Project", [["Source code", REPO], ["Notes for judges", REPO + "/blob/main/JUDGES.md"], ["Licence", REPO + "/blob/main/LICENSE"],
        ["Models, voices and fonts", REPO + "/blob/main/MODEL_LICENSES.md"]])
    ]));
    var note = el("p", { text: "Description voices are synthetic speech." });
    container.appendChild(el("div", { class: "foot-note" }, [
      el("p", { text: "Gemma 4 on AMD Token Factory. Made for AMD Developer Hackathon ACT III." }),
      note
    ]));
    fetchOptionalJSON("data/catalog.json").then(function (cat) {
      var ps = (cat && cat.projects) || [];
      var bits = ["Description voices are synthetic speech."];
      if (ps.some(function (p) { return p.synthetic_test_data; })) bits.push("The demo video here is a test fixture with canned model outputs.");
      if (ps.some(function (p) { return !p.human_reviewed; })) bits.push("Versions no person has approved yet are labelled as drafts.");
      note.textContent = bits.join(" ");
    }).catch(function () { /* the line above still stands */ });
  }

  function fmtTime(ms, precise) {
    if (ms === null || ms === undefined || isNaN(ms)) return "?";
    var neg = ms < 0; ms = Math.abs(ms);
    var totalS = ms / 1000;
    var m = Math.floor(totalS / 60);
    var s = totalS - m * 60;
    var sStr = precise ? s.toFixed(1) : String(Math.floor(s));
    if ((precise ? s < 10 : Math.floor(s) < 10)) sStr = "0" + sStr;
    return (neg ? "-" : "") + m + ":" + sStr;
  }

  function cueText(cue) {
    var t = cue && cue.text ? cue.text : "";
    return t.replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim();
  }

  function wordCount(text) {
    var t = (text || "").trim();
    return t ? t.split(/\s+/).length : 0;
  }

  /* Which track a version shows for a given role: "sdh" | "easy" | "subs" | "desc". */
  function findTrack(version, role) {
    var tracks = (version && version.tracks) || [];
    var prefix = { sdh: "sdh.", easy: "easy.", subs: "subs.", desc: "desc." }[role];
    var byName = tracks.filter(function (t) { return t.name && t.name.indexOf(prefix) === 0; })[0];
    if (byName) return byName;
    if (role === "desc") return tracks.filter(function (t) { return t.kind === "descriptions"; })[0] || null;
    return null;
  }

  /* Replace the <track> children of a video. Returns {name: HTMLTrackElement}. */
  function setTracks(video, base, version) {
    Array.prototype.slice.call(video.querySelectorAll("track")).forEach(function (t) { t.remove(); });
    var out = {};
    ((version && version.tracks) || []).forEach(function (t) {
      var tr = el("track", { kind: t.kind, srclang: t.srclang, label: t.label, src: base + t.file, "data-name": t.name });
      video.appendChild(tr);
      tr.track.mode = "hidden";
      out[t.name] = tr;
    });
    return out;
  }

  /* source_to_output mapping (AudioSight timeline rows). */
  function sourceToOutput(rows, srcMs) {
    if (!rows || !rows.length) return srcMs;
    var ins = rows.filter(function (r) { return r.type === "insertion"; });
    for (var i = 0; i < ins.length; i++) {
      if (Math.abs(ins[i].source_anchor_ms - srcMs) < 50) return ins[i].output_start_ms;
    }
    var src = rows.filter(function (r) { return r.type === "source"; });
    for (var j = 0; j < src.length; j++) {
      var r = src[j];
      if (srcMs >= r.source_start_ms && srcMs < r.source_end_ms) return r.output_start_ms + (srcMs - r.source_start_ms);
    }
    if (src.length && srcMs >= src[src.length - 1].source_end_ms) return src[src.length - 1].output_end_ms;
    return srcMs;
  }
  function outputToSource(rows, outMs) {
    if (!rows || !rows.length) return outMs;
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      if (outMs >= r.output_start_ms && outMs < r.output_end_ms) {
        if (r.type === "insertion") return r.source_anchor_ms;
        return r.source_start_ms + (outMs - r.output_start_ms);
      }
    }
    var src = rows.filter(function (x) { return x.type === "source"; });
    if (src.length && outMs >= src[src.length - 1].output_end_ms) return src[src.length - 1].source_end_ms;
    return outMs;
  }
  function insertionStart(rows, narrationId) {
    var r = (rows || []).filter(function (x) { return x.type === "insertion" && x.narration_id === narrationId; })[0];
    return r ? r.output_start_ms : null;
  }

  window.AC = {
    REPO: REPO, el: el, fetchJSON: fetchJSON, fetchOptionalJSON: fetchOptionalJSON, params: params, store: store,
    loadProject: loadProject, versionName: versionName, dateOnly: dateOnly, renderDisclosure: renderDisclosure,
    renderFooter: renderFooter, fmtTime: fmtTime, cueText: cueText, wordCount: wordCount, findTrack: findTrack,
    setTracks: setTracks, sourceToOutput: sourceToOutput, outputToSource: outputToSource, insertionStart: insertionStart
  };
})();
