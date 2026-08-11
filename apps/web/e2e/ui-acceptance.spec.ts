import { expect, test, type Page, type TestInfo } from "@playwright/test";

test.setTimeout(120_000);

const rulebookFixture = {
  task_id: "ui-contract-rulebook",
  task_name: "朋友墊款風險規則",
  task_type: "general",
  raw_input: "凡是朋友要求我先墊錢，先判斷是否把風險轉嫁給我。",
  status: "waiting_user_confirm",
  confirmed: false,
  review_passed: false,
  storage_confirmed: false,
  runtime: "local",
  rule_assist_plan: "FREE",
  draft_source: "model_assisted_rulebook",
  model_used: true,
  model_provider: "lm_studio",
  model_name: "local-test-model",
  model_schema_valid: true,
  model_semantic_valid: true,
  validator_passed: true,
  fallback_used: false,
  requires_user_signature: true,
  model_signature_allowed: false,
  next_required_action: "owner_review_and_signature",
  scbkr: {
    draft_source: "model_assisted_rulebook",
    model_participated: true,
    model_schema_valid: true,
    model_semantic_valid: true,
    validator_passed: true,
    rule_summary: "先判斷墊款是否把還款與追討風險轉嫁給使用者，再決定是否只保留草稿或拒絕墊款。",
    missing_information: ["還款日期與書面承諾尚未確認"],
    user_confirmation_items: ["請確認可承受的最高墊款金額"],
    model_cannot_decide: ["模型不能替使用者承擔借款損失"],
    risk_reminders: ["口頭承諾可能無法作為可靠還款依據"],
    next_actions: ["owner_review_and_signature"],
    S: {
      owner_draft_content: "使用者遇到朋友要求先代墊款項時，適用這條本地規則。",
      model_explanation: "先界定誰要做決定、面對什麼要求，以及規則何時啟動。",
      missing_information: ["墊款上限"],
      needs_user_confirmation: ["誰有權例外同意"],
    },
    C: {
      owner_draft_content: "先查還款來源與日期，再判斷損失、追討與關係壓力是否被轉嫁。",
      model_explanation: "把判斷順序寫清楚，避免只因對方承諾就跳到結論。",
    },
    B: {
      owner_draft_content: "沒有可驗證還款能力、書面條件或超過可承受金額時停止。不得替對方保證結果。",
      model_explanation: "明確列出禁止事項與停止條件，防止模型自行放寬。",
      risk_notes: ["未留下紀錄會增加後續爭議"],
    },
    K: {
      owner_draft_content: "只引用使用者確認的金額、日期、對話與正式文件；相似案例只能協助搜尋。",
      model_explanation: "區分正式依據與檢索候選，VECTOR 不能直接作為判斷依據。",
    },
    R: {
      owner_draft_content: "使用者負責最後決定與簽名；模型只能草擬、提醒與檢查，不能代簽或入庫。",
      model_explanation: "把決策、驗收與簽名責任留在使用者手上。",
    },
  },
};

const chatFixture = {
  reply: "SCBKR 可以一般聊天，也能把可重用的判斷整理成由你確認與簽名的五維規則。",
  model_used: true,
  model_connected: true,
  current_rule_package: {
    package_version: "1",
    task_type: "general_chat",
    matched_rules: [],
    citable_data: [],
    user_preferences: [],
    retrieval_candidates: [],
    non_citable_data: [],
    prohibitions: ["不得把一般聊天寫入規則庫"],
    stop_conditions: [],
    missing_information: [],
    output_constraints: ["只回答本次問題"],
    plan_level: "FREE",
    draft_only: false,
    requires_followup: false,
    chat_context_used: false,
  },
  post_check: { checked: true, allowed: true, action: "allow", violations: [] },
  token_cost_audit: {
    measurement_scope: "general_chat",
    measurement_basis: "provider_usage",
    comparison_basis: "single_provider_call",
    savings_verified: false,
    provider_usage_available: true,
    actual_usage_verified: true,
    actual_prompt_tokens: 120,
    actual_completion_tokens: 32,
    actual_total_tokens: 152,
    baseline_prompt_tokens: null,
    current_rule_package_tokens_est: null,
    tokens_saved: null,
    reduction_percent: null,
    api_cost: 0,
    price_status: "local_no_api_charge",
    currency: "USD",
    chat_context_used: false,
    formal_source_summary: {
      matched_rules: 0,
      citable_data: 0,
      user_preferences: 0,
      vector_candidates: 0,
      non_citable_data: 0,
      vector_recall_only: true,
    },
  },
};

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
  await page.locator(".side-nav").getByRole("button", { name: label, exact: true }).click();
}

