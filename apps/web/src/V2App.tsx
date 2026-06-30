import { useEffect, useMemo, useState } from "react";
import {
  Activity, Archive, Bot, Box, Braces, Check, ChevronRight, CircleGauge,
  Database, FileKey, Globe2, HardDrive, Info, Languages, Menu, MessageSquare,
  Network, Play, RefreshCw, Save, Search, Send, Settings, ShieldCheck,
  SlidersHorizontal, Sparkles, SquareTerminal, Wrench, X,
} from "lucide-react";
import ResponsibilityCore from "./components/ResponsibilityCore";
import { getMessages, normalizeLocale, type Locale } from "./i18n";
import { isLoopbackHostname, resolveApiBaseUrl } from "./apiBase";
import type { ModelSettings, ScbkrDimensionKey, TaskSummary } from "./types";

const TOKEN_KEY = "scbkr.companionToken";
const BACKEND_KEY = "scbkr.activeBackendUrl";
const LOCALE_KEY = "scbkr.locale";
const dims: ScbkrDimensionKey[] = ["S", "C", "B", "K", "R"];
const dimColor: Record<ScbkrDimensionKey, string> = { S: "blue", C: "cyan", B: "yellow", K: "red", R: "green" };

type View = "command" | "rules" | "workbench" | "tools" | "data" | "model" | "about";
type CommandMode = "chat" | "search" | "rule";
type Rule = Record<string, any>;
type Tool = Record<string, any>;

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

