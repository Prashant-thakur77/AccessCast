// Screenshots for the README (docs/media/*.png) from the exported site, so the pictures show what the site really does.
// Usage: SITE=http://127.0.0.1:8096 LIVE=https://accesscast.vercel.app node scripts/readme_shots.mjs [name ...]
// SITE must support HTTP Range (video seeking). LIVE is used only for the Try box, which calls Gemma on AMD.
import { mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const out = resolve(root, "docs/media");
mkdirSync(out, { recursive: true });
const SITE = process.env.SITE || "http://127.0.0.1:8096";
const LIVE = process.env.LIVE || "https://accesscast.vercel.app";
const ONLY = process.argv.slice(2);

const browser = await chromium.launch();
async function shot(name, fn, viewport = { width: 1440, height: 900 }) {
  if (ONLY.length && !ONLY.includes(name)) return;
  const page = await browser.newPage({ viewport, deviceScaleFactor: 1.5 });
  try {
    await fn(page);
    console.log(`shot ${name}`);
  } catch (e) {
    console.error(`FAILED ${name}: ${e}`);
    process.exitCode = 1;
  } finally {
    await page.close();
  }
}
const at = (p, sel) => p.locator(sel).first();
const seek = (p, t) =>
  p.evaluate(async (t) => {
    const v = document.getElementById("video");
    if (v.readyState < 1) await new Promise((r) => v.addEventListener("loadedmetadata", r, { once: true }));
    v.currentTime = t;
    await new Promise((r) => v.addEventListener("seeked", r, { once: true }));
    v.dispatchEvent(new Event("timeupdate"));
  }, t);

await shot("home", async (p) => {
  await p.goto(`${SITE}/index.html`);
  await p.waitForTimeout(2500);
  await p.screenshot({ path: `${out}/home.png` });
});

// The player for someone who can't see the screen, with the description text shown (Sintel draft, a described moment).
await shot("watch", async (p) => {
  await p.goto(`${SITE}/watch.html?p=cbf141ec3213&audience=blind`);
  await p.waitForTimeout(2000);
  await p.locator("#caption-settings summary").click();
  const desc = p.locator("#c-desctext");
  if (!(await desc.isChecked())) await desc.check();
  await p.locator("#caption-settings summary").click();  // closed again: the picture, not the settings
  await seek(p, 26.2);  // the line "A red-haired person…" is on from 25.2 s; the picture goes dark at 28 s
  await p.evaluate(async () => {  // play a moment so the frame is painted, then hold it
    const v = document.getElementById("video");
    v.muted = true;
    await v.play();
    await new Promise((r) => setTimeout(r, 300));
    v.pause();
  });
  await p.waitForTimeout(800);
  const box = await p.evaluate(() => {  // page coordinates (the page may have scrolled)
    const r = (s) => { const b = document.querySelector(s).getBoundingClientRect(); return { x: b.x + scrollX, y: b.y + scrollY, w: b.width, h: b.height }; };
    return { a: r(".video-frame"), b: r("#desc-visible") };
  });
  const { a, b } = box;
  await p.screenshot({ path: `${out}/watch.png`, fullPage: true, clip: { x: a.x - 8, y: a.y - 8, width: a.w + 16, height: b.y + b.h - a.y + 16 } });
});

// What the models decided: the drawer, opened on the first line.
await shot("drawer", async (p) => {
  await p.goto(`${SITE}/watch.html?p=dac08bcd9d7a&audience=blind`);
  await p.waitForTimeout(2000);
  await p.locator("#drawer-toggle").click();
  await p.waitForTimeout(800);
  const first = p.locator("#lines > li").first();
  await first.scrollIntoViewIfNeeded();
  const d = first.locator("details summary, button").first();
  if (await d.count()) await d.click().catch(() => {});
  await p.waitForTimeout(800);
  await first.screenshot({ path: `${out}/drawer.png` });  // one line: frames, pause, draft, checks, repair
}, { width: 1280, height: 1600 });

// How it works, on the NASA clip: the check that stopped a draft, and Gemma's repair.
await shot("how", async (p) => {
  await p.goto(`${SITE}/how.html?p=dac08bcd9d7a`);
  await p.waitForFunction(() => document.querySelectorAll("#repairs > li").length > 0, null, { timeout: 30000 });
  await p.waitForTimeout(1500);
  const a = await p.locator("#s-check").boundingBox();
  const b = await p.locator("#s-repair").boundingBox();
  await p.screenshot({
    path: `${out}/how.png`,
    fullPage: true,
    clip: { x: Math.min(a.x, b.x) - 12, y: a.y - 12, width: Math.max(a.width, b.width) + 24, height: b.y + b.height - a.y + 24 },
  });
}, { width: 1280, height: 900 });

await shot("results", async (p) => {
  await p.goto(`${SITE}/results.html`);
  await p.waitForTimeout(2500);
  const cards = p.locator(".result-card");
  const a = await cards.nth(0).boundingBox();
  const b = await cards.nth(1).boundingBox();
  await p.screenshot({ path: `${out}/results.png`, fullPage: true, clip: { x: a.x - 16, y: a.y - 16, width: a.width + 32, height: b.y + b.height - a.y + 32 } });
}, { width: 1280, height: 900 });

// The live Try box on the deployed site: one sentence, every version, made by Gemma on AMD and checked.
await shot("try", async (p) => {
  await p.goto(`${LIVE}/proof.html`);
  await p.waitForTimeout(2000);
  await p.locator("#try-text").fill("Do not open the door before 5 pm. Press the green button 2 times for help.");
  await p.locator("#try-form button[type=submit]").click();
  await p.waitForFunction(() => /^Done/.test(document.getElementById("try-status").textContent || ""), null, { timeout: 180000 });
  await p.waitForTimeout(1500);
  const res = p.locator("#try-result");
  await res.screenshot({ path: `${out}/try.png` });
}, { width: 1440, height: 1200 });

// "Describe a picture" on the deployed site: one sample picture, Gemma on AMD looks and writes, our rules check it.
await shot("describe", async (p) => {
  await p.goto(`${LIVE}/proof.html`);
  await p.waitForTimeout(2000);
  await p.getByRole("button", { name: "NASA: a slide with a question" }).click();
  await p.locator("#b-desc").click({ timeout: 30000 });
  await p.waitForFunction(() => /^(Done|The live)/.test(document.getElementById("desc-status").textContent || ""), null, { timeout: 180000 });
  await p.waitForTimeout(1000);
  const box = await p.evaluate(() => {
    const r = (s) => { const b = document.querySelector(s).getBoundingClientRect(); return { x: b.x + scrollX, y: b.y + scrollY, w: b.width, h: b.height }; };
    return { a: r("#desc-figure"), b: r("#desc-result") };
  });
  const { a, b } = box;
  await p.screenshot({ path: `${out}/describe.png`, fullPage: true, clip: { x: Math.min(a.x, b.x) - 12, y: a.y - 12, width: Math.max(a.w, b.w) + 24, height: b.y + b.h - a.y + 24 } });
}, { width: 1280, height: 1000 });

await browser.close();
