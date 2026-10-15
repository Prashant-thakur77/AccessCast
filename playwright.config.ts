import { defineConfig, devices } from "@playwright/test";
import * as path from "node:path";

// Serves an exported site (accesscast export-site) on 127.0.0.1:8090.
const siteDir = path.resolve(process.env.ACCESSCAST_SITE_DIR ?? "projects/_fixture_site");
const port = 8090;

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 60_000,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `python3 -m http.server ${port} --bind 127.0.0.1 --directory "${siteDir}"`,
    url: `http://127.0.0.1:${port}/data/catalog.json`,
    reuseExistingServer: false,
    timeout: 30_000,
    stdout: "ignore",
    stderr: "ignore",
  },
});