export default function V2App() {
  captureToken();
  const [locale, setLocale] = useState<Locale>(normalizeLocale(localStorage.getItem(LOCALE_KEY) || "zh-TW"));
  const copy = getMessages(locale);
  const en = locale === "en";
  const [view, setView] = useState<View>("command");
  const [isMobile, setIsMobile] = useState(() => window.matchMedia("(max-width: 820px)").matches);
  const [rightMode, setRightMode] = useState<"workbench" | "tools">("workbench");
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
  const [traces, setTraces] = useState<Record<string, any>[]>([]);
  const [overview, setOverview] = useState<Record<string, any>>({});
  const [tokenMetrics, setTokenMetrics] = useState<Record<string, any>>({});
  const [notice, setNotice] = useState("");
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string }[]>([
    { role: "assistant", content: en ? "SCBKR local runtime ready." : "SCBKR 本機責任核心已就緒。" },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [commandMode, setCommandMode] = useState<CommandMode>("chat");
  const [naturalRuleText, setNaturalRuleText] = useState("");
  const [dataQuery, setDataQuery] = useState("");
  const [readResult, setReadResult] = useState<Record<string, any> | null>(null);
  const [taskInput, setTaskInput] = useState("");
  const [task, setTask] = useState<TaskSummary | null>(null);
  const [ownerSignature, setOwnerSignature] = useState("");
  const [selectedStores, setSelectedStores] = useState(["vector", "logic"]);
  const [ruleForm, setRuleForm] = useState({ name: "", keywords: "", tools: "", action: "draft" });
  const [ruleSignature, setRuleSignature] = useState("");
  const [selectedRule, setSelectedRule] = useState<string>("");
  const [selectedTool, setSelectedTool] = useState("web_search");
  const [toolAction, setToolAction] = useState("search");
  const [toolConfirmed, setToolConfirmed] = useState(false);
  const [toolResult, setToolResult] = useState<Record<string, any> | null>(null);
  const [modelForm, setModelForm] = useState({ provider: "lm_studio", mode: "local", base_url: "http://127.0.0.1:1234/v1", api_key: "", model_name: "", temperature: 0.2, max_tokens: 4096, context_length: 8192, timeout: 120 });

  const activeRules = rules.filter((rule) => rule.activation_status === "active").length;
  const citations = Number(task?.data_center_context?.evidence_packet?.authority_count || 0);
  const status = task?.status || "draft";

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

  async function refreshAll() {
    if (pairingRequired) return;
    const result = await run(en ? "Refresh runtime" : "更新系統", async () => {
      const [healthData, modelData, manifestData, companionData, ruleData, packData, toolData, traceData, overviewData, tokenData] = await Promise.all([
        api<any>("/health"), api<ModelSettings>("/api/settings/model"), api<any>(`/api/product/manifest?locale=${locale}`),
        api<any>("/api/companion/status"),
        api<any>("/api/rules"), api<any>("/api/rulepacks"), api<any>("/api/tools"), api<any>("/api/tools/traces?limit=20"), api<any>("/api/data-center/overview"), api<any>("/api/metrics/token-efficiency"),
      ]);
      return { healthData, modelData, manifestData, companionData, ruleData, packData, toolData, traceData, overviewData, tokenData };
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
    setOverview(result.overviewData || {});
    setTokenMetrics(result.tokenData || {});
    setModelForm((current) => ({ ...current, ...result.modelData, api_key: "" }));
  }

  useEffect(() => { void refreshAll(); }, [backend, locale, pairingRequired]);
  useEffect(() => { localStorage.setItem(LOCALE_KEY, locale); }, [locale]);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 820px)");
    const update = () => setIsMobile(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  async function sendChat() {
    const text = chatInput.trim();
    if (!text) return;
    setMessages((current) => [...current, { role: "user", content: text }]);
    setChatInput("");
    if (commandMode === "search") {
      const result = await readFourStores(text);
      if (result) setMessages((current) => [...current, { role: "assistant", content: result.answer }]);
      return;
    }
    if (commandMode === "rule") {
      const result = await createNaturalRule(text);
      if (result) {
        setMessages((current) => [...current, { role: "assistant", content: en ? "Rule draft created. Review and sign it in Rule Center." : "規則草案已建立。請在規則中心檢查、簽名，再決定是否啟用。" }]);
        setView("rules");
      }
      return;
    }
    const routed = await run(en ? "Route request" : "判斷任務", () => api<any>("/api/chat/intent", { method: "POST", body: JSON.stringify({ message: text }) }));
    if (!routed) return;
    if (routed.intent === "create_new_rule_confirmation") {
      const drafted = await createNaturalRule(text);
      if (drafted) setMessages((current) => [...current, { role: "assistant", content: en ? "I created an unsigned rule draft. You remain the only signer and activator." : "我已建立未簽名規則草案。只有你能簽名與啟用。" }]);
      return;
    }
    if (routed.intent === "create_confirmation") {
      setTaskInput(text);
      await createTask(text);
      setMessages((current) => [...current, { role: "assistant", content: en ? "Draft compiled. Review S/C/B/K/R in Workbench." : "草案已編譯，請在工作台檢查 S/C/B/K/R。" }]);
      return;
    }
    const reply = await run(en ? "Chat" : "模型回覆", () => api<any>("/api/chat/general", { method: "POST", body: JSON.stringify({ message: text, locale }) }));
    if (reply) {
      let ruleNotice = "";
      if (reply.suggestion) {
        const drafted = await createNaturalRule(reply.suggestion.suggested_instruction || text);
        if (drafted) ruleNotice = en ? "\n\nUnsigned rule draft created automatically. Review it in Rule Center before signing." : "\n\n已自動建立未簽名規則草案；請到規則中心檢查後再簽名。";
      }
      setMessages((current) => [...current, { role: "assistant", content: `${reply.reply}${ruleNotice}` }]);
    }
  }

  async function createTask(input = taskInput) {
    if (!input.trim()) { setNotice(en ? "Task input required" : "請輸入任務內容"); return; }
    const created = await run(en ? "Compile draft" : "編譯草案", () => api<TaskSummary>("/api/tasks/create", { method: "POST", body: JSON.stringify({ raw_input: input.trim(), task_type: "general", create_scbkr_draft: true }) }));
    if (created) { setTask(created); setOwnerSignature(""); setRightMode("workbench"); setView("workbench"); }
  }

  async function confirmTask() {
    if (!task || !ownerSignature.trim()) return;
    const confirmed = await run(en ? "Sign responsibility chain" : "簽名責任鏈", () => api<TaskSummary>(`/api/tasks/${task.task_id}/confirm`, { method: "POST", body: JSON.stringify({ scbkr: task.scbkr, confirmed_by: "user", signature: ownerSignature.trim() }) }));
    if (confirmed) setTask(confirmed);
  }

  async function generate() {
    if (!task) return;
    const generated = await run(en ? "Generate" : "模型生成", () => api<TaskSummary>(`/api/tasks/${task.task_id}/generate`, { method: "POST", body: "{}" }));
    if (generated) setTask(generated);
  }

  async function review(decision: "pass" | "fail") {
    if (!task) return;
    const reviewed = await run(en ? "Review output" : "驗收輸出", () => api<TaskSummary>(`/api/tasks/${task.task_id}/review`, { method: "POST", body: JSON.stringify({ review_decision: decision, review_message: decision === "pass" ? "Owner accepted" : "Owner rejected", reviewer_signature: ownerSignature || "owner" }) }));
    if (reviewed) setTask(reviewed);
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
    if (committed) { setTask(committed); void refreshAll(); }
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
    const created = await run(en ? "Compile natural-language rule" : "編譯自然語言規則", () => api<any>("/api/rules/draft-from-text", { method: "POST", body: JSON.stringify({ instruction: text }) }));
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

  const nav = [
    { id: "command" as View, label: copy.navigation.chat, icon: MessageSquare },
    { id: "rules" as View, label: copy.navigation.rules, icon: FileKey },
    { id: "workbench" as View, label: copy.navigation.workbench, icon: SlidersHorizontal },
    { id: "tools" as View, label: en ? "Tools" : "工具", icon: Wrench },
    { id: "data" as View, label: copy.navigation.dataCenter, icon: Database },
    { id: "model" as View, label: copy.navigation.modelSettings, icon: Settings },
    { id: "about" as View, label: copy.navigation.about, icon: Info },
  ];

  const stores = [
    { id: "vector", label: copy.stores.vector, count: overview.vector_count || 0, icon: Network },
    { id: "corpus", label: copy.stores.corpus, count: overview.corpus_count || 0, icon: Archive },
    { id: "logic", label: copy.stores.logic, count: overview.logic_count || 0, icon: Braces },
    { id: "memory", label: copy.stores.memory, count: overview.memory_count || 0, icon: HardDrive },
  ];

  const rulePanel = (
    <section className="sovereignty-zone" aria-label={en ? "Rule sovereignty" : "規則主權區"}>
      <div className="zone-title"><div><span>RULE SOVEREIGNTY</span><h2>{copy.navigation.rules}</h2></div><button className="icon-button" onClick={() => void refreshAll()} title={en ? "Refresh" : "更新"}><RefreshCw size={16} /></button></div>
      <div className="metric-line"><span>{en ? "Active" : "啟用"}<b>{activeRules}</b></span><span>{en ? "Signed" : "已簽名"}<b>{rules.filter((r) => ["owner_signed", "active"].includes(r.activation_status)).length}</b></span><span>{en ? "Packs" : "規則包"}<b>{packs.length}</b></span></div>
      <div className="natural-rule-composer"><label>{en ? "Describe the rule in plain language" : "用一句人話建立規則"}<textarea value={naturalRuleText} onChange={(e) => setNaturalRuleText(e.target.value)} placeholder={en ? "Before publishing anything, require my signature." : "例如：凡是要發布內容，都必須先讓我簽名確認。"} /></label><button disabled={!naturalRuleText.trim()} onClick={() => void createNaturalRule()}><Sparkles size={15} />{en ? "Create unsigned draft" : "建立未簽名草案"}</button></div>
      <div className="rule-stack">
        {rules.length === 0 && <div className="empty-state">{en ? "No local rules" : "尚無本機規則"}</div>}
        {rules.slice(0, 8).map((rule) => <button key={rule.rule_id} className={`rule-row ${selectedRule === rule.rule_id ? "selected" : ""}`} onClick={() => setSelectedRule(rule.rule_id)}><span className={`state-dot ${rule.activation_status}`} /><span><b>{rule.rule_name}</b><small>{rule.rule_text || rule.rule_name}</small><small>{rule.rule_source} · {rule.rule_version}</small></span><em>{rule.activation_status}</em></button>)}
      </div>
      <details className="compact-form" open={view === "rules"}>
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
      <ResponsibilityCore status={status} locale={locale} activeRules={activeRules} citations={citations} tokensAvoided={Number(tokenMetrics.estimated_tokens_avoided || task?.scbkr?.token_metrics?.estimated_tokens_avoided || 0)} />
      <header className="command-header"><div><span>NATURAL LANGUAGE CONTROL PLANE</span><h1>{en ? "Natural Language Console" : "自然語言控制台"}</h1></div><div className="stage-chip"><Activity size={15} />{status}</div></header>
      <div className="command-modes" role="tablist" aria-label={en ? "Natural language mode" : "自然語言模式"}><button className={commandMode === "chat" ? "active" : ""} onClick={() => setCommandMode("chat")}><MessageSquare size={15} />{en ? "Chat" : "一般對話"}</button><button className={commandMode === "search" ? "active" : ""} onClick={() => setCommandMode("search")}><Search size={15} />{en ? "Search stores" : "搜尋閱讀四庫"}</button><button className={commandMode === "rule" ? "active" : ""} onClick={() => setCommandMode("rule")}><FileKey size={15} />{en ? "Create rule" : "建立規則"}</button></div>
      <div className="message-list">{messages.map((item, index) => <div key={`${item.role}-${index}`} className={`message ${item.role}`}><span>{item.role === "assistant" ? "SCBKR" : en ? "YOU" : "你"}</span>{item.content}</div>)}</div>
      <div className="chat-input"><label className="natural-input-label"><span>{commandMode === "chat" ? (en ? "Talk to the local model" : "直接用人話跟本機模型說") : commandMode === "search" ? (en ? "Ask the signed four stores" : "搜尋並閱讀已簽名四庫") : (en ? "Describe the rule you want" : "說出你要建立的規則")}</span><textarea aria-label={en ? "Natural language input" : "自然語言輸入"} value={chatInput} onChange={(e) => setChatInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void sendChat(); } }} placeholder={commandMode === "chat" ? (en ? "Describe a task or ask SCBKR..." : "直接輸入你想做的事或想問的問題…") : commandMode === "search" ? (en ? "What do the signed stores say about..." : "例如：四庫裡有哪些關於發布規則的資料？") : (en ? "Before publishing, require my signature..." : "例如：凡是要發布內容，都必須先讓我簽名。")} /></label><button className="icon-button send-button" onClick={() => void sendChat()} title={en ? "Run" : "執行"}>{commandMode === "search" ? <Search size={20} /> : commandMode === "rule" ? <FileKey size={20} /> : <Send size={20} />}</button></div>
    </section>
  );

  const workbenchPanel = (
    <section className="workbench-zone workbench-panel" aria-label="SCBKR 工作台側欄">
      <div className="zone-title"><div><span>RESPONSIBILITY MATRIX</span><h2>Workbench / SCBKR 工作台</h2></div><CircleGauge size={20} /></div>
      {!task ? <div className="workbench-empty"><SquareTerminal size={26} /><h3>建立責任鏈確認單</h3><label>{en ? "Task" : "任務指令"}<textarea value={taskInput} onChange={(e) => setTaskInput(e.target.value)} /></label><button disabled={!taskInput.trim()} onClick={() => void createTask()}><Sparkles size={16} />{en ? "Compile SCBKR" : "編譯 SCBKR 草案"}</button></div> : <>
        <div className="task-state"><span>{task.task_id}</span><b>{task.status}</b></div>
        <div className="dimension-grid">{dims.map((dim) => <details className={`dimension-row ${dimColor[dim]}`} key={dim} open={dim === "S"}><summary><b>{dim}</b><span>{human(task.scbkr?.[dim]?.task_subject || task.scbkr?.[dim]?.core_logic || task.scbkr?.[dim]?.stop_conditions || task.scbkr?.[dim]?.references || task.scbkr?.[dim]?.acceptance_criteria).slice(0, 88) || (en ? "Pending" : "待補")}</span><ChevronRight size={15} /></summary><pre>{JSON.stringify(task.scbkr?.[dim] || {}, null, 2)}</pre></details>)}</div>
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

  const desktopCommand = <div className="control-grid">{rulePanel}{chatPanel}{rightMode === "workbench" ? workbenchPanel : toolPanel}<div className="right-switch"><button className={rightMode === "workbench" ? "active" : ""} onClick={() => setRightMode("workbench")}><SlidersHorizontal size={15} /></button><button className={rightMode === "tools" ? "active" : ""} onClick={() => setRightMode("tools")}><Wrench size={15} /></button></div></div>;

  const dataPage = <section className="full-panel data-center-panel"><div className="page-head"><div><span>LOCAL EVIDENCE PLANE</span><h1>{en ? "Search & Read Data Center" : "四庫搜尋與閱讀區"}</h1></div><button onClick={() => void refreshAll()}><RefreshCw size={15} />{en ? "Refresh" : "讀回資料中心"}</button></div><div className="data-reader"><div><span>AUTHORITATIVE STORE READER</span><h2>{en ? "Ask your signed knowledge" : "用人話查詢已簽名資料"}</h2><small>{en ? "Vector matches are candidates only. The model reads signed and reviewed citations." : "向量只負責找候選；模型只整理已簽名、已驗收的正式引用。"}</small></div><div className="reader-input"><input aria-label={en ? "Search four stores" : "搜尋四庫"} value={dataQuery} onChange={(e) => setDataQuery(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") void readFourStores(); }} placeholder={en ? "Ask a question about your stored rules..." : "例如：我的發布規則要求什麼？"} /><button disabled={!dataQuery.trim()} onClick={() => void readFourStores()}><Search size={16} />{en ? "Search and read" : "搜尋並閱讀"}</button></div>{readResult && <div className={`reader-result ${readResult.citation_count ? "has-evidence" : "empty"}`}><header><b>{readResult.citation_count || 0} {en ? "authoritative citations" : "筆正式引用"}</b><span>{readResult.candidates_excluded || 0} {en ? "candidates excluded" : "筆候選已排除"}</span><em>{readResult.model_called ? (en ? "MODEL READING DRAFT" : "模型閱讀草稿") : (en ? "NO MODEL CLAIM" : "未讓模型無依據作答")}</em></header><p>{readResult.answer}</p>{(readResult.citations || []).map((citation: any, index: number) => <div className="citation-row" key={`${citation.content_hash}-${index}`}><b>{citation.source_store}</b><span>{citation.rule}</span><code>{String(citation.content_hash || "").slice(0, 12)}</code></div>)}</div>}</div><div className="store-band">{stores.map((store) => { const Icon = store.icon; return <section key={store.id}><Icon /><span>{store.label}</span><strong>{store.count}</strong></section>; })}</div><div className="trace-table"><h2>{en ? "Execution traces" : "執行回放"}</h2>{traces.map((trace) => <div key={trace.trace_id}><span className={`state-dot ${trace.allowed ? "active" : "revoked"}`} /><b>{trace.tool_id}</b><span>{trace.action}</span><span>{trace.reason}</span><time>{trace.timestamp}</time></div>)}</div></section>;

  const modelPage = <section className="full-panel model-settings"><div className="page-head"><div><span>RUNTIME CONNECTION</span><h1>模型設定</h1></div><Bot /></div><div className="settings-grid"><section><h2>{en ? "Desktop / phone connection" : "桌機 / 手機連線"}</h2><div className={`companion-state ${companion?.lan_companion_enabled ? "on" : "off"}`}><span>LAN COMPANION</span><b>{companion?.lan_companion_enabled ? "ON" : "OFF"}</b><small>{companion?.base_url || backend} · {companion?.active_devices || 0} devices</small></div><label>Backend API URL<input value={backend} onChange={(e) => setBackend(e.target.value)} /></label><label>Companion token<input type="password" value={tokenInput} onChange={(e) => setTokenInput(e.target.value)} /></label><div className="button-row"><button onClick={saveConnection}><Network size={15} />{en ? "Connect" : "儲存並連線"}</button><button disabled={!companion?.lan_companion_enabled} onClick={() => void startPairing()}><FileKey size={15} />{en ? "Pair code" : "取得配對碼"}</button><button disabled={!companion?.active_devices} onClick={() => void revokeCompanions()}><X size={15} />{en ? "Revoke" : "撤銷裝置"}</button></div>{pairing && <div className="pairing-code"><span>{en ? "PAIRING CODE" : "手機配對碼"}</span><strong>{pairing.pairing_code}</strong><small>{pairing.base_url}</small><time>{pairing.expires_at}</time></div>}</section><section><h2>LLM Runtime</h2><label>Provider<select value={modelForm.provider} onChange={(e) => setModelForm({ ...modelForm, provider: e.target.value })}><option value="lm_studio">LM Studio</option><option value="ollama">Ollama</option><option value="openai_compatible">OpenAI-compatible</option><option value="sandbox_mock_model">Sandbox</option></select></label><label>Base URL<input value={modelForm.base_url} onChange={(e) => setModelForm({ ...modelForm, base_url: e.target.value })} /></label><label>Model name<input value={modelForm.model_name} onChange={(e) => setModelForm({ ...modelForm, model_name: e.target.value })} /></label><label>API Key<input type="password" value={modelForm.api_key} onChange={(e) => setModelForm({ ...modelForm, api_key: e.target.value })} /></label><div className="button-row"><button onClick={() => void saveModel()}><Save size={15} />{en ? "Save" : "儲存設定"}</button><button onClick={() => void testModel()}><Activity size={15} />{en ? "Test" : "測試模型連線"}</button></div></section></div></section>;

  const aboutPage = <section className="full-panel about-panel"><div className="about-mark">SCBKR<span>2.0</span></div><h1>{manifest?.name || copy.product.name}</h1><p className="about-tagline">{manifest?.tagline || copy.product.category}</p><dl><div><dt>{en ? "Author" : "作者"}</dt><dd>{manifest?.creator?.name || "許文耀 / 沈耀888π"}</dd></div><div><dt>{en ? "Organization" : "組織"}</dt><dd>{manifest?.creator?.organization || "語意防火牆"}</dd></div><div><dt>{en ? "Contact" : "合作聯絡"}</dt><dd>{manifest?.creator?.contact_email || "ken0963521@gmail.com"}</dd></div><div><dt>{en ? "Runtime" : "運行定位"}</dt><dd>{manifest?.runtime_relationship || "Local rule-driven AI control layer"}</dd></div></dl></section>;

  let mobileContent = chatPanel;
  if (view === "rules") mobileContent = rulePanel;
  if (view === "workbench") mobileContent = workbenchPanel;
  if (view === "tools") mobileContent = toolPanel;

  if (pairingRequired) return <main className="pair-gate"><div className="pair-stars" /><section><div className="pair-mark"><ShieldCheck size={30} /><span>SCBKR 2.0</span></div><p>SECURE MOBILE COMPANION</p><h1>{en ? "Pair this phone" : "配對這支手機"}</h1><small>{en ? "Enter the one-time code shown on your desktop. The code expires after 10 minutes." : "輸入桌機顯示的一次性配對碼，配對碼 10 分鐘後失效。"}</small><label>{en ? "Pairing code" : "6 位數配對碼"}<input inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={pairCode} onChange={(event) => setPairCode(event.target.value.replace(/\D/g, "").slice(0, 6))} onKeyDown={(event) => { if (event.key === "Enter") void redeemPairingCode(); }} placeholder="000000" /></label>{pairError && <div className="pair-error">{pairError}</div>}<button disabled={pairCode.length !== 6} onClick={() => void redeemPairingCode()}><FileKey size={17} />{en ? "Pair securely" : "安全配對"}</button><button className="pair-language" onClick={switchLocale}><Languages size={15} />{en ? "繁體中文" : "English"}</button><footer>{backend}</footer></section></main>;

  return <main className="app-shell v2-shell"><aside className="side-nav"><div className="brand-lockup"><Box size={24} /><div><b>SCBKR</b><span>RESPONSIBILITY OS</span></div></div>{nav.map(({ id, label, icon: Icon }) => <button key={id} className={view === id ? "active" : ""} onClick={() => setView(id)} title={label}><Icon size={18} /><span>{label}</span></button>)}<button onClick={switchLocale} title="Language"><Languages size={18} /><span>{locale === "en" ? "繁中" : "EN"}</span></button></aside><nav className="mobile-drawer">{nav.map(({ id, label, icon: Icon }) => <button key={id} className={view === id ? "active" : ""} onClick={() => setView(id)}><Icon size={18} /><span>{label}</span></button>)}</nav><header className="top-status-bar"><button className="mobile-menu icon-button" onClick={() => setView("command")}><Menu size={18} /></button><span className={`system-signal ${health}`}><i />API {health}</span><span>MODEL {model?.enabled && model?.last_test_status === "success" ? "LINKED" : "STANDBY"}</span><span>RULES {activeRules}</span><span>TOKEN SAVE {tokenMetrics.estimated_tokens_avoided || 0}</span><span>CITATIONS {citations}</span><button className="locale-button" onClick={switchLocale}><Globe2 size={14} />{locale}</button><em>{notice}</em></header><div className="desktop-stage">{!isMobile && (view === "data" ? dataPage : view === "model" ? modelPage : view === "about" ? aboutPage : desktopCommand)}</div><div className="mobile-stage">{isMobile && (view === "data" ? dataPage : view === "model" ? modelPage : view === "about" ? aboutPage : mobileContent)}</div>{dataDock}</main>;
}
