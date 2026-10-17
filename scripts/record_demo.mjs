// Record the demo video's screen segments with Playwright (1920×1080, real keyboard input, no mouse tricks).
// Usage: SITE=http://127.0.0.1:8080 REVIEW=http://127.0.0.1:8081 PROJECT=<sha12> node scripts/record_demo.mjs
// Output: data/demo/<segment>.webm (git-ignored). scripts/make_demo_video.py assembles them with narration.
import { mkdirSync, renameSync, readdirSync, writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const out = resolve(root, "data/demo");
mkdirSync(out, { recursive: true });
const SITE = process.env.SITE || "http://127.0.0.1:8080";
const REVIEW = process.env.REVIEW || "";
const PROJECT = process.env.PROJECT || "";
const size = { width: 1280, height: 720 }; // recorded larger on screen, scaled to 1080p
const video = { width: 1920, height: 1080 };

const ONLY = (process.env.ONLY || "").split(",").filter(Boolean); // e.g. ONLY=five_ways,proof

async function segment(name, fn) {
  if (ONLY.length && !ONLY.includes(name)) return;
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: size, recordVideo: { dir: out, size } });
  const page = await ctx.newPage();
  // Marks: seconds from the start of the recording, read by make_demo_video.py ("mark" in a storyboard scene).
  const t0 = Date.now();
  const marks = {};
  page.mark = (label) => { marks[label] = (Date.now() - t0) / 1000; };
  try {
    await fn(page);
  } finally {
    writeFileSync(resolve(out, `${name}.marks.json`), JSON.stringify(marks, null, 1));
    const v = page.video();
    await ctx.close();
    await browser.close();
    if (v) renameSync(await v.path(), resolve(out, `${name}.webm`));
    console.log(`recorded ${name}`);
  }
}

const pause = (p, ms) => p.waitForTimeout(ms);

// Same clip, five ways: every version, each at its telling moment. The page plays the excerpt from its start for
// each version; for the caption and subtitle versions we scrub to the first spoken line, as a viewer could.
const SPOKEN_S = Number(process.env.FIVE_WAYS_SPOKEN_S || 37); // Sintel draft: first caption with words at 37.5 s
const playingFrom = (p, t) =>
  p.waitForFunction(
    (t) => { const v = document.getElementById("video"); return v.readyState >= 3 && !v.paused && v.currentTime >= t; },
    t,
    { timeout: 30000 },
  );
await segment("five_ways", async (p) => {
  await p.goto(`${SITE}/five-ways.html${PROJECT ? `?p=${PROJECT}` : ""}`);
  await p.evaluate(() => { document.body.style.zoom = "0.8"; });  // the player and its captions clear the narration captions
  await pause(p, 2500);
  p.mark("page");
  await p.locator("#b-start").focus();
  await p.keyboard.press("Enter");
  await p.evaluate(() => {  // the heading and the whole picture in view
    const w = document.getElementById("who");
    window.scrollTo(0, w.getBoundingClientRect().top + window.scrollY - 12);
  });
  const segStart = await p.evaluate(() => document.getElementById("video").currentTime);
  await playingFrom(p, Math.max(0, segStart - 0.5));
  p.mark("blind");
  await pause(p, 8000);
  for (const step of ["deaf", "easy", "hi", "it"]) {
    await p.evaluate(() => document.getElementById("b-skip").focus({ preventScroll: true }));
    await p.keyboard.press("Enter");
    await pause(p, 300);
    await playingFrom(p, 0);
    await p.evaluate((t) => { document.getElementById("video").currentTime = t; }, SPOKEN_S);
    await playingFrom(p, SPOKEN_S);
    p.mark(step);
    await pause(p, 7000);
  }
});

// The home page: what a viewer sees first (hero, then the five ways in).
await segment("home", async (p) => {
  await p.goto(`${SITE}/index.html`);
  await pause(p, 2500);
  p.mark("page");
  await pause(p, 7000);  // the hero alone for the whole narration line; the reveal below starts after the scroll
  await p.evaluate(() => window.scrollBy({ top: 650, behavior: "smooth" }));
  await pause(p, 3000);
  p.mark("scrolled");
  await p.evaluate(() => window.scrollBy({ top: 650, behavior: "smooth" }));
  await pause(p, 4000);
});

