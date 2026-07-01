import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [
    ["list"],
    ["html", { outputFolder: "./playwright-report", open: "never" }],
  ],
  use: {
    baseURL: "http://127.0.0.1:5500",
    channel: "msedge",
    colorScheme: "dark",
    reducedMotion: "reduce",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "desktop-chromium",
      use: { viewport: { width: 1440, height: 900 } },
    },
    {
      name: "mobile-chromium",
      use: {
        viewport: { width: 390, height: 844 },
        deviceScaleFactor: 1,
        hasTouch: true,
        isMobile: true,
      },
    },
  ],
  webServer: [
    {
      command: "py -3.12 -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8787",
      cwd: "../..",
      url: "http://127.0.0.1:8787/health",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "npm run dev",
      cwd: ".",
      url: "http://127.0.0.1:5500",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
