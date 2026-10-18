/* "Read it as text" (watch page): the version being played as one readable list, in time order, built from that
   version's own caption, subtitle and description tracks (the same files the player uses), with downloads. For
   reading, a screen reader or a braille display; nothing here is written on this side. */
(function () {
  "use strict";
  var AC = window.AC, el = AC.el;
  var $ = function (id) { return document.getElementById(id); };
  var KIND = { descriptions: "Description", captions: "Said", subtitles: "Said" };
  var current = null, lines = [];

  // WebVTT cues as {start (s), text}; cue settings, tags and NOTE blocks are dropped
  function parseVtt(txt) {
    var out = [];
    txt.replace(/\r/g, "").split(/\n\n+/).forEach(function (block) {
      var rows = block.split("\n");
      var i = -1;
      for (var k = 0; k < rows.length; k++) if (rows[k].indexOf("-->") >= 0) { i = k; break; }
      if (i < 0) return;
      var m = rows[i].match(/^(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)\s+-->/);
      if (!m) return;
      var start = (m[1] ? parseInt(m[1], 10) * 3600 : 0) + parseInt(m[2], 10) * 60 + parseFloat(m[3]);
      var text = rows.slice(i + 1).join(" ").replace(/<[^>]+>/g, "").trim();
      if (text) out.push({ start: start, text: text });
    });
    return out;
  }

  function stamp(s) { var m = Math.floor(s / 60), r = Math.floor(s % 60); return m + ":" + (r < 10 ? "0" : "") + r; }

  function downloads(d) {
    var ul = $("text-downloads");
    ul.textContent = "";
    var add = function (href, label, file) {
      ul.appendChild(el("li", null, [el("a", { href: href, download: file || "", text: label })]));
    };
    add(d.base + d.version.file, "Video: " + d.name + " (MP4)");
    (d.version.tracks || []).forEach(function (t) { add(d.base + t.file, t.label + " (WebVTT)"); });
    var blob = new Blob([lines.map(function (l) { return stamp(l.start) + "  " + l.who + ": " + l.text; }).join("\n") + "\n"], { type: "text/plain" });
    add(URL.createObjectURL(blob), "This text (.txt)", "accesscast-" + d.key + ".txt");
  }

  function render(d) {
    current = d;
    var tracks = (d.version.tracks || []).filter(function (t) { return KIND[t.kind]; });
    $("text-status").textContent = "Loading the text…";
    Promise.all(tracks.map(function (t) {
      return fetch(d.base + t.file).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.text(); })
        .then(function (txt) { return parseVtt(txt).map(function (c) { return { start: c.start, text: c.text, who: KIND[t.kind], lang: t.srclang }; }); });
    })).then(function (parts) {
      if (current !== d) return;  // the viewer switched again meanwhile
      lines = [].concat.apply([], parts).sort(function (a, b) { return a.start - b.start || (a.who === "Description" ? -1 : 1); });
      var ol = $("text-lines");
      ol.textContent = "";
      lines.forEach(function (l) {
        ol.appendChild(el("li", { class: l.who === "Description" ? "is-desc" : "is-said" }, [
          el("time", { text: stamp(l.start) }),
          el("span", null, [el("span", { class: "who", text: l.who + ": " }), el("span", { lang: l.lang, text: l.text })])
        ]));
      });
      $("text-status").textContent = lines.length + " lines from " + d.name + ".";
      downloads(d);
    }).catch(function (err) {
      $("text-status").textContent = "The text could not be loaded (" + err.message + "). The video and its tracks still play above.";
    });
  }

  document.addEventListener("ac:version", function (e) { render(e.detail); });
  $("text-toggle").addEventListener("click", function () {
    var open = this.getAttribute("aria-expanded") !== "true";
    this.setAttribute("aria-expanded", open ? "true" : "false");
    $("text-body").hidden = !open;
  });
})();
