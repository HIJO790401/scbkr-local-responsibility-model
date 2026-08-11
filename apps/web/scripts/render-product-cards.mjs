import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const outputDir = path.join(root, "docs", "images");
const appUrl = process.env.SCBKR_CAPTURE_URL || "http://127.0.0.1:8787";
fs.mkdirSync(outputDir, { recursive: true });

const browser = await chromium.launch({ channel: "msedge", headless: true });

async function captureProductUi() {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, colorScheme: "light" });
  await page.goto(appUrl, { waitUntil: "networkidle" });
  const closeTour = page.getByRole("button", { name: /關閉導覽|Close tour/ });
  if (await closeTour.count()) await closeTour.first().click();
  await page.screenshot({ path: path.join(outputDir, "scbkr-ui-current-zh.png") });
  const english = page.getByRole("button", { name: "EN", exact: true });
  if (await english.count()) await english.first().click();
  await page.waitForTimeout(350);
  await page.screenshot({ path: path.join(outputDir, "scbkr-ui-current-en.png") });
  await page.close();
}

function imageData(name) {
  return `data:image/png;base64,${fs.readFileSync(path.join(outputDir, name)).toString("base64")}`;
}

const p = {
  ink: "#10263e", muted: "#5b7188", line: "#d6e2ee", blue: "#0869e8",
  blueSoft: "#eaf3ff", cyan: "#1ba7c4", green: "#148657", greenSoft: "#e9f8f1",
  yellowSoft: "#fff6df", red: "#bf3d44", redSoft: "#fff0f1", purple: "#6f4bd8",
};

function baseCss() {
  return `
    *{box-sizing:border-box}html,body{margin:0;width:1920px;height:1080px;overflow:hidden}
    body{font-family:"Segoe UI","Microsoft JhengHei",Arial,sans-serif;color:${p.ink};background:#f7fbff;letter-spacing:0}
    .canvas{position:relative;width:1920px;height:1080px;padding:58px 68px;background:linear-gradient(180deg,#fff 0%,#f4f9ff 100%)}
    .topline{position:absolute;inset:0 0 auto;height:8px;background:linear-gradient(90deg,${p.blue} 0 48%,${p.cyan} 48% 68%,${p.green} 68% 84%,#e8a21a 84% 94%,${p.red} 94%)}
    .brand{display:flex;align-items:center;gap:18px;min-width:430px}.mark{width:58px;height:58px;flex:0 0 58px;display:grid;place-items:center;border-radius:8px;color:#fff;background:${p.blue};font-size:28px;font-weight:800;box-shadow:0 10px 28px rgba(8,105,232,.22)}
    .brand b{display:block;white-space:nowrap;font-size:30px}.brand small{display:block;margin-top:3px;white-space:nowrap;color:${p.muted};font-size:17px}.badge{margin-left:auto;padding:10px 15px;border:1px solid #acd0fa;border-radius:999px;color:${p.blue};background:${p.blueSoft};font-size:16px;font-weight:700}
    h1,h2,h3,p{margin:0}.eyebrow{color:${p.blue};font-weight:800;font-size:18px}.footer{position:absolute;left:68px;right:68px;bottom:30px;display:flex;justify-content:space-between;color:#6b8196;font-size:14px}
  `;
}

