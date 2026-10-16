import { test, expect, type Page, type Locator } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function axeViolations(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"])
    .analyze();
  return results.violations.map((v) => ({
    id: v.id,
    impact: v.impact,
    help: v.help,
    nodes: v.nodes.map((n) => n.target.join(" ")),
  }));
}

/** Press Tab until `target` has focus (keyboard only, no clicks). */
async function tabTo(page: Page, target: Locator, max = 80) {
  for (let i = 0; i < max; i++) {
    await page.keyboard.press("Tab");
    if (await target.evaluate((el) => el === document.activeElement)) return;
  }
  throw new Error(`could not reach ${target} with Tab in ${max} presses`);
}

const status = (page: Page) => page.locator("#status");
const videoSrc = (page: Page) => page.locator("#video").getAttribute("src");

for (const scheme of ["light", "dark"] as const) {
  test.describe(`axe-core (${scheme})`, () => {
    test.use({ colorScheme: scheme });

    test("player: picker and drawer open", async ({ page }) => {
      await page.goto("/watch.html?audience=judge,blind,easy");
      await expect(page.locator("#judge-banner")).toBeVisible();
      await expect(page.locator("#drawer-body")).toBeVisible();
      await expect(page.locator("#lines > li").first()).toBeVisible();
      await expect(page.locator("#sub-blind")).toBeVisible();
      await expect(page.locator("#sub-easy")).toBeVisible();
      await page.locator("#caption-settings > summary").click();
      expect(await axeViolations(page)).toEqual([]);
    });

    test("five ways", async ({ page }) => {
      await page.goto("/five-ways.html");
      await expect(page.locator("#steps > li")).toHaveCount(5);
      expect(await axeViolations(page)).toEqual([]);
    });

    test("proof", async ({ page }) => {
      await page.goto("/proof.html");
      await expect(page.locator("#last-run")).not.toContainText("Loading");
      expect(await axeViolations(page)).toEqual([]);
    });

    test("landing: every section, in its own colour world", async ({ page }) => {
      await page.goto("/index.html");
      await expect(page.locator("#l-play")).toBeEnabled();
      await expect(page.locator("#results-rows .big-row")).toHaveCount(5);
      await expect(page.locator("#ex-result .stamp")).toBeVisible();
      await page.waitForTimeout(1200);
      expect(await axeViolations(page)).toEqual([]);
      for (const [id, world] of [["listen", "blind"], ["who", "paper"], ["how", "easy"], ["rules", "deaf"], ["results", "paper"], ["law", "it"], ["proof-teaser", "blind"]]) {
        await page.locator(`#${id}`).evaluate((n) => n.scrollIntoView({ block: "start" }));
        await page.mouse.wheel(0, 200);
        await expect(page.locator("body")).toHaveAttribute("data-world", world);
        await page.waitForTimeout(1200);
        expect(await axeViolations(page), id).toEqual([]);
      }
    });

    test("watch: each audience colour world", async ({ page }) => {
      for (const a of ["blind", "deaf", "easy", "hi", "it"]) {
        await page.goto(`/watch.html?audience=${a}`);
        await expect(page.locator("body")).toHaveAttribute("data-world", a);
        await expect(page.locator(`#t-${a}`)).toHaveAttribute("aria-pressed", "true");
        await page.waitForTimeout(1000);
        expect(await axeViolations(page), a).toEqual([]);
      }
    });
  });
}

test("proof page never fakes a run", async ({ page }) => {
  await page.goto("/proof.html");
  await expect(page.locator("#b-attack")).toBeDisabled();
  await expect(page.locator("#live-state")).toContainText("not connected");
  await expect(page.locator("#last-run")).toContainText("No recorded run yet.");
});

test("disclosure banner is always visible for drafts", async ({ page }) => {
  await page.goto("/watch.html");
  await expect(page.locator("#disclosure")).toContainText("UNREVIEWED DRAFT");
});

test("no horizontal scroll at 360 px", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  for (const path of ["/index.html", "/watch.html?audience=judge,blind,easy", "/five-ways.html", "/proof.html"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, path).toBeLessThanOrEqual(0);
  }
});

test("keyboard only: pick profiles, open the drawer, jump to a line", async ({ page }) => {
  await page.goto("/watch.html");
  await expect(status(page)).toContainText("Now playing");
  const src0 = await videoSrc(page);

  // 1. "I can't see the screen"
  const blind = page.locator("#t-blind");
  await tabTo(page, blind);
  await page.keyboard.press("Space");
  await expect(blind).toHaveAttribute("aria-pressed", "true");
  await expect(status(page)).toContainText("Now playing: English, with audio description.");
  const src1 = await videoSrc(page);
  expect(src1).not.toBe(src0);
  expect(src1).toContain("blind.en.mp4");

  // 2. Extended (radio group: Tab lands on the checked radio, arrow keys change it)
  const standard = page.locator('input[name="blindmode"][value="standard"]');
  await tabTo(page, standard);
  await page.keyboard.press("ArrowDown");
  await expect(page.locator("#r-extended")).toBeChecked();
  await expect(status(page)).toContainText("extended audio description");
  expect(await videoSrc(page)).toContain("blind_ext.en.mp4");

  // 3. Italiano
  const it = page.locator("#t-it");
  await tabTo(page, it);
  await page.keyboard.press("Space");
  await expect(it).toHaveAttribute("aria-pressed", "true");
  await expect(status(page)).toContainText("Now playing: Italian version.");
  expect(await videoSrc(page)).toContain("/it.mp4");

  // 4. Open the drawer
  const drawer = page.locator("#drawer-toggle");
  await tabTo(page, drawer);
  await page.keyboard.press("Enter");
  await expect(drawer).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator("#lines > li").first()).toBeVisible();

  // 5. Activate a line: the video seeks and the live region says so
  const seek = page.locator("#lines button.seek").last();
  await tabTo(page, seek, 200);
  const before = await status(page).textContent();
  await page.keyboard.press("Enter");
  await expect(status(page)).toContainText("Moved to");
  expect(await status(page).textContent()).not.toBe(before);
  await expect(page.locator("#video")).toBeFocused();
});

