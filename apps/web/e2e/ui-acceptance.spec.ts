import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { PNG } from "pngjs";

async function openSection(page: Page, testInfo: TestInfo, label: string) {
  if (testInfo.project.name === "mobile-chromium") {
    const drawer = page.locator(".mobile-drawer");
    await expect(drawer).toBeVisible();
    await drawer.locator("button").filter({ hasText: label }).click();
    return;
  }

  await page.locator(".side-nav button").filter({ hasText: label }).click();
}

async function attachScreen(page: Page, testInfo: TestInfo, name: string) {
  await testInfo.attach(name, {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });
}

test("核心 UI 可開啟、可導覽且沒有明顯版面溢出", async ({ page }, testInfo) => {
  const browserErrors: string[] = [];
  const failedResponses: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  page.on("response", (response) => {
    if (response.status() >= 400) {
      failedResponses.push(`${response.status()} ${response.url()}`);
    }
  });
  page.on("console", (message) => {
    if (
      message.type() === "error" &&
      !message.text().startsWith("Failed to load resource:")
    ) {
      browserErrors.push(message.text());
    }
  });

  await page.goto("/");
  await expect(page.locator(".app-shell")).toBeVisible();
  const healthResponse = await page.request.get("http://127.0.0.1:8787/health");
  expect(healthResponse.ok(), "本機 FastAPI health 必須可連線").toBe(true);
  if (testInfo.project.name === "desktop-chromium") {
    await expect(page.getByText("API online", { exact: true })).toBeVisible();
  }
  await expect(page.getByLabel("一般聊天主視窗")).toBeVisible();
  await expect(page.getByRole("heading", { name: "自然語言控制台" })).toBeVisible();
  await expect(page.getByRole("button", { name: "搜尋閱讀四庫", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "建立規則", exact: true })).toBeVisible();
  await expect(page.getByLabel("自然語言輸入", { exact: true })).toBeVisible();
  const canvas = page.locator('[data-testid="scbkr-canvas"]');
  await expect(canvas).toHaveCount(1);
  await expect(canvas).toBeVisible();
  const canvasBox = await canvas.boundingBox();
  expect(canvasBox?.width).toBeGreaterThan(280);
  expect(canvasBox?.height).toBeGreaterThan(220);
  const pixels = PNG.sync.read(await canvas.screenshot());
  const sampledColors = new Set<string>();
  let luminousSamples = 0;
  for (let y = 0; y < pixels.height; y += 8) {
    for (let x = 0; x < pixels.width; x += 8) {
      const offset = (pixels.width * y + x) * 4;
      const r = pixels.data[offset];
      const g = pixels.data[offset + 1];
      const b = pixels.data[offset + 2];
      sampledColors.add(`${Math.floor(r / 16)}:${Math.floor(g / 16)}:${Math.floor(b / 16)}`);
      if (r + g + b > 420) luminousSamples += 1;
    }
  }
  expect(sampledColors.size, "Three.js canvas must contain a rendered multi-color scene").toBeGreaterThan(12);
  expect(luminousSamples, "Three.js nodes and stars must produce visible pixels").toBeGreaterThan(20);
  await attachScreen(page, testInfo, "01-chat-home");

  await openSection(page, testInfo, "工作台");
  await expect(page.getByRole("heading", { name: "建立責任鏈確認單" })).toBeVisible();
  await attachScreen(page, testInfo, "02-workbench");

  await openSection(page, testInfo, "規則中心");
  await expect(page.getByLabel("用一句人話建立規則", { exact: true })).toBeVisible();

  await openSection(page, testInfo, "模型設定");
  await expect(page.getByRole("heading", { name: "模型設定" })).toBeVisible();
  await attachScreen(page, testInfo, "03-model-settings");

  await openSection(page, testInfo, "資料中心");
  await expect(page.getByRole("heading", { name: "四庫搜尋與閱讀區", exact: true })).toBeVisible();
  await expect(page.getByLabel("搜尋四庫", { exact: true })).toBeVisible();
  await attachScreen(page, testInfo, "04-data-center");

  const viewportFits = await page.evaluate(() =>
    document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
  );
  expect(viewportFits, "頁面不應產生整頁水平溢出").toBe(true);
  expect(browserErrors, "瀏覽器 console/page 不應出現錯誤").toEqual([]);
  expect(failedResponses, "頁面資源與 API 不應回傳 4xx/5xx").toEqual([]);
});
