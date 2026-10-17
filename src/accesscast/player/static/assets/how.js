/* "How it works": one clip, step by step, drawn only from the project's exported files (analysis.json,
   decisions.json, index.json, the extended timeline). Nothing here is typed by hand except the plain-words
   explanation of each rule. */
(function () {
  "use strict";
  var AC = window.AC, el = AC.el;
  var $ = function (id) { return document.getElementById(id); };

  // Plain words for the rules a line can break (docs/rules.md has the full table and sources).
  var RULE_WORDS = {
    AD001: "It is too long for the pause: the voice would run into speech.",
    AD002: "It starts in the middle of a spoken word.",
    AD004: "It would be spoken over dialogue.",
    AD005: "It is placed too far from the moment it describes.",
    AD006: "It overlaps another description line.",
    AD007: "It has more words than the time allows.",
    AD008: "It repeats what is already said aloud.",
    AD009: "It uses a name that nobody on screen gave.",
    AD010: "It claims something the frames do not show, like a motive or a job.",
    AD011: "It describes a sound or speech. A blind viewer already hears that, so it wastes the pause.",
    AD012: "It mentions things that are not in Gemma's own list of what is visible.",
    AD016: "It is in the wrong language.",
    AD018: "It repeats an instruction written on screen as if it were an instruction.",
    AD019: "It is empty or filler."
  };

  function secs(ms) { return (ms / 1000).toFixed(1) + " s"; }

  function timeline(container, an, opts) {
    var dur = an.duration_ms || 1;
    var bar = el("div", { class: "tl", role: "img", "aria-label": opts.label });
    (an.speech || []).forEach(function (s) {
      bar.appendChild(el("span", { class: "tl-speech", style: "left:" + (100 * s[0] / dur) + "%;width:" + Math.max(0.2, 100 * (s[1] - s[0]) / dur) + "%" }));
    });
    if (opts.gaps) {
      (an.gaps || []).forEach(function (g) {
        var w = 100 * (g[1] - g[0]) / dur;
        var gap = el("span", { class: "tl-gap", style: "left:" + (100 * g[0] / dur) + "%;width:" + Math.max(0.4, w) + "%" });
        if (w > 3) gap.appendChild(el("span", { class: "tl-len", text: secs(g[1] - g[0]) }));
        bar.appendChild(gap);
      });
    }
    (opts.marks || []).forEach(function (m) {
      bar.appendChild(el("span", { class: "tl-mark " + (m.cls || ""), style: "left:" + (100 * m.ms / dur) + "%" }, [
        el("span", { class: "tl-mark-label", text: m.text })
      ]));
    });
    var axis = el("div", { class: "tl-axis", "aria-hidden": "true" }, [
      el("span", { text: AC.fmtTime(0) }), el("span", { text: AC.fmtTime(dur) })
    ]);
    var key = el("p", { class: "tl-key" }, opts.gaps
      ? [el("span", { class: "k k-speech", "aria-hidden": "true" }), "Speech ", el("span", { class: "k k-gap", "aria-hidden": "true" }), "Pause long enough for a description"]
      : [el("span", { class: "k k-speech", "aria-hidden": "true" }), "Speech (each dark stripe is someone talking)"]);
    container.textContent = "";
    container.appendChild(bar);
    container.appendChild(axis);
    container.appendChild(key);
  }

  function pickLine(items) {
    var want = AC.params().get("line");
    var ad = items.filter(function (x) { return x.kind === "ad"; });
    if (want) {
      var w = ad.filter(function (x) { return x.id === want; })[0];
      if (w) return w;
    }
    var fixed = ad.filter(function (x) { return (x.repairs || []).length > 1 && (x.rules_fired || []).length && x.final_text; });
    return fixed[0] || ad[0] || null;
  }

  function render(res, an, dec, rows) {
    var idx = res.index, base = res.base;
    var items = dec.items || [];
    var line = pickLine(items);
    $("clip").textContent = "Clip: " + (idx.title || res.project.sha12) + (idx.credit ? ". " + idx.credit + "." : "");
    AC.renderDisclosure($("disclosure"), idx);

    // 1. Listen
    var dur = an.duration_ms || 0;
    var talk = (an.speech || []).reduce(function (a, s) { return a + (s[1] - s[0]); }, 0);
    timeline($("tl-listen"), an, {
      label: "Timeline of the clip, " + AC.fmtTime(dur) + " long, with speech marked: " + Math.round(100 * talk / Math.max(1, dur)) + " percent of it is speech."
    });
    var caps = items.filter(function (x) { return x.kind === "sdh" && x.final_text && x.final_text.charAt(0) !== "["; })
      .sort(function (a, b) { return a.slot.start_ms - b.slot.start_ms; }).slice(0, 3);
    $("transcript").textContent = "";
    caps.forEach(function (c) {
      $("transcript").appendChild(el("li", null, [
        el("span", { class: "t-time", text: AC.fmtTime(c.slot.start_ms) }), " ",
        el("span", { text: c.final_text.replace(/\n/g, " ") })
      ]));
    });

    // 2. Pauses
    var gaps = an.gaps || [];
    var gapTotal = gaps.reduce(function (a, g) { return a + (g[1] - g[0]); }, 0);
    var marks = line ? [{ ms: line.anchor_ms, text: "The line below", cls: "tl-mark-line" }] : [];
    timeline($("tl-pauses"), an, {
      gaps: true, marks: marks,
      label: "The same timeline with " + gaps.length + " pauses long enough for a description marked, " + secs(gapTotal) + " in total."
    });
    $("pauses-note").textContent = gaps.length + " pauses, " + secs(gapTotal) + " in all, in a clip of " + AC.fmtTime(dur) +
      (gapTotal < dur / 4 ? ". This clip is mostly talk, so most of its description will need the picture to hold." : ".");

    if (!line) { $("check").textContent = "This clip has no description lines."; return; }

    // 3. Look
    $("frames").textContent = "";
    (line.frames || []).slice(0, 4).forEach(function (f, i) {
      $("frames").appendChild(el("img", { src: base + f, alt: "Still frame " + (i + 1) + " that Gemma looked at", loading: "lazy" }));
    });
    $("facts").textContent = "";
    (line.facts || []).forEach(function (f) {
      $("facts").appendChild(el("li", null, [
        el("span", { class: "fid", text: f.fid }), " ", f.text,
        el("span", { class: "muted", text: " (frames " + (f.frames || []).map(function (n) { return n + 1; }).join(", ") + ")" })
      ]));
    });

    // 4. Write
    var first = (line.repairs && line.repairs[0] && line.repairs[0].text) || line.first_draft || "";
    $("draft").textContent = first;
    var b = line.budget || {};
    $("budget").textContent = line.extended
      ? "Budget: at most " + b.words_max + " words. There is no pause at " + AC.fmtTime(line.anchor_ms) + ", so this line will be read while the picture holds."
      : "Budget: at most " + b.words_max + " words, because the pause at " + AC.fmtTime(line.anchor_ms) + " lasts " + secs(line.slot.end_ms - line.slot.start_ms) + ".";

    // 5. Check
    var fired = (line.repairs && line.repairs[0] && line.repairs[0].rules) || line.rules_fired || [];
    var box = $("check");
    box.textContent = "";
    if (fired.length) {
      box.appendChild(el("p", { class: "check-verdict bad", text: "Stopped. The draft broke " + (fired.length === 1 ? "one rule:" : fired.length + " rules:") }));
      var ul = el("ul", { class: "check-list" });
      fired.forEach(function (r) {
        ul.appendChild(el("li", null, [el("span", { class: "rule-id", text: r }), " ", RULE_WORDS[r] || "A check failed (see docs/rules.md)."]));
      });
      box.appendChild(ul);
      box.appendChild(el("p", { class: "muted", text: "The draft is not used. Nothing a check stops reaches a viewer." }));
    } else {
      box.appendChild(el("p", { class: "check-verdict good", text: "Passed every rule on the first try." }));
    }

    // 6. Repair
    var ol = $("repairs");
    ol.textContent = "";
    (line.repairs || []).forEach(function (r, i) {
      var ok = !(r.rules || []).length;
      ol.appendChild(el("li", { class: ok ? "ok" : "bad" }, [
        el("span", { class: "rep-who", text: i === 0 ? "First draft" : "Gemma's repair" }),
        el("q", { text: r.text }),
        el("span", { class: "rep-verdict", text: ok ? "Passed every check" : "Stopped by " + r.rules.join(", ") })
      ]));
    });

    // 7. Fit
    var fit = $("fit");
    fit.textContent = "";
    var std = items.filter(function (x) { return x.kind === "ad" && !x.extended && x.tts && x.final_text && x.slot.end_ms > x.slot.start_ms; })[0];
    if (std) {
      var pause = std.slot.end_ms - std.slot.start_ms;
      var voice = std.tts.duration_ms + 300;  // 150 ms of silence each side (docs/rules.md, timing convention)
      fit.appendChild(el("div", { class: "fit-card" }, [
        el("p", { class: "fit-h", text: "In a pause at " + AC.fmtTime(std.anchor_ms) }),
        el("q", { text: std.final_text }),
        el("div", { class: "fit-bar", role: "img", "aria-label": "The voice takes " + secs(voice) + " of a " + secs(pause) + " pause." }, [
          el("span", { class: "fit-voice", style: "width:" + Math.min(100, 100 * voice / pause) + "%" })
        ]),
        el("p", { class: "muted", text: "Voice " + secs(voice) + " in a pause of " + secs(pause) + "." })
      ]));
    }
    if (line.extended && line.tts) {
      var ins = (rows || []).filter(function (r) { return r.type === "insertion" && r.narration_id === line.id; })[0];
      var hold = ins ? ins.output_end_ms - ins.output_start_ms : line.tts.duration_ms + 300;
      fit.appendChild(el("div", { class: "fit-card hold-card" }, [
        el("p", { class: "fit-h", text: "No pause at " + AC.fmtTime(line.anchor_ms) }),
        el("q", { text: line.final_text || first }),
        el("p", { class: "hold-badge", text: "The picture holds for " + secs(hold) + " while this is read, then the video carries on." })
      ]));
    }

    // 8. A person decides
    var st = line.status;
    $("person-note").textContent = idx.human_reviewed
      ? "A person approved every description line in this clip."
      : "This clip is a machine draft: no person has reviewed it yet" + (st === "auto_approved" ? ", so its lines were passed by the checks alone for this demo" : "") + ". Every version says so on screen.";

    // 9. Versions
    var outs = $("outs");
    outs.textContent = "";
    [["blind", "blind.en", "For someone who can't see the screen"], ["extended", "blind_ext.en", "The same, with the picture held where there is no pause"],
     ["deaf", "deaf.en", "For someone who can't hear"], ["easy", "easy.en", "For someone who wants simpler words"],
     ["hi", "hi", "हिन्दी"], ["it", "it", "Italiano"], ["es", "es", "Español"], ["fr", "fr", "Français"]].forEach(function (v) {
      if (!idx.versions[v[1]]) return;
      var a = el("a", { href: "watch.html?audience=" + v[0] + "&p=" + res.project.sha12, text: v[2] });
      if (v[1] === "hi") a.setAttribute("lang", "hi");
      if (["it", "es", "fr"].indexOf(v[1]) >= 0) a.setAttribute("lang", v[1]);
      outs.appendChild(el("li", null, [a]));
    });
  }

  function init() {
    AC.renderFooter($("footer"));
    AC.loadProject().then(function (res) {
      var v = res.index.versions["blind_ext.en"];
      var rowsUrl = v && v.source_to_output ? res.base + v.source_to_output : null;
      return Promise.all([
        fetch(res.base + "analysis.json").then(function (r) { if (!r.ok) throw new Error("analysis.json: HTTP " + r.status); return r.json(); }),
        fetch(res.base + "decisions.json").then(function (r) { if (!r.ok) throw new Error("decisions.json: HTTP " + r.status); return r.json(); }),
        rowsUrl ? fetch(rowsUrl).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }) : Promise.resolve(null)
      ]).then(function (all) {
        var rows = all[2] && all[2].rows ? all[2].rows : all[2];
        render(res, all[0], all[1], Array.isArray(rows) ? rows : []);
      });
    }).catch(function (e) {
      var box = $("load-error");
      box.hidden = false;
      box.textContent = "Could not load this clip: " + e.message;
    });
  }

  init();
})();
