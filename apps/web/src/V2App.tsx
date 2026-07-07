import { useEffect, useRef, useState } from "react";
import {
  Activity, Archive, Bot, Box, Braces, Check, ChevronRight, CircleGauge,
  Cloud, CreditCard, Crown, Database, Eye, FileKey, FolderOpen, Globe2, HardDrive, Info, KeyRound, Languages, Lock, Mail, Menu, MessageSquare,
  Monitor, Network, Play, Plus, RefreshCw, Save, Search, Send, Settings, ShieldCheck,
  SlidersHorizontal, Smartphone, Sparkles, SquareTerminal, Rocket, Wrench, X, AlertTriangle, BrainCircuit, CheckCircle2, Wifi,
} from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { getMessages, normalizeLocale, type Locale } from "./i18n";
import { isLoopbackHostname, resolveApiBaseUrl } from "./apiBase";
import type { ModelSettings, ScbkrDimensionKey, TaskSummary } from "./types";

const TOKEN_KEY = "scbkr.companionToken";
const BACKEND_KEY = "scbkr.activeBackendUrl";
const LOCALE_KEY = "scbkr.locale";
const dims: ScbkrDimensionKey[] = ["S", "C", "B", "K", "R"];
const dimColor: Record<ScbkrDimensionKey, string> = { S: "blue", C: "cyan", B: "yellow", K: "red", R: "green" };
const dimensionNames: Record<ScbkrDimensionKey, { zh: string; en: string }> = {
  S: { zh: "這件事是什麼", en: "What this is" },
  C: { zh: "流程與原因", en: "Flow and reasons" },
  B: { zh: "界線與禁止事項", en: "Boundaries" },
  K: { zh: "依據與引用", en: "Basis and citations" },
  R: { zh: "責任與驗收", en: "Responsibility" },
};

