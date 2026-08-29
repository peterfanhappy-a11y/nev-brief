import { defineConfig, devices } from "@playwright/test";

const port = Number(process.env.AIVIZENS_TEST_WEB_PORT ?? "55439");
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "line",
  use: {
    ...devices["Desktop Chrome"],
    baseURL,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  webServer: {
    command: `next dev -p ${port}`,
    cwd: __dirname,
    url: baseURL,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
