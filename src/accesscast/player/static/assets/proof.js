/* Proof page (PLAN §13.5). Never shows a result that did not come from the live endpoint or a recorded file.
 *
 * Expected shape, for both the live response (POST <api_base>/api/attack) and data/e11_last_run.json:
 * {
 *   "recorded_at": ISO date (or "finished_at"),
 *   "evidence_file": "evidence/e11_....json",
 *   "case_id": str, "endpoint": str,
 *   "tries": [{"try": int, "endpoint": str, "seed": int, "temperature": number,
 *              "text": str, "failed": bool, "blocked_by": [rule ids] | str | null, "reached_viewer": bool}]
 * }
 * The tally is counted here from "tries"; if a field is missing, the page shows the raw JSON instead of guessing.
 */
(function () {
  "use strict";
  var AC = window.AC, el = AC.el;
  var $ = function (id) { return document.getElementById(id); };
  var LIVE_TIMEOUT_MS = 130000;  // the function may run up to 120 s (site/vercel.json)
  var LIVE_TRIES = 5;  // five live tries per press, in parallel on the server: about 15–30 seconds
  var ENDPOINTS = { tokenfactory: "Gemma 4 31B on AMD Token Factory" };
  var RULES = { ER004: "the number check (ER004)", ER005: "the negation check (ER005)", AD009: "the invented-name check (AD009)",
    AD011: "the sound-word check (AD011)", AD018: "the instruction-on-screen check (AD018)", VERIFIER_CRASH: "a check that could not run (fails closed)" };

  function announce(msg) {
    var s = $("status");
    s.textContent = "";
    window.setTimeout(function () { s.textContent = msg; }, 30);
  }

  function blockedList(t) {
    var b = t.blocked_by;
    if (Array.isArray(b)) return b.filter(Boolean);
    return b ? [String(b)] : [];
  }

  function wellFormed(run) {
    return run && Array.isArray(run.tries) && run.tries.length > 0 && run.tries.every(function (t) {
      return t && typeof t.text === "string" && typeof t.failed === "boolean" && typeof t.reached_viewer === "boolean" && "blocked_by" in t;
    });
  }

  function renderRun(container, run, opts) {
    container.textContent = "";
    var when = run && (run.recorded_at || run.finished_at);
    if (opts.recorded) {
      container.appendChild(el("p", null, [
        "Recorded on " + (when ? AC.dateOnly(when) : "an unknown date") + ". Evidence file: ",
        run && run.evidence_file
          ? el("a", { href: AC.REPO + "/blob/main/" + run.evidence_file, text: run.evidence_file })
          : el("span", { text: "not named in the record" }),
        "."
      ]));
    }
    if (!wellFormed(run)) {
      container.appendChild(el("p", { text: "This run is not in the format this page expects, so here is the raw data." }));
      container.appendChild(el("pre", { class: "raw", text: JSON.stringify(run, null, 2) }));
      return;
    }
    var n = run.tries.length;
    var failed = run.tries.filter(function (t) { return t.failed; }).length;
    var blocked = run.tries.filter(function (t) { return blockedList(t).length > 0; }).length;
    var reached = run.tries.filter(function (t) { return t.reached_viewer; }).length;
    container.appendChild(el("p", { class: "now",
      text: "Gemma failed " + failed + " of " + n + ". Our checks blocked " + blocked + " of " + n + ". Reached the viewer: " + reached + "." }));
    if (run.case_text) container.appendChild(el("p", null, [el("strong", { text: "The test: " }), run.case_text]));
    if (run.endpoint) container.appendChild(el("p", { text: "Endpoint: " + (run.endpoint_label || ENDPOINTS[run.endpoint] || run.endpoint) + "." }));
    var ol = el("ol", { class: "tries" });
    run.tries.forEach(function (t) {
      var rules = blockedList(t);
      ol.appendChild(el("li", null, [
        el("p", null, [el("strong", { text: "Gemma wrote: " }), t.text]),
        el("p", { text: (t.failed ? "This answer broke the rule. " : "This answer was fine. ") +
          (rules.length ? "Blocked by: " + rules.map(function (r) { return RULES[r] || r; }).join(", ") + ". " : "Not blocked. ") +
          (t.reached_viewer ? "It reached the viewer." : "It did not reach the viewer.") }),
        t.final && t.final !== t.text && !t.reached_viewer
          ? el("p", null, [el("strong", { text: "After the check, Gemma's repair: " }), t.final]) : null,
        t.endpoint ? el("p", { class: "muted", text: "Served by: " + (ENDPOINTS[t.endpoint] || t.endpoint) + "." }) : null
      ]));
    });
    container.appendChild(ol);
  }

  function runLive() {
    var btn = $("b-attack");
    btn.disabled = true;
    announce("Running. This asks Gemma several times, so it can take a while.");
    var ctrl = typeof AbortController === "function" ? new AbortController() : null;
    var timer = ctrl ? window.setTimeout(function () { ctrl.abort(); }, LIVE_TIMEOUT_MS) : null;
    fetch(window.ACCESSCAST_API_BASE.replace(/\/+$/, "") + "/api/attack?n=" + LIVE_TRIES, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
      signal: ctrl ? ctrl.signal : undefined
    }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (run) {
      renderRun($("live-result"), run, { recorded: false });
      announce("Done. The results are below.");
    }).catch(function (err) {
      $("live-result").textContent = "";
      $("live-result").appendChild(el("p", { class: "error", text: "The live endpoint did not answer (" + (err && err.message ? err.message : "error") + "). Nothing was run. See the last recorded run below." }));
      announce("The live endpoint did not answer. Nothing was run.");
    }).then(function () {
      if (timer) window.clearTimeout(timer);
      btn.disabled = false;
    });
  }

  function init() {
    AC.renderFooter($("footer"));
    var btn = $("b-attack");
    AC.fetchOptionalJSON("data/proof_config.json").then(function (cfg) {
      if (cfg && typeof cfg.api_base === "string" && cfg.api_base) {
        window.ACCESSCAST_API_BASE = cfg.api_base;
        btn.disabled = false;
        $("live-state").textContent = "The live endpoint is connected. Each press asks Gemma 4 31B on AMD Token Factory five times, live; it takes about half a minute.";
      } else {
        btn.disabled = true;
        $("live-state").textContent = "The live endpoint is not connected, so the button is off. The last recorded run is below.";
      }
    }).catch(function () {
      btn.disabled = true;
      $("live-state").textContent = "The live endpoint is not connected, so the button is off. The last recorded run is below.";
    });
    btn.addEventListener("click", runLive);

    AC.fetchOptionalJSON("data/e11_last_run.json").then(function (run) {
      if (!run) { $("last-run").textContent = ""; $("last-run").appendChild(el("p", { text: "No recorded run yet." })); return; }
      renderRun($("last-run"), run, { recorded: true });
    }).catch(function (err) {
      $("last-run").textContent = "";
      $("last-run").appendChild(el("p", { class: "error", text: "Could not read the recorded run (" + (err && err.message ? err.message : "error") + ")." }));
    });
  }

  init();
})();