type View = "command" | "rules" | "workbench" | "tools" | "data" | "runtime" | "model" | "launch" | "about" | "more";
type CommandMode = "chat" | "web" | "search" | "rule";
type Rule = Record<string, any>;
type Tool = Record<string, any>;
type WorkflowCard = {
  id: string;
  kind: "suggestion" | "task" | "rule";
  title: string;
  summary: string;
  state: string;
  taskId?: string;
  ruleId?: string;
  objectType?: string;
  suggestedStores?: string[];
  suggestion?: Record<string, any>;
};
type ChatMessage = { role: "user" | "assistant"; content: string; card?: WorkflowCard };
type RuleAssistStatus = {
  plan_level?: "FREE" | "NT690" | "NT3300" | string;
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

function fieldTitle(key: string, en: boolean) {
  const labels: Record<string, [string, string]> = {
    task_subject: ["任務主體", "Subject"], user_instruction: ["使用者原句", "Owner request"], output_format: ["預期輸出", "Expected output"],
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
  const labels: Record<string, [string, string]> = {
    model_compiled: ["模型已補寫表單", "Model filled the form"],
    base_logic_after_model: ["模型嘗試失敗，已用後端基礎邏輯補表", "Model failed; backend base logic filled it"],
    base_logic: ["後端基礎邏輯補表", "Backend base logic filled it"],
  };
  return labels[String(status || "base_logic")]?.[en ? 1 : 0] || String(status || "base_logic");
}

function readableStatus(status: string, en: boolean) {
  const labels: Record<string, [string, string]> = {
    draft: ["草案", "Draft"],
    confirmed: ["已簽名", "Signed"],
    generating: ["生成中", "Generating"],
    waiting_review: ["待驗收", "Review"],
    completed: ["已完成", "Done"],
    storage_committed: ["已入庫", "Stored"],
  };
  return labels[String(status || "draft").toLowerCase()]?.[en ? 1 : 0] || String(status || "draft").replace(/_/g, " ");
}

function RuleFlowSurface({
  en,
  status,
  activeRules,
  citations,
  tokensAvoided,
  planLevel,
}: {
  en: boolean;
  status: string;
  activeRules: number;
  citations: number;
  tokensAvoided: number;
  planLevel: string;
}) {
  const steps = [
    { icon: MessageSquare, label: en ? "Intake" : "一句話入口", value: en ? "Ready" : "就緒", state: "active" },
    { icon: Search, label: en ? "Route" : "自動分流", value: en ? "Chat / stores / rule" : "對話／四庫／規則", state: "active" },
    { icon: FileKey, label: en ? "Draft" : "待簽名草案", value: readableStatus(status, en), state: status === "draft" ? "wait" : "active" },
    { icon: Database, label: en ? "Citations" : "四庫引用", value: String(citations), state: citations > 0 ? "active" : "wait" },
  ];
  return (
    <section className="plain-rule-surface" aria-label={en ? "Natural language routing" : "自然語言納編狀態"}>
      <div className="flow-summary">
        <div>
          <span>RULE ROUTER</span>
          <strong>{en ? "One-line workbench" : "一句話工作台"}</strong>
        </div>
        <div className="scbkr-rail" aria-label="SCBKR">
          {dims.map((dim) => <i key={dim} className={dimColor[dim]}>{dim}</i>)}
        </div>
      </div>
      <div className="flow-steps">
        {steps.map(({ icon: Icon, label, value, state }) => (
          <span key={label} className={state}>
            <Icon size={16} />
            <b>{label}</b>
            <small>{value}</small>
          </span>
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
  const [isMobile, setIsMobile] = useState(() => window.matchMedia("(max-width: 820px)").matches);
  const [health, setHealth] = useState("checking");
  const [backend, setBackend] = useState(initialBackend());
  const [tokenInput, setTokenInput] = useState(localStorage.getItem(TOKEN_KEY) || "");
  const [pairCode, setPairCode] = useState("");
  const [pairError, setPairError] = useState("");
  const [pairingRequired, setPairingRequired] = useState(
    () => !isLoopbackHostname(location.hostname) && !localStorage.getItem(TOKEN_KEY),
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
  const [tokenMetrics, setTokenMetrics] = useState<Record<string, any>>({});
  const [ruleState, setRuleState] = useState<Record<string, any>>({ state: "independent", effective_label: "獨立使用者規則" });
  const [ruleAssist, setRuleAssist] = useState<RuleAssistStatus>({ plan_level: "FREE", locale: "zh-TW" });
  const [runtimeCatalog, setRuntimeCatalog] = useState<Record<string, any>[]>([]);
  const [launchSettings, setLaunchSettings] = useState<Record<string, any>>({});
  const [readiness, setReadiness] = useState<Record<string, any>>({ checks: [] });
  const [permissions, setPermissions] = useState<Record<string, any>>({});
  const [notice, setNotice] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: en ? "SCBKR local runtime ready." : "SCBKR 本機責任核心已就緒。" },
  ]);
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
  const [runtimeMode, setRuntimeMode] = useState("black_shield_strict");
  const [runtimeSignature, setRuntimeSignature] = useState("");
  const [taskInput, setTaskInput] = useState("");
  const [task, setTask] = useState<TaskSummary | null>(null);
  const [ownerSignature, setOwnerSignature] = useState("");
  const [patchLayer, setPatchLayer] = useState<ScbkrDimensionKey>("B");
  const [patchInstruction, setPatchInstruction] = useState("");
  const [pendingPatch, setPendingPatch] = useState<Record<string, any> | null>(null);
  const [selectedStores, setSelectedStores] = useState(["vector", "logic"]);
  const [ruleForm, setRuleForm] = useState({ name: "", keywords: "", tools: "", action: "draft" });
  const [ruleSignature, setRuleSignature] = useState("");
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
      try { throw new Error(JSON.parse(body).detail || body); } catch (error) { if (error instanceof SyntaxError) throw new Error(body); throw error; }
    }
    return response.json() as Promise<T>;
  }

  async function run<T>(label: string, operation: () => Promise<T>): Promise<T | null> {
    try {
      const result = await operation();
      setNotice(`${label} · ${en ? "done" : "完成"}`);
      return result;
    } catch (error) {
      setNotice(`${label} · ${String(error).replace("Error: ", "")}`);
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

  async function refreshAll() {
    if (pairingRequired) return;
    const result = await run(en ? "Refresh runtime" : "更新系統", async () => {
      const [healthData, modelData, manifestData, companionData, ruleData, packData, toolData, traceData, taskData, overviewData, tokenData, ruleStateData, ruleAssistData, runtimeData, launchData, readinessData, permissionData] = await Promise.all([
        api<any>("/health"), api<ModelSettings>("/api/settings/model"), api<any>(`/api/product/manifest?locale=${locale}`),
        api<any>("/api/companion/status"),
        api<any>("/api/rules"), api<any>("/api/rulepacks"), api<any>("/api/tools"), api<any>("/api/tools/traces?limit=20"), api<any>("/api/tasks"), api<any>("/api/data-center/overview"), api<any>("/api/metrics/token-efficiency"),
        api<any>("/api/rule-state/status"), api<any>(`/api/rule-assist/status?locale=${locale}`), api<any>("/api/rule-state/catalog"), api<any>("/api/launch/settings"), api<any>("/api/launch/readiness"), api<any>("/api/settings/permissions"),
      ]);
      return { healthData, modelData, manifestData, companionData, ruleData, packData, toolData, traceData, taskData, overviewData, tokenData, ruleStateData, ruleAssistData, runtimeData, launchData, readinessData, permissionData };
    });
    if (!result) { setHealth("offline"); return; }
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
    setTokenMetrics(result.tokenData || {});
    setRuleState(result.ruleStateData || {});
    setRuleAssist(result.ruleAssistData || { plan_level: "FREE", locale: locale });
    setMessages((current) => current.length === 1 && (current[0].content.includes("runtime ready") || current[0].content.includes("本機責任核心已就緒"))
      ? [{ role: "assistant", content: assistantEnvelope(en ? "Local runtime ready." : "本機 Runtime 已就緒。", result.ruleStateData || {}) }]
      : current);
    setRuntimeCatalog(result.runtimeData.runtimes || []);
    setLaunchSettings(result.launchData || {});
    setReadiness(result.readinessData || { checks: [] });
    setPermissions(result.permissionData || {});
    setModelForm((current) => ({ ...current, ...result.modelData, api_key: "" }));
  }

  useEffect(() => { void refreshAll(); }, [backend, locale, pairingRequired]);
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
      if (result) setMessages((current) => [...current, { role: "assistant", content: assistantEnvelope(result.answer, result.rule_state || ruleState) }]);
      return;
    }
    if (commandMode === "rule") {
      const result = await createNaturalRule(text);
      if (result) {
        setMessages((current) => [...current, { role: "assistant", content: assistantEnvelope(en ? "An unsigned rule draft is ready." : "未簽名規則草案已建立。", result.rule_state || ruleState), card: ruleCard(result) }]);
      }
      return;
    }
    const routed = await run(en ? "Route request" : "判斷任務", () => api<any>("/api/chat/intent", { method: "POST", body: JSON.stringify({ message: text, locale: replyLocale }) }));
    if (!routed) return;
    if (routed.intent === "create_new_rule_confirmation") {
      const drafted = await createNaturalRule(text);
      if (drafted) setMessages((current) => [...current, { role: "assistant", content: assistantEnvelope(en ? "I created an unsigned rule draft. You remain the only signer and activator." : "我已建立未簽名規則草案。只有你能簽名與啟用。", drafted.rule_state || ruleState), card: ruleCard(drafted) }]);
      return;
    }
    if (routed.intent === "create_confirmation") {
      setTaskInput(text);
      const created = await createTask(text, false, routed.intent, routed.draft_object_type || "task");
      if (created) setMessages((current) => [...current, { role: "assistant", content: assistantEnvelope(en ? "Draft compiled. It is waiting for your review." : "草案已編譯，正在等待你檢查。"), card: taskCard(created) }]);
      return;
    }
    if (routed.intent === "data_center_query") {
      const result = await readFourStores(text);
      if (result) setMessages((current) => [...current, { role: "assistant", content: assistantEnvelope(result.answer, result.rule_state || ruleState) }]);
      return;
    }
    const reply = await run(en ? "Chat" : "模型回覆", () => api<any>("/api/chat/general", { method: "POST", body: JSON.stringify({ message: text, locale: replyLocale }) }));
    if (reply) {
      const suggestion = routed.suggestion || reply.suggestion;
      setMessages((current) => [...current, { role: "assistant", content: reply.reply, card: suggestion ? suggestionCard(suggestion, text) : undefined }]);
    }
  }

  async function createTask(input = taskInput, navigate = true, intent = "create_confirmation", objectType = "task") {
    if (!input.trim()) { setNotice(en ? "Task input required" : "請輸入任務內容"); return; }
    const created = await run(en ? "Compile draft" : "編譯草案", () => api<TaskSummary>("/api/tasks/create", { method: "POST", body: JSON.stringify({ raw_input: input.trim(), task_type: "general", intent, object_type: objectType, create_scbkr_draft: true, locale: replyLocale, rule_assist_plan: planLevel }) }));
    if (created) { setTask(created); setOwnerSignature(""); setTasks((current) => [created, ...current.filter((item) => item.task_id !== created.task_id)]); if (navigate) setView("workbench"); }
    return created;
  }

  function syncTask(updated: TaskSummary) {
    setTask(updated);
    setTasks((current) => [updated, ...current.filter((item) => item.task_id !== updated.task_id)]);
    setPendingPatch(null);
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
    if (!task) return;
    const reviewed = await run(en ? "Review output" : "驗收輸出", () => api<TaskSummary>(`/api/tasks/${task.task_id}/review`, { method: "POST", body: JSON.stringify({ review_decision: decision, review_message: decision === "pass" ? "Owner accepted" : "Owner rejected", reviewer_signature: ownerSignature || "owner" }) }));
    if (reviewed) syncTask(reviewed);
  }

  async function commitStores() {
    if (!task || !ownerSignature.trim()) return;
    let current = task;
    if (!current.storage_plan) {
      const requested = await run(en ? "Create storage plan" : "建立入庫計畫", () => api<TaskSummary>(`/api/tasks/${current.task_id}/storage-request`, { method: "POST", body: JSON.stringify({ selected_targets: selectedStores, user_decision: "custom", signature: ownerSignature }) }));
      if (!requested) return;
      current = requested;
    }
    const committed = await run(en ? "Commit four stores" : "二次確認入庫", () => api<TaskSummary>(`/api/tasks/${current.task_id}/storage-confirm`, { method: "POST", body: JSON.stringify({ storage_confirmed: true, second_confirm: true, confirmed_by: "user", signature: ownerSignature, selected_targets: selectedStores }) }));
    if (committed) { syncTask(committed); void refreshAll(); }
  }

  async function createRule() {
    const payload = {
      rule_name: ruleForm.name,
      rule_text: ruleForm.name,
      rule_author: manifest?.creator?.name || "Owner",
      rule_source: "user_defined",
      rule_version: "v1.0.0",
      rule_scope: { task_types: ["*"], tools: ruleForm.tools.split(",").map((x) => x.trim()).filter(Boolean), workflows: ["*"], keywords: ruleForm.keywords.split(",").map((x) => x.trim()).filter(Boolean), actions: [ruleForm.action] },
      allowed_tools: ruleForm.tools.split(",").map((x) => x.trim()).filter(Boolean), denied_tools: [], automation_level: "manual", risk_level: "medium", changelog: ["Created in SCBKR 2.0 Rule Center"],
    };
    const created = await run(en ? "Create rule draft" : "建立規則草案", () => api<any>("/api/rules/draft", { method: "POST", body: JSON.stringify(payload) }));
    if (created) { setSelectedRule(created.rule.rule_id); await refreshAll(); }
  }

  async function createNaturalRule(instruction = naturalRuleText) {
    const text = instruction.trim();
    if (!text) return null;
    const created = await run(en ? "Compile natural-language rule" : "編譯自然語言規則", () => api<any>("/api/rules/draft-from-text", { method: "POST", body: JSON.stringify({ instruction: text, locale: replyLocale, rule_assist_plan: planLevel }) }));
    if (created) {
      setSelectedRule(created.rule.rule_id);
      setNaturalRuleText("");
      await refreshAll();
    }
    return created;
  }

  async function readFourStores(query = dataQuery) {
    const text = query.trim();
    if (!text) return null;
    const result = await run(en ? "Search and read four stores" : "搜尋並閱讀四庫", () => api<any>("/api/data-center/ask", { method: "POST", body: JSON.stringify({ query: text }) }));
    if (result) { setReadResult(result); setDataQuery(text); }
    return result;
  }

  async function openDataSection(section = dataSection) {
    const result = await run(en ? "Open data store" : "打開四庫資料", () => api<any>(`/api/data-center/${encodeURIComponent(section)}`));
    if (result) {
      setDataSection(section);
      setDataSectionResult(result);
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

  async function saveLaunchSettings() {
    const saved = await run(en ? "Save launch settings" : "儲存上線設定", () => api<any>("/api/launch/settings", { method: "POST", body: JSON.stringify(launchSettings) }));
    if (saved) { setLaunchSettings(saved); await refreshAll(); }
  }

  async function setWebPermission(enabled: boolean) {
    const saved = await run(en ? "Update web permission" : "更新網路權限", () => api<any>("/api/settings/permissions", { method: "POST", body: JSON.stringify({ web_search: enabled }) }));
    if (saved) setPermissions(saved);
  }

  async function activateRuntimePreview() {
    if (!runtimeSignature.trim()) return;
    const selected = await run(en ? "Activate runtime preview" : "啟用規則狀態預覽", () => api<any>("/api/rule-state/select", { method: "POST", body: JSON.stringify({ runtime_id: "shenyao-rule-state", version: "1.2.0", mode: runtimeMode, update_channel: "stable", developer_preview: true, preview_token: runtimeSignature }) }));
    if (selected) { setRuleState(selected); setRuntimeSignature(""); }
  }

  async function useIndependentState() {
    const state = await run(en ? "Use independent state" : "切換獨立規則狀態", () => api<any>("/api/rule-state/deactivate", { method: "POST", body: JSON.stringify({ reason: "user_selected_independent" }) }));
    if (state) setRuleState(state);
  }

  async function updateRuleAssistSettings(payload: Record<string, any>) {
    const updated = await run(en ? "Update rule assist" : "更新規則輔助", () => api<RuleAssistStatus>("/api/rule-assist/settings", { method: "POST", body: JSON.stringify({ locale: ruleAssist.locale || locale, ...payload }) }));
    if (updated) setRuleAssist(updated);
  }

  async function runRuleAssistMock() {
    const text = chatInput.trim() || (en ? "Hello, explain what this system can do." : "你好，說明這套系統可以怎麼建立規則。");
    const result = await run(en ? "Run rule-assist mock" : "測試規則層回覆", () => api<any>("/api/rule-assist/mock-chat", { method: "POST", body: JSON.stringify({ message: text, locale: replyLocale }) }));
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

  function renderWorkflowCard(card: WorkflowCard) {
    if (card.state === "DISMISSED") return null;
    return <section className={`workflow-card ${card.kind}`} aria-label={en ? "Workflow draft" : "待辦草案"}><header><span>{card.kind === "rule" ? (en ? "RULE DRAFT" : "規則草案") : card.kind === "task" ? (en ? "SCBKR DRAFT" : "責任鏈草案") : (en ? "DRAFT SUGGESTION" : "草案建議")}</span><b>{card.state}</b></header><h3>{card.title}</h3><p>{card.summary}</p>{Boolean(card.suggestedStores?.length) && <div className="store-chips">{card.suggestedStores?.map((store) => <span key={store}>{store}</span>)}</div>}<div className="workflow-actions">{card.kind === "suggestion" && <button onClick={() => void acceptSuggestion(card)}><Sparkles size={14} />{en ? "Create draft" : "建立草案"}</button>}{card.kind === "task" && card.taskId && <button onClick={() => void openTask(card.taskId!)}><SlidersHorizontal size={14} />{en ? "Open Workbench" : "前往工作台"}</button>}{card.kind === "rule" && card.ruleId && <button onClick={() => { setSelectedRule(card.ruleId!); setView("rules"); }}><FileKey size={14} />{en ? "Open Rule Center" : "前往規則中心"}</button>}<button className="quiet" onClick={() => dismissCard(card.id)}><X size={14} />{en ? "Dismiss" : "留在本次對話"}</button></div><small>{en ? "Not signed or stored." : "尚未簽名、尚未入庫。"}</small></section>;
  }

  const nav = [
    { id: "command" as View, label: copy.navigation.chat, icon: MessageSquare },
    { id: "rules" as View, label: copy.navigation.rules, icon: FileKey },
    { id: "workbench" as View, label: copy.navigation.workbench, icon: SlidersHorizontal },
    { id: "tools" as View, label: en ? "Tools" : "工具", icon: Wrench },
    { id: "data" as View, label: copy.navigation.dataCenter, icon: Database },
    { id: "runtime" as View, label: en ? "Rule State" : "規則狀態", icon: ShieldCheck },
    { id: "model" as View, label: copy.navigation.modelSettings, icon: Settings },
    { id: "launch" as View, label: en ? "Launch" : "上線中心", icon: Rocket },
    { id: "about" as View, label: copy.navigation.about, icon: Info },
  ];
  const mobileNav = [nav[0], nav[1], nav[2], nav[4], { id: "more" as View, label: en ? "More" : "更多", icon: Menu }];

  const stores = [
    { id: "vector", label: copy.stores.vector, count: overview.vector_count || 0, icon: Network },
    { id: "corpus", label: copy.stores.corpus, count: overview.corpus_count || 0, icon: Archive },
    { id: "logic", label: copy.stores.logic, count: overview.logic_count || 0, icon: Braces },
    { id: "memory", label: copy.stores.memory, count: overview.memory_count || 0, icon: HardDrive },
  ];
  const planCatalog = ruleAssist.catalog || [];
  const planIcon = planLevel === "NT3300" ? Crown : planLevel === "NT690" ? BrainCircuit : FileKey;
  const PlanIcon = planIcon;
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
      <details className="plan-details">
        <summary><SlidersHorizontal size={15} />{en ? "Switch plan" : "切換方案"}<span>{planLevel}</span></summary>
        <div className="plan-picker" aria-label={en ? "Plan selector" : "方案選擇"}>
          {planCatalog.map((plan) => <button key={plan.plan_level} className={planLevel === plan.plan_level ? "active" : ""} onClick={() => void updateRuleAssistSettings({ plan_level: plan.plan_level })}><span>{plan.price_label}</span><b>{plan.display_name}</b></button>)}
        </div>
      </details>
      <label>{en ? "Answer language" : "模型輸出語言"}<select value={ruleAssist.locale || "auto"} onChange={(event) => void updateRuleAssistSettings({ locale: event.target.value })}><option value="auto">Auto</option><option value="zh-TW">繁體中文</option><option value="en">English</option><option value="ja">日本語</option><option value="ko">한국어</option></select></label>
      <button className="primary-action" onClick={() => void runRuleAssistMock()}><Play size={15} />{en ? "Test rule layer" : "測試規則層回覆"}</button>
    </section>
  );

  const activeRulePanel = (
    <section className="ops-panel active-rule-panel">
      <header><ShieldCheck size={20} /><div><span>CURRENT RULE STATE</span><h2>{en ? "Enabled rule" : "目前啟用規則"}</h2></div></header>
      <dl><div><dt>{en ? "Source" : "規則來源"}</dt><dd>{ruleState.active_rulepack_id ? (en ? "ShenYao rule runtime" : "沈耀規則 Runtime") : ruleState.active_rule_id ? (en ? "User local rule" : "使用者本機規則") : (en ? "No active rule" : "尚無生效規則")}</dd></div><div><dt>{en ? "Version" : "版本"}</dt><dd>{ruleState.active_rulepack_version || ruleState.active_rule_version || "DRAFT"}</dd></div><div><dt>{en ? "Signature" : "簽名狀態"}</dt><dd>{ruleState.responsibility_holder || (en ? "Waiting user signature" : "等待使用者簽名")}</dd></div></dl>
      <button onClick={() => setView("runtime")}><ChevronRight size={15} />{en ? "Open rule state" : "查看規則狀態"}</button>
    </section>
  );

  const toolLauncher = (
    <div className={`tool-launcher ${toolLauncherOpen ? "open" : ""}`}>
      <button className="tool-plus" onClick={() => setToolLauncherOpen((value) => !value)} title={en ? "Open tool launcher" : "開啟工具列"}><Plus size={22} /></button>
      {toolLauncherOpen && <section className="tool-launcher-menu"><header><Sparkles size={17} /><div><span>CONNECTORS</span><h2>{en ? "Model-accessible tools" : "模型可碰的工具"}</h2></div></header><div>{aiToolCards.map(({ id, icon: Icon, title, status, detail }) => <button key={id} onClick={() => { setSelectedTool(id); setView("tools"); setToolLauncherOpen(false); }}><Icon size={18} /><span><b>{title}</b><small>{detail}</small></span><em className={status}>{status}</em></button>)}</div></section>}
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
      <small>{planLevel === "NT3300" ? (en ? "Current ceiling: CLOSE_CANDIDATE before owner signature." : "目前上限：使用者簽名前最多 CLOSE_CANDIDATE。") : (en ? "Current ceiling: draft and structure assist." : "目前上限：草案與結構輔助。")}</small>
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

  const rulePanel = (
    <section className="sovereignty-zone" aria-label={en ? "Rule sovereignty" : "規則主權區"}>
      <div className="zone-title"><div><span>RULE SOVEREIGNTY</span><h2>{copy.navigation.rules}</h2></div><button className="icon-button" onClick={() => void refreshAll()} title={en ? "Refresh" : "更新"}><RefreshCw size={16} /></button></div>
      <div className="metric-line"><span>{en ? "Active" : "啟用"}<b>{activeRules}</b></span><span>{en ? "Signed" : "已簽名"}<b>{rules.filter((r) => ["owner_signed", "active"].includes(r.activation_status)).length}</b></span><span>{en ? "Packs" : "規則包"}<b>{packs.length}</b></span></div>
      <div className="natural-rule-composer"><label>{en ? "Describe the rule in plain language" : "用一句人話建立規則"}<textarea value={naturalRuleText} onChange={(e) => setNaturalRuleText(e.target.value)} placeholder={en ? "Before publishing anything, require my signature." : "例如：凡是要發布內容，都必須先讓我簽名確認。"} /></label><button disabled={!naturalRuleText.trim()} onClick={() => void createNaturalRule()}><Sparkles size={15} />{en ? "Create unsigned draft" : "建立未簽名草案"}</button></div>
      <div className="rule-stack">
        {rules.length === 0 && <div className="empty-state">{en ? "No local rules" : "尚無本機規則"}</div>}
        {rules.slice(0, 8).map((rule) => <button key={rule.rule_id} className={`rule-row ${selectedRule === rule.rule_id ? "selected" : ""}`} onClick={() => setSelectedRule(rule.rule_id)}><span className={`state-dot ${rule.activation_status}`} /><span><b>{rule.rule_name}</b><small>{rule.rule_text || rule.rule_name}</small><small>{rule.rule_source} · {rule.rule_version}</small></span><em>{rule.activation_status}</em></button>)}
      </div>
      <details className="compact-form">
        <summary><Sparkles size={15} />{en ? "New user rule" : "新增使用者規則"}</summary>
        <label>{en ? "Rule name" : "規則名稱"}<input value={ruleForm.name} onChange={(e) => setRuleForm({ ...ruleForm, name: e.target.value })} /></label>
        <label>{en ? "Keywords" : "命中關鍵字"}<input value={ruleForm.keywords} onChange={(e) => setRuleForm({ ...ruleForm, keywords: e.target.value })} placeholder={en ? "comma separated" : "以逗號分隔"} /></label>
        <label>{en ? "Allowed tools" : "允許工具"}<input value={ruleForm.tools} onChange={(e) => setRuleForm({ ...ruleForm, tools: e.target.value })} placeholder="web_search, code_workspace" /></label>
        <label>{en ? "Action" : "動作"}<select value={ruleForm.action} onChange={(e) => setRuleForm({ ...ruleForm, action: e.target.value })}><option value="draft">draft</option><option value="execute">execute</option><option value="publish">publish</option><option value="store">store</option></select></label>
        <button disabled={!ruleForm.name.trim()} onClick={() => void createRule()}><Save size={15} />{en ? "Create draft" : "建立草案"}</button>
      </details>
      {selectedRule && <div className="signature-dock"><label>{en ? "Owner signature" : "擁有者簽名"}<input type="password" value={ruleSignature} onChange={(e) => setRuleSignature(e.target.value)} /></label><div><button disabled={!ruleSignature} onClick={() => void signRule()}><ShieldCheck size={15} />{en ? "Sign" : "簽名"}</button><button disabled={!ruleSignature} onClick={() => void activateRule()}><Play size={15} />{en ? "Activate" : "啟用"}</button></div></div>}
    </section>
  );

  const chatPanel = (
    <section className="command-zone chat-main" aria-label="一般聊天主視窗">
      <header className="command-header"><div><span>SCBKR 2.3</span><h1>{en ? "One-line Workbench" : "一句話工作台"}</h1></div><div className="stage-chip"><Activity size={15} />{readableStatus(status, en)}</div></header>
      <div className={`rule-awareness-strip ${String(ruleState.awareness_state || "EMPTY").toLowerCase()}`}><span>{ruleState.awareness_state || "EMPTY"}</span><b>{ruleState.active_rulepack_id ? `${ruleState.active_rulepack_id} v${ruleState.active_rulepack_version}` : ruleState.active_rule_id ? `${ruleState.active_rule_id} v${ruleState.active_rule_version}` : (en ? "No active rule" : "尚無生效規則")}</b><em>{ruleState.responsibility_holder ? `${en ? "RESPONSIBILITY" : "責任歸屬"} · ${ruleState.responsibility_holder}` : (en ? "ASSISTANCE ONLY" : "僅供輔助對話")}</em></div>
      <RuleFlowSurface en={en} status={status} activeRules={activeRules} citations={citations} tokensAvoided={Number(tokenMetrics.estimated_tokens_avoided || task?.scbkr?.token_metrics?.estimated_tokens_avoided || 0)} planLevel={planLevel} />
      <div className="command-modes" role="tablist" aria-label={en ? "Quick route" : "自然語言快速路由"}><button className={commandMode === "chat" ? "active" : ""} onClick={() => setCommandMode("chat")}><MessageSquare size={15} />{en ? "Auto route" : "自動分流"}</button><button className={commandMode === "web" ? "active" : ""} onClick={() => setCommandMode("web")}><Globe2 size={15} />{en ? "Verify web" : "上網查證"}</button><button className={commandMode === "search" ? "active" : ""} onClick={() => setCommandMode("search")}><Search size={15} />{en ? "Read stores" : "查四庫"}</button><button className={commandMode === "rule" ? "active" : ""} onClick={() => setCommandMode("rule")}><FileKey size={15} />{en ? "New rule" : "建規則"}</button></div>
      <div className="message-list" ref={messageListRef}>{messages.map((item, index) => <div key={`${item.role}-${index}`} className={`message ${item.role} ${item.card ? "has-card" : ""}`}><span>{item.role === "assistant" ? "SCBKR" : en ? "YOU" : "你"}</span><div>{item.content}</div>{item.card && renderWorkflowCard(item.card)}</div>)}</div>
      <div className="chat-input"><label className="natural-input-label"><span>{commandMode === "chat" ? (en ? "One-line input" : "一句話輸入") : commandMode === "web" ? (en ? "Verified web query" : "上網查證") : commandMode === "search" ? (en ? "Signed-store question" : "四庫問題") : (en ? "Rule sentence" : "規則句")}</span><textarea aria-label={en ? "Natural language input" : "自然語言輸入"} value={chatInput} onChange={(e) => setChatInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void sendChat(); } }} placeholder={commandMode === "chat" ? (en ? "Create a rule: require my signature before publishing." : "例如：幫我建立規則：發布前都要我簽名。") : commandMode === "web" ? (en ? "Verify current information about..." : "例如：查目前某項服務是否可用。") : commandMode === "search" ? (en ? "What do my signed rules say about publishing?" : "例如：四庫裡我對發布有什麼規則？") : (en ? "Before publishing, require my signature." : "例如：凡是要發布內容，都必須先讓我簽名。")} /></label><button className="icon-button send-button" onClick={() => void sendChat()} title={en ? "Run" : "執行"}>{commandMode === "web" ? <Globe2 size={20} /> : commandMode === "search" ? <Search size={20} /> : commandMode === "rule" ? <FileKey size={20} /> : <Send size={20} />}</button></div>
    </section>
  );

  const workbenchPanel = (
    <section className="workbench-zone workbench-panel" aria-label="SCBKR 工作台側欄">
      <div className="zone-title"><div><span>RESPONSIBILITY MATRIX</span><h2>Workbench / SCBKR 工作台</h2></div><CircleGauge size={20} /></div>
      {!task ? <div className="workbench-empty"><SquareTerminal size={26} /><h3>建立責任鏈確認單</h3><label>{en ? "Task" : "任務指令"}<textarea value={taskInput} onChange={(e) => setTaskInput(e.target.value)} /></label><button disabled={!taskInput.trim()} onClick={() => void createTask()}><Sparkles size={16} />{en ? "Compile SCBKR" : "編譯 SCBKR 草案"}</button></div> : <>
        <div className="task-state"><span>{task.task_id}</span><b>{task.status}</b></div>
        <section className="compiler-panel">
          <header><Bot size={16} /><div><span>{en ? "FORM FILLER" : "表單補寫"}</span><b>{compilerStatusLabel(task.scbkr?.compiler_report?.status, en)}</b></div></header>
          <div className="compiler-meta"><span>{en ? "Attempts" : "嘗試"} {task.scbkr?.compiler_report?.attempts ?? 0}</span><span>{task.scbkr?.model_participated ? (en ? "Model participated" : "模型有參與") : (en ? "Backend base logic" : "後端基礎邏輯")}</span><span>{task.scbkr?.draft_source || "draft"}</span></div>
          {Boolean(task.scbkr?.draft_model_call_skipped_reason || task.scbkr?.compiler_report?.errors?.length) && <small>{task.scbkr?.draft_model_call_skipped_reason || human(task.scbkr?.compiler_report?.errors)}</small>}
          <div className="button-row">
            {!task.confirmed && <button onClick={() => void regenerateCurrentScbkr()}><BrainCircuit size={15} />{en ? "Ask model to fill again" : "模型補寫表單"}</button>}
            {!task.confirmed && <button onClick={() => void applyCurrentRuleAssist()}><SlidersHorizontal size={15} />{en ? "Apply plan assist" : "套用690/3300結構補強"}</button>}
          </div>
        </section>
        {!task.confirmed && <section className="patch-assistant">
          <header><MessageSquare size={16} /><div><span>{en ? "EDIT BY CONVERSATION" : "對話修表單"}</span><b>{en ? "Model proposes, user applies" : "模型先草案，使用者再套用"}</b></div></header>
          <div className="patch-controls">
            <label>{en ? "Layer" : "要修改哪一層"}<select value={patchLayer} onChange={(event) => setPatchLayer(event.target.value as ScbkrDimensionKey)}>{dims.map((dim) => <option key={dim} value={dim}>{dim} · {dimensionNames[dim][en ? "en" : "zh"]}</option>)}</select></label>
            <label>{en ? "Instruction" : "用人話說哪裡不對"}<textarea value={patchInstruction} onChange={(event) => setPatchInstruction(event.target.value)} placeholder={en ? "Example: B is missing publish boundaries and K is claiming citations." : "例如：B 層沒有寫清楚不能發布；K 層不能假裝有引用四庫。"} /></label>
          </div>
          <div className="button-row"><button disabled={!patchInstruction.trim()} onClick={() => void draftLayerPatch()}><Sparkles size={15} />{en ? "Propose patch" : "請模型提出修改"}</button><button disabled={!pendingPatch} onClick={() => void applyLayerPatch()}><Check size={15} />{en ? "Apply patch" : "套用修改草案"}</button><button disabled={!pendingPatch} onClick={() => setPendingPatch(null)}><X size={15} />{en ? "Discard" : "取消草案"}</button></div>
          {pendingPatch && <div className="patch-preview"><b>{pendingPatch.layer} · {pendingPatch.plan_level || planLevel}</b><p>{pendingPatch.reason}</p><pre>{human(pendingPatch.after_draft)}</pre></div>}
        </section>}
        <div className="dimension-grid">{dims.map((dim) => { const content = task.scbkr?.[dim] || {}; const preview = human(content.task_subject || content.core_logic || content.stop_conditions || content.references || content.acceptance_criteria).slice(0, 88); return <details className={`dimension-row ${dimColor[dim]}`} key={dim} open={dim === "S"}><summary><b>{dim}</b><span><strong>{dimensionNames[dim][en ? "en" : "zh"]}</strong>{preview || (en ? "Pending" : "待補")}</span><ChevronRight size={15} /></summary><div className="dimension-readable">{Object.entries(content).filter(([key, value]) => key !== "pending_questions" && human(value).trim()).map(([key, value]) => <div key={key}><b>{fieldTitle(key, en)}</b><p>{human(value)}</p></div>)}</div></details>; })}</div>
        <div className="gate-sequence"><span className={task.confirmed ? "passed" : "current"}>1 {en ? "SIGN" : "簽名"}</span><span className={task.generation_result ? "passed" : task.confirmed ? "current" : ""}>2 {en ? "GENERATE" : "生成"}</span><span className={task.review_passed ? "passed" : task.status === "waiting_review" ? "current" : ""}>3 {en ? "REVIEW" : "驗收"}</span><span className={task.storage_confirmed ? "passed" : task.review_passed ? "current" : ""}>4 {en ? "STORE" : "入庫"}</span></div>
        <label>{en ? "Owner signature" : "使用者簽名"}<input value={ownerSignature} onChange={(e) => setOwnerSignature(e.target.value)} disabled={task.confirmed} /></label>
        <div className="action-grid">
          {!task.confirmed && <button disabled={!ownerSignature.trim()} onClick={() => void confirmTask()}><ShieldCheck size={15} />{en ? "Confirm" : "確認責任鏈"}</button>}
          {task.status === "confirmed" && <button onClick={() => void generate()}><Bot size={15} />{en ? "Generate" : "開始生成"}</button>}
          {task.status === "waiting_review" && <><button onClick={() => void review("pass")}><Check size={15} />{en ? "Pass" : "通過驗收"}</button><button className="danger" onClick={() => void review("fail")}><X size={15} />{en ? "Fail" : "驗收失敗"}</button></>}
        </div>
        {(task.review_passed || task.storage_plan) && <div className="store-select"><b>{en ? "Second-confirm stores" : "二次確認入庫"}</b>{stores.map((store) => <label key={store.id}><input type="checkbox" checked={selectedStores.includes(store.id)} onChange={() => setSelectedStores((current) => current.includes(store.id) ? current.filter((id) => id !== store.id) : [...current, store.id])} />{store.label}</label>)}<button disabled={!ownerSignature.trim()} onClick={() => void commitStores()}><Database size={15} />{en ? "Commit" : "確認寫入"}</button></div>}
        {task.generation_result && <div className="output-console"><span>MODEL OUTPUT</span>{human(task.generation_result.content || task.generation_result.generated_text || task.generation_result.output)}</div>}
      </>}
    </section>
  );

  const toolPanel = (
    <section className="workbench-zone tool-zone">
      <div className="zone-title"><div><span>AI ENGINE GATES</span><h2>{en ? "Tool Registry" : "工具註冊與權限"}</h2></div><Wrench size={20} /></div>
      <div className="tool-matrix">{tools.map((tool) => <button key={tool.tool_id} className={selectedTool === tool.tool_id ? "selected" : ""} onClick={() => setSelectedTool(tool.tool_id)}><span>{tool.name}</span><small>{tool.risk_level} · {tool.capabilities.join(" / ")}</small></button>)}</div>
      <div className="gate-console"><label>{en ? "Action" : "動作"}<select value={toolAction} onChange={(e) => setToolAction(e.target.value)}><option value="observe">observe</option><option value="search">search</option><option value="draft">draft</option><option value="execute">execute</option><option value="send">send</option><option value="publish">publish</option><option value="store">store</option></select></label><label className="toggle-line"><input type="checkbox" checked={toolConfirmed} onChange={(e) => setToolConfirmed(e.target.checked)} />{en ? "Confirm this high-risk call" : "確認本次高風險呼叫"}</label><button onClick={() => void evaluateTool()}><ShieldCheck size={15} />{en ? "Evaluate gates" : "檢查五道 Gate"}</button></div>
      {toolResult && <div className={`tool-result ${toolResult.allowed ? "allowed" : "blocked"}`}><b>{toolResult.allowed ? "AUTHORIZED" : "BLOCKED"}</b><span>{toolResult.reason}</span><small>{toolResult.execution_status}</small></div>}
    </section>
  );

  const dataDock = <footer className="data-dock">{stores.map((store) => { const Icon = store.icon; return <button key={store.id} onClick={() => setView("data")}><Icon size={17} /><span>{store.label}</span><b>{store.count}</b></button>; })}<button onClick={() => setView("tools")}><Activity size={17} /><span>{en ? "Traces" : "執行回放"}</span><b>{traces.length}</b></button></footer>;

  const selectedRuleData = rules.find((rule) => rule.rule_id === selectedRule);
  const selectedToolData = tools.find((tool) => tool.tool_id === selectedTool);
  const pendingTasks = tasks.filter((item) => !["completed", "storage_committed"].includes(item.status)).slice(0, 12);

  const commandPage = <div className="workspace-page command-workspace premium-dashboard"><div className="dashboard-grid"><section className="dashboard-main">{chatPanel}</section><aside className="dashboard-mid">{planConsole}{activeRulePanel}{aiToolPanel}</aside><aside className="dashboard-right">{auditPanel}{principlesPanel}{automationPanel}{phonePanel}<section className="ops-panel pending-panel"><header><FileKey size={20} /><div><span>ACTIVE DRAFTS</span><h2>{en ? "Pending work" : "待辦草案"}</h2></div></header><div className="activity-list">{pendingTasks.length === 0 && <div className="empty-state">{en ? "No pending drafts" : "目前沒有待辦草案"}</div>}{pendingTasks.slice(0, 5).map((item) => <button key={item.task_id} onClick={() => void openTask(item.task_id)}><span className="state-dot waiting_owner_signature" /><div><b>{item.task_name}</b><small>{item.status}</small></div><ChevronRight size={15} /></button>)}</div></section></aside>{toolLauncher}</div></div>;

  const rulesPage = <div className="workspace-page split-workspace rules-workspace"><div className="workspace-primary">{rulePanel}</div><aside className="workspace-inspector"><div className="workspace-heading"><span>RULE INSPECTOR</span><h2>{selectedRuleData ? selectedRuleData.rule_name : (en ? "Select a rule" : "選擇一條規則")}</h2></div>{selectedRuleData ? <div className="rule-inspector"><div className={`status-banner ${selectedRuleData.activation_status}`}><span>{selectedRuleData.activation_status}</span><b>{selectedRuleData.rule_version}</b></div><p>{selectedRuleData.rule_text}</p><dl><div><dt>{en ? "Author" : "作者"}</dt><dd>{selectedRuleData.rule_author}</dd></div><div><dt>{en ? "Scope" : "適用範圍"}</dt><dd>{scopeSummary(selectedRuleData.rule_scope, en)}</dd></div><div><dt>{en ? "Allowed tools" : "允許工具"}</dt><dd>{human(selectedRuleData.allowed_tools) || (en ? "None" : "未指定")}</dd></div><div><dt>{en ? "Risk" : "風險"}</dt><dd>{selectedRuleData.risk_level}</dd></div></dl></div> : <div className="empty-state">{en ? "Rule details appear here." : "規則內容會顯示在這裡。"}</div>}<ContextAssistant en={en} title={en ? "Rule review" : "規則檢查"} context={selectedRuleData ? `Current unsigned or active rule: ${JSON.stringify({ name: selectedRuleData.rule_name, text: selectedRuleData.rule_text, scope: selectedRuleData.rule_scope, status: selectedRuleData.activation_status })}` : "No rule selected. Discuss rule design without claiming a rule is active."} onAsk={(text) => askWorkspace("RULE_CENTER", text)} /></aside></div>;

  const workbenchPage = <div className="workspace-page workbench-workspace"><aside className="task-queue"><div className="workspace-heading"><span>DRAFT INBOX</span><h2>{en ? "Tasks" : "草案佇列"}</h2></div><button className="new-task" onClick={() => setTask(null)}><Sparkles size={15} />{en ? "New draft" : "新增草案"}</button><div className="activity-list">{tasks.slice(0, 20).map((item) => <button className={task?.task_id === item.task_id ? "selected" : ""} key={item.task_id} onClick={() => void openTask(item.task_id)}><span className={`state-dot ${item.confirmed ? "active" : "waiting_owner_signature"}`} /><div><b>{item.task_name}</b><small>{item.status}</small></div><ChevronRight size={15} /></button>)}</div></aside><div className="workspace-primary">{workbenchPanel}</div><aside className="workspace-inspector"><ContextAssistant en={en} title={en ? "Draft copilot" : "草案協作"} context={task ? `Current SCBKR task ${task.task_id}, status ${task.status}. Model may explain or propose a patch, but cannot sign, review, or store.` : "No task selected. Help the user clarify a task before creating a draft."} onAsk={(text) => askWorkspace("WORKBENCH", text)} /></aside></div>;

  const toolsPage = <div className="workspace-page split-workspace tools-workspace"><div className="workspace-primary">{toolPanel}</div><aside className="workspace-inspector"><div className="workspace-heading"><span>TOOL INSPECTOR</span><h2>{selectedToolData?.name || (en ? "Select a tool" : "選擇工具")}</h2></div>{selectedToolData && <div className="tool-inspector"><div className="status-banner"><span>{selectedToolData.risk_level}</span><b>{selectedToolData.tool_id}</b></div><p>{human(selectedToolData.capabilities)}</p><dl><div><dt>{en ? "Permissions" : "需要權限"}</dt><dd>{human(selectedToolData.required_permissions)}</dd></div><div><dt>{en ? "Actions" : "可用動作"}</dt><dd>{human(selectedToolData.allowed_actions)}</dd></div></dl></div>}<ContextAssistant en={en} title={en ? "Tool guidance" : "工具協作"} context={selectedToolData ? `Current tool: ${JSON.stringify({ id: selectedToolData.tool_id, risk: selectedToolData.risk_level, capabilities: selectedToolData.capabilities })}. Explain gates and risks without executing the tool.` : "No tool selected."} onAsk={(text) => askWorkspace("TOOLS", text)} /><div className="trace-mini"><h3>{en ? "Recent traces" : "最近回放"}</h3>{traces.slice(0, 6).map((trace) => <div key={trace.trace_id}><span className={`state-dot ${trace.allowed ? "active" : "revoked"}`} /><b>{trace.tool_id}</b><small>{trace.action}</small></div>)}</div></aside></div>;

  const dataPage = <section className="full-panel data-center-panel"><div className="page-head"><div><span>LOCAL EVIDENCE PLANE</span><h1>{en ? "Four Stores" : "四庫資料中心"}</h1></div><button onClick={() => void refreshAll()}><RefreshCw size={15} />{en ? "Refresh" : "讀回資料中心"}</button></div><div className="data-reader"><div><span>AUTHORITATIVE STORE READER</span><h2>{en ? "Ask your signed knowledge" : "用人話查詢已簽名資料"}</h2><small>{en ? "The model may only cite signed and reviewed records. Open a store below to inspect what is actually saved." : "模型只能引用已簽名、已驗收的資料；下面可直接打開四庫看實際存了什麼。"}</small></div><div className="reader-input"><input aria-label={en ? "Search four stores" : "搜尋四庫"} value={dataQuery} onChange={(e) => setDataQuery(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") void readFourStores(); }} placeholder={en ? "Ask a question about your stored rules..." : "例如：我的發布規則要求什麼？"} /><button disabled={!dataQuery.trim()} onClick={() => void readFourStores()}><Search size={16} />{en ? "Search and read" : "搜尋並閱讀"}</button></div>{readResult && <div className={`reader-result ${readResult.citation_count ? "has-evidence" : "empty"}`}><header><b>{readResult.citation_count || 0} {en ? "authoritative citations" : "筆正式引用"}</b><span>{readResult.candidates_excluded || 0} {en ? "candidates excluded" : "筆候選已排除"}</span><em>{readResult.model_called ? (en ? "MODEL READING DRAFT" : "模型閱讀草稿") : (en ? "NO MODEL CLAIM" : "未讓模型無依據作答")}</em></header><p>{readResult.answer}</p>{(readResult.citations || []).map((citation: any, index: number) => <div className="citation-row" key={`${citation.content_hash}-${index}`}><b>{citation.source_store}</b><span>{citation.store_role ? `${citation.store_role} · ` : ""}{citation.rule}</span><code>{String(citation.content_hash || "").slice(0, 12)}</code></div>)}</div>}</div><div className="store-band openable">{stores.map((store) => { const Icon = store.icon; return <button key={store.id} className={dataSection === store.id ? "selected" : ""} onClick={() => void openDataSection(store.id)} aria-label={`${store.label} ${en ? "store" : "資料庫"}`}><Icon /><span>{store.label}</span><strong>{store.count}</strong><small>{en ? "Open" : "打開"}</small></button>; })}</div><section className="store-browser"><header><div><span>{en ? "OPEN STORE" : "目前打開"}</span><h2>{stores.find((store) => store.id === dataSection)?.label || dataSection}</h2></div><button onClick={() => void openDataSection(dataSection)}><RefreshCw size={15} />{en ? "Reload store" : "重新讀取"}</button></header>{!dataSectionResult && <div className="empty-state">{en ? "Choose a store above to inspect saved records." : "點上面的向量庫、語料庫、邏輯庫或記憶庫，就能看到實際存入資料。"}</div>}{dataSectionResult && dataSectionResult.count === 0 && <div className="empty-state">{dataSectionResult.empty_message || (en ? "No records in this store." : "這個庫目前沒有資料。")}</div>}{(dataSectionResult?.items || []).map((item: any) => <article className="store-record" key={item.item_id || item.id}><button onClick={() => setExpandedDataItem((current) => current === (item.item_id || item.id) ? "" : (item.item_id || item.id))}><span className={`state-dot ${item.status === "active" ? "active" : "waiting_owner_signature"}`} /><div><b>{item.title || item.item_id}</b><small>{item.store_label || item.target} · {item.store_role || item.status_label || item.status} · v{item.version || 1}</small></div><code>{String(item.content_hash || item.hash || "").slice(0, 12)}</code></button><div className="store-role-note"><b>{item.citation_policy || item.status_label || item.status}</b><span>{item.store_purpose || item.model_reading_hint}</span></div><p>{item.plain_summary || item.summary || item.preview}</p><small>{item.storage_location || item.relative_path}</small>{expandedDataItem === (item.item_id || item.id) && <pre>{item.content_text || JSON.stringify(item.payload || item, null, 2)}</pre>}</article>)}</section><div className="trace-table"><h2>{en ? "Execution traces" : "執行回放"}</h2>{traces.map((trace) => <div key={trace.trace_id}><span className={`state-dot ${trace.allowed ? "active" : "revoked"}`} /><b>{trace.tool_id}</b><span>{trace.action}</span><span>{trace.reason}</span><time>{trace.timestamp}</time></div>)}</div></section>;

  const runtime = runtimeCatalog[0];
  const runtimeRelease = runtime?.versions?.[0];
  const runtimePage = <section className="full-panel runtime-page"><div className="page-head"><div><span>RULE STATE RUNTIME</span><h1>{en ? "Rule State" : "規則狀態"}</h1></div><ShieldCheck size={25} /></div><div className={`rule-state-hero ${ruleState.state === "shenyao_active" ? "active" : "independent"}`}><div><span>{en ? "CURRENT GOVERNANCE" : "目前治理狀態"}</span><h2>{ruleState.effective_label}</h2><p>{ruleState.state === "shenyao_active" ? `${ruleState.runtime_id} · v${ruleState.runtime_version} · ${ruleState.mode}` : (en ? "Custom rules run without ShenYao completeness validation." : "使用者可自行建立規則，但不提供沈耀邏輯完整性保證。")}</p></div><b>{ruleState.state === "shenyao_active" ? "SHENYAO ACTIVE" : "INDEPENDENT"}</b></div><div className="runtime-layout"><section className="runtime-product"><div className="runtime-brand"><ShieldCheck size={32} /><div><span>PROTECTED RULE RUNTIME</span><h2>{runtime?.name?.[locale] || "沈耀規則狀態"}</h2></div></div><p>{runtime?.description?.[locale]}</p><dl><div><dt>{en ? "Author" : "作者"}</dt><dd>{runtime?.author}</dd></div><div><dt>{en ? "Version" : "版本"}</dt><dd>{runtimeRelease?.version || "1.2.0"} · stable</dd></div><div><dt>{en ? "Source" : "核心交付"}</dt><dd>{en ? "Protected runtime; source not distributed" : "受保護 Runtime；不散布私有原始規則"}</dd></div></dl><label>{en ? "Mode" : "運行模式"}<select value={runtimeMode} onChange={(e) => setRuntimeMode(e.target.value)}>{(runtimeRelease?.modes || ["black_shield_strict", "responsibility_audit", "draft_compiler"]).map((mode: string) => <option value={mode} key={mode}>{mode}</option>)}</select></label><label>{en ? "Owner preview token" : "作者預覽權杖"}<input type="password" value={runtimeSignature} onChange={(e) => setRuntimeSignature(e.target.value)} placeholder="SCBKR_OWNER_PREVIEW_TOKEN" /></label><div className="button-row"><button disabled={!runtimeSignature.trim()} onClick={() => void activateRuntimePreview()}><Play size={15} />{en ? "Activate preview" : "啟用預覽狀態"}</button><button disabled={ruleState.state !== "shenyao_active"} onClick={() => void useIndependentState()}><X size={15} />{en ? "Use independent state" : "切回獨立狀態"}</button></div></section><section className="subscription-console"><span>SUBSCRIPTION INTERFACE</span><h2>{en ? "Monthly or annual access" : "月費／年費使用權"}</h2><p>{en ? "Subscription grants runtime execution entitlement, not the private rule source." : "訂閱取得規則 Runtime 執行資格，不取得私有規則原始碼。"}</p><div className="plan-row"><div><b>{en ? "Monthly" : "月費"}</b><small>{launchSettings.stripe_monthly_price_id || (en ? "Waiting for Stripe Price ID" : "等待 Stripe Price ID")}</small></div><button disabled><CreditCard size={15} />{en ? "Not connected" : "尚未接通"}</button></div><div className="plan-row"><div><b>{en ? "Annual" : "年費"}</b><small>{launchSettings.stripe_annual_price_id || (en ? "Waiting for Stripe Price ID" : "等待 Stripe Price ID")}</small></div><button disabled><CreditCard size={15} />{en ? "Not connected" : "尚未接通"}</button></div><div className="runtime-changelog"><b>{en ? "Version contract" : "版本契約"}</b>{(runtimeRelease?.changelog || []).map((item: string) => <span key={item}><Check size={14} />{item}</span>)}</div></section></div></section>;

  const launchPage = <section className="full-panel launch-page"><div className="page-head"><div><span>PRODUCTION CONTROL PLANE</span><h1>{en ? "Launch Center" : "上線中心"}</h1></div><Rocket size={25} /></div><div className="readiness-head"><div><span>{en ? "STORE READINESS" : "上架準備度"}</span><strong>{readiness.ready_count || 0}/{readiness.total_count || 8}</strong></div><div className="readiness-track"><i style={{ width: `${((readiness.ready_count || 0) / (readiness.total_count || 8)) * 100}%` }} /></div><small>{en ? "Fill in the services you create. Secret server keys never belong in the desktop client." : "你申請好服務後填在這裡；伺服器私鑰永遠不能放進桌面客戶端。"}</small></div><div className="launch-grid"><section><div className="integration-title"><Cloud /><div><b>Account & Domain</b><span>Supabase / Public URL</span></div></div><label>{en ? "Public domain" : "正式網域"}<input value={launchSettings.public_domain || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, public_domain: e.target.value })} placeholder="https://scbkr.example" /></label><label>Supabase URL<input value={launchSettings.supabase_url || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, supabase_url: e.target.value })} placeholder="https://project.supabase.co" /></label><label>Supabase publishable key<input type="password" value={launchSettings.supabase_publishable_key || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, supabase_publishable_key: e.target.value })} /></label></section><section><div className="integration-title"><CreditCard /><div><b>Stripe Billing</b><span>Entitlements / Customer Portal</span></div></div><label>Stripe publishable key<input value={launchSettings.stripe_publishable_key || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, stripe_publishable_key: e.target.value })} /></label><label>{en ? "Monthly Price ID" : "月費 Price ID"}<input value={launchSettings.stripe_monthly_price_id || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, stripe_monthly_price_id: e.target.value })} /></label><label>{en ? "Annual Price ID" : "年費 Price ID"}<input value={launchSettings.stripe_annual_price_id || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, stripe_annual_price_id: e.target.value })} /></label></section><section><div className="integration-title"><Globe2 /><div><b>Web Search</b><span>SearXNG / Brave Search</span></div></div><label>{en ? "Provider" : "搜尋服務"}<select value={launchSettings.search_provider || "searxng"} onChange={(e) => setLaunchSettings({ ...launchSettings, search_provider: e.target.value })}><option value="searxng">SearXNG</option><option value="brave">Brave Search API</option></select></label>{launchSettings.search_provider === "brave" ? <label>{en ? "Brave runtime credential" : "Brave 後端憑證"}<input disabled value={launchSettings.brave_api_key_configured ? (en ? "Configured" : "已設定") : (en ? "Not configured" : "未設定")} /></label> : <label>SearXNG URL<input value={launchSettings.searxng_url || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, searxng_url: e.target.value })} placeholder="https://search.example" /></label>}<label className="toggle-line"><input type="checkbox" checked={permissions.web_search === true} onChange={(e) => void setWebPermission(e.target.checked)} />{en ? "Allow confirmed web searches" : "允許經使用者確認的網路搜尋"}</label></section><section><div className="integration-title"><KeyRound /><div><b>Windows Distribution</b><span>Partner Center / Signing / Updater</span></div></div><label>Microsoft Partner Product ID<input value={launchSettings.microsoft_partner_product_id || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, microsoft_partner_product_id: e.target.value })} /></label><label>{en ? "Code signing subject" : "程式簽章主體"}<input value={launchSettings.code_signing_subject || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, code_signing_subject: e.target.value })} /></label><label>{en ? "Update endpoint" : "更新端點"}<input value={launchSettings.tauri_update_endpoint || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, tauri_update_endpoint: e.target.value })} /></label></section><section><div className="integration-title"><ShieldCheck /><div><b>Legal & Support</b><span>Privacy / Terms / Contact</span></div></div><label>{en ? "Privacy policy URL" : "隱私政策網址"}<input value={launchSettings.privacy_policy_url || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, privacy_policy_url: e.target.value })} /></label><label>{en ? "Terms URL" : "服務條款網址"}<input value={launchSettings.terms_of_service_url || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, terms_of_service_url: e.target.value })} /></label><label>{en ? "Support email" : "客服信箱"}<input value={launchSettings.support_email || ""} onChange={(e) => setLaunchSettings({ ...launchSettings, support_email: e.target.value })} /></label></section><section className="checklist-panel"><span>LAUNCH CHECKLIST</span>{(readiness.checks || []).map((check: any) => <div key={check.id} className={check.ready ? "ready" : "pending"}><i>{check.ready ? <Check size={13} /> : <X size={13} />}</i><b>{check.label}</b><em>{check.owner_action ? (en ? "OWNER" : "需你申請") : (en ? "ENGINEERING" : "工程")}</em></div>)}</section></div><div className="launch-actions"><button onClick={() => void saveLaunchSettings()}><Save size={16} />{en ? "Save launch configuration" : "儲存上線設定"}</button><span>{readiness.ready_for_store_submission ? (en ? "Ready for store submission" : "已具備送審條件") : (en ? "Missing external accounts or release materials" : "仍缺外部帳號或發布資料")}</span></div></section>;

  const modelPage = <section className="full-panel model-settings"><div className="page-head"><div><span>RUNTIME CONNECTION</span><h1>模型設定</h1></div><Bot /></div><div className="settings-grid"><section><h2>{en ? "Desktop / phone connection" : "桌機 / 手機連線"}</h2><div className={`companion-state ${companion?.lan_companion_enabled ? "on" : "off"}`}><span>LAN COMPANION</span><b>{companion?.lan_companion_enabled ? "ON" : "OFF"}</b><small>{companion?.base_url || backend} · {companion?.active_devices || 0} devices</small></div><label>Backend API URL<input value={backend} onChange={(e) => setBackend(e.target.value)} /></label><label>Companion token<input type="password" value={tokenInput} onChange={(e) => setTokenInput(e.target.value)} /></label><div className="button-row"><button onClick={saveConnection}><Network size={15} />{en ? "Connect" : "儲存並連線"}</button><button disabled={!companion?.lan_companion_enabled} onClick={() => void startPairing()}><FileKey size={15} />{en ? "Pair code" : "取得配對碼"}</button><button disabled={!companion?.active_devices} onClick={() => void revokeCompanions()}><X size={15} />{en ? "Revoke" : "撤銷裝置"}</button></div>{pairing && <div className="pairing-code"><span>{en ? "PAIRING CODE" : "手機配對碼"}</span><strong>{pairing.pairing_code}</strong><small>{pairing.base_url}</small><time>{pairing.expires_at}</time></div>}</section><section><h2>LLM Runtime</h2><label>Provider<select value={modelForm.provider} onChange={(e) => setModelForm({ ...modelForm, provider: e.target.value })}><option value="lm_studio">LM Studio</option><option value="ollama">Ollama</option><option value="openai_compatible">OpenAI-compatible</option><option value="sandbox_mock_model">Sandbox</option></select></label><label>Base URL<input value={modelForm.base_url} onChange={(e) => setModelForm({ ...modelForm, base_url: e.target.value })} /></label><label>Model name<input value={modelForm.model_name} onChange={(e) => setModelForm({ ...modelForm, model_name: e.target.value })} /></label><label>API Key<input type="password" value={modelForm.api_key} onChange={(e) => setModelForm({ ...modelForm, api_key: e.target.value })} /></label><div className="button-row"><button onClick={() => void saveModel()}><Save size={15} />{en ? "Save" : "儲存設定"}</button><button onClick={() => void testModel()}><Activity size={15} />{en ? "Test" : "測試模型連線"}</button></div></section></div></section>;

  const aboutPage = <section className="full-panel about-panel"><div className="about-mark">SCBKR<span>2.3</span></div><h1>{manifest?.name || copy.product.name}</h1><p className="about-tagline">{manifest?.tagline || copy.product.category}</p><dl><div><dt>{en ? "Author" : "作者"}</dt><dd>{manifest?.creator?.name || "許文耀 / 沈耀888π"}</dd></div><div><dt>{en ? "Organization" : "組織"}</dt><dd>{manifest?.creator?.organization || "語意防火牆"}</dd></div><div><dt>{en ? "Contact" : "合作聯絡"}</dt><dd>{manifest?.creator?.contact_email || "ken0963521@gmail.com"}</dd></div><div><dt>{en ? "Runtime" : "運行定位"}</dt><dd>{manifest?.runtime_relationship || "Local rule-driven AI control layer"}</dd></div></dl></section>;

  const morePage = <section className="full-panel more-page"><div className="page-head"><div><span>OPERATIONS</span><h1>{en ? "More" : "更多功能"}</h1></div><Menu /></div><div className="more-grid">{nav.filter((item) => ["tools", "runtime", "model", "launch", "about"].includes(item.id)).map(({ id, label, icon: Icon }) => <button key={id} onClick={() => setView(id)}><Icon size={23} /><b>{label}</b><ChevronRight size={16} /></button>)}</div></section>;

  const primaryPage = view === "rules" ? rulesPage : view === "workbench" ? workbenchPage : view === "tools" ? toolsPage : commandPage;
  const standalonePage = view === "data" ? dataPage : view === "runtime" ? runtimePage : view === "model" ? modelPage : view === "launch" ? launchPage : view === "about" ? aboutPage : view === "more" ? morePage : null;

  if (pairingRequired) return <main className="pair-gate"><div className="pair-stars" /><section><div className="pair-mark"><ShieldCheck size={30} /><span>SCBKR 2.3</span></div><p>SECURE MOBILE COMPANION</p><h1>{en ? "Pair this phone" : "配對這支手機"}</h1><small>{en ? "Enter the one-time code shown on your desktop. The code expires after 10 minutes." : "輸入桌機顯示的一次性配對碼，配對碼 10 分鐘後失效。"}</small><label>{en ? "Pairing code" : "6 位數配對碼"}<input inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={pairCode} onChange={(event) => setPairCode(event.target.value.replace(/\D/g, "").slice(0, 6))} onKeyDown={(event) => { if (event.key === "Enter") void redeemPairingCode(); }} placeholder="000000" /></label>{pairError && <div className="pair-error">{pairError}</div>}<button disabled={pairCode.length !== 6} onClick={() => void redeemPairingCode()}><FileKey size={17} />{en ? "Pair securely" : "安全配對"}</button><button className="pair-language" onClick={switchLocale}><Languages size={15} />{en ? "繁體中文" : "English"}</button><footer>{backend}</footer></section></main>;

  return <main className="app-shell v2-shell"><aside className="side-nav"><div className="brand-lockup"><Box size={24} /><div><b>SCBKR 2.3</b><span>RESPONSIBILITY OS</span></div></div>{nav.map(({ id, label, icon: Icon }) => <button key={id} className={view === id ? "active" : ""} onClick={() => setView(id)} title={label}><Icon size={18} /><span>{label}</span></button>)}<button onClick={switchLocale} title="Language"><Languages size={18} /><span>{locale === "en" ? "繁中" : "EN"}</span></button></aside><nav className="mobile-drawer">{mobileNav.map(({ id, label, icon: Icon }) => <button key={id} className={view === id ? "active" : ""} onClick={() => setView(id)}><Icon size={18} /><span>{label}</span></button>)}</nav><header className="top-status-bar"><button className="mobile-menu icon-button" onClick={() => setView("command")}><Menu size={18} /></button><span className={`system-signal ${health}`}><i />API {health}</span><span>STATE {ruleState.awareness_state || "EMPTY"}</span><span>PLAN {planLevel}</span><span>MODEL {model?.enabled && model?.last_test_status === "success" ? "LINKED" : "RULE-GATE"}</span><span>RULES {activeRules}</span><span>TOKEN SAVE {tokenMetrics.estimated_tokens_avoided || 0}</span><span>CITATIONS {citations}</span><button className="locale-button" onClick={switchLocale}><Globe2 size={14} />{locale}</button><em>{notice}</em></header><div className="desktop-stage">{!isMobile && (standalonePage || primaryPage)}</div><div className="mobile-stage">{isMobile && (standalonePage || primaryPage)}</div>{dataDock}</main>;
}
