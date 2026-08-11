import { defineConfig } from "@playwright/test";

const externalProductServer = process.env.SCBKR_UI_EXTERNAL_SERVER === "1";
const baseURL = process.env.SCBKR_UI_BASE_URL || "http://127.0.0.1:5500";

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
    baseURL,
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
  webServer: externalProductServer ? undefined : [
    {
      command: "python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8787",
      cwd: "../..",
      url: "http://127.0.0.1:8787/health",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "node ./node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5500",
      cwd: ".",
      url: "http://127.0.0.1:5500",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
