import { useEffect, useRef, useState } from "react";
import {
  Activity, Archive, Bot, Box, Braces, Check, ChevronRight, CircleGauge, CircleHelp,
  Cloud, Database, Eye, FileKey, FolderOpen, Globe2, HardDrive, Info, KeyRound, Languages, Lock, Mail, Menu, MessageSquare,
  Monitor, Network, Play, Plus, RefreshCw, Save, Search, Send, Settings, ShieldCheck,
  SlidersHorizontal, Smartphone, Sparkles, SquareTerminal, Rocket, Wrench, X, AlertTriangle, BrainCircuit, CheckCircle2, Wifi,
  GitBranch, Power, Trash2,
} from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { getMessages, normalizeLocale, type Locale } from "./i18n";
import { isLoopbackHostname, isTauriDesktopHostname, resolveApiBaseUrl } from "./apiBase";
import type {
  ChatResponse,
  CurrentRulePackage,
  ModelSettings,
  PostCheck,
  ScbkrDimensionKey,
  TaskSummary,
  TokenCostAudit,
} from "./types";

const TOKEN_KEY = "scbkr.companionToken";
const BACKEND_KEY = "scbkr.activeBackendUrl";
const LOCALE_KEY = "scbkr.locale";
const ONBOARDING_KEY = "scbkr.onboarding.2.3";
const dims: ScbkrDimensionKey[] = ["S", "C", "B", "K", "R"];
const dimColor: Record<ScbkrDimensionKey, string> = { S: "blue", C: "cyan", B: "yellow", K: "red", R: "green" };
const dimensionNames: Record<ScbkrDimensionKey, { zh: string; en: string }> = {
  S: { zh: "誰、什麼事、何時適用", en: "Who, what, and when it applies" },
  C: { zh: "為什麼成立、先判什麼再判什麼", en: "Why it applies and the decision order" },
  B: { zh: "不能做什麼、何時必須停止", en: "What is forbidden and when to stop" },
  K: { zh: "憑什麼判、哪些來源能引用", en: "What supports it and what may be cited" },
  R: { zh: "誰承擔、怎樣驗收、誰能簽名", en: "Who is accountable, accepts, and signs" },
};

type View = "command" | "rules" | "workbench" | "tools" | "data" | "runtime" | "model" | "launch" | "about" | "more";
type CommandMode = "chat" | "web" | "search" | "rule";
type Rule = Record<string, any>;
type Tool = Record<string, any>;
type WorkflowCard = {
  id: string;
  kind: "advisory" | "suggestion" | "task" | "rule";
  title: string;
  summary: string;
  state: string;
  details?: string[];
  taskId?: string;
  ruleId?: string;
  objectType?: string;
  suggestedStores?: string[];
  suggestion?: Record<string, any>;
};
type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  card?: WorkflowCard;
  rulePackage?: CurrentRulePackage;
  postCheck?: PostCheck;
  tokenAudit?: TokenCostAudit;
};
type RuleAssistStatus = {
  plan_level?: "FREE" | string;
  locale?: string;
  active_plan?: Record<string, any>;
  catalog?: Record<string, any>[];
  identity?: Record<string, any>;
  mock_model_enabled?: boolean;
};

function initialBackend() {
  const stored = localStorage.getItem(BACKEND_KEY);
  if (stored) return stored.replace(/\/+$/, "");
  return resolveApiBaseUrl({ protocol: location.protocol, hostname: location.hostname, port: location.port, search: location.search, envApiUrl: import.meta.env.VITE_SCBKR_API_URL }).replace(/\/+$/, "");
}

function captureToken() {
  const token = new URLSearchParams(location.search).get("companion_token");
  if (token) localStorage.setItem(TOKEN_KEY, token);
}

function human(value: any): string {
  if (Array.isArray(value)) return value.join("\n");
  if (value && typeof value === "object") return Object.values(value).filter(Boolean).join("\n");
  return String(value ?? "");
}

function readableItems(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.flatMap((item) => readableItems(item)).filter(Boolean);
  }
  if (value && typeof value === "object") {
    return Object.values(value as Record<string, unknown>).flatMap((item) => readableItems(item)).filter(Boolean);
  }
  const text = String(value ?? "").trim();
  return text ? [text] : [];
}

function compactPublicText(value: unknown, en: boolean, limit = 7): string {
  const technicalOnly = (text: string) => !text
    || /^(true|false|user|confirmed|json|local-sidecar-api)$/i.test(text)
    || /^(?:[a-f0-9]{32,}|SCBKR_TEST_|[A-Z][A-Z0-9_]{5,})/.test(text)
    || /^\d{4}-\d{2}-\d{2}T/.test(text)
    || text.includes("schemas/")
    || text.includes("=");
  const friendly = (text: string) => text
    .replace(/OWNER_REVIEW/g, en ? "user review" : "等待使用者確認")
    .replace(/CLOSE_CANDIDATE_ONLY_BEFORE_OWNER_SIGNATURE|CLOSE/g, en ? "formally accepted" : "正式成立")
    .replace(/owner_signed/g, en ? "signed by user" : "使用者已簽名")
    .replace(/review_passed/g, en ? "review passed" : "驗收通過")
    .replace(/storage_confirmed/g, en ? "storage confirmed" : "已確認入庫")
    .replace(/\bfallback\b/gi, en ? "replacement draft" : "替代草稿")
    .trim();
  const items = readableItems(value)
    .map((item) => friendly(item.trim()))
    .filter((item) => !technicalOnly(item))
    .filter((item, index, all) => all.indexOf(item) === index)
    .slice(0, limit)
    .map((item) => item.length > 220 ? `${item.slice(0, 217)}...` : item);
  if (items.length === 0) return "";
  return items.length === 1 ? items[0] : items.map((item) => `• ${item}`).join("\n");
}

function dimensionDraftText(content: Record<string, any>, dimension: ScbkrDimensionKey, en: boolean): string {
  for (const key of ["owner_draft_content", "model_draft_content", "content"]) {
    const value = content[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  const preferredFields: Record<ScbkrDimensionKey, string[]> = {
    S: ["task_subject", "task_name", "user_instruction", "input_content"],
    C: ["core_logic", "flow_steps", "execution_order", "event_flow", "dependencies"],
    B: ["stop_conditions", "data_write_scope", "failure_conditions", "external_scope"],
    K: ["references", "source_credibility", "model_basis", "framework_choice"],
    R: ["acceptance_criteria", "basic_formation_conditions", "basic_failure_reminders", "expected_outputs", "replay_requirements"],
  };
  return compactPublicText(preferredFields[dimension].flatMap((key) => readableItems(content[key])), en);
}

function publicNextAction(value: unknown, en: boolean): string {
  const action = String(value || "").toLowerCase();
  if (!action) return en ? "Review the draft" : "逐欄檢查草稿";
  if (action.includes("refresh_revision")) return en ? "Reload the latest rule and review a new revision" : "重新載入最新版規則並檢查新草稿";
  if (action.includes("retry") || action.includes("model_connection")) return en ? "Reconnect the model and try again" : "重新連接模型後再試一次";
  if (action.includes("owner_review") || action.includes("signature")) return en ? "Review every field, then sign" : "逐欄確認後由你簽名";
  if (action.includes("storage")) return en ? "Review and confirm storage" : "驗收並二次確認入庫";
  return en ? "Continue with the next visible step" : "依畫面進入下一步";
}

function providerLabel(value: unknown): string {
  const provider = String(value || "").toLowerCase();
  if (provider === "lm_studio") return "LM Studio";
  if (provider === "ollama") return "Ollama";
  if (provider === "openai_compatible") return "OpenAI-compatible";
  if (provider === "sandbox_mock_model") return "UI acceptance model";
  return String(value || "Model");
}

function capabilityGapLabel(value: unknown, en: boolean): string {
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (/[^\x00-\x7F]/.test(raw) || /\s/.test(raw)) return raw;
  const labels: Record<string, [string, string]> = {
    s_role_unresolved: ["主體、任務或適用時機還不夠清楚", "The subject, task, or trigger is not clear enough"],
    model_explanations_missing: ["模型尚未解釋每一維為什麼這樣寫", "The model has not explained every dimension"],
    c_b_roles_overlapping: ["因果流程與禁止邊界寫得太相似", "Causality and boundary content overlap too much"],
    unrequested_identity_injection: ["草稿加入了使用者沒有指定的身分", "The draft introduced an identity the user did not request"],
    k_signature_as_basis: ["簽名被誤寫成判斷依據，需改成正式來源", "A signature was treated as evidence instead of a formal source"],
    support_fields_missing: ["缺資料、風險或待確認項目尚未補齊", "Missing-data, risk, or confirmation notes are incomplete"],
  };
  return labels[raw]?.[en ? 1 : 0] || (en ? "One part of the five-dimension draft still needs review" : "五維草稿仍有一處需要人工確認");
}

function packageItemTitle(value: Record<string, unknown>, en: boolean): string {
  return String(
    value.rule_name || value.title || value.name || value.rule || value.summary || value.content
    || (en ? "Signed local item" : "已簽名本機項目"),
  );
}

function productWelcome(en: boolean, manifest?: Record<string, any> | null): string {
  const manifestWelcome = manifest?.welcome;
  const configured = typeof manifestWelcome === "string"
    ? manifestWelcome.trim()
    : typeof manifestWelcome === "object"
      ? String(manifestWelcome?.[en ? "en" : "zh-TW"] || "").trim()
      : "";
  if (configured) return configured;
  return en
    ? [
      "I am the FREE public experience edition of SCBKR Responsibility Chain Language Model 2.3, created by Wen-Yao Hsu / ShenYao888pi, founder of Semantic Firewall and author of the product and its rules.",
      "",
      "I can chat normally and let your connected model turn plain language into an editable S/C/B/K/R confirmation sheet: Subject, Causality, Boundary, Basis, and Responsibility.",
      "",
      "Only you may review and sign. A signed rule is compiled into the four stores and becomes formal authority ahead of chat context. FREE lets you create and own your own rules; it does not include ShenYao's private official rule packs. The interface fully supports Traditional Chinese and English.",
      "",
      "Chat normally, or tell me: \"Turn this into my local rule.\" For official rule packs, deep customization, or commercial workflows, wait for a future product or request a commercial collaboration.",
    ].join("\n")
    : [
      "我是 SCBKR 責任鏈語言模型 2.3 的 FREE 公開體驗版，由許文耀／沈耀888π（語意防火牆創辦人、產品與規則作者）建立。",
      "",
      "我能像一般 AI 聊天，也能讓你連接的模型把人話整理成可編輯的 S／C／B／K／R 確認單：S 主體、C 因果、B 邊界、K 依據、R 責任。",
      "",
      "只有你能確認與簽名；簽名後規則才會編譯進四庫，並優先於聊天上下文成為後續回答依據。FREE 版讓你建立並承擔自己的規則，不包含沈耀的私人正式規則包。介面完整支援繁體中文與英文。",
      "",
      "直接聊天，或告訴我「把這個寫成我的本地規則」。如需沈耀正式規則包、深度客製或商業流程，請等待後續產品或洽商業合作。",
    ].join("\n");
}

function fieldTitle(key: string, en: boolean) {
  const labels: Record<string, [string, string]> = {
    task_subject: ["任務主體", "Subject"], user_instruction: ["使用者原句", "Owner request"], output_format: ["預期輸出", "Expected output"], model_draft_content: ["模型原文", "Model draft"],
    flow_steps: ["處理步驟", "Steps"], core_logic: ["核心邏輯", "Core logic"], dependencies: ["需要的資料", "Dependencies"],
    stop_conditions: ["停止條件", "Stop conditions"], data_write_scope: ["可寫入範圍", "Write scope"], error_handling: ["錯誤處理", "Error handling"],
    references: ["正式依據", "References"], source_credibility: ["來源狀態", "Source status"], acceptance_criteria: ["驗收標準", "Acceptance criteria"],
    expected_outputs: ["交付內容", "Deliverables"], signature_status: ["簽名狀態", "Signature status"], review_status: ["驗收狀態", "Review status"],
    formation_conditions: ["成立條件", "Formation conditions"], failure_conditions: ["失效條件", "Failure conditions"], repair_path: ["修復路徑", "Repair path"],
    evidence_policy: ["引用政策", "Evidence policy"], closure_state: ["閉環狀態", "Closure state"], structure_assist: ["結構輔助", "Structure assist"],
    store_role: ["四庫角色", "Store role"], store_purpose: ["四庫用途", "Store purpose"], citation_policy: ["引用政策", "Citation policy"],
  };
  return labels[key]?.[en ? 1 : 0] || key.split("_").join(" ");
}

function scopeSummary(scope: Record<string, any> | undefined, en: boolean) {
  const value = scope || {};
  const row = (labelZh: string, labelEn: string, items: any) => `${en ? labelEn : labelZh}: ${human(items) || (en ? "Any" : "不限")}`;
  return [
    row("任務", "Tasks", value.task_types),
    row("動作", "Actions", value.actions),
    row("關鍵字", "Keywords", value.keywords),
    row("工具", "Tools", value.tools),
  ].join("\n");
}

function listText(value: any): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item)).filter(Boolean);
  if (typeof value === "string" && value.trim()) return [value.trim()];
  return [];
}

function compilerStatusLabel(status: string | undefined, en: boolean) {
  if (!status) return en ? "Waiting for model" : "等待模型草擬";
  const labels: Record<string, [string, string]> = {
    model_assisted_rulebook: ["模型已完成五維草擬", "Model completed the five-dimension draft"],
    model_capability_limited: ["模型已草擬，結構待補強", "Model drafted; structure needs reinforcement"],
    model_compiled: ["模型已補寫表單", "Model filled the form"],
    model_unavailable: ["模型未完成草擬", "Model authoring did not complete"],
    model_timeout: ["模型本次生成逾時", "Model generation timed out"],
    model_rulebook_schema_invalid: ["模型草稿需要修正", "Model draft needs repair"],
  };
  return labels[String(status)]?.[en ? 1 : 0] || (en ? "Waiting for model validation" : "等待模型驗證");
}

function readableStatus(status: string, en: boolean) {
  const labels: Record<string, [string, string]> = {
    draft: ["草案", "Draft"],
    confirmed: ["已簽名", "Signed"],
    generating: ["生成中", "Generating"],
    model_compiling: ["模型正在編譯", "Model compiling"],
    model_unavailable: ["模型未連線", "Model unavailable"],
    model_timeout: ["模型已連線，本次生成逾時", "Model online; generation timed out"],
    model_rulebook_schema_invalid: ["模型表單格式不合格", "Model form needs repair"],
    model_capability_limited: ["模型可草擬，本次待補強", "Draft ready; this task needs reinforcement"],
    waiting_review: ["待驗收", "Review"],
    completed: ["已完成", "Done"],
    storage_committed: ["已入庫", "Stored"],
    waiting_user_confirm: ["待逐欄確認", "Review each field"],
    waiting_storage_confirm: ["等待二次確認入庫", "Confirm storage"],
    storage_requested: ["入庫計畫已建立", "Storage plan ready"],
    storage_conflict: ["來源規則已更新，入庫已停止", "Source rule changed; storage stopped"],
    review_passed: ["驗收通過", "Review passed"],
    review_failed: ["驗收失敗", "Review failed"],
    rollback_requested: ["已退回修改", "Returned for revision"],
    draft_failed: ["草擬失敗", "Draft failed"],
    model_validation_failed: ["模型草稿未通過檢查", "Model draft failed validation"],
    active: ["已啟用", "Active"],
    disabled: ["已停用", "Disabled"],
    archived: ["已封存", "Archived"],
    superseded: ["已被新版取代", "Superseded"],
    revoked: ["已撤銷", "Revoked"],
    deleted: ["已刪除（保留回放）", "Deleted (replay retained)"],
  };
  return labels[String(status || "draft").toLowerCase()]?.[en ? 1 : 0] || (en ? "In progress" : "處理中");
}

function apiErrorMessage(body: string, status: number, en: boolean): string {
  try {
    const parsed = JSON.parse(body);
    const detail = parsed?.detail ?? parsed;
    const code = typeof detail === "object" && detail ? String(detail.code || "") : "";
    if (status === 409 && (code === "state_conflict_reconfirmation_required" || code.includes("evidence_snapshot"))) {
      return en
        ? "The source changed while this draft was waiting for confirmation. Nothing was written. Reload the latest rule, review the differences, and sign again."
        : "這份草稿等待確認時，來源規則已被更新；系統沒有寫入任何資料。請重新載入最新版、檢查差異後再簽名。";
    }
    if (typeof detail === "string") return detail;
    if (detail && typeof detail.message === "string") return detail.message;
    return JSON.stringify(detail || parsed);
  } catch {
    return body || (en ? `Request failed (${status})` : `請求失敗（${status}）`);
  }
}

function riskLevelLabel(value: unknown, en: boolean) {
  const labels: Record<string, [string, string]> = {
    low: ["低風險", "Low risk"],
    medium: ["中度風險", "Medium risk"],
    high: ["高風險", "High risk"],
    critical: ["重大風險", "Critical risk"],
  };
  return labels[String(value || "medium").toLowerCase()]?.[en ? 1 : 0] || (en ? "Needs review" : "需要確認");
}

function ruleSourceLabel(value: unknown, en: boolean) {
  const source = String(value || "").toLowerCase();
  if (source.includes("free") || source.includes("owner") || source.includes("user")) return en ? "Local user rule" : "本機使用者規則";
  if (source.includes("model")) return en ? "Model-assisted draft" : "模型協作草稿";
  return en ? "Local rule" : "本機規則";
}

function ruleAuthorLabel(value: unknown, en: boolean) {
  const author = String(value || "").trim();
  if (!author || ["user", "owner", "local_user"].includes(author.toLowerCase())) return en ? "Local user" : "本機使用者";
  return author;
}

function versionNoteLabel(value: unknown, en: boolean) {
  const note = String(value || "").trim();
  if (!note) return en ? "No change note" : "尚無版本說明";
  if (/compiled from owner-signed scbkr workbench flow/i.test(note)) return en ? "Compiled after user signature and Workbench review." : "由使用者簽名並完成工作台驗收後編譯。";
  return note;
}

function ruleOverview(rule: Rule, en: boolean): string {
  const subject = rule?.rule_scope?.task_subject;
  const instruction = rule?.scbkr_summary?.S?.user_instruction || rule?.scbkr_summary?.S?.input_content;
  const concise = compactPublicText([subject, instruction], en, 2).replace(/[•\n]/g, " ").replace(/\s+/g, " ").trim();
  if (concise) return `${en ? "Applies to" : "適用主體"}：${concise}`;
  const firstLine = String(rule?.rule_text || "").split(/\r?\n/).map((line) => line.trim()).find(Boolean) || "";
  if (firstLine) return firstLine.slice(0, 140);
  return en ? "Open this rule to inspect its five dimensions." : "點開查看這條規則的五維內容。";
}

function workflowStateLabel(card: WorkflowCard, drafting: boolean, en: boolean) {
  if (drafting) return en ? "Model drafting" : "模型草擬中";
  if (card.kind === "advisory") return en ? "Waiting for your choice" : "等待你選擇";
  if (card.kind === "suggestion") return en ? "Not stored" : "尚未入庫";
  return readableStatus(card.state, en);
}

function responsibilityHolderLabel(value: unknown, en: boolean) {
  const holder = String(value || "").trim().toLowerCase();
  if (!holder) return en ? "Waiting for user signature" : "等待使用者簽名";
  if (["user", "owner", "user_signed", "owner_signed"].includes(holder)) return en ? "Signed by user" : "使用者已簽名";
  return String(value).replace(/_/g, " ");
}

function storeDisplayMetadata(targetValue: unknown, statusValue: unknown, en: boolean) {
  const target = String(targetValue || "").replace("vector_db", "vector");
  const status = String(statusValue || "active").toLowerCase();
  const stores: Record<string, { label: [string, string]; role: [string, string]; purpose: [string, string]; citation: [string, string] }> = {
    logic: {
      label: ["規則庫", "Rule store"],
      role: ["可執行規則判準", "Executable rule authority"],
      purpose: ["保存五維規則、成立與失效條件、邊界、驗收與責任。", "Stores five-dimension rules, validity, invalidation, boundaries, review, and responsibility."],
      citation: ["已簽名並驗收後，可作正式規則依據", "Citable as formal rule authority after signature and review"],
    },
    corpus: {
      label: ["資料庫", "Source data store"],
      role: ["使用者確認的正式資料", "User-confirmed source material"],
      purpose: ["保存使用者確認過的文件、內容與正式資料。", "Stores documents, content, and facts confirmed by the user."],
      citation: ["已簽名並驗收後，可作正式資料依據", "Citable as formal source material after signature and review"],
    },
    memory: {
      label: ["記憶庫", "User memory store"],
      role: ["任務命中時使用的長期偏好", "Task-matched long-term preferences"],
      purpose: ["保存語氣、格式、禁止用語與長期判斷偏好，不污染一般聊天。", "Stores tone, format, forbidden wording, and long-term preferences without polluting ordinary chat."],
      citation: ["只在命中相符任務時套用", "Applied only when the current task matches"],
    },
    vector: {
      label: ["檢索庫", "Retrieval store"],
      role: ["相似候選召回", "Similar-candidate retrieval"],
      purpose: ["只負責找候選；命中後仍須回四庫確認。", "Finds candidates only; every hit must be verified against the formal stores."],
      citation: ["只做召回，不可單獨作正式依據", "Retrieval only; never formal authority by itself"],
    },
  };
  const statuses: Record<string, [string, string]> = {
    active: ["可引用", "Citable"],
    superseded: ["已被新版取代", "Superseded"],
    archived: ["已封存", "Archived"],
    revoked: ["已撤銷", "Revoked"],
  };
  const store = stores[target] || {
    label: [target || "資料", target || "Data"], role: ["本機資料", "Local data"],
    purpose: ["由本機 Runtime 管理。", "Managed by the local runtime."], citation: ["依目前狀態判定", "Citation depends on current status"],
  };
  return {
    label: store.label[en ? 1 : 0],
    role: store.role[en ? 1 : 0],
    purpose: store.purpose[en ? 1 : 0],
    citation: store.citation[en ? 1 : 0],
    status: (statuses[status] || [status, status])[en ? 1 : 0],
  };
}

function toolStatusLabel(status: string, en: boolean) {
  if (status === "enabled") return en ? "Enabled" : "已啟用";
  if (status === "standby") return en ? "Planned" : "規劃中";
  return en ? "Confirmation required" : "需要確認";
}

