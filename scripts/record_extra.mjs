// Two demo segments from the local review server (start it on projects/_studio_demo first):
// the Studio after a real run, and one real repair in the review app. Usage: REVIEW=http://127.0.0.1:8081 PROJECT=<sha12> ITEM=<id> node scripts/record_extra.mjs
import { mkdirSync, renameSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const out = resolve(root, "data/demo");
mkdirSync(out, { recursive: true });
const REVIEW = process.env.REVIEW || "http://127.0.0.1:8081";
const size = { width: 1280, height: 720 };
async function segment(name, fn) {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: size, recordVideo: { dir: out, size } });
  const page = await ctx.newPage();
  try { await fn(page); } finally {
    const v = page.video(); await ctx.close(); await browser.close();
    if (v) renameSync(await v.path(), resolve(out, `${name}.webm`));
    console.log(`recorded ${name}`);
  }
}
const pause = (p, ms) => p.waitForTimeout(ms);
await segment("studio", async (p) => {
  await p.goto(`${REVIEW}/app/studio.html`);
  await pause(p, 3000);
  await p.locator("#run").scrollIntoViewIfNeeded();
  await pause(p, 6000);
  await p.locator("#done").scrollIntoViewIfNeeded();
  await pause(p, 6000);
});
await segment("decisions_drawer", async (p) => {
  await p.goto(`${REVIEW}/app/index.html?p=${process.env.PROJECT}`);
  await p.locator("#workspace").waitFor();
  await pause(p, 1500);
  await p.locator(`[data-id="${process.env.ITEM}"]`).first().click();
  await pause(p, 2000);
  await p.locator("#repairs").scrollIntoViewIfNeeded();
  await pause(p, 9000);
});