function heroHtml(locale) {
  const en = locale === "en";
  const shot = imageData(en ? "scbkr-ui-current-en.png" : "scbkr-ui-current-zh.png");
  const steps = en
    ? ["Chat normally", "Model drafts S/C/B/K/R", "You review and sign", "Signed rules control later answers"]
    : ["自然聊天", "模型草擬 S／C／B／K／R", "使用者確認與簽名", "後續回答優先引用已簽名規則"];
  return `<!doctype html><html><head><meta charset="utf-8"><style>${baseCss()}
    header{display:flex;align-items:center}.layout{display:grid;grid-template-columns:650px 1fr;gap:44px;margin-top:50px;align-items:center}
    h1{max-width:650px;margin-top:16px;font-size:58px;line-height:1.13;font-weight:820}.intro{max-width:620px;margin-top:25px;color:#38536c;font-size:23px;line-height:1.62}
    .steps{display:grid;gap:12px;margin-top:30px}.step{display:flex;align-items:center;gap:13px;font-size:18px;font-weight:650}.step i{width:30px;height:30px;flex:0 0 30px;display:grid;place-items:center;border-radius:50%;color:#fff;background:${p.blue};font-style:normal;font-size:14px}
    .product-shot{overflow:hidden;border:1px solid #bfd4e8;border-radius:8px;background:#fff;box-shadow:0 24px 70px rgba(26,66,110,.18)}.product-shot img{display:block;width:100%;height:618px;object-fit:cover;object-position:top left}
    .proof{display:grid;grid-template-columns:1fr auto auto;gap:28px;align-items:center;margin-top:32px;padding:18px 22px;border:1px solid #bce3d0;border-radius:8px;background:${p.greenSoft}}.proof b,.proof strong{color:${p.green}}.proof b{font-size:18px}.proof strong{font-size:30px}.proof span{white-space:pre-line;color:#355b4b;font-size:15px}
    .stack{display:flex;gap:9px;margin-top:24px;flex-wrap:wrap}.stack span{padding:7px 10px;border:1px solid ${p.line};border-radius:6px;background:#fff;color:#48647c;font-size:14px}
  </style></head><body><main class="canvas"><div class="topline"></div><header><div class="brand"><div class="mark">S</div><div><b>SCBKR 2.3</b><small>${en ? "Local Responsibility Chain Model" : "本地責任鏈語言模型"}</small></div></div><div class="badge">FREE · WINDOWS DESKTOP RC</div></header>
  <section class="layout"><div><div class="eyebrow">${en ? "FREE FRAMEWORK EXPERIENCE" : "FREE 框架體驗版"}</div><h1>${en ? "Local rules that models must actually follow." : "讓模型真正依照你確認的規則工作。"}</h1><p class="intro">${en ? "Normal AI chat plus model-authored S/C/B/K/R confirmation sheets, owner signatures, four-store authority, replay, and token audit. You define and own your rules." : "一般 AI 聊天，加上模型協作 S／C／B／K／R 確認單、使用者簽名、四庫正式依據、回放與 Token 審計；規則由你定義並承擔。"}</p><div class="steps">${steps.map((s,i)=>`<div class="step"><i>${i+1}</i><span>${s}</span></div>`).join("")}</div><div class="stack"><span>LM Studio</span><span>Ollama</span><span>OpenAI-compatible</span><span>繁體中文</span><span>English</span></div></div>
  <div><div class="product-shot"><img src="${shot}"></div><div class="proof"><div><b>${en ? "Verified same-model A/B" : "同模型 A/B 已驗證"}</b><br><span>LM Studio · qwen2.5-3b-instruct · provider usage</span></div><strong>-69.55%</strong><span>${en ? "prompt tokens\n-68.82% total" : "提示 token\n總量 -68.82%"}</span></div></div></section>
  <footer class="footer"><span>${en ? "Created by Wen-Yao Hsu / ShenYao888pi · No official rule packs bundled" : "許文耀／沈耀888π · 不附沈耀正式規則包"}</span><span>github.com/HIJO790401/scbkr-local-responsibility-model</span></footer></main></body></html>`;
}

