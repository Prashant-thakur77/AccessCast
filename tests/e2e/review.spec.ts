// Review app E2E (PLAN §12, E16): axe-core scans and a keyboard-only review of a whole project.
// Run with:  ACCESSCAST_REVIEW_FIXTURE=<projects dir> npx playwright test -c playwright.review.config.ts
import { test, expect, type Page, type Locator, type APIRequestContext } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.skip(process.env.ACCESSCAST_REVIEW_E2E !== "1", "runs only with playwright.review.config.ts");
test.describe.configure({ mode: "serial" });

const WAITING = new Set(["pending", "needs_revision"]);

async function projectId(request: APIRequestContext): Promise<string> {
  const r = await request.get("/api/projects");
  expect(r.ok()).toBeTruthy();
  const projects = (await r.json()) as { id: string }[];
  expect(projects.length).toBeGreaterThan(0);
  return projects[0].id;
}

async function openProject(page: Page, pid: string) {
  await page.goto(`/app/index.html?p=${pid}`);
  await expect(page.locator("#workspace")).toBeVisible();
  await expect(page.locator("#status")).toContainText("Project loaded");
}

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
  throw new Error(`could not reach the target with Tab in ${max} presses`);
}

const detail = (page: Page) => page.locator("#detail");

for (const scheme of ["light", "dark"] as const) {
  test(`axe-core (${scheme}): picker, a selected line and the key help dialog have 0 violations`, async ({ page, request }) => {
    await page.emulateMedia({ colorScheme: scheme });
    const pid = await projectId(request);

    await page.goto("/app/index.html");
    await expect(page.locator("#project-list a").first()).toBeVisible();
    expect(await axeViolations(page)).toEqual([]);

    await openProject(page, pid);
    await page.keyboard.press("]");
    await expect(detail(page)).toHaveAttribute("data-check-state", "ready");
    await page.locator("#timeline-text summary").press("Enter"); // open "Timeline as text" so it is scanned
    await expect(page.locator("#timeline-text-body")).toBeVisible();
    expect(await axeViolations(page)).toEqual([]);

    await page.locator("body").press("?");
    await expect(page.locator("#help")).toBeVisible();
    await expect(page.locator("#help-close")).toBeFocused();
    expect(await axeViolations(page)).toEqual([]);
    await page.keyboard.press("Escape");
    await expect(page.locator("#help")).toBeHidden();
  });
}

test("360 px wide: panels stack and nothing scrolls sideways", async ({ page, request }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await openProject(page, await projectId(request));
  await page.keyboard.press("]");
  await expect(detail(page)).toHaveAttribute("data-check-state", "ready");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  expect(await axeViolations(page)).toEqual([]);
});

test("every language has its own filter, and a filter shows only that language's lines", async ({ page, request }) => {
  const pid = await projectId(request);
  await openProject(page, pid);
  for (const [kind, label] of [["es", "Spanish"], ["fr", "French"], ["pt", "Portuguese"]]) {
    const b = page.locator(`#kind-filters button[data-kind='${kind}']`);
    await expect(b).toContainText(label);
    await b.click();
    await expect(b).toHaveAttribute("aria-pressed", "true");
    const n = Number(((await b.textContent()) || "").match(/\((\d+)\)/)?.[1] ?? "0");
    await expect(page.locator("#item-list button[data-id]")).toHaveCount(n);
  }
});

test("the list of lines is one Tab stop: arrows move inside it, Tab leaves it", async ({ page, request }) => {
  const pid = await projectId(request);
  await openProject(page, pid);
  const items = page.locator("#item-list button[data-id]");
  expect(await items.count()).toBeGreaterThan(2);
  await expect(page.locator("#item-list button[data-id][tabindex='0']")).toHaveCount(1);
  await tabTo(page, page.locator("#item-list button[data-id][tabindex='0']"));
  const first = await page.evaluate(() => (document.activeElement as HTMLElement).dataset.id);
  await page.keyboard.press("ArrowDown");
  const second = await page.evaluate(() => (document.activeElement as HTMLElement).dataset.id);
  expect(second).toBeTruthy();
  expect(second).not.toBe(first);
  await page.keyboard.press("End");
  await expect(items.last()).toBeFocused();
  await page.keyboard.press("Tab");
  expect(await page.evaluate(() => !!document.activeElement?.closest("#item-list"))).toBe(false);
});

test("a save that conflicts with another change shows 'Changed elsewhere; reloaded.'", async ({ page, request }) => {
  const pid = await projectId(request);
  await openProject(page, pid);
  await page.keyboard.press("]");
  await expect(detail(page)).toHaveAttribute("data-check-state", "ready");
  const id = (await detail(page).getAttribute("data-id"))!;
  const items = (await (await request.get(`/api/projects/${pid}/items`)).json()).items as {
    id: string; revision: number; text: string;
  }[];
  const it = items.find((i) => i.id === id)!;

  // Someone else saves the same line first.
  const other = await request.patch(`/api/projects/${pid}/items/${id}`, {
    data: { expected_revision: it.revision, reviewer_note: "changed by another reviewer (e2e)" },
    headers: { "X-Reviewer": "e2e-other" },
  });
  expect(other.ok()).toBeTruthy();

  // Our edit is saved with the old revision: the server answers 409 and the view reloads.
  await page.keyboard.press("e");
  await expect(page.locator("#final")).toBeFocused();
  await page.keyboard.press("End");
  await page.keyboard.type(" Extra");
  await expect(page.locator("#status")).toHaveText("Changed elsewhere; reloaded.");
  await expect(page.locator("#item-save")).toContainText("Changed elsewhere; reloaded.");
  await expect(page.locator("#final")).toHaveValue(it.text);

  // Esc leaves the text field and returns focus to the list.
  await page.locator("#final").press("Escape");
  await expect(page.locator(`#item-list button[data-id="${id}"]`)).toBeFocused();
});