// How it works: one real clip, step by step (how.html), each step brought to the top and held for its narration.
const HOW_P = process.env.HOW_PROJECT || "dac08bcd9d7a";
await segment("how", async (p) => {
  await p.goto(`${SITE}/how.html?p=${HOW_P}`);
  await p.evaluate(() => { document.body.style.zoom = "0.8"; });  // each step clears the narration captions
  await p.waitForFunction(() => document.querySelectorAll("#repairs > li").length > 0, null, { timeout: 30000 });
  await p.evaluate(() => Promise.all([...document.images].map((i) => (i.complete ? 0 : new Promise((r) => (i.onload = i.onerror = r))))));
  await pause(p, 1500);
  p.mark("page");
  await pause(p, 4000);
  for (const id of ["s-listen", "s-pauses", "s-look", "s-write", "s-check", "s-repair", "s-fit", "s-person", "s-out"]) {
    await p.evaluate((id) => {
      const el = document.getElementById(id);
      window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - 12, behavior: "smooth" });
    }, id);
    await pause(p, 900);
    p.mark(id);
    await pause(p, 9000);
  }
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

await segment("site_drawer", async (p) => {
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

// Studio: a finished job on the review server (start it with `make review`, run one dev clip through the Studio first)
if (REVIEW) {
  await segment("studio", async (p) => {
    await p.goto(`${REVIEW}/app/studio.html`);
    await pause(p, 3000);
    await p.mouse.wheel(0, 500);
    await pause(p, 5000);
    await p.mouse.wheel(0, 900);
    await pause(p, 5000);
  });
}

await segment("proof", async (p) => {
  await p.goto(`${SITE}/proof.html`);
  await pause(p, 2500);
  p.mark("page");
  const run = p.locator("#b-attack");
  if (await run.isEnabled().catch(() => false)) {
    await p.evaluate(() => {
      const h = document.getElementById("live-h");
      window.scrollTo(0, h.getBoundingClientRect().top + window.scrollY - 12);
    });
    await run.focus({ preventScroll: true }).catch(() => run.focus());
    await p.keyboard.press("Enter");
    p.mark("pressed");
    await p.waitForFunction(
      () => /Done|did not answer/.test(document.getElementById("status").textContent || ""),
      null,
      { timeout: 120000 },
    );
    p.mark("done");
    await pause(p, 1500);
    await p.evaluate(() => {
      const r = document.getElementById("live-result");
      window.scrollTo(0, r.getBoundingClientRect().top + window.scrollY - 140);
    });
    p.mark("result");
    await pause(p, 12000);
    await p.mouse.wheel(0, 350);
    await pause(p, 6000);
  } else {
    // the recorded run: the test, Gemma's answer, the check, and what the repair published
    await p.locator("#last-h").scrollIntoViewIfNeeded();
    p.mark("result");
    await pause(p, 9000);
    await p.mouse.wheel(0, 350);
    await pause(p, 5000);
  }
});

// Try your own caption (proof page): typed with the keyboard, made live on AMD, every answer checked.
await segment("try", async (p) => {
  await p.goto(`${SITE}/proof.html`);
  await p.waitForFunction(() => !document.getElementById("b-try").disabled, null, { timeout: 30000 });
  await p.evaluate(() => {
    const h = document.getElementById("try-h");
    window.scrollTo(0, h.getBoundingClientRect().top + window.scrollY - 12);
  });
  await pause(p, 1200);
  p.mark("page");
  await p.locator("#try-text").focus();
  await p.keyboard.press("Control+A");
  await p.keyboard.type(process.env.TRY_TEXT || "Do not open the door before 5 pm. Press the green button twice to call for help.", { delay: 35 });
  p.mark("typed");
  await p.locator("#b-try").focus({ preventScroll: true });
  await p.keyboard.press("Enter");
  p.mark("pressed");
  await p.waitForFunction(() => /^Done|did not answer/.test(document.getElementById("try-status").textContent || ""), null, { timeout: 180000 });
  p.mark("done");
  await p.evaluate(() => {
    const r = document.getElementById("try-status");
    window.scrollTo({ top: r.getBoundingClientRect().top + window.scrollY - 20, behavior: "smooth" });
  });
  await pause(p, 1000);
  p.mark("result");
  await pause(p, 14000);
});

console.log(readdirSync(out).filter((f) => f.endsWith(".webm")).join("\n"));
