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
      await page.goto("/index.html?audience=judge,blind,easy");
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
  });
}

test("proof page never fakes a run", async ({ page }) => {
  await page.goto("/proof.html");
  await expect(page.locator("#b-attack")).toBeDisabled();
  await expect(page.locator("#live-state")).toContainText("not connected");
  await expect(page.locator("#last-run")).toContainText("No recorded run yet.");
});

test("disclosure banner is always visible for drafts", async ({ page }) => {
  await page.goto("/index.html");
  await expect(page.locator("#disclosure")).toContainText("UNREVIEWED DRAFT");
});

test("no horizontal scroll at 360 px", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  for (const path of ["/index.html?audience=judge,blind,easy", "/five-ways.html", "/proof.html"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, path).toBeLessThanOrEqual(0);
  }
});

test("keyboard only: pick profiles, open the drawer, jump to a line", async ({ page }) => {
  await page.goto("/index.html");
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
