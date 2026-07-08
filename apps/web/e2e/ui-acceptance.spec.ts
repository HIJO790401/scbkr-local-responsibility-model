import { expect, test, type Page, type TestInfo } from "@playwright/test";

test.setTimeout(60_000);

async function openSection(page: Page, testInfo: TestInfo, label: string) {
  if (testInfo.project.name === "mobile-chromium") {
    const drawer = page.locator(".mobile-drawer");
    await expect(drawer).toBeVisible();
    const primary = drawer.getByRole("button", { name: label, exact: true });
    if (await primary.count()) {
      await primary.click();
    } else {
      await drawer.getByRole("button", { name: "更多", exact: true }).click();
      const nested = page.locator(".more-grid").getByRole("button", { name: label, exact: true });
      await expect(nested).toBeVisible();
      await nested.click();
    }
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
  await expect(page.locator(".top-status-bar")).toContainText("API online", { timeout: 15_000 });
  if (testInfo.project.name === "desktop-chromium") {
    await expect(page.locator(".top-status-bar")).toContainText(/PLAN (FREE|NT690|NT3300)/);
  }
  await expect(page.getByLabel("一般聊天主視窗")).toBeVisible();
  await expect(page.getByRole("heading", { name: "SCBKR 聊天" })).toBeVisible();
  if (testInfo.project.name === "desktop-chromium") {
    const planDetails = page.locator(".plan-details");
    await expect(planDetails).toBeVisible();
    await planDetails.evaluate((element) => {
      (element as HTMLDetailsElement).open = true;
    });
    await expect(planDetails).toContainText(/免費草稿層|責任鏈結構層|規則書閉環審計層/);
    await expect(page.locator(".plan-picker button")).toHaveCount(3, { timeout: 15_000 });
    await expect(page.getByLabel("方案選擇")).toBeVisible();
  }
  await expect(page.getByRole("button", { name: "開啟一般聊天" })).toBeVisible();
  await expect(page.getByRole("button", { name: "開啟規則輔助" })).toBeVisible();
  await expect(page.getByRole("button", { name: "開啟待簽名草案" })).toBeVisible();
  await expect(page.getByRole("button", { name: "開啟四庫引用" })).toBeVisible();
  await expect(page.locator(".rule-awareness-strip")).toContainText(/EMPTY|DRAFTING/);
  await expect(page.locator(".rule-awareness-strip")).toContainText("尚無生效規則");
  await expect(page.getByLabel("自然語言納編狀態")).toBeVisible();
  await expect(page.locator('[data-testid="scbkr-canvas"]')).toHaveCount(0);
  await expect(page.getByRole("button", { name: "上網查證", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "查四庫", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "建規則", exact: true })).toBeVisible();
  await expect(page.getByLabel("自然語言輸入", { exact: true })).toBeVisible();
  await page.getByLabel("自然語言輸入", { exact: true }).fill("以後凡是朋友要求我先墊錢，我要先判斷這是不是風險轉嫁，把這個寫成我的本地規則。");
  await page.locator(".send-button").click();
  const advisoryCard = page.locator(".workflow-card.advisory").filter({ hasText: "第0原理建議閘" }).first();
  await expect(advisoryCard).toBeVisible({ timeout: 15_000 });
  await expect(advisoryCard.getByRole("button", { name: "草擬確認單", exact: true })).toBeVisible();
  await expect(advisoryCard.getByRole("button", { name: "保持一般聊天", exact: true })).toBeVisible();
  await expect(advisoryCard.getByRole("button", { name: "補角色與邊界", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "建立責任鏈確認單" })).toHaveCount(0);
  await expect(page.locator(".token-audit-panel")).toContainText("上下文壓縮審計");
  await expect(page.locator(".token-audit-panel")).toContainText("聊天上下文作正式依據");
  await advisoryCard.getByTestId("draft-confirmation-sheet").click();
  await expect(page.getByRole("heading", { name: "Workbench / SCBKR 工作台" })).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".workbench-panel")).toContainText("DRAFT_ONLY");
  await expect(page.locator(".workbench-panel")).toContainText("FREE_DRAFT_ASSISTED");
  await expect(page.locator(".workbench-panel")).toContainText("S｜主體");
  await expect(page.locator(".workbench-panel")).toContainText("C｜因果");
  await expect(page.locator(".workbench-panel")).toContainText("B｜邊界");
  await expect(page.locator(".workbench-panel")).toContainText("K｜依據");
  await expect(page.locator(".workbench-panel")).toContainText("R｜責任");
  const workbench = page.locator(".workbench-panel");
  await expect(workbench.getByRole("button", { name: "模型補寫表單", exact: true })).toBeVisible();
  await expect(workbench.getByRole("button", { name: "補失效條件", exact: true })).toBeVisible();
  await expect(workbench.getByRole("button", { name: "補邊界", exact: true })).toBeVisible();
  await expect(workbench.getByRole("button", { name: "補回放要求", exact: true })).toBeVisible();
  await expect(page.locator(".workbench-panel")).toContainText("模型不能簽名");
  await attachScreen(page, testInfo, "01-chat-home");
  await attachScreen(page, testInfo, "02-workbench");

  await openSection(page, testInfo, "規則中心");
  await expect(page.getByLabel("用一句人話建立規則", { exact: true })).toBeVisible();
  await expect(page.locator(".product-rules")).toContainText(/SCBKR 規則中心|選擇一條規則查看詳情/);
  await expect(page.getByRole("heading", { name: "Workbench / SCBKR 工作台" })).toHaveCount(0);

  await openSection(page, testInfo, "工具與搜尋");
  await expect(page.getByRole("heading", { name: "工具註冊與權限" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "SCBKR 聊天" })).toHaveCount(0);

  await openSection(page, testInfo, "模型設定");
  await expect(page.getByRole("heading", { name: "模型設定" })).toBeVisible();
  await attachScreen(page, testInfo, "03-model-settings");

  await openSection(page, testInfo, "規則狀態");
  await expect(page.getByRole("heading", { name: "規則狀態", exact: true })).toBeVisible();

  await openSection(page, testInfo, "上線中心");
  await expect(page.getByRole("heading", { name: "上線中心", exact: true })).toBeVisible();

  await openSection(page, testInfo, "資料中心");
  await expect(page.getByRole("heading", { name: "四庫資料中心", exact: true })).toBeVisible();
  await expect(page.getByLabel("搜尋四庫", { exact: true })).toBeVisible();
  await expect(page.locator(".data-center-panel")).toContainText("VECTOR");
  await page.getByLabel("LOGIC 資料庫").click();
  await expect(page.getByRole("heading", { name: "LOGIC", exact: true })).toBeVisible();
  await attachScreen(page, testInfo, "04-data-center");

  const viewportFits = await page.evaluate(() =>
    document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
  );
  expect(viewportFits, "頁面不應產生整頁水平溢出").toBe(true);
  expect(browserErrors, "瀏覽器 console/page 不應出現錯誤").toEqual([]);
  expect(failedResponses, "頁面資源與 API 不應回傳 4xx/5xx").toEqual([]);
});
