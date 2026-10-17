// Render docs/demo/motion/index.html scenes frame by frame (30 fps, transparent background) into
// data/demo/motion/<scene>/%05d.png. Numbers come from evidence/public-claims.json; a missing claim stops the render.
// Usage: node scripts/render_motion.mjs [scene ...]   (needs a static server on the repo root: MOTION_BASE)
import { mkdirSync, readFileSync, rmSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const BASE = process.env.MOTION_BASE || "http://127.0.0.1:8094";
const FPS = 30;
const claims = Object.fromEntries(
  JSON.parse(readFileSync(resolve(root, "evidence/public-claims.json"), "utf8")).claims.map((c) => [c.claim_id, c]),
);
const all = ["p_upload", "p_blind", "p_deaf", "p_read", "p_cost", "split", "pipeline", "amd", "res_neg", "laws", "close"];
const scenes = process.argv.slice(2).length ? process.argv.slice(2) : all;

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
await page.goto(`${BASE}/docs/demo/motion/index.html`);
await page.evaluate(() => document.fonts.ready);
for (const scene of scenes) {
  const dur = await page.evaluate(([c, s]) => window.__setup(c, s), [claims, scene]);
  await page.evaluate(() => Promise.all([...document.images].map((i) => (i.complete ? 0 : new Promise((r) => (i.onload = i.onerror = r))))));
  await page.waitForTimeout(300); // background images and fonts settle
  const dir = resolve(root, "data/demo/motion", scene);
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir, { recursive: true });
  const n = Math.round(dur * FPS);
  for (let f = 0; f < n; f++) {
    await page.evaluate((t) => window.__seek(t), f / FPS);
    await page.screenshot({ path: `${dir}/${String(f).padStart(5, "0")}.png`, omitBackground: true });
  }
  console.log(`${scene}: ${n} frames`);
}
await browser.close();
if (errors.length) {
  console.error(errors.join("\n"));
  process.exit(1);
}
