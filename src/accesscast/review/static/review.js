/* AccessCast review app (PLAN §12). Vanilla JS, no build step, no network requests beyond this server.
 *
 * Fail closed: if the live checks cannot run, Approve stays blocked. The server is the last word:
 * PATCH approve returns 422 when checks fail without an override, 409 when the line changed elsewhere.
 */
"use strict";

(() => {
  const DEBOUNCE_MS = 550; // PLAN §12.4: edits saved optimistically, debounced 550 ms
  const IDLE_MS = 60000; // PLAN §12.4: idle > 60 s is not counted as review time
  const CONTEXT_MS = 2000; // PLAN §12.3: 2 s of original before and after
  const WAITING = new Set(["pending", "needs_revision"]);

  const STATUS_LABEL = {
    pending: "Pending",
    approved: "Approved",
    auto_approved: "Approved automatically",
    rejected: "Rejected",
    needs_revision: "Needs revision",
  };
  const STATUS_FILTERS = [
    ["all", "All", () => true],
    ["pending", "Pending", (i) => i.status === "pending"],
    ["needs_revision", "Needs revision", (i) => i.status === "needs_revision"],
    ["approved", "Approved", (i) => i.status === "approved" || i.status === "auto_approved"],
    ["rejected", "Rejected", (i) => i.status === "rejected"],
  ];
  const KIND_FILTERS = [
    ["all", "All kinds", () => true],
    ["description", "Description", (i) => i.kind === "ad" || i.kind === "ad_translation"],
    ["captions", "Captions", (i) => i.kind === "sdh"],
    ["easy", "Easy-read", (i) => i.kind === "easy"],
    ["hi", "Hindi", (i) => i.lang === "hi"],
    ["it", "Italian", (i) => i.lang === "it"],
  ];
  const KIND_LABEL = {
    ad: "Description",
    ad_translation: "Description",
    sdh: "Captions",
    easy: "Easy-read",
    subtitle: "Subtitles",
    voiceover: "Voice-over",
  };
  const LANG_LABEL = { en: "English", hi: "Hindi", it: "Italian" };
  const TERM_LABEL = {
    grounding: "Grounding: share of nouns found in the facts",
    slack: "Room left in the pause",
    asr: "Speech recognition certainty nearby",
    ocr: "On-screen text agreement",
    repairs: "Repairs used (subtracted)",
    warnings: "Warnings (subtracted)",
  };
  const STOP_REASON = {
    safe_initial_proposal: "The first draft passed the checks.",
    safe_model_revision: "A model revision passed the checks.",
    repair_limit_reached: "Still failing after the last repair; sent to a person.",
    revision_generation_failed: "The model could not produce a revision; sent to a person.",
    non_repairable: "A problem the model is not allowed to fix; sent to a person.",
  };
  const NUM = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"];

  const $ = (id) => document.getElementById(id);
  const el = {};
  [
    "status", "gate-result", "picker", "project-list", "workspace", "project-title", "fake-banner", "reviewer",
    "btn-complete", "btn-render", "btn-help", "help", "help-close", "pending-badge", "status-filters",
    "kind-filters", "btn-lowest", "list-summary", "item-list", "video", "video-time", "frames", "frames-note",
    "timeline", "timeline-text-body", "no-item", "detail", "item-head", "item-save", "source-wrap",
    "source-text", "draft", "final", "meter", "meter-fill", "override-wrap", "override", "override-reason",
    "btn-approve", "btn-reject", "btn-revise", "btn-edit", "btn-context", "btn-hear", "findings", "bt-wrap",
    "back-translation", "facts", "confidence", "repairs", "clip", "items-panel",
    "btn-add", "add", "add-form", "add-start", "add-end", "add-text", "add-error", "add-cancel",
  ].forEach((id) => { el[id] = $(id); });

  const S = {
    pid: null,
    info: null,
    analysis: null,
    items: [],
    byId: new Map(),
    order: new Map(),
    selectedId: null,
    statusFilter: "all",
    kindFilter: "all",
    check: null, // latest verifier result for the selected item
    checkText: null,
    checkFor: null,
    checkState: "none", // none | running | ready | failed
    verifyToken: 0,
    verifyTimer: null,
    saveTimer: null,
    saveChain: Promise.resolve(),
    lastSummary: "",
    secs: {}, // unsent review seconds per item
    activity: Date.now(),
    seq: 0, // playback sequence token
    stopAt: null,
  };

  // ------------------------------------------------------------------ helpers
  function h(tag, attrs, ...kids) {
    const n = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (v === null || v === undefined || v === false) continue;
        if (k === "class") n.className = v;
        else if (k === "text") n.textContent = v;
        else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
        else if (k === "dataset") Object.assign(n.dataset, v);
        else n.setAttribute(k, v === true ? "" : String(v));
      }
    }
    for (const k of kids.flat()) {
      if (k === null || k === undefined || k === false) continue;
      n.append(k instanceof Node ? k : document.createTextNode(String(k)));
    }
    return n;
  }
  function fmtTime(ms) {
    const s = Math.max(0, ms) / 1000;
    const m = Math.floor(s / 60);
    const rest = (s - m * 60).toFixed(1).padStart(4, "0");
    return `${m}:${rest}`;
  }
  const fmtSec = (s) => `${Number(s).toFixed(1)} s`;
  function plural(n, one, many) { return `${n} ${n === 1 ? one : many}`; }
  function numWord(n) { return n < NUM.length ? NUM[n] : String(n); }
  function announce(msg) {
    // Clear first so the same message is announced again.
    el.status.textContent = "";
    window.setTimeout(() => { el.status.textContent = msg; }, 30);
  }
  function itemEnd(it) {
    if (it.slot.end_ms > it.anchor_ms) return it.slot.end_ms;
    return it.anchor_ms + (it.tts ? it.tts.duration_ms : 1000);
  }
  function isDescription(it) { return it.kind === "ad" || it.kind === "ad_translation"; }
  function kindText(it) {
    const base = KIND_LABEL[it.kind] || it.kind;
    return `${it.extended ? "Extended " + base.toLowerCase() : base}, ${LANG_LABEL[it.lang] || it.lang}`;
  }
  function current() { return S.selectedId ? S.byId.get(S.selectedId) || null : null; }
  function errorsOf(check) { return check ? check.violations.filter((f) => f.severity === "error") : []; }

  function reviewerName() {
    return el.reviewer.value.trim();
  }
  function headerSafe(v) { return /^[\x20-\x7e]*$/.test(v) ? v : encodeURIComponent(v); }

  async function api(method, path, body) {
    const headers = { Accept: "application/json" };
    const who = reviewerName();
    if (who) headers["X-Reviewer"] = headerSafe(who);
    if (body !== undefined) headers["Content-Type"] = "application/json";
    let res;
    try {
      res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    } catch (e) {
      return { ok: false, status: 0, data: { detail: "The review server did not answer." } };
    }
    let data = null;
    try { data = await res.json(); } catch (e) { data = null; }
    return { ok: res.ok, status: res.status, data: data || {} };
  }
  function detailOf(r) {
    const d = r.data && r.data.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return "The server did not accept the request.";
    return r.status ? `The server answered with error ${r.status}.` : "The review server did not answer.";
  }

  // ------------------------------------------------------------------ reviewer name
  try { el.reviewer.value = window.localStorage.getItem("accesscast.reviewer") || ""; } catch (e) { /* no storage */ }
  el.reviewer.addEventListener("change", () => {
    try { window.localStorage.setItem("accesscast.reviewer", el.reviewer.value.trim()); } catch (e) { /* no storage */ }
  });

  // ------------------------------------------------------------------ review timer (PLAN §12.4)
  function markActive() { S.activity = Date.now(); }
  ["keydown", "mousedown", "mousemove", "wheel", "touchstart", "focusin"].forEach((t) =>
    document.addEventListener(t, markActive, { passive: true, capture: true }));
  window.setInterval(() => {
    if (!S.selectedId || document.visibilityState !== "visible") return;
    const playing = !el.video.paused || !el.clip.paused;
    if (playing) markActive();
    if (Date.now() - S.activity > IDLE_MS) return;
    S.secs[S.selectedId] = (S.secs[S.selectedId] || 0) + 1;
    renderSaveLine();
  }, 1000);
  function takeSeconds(id) {
    const s = Math.round((S.secs[id] || 0) * 10) / 10;
    S.secs[id] = 0;
    return s;
  }
  function putBackSeconds(id, s) { S.secs[id] = (S.secs[id] || 0) + s; }

  // ------------------------------------------------------------------ loading
  async function start() {
    const params = new URLSearchParams(window.location.search);
    const pid = params.get("p");
    const r = await api("GET", "/api/projects");
    const projects = r.ok && Array.isArray(r.data) ? r.data : [];
    if (!r.ok) announce(`Could not list projects: ${detailOf(r)}`);
    if (!pid) { showPicker(projects); return; }
    S.pid = pid;
    S.info = projects.find((p) => p.id === pid) || null;
    const [items, analysis] = await Promise.all([
      api("GET", `/api/projects/${encodeURIComponent(pid)}/items`),
      api("GET", `/api/projects/${encodeURIComponent(pid)}/analysis`),
    ]);
    if (!items.ok || !analysis.ok) {
      announce(`Could not open project ${pid}: ${detailOf(items.ok ? analysis : items)}`);
      showPicker(projects);
      return;
    }
    S.analysis = analysis.data;
    setItems(items.data.items);
    el.workspace.hidden = false;
    el.picker.hidden = true;
    el["btn-complete"].disabled = false;
    el["btn-render"].disabled = false;
    el["btn-add"].disabled = false;
    const title = (S.info && S.info.title) || S.analysis.title || pid;
    el["project-title"].textContent = `Project ${pid}: ${title}, ${fmtSec(S.analysis.duration_ms / 1000)} long`;
    document.title = `Review ${title} – AccessCast`;
    el["fake-banner"].hidden = !((S.info && S.info.fake) || S.analysis.fake);
    el.video.src = `/media/${encodeURIComponent(pid)}/media/source.mp4`;
    renderFilters();
    renderList();
    renderTimeline();
    const waiting = S.items.filter((i) => WAITING.has(i.status)).length;
    announce(`Project loaded. ${plural(waiting, "line is", "lines are")} waiting for a person. Press ] for the next line, ? for keys.`);
  }

  function showPicker(projects) {
    el.picker.hidden = false;
    el.workspace.hidden = true;
    el["project-list"].replaceChildren();
    if (!projects.length) {
      el["project-list"].append(h("li", { text: "No projects found in the projects folder." }));
      return;
    }
    for (const p of projects) {
      const label = `${p.title} (${p.id}): ${fmtSec(p.duration_ms / 1000)}, ${p.pending} of ${p.items} lines waiting` +
        (p.fake ? ". Demo fixture: canned model outputs" : "");
      el["project-list"].append(h("li", null, h("a", { href: `?p=${encodeURIComponent(p.id)}`, text: label })));
    }
    if (projects.some((p) => p.fake)) el["fake-banner"].hidden = false;
  }

  function setItems(list) {
    S.items = list.slice().sort((a, b) => a.anchor_ms - b.anchor_ms || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
    S.byId = new Map(S.items.map((i) => [i.id, i]));
    S.order = new Map(S.items.map((i, k) => [i.id, k]));
  }

  async function reloadItems() {
    const r = await api("GET", `/api/projects/${encodeURIComponent(S.pid)}/items`);
    if (!r.ok) { announce(`Could not reload the lines: ${detailOf(r)}`); return false; }
    setItems(r.data.items);
    renderFilters();
    renderList();
    renderTimeline();
    if (S.selectedId && S.byId.has(S.selectedId)) {
      renderDetail(true);
      runVerify(el.final.value, false);
    }
    return true;
  }

  // ------------------------------------------------------------------ left panel
  const statusPred = () => STATUS_FILTERS.find((f) => f[0] === S.statusFilter)[2];
  const kindPred = () => KIND_FILTERS.find((f) => f[0] === S.kindFilter)[2];
  function filtered() { const sp = statusPred(), kp = kindPred(); return S.items.filter((i) => sp(i) && kp(i)); }

  function renderFilters() {
    const kp = kindPred(), sp = statusPred();
    el["status-filters"].replaceChildren(...STATUS_FILTERS.map(([key, label, pred]) => {
      const n = S.items.filter((i) => kp(i) && pred(i)).length;
      return h("button", {
        type: "button", "aria-pressed": S.statusFilter === key ? "true" : "false", dataset: { filter: key },
        onclick: () => { S.statusFilter = key; renderFilters(); renderList(); announceList(); },
      }, `${label} (${n})`);
    }));
    el["kind-filters"].replaceChildren(...KIND_FILTERS.map(([key, label, pred]) => {
      const n = S.items.filter((i) => sp(i) && pred(i)).length;
      return h("button", {
        type: "button", "aria-pressed": S.kindFilter === key ? "true" : "false", dataset: { kind: key },
        onclick: () => { S.kindFilter = key; renderFilters(); renderList(); announceList(); },
      }, `${label} (${n})`);
    }));
    const waiting = S.items.filter((i) => WAITING.has(i.status)).length;
    el["pending-badge"].textContent = waiting ? `${waiting} waiting` : "";
  }
  function announceList() { announce(`Showing ${plural(filtered().length, "line", "lines")}.`); }

  function renderList() {
    const list = filtered();
    const active = document.activeElement;
    const focusId = active && el["item-list"].contains(active) ? active.dataset.id : null;
    el["list-summary"].textContent = `Showing ${list.length} of ${S.items.length} lines, sorted by time.`;
    el["item-list"].replaceChildren(...list.map((it) => {
      const meta = [fmtTime(it.anchor_ms), kindText(it)];
      if (it.confidence !== null && it.confidence !== undefined) meta.push(`confidence ${it.confidence.toFixed(2)}`);
      return h("li", null, h("button", {
        type: "button", class: `st-${it.status}`, dataset: { id: it.id },
        "aria-current": it.id === S.selectedId ? "true" : null,
        onclick: () => selectItem(it.id),
      },
      h("span", { class: "iid", text: it.id }),
      h("span", { class: `chip ${it.status}`, text: STATUS_LABEL[it.status] || it.status }),
      h("span", { class: "meta" }, meta.join(" · "), it.source === "manual" ? h("span", { class: "tag", text: "manual" }) : null),
      h("span", { class: "txt", lang: it.lang, text: it.text })));
    }));
    if (list.length === 0) el["item-list"].append(h("li", { class: "muted", text: "No lines match these filters." }));
    if (focusId) focusItemButton(focusId) || focusItemButton(S.selectedId);
  }
  function focusItemButton(id) {
    if (!id) return false;
    const b = el["item-list"].querySelector(`button[data-id="${CSS.escape(id)}"]`);
    if (b) { b.focus(); return true; }
    return false;
  }
  function focusList() {
    if (!focusItemButton(S.selectedId)) {
      const first = el["item-list"].querySelector("button");
      if (first) first.focus(); else el["items-panel"].focus();
    }
  }

  function step(dir) {
    const list = filtered();
    if (!list.length) { announce("No lines match these filters."); return; }
    let target;
    if (!S.selectedId) target = dir > 0 ? list[0] : list[list.length - 1];
    else {
      const pos = S.order.get(S.selectedId);
      target = dir > 0 ? list.find((i) => S.order.get(i.id) > pos)
        : [...list].reverse().find((i) => S.order.get(i.id) < pos);
    }
    if (!target) { announce(dir > 0 ? "This is the last line." : "This is the first line."); return; }
    const inList = el["item-list"].contains(document.activeElement);
    selectItem(target.id);
    if (inList) focusItemButton(target.id);
  }

  function jumpLowest() {
    const cands = filtered().filter((i) => WAITING.has(i.status) && typeof i.confidence === "number");
    if (!cands.length) { announce("No waiting line in this view has a confidence score."); return; }
    cands.sort((a, b) => a.confidence - b.confidence || S.order.get(a.id) - S.order.get(b.id));
    selectItem(cands[0].id, `Lowest confidence: ${cands[0].confidence.toFixed(2)}.`);
    focusItemButton(cands[0].id);
  }

  // ------------------------------------------------------------------ select
  function selectItem(id, prefix) {
    const prev = S.selectedId;
    if (prev && prev !== id && S.saveTimer) { // save the previous line's edit now
      window.clearTimeout(S.saveTimer);
      S.saveTimer = null;
      const it = S.byId.get(prev);
      if (it && el.final.value !== it.text) patchItem(prev, { final: el.final.value });
    }
    window.clearTimeout(S.verifyTimer);
    S.selectedId = id;
    const it = current();
    if (!it) return;
    stopPlayback();
    el.video.pause();
    try { el.video.currentTime = it.anchor_ms / 1000; } catch (e) { /* metadata not ready */ }
    S.lastSummary = "";
    renderList();
    const btn = el["item-list"].querySelector(`button[data-id="${CSS.escape(id)}"]`);
    if (btn) btn.scrollIntoView({ block: "nearest" });
    renderDetail(true);
    renderFrames();
    renderTimelineSelection();
    const head = `${prefix ? prefix + " " : ""}${it.id}, ${kindText(it)}, at ${fmtTime(it.anchor_ms)}, ${STATUS_LABEL[it.status]}.` +
      `${it.source === "manual" ? " Manual line." : ""} Text: ${it.text}`;
    runVerify(it.text, false).then((chk) => {
      if (S.selectedId !== id) return;
      announce(`${head} ${chk ? summarize(chk) : "The checks could not run."}`);
    });
  }

  // ------------------------------------------------------------------ right panel
  function renderDetail(resetText) {
    const it = current();
    el["no-item"].hidden = !!it;
    el.detail.hidden = !it;
    if (!it) return;
    el.detail.dataset.id = it.id;
    el.detail.dataset.status = it.status;
    el["item-head"].replaceChildren(...[
      h("span", null, `${it.id} · ${kindText(it)} · ${fmtTime(it.anchor_ms)} to ${fmtTime(itemEnd(it))} · `),
      h("span", { class: `chip ${it.status}`, text: STATUS_LABEL[it.status] || it.status }),
      it.source === "manual" ? h("span", { class: "tag", text: "manual" }) : null,
      it.extended ? h("span", { class: "muted" }, " The video pauses for this line.") : null,
    ].filter(Boolean));
    if (it.source_text) {
      el["source-wrap"].hidden = false;
      el["source-text"].textContent = it.source_text;
    } else el["source-wrap"].hidden = true;
    el.draft.textContent = it.draft;
    el.draft.lang = it.lang;
    el.final.lang = it.lang;
    if (resetText) {
      el.final.value = it.text;
      el.override.checked = false;
      el["override-reason"].value = "";
    }
    // Back-translation (translated lines only)
    if (it.lang !== "en") {
      el["bt-wrap"].hidden = false;
      el["back-translation"].textContent = it.back_translation || "No back-translation is stored for this line.";
    } else el["bt-wrap"].hidden = true;
    renderFacts(it);
    renderConfidence(it);
    renderRepairs(it);
    renderSaveLine();
    renderCheck();
  }

  function renderSaveLine(msg) {
    const it = current();
    if (!it) return;
    if (msg !== undefined) el["item-save"].dataset.msg = msg;
    const m = el["item-save"].dataset.msg || "";
    const secs = Math.round((it.review_seconds || 0) + (S.secs[it.id] || 0));
    el["item-save"].textContent = `${m ? m + " " : ""}Revision ${it.revision}. Review time on this line: ${secs} s.` +
      (it.reviewer ? ` Last decided by ${it.reviewer}.` : "");
  }

  function factsIndex() {
    const out = new Map();
    const ev = (S.analysis && S.analysis.evidence) || {};
    for (const [sid, e] of Object.entries(ev)) for (const f of e.facts || []) out.set(f.fid, { ...f, scene: sid });
    return out;
  }
  function renderFacts(it) {
    const idx = factsIndex();
    if (!it.fact_ids.length) {
      el.facts.replaceChildren(h("li", { text: isDescription(it) ? "No facts linked to this line."
        : "No picture facts: this line comes from the dialogue." }));
      return;
    }
    el.facts.replaceChildren(...it.fact_ids.map((fid) => {
      const f = idx.get(fid);
      return h("li", null, h("strong", { text: `${fid}: ` }), f ? f.text : "This fact is missing from the evidence.");
    }));
  }
  function renderConfidence(it) {
    if (typeof it.confidence !== "number") {
      el.confidence.replaceChildren(h("p", { text: "Not computed for this kind of line." }));
      return;
    }
    const terms = Object.entries(it.confidence_terms || {});
    el.confidence.replaceChildren(...[
      h("p", { text: `${it.confidence.toFixed(2)} out of 1. Computed in code from measured signals, never asked of the model.` }),
      terms.length ? h("dl", { class: "terms" }, ...terms.map(([k, v]) => [
        h("dt", { text: TERM_LABEL[k] || k }), h("dd", { text: Number(v).toFixed(2) })])) : null,
    ].filter(Boolean));
  }
  function renderRepairs(it) {
    const hist = (it.repair && it.repair.history) || [];
    const lis = hist.map((s) => h("li", null,
      h("strong", { text: s.attempt === 0 ? "Draft: " : `Revision ${s.attempt}: ` }),
      h("span", { lang: it.lang, text: s.text }),
      h("br"),
      h("span", { class: "muted", text: s.rules.length ? `Failed checks: ${s.rules.join(", ")}.` : "Passed the checks." })));
    if (!lis.length) lis.push(h("li", { text: "No repair steps recorded." }));
    const reason = it.repair ? STOP_REASON[it.repair.stop_reason] || it.repair.stop_reason : "";
    el.repairs.replaceChildren(...lis);
    if (reason) el.repairs.append(h("li", { class: "muted", text: `Result: ${reason}` }));
  }

  // ------------------------------------------------------------------ checks
  function meterText(m) {
    const parts = [];
    if (m.words_max !== null && m.words_max !== undefined) parts.push(`${m.words} of ${m.words_max} words`);
    else parts.push(plural(m.words, "word", "words"));
    if (m.seconds_max !== null && m.seconds_max !== undefined) parts.push(`${m.seconds.toFixed(1)} of ${m.seconds_max.toFixed(1)} s`);
    else parts.push(`about ${m.seconds.toFixed(1)} s`);
    return `${parts.join(", ")} (${m.measured ? "measured with the voice" : "estimated"})`;
  }
  function summarize(chk) {
    const m = chk.meter;
    let lead;
    if (m.seconds_max !== null && m.seconds_max !== undefined) {
      lead = `${m.seconds <= m.seconds_max ? "Fits" : "Too long"}: ${m.seconds.toFixed(1)} of ${m.seconds_max.toFixed(1)} seconds.`;
    } else lead = `About ${m.seconds.toFixed(1)} seconds.`;
    const errs = errorsOf(chk);
    const warns = chk.warnings;
    const bits = [lead];
    if (!errs.length && !warns.length) bits.push("No problems found.");
    if (errs.length) bits.push(`${numWord(errs.length)} ${errs.length === 1 ? "error" : "errors"}: ${errs.map((f) => f.message).join(" ")}`);
    if (warns.length) bits.push(`${numWord(warns.length)} ${warns.length === 1 ? "warning" : "warnings"}: ${warns.map((f) => f.message).join(" ")}`);
    return bits.join(" ");
  }
  function findingNode(f) {
    const label = f.severity === "error" ? "Error" : "Warning";
    return h("div", { class: `finding ${f.severity}` },
      h("p", null, h("span", { class: "rule", text: `${label} (${f.rule}): ` }), f.message),
      h("p", { text: `Found: ${f.observed}. Limit: ${f.threshold}.` }));
  }
  function renderCheck() {
    const it = current();
    if (!it) return;
    const chk = S.checkFor === it.id ? S.check : null;
    el.detail.dataset.checkState = S.checkFor === it.id ? S.checkState : "running";
    if (S.checkState === "failed" && S.checkFor === it.id) {
      el.findings.replaceChildren(h("p", { class: "finding error", text: "The checks could not run, so this line cannot be approved yet. Edit the text or try again." }));
      el.meter.textContent = "Fit not known: the checks did not run.";
      el["meter-fill"].style.width = "0";
      el.detail.dataset.hasErrors = "unknown";
      el["override-wrap"].hidden = true;
      return;
    }
    if (!chk) {
      el.findings.replaceChildren(h("p", { class: "muted", text: "Checking…" }));
      return;
    }
    el.meter.textContent = meterText(chk.meter);
    const m = chk.meter;
    let ratio = 0;
    if (m.seconds_max) ratio = m.seconds / m.seconds_max;
    else if (m.words_max) ratio = m.words / m.words_max;
    el["meter-fill"].style.width = `${Math.min(100, Math.round(ratio * 100))}%`;
    el["meter-fill"].classList.toggle("over", ratio > 1);
    el["meter-fill"].parentElement.hidden = !(m.seconds_max || m.words_max);
    const errs = errorsOf(chk);
    const nodes = [...errs, ...chk.warnings].map(findingNode);
    el.findings.replaceChildren(...(nodes.length ? nodes : [h("p", { class: "ok-text", text: "No problems found by the automatic checks." })]));
    el.detail.dataset.hasErrors = errs.length ? "true" : "false";
    el["override-wrap"].hidden = !errs.length;
  }

  async function runVerify(text, speak) {
    const it = current();
    if (!it) return null;
    const id = it.id;
    const tok = ++S.verifyToken;
    S.checkFor = id;
    S.checkState = "running";
    el.detail.dataset.checkState = "running";
    const r = await api("POST", `/api/projects/${encodeURIComponent(S.pid)}/items/${encodeURIComponent(id)}/verify`, { text });
    if (tok !== S.verifyToken) return r.ok ? r.data : null;
    if (!r.ok || !r.data || !Array.isArray(r.data.violations)) {
      S.check = null; S.checkText = null; S.checkState = "failed";
      renderCheck();
      if (speak) announce(`The checks could not run: ${detailOf(r)}`);
      return null;
    }
    S.check = r.data; S.checkText = text; S.checkState = "ready";
    renderCheck();
    const summary = summarize(r.data);
    if (speak && summary !== S.lastSummary) announce(summary);
    S.lastSummary = summary;
    return r.data;
  }
  async function ensureCheck(text) {
    const it = current();
    if (it && S.checkFor === it.id && S.checkState === "ready" && S.checkText === text) return S.check;
    return runVerify(text, false);
  }

  // ------------------------------------------------------------------ saving
  function patchItem(id, body) {
    const run = async () => {
      const it = S.byId.get(id);
      if (!it) return { ok: false, status: 404, data: {} };
      const secs = takeSeconds(id);
      const payload = { expected_revision: it.revision, ...body };
      if (secs > 0) payload.review_seconds = secs;
      if (id === S.selectedId) renderSaveLine("Saving…");
      const r = await api("PATCH", `/api/projects/${encodeURIComponent(S.pid)}/items/${encodeURIComponent(id)}`, payload);
      if (r.ok) {
        it.revision = r.data.revision;
        it.status = r.data.status;
        it.final = r.data.final;
        it.text = it.final !== null && it.final !== undefined ? it.final : it.draft;
        it.review_seconds = (it.review_seconds || 0) + secs;
        if (body.status && body.status !== "pending") it.reviewer = reviewerName() || it.reviewer || "reviewer";
        if (body.override_reason) it.override_reason = body.override_reason;
        renderFilters();
        renderList();
        renderTimeline();
        if (id === S.selectedId) {
          el.detail.dataset.status = it.status;
          renderDetail(false);
          renderSaveLine("Saved.");
        }
        return r;
      }
      putBackSeconds(id, secs);
      if (r.status === 409) {
        announce("Changed elsewhere; reloaded.");
        await reloadItems();
        if (id === S.selectedId) renderSaveLine("Changed elsewhere; reloaded.");
      } else if (r.status === 422) {
        if (id === S.selectedId && r.data.check) {
          S.check = r.data.check; S.checkText = el.final.value; S.checkFor = id; S.checkState = "ready";
          renderCheck();
        }
        announce(`Not approved. ${r.data.detail || "This line still fails checks."}`);
        if (id === S.selectedId) renderSaveLine("Not approved.");
      } else {
        announce(`Could not save ${id}: ${detailOf(r)}`);
        if (id === S.selectedId) renderSaveLine("Not saved.");
      }
      return r;
    };
    S.saveChain = S.saveChain.then(run, run);
    return S.saveChain;
  }

  el.final.addEventListener("input", () => {
    const it = current();
    if (!it) return;
    renderSaveLine("Not saved yet…");
    el.detail.dataset.checkState = "running";
    window.clearTimeout(S.verifyTimer);
    window.clearTimeout(S.saveTimer);
    const id = it.id;
    S.verifyTimer = window.setTimeout(() => { if (S.selectedId === id) runVerify(el.final.value, true); }, DEBOUNCE_MS);
    S.saveTimer = window.setTimeout(() => {
      S.saveTimer = null;
      const cur = S.byId.get(id);
      if (S.selectedId === id && cur && el.final.value !== cur.text) patchItem(id, { final: el.final.value });
      else if (S.selectedId === id) renderSaveLine("Saved.");
    }, DEBOUNCE_MS);
  });

  async function decide(status) {
    const it = current();
    if (!it) { announce("Choose a line first. Press ] for the next line."); return; }
    window.clearTimeout(S.saveTimer);
    S.saveTimer = null;
    await S.saveChain;
    const text = el.final.value;
    const body = { status };
    if (text !== it.text) body.final = text;
    if (status === "approved") {
      window.clearTimeout(S.verifyTimer);
      const chk = await ensureCheck(text);
      if (!chk) { announce("Can't approve: the checks did not run. Try again."); return; }
      if (errorsOf(chk).length) {
        const reason = el["override-reason"].value.trim();
        if (!(el.override.checked && reason)) {
          el["override-wrap"].hidden = false;
          const n = errorsOf(chk).length;
          announce(`Can't approve: this line still fails ${plural(n, "check", "checks")}. Fix the text, or tick Override and write a reason.`);
          (el.override.checked ? el["override-reason"] : el.override).focus();
          return;
        }
        body.override_reason = reason;
      }
    }
    const r = await patchItem(it.id, body);
    if (r && r.ok) {
      const waiting = S.items.filter((i) => WAITING.has(i.status)).length;
      announce(`${STATUS_LABEL[status]}: ${it.id}.${body.override_reason ? " Override logged." : ""} ${plural(waiting, "line", "lines")} still waiting. Press ] for the next line.`);
    }
  }

  // ------------------------------------------------------------------ centre: frames
  function sceneFor(it) {
    if (it.scene_id) return it.scene_id;
    const scenes = (S.analysis.scenes && S.analysis.scenes.scenes) || [];
    const s = scenes.find((sc) => it.anchor_ms >= sc.start_ms && it.anchor_ms < sc.end_ms);
    return s ? s.scene_id : null;
  }
  function renderFrames() {
    const it = current();
    el.frames.replaceChildren();
    if (!it) { el["frames-note"].textContent = ""; return; }
    const sid = sceneFor(it);
    const ev = sid ? (S.analysis.evidence || {})[sid] : null;
    if (!ev) { el["frames-note"].textContent = "No evidence frames for this line."; return; }
    const scene = ((S.analysis.scenes && S.analysis.scenes.scenes) || []).find((s) => s.scene_id === sid);
    const used = new Set(it.fact_ids);
    el["frames-note"].textContent = `Scene ${sid}${scene ? `, ${fmtTime(scene.start_ms)} to ${fmtTime(scene.end_ms)}` : ""}.` +
      (ev.status !== "ok" ? " Evidence failed for this scene." : "") +
      (used.size ? " Frames with a blue border support a fact this line uses." : "");
    ev.frames.forEach((name, k) => {
      const facts = (ev.facts || []).filter((f) => f.frames.includes(k));
      const supports = facts.some((f) => used.has(f.fid));
      const alt = facts.length ? facts.map((f) => f.text).join(" ") : `Frame ${k + 1} of scene ${sid}. No facts listed for this frame.`;
      const ms = ev.frame_ms && ev.frame_ms[k] !== undefined ? ev.frame_ms[k] : null;
      el.frames.append(h("li", null, h("figure", null,
        h("img", {
          src: `/media/${encodeURIComponent(S.pid)}/evidence/${encodeURIComponent(sid)}/${encodeURIComponent(name)}`,
          alt, class: supports ? "supports" : null, loading: "lazy", width: 640, height: 360,
        }),
        h("figcaption", { text: `${ms !== null ? fmtTime(ms) : name}${supports ? ", used" : ""}` }))));
    });
  }

  // ------------------------------------------------------------------ centre: timeline
  function lanes() {
    const byGroup = (pred) => {
      const groups = new Map();
      for (const it of S.items.filter(pred)) {
        const key = `${KIND_LABEL[it.kind]} ${LANG_LABEL[it.lang] || it.lang}`;
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(it);
      }
      return groups;
    };
    return [
      ["Description", byGroup(isDescription)],
      ["Captions", byGroup((i) => i.kind === "sdh" || i.kind === "easy" || i.kind === "subtitle")],
      ["Voice-over", byGroup((i) => i.kind === "voiceover")],
    ];
  }
  function pct(ms) { return `${Math.max(0, Math.min(100, (ms / S.analysis.duration_ms) * 100))}%`; }
  function boxStyle(a, b) { return `left:${pct(a)};width:${pct(Math.max(b - a, 0))}`; }

  function track(rows) {
    const t = h("div", { class: "lane-track" }, ...rows, h("div", { class: "playhead" }));
    t.addEventListener("click", (e) => {
      if (e.target.closest(".box.item")) return;
      const r = t.getBoundingClientRect();
      const ms = ((e.clientX - r.left) / r.width) * S.analysis.duration_ms;
      el.video.currentTime = Math.max(0, ms / 1000);
    });
    return t;
  }

  function renderTimeline() {
    if (!S.analysis) return;
    const words = (S.analysis.words && S.analysis.words.words) || [];
    const gaps = (S.analysis.gaps && S.analysis.gaps.gaps) || [];
    const out = [];
    out.push(h("div", { class: "lane" }, h("span", { class: "lane-name", text: "Words" }),
      track([h("div", { class: "lane-row" }, ...words.map((w) =>
        h("div", { class: "box word", style: boxStyle(w.start_ms, w.end_ms), title: w.w })))])));
    out.push(h("div", { class: "lane" }, h("span", { class: "lane-name", text: "Gaps" }),
      track([h("div", { class: "lane-row" }, ...gaps.map((g) =>
        h("div", { class: "box gap", style: boxStyle(g.start_ms, g.end_ms), title: `${g.gap_id} ${fmtSec(g.len_ms / 1000)}` })))])));
    for (const [name, groups] of lanes()) {
      const rows = [...groups.entries()].map(([gname, its]) => h("div", { class: "lane-row", title: gname },
        ...its.map((it) => h("div", {
          class: `box item ${it.status}${it.source === "manual" ? " manual" : ""}${it.id === S.selectedId ? " selected" : ""}`,
          style: boxStyle(it.anchor_ms, itemEnd(it)), title: `${it.id}: ${STATUS_LABEL[it.status]}`,
          dataset: { id: it.id }, onclick: () => selectItem(it.id),
        }))));
      if (!rows.length) rows.push(h("div", { class: "lane-row" }));
      out.push(h("div", { class: "lane" }, h("span", { class: "lane-name", text: name }), track(rows)));
    }
    el.timeline.replaceChildren(...out);
    renderTimelineText(words, gaps);
    updatePlayhead();
  }
  function renderTimelineSelection() {
    el.timeline.querySelectorAll(".box.item").forEach((b) => b.classList.toggle("selected", b.dataset.id === S.selectedId));
    el["timeline-text-body"].querySelectorAll("button[data-id]").forEach((b) => {
      if (b.dataset.id === S.selectedId) b.setAttribute("aria-current", "true"); else b.removeAttribute("aria-current");
    });
  }

  function renderTimelineText(words, gaps) {
    const segs = new Map();
    for (const w of words) {
      if (!segs.has(w.seg)) segs.set(w.seg, []);
      segs.get(w.seg).push(w);
    }
    const body = [];
    body.push(h("h4", { text: "Words" }));
    body.push(segs.size ? h("ul", null, ...[...segs.values()].map((ws) => h("li", {
      text: `${fmtTime(ws[0].start_ms)} to ${fmtTime(ws[ws.length - 1].end_ms)}: ${ws.map((w) => w.w).join(" ")}`,
    }))) : h("p", { text: "No words." }));
    body.push(h("h4", { text: "Gaps (pauses in speech)" }));
    body.push(gaps.length ? h("ul", null, ...gaps.map((g) => h("li", {
      text: `${g.gap_id}: ${fmtTime(g.start_ms)} to ${fmtTime(g.end_ms)}, ${fmtSec(g.len_ms / 1000)}, ${g.under.replace(/_/g, " ")}`,
    }))) : h("p", { text: "No gaps." }));
    for (const [name, groups] of lanes()) {
      body.push(h("h4", { text: name }));
      const its = [...groups.values()].flat().sort((a, b) => S.order.get(a.id) - S.order.get(b.id));
      body.push(its.length ? h("ul", null, ...its.map((it) => h("li", null, h("button", {
        type: "button", dataset: { id: it.id }, "aria-current": it.id === S.selectedId ? "true" : null,
        onclick: () => selectItem(it.id),
      }, `${it.id}, ${fmtTime(it.anchor_ms)} to ${fmtTime(itemEnd(it))}, ${STATUS_LABEL[it.status]}${it.source === "manual" ? ", manual" : ""}: `,
      h("span", { lang: it.lang, text: it.text }))))) : h("p", { text: "No lines." }));
    }
    el["timeline-text-body"].replaceChildren(...body);
  }

  function updatePlayhead() {
    if (!S.analysis) return;
    const ms = (el.video.currentTime || 0) * 1000;
    el.timeline.querySelectorAll(".playhead").forEach((p) => { p.style.left = pct(ms); });
    el["video-time"].textContent = `Video at ${fmtTime(ms)}`;
  }
  el.video.addEventListener("timeupdate", () => {
    updatePlayhead();
    if (S.stopAt !== null && el.video.currentTime * 1000 >= S.stopAt) { el.video.pause(); }
  });
  el.video.addEventListener("seeked", updatePlayhead);

  // ------------------------------------------------------------------ playback
  function stopPlayback() {
    S.seq += 1;
    S.stopAt = null;
    if (!el.clip.paused) el.clip.pause();
  }
  function seekTo(ms) {
    return new Promise((resolve) => {
      const target = Math.max(0, ms / 1000);
      if (Math.abs(el.video.currentTime - target) < 0.01) { resolve(); return; }
      const done = () => { el.video.removeEventListener("seeked", done); resolve(); };
      el.video.addEventListener("seeked", done);
      el.video.currentTime = target;
      window.setTimeout(done, 1500);
    });
  }
  async function playVideoRange(a, b, tok) {
    await seekTo(a);
    if (tok !== S.seq) return;
    S.stopAt = b;
    try { await el.video.play(); } catch (e) { announce("The browser did not let the video play."); return; }
    await new Promise((resolve) => {
      const tick = () => {
        if (tok !== S.seq || el.video.paused || el.video.ended || el.video.currentTime * 1000 >= b) {
          el.video.pause();
          resolve();
          return;
        }
        window.requestAnimationFrame(tick);
      };
      window.requestAnimationFrame(tick);
    });
    if (S.stopAt === b) S.stopAt = null;
  }
  function playClip(url, tok) {
    return new Promise((resolve) => {
      if (tok !== S.seq) { resolve(); return; }
      const end = () => { el.clip.removeEventListener("ended", end); el.clip.removeEventListener("error", end); resolve(); };
      el.clip.addEventListener("ended", end);
      el.clip.addEventListener("error", end);
      el.clip.src = url;
      el.clip.play().catch(() => { announce("The browser did not let the clip play."); end(); });
    });
  }
  async function playInContext() {
    const it = current();
    if (!it) { announce("Choose a line first."); return; }
    stopPlayback();
    const tok = S.seq;
    const a = Math.max(0, it.anchor_ms - CONTEXT_MS);
    const b = Math.min(S.analysis.duration_ms, itemEnd(it) + CONTEXT_MS);
    announce(`Playing ${fmtTime(a)} to ${fmtTime(b)}.`);
    await playVideoRange(a, b, tok);
  }
  async function hearIt() {
    const it = current();
    if (!it) { announce("Choose a line first."); return; }
    const text = el.final.value;
    if (!text.trim()) { announce("There is no text to hear."); return; }
    stopPlayback();
    const tok = S.seq;
    el["btn-hear"].setAttribute("aria-busy", "true");
    el["btn-hear"].disabled = true;
    announce("Making the voice for this line. This can take a few seconds.");
    const r = await api("POST", `/api/projects/${encodeURIComponent(S.pid)}/items/${encodeURIComponent(it.id)}/hear`, { text });
    el["btn-hear"].removeAttribute("aria-busy");
    el["btn-hear"].disabled = false;
    if (!r.ok || !r.data.audio) { announce(`Could not make the voice: ${detailOf(r)}`); return; }
    if (S.selectedId === it.id && el.final.value === text && r.data.check) {
      S.check = r.data.check; S.checkText = text; S.checkFor = it.id; S.checkState = "ready";
      renderCheck();
    }
    if (tok !== S.seq) return;
    announce(`Measured with the voice: ${fmtSec(r.data.duration_ms / 1000)}. ${r.data.check ? summarize(r.data.check) : ""}`);
    if (isDescription(it)) {
      const startMs = r.data.start_ms;
      await playVideoRange(Math.max(0, startMs - CONTEXT_MS), startMs, tok);
      if (tok !== S.seq) return;
      await playClip(r.data.audio, tok);
      if (tok !== S.seq) return;
      const after = it.extended ? startMs : startMs + r.data.duration_ms;
      await playVideoRange(after, Math.min(S.analysis.duration_ms, after + CONTEXT_MS), tok);
    } else {
      await playClip(r.data.audio, tok);
    }
  }
  function togglePlay() {
    if (!el.clip.paused) { stopPlayback(); return; }
    stopPlayback();
    if (el.video.paused) el.video.play().catch(() => announce("The browser did not let the video play."));
    else el.video.pause();
  }
  function frameStep(dir) {
    stopPlayback();
    el.video.pause();
    const fps = (S.analysis && S.analysis.fps) || 30;
    el.video.currentTime = Math.max(0, el.video.currentTime + dir / fps);
  }

  // ------------------------------------------------------------------ gate and render
  function showGate(nodes, good) {
    const g = el["gate-result"];
    g.hidden = false;
    g.className = `gate-result ${good ? "good" : "bad"}`;
    g.replaceChildren(...nodes);
  }
  function countsText(counts) {
    const names = { approved: "approved by a person", auto_approved: "approved automatically", rejected: "rejected", pending: "pending", needs_revision: "needing revision" };
    return Object.entries(counts || {}).map(([k, v]) => `${v} ${names[k] || k}`).join(", ");
  }
  el["btn-complete"].addEventListener("click", async () => {
    await S.saveChain;
    const r = await api("POST", `/api/projects/${encodeURIComponent(S.pid)}/review/complete`);
    const d = r.data || {};
    if (r.ok && d.ok) {
      const msg = `Review complete. Every line has a decision. ${countsText(d.counts)}. ` +
        `Reviewed by a person: ${d.human_reviewed ? "yes" : "no"}. You can render now.`;
      showGate([h("p", { text: msg })], true);
      el["gate-result"].dataset.ok = "true";
      announce(msg);
    } else if (r.status === 409 && Array.isArray(d.blocking)) {
      const n = d.blocking.length;
      const msg = `Review not complete: ${plural(n, "line is", "lines are")} still waiting for a person.`;
      showGate([h("p", { text: msg }), h("ul", null, ...d.blocking.map((id) => h("li", null,
        h("button", { type: "button", onclick: () => { S.statusFilter = "all"; S.kindFilter = "all"; renderFilters(); selectItem(id); focusItemButton(id); } }, `Go to ${id}`))))], false);
      el["gate-result"].dataset.ok = "false";
      announce(msg);
    } else {
      showGate([h("p", { text: `Could not check the review: ${detailOf(r)}` })], false);
      el["gate-result"].dataset.ok = "false";
      announce(`Could not check the review: ${detailOf(r)}`);
    }
  });
  function plainRefusal(detail) {
    const m = /(\d+) item\(s\) still pending/.exec(detail || "");
    if (m) {
      const n = Number(m[1]);
      return `Can't render yet: ${plural(n, "line is", "lines are")} still waiting for a person.`;
    }
    if (/no validation/.test(detail || "")) return "Can't render yet: press Mark review complete first.";
    if (/stale/.test(detail || "")) return "Can't render yet: lines changed after the last check. Press Mark review complete again.";
    return `Can't render yet: ${detail || "the server refused."}`;
  }
  el["btn-render"].addEventListener("click", async () => {
    const b = el["btn-render"];
    b.disabled = true;
    b.setAttribute("aria-busy", "true");
    announce("Rendering. This can take a minute.");
    await S.saveChain;
    const r = await api("POST", `/api/projects/${encodeURIComponent(S.pid)}/render`);
    b.disabled = false;
    b.removeAttribute("aria-busy");
    if (r.ok) {
      const vs = Object.entries(r.data.versions || {});
      const bad = vs.filter(([, ok]) => !ok).map(([k]) => k);
      const msg = r.data.ok ? `Rendered ${plural(vs.length, "version", "versions")}.`
        : `Rendered with problems: ${bad.join(", ")} did not pass.`;
      showGate([h("p", { text: msg })], !!r.data.ok);
      announce(msg);
    } else if (r.status === 409) {
      const msg = plainRefusal(r.data.detail);
      showGate([h("p", { text: msg })], false);
      announce(msg);
    } else {
      const msg = `Render failed: ${detailOf(r)}`;
      showGate([h("p", { text: msg })], false);
      announce(msg);
    }
  });

  // ------------------------------------------------------------------ buttons
  el["btn-approve"].addEventListener("click", () => decide("approved"));
  el["btn-reject"].addEventListener("click", () => decide("rejected"));
  el["btn-revise"].addEventListener("click", () => decide("needs_revision"));
  el["btn-edit"].addEventListener("click", () => editText());
  el["btn-context"].addEventListener("click", () => playInContext());
  el["btn-hear"].addEventListener("click", () => hearIt());
  el["btn-lowest"].addEventListener("click", () => jumpLowest());
  function editText() {
    if (!current()) { announce("Choose a line first."); return; }
    el.final.focus();
    const n = el.final.value.length;
    el.final.setSelectionRange(n, n);
  }

  // Add a line (E12 "from scratch", and any reviewer): native modal <dialog>, starts at the playhead.
  let addReturn = null;
  function openAdd() {
    if (!S.pid || el.add.open) return;
    addReturn = document.activeElement;
    const t = Math.max(0, el.video.currentTime || 0);
    el["add-start"].value = t.toFixed(1);
    el["add-end"].value = (t + 3).toFixed(1);
    el["add-text"].value = "";
    el["add-error"].hidden = true;
    el.video.pause();
    el.add.showModal();
    el["add-text"].focus();
  }
  function closeAdd() { if (el.add.open) el.add.close(); }
  el["btn-add"].addEventListener("click", openAdd);
  el["add-cancel"].addEventListener("click", closeAdd);
  el.add.addEventListener("close", () => {
    if (addReturn && document.contains(addReturn)) addReturn.focus();
    addReturn = null;
  });
  el["add-form"].addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const a = Math.round(Number(el["add-start"].value) * 1000);
    const b = Math.round(Number(el["add-end"].value) * 1000);
    const text = el["add-text"].value.trim();
    const fail = (msg) => { el["add-error"].textContent = msg; el["add-error"].hidden = false; };
    if (!text) { fail("Write the line first."); el["add-text"].focus(); return; }
    if (!(b > a)) { fail("The end must be after the start."); el["add-end"].focus(); return; }
    const r = await api("POST", `/api/projects/${encodeURIComponent(S.pid)}/items`,
      { kind: "ad", lang: "en", anchor_ms: a, end_ms: b, text });
    if (!r.ok) { fail(`Not added: ${detailOf(r)}`); return; }
    addReturn = null;
    closeAdd();
    await reloadItems();
    if (S.byId.has(r.data.item_id)) selectItem(r.data.item_id);
    announce(`Line added at ${fmtTime(a)}. It is waiting for review.`);
  });

  // Help dialog: native modal <dialog>; focus goes to Close, Esc closes, focus returns.
  let helpReturn = null;
  function openHelp() {
    if (el.help.open) return;
    helpReturn = document.activeElement;
    el.help.showModal();
    el["help-close"].focus();
  }
  el["btn-help"].addEventListener("click", openHelp);
  el.help.addEventListener("close", () => {
    if (helpReturn && document.contains(helpReturn)) helpReturn.focus();
    helpReturn = null;
  });

  // ------------------------------------------------------------------ keyboard (PLAN §12.2)
  function isTextField(t) {
    if (!t || !t.tagName) return false;
    if (t.isContentEditable) return true;
    const tag = t.tagName;
    if (tag === "TEXTAREA" || tag === "SELECT") return true;
    if (tag === "INPUT") return !["checkbox", "radio", "button", "submit", "reset", "range", "file", "color"].includes(t.type);
    return false;
  }
  document.addEventListener("keydown", (e) => {
    if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return;
    if (el.help.open || el.add.open) return; // the dialog handles Esc itself
    const t = e.target;
    if (isTextField(t)) {
      if (e.key === "Escape") { e.preventDefault(); focusList(); }
      return;
    }
    if (el.workspace.hidden) { if (e.key === "?") { e.preventDefault(); openHelp(); } return; }
    const tag = t && t.tagName;
    switch (e.key) {
      case " ":
        if (tag === "VIDEO" || tag === "SUMMARY" || tag === "INPUT") return; // native Space there
        e.preventDefault(); togglePlay(); break;
      case ",": e.preventDefault(); frameStep(-1); break;
      case ".": e.preventDefault(); frameStep(1); break;
      case "[": e.preventDefault(); step(-1); break;
      case "]": e.preventDefault(); step(1); break;
      case "a": e.preventDefault(); decide("approved"); break;
      case "r": e.preventDefault(); decide("rejected"); break;
      case "n": e.preventDefault(); decide("needs_revision"); break;
      case "e": e.preventDefault(); editText(); break;
      case "p": e.preventDefault(); playInContext(); break;
      case "h": e.preventDefault(); hearIt(); break;
      case "l": e.preventDefault(); jumpLowest(); break;
      case "?": e.preventDefault(); openHelp(); break;
      case "i": e.preventDefault(); openAdd(); break;
      default: break;
    }
  });

  start();
})();
