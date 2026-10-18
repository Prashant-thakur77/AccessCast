/* "Describe a picture" (proof page): the visitor's picture, shrunk in the browser to at most 1024 px, is sent once to
   POST <api_base>/api/describe. Shows only what the live endpoint returned: the facts Gemma saw, its first line, the
   rules that stopped it, and what would be published, or that the line would go to a person. Nothing is invented
   on this side, and nothing is stored. */
(function () {
  "use strict";
  var AC = window.AC, el = AC.el;
  var $ = function (id) { return document.getElementById(id); };
  var TIMEOUT_MS = 130000;  // the function may run up to 120 s (site/vercel.json)
  var MAX_SIDE = 1024;      // matches DESCRIBE_MAX_BYTES on the server with room to spare
  var RULES = {
    AD001: "too long for the pause", AD004: "it would talk over speech", AD005: "not tied to what is on screen",
    AD007: "over the word budget", AD008: "it repeats the dialogue", AD009: "a name nobody said or showed",
    AD010: "a claim the picture does not support", AD011: "it describes a sound or speech",
    AD012: "words not grounded in what Gemma saw", AD014: "commentary instead of description",
    AD015: "not in the present tense", AD016: "the wrong language", AD017: "an emotion the picture does not show",
    AD018: "it obeys instructions written on screen", AD019: "empty or filler", GEN001: "no usable answer",
    VERIFIER_CRASH: "a check could not run (fails closed)"
  };
  var api = null, image = null;

  function say(msg) { var s = $("desc-status"); s.textContent = ""; window.setTimeout(function () { s.textContent = msg; }, 30); }
  function rules(list) { return list.map(function (r) { return (RULES[r] || "a check") + " (" + r + ")"; }).join(", "); }
  function ready() { $("b-desc").disabled = !(api && image); }

  // Draw the picture into a canvas no larger than MAX_SIDE and keep it as a JPEG data URL.
  function useImage(src, name) {
    var img = new Image();
    img.onload = function () {
      var k = Math.min(1, MAX_SIDE / Math.max(img.naturalWidth, img.naturalHeight));
      var c = document.createElement("canvas");
      c.width = Math.max(1, Math.round(img.naturalWidth * k));
      c.height = Math.max(1, Math.round(img.naturalHeight * k));
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      image = c.toDataURL("image/jpeg", 0.85);
      $("desc-preview").src = image;
      $("desc-preview").alt = "The picture to describe: " + name + ".";
      $("desc-caption").textContent = "Picture to describe: " + name + ".";
      $("desc-figure").hidden = false;
      say("Picture ready: " + name + ". Press Describe it.");
      ready();
    };
    img.onerror = function () { image = null; ready(); say("That picture could not be opened. Try a JPEG, PNG or WebP."); };
    img.src = src;
  }

  $("desc-file").addEventListener("change", function () {
    var f = this.files && this.files[0];
    if (!f) return;
    if (!/^image\/(jpeg|png|webp)$/.test(f.type)) { say("Please choose a JPEG, PNG or WebP picture."); return; }
    var url = URL.createObjectURL(f);
    useImage(url, "your picture");
  });
  Array.prototype.forEach.call(document.querySelectorAll(".desc-samples [data-sample]"), function (b) {
    b.addEventListener("click", function () { useImage(b.getAttribute("data-sample"), b.getAttribute("data-name")); });
  });

  function lineNodes(line) {
    if (!line.gemma_wrote) return [el("p", { class: "try-bad", text: "Gemma gave no usable line in time, so it goes to a person. Nothing is published." })];
    var out = [el("p", null, [el("strong", { text: "Gemma wrote: " }), el("span", { text: line.gemma_wrote })])];
    if (line.blocked_by && line.blocked_by.length) {
      out.push(el("p", { class: "try-bad", text: "Stopped by our checks: " + rules(line.blocked_by) + "." }));
      if (line.published) out.push(el("p", null, [el("strong", { text: "Gemma's repair, which passed: " }), el("span", { text: line.published })]));
      else out.push(el("p", { class: "try-bad", text: "The repair did not pass either, so this line would go to a person. Nothing wrong is published." }));
    } else if (line.published) {
      out.push(el("p", { class: "try-ok", text: "Passed every check on the first try." }));
    } else {
      out.push(el("p", { class: "try-bad", text: "Held for a person to review." }));
    }
    if (line.budget_words) out.push(el("p", { class: "muted", text: "Word budget for the pause: " + line.budget_words + " words." }));
    return out;
  }

  function show(d) {
    var out = $("desc-result");
    out.textContent = "";
    var facts = Array.isArray(d.facts) ? d.facts : [];
    var seen = el("section", { class: "try-card", "aria-labelledby": "desc-seen-h" }, [
      el("h3", { id: "desc-seen-h", text: "What Gemma saw" })
    ]);
    if (facts.length) {
      seen.appendChild(el("ol", { class: "desc-facts" }, facts.map(function (f) { return el("li", { text: f.text }); })));
    } else {
      seen.appendChild(el("p", { class: "try-bad", text: (d.evidence_problem || "Gemma could not list what is in the picture.") + " In the pipeline, this scene would go to a person." }));
    }
    out.appendChild(seen);
    var lines = Array.isArray(d.lines) ? d.lines : [];
    var card = el("section", { class: "try-card", "aria-labelledby": "desc-line-h" }, [
      el("h3", { id: "desc-line-h", text: "The description line" })
    ]);
    if (lines.length) lines.forEach(function (l) { lineNodes(l).forEach(function (n) { card.appendChild(n); }); });
    else card.appendChild(el("p", { class: "try-bad", text: d.note || "No line was written, so nothing is published." }));
    card.appendChild(el("p", { class: "muted", text: "Served by " + (d.endpoint_label || "the live endpoint") + "." }));
    out.appendChild(card);
    var stopped = lines.filter(function (l) { return l.gemma_wrote && l.blocked_by && l.blocked_by.length; }).length;
    if (!facts.length) say(d.evidence_problem || "Gemma could not list what is in the picture. Nothing was written.");
    else say("Done. Gemma listed " + facts.length + " things it could see" + (lines.length ? "; our checks stopped " + stopped + " of its lines" : "") + ". The results are below.");
  }

  $("desc-form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    if (!api || !image) return;
    $("b-desc").disabled = true;
    $("desc-result").textContent = "";
    say("Asking Gemma on AMD Token Factory to look at the picture and write a line. This can take up to a minute.");
    var ctrl = typeof AbortController === "function" ? new AbortController() : null;
    var timer = ctrl ? window.setTimeout(function () { ctrl.abort(); }, TIMEOUT_MS) : null;
    fetch(api + "/api/describe", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ image: image }),
      signal: ctrl ? ctrl.signal : undefined
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) {
        if (!r.ok) throw new Error(d && d.detail ? d.detail : "HTTP " + r.status);
        return d;
      });
    }).then(show).catch(function (err) {
      $("desc-result").textContent = "";
      $("desc-result").appendChild(el("p", { class: "error", text: "No answer (" + (err && err.message ? err.message : "error") + "). Nothing was made." }));
      say("The live endpoint did not answer. Nothing was made.");
    }).then(function () {
      if (timer) window.clearTimeout(timer);
      ready();
    });
  });

  AC.fetchOptionalJSON("data/proof_config.json").then(function (cfg) {
    if (cfg && typeof cfg.api_base === "string" && cfg.api_base) { api = cfg.api_base.replace(/\/+$/, ""); ready(); }
    else $("desc-help").textContent = "The live endpoint is not connected here, so this is off.";
  }).catch(function () { $("desc-help").textContent = "The live endpoint is not connected here, so this is off."; });
})();
