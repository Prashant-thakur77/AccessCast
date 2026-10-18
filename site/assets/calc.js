/* Cost estimator (results page): minutes of video × per-minute prices. Every per-minute figure is a registered claim
   in data/claims.json (our measured Gemma cost, cited list prices); a missing claim leaves its row out, never a
   guess. Ours is labelled an estimate and excludes a person's review time. */
(function () {
  "use strict";
  var AC = window.AC, el = AC.el;
  var $ = function (id) { return document.getElementById(id); };
  var ROWS = [
    { id: "cost.usd_per_min", what: "AccessCast: Gemma work for the five versions we measured (estimate)", ours: true },
    { id: "cited.price.3play_launch", what: "3Play Media: AI script and voice, English only (list price)" },
    { id: "cited.price.umich_machine_std", what: "University of Michigan: machine description (list price)" },
    { id: "cited.price.3play_refine_std", what: "3Play Media: AI description with a human spot check (list price)" },
    { id: "cited.price.umich_human_low", what: "University of Michigan: human description, low end (list price)" },
    { id: "cited.price.3play_voice_artist_std", what: "3Play Media: voice artist (list price)" }
  ];
  var prices = [];

  function money(x) {
    if (x < 1) return "$" + x.toFixed(x < 0.1 ? 4 : 2);
    return x.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: x < 100 ? 2 : 0 });
  }

  function compute() {
    var raw = $("calc-min").value.trim();
    var n = Math.floor(Number(raw));
    var rows = $("calc-rows");
    rows.textContent = "";
    if (!raw || !isFinite(n) || n < 1 || n > 1000000) {
      $("calc-out").textContent = "Type a whole number of minutes from 1 to 1,000,000.";
      return;
    }
    prices.forEach(function (p) {
      rows.appendChild(el("tr", { class: p.ours ? "ours" : null }, [
        el("td", { text: p.what }), el("td", { text: p.display }), el("td", { text: money(p.value * n) })
      ]));
    });
    var ours = prices.filter(function (p) { return p.ours; })[0];
    $("calc-out").textContent = ours
      ? "For " + n.toLocaleString("en-US") + " minutes, the Gemma work comes to about " + money(ours.value * n) + " (an estimate), plus a person's review time."
      : "Our measured cost is not available here, so only list prices are shown.";
  }

  AC.fetchOptionalJSON("data/claims.json").then(function (data) {
    var claims = (data && data.claims) || {};
    prices = ROWS.map(function (r) {
      var c = claims[r.id];
      var display = c && (Array.isArray(c.display) ? c.display[0] : c.display);
      var value = display ? parseFloat(String(display).replace(/[^0-9.]/g, "")) : NaN;
      return isFinite(value) ? { id: r.id, what: r.what, ours: !!r.ours, display: display, value: value } : null;
    }).filter(Boolean);
    compute();
  }).catch(function () { $("calc-out").textContent = "The prices could not be loaded."; });
  var timer = null;  // wait for the visitor to stop typing, so a screen reader hears one total, not one per key
  $("calc-min").addEventListener("input", function () { window.clearTimeout(timer); timer = window.setTimeout(compute, 400); });
  $("calc-form").addEventListener("submit", function (e) { e.preventDefault(); compute(); });
})();
