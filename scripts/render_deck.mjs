// Render docs/deck/deck.md → docs/deck/deck.html (accessible slides) → docs/deck/deck.pdf, and
// docs/cover.html → docs/cover.png. Usage: node scripts/render_deck.mjs
import { readFileSync, writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const inline = (s) => esc(s)
  .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
  .replace(/`([^`]+)`/g, "<code>$1</code>")
  .replace(/&lt;pending: ([^&]+)&gt;/g, '<span class="pending">[pending: $1]</span>');

function mdToHtml(md) {
  const lines = md.split("\n");
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (/^<!--/.test(l)) { i++; continue; }
    if (/^### /.test(l)) { out.push(`<h3>${inline(l.slice(4))}</h3>`); i++; continue; }
    if (/^## /.test(l)) { out.push(`<p class="sub">${inline(l.slice(3))}</p>`); i++; continue; }
    if (/^# /.test(l)) { out.push(`<h2>${inline(l.slice(2))}</h2>`); i++; continue; }
    if (/^\|/.test(l)) {
      const rows = [];
      while (i < lines.length && /^\|/.test(lines[i])) { rows.push(lines[i]); i++; }
      const cells = (r) => r.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const head = cells(rows[0]);
      const body = rows.slice(2).map(cells);
      out.push(`<table><thead><tr>${head.map((h) => `<th scope="col">${inline(h)}</th>`).join("")}</tr></thead><tbody>` +
        body.map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("") + "</tbody></table>");
      continue;
    }
    if (/^(\d+\.|-) /.test(l)) {
      const ordered = /^\d+\./.test(l);
      const items = [];
      while (i < lines.length && /^(\d+\.|-) /.test(lines[i])) { items.push(lines[i].replace(/^(\d+\.|-) /, "")); i++; }
      const tag = ordered ? "ol" : "ul";
      out.push(`<${tag}>${items.map((x) => `<li>${inline(x)}</li>`).join("")}</${tag}>`);
      continue;
    }
    if (l.trim()) out.push(`<p>${inline(l)}</p>`);
    i++;
  }
  return out.join("\n");
}

const css = `
:root{--bg:#0f1b33;--fg:#f4f6fb;--muted:#c9d3ea;--accent:#ffc857;--card:#18294d}
*{box-sizing:border-box}body{margin:0;background:#000;font-family:"DejaVu Sans",system-ui,sans-serif}
section{width:1600px;height:900px;background:var(--bg);color:var(--fg);padding:80px 100px;display:flex;flex-direction:column;
  gap:22px;page-break-after:always;break-after:page;position:relative;overflow:hidden}
h1,h2{font-size:58px;line-height:1.1;margin:0 0 10px}h1{font-size:96px}
.sub{font-size:40px;color:var(--accent);margin:0}
p,li{font-size:31px;line-height:1.35;margin:0}ul,ol{margin:0;padding-left:1.2em;display:flex;flex-direction:column;gap:14px}
table{border-collapse:collapse;font-size:28px;width:100%}th,td{border-bottom:2px solid #33476f;padding:12px 16px;text-align:left}
th{color:var(--accent)}code{font-size:.9em;background:var(--card);padding:2px 8px;border-radius:6px}
.pending{color:#ff9b9b;font-style:italic}
footer{position:absolute;bottom:34px;left:100px;right:100px;display:flex;justify-content:space-between;font-size:20px;color:var(--muted)}
@page{size:1600px 900px;margin:0}`;

const md = readFileSync(resolve(root, "docs/deck/deck.md"), "utf8");
const slides = md.split(/\n---\n/);
const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>AccessCast deck</title>
<style>${css}</style></head><body><main>` +
  slides.map((s, k) => `<section aria-label="Slide ${k + 1}">${mdToHtml(s.trim())}
  <footer><span>AccessCast · Gemma 4 on AMD Token Factory</span><span>${k + 1} / ${slides.length}</span></footer></section>`).join("\n") +
  "</main></body></html>";
writeFileSync(resolve(root, "docs/deck/deck.html"), html);

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
await page.goto("file://" + resolve(root, "docs/deck/deck.html"));
await page.pdf({ path: resolve(root, "docs/deck/deck.pdf"), width: "1600px", height: "900px", printBackground: true });
const cover = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await cover.goto("file://" + resolve(root, "docs/cover.html"));
await cover.screenshot({ path: resolve(root, "docs/cover.png") });
await browser.close();
console.log(`deck: ${slides.length} slides → docs/deck/deck.pdf; cover → docs/cover.png`);