test("keyboard only: review a whole project, then mark review complete", async ({ page, request }) => {
  const pid = await projectId(request);
  await openProject(page, pid);
  const ids = await page.locator("#item-list button[data-id]").evaluateAll((bs) =>
    bs.map((b) => (b as HTMLElement).dataset.id!));
  expect(ids.length).toBeGreaterThan(0);

  // Render is refused in plain words while lines wait for a person.
  await tabTo(page, page.locator("#btn-render"));
  await page.keyboard.press("Enter");
  await expect(page.locator("#gate-result")).toContainText(/Can't render yet: \d+ lines? (is|are) still waiting for a person\./);

  // Say who is reviewing, then go back to the list with Esc.
  await tabTo(page, page.locator("#reviewer"));
  await page.keyboard.type("e2e-keyboard");
  await page.keyboard.press("Escape");

  let approved = 0;
  let rejected = 0;
  for (const expected of ids) {
    await page.keyboard.press("]");
    await expect(detail(page)).toHaveAttribute("data-id", expected);
    await expect(detail(page)).toHaveAttribute("data-check-state", "ready");
    const status = (await detail(page).getAttribute("data-status"))!;
    if (!WAITING.has(status)) continue;
    const hasErrors = (await detail(page).getAttribute("data-has-errors")) === "true";
    await page.keyboard.press(hasErrors ? "r" : "a");
    await expect(detail(page)).toHaveAttribute("data-status", hasErrors ? "rejected" : "approved");
    if (hasErrors) rejected += 1; else approved += 1;
  }
  expect(approved).toBeGreaterThan(0);
  await page.keyboard.press("]");
  await expect(page.locator("#status")).toHaveText("This is the last line.");
  await expect(page.locator("#pending-badge")).toHaveText("");

  await tabTo(page, page.locator("#btn-complete"));
  await page.keyboard.press("Enter");
  await expect(page.locator("#gate-result")).toHaveAttribute("data-ok", "true");
  await expect(page.locator("#gate-result")).toContainText("Review complete.");

  // The server agrees: nothing waits, and every decision carries the reviewer's name.
  const after = (await (await request.get(`/api/projects/${pid}/items`)).json()).items as {
    id: string; status: string; reviewer: string | null;
  }[];
  expect(after.filter((i) => WAITING.has(i.status))).toEqual([]);
  expect(after.filter((i) => i.status === "rejected").length).toBe(rejected);
  expect(after.filter((i) => i.reviewer === "e2e-keyboard").length).toBe(approved + rejected);
});

test("studio: axe clean, keyboard-only upload, every stage listed, review link opens the project", async ({ page }) => {
  await page.goto("/app/studio.html");
  expect(await axeViolations(page)).toEqual([]);
  await page.locator("#file").setInputFiles("tests/fixtures/fixture20/source.mp4");
  await tabTo(page, page.locator("#go"));
  await page.keyboard.press("Enter");
  await expect(page.locator("#status")).toContainText("Started", { timeout: 30_000 });
  await expect(page.locator("#stages li")).toHaveCount(26);  // 20 stages + Spanish, French and Portuguese subtitles and voice-over
  await expect(page.locator("#status")).toContainText("Finished", { timeout: 300_000 });
  await expect(page.locator("#stages li[data-state='failed']")).toHaveCount(0);
  await expect(page.locator("#fake-banner")).toBeVisible(); // the fixture server runs in fake mode: said on screen
  await expect(page.locator("#gemma")).toContainText("nothing here came from a model");
  await expect(page.locator("#lines tbody tr").first()).toBeVisible();
  expect(await axeViolations(page)).toEqual([]);
  const href = await page.locator("#review-link").getAttribute("href");
  expect(href).toMatch(/index\.html\?p=[0-9a-f]{12}$/);
  await page.locator("#review-link").focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#workspace")).toBeVisible();
});

test("add a line by keyboard: dialog is labelled, axe clean, the line lands and waits for review", async ({ page, request }) => {
  const pid = await projectId(request);
  await openProject(page, pid);
  const before = ((await (await request.get(`/api/projects/${pid}/items`)).json()).items as { id: string }[]).length;
  await page.locator("#item-list").focus();
  await page.keyboard.press("i");
  const dlg = page.locator("#add");
  await expect(dlg).toBeVisible();
  await expect(page.locator("#add-text")).toBeFocused();
  expect(await axeViolations(page)).toEqual([]);
  await page.keyboard.type("A woman opens a laptop on a desk.");
  await tabTo(page, page.locator("#add-save"));
  await page.keyboard.press("Enter");
  await expect(dlg).toBeHidden();
  // "Line added" is announced, then the new line is selected and its live check results are read out
  await expect(page.locator("#status")).toContainText(/Line added|Manual line/);
  const items = (await (await request.get(`/api/projects/${pid}/items`)).json()).items as {
    id: string; status: string; source: string; text: string;
  }[];
  expect(items.length).toBe(before + 1);
  const mine = items.find((i) => i.source === "manual" && i.text === "A woman opens a laptop on a desk.");
  expect(mine && mine.status).toBe("pending");
});
