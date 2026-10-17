/* "Try your own caption" (proof page): POST <api_base>/api/try?version=easy|hi|it, one request per version, all at
   once. Shows only what the live endpoint returned: Gemma's first answer, the checks that stopped it, and what
   would be published, or that the line would go to a person. Nothing is invented on this side. */
(function () {
  "use strict";
  var AC = window.AC, el = AC.el;
  var $ = function (id) { return document.getElementById(id); };
  var TIMEOUT_MS = 130000;  // the function may run up to 120 s (site/vercel.json)
  var VERSIONS = [
    { key: "easy", title: "Easy-read", lang: "en" },
    { key: "hi", title: "हिन्दी", lang: "hi" },
    { key: "it", title: "Italiano", lang: "it" }
  ];
  var RULES = {
    ER001: "too fast to read", ER002: "a sentence is too long", ER004: "a number changed", ER005: "a \"not\" was lost or added",
    ER006: "a name or term was lost", ER007: "an abbreviation", ER010: "too many characters on a line",
    CC001: "too fast to read", CC002: "too many characters on a line", CC003: "too many lines", CC004: "on screen too briefly or too long",
    CC007: "the lines came back out of order", CC008: "not translated", CC009: "a number or name changed",
    AD016: "the wrong language", VERIFIER_CRASH: "a check could not run (fails closed)"
  };
  var api = null;

  function say(msg) { var s = $("try-status"); s.textContent = ""; window.setTimeout(function () { s.textContent = msg; }, 30); }
  function rules(list) { return list.map(function (r) { return (RULES[r] || "a check") + " (" + r + ")"; }).join(", "); }

  function card(v, body) {
    var box = el("section", { class: "try-card", "aria-labelledby": "try-h-" + v.key }, [
      el("h3", { id: "try-h-" + v.key, lang: v.lang === "en" ? null : v.lang, text: v.title })
    ]);
    body.forEach(function (n) { box.appendChild(n); });
    return box;
  }

  function cueNodes(v, cues) {
    return cues.map(function (c) {
      var lines = [el("p", null, [el("strong", { text: "Gemma wrote: " }), el("span", { lang: v.lang, text: c.gemma_wrote })])];
      if (c.blocked_by && c.blocked_by.length) {
        lines.push(el("p", { class: "try-bad", text: "Stopped by our checks: " + rules(c.blocked_by) + "." }));
        if (c.published) lines.push(el("p", null, [el("strong", { text: "Gemma's repair, which passed: " }), el("span", { lang: v.lang, text: c.published })]));
        else lines.push(el("p", { class: "try-bad", text: "The repair did not pass either, so this line would go to a person. Nothing wrong is published." }));
      } else if (c.published) {
        lines.push(el("p", { class: "try-ok", text: "Passed every check on the first try." }));
      } else {
        lines.push(el("p", { class: "try-bad", text: "Held for a person to review." }));
      }
      return el("div", { class: "try-cue" }, lines);
    });
  }

  function run(ev) {
    ev.preventDefault();
    var text = $("try-text").value.trim();
    if (!api) return;
    $("b-try").disabled = true;
    var out = $("try-result");
    out.textContent = "";
    var slots = {};
    VERSIONS.forEach(function (v) {
      slots[v.key] = card(v, [el("p", { class: "muted", text: "Asking Gemma…" })]);
      out.appendChild(slots[v.key]);
    });
    say("Asking Gemma on AMD Token Factory for three versions. This can take a minute or two.");
    var done = 0, stopped = 0, failed = 0;
    Promise.all(VERSIONS.map(function (v) {
      var ctrl = typeof AbortController === "function" ? new AbortController() : null;
      var timer = ctrl ? window.setTimeout(function () { ctrl.abort(); }, TIMEOUT_MS) : null;
      return fetch(api + "/api/try?version=" + v.key, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: text }),
        signal: ctrl ? ctrl.signal : undefined
      }).then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (d) {
          if (!r.ok) throw new Error(d && d.detail ? d.detail : "HTTP " + r.status);
          return d;
        });
      }).then(function (d) {
        var cues = Array.isArray(d.cues) ? d.cues : [];
        cues.forEach(function (c) { if (c.blocked_by && c.blocked_by.length) stopped++; });
        var fresh = card(v, cueNodes(v, cues).concat([el("p", { class: "muted", text: "Served by " + (d.endpoint_label || "the live endpoint") + "." })]));
        out.replaceChild(fresh, slots[v.key]);
        slots[v.key] = fresh;
      }).catch(function (err) {
        failed++;
        var fresh = card(v, [el("p", { class: "error", text: "No answer (" + (err && err.message ? err.message : "error") + "). Nothing was made for this version." })]);
        out.replaceChild(fresh, slots[v.key]);
        slots[v.key] = fresh;
      }).then(function () {
        if (timer) window.clearTimeout(timer);
        done++;
      });
    })).then(function () {
      $("b-try").disabled = false;
      say(failed === VERSIONS.length ? "The live endpoint did not answer. Nothing was made."
        : "Done. Our checks stopped " + stopped + " of Gemma's answers" + (failed ? "; " + failed + " version(s) got no answer" : "") + ". The results are below.");
    });
  }

  AC.fetchOptionalJSON("data/proof_config.json").then(function (cfg) {
    if (cfg && typeof cfg.api_base === "string" && cfg.api_base) {
      api = cfg.api_base.replace(/\/+$/, "");
      $("b-try").disabled = false;
    } else {
      $("try-help").textContent = "The live endpoint is not connected here, so this is off.";
    }
  }).catch(function () { $("try-help").textContent = "The live endpoint is not connected here, so this is off."; });
  $("try-form").addEventListener("submit", run);
})();