function flowHtml(locale) {
  const en = locale === "en";
  const steps = en ? [
    ["1","Hard route","Chat, authoring, rule answer, revision, storage, tools, or high risk"],
    ["2","Model authors","The connected model writes task-specific S/C/B/K/R and explanations"],
    ["3","Kernel validates","Schema, semantic separation, boundaries, evidence, and responsibility"],
    ["4","Owner decides","Only the user may edit, sign, review, and confirm storage"],
    ["5","Compile stores","LOGIC judges · CORPUS grounds · MEMORY personalizes · VECTOR recalls"],
    ["6","Rule-first answer","Build current_rule_package, post-check, then write replay"],
  ] : [
    ["1","硬路由","先分聊天、生成規則、規則回答、修改、入庫、工具與高風險動作"],
    ["2","模型草擬","連線模型依實際需求填寫 S／C／B／K／R 與每一層解釋"],
    ["3","Kernel 驗證","檢查格式、五維分工、邊界、依據與責任，不合格停在草稿"],
    ["4","使用者決定","只有使用者能修改、簽名、驗收與二次確認入庫"],
    ["5","編譯四庫","LOGIC 判斷 · CORPUS 依據 · MEMORY 偏好 · VECTOR 只召回"],
    ["6","規則優先回答","產生 current_rule_package、回答後檢查並留下回放"],
  ];
  const dims = en ? [["S","Subject","who and what"],["C","Causality","why and order"],["B","Boundary","limits and stop"],["K","Basis","formal evidence"],["R","Responsibility","owner and review"]] : [["S","主體","誰、什麼任務"],["C","因果","原因與順序"],["B","邊界","禁止與停止"],["K","依據","可引用證據"],["R","責任","誰驗收承擔"]];
  const accents=[p.blue,p.green,"#e28400",p.purple,p.red];
  return `<!doctype html><html><head><meta charset="utf-8"><style>${baseCss()}
    header{display:flex;align-items:center}h1{margin-top:42px;font-size:52px}.lead{margin-top:12px;color:${p.muted};font-size:21px}.flow{display:grid;grid-template-columns:repeat(6,1fr);gap:14px;margin-top:42px}
    .node{position:relative;min-height:220px;padding:22px 20px;border:1px solid ${p.line};border-radius:8px;background:#fff;box-shadow:0 12px 35px rgba(34,74,113,.08)}.node:not(:last-child)::after{content:"›";position:absolute;right:-13px;top:88px;z-index:2;width:26px;height:40px;display:grid;place-items:center;color:${p.blue};background:#f7fbff;font-size:34px;font-weight:800}.node em{width:38px;height:38px;display:grid;place-items:center;border-radius:8px;color:#fff;background:${p.blue};font-style:normal;font-size:17px;font-weight:800}.node h2{margin-top:20px;font-size:21px}.node p{margin-top:12px;color:${p.muted};font-size:16px;line-height:1.55}
    .dimensions{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-top:26px}.dimension{display:grid;grid-template-columns:52px 1fr;align-items:center;gap:14px;padding:18px;border:1px solid ${p.line};border-top:5px solid var(--accent);border-radius:8px;background:#fff}.dimension strong{color:var(--accent);font-size:36px}.dimension b{display:block;font-size:19px}.dimension span{display:block;margin-top:4px;color:${p.muted};font-size:14px}
    .guardrail{display:grid;grid-template-columns:1.25fr 1fr 1fr;gap:15px;margin-top:25px}.guardrail div{padding:17px 20px;border-radius:8px;font-size:16px;line-height:1.5}.formal{border:1px solid #acd5c0;background:${p.greenSoft};color:#245b43}.candidate{border:1px solid #f0cf8b;background:${p.yellowSoft};color:#76511c}.blocked{border:1px solid #f0b9bd;background:${p.redSoft};color:#81353a}
  </style></head><body><main class="canvas"><div class="topline"></div><header><div class="brand"><div class="mark">S</div><div><b>SCBKR 2.3</b><small>${en ? "Executable responsibility chain" : "可執行責任鏈"}</small></div></div><div class="badge">${en ? "MODEL ASSISTS · OWNER CONTROLS" : "模型協作 · 使用者掌權"}</div></header><h1>${en ? "From plain language to signed local authority" : "從人話需求，到可引用的本地正式規則"}</h1><p class="lead">${en ? "The model drafts. The kernel validates. The owner decides. Signed rules govern later model calls." : "模型寫草稿，Kernel 驗證，使用者決定；只有已簽名規則能控制後續模型回答。"}</p>
  <section class="flow">${steps.map(([n,t,d])=>`<article class="node"><em>${n}</em><h2>${t}</h2><p>${d}</p></article>`).join("")}</section><section class="dimensions">${dims.map(([k,t,d],i)=>`<article class="dimension" style="--accent:${accents[i]}"><strong>${k}</strong><div><b>${t}</b><span>${d}</span></div></article>`).join("")}</section><section class="guardrail"><div class="formal"><b>${en ? "Formal authority" : "正式依據"}</b><br>${en ? "Signed + reviewed + active LOGIC / CORPUS / MEMORY" : "已簽名、已驗收、Active 的 LOGIC／CORPUS／MEMORY"}</div><div class="candidate"><b>VECTOR</b><br>${en ? "Recall candidate only" : "只找候選，不可單獨當 K"}</div><div class="blocked"><b>${en ? "Model boundary" : "模型邊界"}</b><br>${en ? "Cannot sign, store, activate, or execute tools" : "不能簽名、入庫、啟用或自行執行工具"}</div></section><footer class="footer"><span>${en ? "FREE framework experience · user-owned rules" : "FREE 框架體驗版 · 使用者自訂規則"}</span><span>SCBKR · 2026</span></footer></main></body></html>`;
}

