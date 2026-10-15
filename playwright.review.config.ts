import { defineConfig, devices } from "@playwright/test";
import * as path from "node:path";

// E2E + axe-core for the review app (PLAN §12, E16). Starts the review server on 127.0.0.1:8091
// against a fresh copy of the project folder in ACCESSCAST_REVIEW_FIXTURE (see tests/e2e/setup_review_fixture.sh).
//   ACCESSCAST_REVIEW_FIXTURE=<projects dir> npx playwright test -c playwright.review.config.ts
const port = Number(process.env.ACCESSCAST_REVIEW_PORT ?? 8091);
const fixture = process.env.ACCESSCAST_REVIEW_FIXTURE ?? "";
// review.spec.ts skips itself unless this is set, so the player config (testDir tests/e2e) can't run it
// against the wrong server. Workers load this file too, so the flag reaches the tests.
process.env.ACCESSCAST_REVIEW_E2E = "1";

export default defineConfig({
  testDir: "tests/e2e",
  testMatch: /review\.spec\.ts$/,
  timeout: 120_000,
  retries: 0,
  workers: 1,
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: "retain-on-failure",
  },
  projects: [{ name: "review-chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `bash "${path.resolve("tests/e2e/setup_review_fixture.sh")}"`,
    env: { ACCESSCAST_REVIEW_FIXTURE: fixture, ACCESSCAST_REVIEW_PORT: String(port) },
    url: `http://127.0.0.1:${port}/api/projects`,
    reuseExistingServer: false,
    timeout: 120_000,
    stdout: "ignore",
    stderr: "pipe",
  },
});