function toolActionLabel(value: unknown, en: boolean) {
  const labels: Record<string, [string, string]> = {
    observe: ["查看", "Observe"],
    search: ["搜尋", "Search"],
    draft: ["建立草稿", "Draft"],
    execute: ["執行", "Execute"],
    send: ["寄送", "Send"],
    publish: ["發布", "Publish"],
    store: ["寫入資料", "Store"],
  };
  const key = String(value || "").toLowerCase();
  return labels[key]?.[en ? 1 : 0] || (en ? "Needs review" : "需要確認");
}

function toolPermissionLabel(value: unknown, en: boolean) {
  const labels: Record<string, [string, string]> = {
    web_search: ["網路搜尋權限", "Web search permission"],
    external_api: ["外部 API 權限", "External API permission"],
    local_file_access: ["本機檔案權限", "Local file permission"],
    storage_write: ["資料寫入權限", "Storage write permission"],
    memory_write: ["記憶寫入權限", "Memory write permission"],
    email_read: ["信箱讀取權限", "Email read permission"],
    email_send: ["信件寄送權限", "Email send permission"],
    model_generate: ["模型生成權限", "Model generation permission"],
  };
  const key = String(value || "").toLowerCase();
  return labels[key]?.[en ? 1 : 0] || String(value || "").replace(/_/g, " ");
}

function toolListLabel(value: unknown, en: boolean, kind: "action" | "permission") {
  const items = Array.isArray(value) ? value : value ? [value] : [];
  if (!items.length) return en ? "No additional permission" : "不需額外權限";
  return items.map((item) => kind === "action" ? toolActionLabel(item, en) : toolPermissionLabel(item, en)).join(en ? ", " : "、");
}

function toolExecutionStatusLabel(value: unknown, en: boolean) {
  const key = String(value || "").toLowerCase();
  if (key.includes("no_execution") || key.includes("gate_only")) return en ? "Permission check only; nothing executed" : "只完成權限檢查，尚未執行";
  if (key.includes("blocked") || key.includes("denied")) return en ? "Blocked before execution" : "已在執行前擋下";
  if (key.includes("authorized") || key.includes("allowed")) return en ? "Authorized; waiting for explicit execution" : "已授權，等待明確執行";
  return en ? "Waiting for permission check" : "等待權限檢查";
}

function RuleFlowSurface({
  en,
  status,
  activeRules,
  citations,
  tokensAvoided,
  planLevel,
  onChat,
  onRule,
  onDraft,
  onData,
}: {
  en: boolean;
  status: string;
  activeRules: number;
  citations: number;
  tokensAvoided: number;
  planLevel: string;
  onChat: () => void;
  onRule: () => void;
  onDraft: () => void;
  onData: () => void;
}) {
  const steps = [
    { icon: MessageSquare, label: en ? "Chat" : "一般聊天", value: en ? "Ready" : "就緒", state: "active", action: onChat, aria: en ? "Open chat" : "開啟一般聊天" },
    { icon: Search, label: en ? "Rule assist" : "規則輔助", value: en ? "Chat first" : "聊天優先", state: "active", action: onRule, aria: en ? "Open rule assist" : "開啟規則輔助" },
    { icon: FileKey, label: en ? "Pending drafts" : "待簽名草案", value: readableStatus(status, en), state: status === "draft" ? "wait" : "active", action: onDraft, aria: en ? "Open pending drafts" : "開啟待簽名草案" },
    { icon: Database, label: en ? "Four stores" : "四庫引用", value: String(citations), state: citations > 0 ? "active" : "wait", action: onData, aria: en ? "Open four stores" : "開啟四庫引用" },
  ];
  return (
    <section className="plain-rule-surface" aria-label={en ? "Natural language routing" : "自然語言納編狀態"}>
      <div className="flow-summary">
        <div>
          <span>RULE ROUTER</span>
          <strong>{en ? "Chat-first workspace" : "聊天優先工作區"}</strong>
        </div>
        <div className="scbkr-rail" aria-label="SCBKR">
          {dims.map((dim) => <i key={dim} className={dimColor[dim]}>{dim}</i>)}
        </div>
      </div>
      <div className="flow-steps">
        {steps.map(({ icon: Icon, label, value, state, action, aria }) => (
          <button key={label} className={state} onClick={action} aria-label={aria}>
            <Icon size={16} />
            <b>{label}</b>
            <small>{value}</small>
          </button>
        ))}
      </div>
      <div className="flow-metrics">
        <span><ShieldCheck size={14} />{activeRules} {en ? "rules" : "規則"}</span>
        <span><Activity size={14} />{planLevel}</span>
        <span><Sparkles size={14} />{tokensAvoided} {en ? "tokens saved" : "Token 節省"}</span>
      </div>
    </section>
  );
}

function ContextAssistant({ en, title, context, onAsk }: { en: boolean; title: string; context: string; onAsk: (text: string) => Promise<string | null> }) {
  const [input, setInput] = useState("");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  async function ask() {
    const text = input.trim();
    if (!text || busy) return;
    setBusy(true);
    const result = await onAsk(`${context}\n\n${text}`);
    if (result) setAnswer(result);
    setBusy(false);
  }
  return <section className="context-assistant"><header><Bot size={18} /><div><span>CONTEXT MODEL</span><h3>{title}</h3></div></header>{answer && <div className="context-answer">{answer}</div>}<label>{en ? "Ask about this workspace" : "詢問目前工作區"}<textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void ask(); } }} /></label><button disabled={!input.trim() || busy} onClick={() => void ask()}><Send size={15} />{busy ? (en ? "Thinking" : "處理中") : (en ? "Ask model" : "詢問模型")}</button></section>;
}

