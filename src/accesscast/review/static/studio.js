// AccessCast Studio: upload a video, poll the job, show each stage in plain words, announce changes.
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const STATE_WORDS = { waiting: "Waiting", running: "Working", done: "Done", skipped: "Not run", failed: "Failed" };
  let lastStates = {};
  let timer = null;

  function announce(msg) { $("status").textContent = msg; }

  function fmt(s) { return s < 60 ? `${s.toFixed(1)} s` : `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`; }

  function renderStages(stages) {
    const ol = $("stages");
    ol.replaceChildren();
    for (const st of stages) {
      const li = document.createElement("li");
      li.dataset.state = st.state;
      const state = document.createElement("span");
      state.className = "state";
      state.textContent = STATE_WORDS[st.state] || st.state;
      const label = document.createElement("span");
      label.textContent = st.label;
      const secs = document.createElement("span");
      secs.className = "muted";
      secs.textContent = st.seconds != null ? fmt(st.seconds) : "";
      li.append(state, label, secs);
      if (st.note) {
        const n = document.createElement("span");
        n.className = "note";
        n.textContent = st.note;
        li.append(n);
      }
      ol.append(li);
      const before = lastStates[st.stage];
      if (before && before !== st.state && (st.state === "done" || st.state === "failed")) {
        announce(`${st.label}: ${STATE_WORDS[st.state].toLowerCase()}.`);
      }
      lastStates[st.stage] = st.state;
    }
  }

  function renderLines(lines) {
    const tb = $("lines").querySelector("tbody");
    tb.replaceChildren();
    for (const [name, v] of Object.entries(lines)) {
      const waiting = (v.by_status.pending || 0) + (v.by_status.needs_revision || 0);
      const passed = (v.by_status.auto_approved || 0);
      const tr = document.createElement("tr");
      const th = document.createElement("th");
      th.scope = "row";
      th.textContent = name;
      tr.append(th);
      for (const val of [v.total, v.repaired, waiting, passed]) {
        const td = document.createElement("td");
        td.textContent = String(val);
        tr.append(td);
      }
      tb.append(tr);
    }
  }

  async function poll() {
    let r;
    try {
      r = await fetch("/api/studio/jobs/current");
    } catch (e) {
      announce("Lost contact with the Studio server. Is `make review` still running?");
      return;
    }
    const d = await r.json();
    const j = d.job;
    if (!j) return;
    $("run").hidden = false;
    const who = j.fake ? "fake mode: canned answers, no model is asked"
      : `Gemma 4 31B on ${j.provider === "tokenfactory" ? "AMD Token Factory" : j.provider}`;
    $("run-summary").textContent = `${j.name} · ${fmt(j.elapsed_s)} so far · ${who}`;
    $("fake-banner").hidden = !j.fake;
    renderStages(j.stages);
    $("gemma").textContent = j.fake
      ? `Canned answers used: ${j.gemma.answered} (fake mode; nothing here came from a model).`
      : `Gemma calls answered: ${j.gemma.answered}. Calls that failed (retried, or the line goes to a person): ${j.gemma.failed}.`;
    if (j.status !== "running") {
      clearInterval(timer);
      timer = null;
      $("go").disabled = false;
      $("done").hidden = false;
      renderLines(j.lines);
      $("review-link").href = `index.html?p=${encodeURIComponent(j.project)}`;
      if (j.status === "done") {
        announce(`Finished in ${fmt(j.elapsed_s)}. Every line is waiting for review; nothing is published yet.`);
      } else {
        announce(`The run stopped with an error (exit code ${j.exit_code}). The log is below.`);
        $("log").hidden = false;
        $("log").textContent = j.log_tail || "";
      }
      $("done-h").focus();
    }
  }

  $("done-h").tabIndex = -1;
  $("up-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = $("file").files[0];
    if (!f) { announce("Choose a video first."); return; }
    $("go").disabled = true;
    $("done").hidden = true;
    lastStates = {};
    announce(`Uploading ${f.name}…`);
    let r;
    try {
      r = await fetch(`/api/studio/jobs?name=${encodeURIComponent(f.name)}`, { method: "POST", body: f });
    } catch (e) {
      $("go").disabled = false;
      announce("Upload failed: the Studio server did not answer.");
      return;
    }
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      $("go").disabled = false;
      announce(`Not started: ${body.detail || r.status}.`);
      return;
    }
    const j = await r.json();
    announce(`Started: ${j.name}, ${fmt(j.seconds)} long. Each step is listed below as it runs.`);
    if (!timer) timer = setInterval(poll, 1000);
    poll();
  });
  // Re-attach to a job that is already running (page reloaded).
  fetch("/api/studio/jobs/current").then((r) => r.json()).then((d) => {
    if (d.job) {
      if (d.job.status === "running") { $("go").disabled = true; timer = setInterval(poll, 1000); }
      poll();
    }
  }).catch(() => {});
})();