async function attachScreen(page: Page, testInfo: TestInfo, name: string) {
  await testInfo.attach(name, {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });
}

test("中英雙語核心流程可操作，且不顯示工程狀態碼", async ({ page }, testInfo) => {
  const browserErrors: string[] = [];
  const failedResponses: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().startsWith("Failed to load resource:")) browserErrors.push(message.text());
  });
  page.on("response", (response) => {
    if (response.status() >= 400) failedResponses.push(`${response.status()} ${response.url()}`);
  });

  await page.addInitScript(() => localStorage.setItem("scbkr.onboarding.2.3", "done"));
  await page.route("http://127.0.0.1:8787/api/chat/general", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(chatFixture) });
  });
  await page.route("http://127.0.0.1:8787/api/tasks/create-fast", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(rulebookFixture) });
  });

  await page.goto("/");
  const healthResponse = await page.request.get("http://127.0.0.1:8787/health");
  expect(healthResponse.ok(), "本機 FastAPI health 必須可連線").toBe(true);
  await expect(page.locator(".app-shell")).toBeVisible();
  await expect(page.locator(".top-status-bar")).toContainText("本機服務 運行中", { timeout: 15_000 });
  await expect(page.locator(".top-status-bar")).toContainText("免費版");
  await expect(page.getByRole("heading", { name: "SCBKR 對話" })).toBeVisible();
  await expect(page.getByLabel("一般聊天主視窗")).toContainText("許文耀／沈耀888π");
  await expect(page.getByLabel("一般聊天主視窗")).toContainText("S／C／B／K／R");
  await expect(page.locator(".active-rule-panel")).toContainText("尚無可引用規則");
  await expect(page.locator(".active-rule-panel")).toContainText("尚無生效簽名");
  await expect(page.getByText("王小明", { exact: true })).toHaveCount(0);
  if (testInfo.project.name === "desktop-chromium") await expect(page.locator(".account-card")).toBeVisible();

  await openSection(page, testInfo, "工作台");
  const disconnectedCopy = page.getByText("SCBKR 不會用模板冒充模型完成草擬。", { exact: true });
  await expect(disconnectedCopy).toBeVisible();
  const disconnectedCopyBox = await disconnectedCopy.boundingBox();
  expect(disconnectedCopyBox, "未連線提示必須可量測").not.toBeNull();
  expect(disconnectedCopyBox!.width, "未連線提示不可被壓成逐字直排").toBeGreaterThan(disconnectedCopyBox!.height * 3);
  await openSection(page, testInfo, "聊天");

  const input = page.getByLabel("自然語言輸入", { exact: true });
  await input.fill("請用一句話介紹 SCBKR");
  await page.locator(".send-button").click();
  await expect(page.getByText(chatFixture.reply, { exact: true })).toBeVisible();
  const receipt = page.getByTestId("current-rule-package-receipt");
  await expect(receipt).toBeVisible();
  await expect(receipt).toContainText("本次回答依據");
  await expect(receipt).toContainText("一般聊天，未引用正式規則");
  await expect(receipt).toContainText("聊天上下文作正式依據");
  await expect(page.locator(".token-audit-panel")).toContainText("120");
  await expect(page.locator(".token-audit-panel")).toContainText("本地模型無 API 費");

  await page.getByRole("button", { name: "建規則", exact: true }).click();
  await input.fill("凡是朋友要求我先墊錢，先判斷是否把風險轉嫁給我，並寫成我的本地規則。");
  await page.locator(".send-button").click();
  await expect(page.getByRole("heading", { name: "SCBKR 工作台" })).toBeVisible();
  const evidence = page.getByTestId("model-participation-status");
  await expect(evidence).toContainText("模型已參與");
  await expect(evidence).toContainText("五維格式通過");
  await expect(evidence).toContainText("五維分工通過");
  await expect(evidence).toContainText("核心驗證通過");
  await expect(page.getByTestId("draft-review-overview")).toContainText("還款日期與書面承諾尚未確認");
  await expect(page.getByTestId("draft-review-overview")).toContainText("口頭承諾可能無法作為可靠還款依據");
  await expect(page.locator("details.dimension-row")).toHaveCount(5);
  await expect(page.locator("details.dimension-row").first()).toContainText("模型為什麼這樣寫");
  await expect(page.locator(".workbench-panel")).toContainText("模型不能簽名");
  await expect(page.locator(".workbench-panel")).not.toContainText("model_assisted_rulebook");
  await expect(page.locator(".workbench-panel")).not.toContainText("owner_review_and_signature");
  await expect(page.locator(".workbench-panel")).not.toContainText("waiting_user_confirm");
  const firstEdit = page.locator("details.dimension-row textarea").first();
  await expect(firstEdit).toBeEnabled();
  const signature = page.getByLabel("使用者簽名", { exact: true });
  const submitSignature = page.getByRole("button", { name: "提交簽名", exact: true });
  await expect(submitSignature).toBeDisabled();
  await signature.fill("UI acceptance owner");
  await expect(submitSignature).toBeEnabled();
  await attachScreen(page, testInfo, "01-workbench");

  await openSection(page, testInfo, "規則中心");
  await expect(page.getByLabel("用一句人話建立規則", { exact: true })).toBeVisible();
  await expect(page.locator(".product-rules")).not.toContainText(/\b(active|owner_signed|medium)\b/);

  await openSection(page, testInfo, "資料中心");
  await expect(page.getByRole("heading", { name: "四庫資料中心", exact: true })).toBeVisible();
  await expect(page.getByLabel("搜尋四庫", { exact: true })).toBeVisible();
  for (const store of ["LOGIC", "CORPUS", "MEMORY", "VECTOR"]) {
    await expect(page.getByLabel(`${store} 資料庫`)).toBeVisible();
  }

  await openSection(page, testInfo, "規則狀態");
  await expect(page.getByRole("heading", { name: "規則狀態", exact: true })).toBeVisible();
  await expect(page.getByTestId("current-rule-package-panel")).toContainText("一般聊天，未引用正式規則");
  await expect(page.locator(".token-audit-panel")).toContainText("一般聊天計量");
  await expect(page.locator(".token-audit-panel")).toContainText("120");
  await attachScreen(page, testInfo, "02-rule-state");

  await page.locator(".locale-button").click();
  await expect(page.locator(".top-status-bar")).toContainText("Local service Running");
  await openSection(page, testInfo, "Chat");
  await expect(page.getByRole("heading", { name: "SCBKR Chat" })).toBeVisible();
  await expect(page.getByLabel("Natural language input", { exact: true })).toBeVisible();
  await openSection(page, testInfo, "Workbench");
  await expect(page.getByRole("heading", { name: "SCBKR Workbench" })).toBeVisible();
  await expect(page.getByTestId("model-participation-status")).toContainText("Model participated");

  const layout = await page.evaluate(() => ({
    viewportFits: document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
    clippedButtons: [...document.querySelectorAll("button")].filter((button) => button.scrollWidth > button.clientWidth + 2).length,
  }));
  expect(layout.viewportFits, "頁面不應產生整頁水平溢出").toBe(true);
  expect(layout.clippedButtons, "按鈕文字不應被裁切").toBe(0);
  expect(browserErrors, "瀏覽器 console/page 不應出現錯誤").toEqual([]);
  expect(failedResponses, "頁面資源與 API 不應回傳 4xx/5xx").toEqual([]);
});