export default function V2App() {
  captureToken();
  const [locale, setLocale] = useState<Locale>(normalizeLocale(localStorage.getItem(LOCALE_KEY) || "zh-TW"));
  const copy = getMessages(locale);
  const en = locale === "en";
  const [view, setView] = useState<View>("command");
  const [tourOpen, setTourOpen] = useState(() => localStorage.getItem(ONBOARDING_KEY) !== "done");
  const [tourStep, setTourStep] = useState(0);
  const [isMobile, setIsMobile] = useState(() => window.matchMedia("(max-width: 820px)").matches);
  const [health, setHealth] = useState("checking");
  const [runtimeSynced, setRuntimeSynced] = useState(false);
  const [backend, setBackend] = useState(initialBackend());
  const [tokenInput, setTokenInput] = useState(localStorage.getItem(TOKEN_KEY) || "");
  const [pairCode, setPairCode] = useState("");
  const [pairError, setPairError] = useState("");
  const [pairingRequired, setPairingRequired] = useState(
    () => (
      !isLoopbackHostname(location.hostname)
      && !isTauriDesktopHostname(location.hostname)
      && !localStorage.getItem(TOKEN_KEY)
    ),
  );
  const [model, setModel] = useState<ModelSettings | null>(null);
  const [manifest, setManifest] = useState<Record<string, any> | null>(null);
  const [companion, setCompanion] = useState<Record<string, any> | null>(null);
  const [pairing, setPairing] = useState<Record<string, any> | null>(null);
  const [rules, setRules] = useState<Rule[]>([]);
  const [packs, setPacks] = useState<Record<string, any>[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [traces, setTraces] = useState<Record<string, any>[]>([]);
  const [overview, setOverview] = useState<Record<string, any>>({});
  const [tokenMetrics, setTokenMetrics] = useState<TokenCostAudit>({});
  const [tokenBenchmark, setTokenBenchmark] = useState<Record<string, any>>({ status: "not_run", savings_verified: false });
  const [benchmarkRunning, setBenchmarkRunning] = useState(false);
  const [currentRulePackage, setCurrentRulePackage] = useState<CurrentRulePackage | null>(null);
  const [currentPostCheck, setCurrentPostCheck] = useState<PostCheck | null>(null);
  const [pricing, setPricing] = useState<Record<string, any>>({ currency: "USD", input_per_million: "", output_per_million: "", source: "not_configured" });
  const [ruleState, setRuleState] = useState<Record<string, any>>({ state: "independent", effective_label: "獨立使用者規則" });
  const [ruleAssist, setRuleAssist] = useState<RuleAssistStatus>({ plan_level: "FREE", locale: "zh-TW" });
  const [launchSettings, setLaunchSettings] = useState<Record<string, any>>({});
  const [readiness, setReadiness] = useState<Record<string, any>>({ checks: [] });
  const [permissions, setPermissions] = useState<Record<string, any>>({});
  const [notice, setNotice] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: productWelcome(en) },
  ]);
  const [draftingCardId, setDraftingCardId] = useState("");
  const messageListRef = useRef<HTMLDivElement>(null);
  const [chatInput, setChatInput] = useState("");
  const [commandMode, setCommandMode] = useState<CommandMode>("chat");
  const [naturalRuleText, setNaturalRuleText] = useState("");
  const [dataQuery, setDataQuery] = useState("");
  const [readResult, setReadResult] = useState<Record<string, any> | null>(null);
  const [dataSection, setDataSection] = useState("logic");
  const [dataSectionResult, setDataSectionResult] = useState<Record<string, any> | null>(null);
  const [expandedDataItem, setExpandedDataItem] = useState("");
  const [webResult, setWebResult] = useState<Record<string, any> | null>(null);
  const [taskInput, setTaskInput] = useState("");
  const [task, setTask] = useState<TaskSummary | null>(null);
  const [ownerSignature, setOwnerSignature] = useState("");
  const [dimensionEdits, setDimensionEdits] = useState<Record<string, string>>({});
  const [patchLayer, setPatchLayer] = useState<ScbkrDimensionKey>("B");
  const [patchInstruction, setPatchInstruction] = useState("");
  const [pendingPatch, setPendingPatch] = useState<Record<string, any> | null>(null);
  const [selectedStores, setSelectedStores] = useState(["logic", "corpus", "memory", "vector"]);
  const [ruleSignature, setRuleSignature] = useState("");
  const [revisionInstruction, setRevisionInstruction] = useState("");
  const [lifecycleReason, setLifecycleReason] = useState("");
  const [lifecycleConfirmed, setLifecycleConfirmed] = useState(false);
  const [ruleManageOpen, setRuleManageOpen] = useState(false);
  const [selectedRule, setSelectedRule] = useState<string>("");
  const [selectedTool, setSelectedTool] = useState("web_search");
  const [toolAction, setToolAction] = useState("search");
  const [toolConfirmed, setToolConfirmed] = useState(false);
  const [toolLauncherOpen, setToolLauncherOpen] = useState(false);
  const [toolResult, setToolResult] = useState<Record<string, any> | null>(null);
  const [modelForm, setModelForm] = useState({ provider: "lm_studio", mode: "local", base_url: "http://127.0.0.1:1234/v1", api_key: "", model_name: "", temperature: 0.2, max_tokens: 4096, context_length: 8192, timeout: 120 });

  const activeRules = rules.filter((rule) => rule.activation_status === "active").length;
  const citations = Number(task?.data_center_context?.evidence_packet?.authority_count || 0);
  const status = task?.status || "draft";
  const activePlan = ruleAssist.active_plan || {};
  const planLevel = String(ruleAssist.plan_level || "FREE");
  const replyLocale = ruleAssist.locale && ruleAssist.locale !== "auto" ? ruleAssist.locale : locale;

  async function api<T>(path: string, init?: RequestInit): Promise<T> {
    const token = localStorage.getItem(TOKEN_KEY) || "";
    const response = await fetch(`${backend}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(token ? { "X-SCBKR-Companion-Token": token } : {}), ...(init?.headers || {}) },
    });
    if (!response.ok) {
      if (response.status === 401 && !isLoopbackHostname(location.hostname)) setPairingRequired(true);
      const body = await response.text();
      throw new Error(apiErrorMessage(body, response.status, en));
    }
    return response.json() as Promise<T>;
  }

  async function apiPlainPost<T>(path: string, payload: Record<string, any>): Promise<T> {
    const token = localStorage.getItem(TOKEN_KEY) || "";
    const response = await fetch(`${backend}${path}`, {
      method: "POST",
      headers: { "Content-Type": "text/plain;charset=UTF-8", ...(token ? { "X-SCBKR-Companion-Token": token } : {}) },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const body = await response.text();
      throw new Error(apiErrorMessage(body, response.status, en));
    }
    return response.json() as Promise<T>;
  }

  async function run<T>(label: string, operation: () => Promise<T>): Promise<T | null> {
    try {
      const result = await operation();
      setNotice(`${label} · ${en ? "done" : "完成"}`);
      return result;
    } catch (error) {
      const rawMessage = String(error).replace("Error: ", "");
      const message = /failed to fetch|networkerror|typefailed to fetch/i.test(rawMessage)
        ? (en ? "The local model is busy or unavailable. Check Model Settings and retry." : "本地模型忙碌或未連線，請到模型設定測試後重試。")
        : /timeout/i.test(rawMessage)
          ? (en ? "The model took too long to respond. Check the model and retry." : "模型回覆時間過長，請確認模型狀態後重試。")
          : rawMessage === "task_create_response_timeout"
            ? (en ? "Draft compilation timed out. The model may still be loading; retry when ready." : "確認單編譯逾時，模型可能仍在載入；準備好後再試一次。")
            : rawMessage;
      setNotice(`${label} · ${message}`);
      return null;
    }
  }

  function withTimeout<T>(promise: Promise<T>, timeoutMs: number, message: string): Promise<T> {
    return new Promise((resolve, reject) => {
      const timer = window.setTimeout(() => reject(new Error(message)), timeoutMs);
      promise.then((value) => { window.clearTimeout(timer); resolve(value); }, (error) => { window.clearTimeout(timer); reject(error); });
    });
  }

  async function recoverLatestTask(rawInput: string): Promise<TaskSummary | null> {
    try {
      const list = await api<any>("/api/tasks");
      const normalized = rawInput.trim();
      const found = (list.tasks || []).find((item: TaskSummary) => String(item.raw_input || item.task_name || "").trim() === normalized);
      if (!found?.task_id) return null;
      return await api<TaskSummary>(`/api/tasks/${encodeURIComponent(found.task_id)}`);
    } catch {
      return null;
    }
  }

  function assistantEnvelope(content: string, declaration: Record<string, any> = ruleState) {
    const prefix = String(declaration.declaration_prefix || "").trim();
    const suffix = String(declaration.declaration_suffix || "").trim();
    const text = String(content || "").trim();
    if (!prefix) return text;
    if (text.startsWith(prefix)) return text;
    return `${prefix}\n\n${text}${suffix ? `\n\n${suffix}` : ""}`;
  }

  async function refreshAll(): Promise<boolean> {
    if (pairingRequired) return false;
    setRuntimeSynced(false);
    const result = await run(en ? "Refresh runtime" : "更新系統", async () => {
      const healthData = await api<any>("/health");
      const soft = async <T,>(path: string, fallback: T, timeoutMs = 10000, retries = 1): Promise<T> => {
        for (let attempt = 0; attempt <= retries; attempt += 1) {
          const controller = new AbortController();
          const timer = window.setTimeout(() => controller.abort(), timeoutMs);
          try {
            return await api<T>(path, { signal: controller.signal });
          } catch {
            if (attempt === retries) return fallback;
            await new Promise((resolve) => window.setTimeout(resolve, 350));
          } finally {
            window.clearTimeout(timer);
          }
        }
        return fallback;
      };
      const [modelData, manifestData, ruleData, taskData, overviewData, ruleStateData, permissionData] = await Promise.all([
        soft<ModelSettings>("/api/settings/model", model || { ...modelForm, enabled: false, last_test_status: "unknown", last_test_message: "" }),
        soft<any>(`/api/product/manifest?locale=${locale}`, manifest),
        soft<any>("/api/rules", { rules }),
        soft<any>("/api/tasks", { tasks }),
        soft<any>("/api/data-center/overview", overview || {}),
        soft<any>("/api/rule-state/status", ruleState || {}),
        soft<any>("/api/settings/permissions", permissions || {}),
      ]);
      const [companionData, packData, toolData, traceData, tokenData, tokenBenchmarkData, pricingData, ruleAssistData, launchData, readinessData] = await Promise.all([
        soft<any>("/api/companion/status", companion || {}, 8000, 0),
        soft<any>("/api/rulepacks", { rulepacks: packs }, 8000, 0),
        soft<any>("/api/tools", { tools }, 8000, 0),
        soft<any>("/api/tools/traces?limit=20", { traces }, 8000, 0),
        soft<any>("/api/metrics/token-efficiency", tokenMetrics || {}, 8000, 0),
        soft<any>("/api/metrics/token-ab/latest", tokenBenchmark || { status: "not_run", savings_verified: false }, 8000, 0),
        soft<any>("/api/metrics/pricing", pricing || {}, 8000, 0),
        soft<any>(`/api/rule-assist/status?locale=${locale}`, ruleAssist || { plan_level: "FREE", locale }),
        soft<any>("/api/launch/settings", launchSettings || {}, 8000, 0),
        soft<any>("/api/launch/readiness", readiness || { checks: [] }, 8000, 0),
      ]);
      return { healthData, modelData, manifestData, companionData, ruleData, packData, toolData, traceData, taskData, overviewData, tokenData, tokenBenchmarkData, pricingData, ruleStateData, ruleAssistData, launchData, readinessData, permissionData };
    });
    if (!result) { setHealth("offline"); setRuntimeSynced(false); return false; }
    setHealth("online");
    setModel(result.modelData);
    setManifest(result.manifestData);
    setCompanion(result.companionData);
    setRules(result.ruleData.rules || []);
    setPacks(result.packData.rulepacks || []);
    setTools(result.toolData.tools || []);
    setTraces(result.traceData.traces || []);
    setTasks(result.taskData.tasks || []);
    setOverview(result.overviewData || {});
    setTokenMetrics((current) => current.measurement_scope && current.measurement_scope !== "aggregate_history" ? current : (result.tokenData || {}));
    setTokenBenchmark(result.tokenBenchmarkData || { status: "not_run", savings_verified: false });
    setPricing(result.pricingData || pricing);
    setRuleState(result.ruleStateData || {});
    setRuleAssist(result.ruleAssistData || { plan_level: "FREE", locale: locale });
    setMessages((current) => current.length === 1 && current[0].role === "assistant"
      ? [{ role: "assistant", content: productWelcome(en, result.manifestData) }]
      : current);
    setLaunchSettings(result.launchData || {});
    setReadiness(result.readinessData || { checks: [] });
    setPermissions(result.permissionData || {});
    setModelForm((current) => ({ ...current, ...result.modelData, api_key: "" }));
    setRuntimeSynced(true);
    return true;
  }

  useEffect(() => {
    let cancelled = false;
    let retryTimer = 0;
    const refreshWithStartupRetry = async (attempt = 0) => {
      const synced = await refreshAll();
      if (!cancelled && !synced && !pairingRequired && attempt < 12) {
        retryTimer = window.setTimeout(() => void refreshWithStartupRetry(attempt + 1), 1500);
      }
    };
    void refreshWithStartupRetry();
    return () => {
      cancelled = true;
      window.clearTimeout(retryTimer);
    };
  }, [backend, locale, pairingRequired]);
  useEffect(() => { localStorage.setItem(LOCALE_KEY, locale); }, [locale]);
  useEffect(() => {
    const list = messageListRef.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [messages]);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 820px)");
    const update = () => setIsMobile(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  function taskCard(created: TaskSummary): WorkflowCard {
    const draft = (created as any).draft_object || {};
    return {
      id: `task-${created.task_id}`,
      kind: "task",
      title: draft.proposed_title || created.task_name || (en ? "Responsibility draft" : "責任鏈草案"),
      summary: draft.summary || created.raw_input || "",
      state: draft.state || created.status,
      taskId: created.task_id,
      objectType: draft.object_type || "task",
      suggestedStores: draft.suggested_store || [],
    };
  }

  function ruleCard(created: Record<string, any>): WorkflowCard {
    const rule = created.rule || {};
    const draft = created.draft_object || {};
    return {
      id: `rule-${rule.rule_id}`,
      kind: "rule",
      title: draft.proposed_title || rule.rule_name || (en ? "Rule draft" : "規則草案"),
      summary: draft.summary || rule.rule_text || "",
      state: draft.state || rule.activation_status || "DRAFTING",
      ruleId: rule.rule_id,
      objectType: "rule",
      suggestedStores: draft.suggested_store || ["logic"],
    };
  }

  function suggestionCard(suggestion: Record<string, any>, fallback: string): WorkflowCard {
    return {
      id: `suggestion-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      kind: "suggestion",
      title: suggestion.title || (en ? "Draft suggested" : "建議建立草案"),
      summary: suggestion.user_original || fallback,
      state: "SESSION_CONTEXT_ONLY",
      objectType: suggestion.suggested_type || "task",
      suggestedStores: [suggestion.suggested_write_direction || (en ? "memory" : "記憶庫")],
      suggestion,
    };
  }

  function zerothGateCard(routed: Record<string, any>, fallback: string): WorkflowCard {
    const suggestion = routed.suggestion || {};
    const original = suggestion.user_original || suggestion.suggested_instruction || fallback;
    const objectType = routed.draft_object_type || suggestion.suggested_type || (routed.intent === "create_new_rule_confirmation" ? "rule" : "task");
    return {
      id: `zeroth-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      kind: "advisory",
      title: en ? "Zeroth Principle Advisory Gate" : "第0原理建議閘",
      summary: en
        ? "Reusable rule intent detected. This stays as normal chat until you choose to draft a confirmation sheet."
        : "偵測到可重用規則需求；在你按下草擬之前，這仍然只是一般聊天，不會自動建規則或入庫。",
      state: "π | OWNER_REVIEW",
      details: en
        ? ["Gap: responsibility boundary, invalidation conditions, replay requirements.", "Next: enter the FREE draft confirmation layer."]
        : ["缺口：責任邊界、失效條件、回放條件。", "下一步：進入 FREE 草稿確認單。"],
      objectType,
      suggestedStores: [objectType === "rule" ? "logic" : "memory"],
      suggestion: {
        ...suggestion,
        user_original: original,
        suggested_instruction: suggestion.suggested_instruction || original,
        suggested_type: objectType,
        suggested_reason: suggestion.suggested_reason || "第0原理偵測到可重用需求",
        suggested_write_direction: objectType === "rule" ? "logic" : "memory",
        route_intent: routed.intent,
        advisory_gate: true,
      },
    };
  }

  function openDraftTask(created: TaskSummary, navigate = true) {
    setTask(created);
    const draftMetrics = (created as any).token_metrics || (created as any).scbkr?.token_metrics;
    if (draftMetrics) setTokenMetrics(draftMetrics);
    setOwnerSignature("");
    setDimensionEdits({});
    setTasks((current) => [
      created,
      ...current.filter((item) => item.task_id !== created.task_id),
    ]);
    if (navigate) setView("workbench");
  }

  function dismissCard(cardId: string) {
    setMessages((current) => current.map((item) => item.card?.id === cardId ? { ...item, card: { ...item.card, state: "DISMISSED" } } : item));
  }

  async function openTask(taskId: string) {
    const selected = await run(en ? "Open task" : "開啟草案", () => api<TaskSummary>(`/api/tasks/${taskId}`));
    if (selected) { setTask(selected); setView("workbench"); }
  }

  async function askWorkspace(scope: string, prompt: string) {
    const result = await run(en ? "Ask workspace model" : "詢問工作區模型", () => api<any>("/api/chat/general", { method: "POST", body: JSON.stringify({ message: `[${scope}] ${prompt}`, locale: replyLocale }) }));
    return result?.reply || null;
  }

  async function acceptSuggestion(card: WorkflowCard) {
    const accepted = await run(en ? "Prepare draft" : "準備草案", () => api<any>("/api/chat/suggestions/accept", { method: "POST", body: JSON.stringify({ suggestion: card.suggestion, user_original: card.summary }) }));
    if (!accepted) return;
    const created = await createTask(accepted.prefill?.suggested_instruction || card.summary, false, "create_confirmation", "memory");
    if (created) {
      setMessages((current) => current.map((item) => item.card?.id === card.id ? { ...item, card: taskCard(created) } : item));
    }
  }

  async function draftFromAdvisoryGate(card: WorkflowCard) {
    if (draftingCardId === card.id) return;
    setDraftingCardId(card.id);
    const instruction = String(card.suggestion?.suggested_instruction || card.suggestion?.user_original || card.summary || "").trim();
    if (!instruction) { setDraftingCardId(""); return; }
    const routeIntent = String(card.suggestion?.route_intent || "create_confirmation");
    const isRule = routeIntent === "create_new_rule_confirmation" || card.objectType === "rule";
    setMessages((current) => current.map((item) => item.card?.id === card.id ? {
      ...item,
      content: assistantEnvelope(en
        ? "SCBKR Kernel is compiling the confirmation sheet. I opened the Workbench so you can watch the model status."
        : "SCBKR Kernel 正在編譯確認單；已先打開工作台讓你看到模型狀態。",
      ruleState),
      card: { ...item.card, state: en ? "Compiling" : "編譯中" },
    } : item));
    const pendingTask = {
      task_id: `pending-${Date.now()}`,
      task_name: instruction.slice(0, 40),
      task_type: "general",
      raw_input: instruction,
      status: "model_compiling",
      confirmed: false,
      review_passed: false,
      storage_confirmed: false,
      runtime: "SCBKR model authoring in progress",
      rule_assist_plan: planLevel,
    } as TaskSummary;
    setTask(pendingTask);
    setOwnerSignature("");
    setDimensionEdits({});
    setView("workbench");
    try {
      let created = await run(en ? "Draft confirmation sheet" : "草擬確認單", () => withTimeout(apiPlainPost<TaskSummary>("/api/tasks/create-fast", { raw_input: instruction, task_type: "general", intent: isRule ? "create_new_rule_confirmation" : "create_confirmation", object_type: isRule ? "rule" : (card.objectType || "task"), create_scbkr_draft: true, locale: replyLocale, rule_assist_plan: planLevel }), isRule ? 1200000 : 15000, "task_create_response_timeout"));
      if (!created) created = await recoverLatestTask(instruction);
      if (created) {
        openDraftTask(created);
        setMessages((current) => current.map((item) => item.card?.id === card.id ? {
          ...item,
          content: assistantEnvelope(en
            ? "FREE draft confirmation sheet created. I opened the Workbench so you can edit S/C/B/K/R before signing."
            : "FREE 草稿層確認單已建立，已進入工作台。你可以先編輯 S/C/B/K/R，再決定是否簽名入庫。",
          ruleState),
          card: taskCard(created),
        } : item));
      } else {
        setTask((current) => current?.task_id === pendingTask.task_id ? {
          ...pendingTask,
          status: "model_unavailable",
          model_rulebook_authoring: { failure_message: en ? "The model could not be reached or did not return a valid SCBKR rulebook. No fallback draft was created." : "模型未能連上或未回傳合格 SCBKR 規則書；系統沒有產生 fallback 草稿。" },
          next_required_action: "retry_model_rulebook_authoring",
        } as TaskSummary : current);
      }
    } finally {
      setDraftingCardId("");
    }
  }

  function prepareBoundaryFollowup(card: WorkflowCard) {
    const instruction = String(card.suggestion?.suggested_instruction || card.suggestion?.user_original || "").trim();
    setChatInput(en
      ? `For this reusable rule, help me define the role, responsibility boundary, invalidation conditions, and replay requirements:\n${instruction}`
      : `針對這段可重用規則，先幫我補角色、責任邊界、失效條件與回放條件：\n${instruction}`);
  }

  async function sendChat() {
    const text = chatInput.trim();
    if (!text) return;
    setMessages((current) => [...current, { role: "user", content: text }]);
    setChatInput("");
    if (commandMode === "web") {
      const result = await run(en ? "Search web" : "搜尋網路", () => api<any>("/api/tools/web-search", { method: "POST", body: JSON.stringify({ query: text, limit: 6, user_confirmation: true }) }));
      if (result) {
        setWebResult(result);
        const summary = result.results.length ? result.results.map((item: any, index: number) => `${index + 1}. ${item.title}\n${item.url}\n${item.snippet}`).join("\n\n") : (en ? "No web results." : "沒有搜尋結果。");
        setMessages((current) => [...current, { role: "assistant", content: assistantEnvelope(summary, result.response_declaration || ruleState) }]);
      } else {
        setMessages((current) => [...current, { role: "assistant", content: assistantEnvelope(en ? "Web search is not configured or was blocked. Open Launch Center to configure a provider and enable web_search permission." : "網路搜尋尚未設定或被 Gate 阻擋。請到上線中心設定搜尋服務並開啟 web_search 權限。") }]);
      }
      return;
    }
    if (commandMode === "search") {
      const result = await readFourStores(text);
      if (result) setMessages((current) => [...current, {
        role: "assistant",
        content: assistantEnvelope(result.answer, result.rule_state || ruleState),
        rulePackage: result.current_rule_package,
        postCheck: result.post_check,
      }]);
      return;
    }
    if (commandMode === "rule") {
      const created = await createTask(text, true, "create_new_rule_confirmation", "rule");
      if (created) {
        setView("workbench");
        setMessages((current) => [...current, {
          role: "assistant",
          content: assistantEnvelope(en ? "Unsigned SCBKR review sheet is ready in the Workbench." : "未簽名 SCBKR 確認單已建立，已進入工作台。請檢查 S/C/B/K/R 後再簽名。", ruleState),
          card: taskCard(created),
        }]);
      }
      return;
    }
    const routed = await run(en ? "Route request" : "判斷任務", () => api<any>("/api/chat/intent", { method: "POST", body: JSON.stringify({ message: text, locale: replyLocale }) }));
    if (!routed) return;
    if (routed.requires_draft && (routed.intent === "create_new_rule_confirmation" || routed.intent === "create_confirmation")) {
      const isRule = routed.intent === "create_new_rule_confirmation" || routed.draft_object_type === "rule";
      const created = await createTask(text, true, routed.intent, isRule ? "rule" : (routed.draft_object_type || "task"));
      if (created) {
        setMessages((current) => [...current, {
          role: "assistant",
          content: assistantEnvelope(en
            ? "Your explicit rule request entered the SCBKR five-dimension drafting flow. Review S/C/B/K/R in the Workbench before you sign."
            : "你已明確要求建立規則，系統已直接進入 SCBKR 五維草擬流程。請在工作台逐欄檢查 S/C/B/K/R，再決定是否簽名。",
          routed.rule_state || ruleState),
          card: taskCard(created),
        }]);
      }
      return;
    }
    if (routed.intent === "suggest_new_rule_confirmation" || routed.intent === "suggest_create_confirmation") {
      setMessages((current) => [...current, {
        role: "assistant",
        content: assistantEnvelope(en
          ? "This may be worth reusing as a rule, but it remains normal chat until you choose to draft a confirmation sheet."
          : "這段內容可能值得做成可重用規則，但在你選擇草擬確認單前，它仍然只是一般聊天。",
        routed.rule_state || ruleState),
        card: zerothGateCard(routed, text),
      }]);
      return;
    }
    if (routed.intent === "data_center_query") {
      const result = await readFourStores(text);
      if (result) setMessages((current) => [...current, {
        role: "assistant",
        content: assistantEnvelope(result.answer, result.rule_state || ruleState),
        rulePackage: result.current_rule_package,
        postCheck: result.post_check,
      }]);
      return;
    }
    const modelTimeoutMs = Math.max(30000, Math.min((Number(model?.timeout || modelForm.timeout || 120) + 10) * 1000, 180000));
    const reply = await run<ChatResponse>(
      en ? "Chat" : "模型回覆",
      () => withTimeout(
        api<ChatResponse>("/api/chat/general", {
          method: "POST",
          body: JSON.stringify({
            message: text,
            locale: replyLocale,
            chat_history: messages.slice(-12).map((item) => ({ role: item.role, content: item.content })),
          }),
        }),
        modelTimeoutMs,
        "model_response_timeout",
      ),
    );
    if (reply) {
      if (reply.token_cost_audit) setTokenMetrics(reply.token_cost_audit);
      if (reply.current_rule_package) setCurrentRulePackage(reply.current_rule_package);
      if (reply.post_check) setCurrentPostCheck(reply.post_check);
      const suggestion = routed.suggestion || reply.suggestion;
      setMessages((current) => [...current, {
        role: "assistant",
        content: reply.reply,
        card: suggestion ? suggestionCard(suggestion, text) : undefined,
        rulePackage: reply.current_rule_package,
        postCheck: reply.post_check,
        tokenAudit: reply.token_cost_audit,
      }]);
    }
  }

  async function createTask(input = taskInput, navigate = true, intent = "create_confirmation", objectType = "task") {
    if (!input.trim()) { setNotice(en ? "Task input required" : "請輸入任務內容"); return; }
    const trimmed = input.trim();
    const normalized = trimmed.toLowerCase().replace(/[\s，,。！？!?:：；;（）()\[\]【】「」『』]+/g, "");
    const ruleRequest = objectType === "rule" || intent === "create_new_rule_confirmation" || /(生成規則|建立規則|新增規則|制定規則|變成規則|整理成規則|規則書|規則表單|createarule|generatearule|rulebook|ruleform)/i.test(normalized);
    const routedIntent = ruleRequest ? "create_new_rule_confirmation" : intent;
    const routedObjectType = ruleRequest ? "rule" : objectType;
    const pendingTask = {
      task_id: `pending-${Date.now()}`,
      task_name: trimmed.slice(0, 40),
      task_type: "general",
      raw_input: trimmed,
      status: "model_compiling",
      confirmed: false,
      review_passed: false,
      storage_confirmed: false,
      runtime: "SCBKR model authoring in progress",
      rule_assist_plan: planLevel,
    } as TaskSummary;
    if (navigate) {
      setTask(pendingTask);
      setOwnerSignature("");
      setDimensionEdits({});
      setView("workbench");
    }
    let created = await run(
      en ? "Compile draft" : "編譯草案",
      () => withTimeout(
        apiPlainPost<TaskSummary>("/api/tasks/create-fast", {
          raw_input: trimmed,
          task_type: "general",
          intent: routedIntent,
          object_type: routedObjectType,
          create_scbkr_draft: true,
          locale: replyLocale,
          rule_assist_plan: planLevel,
        }),
        ruleRequest ? 1200000 : 30000,
        "task_create_response_timeout",
      ),
    );
    if (!created) created = await recoverLatestTask(trimmed);
    if (created) openDraftTask(created, navigate);
    else if (navigate) {
      setTask((current) => current?.task_id === pendingTask.task_id ? {
        ...pendingTask,
        status: "model_unavailable",
        model_rulebook_authoring: {
          failure_message: en
            ? "The connected model did not complete a valid SCBKR rulebook. No fallback draft was created."
            : "已連線模型未完成合格的 SCBKR 規則書；系統沒有產生替代模板。",
        },
        next_required_action: "retry_model_rulebook_authoring",
      } as TaskSummary : current);
    }
    return created;
  }

  function syncTask(updated: TaskSummary) {
    setTask(updated);
    const updatedMetrics = (updated as any).token_metrics || (updated as any).scbkr?.token_metrics;
    if (updatedMetrics) setTokenMetrics(updatedMetrics);
    setTasks((current) => [updated, ...current.filter((item) => item.task_id !== updated.task_id)]);
    setPendingPatch(null);
    setDimensionEdits({});
  }

  async function confirmTask() {
    if (!task || !ownerSignature.trim()) return;
    const confirmed = await run(en ? "Sign responsibility chain" : "簽名責任鏈", () => api<TaskSummary>(`/api/tasks/${task.task_id}/confirm`, { method: "POST", body: JSON.stringify({ scbkr: task.scbkr, confirmed_by: "user", signature: ownerSignature.trim() }) }));
    if (confirmed) syncTask(confirmed);
  }

  async function generate() {
    if (!task) return;
    const generated = await run(en ? "Generate" : "模型生成", () => api<TaskSummary>(`/api/tasks/${task.task_id}/generate`, { method: "POST", body: "{}" }));
    if (generated) syncTask(generated);
  }

  async function review(decision: "pass" | "fail") {
    if (!task || !ownerSignature.trim()) return;
    const reviewed = await run(en ? "Review output" : "驗收輸出", () => api<TaskSummary>(`/api/tasks/${task.task_id}/review`, { method: "POST", body: JSON.stringify({ review_decision: decision, review_message: decision === "pass" ? "Owner accepted" : "Owner rejected", reviewer_signature: ownerSignature.trim() }) }));
    if (reviewed) syncTask(reviewed);
  }

  async function commitStores() {
    if (!task || !ownerSignature.trim()) return;
    let current = task;
    if (!current.storage_plan) {
      const requested = await run(en ? "Create storage plan" : "建立入庫計畫", () => api<TaskSummary>(`/api/tasks/${current.task_id}/storage-request`, { method: "POST", body: JSON.stringify({ selected_targets: selectedStores, user_decision: "custom", signature: ownerSignature.trim() }) }));
      if (!requested) return;
      current = requested;
    }
    const committed = await run(en ? "Commit four stores" : "二次確認入庫", () => api<TaskSummary>(`/api/tasks/${current.task_id}/storage-confirm`, { method: "POST", body: JSON.stringify({ storage_confirmed: true, second_confirm: true, confirmed_by: "user", signature: ownerSignature.trim(), selected_targets: selectedStores }) }));
    if (committed) {
      syncTask(committed);
      void refreshAll();
      return;
    }
    try {
      const refreshed = await api<TaskSummary>(`/api/tasks/${encodeURIComponent(current.task_id)}`);
      if (refreshed.status === "storage_conflict") syncTask(refreshed);
    } catch {
      // The actionable conflict message is already shown by run().
    }
  }

  async function refreshConflictedRevision() {
    if (!task?.supersedes_rule_id) return;
    const refreshed = await run(
      en ? "Reload latest rule" : "重新載入最新版規則",
      () => api<TaskSummary>(`/api/rules/${encodeURIComponent(task.supersedes_rule_id || "")}/revision`, {
        method: "POST",
        body: JSON.stringify({
          instruction: task.revision_instruction || (en ? "Reapply the requested revision to the latest rule." : "把原本的修改需求重新套用到最新版規則。"),
          locale: replyLocale,
        }),
      }),
    );
    if (refreshed) {
      setOwnerSignature("");
      syncTask(refreshed);
    }
  }

  async function createNaturalRule(instruction = naturalRuleText) {
    const text = instruction.trim();
    if (!text) return null;
    const created = await createTask(text, true, "create_new_rule_confirmation", "rule");
    if (created) {
      setNaturalRuleText("");
    }
    return created;
  }

  async function createRuleRevision() {
    if (!selectedRule || !revisionInstruction.trim()) return;
    const created = await run(
      en ? "Create new rule version" : "建立新版規則",
      () => withTimeout(
        api<TaskSummary>(`/api/rules/${encodeURIComponent(selectedRule)}/revision`, {
          method: "POST",
          body: JSON.stringify({ instruction: revisionInstruction.trim(), locale: replyLocale }),
        }),
        1200000,
        "rule_revision_timeout",
      ),
    );
    if (created) {
      setRevisionInstruction("");
      openDraftTask(created);
    }
  }

  async function changeSelectedRuleLifecycle(action: "disable" | "archive" | "delete") {
    if (!selectedRule || !ruleSignature.trim() || !lifecycleConfirmed) return;
    const result = await run(
      en ? `${action} rule` : `${action === "disable" ? "停用" : action === "archive" ? "封存" : "刪除"}規則`,
      () => api<any>(`/api/rules/${encodeURIComponent(selectedRule)}/lifecycle`, {
        method: "POST",
        body: JSON.stringify({
          action,
          confirmed_by: "user",
          second_confirm: true,
          signature: ruleSignature.trim(),
          reason: lifecycleReason.trim() || undefined,
        }),
      }),
    );
    if (result) {
      setLifecycleConfirmed(false);
      setLifecycleReason("");
      setRuleSignature("");
      await refreshAll();
    }
  }

  async function readFourStores(query = dataQuery) {
    const text = query.trim();
    if (!text) return null;
    const result = await run(en ? "Search and read four stores" : "搜尋並閱讀四庫", () => api<any>("/api/data-center/ask", { method: "POST", body: JSON.stringify({ query: text }) }));
    if (result) {
      const citationsLocalized = (result.citations || []).map((citation: Record<string, any>) => {
        const meta = storeDisplayMetadata(citation.source_store, "active", en);
        return { ...citation, source_store: meta.label, store_role: meta.role, store_purpose: meta.purpose, citation_policy: meta.citation };
      });
      setReadResult({ ...result, citations: citationsLocalized });
      if (result.current_rule_package) setCurrentRulePackage(result.current_rule_package);
      if (result.post_check) setCurrentPostCheck(result.post_check);
      setDataQuery(text);
    }
    return result;
  }

  async function openDataSection(section = dataSection) {
    const result = await run(en ? "Open data store" : "打開四庫資料", () => api<any>(`/api/data-center/${encodeURIComponent(section)}?locale=${locale}`));
    if (result) {
      const itemsLocalized = (result.items || []).map((item: Record<string, any>) => {
        const meta = storeDisplayMetadata(item.target, item.status, en);
        return {
          ...item,
          store_label: meta.label,
          store_role: meta.role,
          store_purpose: meta.purpose,
          citation_policy: meta.citation,
          status_label: meta.status,
          storage_location: en ? "Local record" : "本機紀錄",
          relative_path: en ? "Local record" : "本機紀錄",
        };
      });
      setDataSection(section);
      setDataSectionResult({ ...result, items: itemsLocalized, empty_message: en ? "No records in this store." : "這個庫目前沒有資料。" });
      setExpandedDataItem("");
    }
    return result;
  }

  async function regenerateCurrentScbkr() {
    if (!task) return null;
    const updated = await run(en ? "Ask model to fill SCBKR" : "模型補寫 SCBKR 表單", () => api<TaskSummary>(`/api/tasks/${task.task_id}/scbkr/regenerate-draft`, { method: "POST", body: JSON.stringify({ raw_input: (task as any).raw_input || taskInput || "" }) }));
    if (updated) syncTask(updated);
    return updated;
  }

  async function applyCurrentRuleAssist() {
    if (!task) return null;
    const updated = await run(en ? "Apply structure assist" : "套用結構補強", () => api<TaskSummary>(`/api/tasks/${task.task_id}/scbkr/apply-rule-assist`, { method: "POST", body: JSON.stringify({ raw_input: (task as any).raw_input || taskInput || "" }) }));
    if (updated) syncTask(updated);
    return updated;
  }

  async function draftLayerPatch() {
    if (!task || !patchInstruction.trim()) return null;
    const drafted = await run(en ? "Draft SCBKR patch" : "模型提出欄位修改草案", () => api<any>(`/api/tasks/${task.task_id}/scbkr/patch-draft`, { method: "POST", body: JSON.stringify({ layer: patchLayer, instruction: patchInstruction.trim() }) }));
    if (drafted?.patch) setPendingPatch(drafted.patch);
    return drafted;
  }

  async function applyLayerPatch() {
    if (!task || !pendingPatch) return null;
    const updated = await run(en ? "Apply SCBKR patch" : "套用欄位修改", () => api<TaskSummary>(`/api/tasks/${task.task_id}/scbkr/apply-patch`, { method: "POST", body: JSON.stringify({ patch: pendingPatch }) }));
    if (updated) {
      setPatchInstruction("");
      syncTask(updated);
    }
    return updated;
  }

  async function saveDimensionEdit(layer: ScbkrDimensionKey) {
    if (!task?.scbkr) return null;
    const content = String(dimensionEdits[layer] ?? "").trim();
    if (!content) return null;
    const updated = await run(en ? "Save field edit" : "儲存欄位編輯", () => api<TaskSummary>(`/api/tasks/${task.task_id}/scbkr/owner-edit`, {
      method: "POST",
      body: JSON.stringify({ layer, content }),
    }));
    if (updated) syncTask(updated);
    return updated;
  }

  function quickPatch(layer: ScbkrDimensionKey, instructionZh: string, instructionEn: string) {
    setPatchLayer(layer);
    setPatchInstruction(en ? instructionEn : instructionZh);
  }

  async function saveLaunchSettings() {
    const saved = await run(en ? "Save launch settings" : "儲存上線設定", () => api<any>("/api/launch/settings", { method: "POST", body: JSON.stringify(launchSettings) }));
    if (saved) { setLaunchSettings(saved); await refreshAll(); }
  }

  async function setWebPermission(enabled: boolean) {
    const saved = await run(en ? "Update web permission" : "更新網路權限", () => api<any>("/api/settings/permissions", { method: "POST", body: JSON.stringify({ web_search: enabled }) }));
    if (saved) setPermissions(saved);
  }

  async function setModelGeneratePermission(enabled: boolean) {
    const saved = await run(en ? "Update model permission" : "更新模型生成權限", () => api<any>("/api/settings/permissions", { method: "POST", body: JSON.stringify({ model_generate: enabled }) }));
    if (saved) setPermissions(saved);
  }

  async function updateRuleAssistSettings(payload: Record<string, any>) {
    const updated = await run(en ? "Update rule assist" : "更新規則輔助", () => api<RuleAssistStatus>("/api/rule-assist/settings", { method: "POST", body: JSON.stringify({ locale: ruleAssist.locale || locale, ...payload }) }));
    if (updated) setRuleAssist(updated);
  }

  async function runRuleAssistCheck() {
    const text = chatInput.trim() || (en ? "Hello, explain what this system can do." : "你好，說明這套系統可以怎麼建立規則。");
    const result = await run(en ? "Run rule-assist check" : "測試規則層回覆", () => api<any>("/api/rule-assist/check-chat", { method: "POST", body: JSON.stringify({ message: text, locale: replyLocale }) }));
    if (result) setMessages((current) => [...current, { role: "user", content: text }, { role: "assistant", content: result.reply }]);
  }

  async function signRule() {
    if (!selectedRule || !ruleSignature.trim()) return;
    const signed = await run(en ? "Sign rule" : "簽名規則", () => api<any>(`/api/rules/${encodeURIComponent(selectedRule)}/sign`, { method: "POST", body: JSON.stringify({ owner_signature: ruleSignature }) }));
    if (signed) await refreshAll();
  }

  async function activateRule() {
    if (!selectedRule || !ruleSignature.trim()) return;
    const activated = await run(en ? "Activate rule" : "啟用規則", () => api<any>(`/api/rules/${encodeURIComponent(selectedRule)}/activate`, { method: "POST", body: JSON.stringify({ adopted_by: "user", adoption_signature: ruleSignature, adoption_scope: { workflow: "local" } }) }));
    if (activated) await refreshAll();
  }

  async function evaluateTool() {
    const result = await run(en ? "Evaluate tool gates" : "檢查工具閘門", () => api<any>("/api/tools/evaluate", { method: "POST", body: JSON.stringify({ tool_id: selectedTool, action: toolAction, task_type: task?.task_type || "general", workflow: "local", text: task?.raw_input || chatInput, task_id: task?.task_id, user_confirmation: toolConfirmed }) }));
    if (result) { setToolResult(result); const latest = await api<any>("/api/tools/traces?limit=20"); setTraces(latest.traces || []); }
  }

  async function saveModel() {
    const payload: any = { ...modelForm };
    if (!payload.api_key) delete payload.api_key;
    const saved = await run(en ? "Save model" : "儲存模型", () => api<ModelSettings>("/api/settings/model", { method: "POST", body: JSON.stringify(payload) }));
    if (saved) setModel(saved);
  }

  async function testModel() {
    const tested = await run(en ? "Test model" : "測試模型", () => api<ModelSettings>("/api/model/test", { method: "POST", body: JSON.stringify(modelForm) }));
    if (tested) setModel(tested);
  }

  async function clearModelApiKey() {
    const cleared = await run(en ? "Clear API key" : "清除 API Key", () => api<ModelSettings>("/api/settings/model", { method: "POST", body: JSON.stringify({ provider: modelForm.provider, api_key: "", clear_api_key: true }) }));
    if (cleared) { setModel(cleared); setModelForm((current) => ({ ...current, api_key: "" })); }
  }

  async function savePricing() {
    const payload = {
      ...pricing,
      model_name: modelForm.model_name || model?.model_name || "",
      source: pricing.source || "user_configured",
    };
    const saved = await run(en ? "Save pricing snapshot" : "儲存價格快照", () => api<Record<string, any>>("/api/metrics/pricing", { method: "POST", body: JSON.stringify(payload) }));
    if (saved) setPricing(saved);
  }

  function updateModelProvider(provider: string) {
    const mode = provider === "sandbox_mock_model" ? "sandbox" : provider === "openai_compatible" ? "external" : "local";
    const base_url = provider === "lm_studio"
      ? "http://127.0.0.1:1234/v1"
      : provider === "ollama"
        ? "http://127.0.0.1:11434/v1"
        : provider === "sandbox_mock_model"
          ? ""
          : modelForm.base_url;
    setModelForm({ ...modelForm, provider, mode, base_url, api_key: provider === "sandbox_mock_model" ? "" : modelForm.api_key, model_name: provider === "sandbox_mock_model" ? "sandbox_mock_model" : modelForm.model_name });
  }

  async function startPairing() {
    const result = await run(en ? "Create pairing code" : "產生手機配對碼", () => api<any>("/api/companion/pairing/start", { method: "POST", body: "{}" }));
    if (result) setPairing(result);
  }

  async function revokeCompanions() {
    const result = await run(en ? "Revoke devices" : "撤銷手機連線", () => api<any>("/api/companion/pairing/revoke-all", { method: "POST", body: "{}" }));
    if (result) { setPairing(null); await refreshAll(); }
  }

  async function redeemPairingCode() {
    const code = pairCode.replace(/\D/g, "").slice(0, 6);
    if (code.length !== 6) { setPairError(en ? "Enter the six-digit code." : "請輸入桌機顯示的 6 位數配對碼。"); return; }
    setPairError("");
    try {
      const response = await fetch(`${backend}/api/companion/pairing/redeem`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pairing_code: code, device_name: navigator.userAgent.slice(0, 80) }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Pairing failed");
      localStorage.setItem(TOKEN_KEY, body.companion_token);
      localStorage.setItem(BACKEND_KEY, backend);
      setTokenInput(body.companion_token);
      setPairingRequired(false);
      setHealth("checking");
    } catch (error) {
      setPairError(String(error).replace("Error: ", ""));
    }
  }

  function switchLocale() { setLocale((current) => current === "en" ? "zh-TW" : "en"); }
  function saveConnection() { localStorage.setItem(BACKEND_KEY, backend.replace(/\/+$/, "")); localStorage.setItem(TOKEN_KEY, tokenInput.trim()); setBackend(backend.replace(/\/+$/, "")); void refreshAll(); }

  function finishTour() {
    localStorage.setItem(ONBOARDING_KEY, "done");
    setTourOpen(false);
    setTourStep(0);
  }

  function renderWorkflowCard(card: WorkflowCard) {
    if (card.state === "DISMISSED") return null;
    const label = card.kind === "advisory" ? (en ? "ZEROTH GATE" : "第0原理建議閘") : card.kind === "rule" ? (en ? "RULE DRAFT" : "規則草案") : card.kind === "task" ? (en ? "SCBKR DRAFT" : "責任鏈草案") : (en ? "DRAFT SUGGESTION" : "草案建議");
    return <section className={`workflow-card ${card.kind}`} aria-label={en ? "Workflow draft" : "待辦草案"}><header><span>{label}</span><b>{workflowStateLabel(card, draftingCardId === card.id, en)}</b></header><h3>{card.title}</h3><p>{card.summary}</p>{Boolean(card.details?.length) && <ul className="workflow-details">{card.details?.map((item) => <li key={item}>{item}</li>)}</ul>}{Boolean(card.suggestedStores?.length) && <div className="store-chips">{card.suggestedStores?.map((store) => <span key={store}>{storeDisplayMetadata(store, "active", en).label}</span>)}</div>}<div className="workflow-actions">{card.kind === "advisory" && <><button type="button" data-testid="draft-confirmation-sheet" disabled={draftingCardId === card.id} onClick={() => void draftFromAdvisoryGate(card)}><Sparkles size={14} />{draftingCardId === card.id ? (en ? "Drafting..." : "建立中...") : (en ? "Draft confirmation" : "草擬確認單")}</button><button type="button" className="secondary" onClick={(event) => { event.preventDefault(); prepareBoundaryFollowup(card); }}><ShieldCheck size={14} />{en ? "Add role and boundary" : "補角色與邊界"}</button></>}{card.kind === "suggestion" && <button type="button" onClick={() => void acceptSuggestion(card)}><Sparkles size={14} />{en ? "Create draft" : "建立草案"}</button>}{card.kind === "task" && card.taskId && <button type="button" onClick={() => void openTask(card.taskId!)}><SlidersHorizontal size={14} />{en ? "Open Workbench" : "前往工作台"}</button>}{card.kind === "rule" && card.ruleId && <button type="button" onClick={() => { setSelectedRule(card.ruleId!); setView("rules"); }}><FileKey size={14} />{en ? "Open Rule Center" : "前往規則中心"}</button>}<button type="button" className="quiet" onClick={() => dismissCard(card.id)}><X size={14} />{card.kind === "advisory" ? (en ? "Keep chatting" : "保持一般聊天") : (en ? "Dismiss" : "留在本次對話")}</button></div><small>{en ? "Not signed or stored. The model may draft; only the user can sign." : "尚未簽名、尚未入庫。模型可以草擬，只有使用者能簽名。"}</small></section>;
  }

  function renderResponseReceipt(message: ChatMessage) {
    const rulePackage = message.rulePackage;
    if (!rulePackage) return null;
    const matchedRules = rulePackage.matched_rules || [];
    const citableData = rulePackage.citable_data || [];
    const preferences = rulePackage.user_preferences || [];
    const candidates = rulePackage.retrieval_candidates || [];
    const hasAuthority = matchedRules.length > 0 || citableData.length > 0 || preferences.length > 0;
    const postAllowed = message.postCheck?.allowed !== false;
    const ruleNames = matchedRules.map((rule) => String(rule.rule_name || rule.title || rule.name || (en ? "Signed local rule" : "已簽名本地規則")));
    return <details className={`response-receipt ${hasAuthority ? "authoritative" : "general"}`} data-testid="current-rule-package-receipt">
      <summary><ShieldCheck size={15} /><span><b>{copy.responseReceipt.title}</b><small>{hasAuthority ? copy.responseReceipt.signedRuleApplied : copy.responseReceipt.generalChat}</small></span><em>{postAllowed ? copy.responseReceipt.passed : copy.responseReceipt.blocked}</em><ChevronRight size={15} /></summary>
      <div className="receipt-source-grid">
        <div><Braces size={15} /><span>{copy.responseReceipt.ruleStore}</span><b>{matchedRules.length}</b></div>
        <div><Archive size={15} /><span>{copy.responseReceipt.dataStore}</span><b>{citableData.length}</b></div>
        <div><HardDrive size={15} /><span>{copy.responseReceipt.memoryStore}</span><b>{preferences.length}</b></div>
        <div className="recall-only"><Network size={15} /><span>{copy.responseReceipt.retrievalStore}</span><b>{candidates.length}</b></div>
      </div>
      {ruleNames.length > 0 ? <div className="receipt-rule-list"><b>{copy.responseReceipt.signedRuleApplied}</b>{ruleNames.map((name, index) => <span key={`${name}-${index}`}>{name}</span>)}</div> : <p>{copy.responseReceipt.noAuthority}</p>}
      <dl><div><dt>{copy.responseReceipt.chatContext}</dt><dd>{rulePackage.chat_context_used ? copy.responseReceipt.included : copy.responseReceipt.excluded}</dd></div><div><dt>{copy.responseReceipt.postCheck}</dt><dd>{postAllowed ? copy.responseReceipt.passed : copy.responseReceipt.blocked}</dd></div></dl>
      <small>{copy.responseReceipt.retrievalOnly}</small>
    </details>;
  }

  const nav = [
    { id: "command" as View, label: copy.navigation.chat, icon: MessageSquare },
    { id: "workbench" as View, label: copy.navigation.workbench, icon: SlidersHorizontal },
    { id: "rules" as View, label: copy.navigation.rules, icon: FileKey },
    { id: "data" as View, label: copy.navigation.dataCenter, icon: Database },
    { id: "tools" as View, label: en ? "Tools & Search" : "工具與搜尋", icon: Wrench },
    { id: "model" as View, label: copy.navigation.modelSettings, icon: Settings },
    { id: "runtime" as View, label: en ? "Rule State" : "規則狀態", icon: ShieldCheck },
    { id: "launch" as View, label: en ? "Launch" : "上線中心", icon: Rocket },
    { id: "about" as View, label: copy.navigation.about, icon: Info },
  ];
  const mobileNav = [nav[0], nav[1], nav[2], nav[3], { id: "more" as View, label: en ? "More" : "更多", icon: Menu }];

  const stores = [
    { id: "logic", label: "LOGIC", hint: en ? "Formal rules" : "正式規則", count: overview.logic_count || 0, icon: Braces },
    { id: "corpus", label: "CORPUS", hint: en ? "Formal data" : "正式資料", count: overview.corpus_count || 0, icon: Archive },
    { id: "memory", label: "MEMORY", hint: en ? "Long-term preferences" : "長期偏好", count: overview.memory_count || 0, icon: HardDrive },
    { id: "vector", label: "VECTOR", hint: en ? "Recall only" : "只做召回", count: overview.vector_count || 0, icon: Network },
  ];
  const PlanIcon = FileKey;
  const aiToolCards = [
    { id: "web_search", icon: Globe2, title: en ? "Web search" : "網頁搜尋", status: permissions.web_search === true ? "enabled" : "confirm", detail: en ? "Confirmed live search" : "依規則執行網頁搜尋與擷取" },
    { id: "email_draft", icon: Mail, title: en ? "Email draft" : "Email 草稿", status: "confirm", detail: en ? "Draft only before signature" : "只先生成草稿，不自動寄出" },
    { id: "code_workspace", icon: SquareTerminal, title: en ? "Code workbench" : "程式碼工作台", status: "confirm", detail: en ? "Patch and verify locally" : "依規則產生與驗證程式碼" },
    { id: "local_files", icon: FolderOpen, title: en ? "Local files" : "本機檔案", status: "confirm", detail: en ? "Read/write requires boundary" : "讀寫必須有邊界與簽名" },
    { id: "voice_io", icon: Bot, title: en ? "Voice I/O" : "語音輸入/輸出", status: "standby", detail: en ? "Reserved for VoxCPM" : "保留給 VoxCPM / 語音流程" },
    { id: "desktop", icon: Monitor, title: en ? "Desktop control" : "電腦控制", status: "confirm", detail: en ? "Agent can operate after gate" : "代理可操作，主責不離使用者" },
  ];
  const corePrinciples = [
    en ? "Model assists; user signs." : "模型只協助，使用者簽名。",
    en ? "Four-store citations outrank chat context." : "四庫正式引用高於聊天上下文。",
    en ? "No signature, no storage." : "沒有簽名，不得入庫。",
    en ? "No review, no final close." : "沒有驗收，不得 CLOSE。",
  ];
  const tourSteps: Array<{ title: string; body: string; view: View; dimensions?: boolean }> = en
    ? [
      { title: "Meet SCBKR", body: "The FREE framework experience created by Wen-Yao Hsu / ShenYao888pi combines normal AI chat with user-authored local rules. Private official rule packs are not bundled.", view: "command" },
      { title: "Connect a model", body: "Open Model Settings, connect LM Studio, Ollama, or an OpenAI-compatible endpoint, test it, then enable generation.", view: "model" },
      { title: "Understand the five dimensions", body: "The connected model must apply all five roles to your actual request. You can read and edit every field before signing.", view: "workbench", dimensions: true },
      { title: "You remain the signer", body: "The model drafts and explains. Only you can sign, review, second-confirm storage, activate, revise, archive, or delete a rule.", view: "rules" },
      { title: "Signed rules drive later answers", body: "SCBKR builds a minimal rule package from active signed four-store records, checks the answer, and shows per-request usage. Only same-model two-call provider usage is marked VERIFIED.", view: "runtime" },
    ]
    : [
      { title: "認識 SCBKR", body: "這是許文耀／沈耀888π 建立的 FREE 框架體驗版：一般 AI 聊天加上使用者自訂本地規則；沈耀私人正式規則包不隨公開版提供。", view: "command" },
      { title: "先連接模型", body: "到模型設定連接 LM Studio、Ollama 或 OpenAI-compatible API，測試成功後再開啟生成權限。", view: "model" },
      { title: "看懂五維責任鏈", body: "連接的模型必須把五個角色套用到你的實際需求。簽名前，每一欄都能看、能問、能改。", view: "workbench", dimensions: true },
      { title: "簽名權只在你手上", body: "模型負責草擬與解釋；只有你能簽名、驗收、二次確認入庫、啟用、建立新版、封存或刪除規則。", view: "rules" },
      { title: "簽名規則控制後續回答", body: "SCBKR 會從生效四庫建立本次最小規則包、檢查回答並顯示本次用量；只有同模型雙呼叫且取得 provider usage 才標成 VERIFIED。", view: "runtime" },
    ];
  const currentTour = tourSteps[Math.min(tourStep, tourSteps.length - 1)];
  const tourPanel = tourOpen ? (
    <aside className="product-tour" aria-label={en ? "SCBKR guided tour" : "SCBKR 新手導覽"}>
      <header><span>{en ? "QUICK START" : "快速導覽"} · {tourStep + 1}/{tourSteps.length}</span><button className="icon-button" onClick={finishTour} title={en ? "Close tour" : "關閉導覽"}><X size={16} /></button></header>
      <div className="tour-progress">{tourSteps.map((_, index) => <i className={index <= tourStep ? "active" : ""} key={index} />)}</div>
      <h2>{currentTour.title}</h2>
      <p>{currentTour.body}</p>
      {currentTour.dimensions && <div className="tour-dimensions">{dims.map((dim) => <div key={dim}><b>{dim}</b><span><strong>{copy.dimensions[dim]}</strong><small>{dimensionNames[dim][en ? "en" : "zh"]}</small></span></div>)}</div>}
      <footer><button className="quiet" onClick={finishTour}>{en ? "Skip" : "略過"}</button>{tourStep > 0 && <button onClick={() => { const next = tourStep - 1; setTourStep(next); setView(tourSteps[next].view); }}>{en ? "Back" : "上一步"}</button>}<button className="primary-action" onClick={() => { if (tourStep >= tourSteps.length - 1) { finishTour(); return; } const next = tourStep + 1; setTourStep(next); setView(tourSteps[next].view); }}>{tourStep >= tourSteps.length - 1 ? (en ? "Start using SCBKR" : "開始使用") : (en ? "Next" : "下一步")}</button></footer>
    </aside>
  ) : null;

  const planConsole = (
    <section className="ops-panel plan-console">
      <header><PlanIcon size={20} /><div><span>RULE ASSIST</span><h2>{activePlan.display_name || (en ? "Free Draft Layer" : "免費草稿層")}</h2></div><b>{planLevel}</b></header>
      <p>{activePlan.display_summary || (en ? "Local draft mode" : "本機草案模式")}</p>
      <div className="plan-contract">
        <div><b>{en ? "Model can fill" : "模型可補"}</b><span>{activePlan.model_scbr_fill || (en ? "Draft only" : "僅草案")}</span></div>
        <details>
          <summary>{en ? "Valid / invalid conditions" : "成立／失效條件"}</summary>
          <div className="condition-grid">
            <section><b>{en ? "Valid when" : "成立條件"}</b>{listText(activePlan.formation_conditions).map((item) => <span key={item}>{item}</span>)}</section>
            <section><b>{en ? "Invalid when" : "失效條件"}</b>{listText(activePlan.failure_conditions).map((item) => <span key={item}>{item}</span>)}</section>
          </div>
        </details>
      </div>
      <div className="plan-details public-edition"><FileKey size={15} /><span>{en ? "Public FREE edition" : "公開免費版"}</span><b>FREE</b></div>
      <label>{en ? "Answer language" : "模型輸出語言"}<select value={["auto", "zh-TW", "en"].includes(ruleAssist.locale || "auto") ? (ruleAssist.locale || "auto") : "auto"} onChange={(event) => void updateRuleAssistSettings({ locale: event.target.value })}><option value="auto">Auto</option><option value="zh-TW">繁體中文</option><option value="en">English</option></select></label>
      <button className="primary-action" onClick={() => void runRuleAssistCheck()}><Play size={15} />{en ? "Test rule layer" : "測試規則層回覆"}</button>
    </section>
  );

  const activeRuleApplied = Boolean((currentRulePackage?.matched_rules || []).length);
  const activeRuleAvailable = Boolean(ruleState.active_rule_id || ruleState.active_rulepack_id);
  const activeRulePanel = (
    <section className="ops-panel active-rule-panel">
      <header><ShieldCheck size={20} /><div><span>{en ? "RULE AUTHORITY" : "規則依據"}</span><h2>{activeRuleApplied ? (en ? "Rule applied to this answer" : "本次已套用規則") : activeRuleAvailable ? (en ? "Signed rule ready" : "已簽名規則可用") : (en ? "No citable rule" : "尚無可引用規則")}</h2></div></header>
      <dl><div><dt>{en ? "Source" : "規則來源"}</dt><dd>{ruleState.active_rulepack_id ? (en ? "ShenYao rule runtime" : "沈耀規則 Runtime") : ruleState.active_rule_id ? (en ? "User local rule" : "使用者本機規則") : (en ? "No active rule" : "尚無生效規則")}</dd></div><div><dt>{en ? "Version" : "版本"}</dt><dd>{activeRuleAvailable ? (ruleState.active_rulepack_version || ruleState.active_rule_version || "--") : "--"}</dd></div><div><dt>{en ? "Signature" : "簽名狀態"}</dt><dd>{activeRuleAvailable ? responsibilityHolderLabel(ruleState.responsibility_holder, en) : (en ? "No active signature" : "尚無生效簽名")}</dd></div></dl>
      <button onClick={() => setView("runtime")}><ChevronRight size={15} />{en ? "Open rule state" : "查看規則狀態"}</button>
    </section>
  );

  const toolLauncher = (
    <div className={`tool-launcher ${toolLauncherOpen ? "open" : ""}`}>
      <button className="tool-plus" onClick={() => setToolLauncherOpen((value) => !value)} title={en ? "Open tool launcher" : "開啟工具列"}><Plus size={22} /></button>
      {toolLauncherOpen && <section className="tool-launcher-menu"><header><Sparkles size={17} /><div><span>CONNECTORS</span><h2>{en ? "Model-accessible tools" : "模型可碰的工具"}</h2></div></header><div>{aiToolCards.map(({ id, icon: Icon, title, status, detail }) => <button key={id} onClick={() => { setSelectedTool(id); setView("tools"); setToolLauncherOpen(false); }}><Icon size={18} /><span><b>{title}</b><small>{detail}</small></span><em className={status}>{toolStatusLabel(status, en)}</em></button>)}</div></section>}
    </div>
  );

  const aiToolPanel = (
    <section className="ops-panel ai-tool-panel">
      <header><BrainCircuit size={20} /><div><span>AI ENGINE TOOLS</span><h2>{en ? "Tool permissions" : "AI 引擎與工具"}</h2></div><em>{en ? "running" : "運行中"}</em></header>
      <div className="tool-card-list">{aiToolCards.slice(0, 5).map(({ id, icon: Icon, title, status, detail }) => <button key={id} onClick={() => { setSelectedTool(id); setView("tools"); }}><Icon size={18} /><span><b>{title}</b><small>{detail}</small></span><i className={status}>{status === "enabled" ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}</i></button>)}</div>
      <button onClick={() => setView("tools")}><Settings size={15} />{en ? "Manage tool gates" : "管理工具權限"}</button>
    </section>
  );

  const auditPanel = (
    <section className="ops-panel audit-panel">
      <header><FileKey size={20} /><div><span>AUDIT STATE</span><h2>{en ? "Responsibility closure" : "審計狀態"}</h2></div></header>
      <div className="audit-steps"><span className="done"><CheckCircle2 size={15} />{en ? "Rules read" : "已讀取規則版本"}</span><span className={permissions.model_generate === true || model?.enabled ? "done" : "wait"}>{permissions.model_generate === true || model?.enabled ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}{en ? "Model permission" : "模型權限"}</span><span className={ownerSignature ? "done" : "wait"}>{ownerSignature ? <CheckCircle2 size={15} /> : <Lock size={15} />}{en ? "Owner signature" : "使用者簽名"}</span><span className={task?.storage_confirmed ? "done" : "wait"}>{task?.storage_confirmed ? <CheckCircle2 size={15} /> : <Database size={15} />}{en ? "Storage confirmed" : "等待驗收 / 入庫"}</span></div>
    </section>
  );

  const metricNumber = (value: any): number | null => {
    if (value === null || value === undefined || value === "") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  };
  const currentModelName = String((task as any)?.model_name || task?.scbkr?.model_name || model?.model_name || "").trim();
  const modelReady = Boolean(runtimeSynced && model?.enabled && model.last_test_status === "success" && permissions.model_generate === true);
  const baselineTokens = metricNumber(tokenMetrics.baseline_prompt_tokens ?? tokenMetrics.full_context_tokens_est);
  const actualPromptTokens = metricNumber(tokenMetrics.actual_prompt_tokens ?? tokenMetrics.compiled_prompt_tokens);
  const actualCompletionTokens = metricNumber(tokenMetrics.actual_completion_tokens);
  const savedTokens = metricNumber(tokenMetrics.tokens_saved ?? tokenMetrics.estimated_tokens_avoided);
  const reductionPercent = metricNumber(tokenMetrics.reduction_percent ?? tokenMetrics.compression_percent);
  const compressionEligible = tokenMetrics.measurement_scope === "rule_answer"
    && Number(tokenMetrics.formal_source_summary?.matched_rules || 0) > 0;
  const hasTokenComparison = compressionEligible
    && baselineTokens !== null && baselineTokens > 0
    && actualPromptTokens !== null && savedTokens !== null;
  const benchmarkVerified = tokenBenchmark.savings_verified === true
    && tokenBenchmark.comparison_basis === "same_provider_same_model_two_real_calls";
  const verifiedTokenComparison = benchmarkVerified || (hasTokenComparison
    && tokenMetrics.savings_verified === true
    && ["ab_provider_usage", "same_provider_same_model_two_real_calls"].includes(String(tokenMetrics.comparison_basis || "")));
  const hasActualUsage = tokenMetrics.provider_usage_available === true && actualPromptTokens !== null;
  const tokenCount = (value: any) => metricNumber(value)?.toLocaleString(en ? "en-US" : "zh-TW") ?? "--";
  const comparisonLabel = verifiedTokenComparison
    ? (en ? "A/B verified savings" : "A/B 實測節省")
    : hasTokenComparison
      ? (en ? "Estimated context avoided" : "估算少送上下文")
      : (en ? "Awaiting measurement" : "等待正式量測");
  const tokenBasis = verifiedTokenComparison
    ? (en ? "Two real provider calls" : "兩條路徑皆真實呼叫")
    : tokenMetrics.measurement_basis === "provider_usage" && hasActualUsage
      ? (en ? "Actual request exact · baseline estimated" : "本次用量精準 · 基準為估算")
      : tokenMetrics.measurement_basis === "tokenizer" && hasTokenComparison
        ? (en ? "Local tokenizer comparison" : "本機 tokenizer 比較")
        : tokenMetrics.measurement_basis === "heuristic_estimate" && hasTokenComparison
          ? (en ? "Heuristic estimate" : "字元估算")
          : (en ? "Run a model response first" : "先完成一次模型回覆");
  const tokenCost = !hasActualUsage
    ? "--"
    : tokenMetrics.price_status === "local_no_api_charge"
      ? `${tokenMetrics.currency || "USD"} 0`
      : tokenMetrics.api_cost === null || tokenMetrics.api_cost === undefined
        ? (en ? "Price not set" : "尚未設定價格")
        : `${tokenMetrics.currency || "USD"} ${tokenMetrics.api_cost}`;
  const savedCost = hasTokenComparison && tokenMetrics.estimated_cost_saved != null
    ? `${tokenMetrics.currency || "USD"} ${tokenMetrics.estimated_cost_saved}`
    : "--";
  const displayRulePackage = currentRulePackage || task?.current_rule_package || null;
  const packageRules = displayRulePackage?.matched_rules || [];
  const packageData = displayRulePackage?.citable_data || [];
  const packagePreferences = displayRulePackage?.user_preferences || [];
  const packageCandidates = displayRulePackage?.retrieval_candidates || [];
  const tokenStatusLabel = benchmarkVerified
    ? (en ? "VERIFIED" : "已實測")
    : hasTokenComparison
      ? (en ? "ESTIMATE" : "估算")
      : (en ? "PENDING" : "待量測");

  async function runVerifiedTokenBenchmark() {
    const question = [...messages].reverse().find((item) => item.role === "user")?.content?.trim() || "";
    const packageForBenchmark = currentRulePackage || task?.current_rule_package || null;
    if (!modelReady) {
      setNotice(en ? "Connect and test a real model before running A/B." : "請先連接並測試真實模型，再執行 A/B。" );
      return;
    }
    if (!question || !(packageForBenchmark?.matched_rules || []).length) {
      setNotice(en ? "Ask a question that matches a signed rule first." : "請先完成規則簽名入庫，再問一個會命中規則的問題。" );
      return;
    }
    setBenchmarkRunning(true);
    const report = await run<Record<string, any>>(
      en ? "Run same-model A/B" : "執行同模型 A/B",
      () => api<Record<string, any>>("/api/metrics/token-ab/run", {
        method: "POST",
        body: JSON.stringify({
          question,
          locale: replyLocale,
          current_rule_package: packageForBenchmark,
          full_history: messages.slice(-100).map((item) => ({ role: item.role, content: item.content })),
        }),
      }),
    );
    if (report) setTokenBenchmark(report);
    setBenchmarkRunning(false);
  }

  const currentRulePackagePanel = (
    <section className="ops-panel current-package-panel" data-testid="current-rule-package-panel">
      <header><ShieldCheck size={20} /><div><span>{copy.ruleOs.currentPackage}</span><h2>{displayRulePackage ? (packageRules.length > 0 ? copy.responseReceipt.signedRuleApplied : copy.responseReceipt.generalChat) : (en ? "Waiting for a response" : "等待一次模型回覆")}</h2></div><em>{currentPostCheck?.allowed === false ? copy.responseReceipt.blocked : displayRulePackage ? copy.responseReceipt.passed : "--"}</em></header>
      {!displayRulePackage ? <p>{en ? "Ask a question after storing a signed rule. This panel will show exactly what the model received." : "完成規則簽名入庫後再提問，這裡會顯示模型本次實際收到的最小規則包。"}</p> : <>
        <div className="package-counts"><div><b>{packageRules.length}</b><span>{copy.responseReceipt.ruleStore}</span></div><div><b>{packageData.length}</b><span>{copy.responseReceipt.dataStore}</span></div><div><b>{packagePreferences.length}</b><span>{copy.responseReceipt.memoryStore}</span></div><div><b>{packageCandidates.length}</b><span>{copy.responseReceipt.retrievalStore}</span></div></div>
        <div className="package-authority-list">{packageRules.length > 0 ? packageRules.map((item, index) => <span key={`package-rule-${index}`}><CheckCircle2 size={14} />{packageItemTitle(item, en)}</span>) : <small>{copy.responseReceipt.noAuthority}</small>}</div>
        <dl><div><dt>{copy.responseReceipt.chatContext}</dt><dd>{displayRulePackage.chat_context_used ? copy.responseReceipt.included : copy.responseReceipt.excluded}</dd></div><div><dt>{copy.responseReceipt.postCheck}</dt><dd>{currentPostCheck?.allowed === false ? copy.responseReceipt.blocked : copy.responseReceipt.passed}</dd></div></dl>
        <small>{copy.responseReceipt.retrievalOnly}</small>
      </>}
    </section>
  );

  const tokenAuditPanel = (
    <section className="ops-panel token-audit-panel">
      <header><Activity size={20} /><div><span>{en ? "TOKEN AUDIT" : "TOKEN 用量審計"}</span><h2>{tokenMetrics.measurement_scope === "rule_authoring" ? (en ? "Rulebook authoring" : "規則書編譯計量") : tokenMetrics.measurement_scope === "general_chat" ? (en ? "General chat meter" : "一般聊天計量") : (en ? "Context compression" : "上下文壓縮審計")}</h2></div><em>{tokenStatusLabel}</em></header>
      <p>{tokenMetrics.measurement_scope === "rule_authoring"
        ? (en ? "This request measures confirmation-sheet authoring. Savings require a later signed-rule answer or the formal A/B benchmark." : "這次計量的是確認單編譯；節省量要等簽名規則回答，或正式 A/B 測試後才成立。")
        : tokenMetrics.measurement_scope === "general_chat"
          ? (en ? "This is a normal chat call. Actual usage may be shown, but rule-compression savings do not apply before a signed rule is matched." : "這次是一般聊天；可以顯示本次實際用量，但尚未命中已簽名規則，不能宣稱規則壓縮節省。")
          : hasTokenComparison
            ? (verifiedTokenComparison ? (en ? "Both the full-context and minimal-rule-package paths were called with the same model." : "完整上下文與最小規則包已用同一模型各自實際呼叫。") : (en ? "The actual request is recorded; the avoided full context remains a counterfactual estimate until the A/B benchmark runs." : "本次實際用量已記錄；完整上下文尚未真的送出，因此節省量在 A/B 測試前仍是反事實估算。"))
            : (en ? "No current response comparison exists. Historical estimates are not shown as verified savings." : "目前沒有本次回覆的比較資料；歷史估算不會顯示成已驗證節省。")}</p>
      <div className="usage-hero">
        <div><span>{comparisonLabel}</span><strong>{hasTokenComparison ? tokenCount(savedTokens) : "--"}</strong><small>tokens</small></div>
        <div><span>{en ? "Reduction" : "壓縮比例"}</span><strong>{hasTokenComparison ? tokenCount(reductionPercent) : "--"}%</strong><small>{verifiedTokenComparison ? (en ? "same-model A/B" : "同模型 A/B") : hasTokenComparison ? (en ? "counterfactual baseline" : "反事實基準") : (en ? "not measured" : "尚未量測")}</small></div>
        <div><span>{en ? "API cost" : "API 成本"}</span><strong>{tokenCost}</strong><small>{hasActualUsage ? tokenMetrics.price_status === "local_no_api_charge" ? (en ? "local runtime" : "本地模型無 API 費") : tokenMetrics.price_status === "configured" ? (en ? "price snapshot" : "依價格快照估算") : (en ? "price not set" : "尚未設定價格") : (en ? "no current call" : "尚無本次呼叫")}</small></div>
      </div>
      <dl>
        <div><dt>{en ? "Full context baseline" : "完整上下文基準"}</dt><dd>{hasTokenComparison ? tokenCount(baselineTokens) : "--"} tokens</dd></div>
        <div><dt>{en ? "Actual prompt sent" : "實際送出提示"}</dt><dd>{hasActualUsage ? tokenCount(actualPromptTokens) : "--"} tokens</dd></div>
        <div><dt>{en ? "Model response" : "模型輸出"}</dt><dd>{hasActualUsage ? tokenCount(actualCompletionTokens) : "--"} tokens</dd></div>
        <div><dt>{en ? "Rule package shape" : "規則包形狀"}</dt><dd>{hasTokenComparison ? tokenCount(tokenMetrics.current_rule_package_tokens_est) : "--"} tokens</dd></div>
        <div><dt>{en ? "Compression" : "壓縮率"}</dt><dd>{hasTokenComparison ? tokenCount(reductionPercent) : "--"}%</dd></div>
        <div><dt>{en ? "Measurement" : "量測方式"}</dt><dd>{tokenBasis}</dd></div>
        <div><dt>{en ? "Estimated saved cost" : "估算省下成本"}</dt><dd>{savedCost}</dd></div>
        <div><dt>{en ? "Formal basis" : "正式依據"}</dt><dd>{en ? "Four-store signed rules" : "四庫已簽名規則"}</dd></div>
        <div><dt>LOGIC / CORPUS / MEMORY</dt><dd>{tokenMetrics.formal_source_summary ? `${tokenMetrics.formal_source_summary.matched_rules ?? 0} / ${tokenMetrics.formal_source_summary.citable_data ?? 0} / ${tokenMetrics.formal_source_summary.user_preferences ?? 0}` : "--"}</dd></div>
        <div><dt>VECTOR</dt><dd>{tokenMetrics.formal_source_summary?.vector_recall_only ? (en ? "Recall only" : "只召回，不作正式依據") : "--"}</dd></div>
        <div><dt>{en ? "Chat context as formal basis" : "聊天上下文作正式依據"}</dt><dd>{typeof tokenMetrics.chat_context_used === "boolean" ? tokenMetrics.chat_context_used ? (en ? "Yes" : "是") : (en ? "No" : "否") : "--"}</dd></div>
      </dl>
      <div className={`token-ab-proof ${benchmarkVerified ? "verified" : "pending"}`}>
        <div><b>{en ? "Same-model A/B proof" : "同模型 A/B 實測"}</b><small>{benchmarkVerified
          ? `${tokenBenchmark.model_name} · ${tokenCount(tokenBenchmark.variants?.A?.prompt_tokens)} -> ${tokenCount(tokenBenchmark.variants?.B?.prompt_tokens)} prompt tokens · ${tokenCount(tokenBenchmark.savings?.prompt?.reduction_percent)}%`
          : (en ? "Runs the full-context control and minimal rule-package path against the exact same connected model. Provider usage is required for VERIFIED." : "用同一個已連線模型各跑一次完整上下文與最小規則包；只有兩次都有 Provider usage 才標成 VERIFIED。")}</small></div>
        <button disabled={benchmarkRunning || !modelReady || !(displayRulePackage?.matched_rules || []).length} onClick={() => void runVerifiedTokenBenchmark()}><Play size={15} />{benchmarkRunning ? (en ? "Running two calls" : "正在跑兩次模型") : (en ? "Run verified A/B" : "執行實測 A/B")}</button>
      </div>
    </section>
  );

  const chatTokenMeter = (
    <section className="chat-token-meter" aria-label={en ? "Token and cost meter" : "Token 與成本計量"} data-testid="chat-token-meter">
      <header><Activity size={17} /><div><span>TOKEN / COST METER</span><b>{en ? "Actual usage per response; savings require a baseline" : "每次記錄實際用量；節省量需要比較基準"}</b></div><em>{tokenBasis}</em><button className="icon-button" onClick={() => setView("model")} title={en ? "Open price settings" : "開啟價格設定"}><Settings size={15} /></button></header>
      <div className="chat-token-values">
        <div><span>{en ? "Actual input" : "實際輸入"}</span><strong>{hasActualUsage ? tokenCount(actualPromptTokens) : "--"}</strong><small>tokens</small></div>
        <div><span>{en ? "Model output" : "模型輸出"}</span><strong>{hasActualUsage ? tokenCount(actualCompletionTokens) : "--"}</strong><small>tokens</small></div>
        <div><span>{comparisonLabel}</span><strong>{hasTokenComparison ? tokenCount(savedTokens) : "--"}</strong><small>tokens</small></div>
        <div><span>{en ? "Reduction" : "壓縮比例"}</span><strong>{hasTokenComparison ? tokenCount(reductionPercent) : "--"}%</strong><small>{verifiedTokenComparison ? (en ? "same-model A/B" : "同模型 A/B") : (en ? "vs local baseline" : "相對本機基準")}</small></div>
        <div><span>{en ? "API cost" : "API 成本"}</span><strong>{tokenCost}</strong><small>{tokenMetrics.price_status === "local_no_api_charge" && hasActualUsage ? (en ? "local model" : "本地模型") : (en ? "price snapshot" : "依價格快照")}</small></div>
      </div>
      <details><summary><Info size={14} />{en ? "How this is calculated" : "這些數字怎麼算"}</summary><p>{en ? "A normal response records provider usage when available. Until the full-context control is also called with the same model, saved tokens are labeled as an estimate. The final benchmark repeats both paths and reports raw usage and latency." : "一般回覆會優先記錄模型回傳的實際 usage；在完整上下文控制組也用同一模型實際呼叫前，節省 Token 只能標成估算。最終測試會重複跑兩條路徑並保留原始用量與耗時。"}</p><dl><div><dt>{en ? "Full-context baseline" : "完整上下文基準"}</dt><dd>{hasTokenComparison ? tokenCount(baselineTokens) : "--"} tokens</dd></div><div><dt>{en ? "Rule package" : "本次規則包"}</dt><dd>{hasTokenComparison ? tokenCount(tokenMetrics.current_rule_package_tokens_est) : "--"} tokens</dd></div><div><dt>{en ? "Saved cost" : "估算省下成本"}</dt><dd>{savedCost}</dd></div></dl></details>
    </section>
  );

  const principlesPanel = (
    <section className="ops-panel principles-panel">
      <header><KeyRound size={20} /><div><span>CORE PRINCIPLES</span><h2>{en ? "Hard rules" : "核心原則"}</h2></div></header>
      <ul>{corePrinciples.map((item) => <li key={item}>{item}</li>)}</ul>
    </section>
  );

  const automationPanel = (
    <section className="ops-panel automation-panel">
      <header><Rocket size={20} /><div><span>AUTOMATION LEVEL</span><h2>{en ? "Execution grade" : "自動化等級"}</h2></div></header>
      <div className="automation-levels"><span><Lock size={15} />L0</span><span className="active"><Eye size={15} />L1</span><span><FileKey size={15} />L2</span><span><SlidersHorizontal size={15} />L3</span><span><Rocket size={15} />L4</span></div>
      <small>{en ? "Current ceiling: draft and structure assist until the user signs." : "目前上限：使用者簽名前只能產生草案與結構輔助。"}</small>
    </section>
  );

  const phonePanel = (
    <section className="ops-panel phone-panel">
      <header><Smartphone size={20} /><div><span>MOBILE LINK</span><h2>{en ? "Phone connection" : "手機連線"}</h2></div><em className={companion?.lan_companion_enabled ? "enabled" : "confirm"}>{companion?.lan_companion_enabled ? (en ? "ready" : "可配對") : "LAN off"}</em></header>
      <div className="phone-link-visual"><Smartphone size={38} /><span><i /><Wifi size={16} /><i /></span><Monitor size={42} /></div>
      <small>{companion?.base_url || backend}</small>
      {pairing ? <div className="qr-wrap"><QRCodeSVG value={`${pairing.base_url}?companion_token=${pairing.pairing_code}`} size={92} /><strong>{pairing.pairing_code}</strong></div> : <button disabled={!companion?.lan_companion_enabled} onClick={() => void startPairing()}><FileKey size={15} />{en ? "Create pair code" : "取得配對碼"}</button>}
    </section>
  );

  const selectedRuleListItem = rules.find((rule) => rule.rule_id === selectedRule);
  const rulePanel = (
    <section className="sovereignty-zone" aria-label={en ? "Rule sovereignty" : "規則主權區"}>
      <div className="zone-title"><div><span>RULE SOVEREIGNTY</span><h2>{copy.navigation.rules}</h2></div><button className="icon-button" onClick={() => void refreshAll()} title={en ? "Refresh" : "更新"}><RefreshCw size={16} /></button></div>
      <div className="metric-line"><span>{en ? "Active" : "啟用"}<b>{activeRules}</b></span><span>{en ? "Signed" : "已簽名"}<b>{rules.filter((r) => ["owner_signed", "active"].includes(r.activation_status)).length}</b></span><span>{en ? "Packs" : "規則包"}<b>{packs.length}</b></span></div>
      <div className="natural-rule-composer"><label>{en ? "Describe the rule in plain language" : "用一句人話建立規則"}<textarea value={naturalRuleText} onChange={(e) => setNaturalRuleText(e.target.value)} placeholder={en ? "Before publishing anything, require my signature." : "例如：凡是要發布內容，都必須先讓我簽名確認。"} /></label><button disabled={!naturalRuleText.trim()} onClick={() => void createNaturalRule()}><Sparkles size={15} />{en ? "Create unsigned draft" : "建立未簽名草案"}</button></div>
      <div className="rule-stack">
        {rules.length === 0 && <div className="empty-state">{en ? "No local rules" : "尚無本機規則"}</div>}
        {rules.slice(0, 8).map((rule) => <button key={rule.rule_id} className={`rule-row ${selectedRule === rule.rule_id ? "selected" : ""}`} onClick={() => setSelectedRule(rule.rule_id)}><span className={`state-dot ${rule.activation_status}`} /><span><b>{rule.rule_name}</b><small>{ruleOverview(rule, en)}</small><small>{en ? "Local user rule" : "本機使用者規則"} · {rule.rule_version}</small></span><em>{readableStatus(rule.activation_status, en)}</em></button>)}
      </div>
      {selectedRule && selectedRuleListItem?.activation_status !== "active" && <div className="signature-dock"><label>{en ? "Owner signature" : "擁有者簽名"}<input type="password" value={ruleSignature} onChange={(e) => setRuleSignature(e.target.value)} /></label><div><button disabled={!ruleSignature} onClick={() => void signRule()}><ShieldCheck size={15} />{en ? "Sign" : "簽名"}</button><button disabled={!ruleSignature} onClick={() => void activateRule()}><Play size={15} />{en ? "Activate" : "啟用"}</button></div></div>}
    </section>
  );

  const modelStatusText = !runtimeSynced
    ? (en ? "Syncing runtime" : "正在同步系統")
    : modelReady
      ? (currentModelName || (en ? "Model online" : "模型已連線"))
      : (en ? "Connect model" : "尚未連接模型");
  const currentWorkbenchStep = !task || !task.scbkr ? 1 : !task.confirmed ? 2 : 3;

  const chatPanel = (
    <section className="command-zone chat-main" aria-label="一般聊天主視窗">
      <header className="command-header"><div><span>{en ? "LOCAL RULE OPERATING SYSTEM" : "本地規則作業系統"}</span><h1>{en ? "SCBKR Chat" : "SCBKR 對話"}</h1></div><div className={`model-live-badge ${!runtimeSynced ? "syncing" : modelReady ? "online" : "offline"}`}>{!runtimeSynced ? <RefreshCw className="spin" size={15} /> : modelReady ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}<span>{modelStatusText}</span></div></header>
      <div className="chat-control-bar">
        <div className="command-modes" role="tablist" aria-label={en ? "Quick route" : "自然語言快速路由"}><button className={commandMode === "chat" ? "active" : ""} onClick={() => setCommandMode("chat")}><MessageSquare size={15} />{en ? "Chat" : "聊天"}</button><button className={commandMode === "web" ? "active" : ""} onClick={() => setCommandMode("web")}><Globe2 size={15} />{en ? "Web" : "上網"}</button><button className={commandMode === "search" ? "active" : ""} onClick={() => setCommandMode("search")}><Search size={15} />{en ? "Four stores" : "查四庫"}</button><button className={commandMode === "rule" ? "active" : ""} onClick={() => setCommandMode("rule")}><FileKey size={15} />{en ? "New rule" : "建規則"}</button></div>
        <div className={`rule-context-pill ${String(ruleState.awareness_state || "empty").toLowerCase()}`}><ShieldCheck size={15} /><span>{activeRuleApplied ? copy.responseReceipt.signedRuleApplied : activeRules > 0 ? (en ? "Signed rules available" : "已有簽名規則可用") : (en ? "General chat" : "一般聊天模式")}</span><b>{activeRules}</b></div>
        <button className="icon-button" onClick={() => setView("runtime")} title={en ? "Open token and rule audit" : "查看規則與 Token 審計"}><Activity size={17} /></button>
      </div>
      <div className="message-list" ref={messageListRef}>{messages.map((item, index) => <div key={`${item.role}-${index}`} className={`message ${item.role} ${item.card ? "has-card" : ""}`}><span>{item.role === "assistant" ? "SCBKR" : en ? "YOU" : "你"}</span><div>{item.content}</div>{item.card && renderWorkflowCard(item.card)}{item.role === "assistant" && renderResponseReceipt(item)}</div>)}</div>
      <div className="chat-input"><button className="icon-button attachment-button" onClick={() => setToolLauncherOpen((value) => !value)} title={en ? "Open tools" : "開啟工具"}><Plus size={20} /></button><label className="natural-input-label"><span>{commandMode === "chat" ? (en ? "Message" : "訊息") : commandMode === "web" ? (en ? "Verified web query" : "上網查證") : commandMode === "search" ? (en ? "Signed-store question" : "四庫問題") : (en ? "Rule request" : "規則需求")}</span><textarea aria-label={en ? "Natural language input" : "自然語言輸入"} value={chatInput} onChange={(e) => setChatInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void sendChat(); } }} placeholder={commandMode === "chat" ? (en ? "Chat normally, write, summarize, or ask how SCBKR works..." : "直接聊天、寫作、摘要，或詢問 SCBKR 怎麼使用…") : commandMode === "web" ? (en ? "Verify current information about..." : "輸入要查證的最新資訊…") : commandMode === "search" ? (en ? "What do my signed rules say about publishing?" : "詢問已簽名規則或四庫資料…") : (en ? "Describe any reusable judgement in plain language." : "用人話描述任何想長期沿用的判斷規則…")} /></label><button className="icon-button send-button" disabled={!chatInput.trim()} onClick={() => void sendChat()} title={en ? "Send" : "送出"}>{commandMode === "web" ? <Globe2 size={20} /> : commandMode === "search" ? <Search size={20} /> : commandMode === "rule" ? <FileKey size={20} /> : <Send size={20} />}</button></div>
    </section>
  );

  const taskCompiling = task?.status === "model_compiling";
  const taskHardBlocked = task?.status === "model_unavailable" || task?.status === "model_timeout" || task?.status === "model_rulebook_schema_invalid";
  const taskCapabilityLimited = task?.status === "model_capability_limited" || task?.scbkr?.draft_source === "model_capability_limited";
  const taskSyncBlocked = taskHardBlocked || taskCapabilityLimited || task?.status === "model_validation_failed";
  const modelCapability = (task as any)?.model_capability || task?.scbkr?.model_capability || {};
  const persistedTaskPassed = Boolean(task?.confirmed && (task?.review_passed || task?.storage_confirmed));
  const taskModelUsed = Boolean((task as any)?.model_used || task?.scbkr?.model_participated);
  const taskSchemaPassed = Boolean((task as any)?.model_schema_valid ?? task?.scbkr?.model_schema_valid ?? persistedTaskPassed);
  const taskMeaningPassed = Boolean((task as any)?.model_semantic_valid ?? task?.scbkr?.model_semantic_valid ?? persistedTaskPassed);
  const taskValidatorPassed = Boolean((task as any)?.validator_passed ?? task?.scbkr?.validator_passed ?? persistedTaskPassed);
  const draftSummary = String(task?.scbkr?.rule_summary || task?.draft_object?.summary || task?.raw_input || "").trim();
  const draftMissing = listText(task?.scbkr?.missing_information);
  const draftConfirmations = listText(task?.scbkr?.user_confirmation_items);
  const draftRisks = listText(task?.scbkr?.risk_reminders);
  const draftModelLimits = listText(task?.scbkr?.model_cannot_decide);
  const draftNextActions = listText(task?.scbkr?.next_actions).map((item) => publicNextAction(item, en));

  const workbenchPanel = (
    <section className="workbench-zone workbench-panel" aria-label="SCBKR 工作台側欄">
      <div className="zone-title product-title"><div><span>{en ? "MODEL-ASSISTED RULEBOOK" : "模型協作確認單"}</span><h2>{en ? "SCBKR Workbench" : "SCBKR 工作台"}</h2><small>{en ? "The model drafts. You review and sign. Signed content is compiled into the four stores." : "模型草擬，你逐欄確認與簽名；驗收後才編譯進四庫。"}</small></div><CircleGauge size={20} /></div>
      <nav className="workbench-steps" aria-label={en ? "Rulebook workflow" : "確認單流程"}>
        <button className={currentWorkbenchStep >= 1 ? "active" : ""} onClick={() => document.getElementById("wb-author")?.scrollIntoView({ behavior: "smooth" })}><span>1</span><b>{en ? "Model draft" : "模型草擬"}</b><small>{en ? "Natural language to S/C/B/K/R" : "人話轉成五維"}</small></button>
        <button className={currentWorkbenchStep >= 2 ? "active" : ""} disabled={!task?.scbkr} onClick={() => document.getElementById("wb-review")?.scrollIntoView({ behavior: "smooth" })}><span>2</span><b>{en ? "Review" : "逐欄確認"}</b><small>{en ? "Read, ask, and edit" : "能看、能問、能改"}</small></button>
        <button className={currentWorkbenchStep >= 3 ? "active" : ""} disabled={!task?.scbkr} onClick={() => document.getElementById("wb-sign")?.scrollIntoView({ behavior: "smooth" })}><span>3</span><b>{en ? "Sign & store" : "簽名與入庫"}</b><small>{en ? "Validate, review, compile" : "驗證、驗收、編譯"}</small></button>
      </nav>
      {!task ? <div className="workbench-empty" id="wb-author"><div className={`model-readiness ${modelReady ? "ready" : "blocked"}`}>{modelReady ? <CheckCircle2 size={19} /> : <AlertTriangle size={19} />}<span><b>{modelReady ? (en ? "Model ready" : "模型已準備好") : (en ? "Connect a model first" : "請先連接模型")}</b><small>{modelReady ? (currentModelName || (en ? "Connected model" : "已連線模型")) : (en ? "SCBKR will not replace a missing model with a template." : "SCBKR 不會用模板冒充模型完成草擬。")}</small></span>{!modelReady && <button onClick={() => setView("model")}><Settings size={15} />{en ? "Model settings" : "模型設定"}</button>}</div><div className="authoring-composer"><Sparkles size={24} /><div><h3>{en ? "Describe any reusable judgement" : "用人話描述任何想長期沿用的判斷"}</h3><p>{en ? "The connected model will apply the SCBKR structure to your actual request, not select a preset template." : "連線模型會理解你的實際需求並填寫 S／C／B／K／R，不是挑一個預設範本。"}</p></div><label>{en ? "Rule request" : "規則需求"}<textarea value={taskInput} onChange={(e) => setTaskInput(e.target.value)} placeholder={en ? "Whenever a friend asks me to pay first, assess whether the risk is being shifted to me and turn that judgement into my local rule." : "例如：凡是朋友要求我先墊錢，先判斷是否把風險轉嫁給我，並寫成我的本地規則。"} /></label><button className="primary-action" disabled={!taskInput.trim() || !modelReady} onClick={() => void createTask()}><BrainCircuit size={16} />{en ? "Ask model to draft" : "請模型草擬確認單"}</button></div></div> : <>
        <div className="task-state product-state" id="wb-author"><span>{task.task_name || task.task_id}</span><b>{readableStatus(task.status, en)}</b><em>{planLevel}</em><em>{currentModelName || (en ? "No model" : "尚無模型")}</em><em>{task.confirmed ? (en ? "Signed" : "已簽名") : taskCapabilityLimited ? (en ? "Signature locked" : "簽名已鎖定") : (en ? "Waiting for your review" : "等待你確認")}</em></div>
        {task.status === "storage_conflict" && <section className="compiler-panel blocked" data-testid="storage-state-conflict">
          <header><AlertTriangle size={16} /><div><span>{copy.stateConflict.eyebrow}</span><b>{copy.stateConflict.title}</b></div></header>
          <p>{copy.stateConflict.body}</p>
          <div className="compiler-meta"><span>{copy.stateConflict.noWrite}</span><span>{copy.stateConflict.freshState}</span><span>{copy.stateConflict.newSignature}</span></div>
          <button onClick={() => void refreshConflictedRevision()}><RefreshCw size={15} />{copy.stateConflict.action}</button>
        </section>}
        {taskHardBlocked && !task.scbkr && <section className="compiler-panel blocked">
          <header><AlertTriangle size={16} /><div><span>{en ? "MODEL AUTHORING BLOCKED" : "模型規則書生成未完成"}</span><b>{readableStatus(task.status, en)}</b></div></header>
          <p>{human((task as any).model_rulebook_authoring?.failure_message || (en ? "The model could not be reached or did not return a valid SCBKR rulebook. No fallback draft was created." : "模型未能連上或未回傳合格 SCBKR 規則書；系統沒有產生 fallback 草稿。"))}</p>
          <div className="compiler-meta"><span>{providerLabel((task as any).model_provider || model?.provider)}</span><span>{(task as any).model_name || model?.model_name || (en ? "No model selected" : "尚未選擇模型")}</span><span>{publicNextAction((task as any).next_required_action, en)}</span></div>
          <div className="button-row"><button onClick={() => setView("model")}><Settings size={15} />{en ? "Open model settings" : "打開模型設定"}</button><button onClick={() => void regenerateCurrentScbkr()}><BrainCircuit size={15} />{en ? "Retry model authoring" : "重新呼叫模型生成"}</button></div>
        </section>}
        {taskCapabilityLimited && task.scbkr && <section className="compiler-panel capability-limited" aria-label={en ? "Current model capability" : "目前模型能力狀態"}>
          <header><CircleGauge size={17} /><div><span>{en ? "CURRENT TASK CAPABILITY" : "本次任務能力判定"}</span><b>{en ? "SCBKR draft understood; closure still missing" : "已理解 SCBKR 草稿，尚未完成閉合"}</b></div><em>{en ? "DRAFT ONLY" : "僅限草稿"}</em></header>
          <p>{human(modelCapability.summary || (en ? "The connected model produced a real SCBKR draft, but unresolved dimension gaps prevent signature and storage." : "目前模型已產生真實 SCBKR 草稿，但仍有五維缺口，因此不能簽名或入庫。"))}</p>
          <div className="capability-gap-list">{listText(modelCapability.unresolved_gaps || task.scbkr?.missing_information).map((gap, index) => <span key={`${gap}-${index}`}><AlertTriangle size={14} />{capabilityGapLabel(gap, en)}</span>)}</div>
          <small>{human(modelCapability.recommended_action || (en ? "Add missing information or select a stronger model for one compilation pass. Latency is not used for this decision." : "補充缺少資料，或切換較強模型完成一次補鏈收束；本判定不以等待時間為依據。"))}</small>
          <div className="compiler-meta"><span>{en ? "Small-model reuse after signing" : "簽名後可回小模型引用"}</span><span>{en ? "No automatic cloud call" : "不自動呼叫雲端"}</span><span>{en ? "Latency ignored" : "不以延遲升級"}</span></div>
          <div className="button-row"><button onClick={() => void regenerateCurrentScbkr()} disabled={taskCompiling}><BrainCircuit size={15} />{en ? "Retry this model" : "讓目前模型再草擬"}</button><button onClick={() => setView("model")}><Settings size={15} />{en ? "Choose a stronger model" : "選擇較強模型收束"}</button></div>
        </section>}
        <section className={`compiler-panel model-evidence-panel ${taskModelUsed && taskValidatorPassed ? "passed" : taskHardBlocked ? "blocked" : "review"}`} data-testid="model-participation-status">
          <header><Bot size={16} /><div><span>{copy.workbench.modelEvidence}</span><b>{taskCompiling ? (en ? "Model is drafting" : "模型正在草擬") : taskHardBlocked ? copy.workbench.modelUnavailable : taskCapabilityLimited ? copy.workbench.modelNeedsRepair : copy.workbench.modelCompleted}</b></div></header>
          <div className="model-checks"><span className={taskModelUsed ? "passed" : "waiting"}>{taskModelUsed ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}{taskModelUsed ? (en ? "Model participated" : "模型已參與") : (en ? "No completed model draft" : "尚無完成的模型草稿")}</span><span className={taskSchemaPassed ? "passed" : "waiting"}>{taskSchemaPassed ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}{taskSchemaPassed ? copy.workbench.formatPassed : copy.workbench.waitingValidation}</span><span className={taskMeaningPassed ? "passed" : "waiting"}>{taskMeaningPassed ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}{taskMeaningPassed ? copy.workbench.meaningPassed : copy.workbench.waitingValidation}</span><span className={taskValidatorPassed ? "passed" : "waiting"}>{taskValidatorPassed ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}{taskValidatorPassed ? copy.workbench.validatorPassed : copy.workbench.waitingValidation}</span></div>
          <small>{providerLabel((task as any).model_provider || model?.provider)} · {(task as any).model_name || task.scbkr?.model_name || model?.model_name || (en ? "No model selected" : "尚未選擇模型")}</small>
          <div className="button-row">
            {!task.confirmed && <button disabled={taskCompiling} onClick={() => void regenerateCurrentScbkr()}><BrainCircuit size={15} />{en ? "Ask model to fill again" : "模型補寫表單"}</button>}
            {!task.confirmed && <button disabled={taskHardBlocked || taskCompiling} onClick={() => void applyCurrentRuleAssist()}><SlidersHorizontal size={15} />{en ? "Apply FREE structure check" : "套用免費版結構檢查"}</button>}
          </div>
        </section>
        {!task.confirmed && <section className="quick-patch-inline">
          <header><Bot size={16} /><div><span>{en ? "COLLABORATION SHORTCUTS" : "協作快捷補欄"}</span><b>{en ? "Model proposes inside SCBKR" : "模型只能在 SCBKR 表單內補寫"}</b></div></header>
          <div className="quick-patch-grid"><button disabled={!task.scbkr || task.confirmed || taskHardBlocked} onClick={() => quickPatch("R", "請補失效條件，尤其未授權發布、未引用正式資料、未通過驗收時如何失效。", "Add invalidation conditions, especially unauthorized publishing, missing formal sources, and failed review.")}>{en ? "Add invalidation" : "補失效條件"}</button><button disabled={!task.scbkr || task.confirmed || taskHardBlocked} onClick={() => quickPatch("B", "請補邊界：不得自動發布、不得編造價格、不得引用檢索庫當正式依據。", "Add boundaries: no auto publishing, no invented prices, no retrieval store as formal basis.")}>{en ? "Add boundary" : "補邊界"}</button><button disabled={!task.scbkr || task.confirmed || taskHardBlocked} onClick={() => quickPatch("R", "請補回放要求：記錄路由、規則包、post-check、簽名、驗收與入庫結果。", "Add replay requirements: route, rule package, post-check, signature, review, and storage result.")}>{en ? "Add replay" : "補回放要求"}</button></div>
        </section>}
        {!task.confirmed && task.scbkr && <section className="patch-assistant" id="wb-review">
          <header><MessageSquare size={16} /><div><span>{en ? "EDIT BY CONVERSATION" : "對話修表單"}</span><b>{en ? "Model proposes, user applies" : "模型先草案，使用者再套用"}</b></div></header>
          <div className="patch-controls">
            <label>{en ? "Layer" : "要修改哪一層"}<select value={patchLayer} onChange={(event) => setPatchLayer(event.target.value as ScbkrDimensionKey)}>{dims.map((dim) => <option key={dim} value={dim}>{dim} · {dimensionNames[dim][en ? "en" : "zh"]}</option>)}</select></label>
            <label>{en ? "Instruction" : "用人話說哪裡不對"}<textarea value={patchInstruction} onChange={(event) => setPatchInstruction(event.target.value)} placeholder={en ? "Example: B is missing publish boundaries and K is claiming citations." : "例如：B 層沒有寫清楚不能發布；K 層不能假裝有引用四庫。"} /></label>
          </div>
          <div className="button-row"><button disabled={!patchInstruction.trim() || taskHardBlocked} onClick={() => void draftLayerPatch()}><Sparkles size={15} />{en ? "Propose patch" : "請模型提出修改"}</button><button disabled={!pendingPatch || taskHardBlocked} onClick={() => void applyLayerPatch()}><Check size={15} />{en ? "Apply patch" : "套用修改草案"}</button><button disabled={!pendingPatch} onClick={() => setPendingPatch(null)}><X size={15} />{en ? "Discard" : "取消草案"}</button></div>
          {pendingPatch && <div className="patch-preview"><b>{pendingPatch.layer} · {pendingPatch.model_name || currentModelName || (en ? "Connected model" : "連線模型")}</b><p>{human(pendingPatch.after_draft?.model_draft_content || pendingPatch.after_draft?.owner_draft_content || pendingPatch.reason)}</p><small>{human(pendingPatch.after_draft?.model_explanation || pendingPatch.reason)}</small></div>}
        </section>}
        {task.scbkr && <section className="draft-review-overview" data-testid="draft-review-overview">
          <header><ShieldCheck size={18} /><div><span>{copy.workbench.overviewTitle}</span><h3>{draftSummary || (en ? "Review this five-dimension draft" : "請逐欄確認這份五維草稿")}</h3></div></header>
          <div className="review-overview-grid">
            <section><b>{copy.workbench.missing}</b>{draftMissing.length > 0 ? draftMissing.map((item, index) => <span key={`global-missing-${index}`}>{item}</span>) : <small>{copy.workbench.none}</small>}</section>
            <section><b>{copy.workbench.risks}</b>{draftRisks.length > 0 ? draftRisks.map((item, index) => <span key={`global-risk-${index}`}>{item}</span>) : <small>{copy.workbench.none}</small>}</section>
            <section><b>{copy.workbench.confirmations}</b>{draftConfirmations.length > 0 ? draftConfirmations.map((item, index) => <span key={`global-confirm-${index}`}>{item}</span>) : <small>{copy.workbench.none}</small>}</section>
            <section><b>{copy.workbench.modelLimits}</b>{draftModelLimits.length > 0 ? draftModelLimits.map((item, index) => <span key={`global-limit-${index}`}>{item}</span>) : <small>{en ? "The model still cannot sign, approve, store, or act for you." : "模型仍不能替你簽名、核准、入庫或執行。"}</small>}</section>
          </div>
          {draftNextActions.length > 0 && <footer><b>{copy.workbench.nextSteps}</b>{draftNextActions.map((item, index) => <span key={`next-${index}`}>{item}</span>)}</footer>}
        </section>}
        {task.scbkr && <div className="workbench-section-head"><div><span>{en ? "FIVE-DIMENSION REVIEW" : "五維逐欄確認"}</span><h3>{en ? "Read the model's reasoning, then edit what is wrong" : "先看模型怎麼判，再直接修改不對的地方"}</h3></div><ShieldCheck size={20} /></div>}
        <div className="dimension-grid product-dimensions">{dims.map((dim) => {
          const content = task.scbkr?.[dim] || {};
          const contract = (content.rule_os_dimension_contract || {}) as Record<string, any>;
          const preview = human(content.task_subject || content.core_logic || content.stop_conditions || content.references || content.acceptance_criteria).slice(0, 180);
          const draftText = dimensionDraftText(content, dim, en) || preview;
          const explanation = human(content.model_explanation || content.explanation || contract.usage_conditions || (en ? "The model filled this field from your request." : "模型依你的需求填寫此欄。"));
          const missing = listText(content.missing_information || contract.gap_notes);
          const confirmations = listText(content.needs_user_confirmation || content.pending_questions);
          const risks = listText(content.risk_notes || content.basic_risk_reminders);
          const editValue = dimensionEdits[dim] ?? draftText;
          return <details className={`dimension-row ${dimColor[dim]}`} key={dim} open={dim === "S"}>
            <summary><b>{dim}</b><span><strong>{copy.dimensions[dim]} <em>{dimensionNames[dim][en ? "en" : "zh"]}</em></strong>{draftText || (en ? "Waiting for model draft" : "等待模型草擬")}</span><ChevronRight size={15} /></summary>
            <div className="dimension-human-content"><div className="dimension-answer"><span>{en ? "MODEL DRAFT" : "模型草稿"}</span><p>{draftText}</p></div><div className="dimension-explanation"><Bot size={16} /><span><b>{en ? "Why the model wrote this" : "模型為什麼這樣寫"}</b><p>{explanation}</p></span></div>{(missing.length > 0 || confirmations.length > 0 || risks.length > 0) && <div className="dimension-review-notes">{missing.length > 0 && <div><b>{en ? "Missing information" : "缺少資料"}</b>{missing.map((item, index) => <span key={`${dim}-missing-${index}`}>{item}</span>)}</div>}{confirmations.length > 0 && <div><b>{en ? "Confirm with you" : "需要你確認"}</b>{confirmations.map((item, index) => <span key={`${dim}-confirm-${index}`}>{item}</span>)}</div>}{risks.length > 0 && <div><b>{en ? "Risk" : "風險"}</b>{risks.map((item, index) => <span key={`${dim}-risk-${index}`}>{item}</span>)}</div>}</div>}</div>
            <label>{en ? "Your edit" : "直接修改這一層"}<textarea value={editValue} onChange={(event) => setDimensionEdits((current) => ({ ...current, [dim]: event.target.value }))} disabled={task.confirmed} /></label>
            {!task.confirmed && <button disabled={!String(dimensionEdits[dim] ?? "").trim()} onClick={() => void saveDimensionEdit(dim)}><Save size={14} />{en ? "Save this layer" : "儲存此層修改"}</button>}
          </details>;
        })}</div>
        <div className="workbench-section-head sign-head" id="wb-sign"><div><span>{en ? "OWNER CONTROL" : "使用者主責"}</span><h3>{en ? "Validate, sign, review, and compile into four stores" : "驗證、簽名、驗收，再編譯進四庫"}</h3></div><Lock size={20} /></div>
        <div className="rulebook-condition-grid">
          <section><b>{en ? "Formation" : "成立條件"}</b><p>{compactPublicText(task.scbkr?.R?.formation_conditions || task.scbkr?.B?.formation_conditions || task.scbkr?.R?.basic_formation_conditions, en, 6) || (en ? "The user confirms every layer and signs." : "使用者逐欄確認並簽名後成立。")}</p></section>
          <section><b>{en ? "Invalidation" : "失效條件"}</b><p>{compactPublicText(task.scbkr?.R?.failure_conditions || task.scbkr?.B?.failure_conditions || task.scbkr?.R?.basic_failure_reminders, en, 6) || (en ? "The subject, boundary, basis, or responsibility is missing." : "主體、邊界、依據或責任缺失時失效。")}</p></section>
          <section><b>{en ? "Risk" : "風險標記"}</b><p>{compactPublicText(task.scbkr?.R?.risk_levels || task.scbkr?.R?.basic_risk_reminders, en, 4) || (en ? "Publishing, storage, and tool execution require a signature." : "發布、入庫與工具執行都需要使用者簽名。")}</p></section>
          <section><b>{en ? "Replay" : "回放要求"}</b><p>{compactPublicText(task.scbkr?.R?.replay_requirements, en, 5) || (en ? "Record routing, the rule package, post-check, and storage result." : "記錄路由、規則包、回答後檢查與入庫結果。")}</p></section>
        </div>
        <div className="gate-sequence"><span className={task.confirmed ? "passed" : "current"}>1 {en ? "SIGN" : "簽名"}</span><span className={task.generation_result ? "passed" : task.confirmed ? "current" : ""}>2 {en ? "GENERATE" : "生成"}</span><span className={task.review_passed ? "passed" : task.status === "waiting_review" ? "current" : ""}>3 {en ? "REVIEW" : "驗收"}</span><span className={task.storage_confirmed ? "passed" : task.review_passed ? "current" : ""}>4 {en ? "STORE" : "入庫"}</span></div>
        <label>{en ? "Owner signature" : "使用者簽名"}<input value={ownerSignature} onChange={(e) => setOwnerSignature(e.target.value)} disabled={task.confirmed || taskCompiling} /></label>
        <small>{en ? "The model cannot sign. The user signature unlocks generation, review, and storage." : "模型不能簽名；只有使用者簽名後才能生成、驗收與入庫。"}</small>
        <div className="action-grid">
          {!task.confirmed && <button disabled={taskHardBlocked} onClick={() => void applyCurrentRuleAssist()}><ShieldCheck size={15} />{en ? "Run structure check" : "檢查五維結構"}</button>}
          {!task.confirmed && <button onClick={() => void run(en ? "Save draft" : "儲存草稿", async () => task)}><Save size={15} />{en ? "Save draft" : "儲存草稿"}</button>}
          {!task.confirmed && <button disabled={!ownerSignature.trim() || taskSyncBlocked || taskCompiling} onClick={() => void confirmTask()}><ShieldCheck size={15} />{en ? "Submit signature" : "提交簽名"}</button>}
          {task.status === "confirmed" && <button onClick={() => void generate()}><Bot size={15} />{en ? "Generate" : "開始生成"}</button>}
          {task.status === "waiting_review" && <><button disabled={!ownerSignature.trim()} onClick={() => void review("pass")}><Check size={15} />{en ? "Pass" : "通過驗收"}</button><button className="danger" disabled={!ownerSignature.trim()} onClick={() => void review("fail")}><X size={15} />{en ? "Fail" : "驗收失敗"}</button></>}
        </div>
        {(task.review_passed || task.storage_plan) && <div className="store-select"><div><b>{en ? "Compile into the four stores" : "編譯進四庫"}</b><small>{en ? "LOGIC decides, CORPUS supplies confirmed data, MEMORY supplies task-matched preferences, and VECTOR only recalls candidates." : "LOGIC 負責判斷、CORPUS 保存正式資料、MEMORY 保存任務命中的長期偏好、VECTOR 只做候選召回。"}</small></div>{stores.map((store) => <label key={store.id}><input type="checkbox" checked={selectedStores.includes(store.id)} onChange={() => setSelectedStores((current) => current.includes(store.id) ? current.filter((id) => id !== store.id) : [...current, store.id])} />{store.label}</label>)}<button disabled={!ownerSignature.trim() || selectedStores.length === 0} onClick={() => void commitStores()}><Database size={15} />{en ? "Compile signed rule" : "編譯已簽名規則"}</button></div>}
        {task.generation_result && <div className="output-console"><span>MODEL OUTPUT</span>{human(task.generation_result.content || task.generation_result.generated_text || task.generation_result.output)}</div>}
      </>}
    </section>
  );

  const toolPanel = (
    <section className="workbench-zone tool-zone">
      <div className="zone-title"><div><span>AI ENGINE GATES</span><h2>{en ? "Tool Registry" : "工具註冊與權限"}</h2></div><Wrench size={20} /></div>
      <div className="tool-matrix">{tools.map((tool) => <button key={tool.tool_id} className={selectedTool === tool.tool_id ? "selected" : ""} onClick={() => setSelectedTool(tool.tool_id)}><span>{tool.name}</span><small>{riskLevelLabel(tool.risk_level, en)} · {toolListLabel(tool.capabilities, en, "action")}</small></button>)}</div>
      <div className="gate-console"><label>{en ? "Action" : "動作"}<select value={toolAction} onChange={(e) => setToolAction(e.target.value)}>{["observe", "search", "draft", "execute", "send", "publish", "store"].map((action) => <option key={action} value={action}>{toolActionLabel(action, en)}</option>)}</select></label><label className="toggle-line"><input type="checkbox" checked={toolConfirmed} onChange={(e) => setToolConfirmed(e.target.checked)} />{en ? "Confirm this high-risk call" : "確認本次高風險呼叫"}</label><button onClick={() => void evaluateTool()}><ShieldCheck size={15} />{en ? "Evaluate gates" : "檢查五道權限閘"}</button></div>
      {toolResult && <div className={`tool-result ${toolResult.allowed ? "allowed" : "blocked"}`}><b>{toolResult.allowed ? (en ? "AUTHORIZED" : "已授權") : (en ? "BLOCKED" : "已擋下")}</b><span>{toolResult.reason}</span><small>{toolExecutionStatusLabel(toolResult.execution_status, en)}</small></div>}
    </section>
  );

  const selectedRuleData = rules.find((rule) => rule.rule_id === selectedRule);
  const ruleManagePanel = view === "rules" && ruleManageOpen && selectedRuleData ? (
    <aside className="rule-manager-drawer" aria-label={en ? "Rule lifecycle manager" : "規則版本與生命週期"}>
      <header><div><span>{en ? "RULE LIFECYCLE" : "規則生命週期"}</span><h2>{selectedRuleData.rule_name}</h2></div><button className="icon-button" onClick={() => setRuleManageOpen(false)} title={en ? "Close" : "關閉"}><X size={16} /></button></header>
      <div className="lifecycle-current"><span>{en ? "Current status" : "目前狀態"}</span><b>{readableStatus(selectedRuleData.activation_status || "draft", en)}</b><small>{selectedRuleData.rule_version}</small></div>
      <section><div className="drawer-section-title"><GitBranch size={17} /><div><b>{en ? "Create a new version" : "建立新版"}</b><small>{en ? "The old version remains active until the new one is signed, reviewed, and stored." : "新版完成簽名、驗收與入庫前，舊版仍維持原狀。"}</small></div></div><label>{en ? "What should change?" : "你要改什麼？"}<textarea value={revisionInstruction} onChange={(event) => setRevisionInstruction(event.target.value)} placeholder={en ? "Example: Add a stop condition when the amount cannot be verified." : "例如：金額無法確認時必須停止，並要求補資料。"} /></label><button disabled={!revisionInstruction.trim()} onClick={() => void createRuleRevision()}><GitBranch size={15} />{en ? "Ask model to draft vNext" : "請模型草擬新版確認單"}</button></section>
      <section className="danger-zone"><div className="drawer-section-title"><ShieldCheck size={17} /><div><b>{en ? "Disable, archive, or delete" : "停用、封存或刪除"}</b><small>{en ? "These actions never erase replay. A deleted rule becomes a tombstone and cannot be cited." : "這些動作不會抹掉回放；刪除後只保留不可引用的紀錄。"}</small></div></div><label>{en ? "Reason" : "原因"}<input value={lifecycleReason} onChange={(event) => setLifecycleReason(event.target.value)} placeholder={en ? "Why are you changing this rule?" : "為什麼要變更這條規則？"} /></label><label>{en ? "Your signature" : "使用者簽名"}<input value={ruleSignature} onChange={(event) => setRuleSignature(event.target.value)} placeholder={en ? "The model cannot sign" : "模型不能代簽"} /></label><label className="toggle-line"><input type="checkbox" checked={lifecycleConfirmed} onChange={(event) => setLifecycleConfirmed(event.target.checked)} />{en ? "I confirm this lifecycle change and understand replay is retained." : "我二次確認本次變更，並知道回放紀錄會保留。"}</label><div className="lifecycle-actions"><button disabled={!ruleSignature.trim() || !lifecycleConfirmed || selectedRuleData.activation_status === "disabled"} onClick={() => void changeSelectedRuleLifecycle("disable")}><Power size={15} />{en ? "Disable" : "停用"}</button><button disabled={!ruleSignature.trim() || !lifecycleConfirmed || selectedRuleData.activation_status === "archived"} onClick={() => void changeSelectedRuleLifecycle("archive")}><Archive size={15} />{en ? "Archive" : "封存"}</button><button className="danger" disabled={!ruleSignature.trim() || !lifecycleConfirmed || selectedRuleData.activation_status === "deleted"} onClick={() => void changeSelectedRuleLifecycle("delete")}><Trash2 size={15} />{en ? "Delete" : "刪除"}</button></div></section>
    </aside>
  ) : null;
  const dataDock = <>{view === "rules" && selectedRuleData && <button className="rule-manager-trigger" onClick={() => { setTourOpen(false); setRuleManageOpen(true); }} title={en ? "Manage selected rule" : "管理選取規則"}><SlidersHorizontal size={18} /><span>{en ? "Manage rule" : "管理規則"}</span></button>}<button className="tour-trigger" onClick={() => { setRuleManageOpen(false); setTourStep(0); setTourOpen(true); }} title={en ? "Open guided tour" : "開啟導覽"}><CircleHelp size={19} /></button>{ruleManagePanel}{tourPanel}<footer className="data-dock">{stores.map((store) => { const Icon = store.icon; return <button key={store.id} onClick={() => setView("data")}><Icon size={17} /><span>{store.label}</span><b>{store.count}</b></button>; })}<button onClick={() => setView("tools")}><Activity size={17} /><span>{en ? "Traces" : "執行回放"}</span><b>{traces.length}</b></button></footer></>;

  const selectedToolData = tools.find((tool) => tool.tool_id === selectedTool);
  const pendingTasks = tasks.filter((item) => !["completed", "storage_committed"].includes(item.status)).slice(0, 12);

  const commandPage = <div className="workspace-page command-workspace premium-dashboard"><div className="dashboard-grid"><section className="dashboard-main">{chatPanel}</section><aside className="dashboard-context"><section className={`ops-panel command-model-panel ${modelReady ? "ready" : "blocked"}`}><header>{modelReady ? <CheckCircle2 size={20} /> : <AlertTriangle size={20} />}<div><span>{en ? "MODEL" : "模型狀態"}</span><h2>{modelReady ? (currentModelName || (en ? "Connected" : "已連線")) : (en ? "Connection required" : "需要連接模型")}</h2></div></header><p>{modelReady ? (en ? "Ready for chat and model-assisted SCBKR authoring." : "可進行一般聊天與模型協作 SCBKR 草擬。") : (en ? "Connect and test LM Studio, Ollama, or an OpenAI-compatible endpoint." : "請連接並測試 LM Studio、Ollama 或 OpenAI-compatible API。")}</p><button onClick={() => setView("model")}><Settings size={15} />{en ? "Model settings" : "模型設定"}</button></section>{activeRulePanel}{tokenAuditPanel}<section className="ops-panel pending-panel"><header><FileKey size={20} /><div><span>{en ? "DRAFTS" : "確認單"}</span><h2>{en ? "Pending review" : "等待你處理"}</h2></div></header><div className="activity-list">{pendingTasks.length === 0 && <div className="empty-state">{en ? "No pending drafts" : "目前沒有待確認草稿"}</div>}{pendingTasks.slice(0, 4).map((item) => <button key={item.task_id} onClick={() => void openTask(item.task_id)}><span className="state-dot waiting_owner_signature" /><div><b>{item.task_name}</b><small>{readableStatus(item.status, en)}</small></div><ChevronRight size={15} /></button>)}</div></section></aside>{toolLauncher}</div></div>;

  const rulesPage = (
    <div className="workspace-page split-workspace rules-workspace product-rules">
      <div className="workspace-primary">{rulePanel}</div>
      <main className="rule-detail-surface">
        {selectedRuleData ? <>
          <div className="page-head inline">
            <div>
              <span>{en ? "RULE CENTER" : "SCBKR 規則中心"}</span>
              <h1>{selectedRuleData.rule_name}</h1>
              <small>{ruleSourceLabel(selectedRuleData.rule_source, en)} / {ruleAuthorLabel(selectedRuleData.rule_author, en)} / {selectedRuleData.rule_version}</small>
            </div>
            <div className="tag-row">
              <b className={selectedRuleData.activation_status}>{readableStatus(selectedRuleData.activation_status, en)}</b>
              <b>{en ? "Free edition" : "免費版"}</b>
              {(selectedRuleData.four_store_locations || ["logic"]).map((store: string) => <b key={store}>{storeDisplayMetadata(store, "active", en).label}</b>)}
            </div>
          </div>
          <section className="rule-main-card">
            <p>{ruleOverview(selectedRuleData, en)}</p>
            <div className="dimension-summary compact">{dims.map((dim) => <div key={dim}><b>{dim}｜{copy.dimensions[dim]}</b><span>{dimensionDraftText(selectedRuleData.scbkr_summary?.[dim] || {}, dim, en) || (en ? "No summary yet." : "尚無摘要。")}</span></div>)}</div>
          </section>
          <div className="rulebook-condition-grid">
            <section><b>{en ? "Formation" : "成立條件"}</b><p>{compactPublicText(selectedRuleData.compiled_rule?.execution_logic?.formation_conditions, en, 6) || (en ? "The rule is enabled after user signature and review." : "由使用者完成簽名與驗收，並啟用規則後成立。")}</p></section>
            <section><b>{en ? "Invalidation" : "失效條件"}</b><p>{compactPublicText(selectedRuleData.compiled_rule?.execution_logic?.failure_conditions, en, 6) || (en ? "The rule is invalid when disabled, archived, superseded, unsigned, or review fails." : "規則被停用、封存、新版取代、未簽名或驗收失敗時失效。")}</p></section>
            <section><b>{en ? "Risk" : "風險"}</b><p>{riskLevelLabel(selectedRuleData.risk_level, en)}</p></section>
            <section><b>{en ? "Replay" : "回放"}</b><p>{compactPublicText(selectedRuleData.compiled_rule?.execution_logic?.replay_requirements, en, 5) || (en ? "Keep rule version, signature, review, and storage history." : "保留規則版本、簽名、驗收與入庫紀錄。")}</p></section>
          </div>
          <section className="version-table">
            <h2>{en ? "Version history" : "版本紀錄"}</h2>
            {(selectedRuleData.version_history || [{ version: selectedRuleData.rule_version, status: selectedRuleData.activation_status, note: selectedRuleData.changelog?.[0] }]).map((item: any) => <div key={`${item.version}-${item.status}`}><b>{item.version}</b><span>{readableStatus(item.status, en)}</span><small>{versionNoteLabel(item.note, en)}</small></div>)}
          </section>
          <section className="citation-strip">
            <b>{en ? "Stored in" : "入庫位置"}</b>
            {(selectedRuleData.four_store_locations || ["logic"]).map((store: string) => <span key={store}>{storeDisplayMetadata(store, "active", en).label}</span>)}
            <em>{en ? "Only enabled, user-signed, and reviewed rules may be cited as formal authority." : "只有已啟用、由使用者簽名且驗收通過的規則，才能作為正式依據。"}</em>
          </section>
        </> : <div className="empty-state">{en ? "Select a rule to inspect details." : "選擇一條規則查看詳情。"}</div>}
      </main>
      <aside className="workspace-inspector rule-side-panel">
        <div className="workspace-heading"><span>{en ? "SIGNATURE" : "簽名狀態"}</span><h2>{selectedRuleData?.signature_status === "owner_signed" ? (en ? "Signed by user" : "使用者已簽名") : (en ? "Waiting for user signature" : "等待使用者簽名")}</h2></div>
        <div className="rule-inspector">
          <div className={`status-banner ${selectedRuleData?.activation_status || ""}`}><span>{readableStatus(selectedRuleData?.activation_status || "draft", en)}</span><b>{selectedRuleData?.review_passed ? (en ? "Review passed" : "驗收通過") : (en ? "Waiting for review" : "等待驗收")}</b></div>
          <dl>
            <div><dt>{en ? "Status" : "啟用狀態"}</dt><dd>{readableStatus(selectedRuleData?.activation_status || "draft", en)}</dd></div>
            <div><dt>{en ? "Storage" : "四庫位置"}</dt><dd>{(selectedRuleData?.four_store_locations || ["logic"]).map((store: string) => storeDisplayMetadata(store, "active", en).label).join("、")}</dd></div>
            <div><dt>{en ? "Citation policy" : "引用限制"}</dt><dd>{en ? "Signed and reviewed source records only. Retrieval candidates are never formal authority." : "只能引用已簽名、已驗收的正式資料；檢索候選不能直接當依據。"}</dd></div>
          </dl>
        </div>
        <div className="quick-actions">
          <button onClick={() => setView("workbench")}><SlidersHorizontal size={15} />{en ? "Open Workbench" : "前往工作台"}</button>
          <button onClick={() => setRuleManageOpen(true)}><GitBranch size={15} />{en ? "Manage version and status" : "管理版本與狀態"}</button>
        </div>
      </aside>
    </div>
  );

  const workbenchPage = <div className="workspace-page workbench-workspace product-workbench"><aside className="task-queue"><div className="workspace-heading"><span>{en ? "LOCAL DRAFTS" : "本機確認單"}</span><h2>{en ? "Rulebooks" : "規則草稿"}</h2></div><button className="new-task" onClick={() => { setTask(null); setTaskInput(""); setPendingPatch(null); }}><Plus size={15} />{en ? "New rulebook" : "新增確認單"}</button><div className="activity-list">{tasks.slice(0, 20).map((item) => <button className={task?.task_id === item.task_id ? "selected" : ""} key={item.task_id} onClick={() => void openTask(item.task_id)}><span className={`state-dot ${item.storage_confirmed ? "active" : item.confirmed ? "review" : "waiting_owner_signature"}`} /><div><b>{item.task_name}</b><small>{readableStatus(item.status, en)}</small></div><ChevronRight size={15} /></button>)}</div></aside><div className="workspace-primary">{workbenchPanel}</div></div>;

  const toolsPage = <div className="workspace-page split-workspace tools-workspace"><div className="workspace-primary">{toolPanel}</div><aside className="workspace-inspector"><div className="workspace-heading"><span>{en ? "TOOL INSPECTOR" : "工具檢視"}</span><h2>{selectedToolData?.name || (en ? "Select a tool" : "選擇工具")}</h2></div>{selectedToolData && <div className="tool-inspector"><div className="status-banner"><span>{riskLevelLabel(selectedToolData.risk_level, en)}</span><b>{en ? "Local permission gate" : "本機權限閘"}</b></div><p>{toolListLabel(selectedToolData.capabilities, en, "action")}</p><dl><div><dt>{en ? "Permissions" : "需要權限"}</dt><dd>{toolListLabel(selectedToolData.required_permissions, en, "permission")}</dd></div><div><dt>{en ? "Actions" : "可用動作"}</dt><dd>{toolListLabel(selectedToolData.allowed_actions, en, "action")}</dd></div></dl></div>}<ContextAssistant en={en} title={en ? "Tool guidance" : "工具協作"} context={selectedToolData ? `Current tool: ${JSON.stringify({ id: selectedToolData.tool_id, risk: selectedToolData.risk_level, capabilities: selectedToolData.capabilities })}. Explain gates and risks without executing the tool.` : "No tool selected."} onAsk={(text) => askWorkspace("TOOLS", text)} /><div className="trace-mini"><h3>{en ? "Recent traces" : "最近回放"}</h3>{traces.slice(0, 6).map((trace) => <div key={trace.trace_id}><span className={`state-dot ${trace.allowed ? "active" : "revoked"}`} /><b>{trace.tool_id}</b><small>{toolActionLabel(trace.action, en)}</small></div>)}</div></aside></div>;

  const dataPage = <section className="full-panel data-center-panel"><div className="page-head"><div><span>LOCAL EVIDENCE PLANE</span><h1>{en ? "Four Stores" : "四庫資料中心"}</h1></div><button onClick={() => void refreshAll()}><RefreshCw size={15} />{en ? "Refresh" : "讀回資料中心"}</button></div><div className="data-reader"><div><span>AUTHORITATIVE STORE READER</span><h2>{en ? "Ask your signed knowledge" : "用人話查詢已簽名資料"}</h2><small>{en ? "The model may only cite signed and reviewed records. VECTOR is recall only." : "模型只能引用已簽名、已驗收的資料；VECTOR 只做召回，不可直接作為 K 依據。"}</small></div><div className="reader-input"><input aria-label={en ? "Search four stores" : "搜尋四庫"} value={dataQuery} onChange={(e) => setDataQuery(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") void readFourStores(); }} placeholder={en ? "Ask a question about your stored rules..." : "例如：我的發布規則要求什麼？"} /><button disabled={!dataQuery.trim()} onClick={() => void readFourStores()}><Search size={16} />{en ? "Search and read" : "搜尋並閱讀"}</button></div>{readResult && <div className={`reader-result ${readResult.citation_count ? "has-evidence" : "empty"}`}><header><b>{readResult.citation_count || 0} {en ? "authoritative citations" : "筆正式引用"}</b><span>{readResult.candidates_excluded || 0} {en ? "candidates excluded" : "筆候選已排除"}</span><em>{readResult.model_called ? (en ? "MODEL READING DRAFT" : "模型閱讀草稿") : (en ? "NO MODEL CLAIM" : "未讓模型無依據作答")}</em></header><p>{readResult.answer}</p>{(readResult.citations || []).map((citation: any, index: number) => <div className="citation-row" key={`${citation.content_hash}-${index}`}><b>{citation.source_store}</b><span>{citation.store_role ? `${citation.store_role} · ` : ""}{citation.rule}</span><code>{String(citation.content_hash || "").slice(0, 12)}</code></div>)}</div>}</div><div className="store-band openable">{stores.map((store) => { const Icon = store.icon; return <button key={store.id} className={dataSection === store.id ? "selected" : ""} onClick={() => void openDataSection(store.id)} aria-label={`${store.label} ${en ? "store" : "資料庫"}`}><Icon /><span>{store.label}</span><strong>{store.count}</strong><small>{store.hint}</small></button>; })}</div><section className="store-browser"><header><div><span>{en ? "OPEN STORE" : "目前打開"}</span><h2>{stores.find((store) => store.id === dataSection)?.label || dataSection}</h2></div><button onClick={() => void openDataSection(dataSection)}><RefreshCw size={15} />{en ? "Reload store" : "重新讀取"}</button></header>{!dataSectionResult && <div className="empty-state">{en ? "Choose LOGIC, CORPUS, MEMORY, or VECTOR to inspect saved records." : "點上面的 LOGIC、CORPUS、MEMORY 或 VECTOR，就能看到實際存入資料。"}</div>}{dataSectionResult && dataSectionResult.count === 0 && <div className="empty-state">{dataSectionResult.empty_message || (en ? "No records in this store." : "這個庫目前沒有資料。")}</div>}{(dataSectionResult?.items || []).map((item: any) => <article className="store-record" key={item.item_id || item.id}><button onClick={() => setExpandedDataItem((current) => current === (item.item_id || item.id) ? "" : (item.item_id || item.id))}><span className={`state-dot ${item.status === "active" ? "active" : "waiting_owner_signature"}`} /><div><b>{item.title || item.item_id}</b><small>{item.store_label || item.target} · {item.store_role || item.status_label || item.status} · v{item.version || 1}</small></div><code>{String(item.content_hash || item.hash || "").slice(0, 12)}</code></button><div className="store-role-note"><b>{item.citation_policy || item.status_label || item.status}</b><span>{item.store_purpose || item.model_reading_hint}</span></div><p>{item.plain_summary || item.summary || item.preview}</p><small>{item.storage_location || item.relative_path}</small>{expandedDataItem === (item.item_id || item.id) && <pre>{item.content_text || JSON.stringify(item.payload || item, null, 2)}</pre>}</article>)}</section><div className="trace-table"><h2>{en ? "Execution traces" : "執行回放"}</h2>{traces.map((trace) => <div key={trace.trace_id}><span className={`state-dot ${trace.allowed ? "active" : "revoked"}`} /><b>{trace.tool_id}</b><span>{trace.action}</span><span>{trace.reason}</span><time>{trace.timestamp}</time></div>)}</div></section>;

  const runtimePage = (
    <section className="full-panel runtime-page">
      <div className="page-head"><div><span>LOCAL RULE RUNTIME</span><h1>{en ? "Rule State" : "規則狀態"}</h1></div><ShieldCheck size={25} /></div>
      <div className="rule-state-hero independent"><div><span>{en ? "PUBLIC EDITION" : "公開版本"}</span><h2>{en ? "Local user rules" : "本機使用者規則"}</h2><p>{en ? "Only rules reviewed and signed by the user can become formal local authority." : "只有經使用者確認與簽名的規則，才能成為本機正式依據。"}</p></div><b>FREE</b></div>
      <div className="runtime-layout">
        <section className="runtime-product">
          <div className="runtime-brand"><ShieldCheck size={32} /><div><span>SCBKR FREE</span><h2>{en ? "Signed-rule runtime" : "簽名規則 Runtime"}</h2></div></div>
          <p>{en ? "The model drafts and explains. The user signs. Signed rules are compiled into the four stores and later answers use a minimal rule package." : "模型負責草擬與解釋，使用者負責簽名；簽名規則會編譯進四庫，後續回答只使用本次最小規則包。"}</p>
          <dl><div><dt>{en ? "Edition" : "版本"}</dt><dd>FREE</dd></div><div><dt>{en ? "Active rules" : "生效規則"}</dt><dd>{activeRules}</dd></div><div><dt>{en ? "Rule packs" : "規則包"}</dt><dd>{packs.length}</dd></div></dl>
          <div className="button-row"><button onClick={() => setView("rules")}><FileKey size={15} />{en ? "Open Rule Center" : "打開規則中心"}</button><button onClick={() => setView("data")}><Database size={15} />{en ? "Open four stores" : "查看四庫"}</button></div>
        </section>
        <div className="runtime-audit-stack">{currentRulePackagePanel}{tokenAuditPanel}</div>
      </div>
    </section>
  );

  const launchChecklistLabels: Record<string, string> = en ? { domain: "Public domain", auth: "Supabase Auth", search: "Web search service", partner: "Microsoft Partner Center", signing: "Code signing", updater: "Tauri update endpoint", legal: "Privacy policy and terms" } : {};
  const launchPage = (
    <section className="full-panel launch-page">
      <div className="page-head"><div><span>PRODUCTION CONTROL PLANE</span><h1>{en ? "Launch Center" : "上線中心"}</h1></div><Rocket size={25} /></div>
      <div className="readiness-head"><div><span>{en ? "STORE READINESS" : "上架準備度"}</span><strong>{readiness.ready_count || 0}/{readiness.total_count || 7}</strong></div><div className="readiness-track"><i style={{ width: `${((readiness.ready_count || 0) / (readiness.total_count || 7)) * 100}%` }} /></div><small>{en ? "Fill in the services you create. Secret server keys never belong in the desktop client." : "你申請好服務後填在這裡；伺服器私鑰永遠不能放進桌面客戶端。"}</small></div>
      <div className="launch-grid">
        <section><div className="integration-title"><Cloud /><div><b>Account & Domain</b><span>Supabase / Public URL</span></div></div><label>{en ? "Public domain" : "正式網域"}<input value={launchSettings.public_domain || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, public_domain: e.target.value })} placeholder="https://scbkr.example" /></label><label>Supabase URL<input value={launchSettings.supabase_url || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, supabase_url: e.target.value })} placeholder="https://project.supabase.co" /></label><label>Supabase publishable key<input type="password" value={launchSettings.supabase_publishable_key || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, supabase_publishable_key: e.target.value })} /></label></section>
        <section><div className="integration-title"><Globe2 /><div><b>Web Search</b><span>SearXNG / Brave Search</span></div></div><label>{en ? "Provider" : "搜尋服務"}<select value={launchSettings.search_provider || "searxng"} onChange={(e) => setLaunchSettings({ ...launchSettings, search_provider: e.target.value })}><option value="searxng">SearXNG</option><option value="brave">Brave Search API</option></select></label>{launchSettings.search_provider === "brave" ? <label>{en ? "Brave runtime credential" : "Brave 後端憑證"}<input disabled value={launchSettings.brave_api_key_configured ? (en ? "Configured" : "已設定") : (en ? "Not configured" : "未設定")} /></label> : <label>SearXNG URL<input value={launchSettings.searxng_url || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, searxng_url: e.target.value })} placeholder="https://search.example" /></label>}<label className="toggle-line"><input type="checkbox" checked={permissions.web_search === true} onChange={(e) => void setWebPermission(e.target.checked)} />{en ? "Allow confirmed web searches" : "允許經使用者確認的網路搜尋"}</label></section>
        <section><div className="integration-title"><KeyRound /><div><b>Windows Distribution</b><span>Partner Center / Signing / Updater</span></div></div><label>Microsoft Partner Product ID<input value={launchSettings.microsoft_partner_product_id || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, microsoft_partner_product_id: e.target.value })} /></label><label>{en ? "Code signing subject" : "程式簽章主體"}<input value={launchSettings.code_signing_subject || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, code_signing_subject: e.target.value })} /></label><label>{en ? "Update endpoint" : "更新端點"}<input value={launchSettings.tauri_update_endpoint || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, tauri_update_endpoint: e.target.value })} /></label></section>
        <section><div className="integration-title"><ShieldCheck /><div><b>Legal & Support</b><span>Privacy / Terms / Contact</span></div></div><label>{en ? "Privacy policy URL" : "隱私政策網址"}<input value={launchSettings.privacy_policy_url || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, privacy_policy_url: e.target.value })} /></label><label>{en ? "Terms URL" : "服務條款網址"}<input value={launchSettings.terms_of_service_url || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, terms_of_service_url: e.target.value })} /></label><label>{en ? "Support email" : "客服信箱"}<input value={launchSettings.support_email || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, support_email: e.target.value })} /></label></section>
        <section className="checklist-panel"><span>LAUNCH CHECKLIST</span>{(readiness.checks || []).map((check: any) => <div key={check.id} className={check.ready ? "ready" : "pending"}><i>{check.ready ? <Check size={13} /> : <X size={13} />}</i><b>{launchChecklistLabels[check.id] || check.label}</b><em>{check.owner_action ? (en ? "OWNER" : "需你申請") : (en ? "ENGINEERING" : "工程")}</em></div>)}</section>
      </div>
      <div className="launch-actions"><button onClick={() => void saveLaunchSettings()}><Save size={16} />{en ? "Save launch configuration" : "儲存上線設定"}</button><span>{readiness.ready_for_store_submission ? (en ? "Ready for store submission" : "已具備送審條件") : (en ? "Missing external accounts or release materials" : "仍缺外部帳號或發布資料")}</span></div>
    </section>
  );

  const modelPage = <section className="full-panel model-settings"><div className="page-head"><div><span>{en ? "RUNTIME CONNECTION" : "模型與裝置連線"}</span><h1>{en ? "Model Settings" : "模型設定"}</h1></div><Bot /></div><div className="settings-grid"><section><h2>{en ? "Desktop / phone connection" : "桌機 / 手機連線"}</h2><div className={`companion-state ${companion?.lan_companion_enabled ? "on" : "off"}`}><span>{en ? "Phone connection" : "手機連線"}</span><b>{companion?.lan_companion_enabled ? copy.common.online : copy.common.offline}</b><small>{companion?.base_url || backend} · {companion?.active_devices || 0} {en ? "devices" : "台裝置"}</small></div><label>{en ? "Local service address" : "本機服務位址"}<input value={backend} onChange={(e) => setBackend(e.target.value)} /></label><label>{en ? "Phone connection token" : "手機連線權杖"}<input type="password" value={tokenInput} onChange={(e) => setTokenInput(e.target.value)} /></label><div className="button-row"><button onClick={saveConnection}><Network size={15} />{en ? "Connect" : "儲存並連線"}</button><button disabled={!companion?.lan_companion_enabled} onClick={() => void startPairing()}><FileKey size={15} />{en ? "Pair code" : "取得配對碼"}</button><button disabled={!companion?.active_devices} onClick={() => void revokeCompanions()}><X size={15} />{en ? "Revoke" : "撤銷裝置"}</button></div>{pairing && <div className="pairing-code"><span>{en ? "PAIRING CODE" : "手機配對碼"}</span><strong>{pairing.pairing_code}</strong><small>{pairing.base_url}</small><time>{pairing.expires_at}</time></div>}</section><section><h2>{en ? "Language model" : "語言模型"}</h2><div className={`model-permission-card ${permissions.model_generate === true ? "on" : "off"}`}><span>{en ? "Generation permission" : "模型生成權限"}</span><b>{modelReady ? (en ? "Ready" : "可使用") : permissions.model_generate === true ? (en ? "Granted; model not connected" : "已授權，等待模型連線") : (en ? "Not granted" : "尚未授權")}</b><small>{modelReady ? (en ? "Model tested and ready" : "模型已測試，可以進入聊天與規則草擬") : (en ? "Save the connection and run the model test." : "請儲存模型設定並完成連線測試。")}</small></div><label>{en ? "Connection type" : "連線類型"}<select value={modelForm.provider} onChange={(e) => updateModelProvider(e.target.value)}><option value="lm_studio">LM Studio</option><option value="ollama">Ollama</option><option value="openai_compatible">OpenAI-compatible</option></select></label><label>{en ? "Service address" : "模型服務位址"}<input value={modelForm.base_url} onChange={(e) => setModelForm({ ...modelForm, base_url: e.target.value })} /></label><label>{en ? "Model name" : "模型名稱"}<input value={modelForm.model_name} onChange={(e) => setModelForm({ ...modelForm, model_name: e.target.value })} /></label><label>API Key<input type="password" value={modelForm.api_key} onChange={(e) => setModelForm({ ...modelForm, api_key: e.target.value })} placeholder={en ? "Leave blank to keep the saved API key." : "留白會保留已儲存金鑰"} /></label><div className="button-row"><button onClick={() => void saveModel()}><Save size={15} />{en ? "Save" : "儲存設定"}</button><button onClick={() => void testModel()}><Activity size={15} />{en ? "Test connection" : "測試模型連線"}</button><button onClick={() => void setModelGeneratePermission(permissions.model_generate !== true)}><Bot size={15} />{permissions.model_generate === true ? (en ? "Disable generation permission" : "關閉模型生成權限") : (en ? "Enable generation permission" : "開啟模型生成權限")}</button><button onClick={() => void clearModelApiKey()}><KeyRound size={15} />{en ? "Clear API Key" : "清除 API Key"}</button></div></section></div><section className="pricing-settings"><div className="settings-section-heading"><div><span>{en ? "COST TRANSPARENCY" : "成本透明"}</span><h2>{en ? "Token price snapshot" : "Token 價格快照"}</h2></div><CircleGauge size={20} /></div><p>{en ? "Provider usage is measured from the response. Add a price snapshot only when you want an estimated cloud bill; local runtime stays API-charge free." : "用量以模型回傳的實際 usage 為準。只有你要看雲端帳單估算時才填價格；本地模型不產生 API 費用。"}</p><div className="pricing-fields"><label>{en ? "Currency" : "幣別"}<input value={pricing.currency || "USD"} onChange={(e) => setPricing({ ...pricing, currency: e.target.value.toUpperCase() })} /></label><label>{en ? "Input / 1M tokens" : "輸入 / 每百萬 token"}<input inputMode="decimal" value={pricing.input_per_million ?? ""} onChange={(e) => setPricing({ ...pricing, input_per_million: e.target.value })} placeholder="e.g. 0.15" /></label><label>{en ? "Output / 1M tokens" : "輸出 / 每百萬 token"}<input inputMode="decimal" value={pricing.output_per_million ?? ""} onChange={(e) => setPricing({ ...pricing, output_per_million: e.target.value })} placeholder="e.g. 0.60" /></label><label>{en ? "Price source" : "價格來源"}<input value={pricing.source === "not_configured" ? "" : (pricing.source || "")} onChange={(e) => setPricing({ ...pricing, source: e.target.value })} placeholder={en ? "Provider pricing page" : "模型供應商價格頁"} /></label></div><div className="button-row"><button onClick={() => void savePricing()}><Save size={16} />{en ? "Save price snapshot" : "儲存價格快照"}</button><span className="settings-note">{pricing.updated_at ? `${en ? "Updated" : "更新於"} ${pricing.updated_at}` : (en ? "No price snapshot yet" : "尚未設定價格快照")}</span></div></section></section>;

  const aboutPage = <section className="full-panel about-panel"><div className="about-mark">SCBKR<span>2.3</span></div><h1>{manifest?.name || copy.product.name}</h1><p className="about-tagline">{manifest?.tagline || copy.product.category}</p><dl><div><dt>{en ? "Author" : "作者"}</dt><dd>{manifest?.creator?.name || "許文耀 / 沈耀888π"}</dd></div><div><dt>{en ? "Organization" : "組織"}</dt><dd>{manifest?.creator?.organization || "語意防火牆"}</dd></div><div><dt>{en ? "Contact" : "合作聯絡"}</dt><dd>{manifest?.creator?.contact_email || "ken0963521@gmail.com"}</dd></div><div><dt>{en ? "Runtime" : "運行定位"}</dt><dd>{manifest?.runtime_relationship || "Local rule-driven AI control layer"}</dd></div></dl></section>;

  const morePage = <section className="full-panel more-page"><div className="page-head"><div><span>OPERATIONS</span><h1>{en ? "More" : "更多功能"}</h1></div><Menu /></div><div className="more-grid">{nav.filter((item) => ["tools", "runtime", "model", "launch", "about"].includes(item.id)).map(({ id, label, icon: Icon }) => <button key={id} onClick={() => setView(id)}><Icon size={23} /><b>{label}</b><ChevronRight size={16} /></button>)}</div></section>;

  const primaryPage = view === "rules" ? rulesPage : view === "workbench" ? workbenchPage : view === "tools" ? toolsPage : commandPage;
  const standalonePage = view === "data" ? dataPage : view === "runtime" ? runtimePage : view === "model" ? modelPage : view === "launch" ? launchPage : view === "about" ? aboutPage : view === "more" ? morePage : null;

  if (pairingRequired) return <main className="pair-gate"><div className="pair-stars" /><section><div className="pair-mark"><ShieldCheck size={30} /><span>SCBKR 2.3</span></div><p>SECURE MOBILE COMPANION</p><h1>{en ? "Pair this phone" : "配對這支手機"}</h1><small>{en ? "Enter the one-time code shown on your desktop. The code expires after 10 minutes." : "輸入桌機顯示的一次性配對碼，配對碼 10 分鐘後失效。"}</small><label>{en ? "Pairing code" : "6 位數配對碼"}<input inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={pairCode} onChange={(event) => setPairCode(event.target.value.replace(/\D/g, "").slice(0, 6))} onKeyDown={(event) => { if (event.key === "Enter") void redeemPairingCode(); }} placeholder="000000" /></label>{pairError && <div className="pair-error">{pairError}</div>}<button disabled={pairCode.length !== 6} onClick={() => void redeemPairingCode()}><FileKey size={17} />{en ? "Pair securely" : "安全配對"}</button><button className="pair-language" onClick={switchLocale}><Languages size={15} />{en ? "繁體中文" : "English"}</button><footer>{backend}</footer></section></main>;

  return <main className="app-shell v2-shell"><aside className="side-nav"><div className="brand-lockup"><Box size={24} /><div><b>SCBKR</b><span>{en ? "Local Rule OS" : "本地規則 OS"}</span></div></div>{nav.map(({ id, label, icon: Icon }) => <button key={id} className={view === id ? "active" : ""} onClick={() => setView(id)} title={label}><Icon size={18} /><span>{label}</span></button>)}<button className="new-chat-button" onClick={() => { setView("command"); setCommandMode("chat"); setChatInput(""); }}><Plus size={18} /><span>{en ? "New chat" : "新增對話"}</span></button><div className="recent-block"><span>{en ? "Recent" : "最近對話"}</span>{tasks.slice(0, 5).map((item) => <button key={item.task_id} onClick={() => void openTask(item.task_id)}><MessageSquare size={14} /><small>{item.task_name}</small></button>)}</div><div className="account-card"><b>U</b><span>{copy.common.owner}<small>{copy.common.personal}</small></span></div><button onClick={switchLocale} title={en ? "Switch language" : "切換語言"}><Languages size={18} /><span>{locale === "en" ? "繁中" : "EN"}</span></button></aside><nav className="mobile-drawer">{mobileNav.map(({ id, label, icon: Icon }) => <button key={id} className={view === id ? "active" : ""} onClick={() => setView(id)}><Icon size={18} /><span>{label}</span></button>)}</nav><header className="top-status-bar"><button className="mobile-menu icon-button" onClick={() => setView("command")} title={en ? "Open chat" : "回到聊天"}><Menu size={18} /></button><span className={`system-signal ${health}`}><i />{en ? "Local service" : "本機服務"} {health === "online" ? copy.common.online : health === "offline" ? copy.common.offline : copy.common.syncing}</span><span>{copy.common.freeEdition}</span><span>{en ? "Active rules" : "生效規則"} {activeRules}</span><span>{en ? "Stored records" : "四庫紀錄"} {Number(overview.logic_count || 0) + Number(overview.corpus_count || 0) + Number(overview.memory_count || 0) + Number(overview.vector_count || 0)}</span><button className="locale-button" onClick={switchLocale}><Globe2 size={14} />{locale}</button><em>{notice}</em></header><div className="desktop-stage">{!isMobile && (standalonePage || primaryPage)}</div><div className="mobile-stage">{isMobile && (standalonePage || primaryPage)}</div>{dataDock}</main>;
}
