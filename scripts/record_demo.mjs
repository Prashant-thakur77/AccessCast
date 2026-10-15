// Record the demo video's screen segments with Playwright (1920×1080, real keyboard input, no mouse tricks).
// Usage: SITE=http://127.0.0.1:8080 REVIEW=http://127.0.0.1:8081 PROJECT=<sha12> node scripts/record_demo.mjs
// Output: data/demo/<segment>.webm (git-ignored). scripts/make_demo_video.py assembles them with narration.
import { mkdirSync, renameSync, readdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const out = resolve(root, "data/demo");
mkdirSync(out, { recursive: true });
const SITE = process.env.SITE || "http://127.0.0.1:8080";
const REVIEW = process.env.REVIEW || "";
const PROJECT = process.env.PROJECT || "";
const size = { width: 1920, height: 1080 };

async function segment(name, fn) {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: size, recordVideo: { dir: out, size }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  try {
    await fn(page);
  } finally {
    const v = page.video();
    await ctx.close();
    await browser.close();
    if (v) renameSync(await v.path(), resolve(out, `${name}.webm`));
    console.log(`recorded ${name}`);
  }
}

const pause = (p, ms) => p.waitForTimeout(ms);

// 0:30–1:20 Same 20 seconds, five ways
await segment("five_ways", async (p) => {
  await p.goto(`${SITE}/five-ways.html${PROJECT ? `?p=${PROJECT}` : ""}`);
  await pause(p, 1500);
  await p.keyboard.press("Tab");
  const start = p.getByRole("button", { name: /start|play/i }).first();
  await start.focus();
  await p.keyboard.press("Enter");
  await pause(p, 48000);
});

// Picker: blind standard → extended → Italiano, with the decisions drawer
await segment("player_picker", async (p) => {
  await p.goto(`${SITE}/?audience=blind${PROJECT ? `&p=${PROJECT}` : ""}`);
  await pause(p, 2000);
  const v = p.locator("video");
  await v.evaluate((el) => el.play());
  await pause(p, 6000);
  await p.getByRole("radio", { name: /extended/i }).check();
  await pause(p, 6000);
  await p.getByRole("button", { name: /italiano/i }).click();
  await pause(p, 6000);
});

await segment("decisions_drawer", async (p) => {
  await p.goto(`${SITE}/?audience=judge${PROJECT ? `&p=${PROJECT}` : ""}`);
  await pause(p, 2500);
  await p.getByRole("button", { name: /code caught/i }).first().click().catch(() => {});
  await pause(p, 1500);
  await p.mouse.wheel(0, 700);
  await pause(p, 8000);
});

if (REVIEW && PROJECT) {
  await segment("review_keyboard", async (p) => {
    await p.goto(`${REVIEW}/app/index.html?p=${PROJECT}`);
    await pause(p, 2500);
    for (let i = 0; i < 3; i++) {
      await p.keyboard.press("]");
      await pause(p, 1800);
    }
    await p.keyboard.press("a");
    await pause(p, 2500);
    await p.getByRole("button", { name: /render/i }).click().catch(() => {});
    await pause(p, 4000);
  });
}

await segment("proof", async (p) => {
  await p.goto(`${SITE}/proof.html`);
  await pause(p, 2500);
  const run = p.getByRole("button", { name: /run the attack/i });
  if (await run.isEnabled().catch(() => false)) {
    await run.click();
    await pause(p, 60000);
  } else {
    await pause(p, 6000);
  }
});

console.log(readdirSync(out).filter((f) => f.endsWith(".webm")).join("\n"));