function tokenHtml(locale) {
  const en=locale==="en";
  return `<!doctype html><html><head><meta charset="utf-8"><style>${baseCss()}
    header{display:flex;align-items:center}h1{margin-top:42px;font-size:53px}.lead{margin-top:12px;color:${p.muted};font-size:21px}.audit{display:grid;grid-template-columns:1.15fr .85fr;gap:34px;margin-top:42px}.chart,.evidence{min-height:680px;padding:34px;border:1px solid ${p.line};border-radius:8px;background:#fff;box-shadow:0 14px 40px rgba(34,74,113,.08)}.chart h2,.evidence h2{font-size:25px}
    .bar-label{display:flex;justify-content:space-between;margin-top:34px;font-size:18px;font-weight:700}.bar{height:72px;margin-top:10px;overflow:hidden;border-radius:7px;background:#e7eef5}.bar div{height:100%;display:flex;align-items:center;padding-left:22px;color:#fff;font-size:23px;font-weight:800}.bar-a div{width:100%;background:#49647e}.bar-b div{width:30.45%;min-width:220px;background:${p.blue}}.result{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:34px}.metric{padding:23px;border-radius:8px;border:1px solid #b9e1cd;background:${p.greenSoft}}.metric strong{color:${p.green};font-size:46px}.metric span{display:block;margin-top:7px;color:#3f6455;font-size:16px}.method{margin-top:28px;padding:18px;border-left:5px solid ${p.blue};background:${p.blueSoft};color:#315c86;font-size:16px;line-height:1.55}
    .evidence ul{display:grid;gap:19px;margin:30px 0 0;padding:0;list-style:none}.evidence li{position:relative;padding-left:34px;color:#35516b;font-size:18px;line-height:1.5}.evidence li::before{content:"✓";position:absolute;left:0;color:${p.green};font-size:20px;font-weight:900}.warning{margin-top:28px;padding:18px;border:1px solid #f0cf8b;border-radius:8px;background:${p.yellowSoft};color:#76511c;font-size:16px;line-height:1.55}code{font-family:Consolas,monospace;color:#215a91}
  </style></head><body><main class="canvas"><div class="topline"></div><header><div class="brand"><div class="mark">T</div><div><b>SCBKR Token Audit</b><small>${en ? "Measured cost transparency" : "可追溯的成本透明"}</small></div></div><div class="badge">VERIFIED · SAME MODEL A/B</div></header><h1>${en ? "Fewer tokens after the rule is solved once" : "規則解決一次，後續不必重塞全部上下文"}</h1><p class="lead">${en ? "A bounded full-context control and a minimal current_rule_package were sent to the same local model." : "完整上下文對照組與最小 current_rule_package，送到同一個本地模型各跑一次。"}</p>
  <section class="audit"><article class="chart"><h2>${en ? "Provider-reported prompt usage" : "模型服務回傳的提示用量"}</h2><div class="bar-label"><span>A · ${en ? "bounded full context" : "受控完整上下文"}</span><b>5,658</b></div><div class="bar bar-a"><div>5,658 tokens</div></div><div class="bar-label"><span>B · <code>current_rule_package</code></span><b>1,723</b></div><div class="bar bar-b"><div>1,723</div></div><div class="result"><div class="metric"><strong>-69.55%</strong><span>${en ? "prompt tokens" : "提示 token"}</span></div><div class="metric"><strong>-68.82%</strong><span>${en ? "total tokens" : "提示加輸出總量"}</span></div></div><div class="method">LM Studio · qwen2.5-3b-instruct · one call per variant · provider usage · same signed-rule task</div></article>
  <article class="evidence"><h2>${en ? "What makes this result auditable" : "為什麼這次數字可以驗證"}</h2><ul><li>${en ? "Same provider and exact same model identity" : "同一個 provider、同一個模型身分"}</li><li>${en ? "Both variants made one real model call" : "A／B 各自真的呼叫模型一次"}</li><li>${en ? "Usage, prompt hashes, outputs, and latency recorded" : "保存 usage、prompt hash、輸出與延遲"}</li><li>${en ? "Signed LOGIC / CORPUS / MEMORY were formal authority" : "正式依據只取已簽名 LOGIC／CORPUS／MEMORY"}</li><li>VECTOR ${en ? "remained recall-only" : "維持只召回、不作正式依據"}</li><li>${en ? "Chat history was not formal authority" : "聊天歷史沒有被當成正式依據"}</li></ul><div class="warning"><b>${en ? "Honest display rule" : "誠實顯示規則"}</b><br>${en ? "This is one task benchmark, not a universal guarantee. Only same-model, two-call provider usage may display VERIFIED." : "這是單一任務基準，不是普遍保證；只有同模型雙呼叫且取得 provider usage，才可標 VERIFIED。"}</div></article></section><footer class="footer"><span>${en ? "Evidence digest: reports/token_ab_verified_free.json" : "證據摘要：reports/token_ab_verified_free.json"}</span><span>SCBKR FREE · 2026</span></footer></main></body></html>`;
}

async function render(name, html) {
  const page=await browser.newPage({viewport:{width:1920,height:1080},deviceScaleFactor:1,colorScheme:"light"});
  await page.setContent(html,{waitUntil:"load"});
  await page.screenshot({path:path.join(outputDir,name)});
  await page.close();
}

await captureProductUi();
await render("scbkr-hero.png",heroHtml("zh-TW"));
await render("scbkr-hero-en.png",heroHtml("en"));
await render("scbkr-rule-flow.png",flowHtml("zh-TW"));
await render("scbkr-rule-flow-en.png",flowHtml("en"));
await render("scbkr-token-audit.png",tokenHtml("zh-TW"));
await render("scbkr-token-audit-en.png",tokenHtml("en"));
await browser.close();
console.log(`Rendered SCBKR product cards to ${outputDir}`);