test("old player links redirect to watch.html", async ({ page }) => {
  await page.goto("/index.html?audience=judge,blind");
  await expect(page).toHaveURL(/\/watch\.html\?audience=judge,blind$/);
  await expect(page.locator("#judge-banner")).toBeVisible();
  await expect(page.locator("#t-blind")).toHaveAttribute("aria-pressed", "true");
});

test("landing: listening toggle works with the keyboard and announces it", async ({ page }) => {
  await page.goto("/index.html");
  const desc = page.locator("#l-desc");
  await expect(desc).toBeEnabled();
  await expect(page.locator("#l-lanes")).toHaveAttribute("aria-label", /Speech comes in \d+ parts/);
  await expect(page.locator("#l-disclosure")).toContainText("Demo fixture");
  await tabTo(page, desc);
  await page.keyboard.press("Enter");
  await expect(desc).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#l-orig")).toHaveAttribute("aria-pressed", "false");
  await expect(page.locator("#l-desc-lane")).not.toHaveClass(/is-off/);
  await expect(page.locator("#l-status")).not.toBeEmpty();
  const play = page.locator("#l-play");
  await tabTo(page, play);
  await page.keyboard.press("Enter");
  await expect(page.locator("#l-status")).not.toBeEmpty();
});

test("landing: audience discs open the player for that viewer", async ({ page }) => {
  await page.goto("/index.html");
  const disc = page.getByRole("link", { name: "I can't hear" });
  await expect(disc).toHaveAttribute("href", "watch.html?audience=deaf");
  await tabTo(page, disc);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/watch\.html\?audience=deaf$/);
  await expect(page.locator("#t-deaf")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("body")).toHaveAttribute("data-world", "deaf");
});

test("landing: rule demo shows real findings and announces the choice", async ({ page }) => {
  await page.goto("/index.html");
  const examples = await (await page.request.get("/data/rule_examples.json")).json();
  const good = page.locator("#ex-0");
  await tabTo(page, page.locator('input[name="example"]:checked'));
  await page.keyboard.press("ArrowUp");
  await expect(good).toBeChecked();
  await expect(page.locator("#ex-status")).toContainText(`${examples.examples[0].label}: passes every check.`);
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("ArrowDown");
  const ex = examples.examples[2];
  await expect(page.locator("#ex-result .chips li")).toHaveCount(ex.findings.length);
  for (const f of ex.findings) await expect(page.locator("#ex-result")).toContainText(f.rule);
  await expect(page.locator("#ex-status")).toContainText(`blocked by ${ex.findings.length} checks`);
});

test("landing: results show only registered numbers, else Measuring", async ({ page }) => {
  await page.goto("/index.html");
  const claims = (await (await page.request.get("/data/claims.json")).json()).claims;
  const rows = page.locator("#results-rows .big-row");
  await expect(rows).toHaveCount(5);
  const first = rows.first();
  if (!claims["e1.fit_c"]?.display || !claims["e1.lines_planned"]?.display) await expect(first).toContainText("Measuring");
  else await expect(first).toContainText(`${claims["e1.fit_c"].display} of ${claims["e1.lines_planned"].display}`);
  await expect(page.locator("#law-rows .big-row").first()).toContainText(claims["cited.law.eaa_apply_date"].display);
});

test("landing: the moving text can be paused", async ({ page }) => {
  await page.goto("/index.html");
  const b = page.locator("#marquee-toggle");
  await tabTo(page, b);
  await page.keyboard.press("Enter");
  await expect(page.locator("#marquee")).toHaveClass(/paused/);
  await expect(b).toHaveText("Play moving text");
});

test("watch: share this view copies a link and says so", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/watch.html?audience=blind,easy");
  await expect(page.locator("#status")).toContainText("Now playing");
  await page.locator("#b-share").click();
  await expect(page.locator("#share-status")).toContainText("Link");
  await expect(page.locator("#share-status")).toContainText("I can't see the screen, Simpler words, please");
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied).toMatch(/watch\.html\?audience=blind,easy$/);
});

test("watch: ? opens the shortcut list, Escape closes it and returns focus", async ({ page }) => {
  await page.goto("/watch.html");
  await expect(page.locator("#status")).toContainText("Now playing");
  await page.locator("body").click({ position: { x: 5, y: 5 } });
  await page.keyboard.press("Shift+Slash");
  const dlg = page.locator("#keys-dialog");
  await expect(dlg).toBeVisible();
  await expect(page.locator("#b-keys-close")).toBeFocused();
  expect(await axeViolations(page)).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(dlg).toBeHidden();
  const keysBtn = page.locator("#b-keys");
  await keysBtn.focus();
  await page.keyboard.press("Enter");
  await expect(dlg).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(keysBtn).toBeFocused();
  // single-key shortcut: 2 picks "I can't hear"
  await page.locator("body").click({ position: { x: 5, y: 5 } });
  await page.keyboard.press("2");
  await expect(page.locator("#t-deaf")).toHaveAttribute("aria-pressed", "true");
});
