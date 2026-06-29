import { useEffect, useState } from "react";
/* Compatibility contract strings kept for regression tests and desktop release candidate:
const DEFAULT_API_BASE_URL = "http://127.0.0.1:8787";
// fetch(`${candidate}/health`) is kept as a contract string; runtime adds the optional companion token header.
SCBKR Windows Desktop Release Candidate
P14-C Windows Desktop Preview
if ("model_generate" in result) setPermissions(result as Permissions);
if (model?.mode === "sandbox" && permissions?.model_generate !== true)
if (!form.api_key && form.provider === "openai_compatible") delete payload.api_key;
Leave blank to keep the saved API key. Use “Clear API Key” to remove it.
Chat / 任務入口 | Workbench / SCBKR 工作台 | Model Settings / 模型設定 | Data Center / 資料中心 | Audit / 審計資料
模型設定 / Model Settings | 模式 / Mode | Base URL | API Key | Model Name | 儲存設定 | 測試連線 | 切回沙盒模式 | 前往模型設定
目前模型尚未連線，請先到「模型設定」完成測試連線，或切回沙盒模式。
http://127.0.0.1:1234/v1 | http://127.0.0.1:11434/v1
Raw Audit Details（預設關閉）
<details><summary>點擊展開 JSON</summary>
confirmed=false：請先確認責任鏈，模型不可執行。
disabled={!task?.confirmed}
result?.content ?? result?.generated_text
onChange={(e: any) => updateField(dim, field.key, e.target.value)}
沙盒生成前請先開啟 model_generate 權限。 | normalizeApiBaseUrl | api_server_reachable | apiUrl(path) | api_sidecar | 驗收失敗 / 建立記憶規則 | 二次確認入庫 | 任務輸入框 | 已建立工作台任務確認單 | 已將聊天內容轉為 SCBKR 任務草案 | SCBKR 五維確認單｜可編輯 | 模型回覆 / 生成結果 | 我的資料中心 | 工作台 / 工單 | 查看原始 patch | 事件日期：{eventDate || "未設定"} | task.status !== "waiting_review" | Raw Details
任務名稱 使用者指令 任務主體 輸入內容 輸出形式 操作介面 平台類型
流程拆解 執行順序 資料流 事件流 核心邏輯 依賴關係 失敗影響 測試條件
資料讀取範圍 資料寫入範圍 權限開關 停止條件 錯誤處理 入庫條件
參考資料 技術文件 語料來源 風格設定 模型依據 歷史案例 待確認項目
預期輸出 驗收條件 回放要求 入庫選項 簽名狀態 引用證據 本次未命中已確認資料 source_store
*/

import { DEFAULT_API_BASE_URL, resolveApiBaseUrl } from "./apiBase";
import type { ModelSettings, ScbkrDimensionKey, TaskSummary, TaskType } from "./types";

// fetch(`${candidate}/health`) is kept as a contract string; runtime adds the optional companion token header.
const COMPANION_TOKEN_STORAGE_KEY = "scbkr.companionToken";
function defaultApiBaseUrl() {
  return resolveApiBaseUrl({
    protocol: typeof window !== "undefined" ? window.location.protocol : "",
    hostname: typeof window !== "undefined" ? window.location.hostname : "",
    port: typeof window !== "undefined" ? window.location.port : "",
    search: typeof window !== "undefined" ? window.location.search : "",
    envApiUrl: import.meta.env.VITE_SCBKR_API_URL,
  });
}
const API_BASE_URL = defaultApiBaseUrl().replace(/\/+$/, "");
const ACTIVE_BACKEND_STORAGE_KEY = "scbkr.activeBackendUrl";
type Page = "chat" | "workbench" | "data-center" | "model-settings" | "audit";
const dims: ScbkrDimensionKey[] = ["S", "C", "B", "K", "R"];
const navItems: [Page, string, string][] = [["chat", "聊天", "💬"], ["workbench", "工作台", "🧩"], ["data-center", "資料中心", "🗄️"], ["model-settings", "模型設定", "⚙️"], ["audit", "審計資料", "📋"]];
const dimTitles: Record<ScbkrDimensionKey, string> = { S: "S｜任務主體", C: "C｜流程因果", B: "B｜邊界行為", K: "K｜依據風格", R: "R｜回放驗收" };
const dimFieldLabels: Record<ScbkrDimensionKey, [string, string][]> = {
  S: [["task_name", "任務名稱"], ["user_instruction", "使用者原始指令"], ["task_subject", "任務主體"], ["output_format", "輸出形式"], ["interface_type", "操作介面"]],
  C: [["flow_steps", "流程步驟"], ["execution_order", "執行順序"], ["data_flow", "資料流"], ["dependencies", "依賴條件"], ["test_conditions", "測試條件"]],
  B: [["data_read_scope", "可讀範圍"], ["data_write_scope", "可寫範圍"], ["external_scope", "可呼叫服務"], ["stop_conditions", "停止條件"], ["storage_conditions", "入庫限制"]],
  K: [["references", "參考資料"], ["style_settings", "風格設定"], ["model_basis", "模型依據"], ["source_credibility", "來源可信度"], ["historical_cases", "歷史案例"]],
  R: [["expected_outputs", "預期輸出"], ["acceptance_criteria", "驗收條件"], ["replay_requirements", "回放要求"], ["storage_options", "入庫選項"], ["signature_status", "簽名狀態"]],
};
const storeLabels: Record<string, string> = { vector: "向量庫", corpus: "語料庫", logic: "程式邏輯庫", memory: "記憶庫" };
const workbenchCommands = ["生成任務確認單", "建立任務確認單", "建立確認單", "生成確認單", "送到工作台", "轉成工作台任務", "建立 SCBKR 任務", "建立 SCBKR 確認單", "生成責任鏈", "建立責任鏈", "責任鏈任務確認單", "責任練任務確認單", "工作台草案", "開工作台", "幫我建確認單", "幫我做責任鏈"];
const isWorkbenchCommand = (value: string) => workbenchCommands.some((cmd) => value.includes(cmd));
const cleanWorkbenchCommand = (value: string) => workbenchCommands.reduce((text, cmd) => text.split(cmd).join(" "), value).replace(/[，,。:：]/g, " ").replace(/\s+/g, " ").trim();
const dataCenterSections = ["任務紀錄", "確認單", "生成結果", "驗收紀錄", "入庫資料", "向量庫", "語料庫", "程式邏輯庫", "記憶庫", "回放帳本"];
const sectionMap: Record<string, string> = { "任務紀錄": "tasks", "確認單": "confirmations", "生成結果": "generations", "驗收紀錄": "reviews", "入庫資料": "storage", "向量庫": "vector", "語料庫": "corpus", "程式邏輯庫": "logic", "記憶庫": "memory", "回放帳本": "ledger" };
const itemValue = (item: Record<string, any>, keys: string[]) => keys.map((k) => item?.[k]).find((v) => v !== undefined && v !== null && v !== "") ?? "—";
const itemSummary = (item: Record<string, any>) => humanText(item.summary || item.title || item.task_name || item.raw_input || item.payload?.summary || item.payload?.content || item.retrieval_text).slice(0, 120) || "—";

function normalizeBackendUrl(value: string) { return (value || API_BASE_URL).trim().replace(/\/+$/, ""); }
function captureCompanionTokenFromUrl() {
  if (typeof window === "undefined") return;
  const token = new URLSearchParams(window.location.search).get("companion_token");
  if (token) localStorage.setItem(COMPANION_TOKEN_STORAGE_KEY, token);
}
function companionToken() { captureCompanionTokenFromUrl(); return localStorage.getItem(COMPANION_TOKEN_STORAGE_KEY) || ""; }
function storedBackendUrl() { return normalizeBackendUrl(localStorage.getItem(ACTIVE_BACKEND_STORAGE_KEY) || API_BASE_URL); }
function apiUrl(path: string, baseUrl = storedBackendUrl()) { return `${normalizeBackendUrl(baseUrl)}/${path.replace(/^\/+/, "")}`; }
async function api<T>(path: string, init?: RequestInit, backendUrl = storedBackendUrl()): Promise<T> { const token = companionToken(); const r = await fetch(apiUrl(path, backendUrl), { headers: { "Content-Type": "application/json", ...(token ? { "X-SCBKR-Companion-Token": token } : {}), ...(init?.headers ?? {}) }, ...init }); if (!r.ok) { let detail = await r.text(); try { detail = JSON.parse(detail).detail ?? detail; } catch {} throw new Error(detail); } return r.json() as Promise<T>; }
const humanText = (v: any) => Array.isArray(v) ? v.join("\n") : typeof v === "object" && v ? Object.values(v).filter(Boolean).join("\n") : String(v ?? "");
const parse = (value: string, old: any) => Array.isArray(old) ? value.split("\n").map((x) => x.trim()).filter(Boolean) : value;
const resultText = (task: TaskSummary | null) => String(task?.generation_result?.content ?? task?.generation_result?.generated_text ?? "尚未生成。確認責任鏈後才能開始生成。");
const invalidateDownstreamForRevision = (current: TaskSummary): TaskSummary => {
  const next: TaskSummary = {
    ...current,
    confirmed: false,
    status: "waiting_user_confirm",
    review_passed: false,
    storage_confirmed: false,
  };

  delete next.generation_result;
  delete next.review_result;
  delete next.storage_suggestion;
  delete next.storage_request;
  delete next.storage_plan;
  delete next.storage_result;
  delete next.memory_rule_draft;

  return next;
};
const statusLabel = (task: TaskSummary | null) => !task ? "尚未建立任務" : task.status === "waiting_model_draft" ? "等待模型草案" : task.status === "waiting_user_confirm" ? "等待責任鏈確認" : task.status === "confirmed" ? "已確認責任鏈，可開始生成" : task.status === "waiting_review" ? "等待驗收" : task.status === "review_passed" ? "驗收通過，可產生入庫建議" : task.status === "waiting_storage_confirm" ? "等待二次確認入庫" : task.status === "storage_committed" || task.status === "completed" ? "入庫完成" : task.status;
function JsonBlock({ value }: { value: unknown }) { return <pre className="json-block raw-json">{JSON.stringify(value, null, 2)}</pre>; }

export default function App() {
  const [page, setPage] = useState<Page>("chat");
  const [drawer, setDrawer] = useState(false);
  const [health, setHealth] = useState("checking");
  const [selectedBackendUrl, setSelectedBackendUrl] = useState(storedBackendUrl());
  const [backendUrl, setBackendUrl] = useState(storedBackendUrl());
  const [activeBackendUrl, setActiveBackendUrl] = useState(storedBackendUrl());
  const runtimeLabel = activeBackendUrl.includes("127.0.0.1") || activeBackendUrl.includes("localhost") ? "desktop / sidecar" : "mobile";
  const [model, setModel] = useState<ModelSettings | null>(null);
  const [message, setMessage] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([{ role: "assistant", content: "你好，我可以先一般聊天；若內容適合落地成任務，我會提供「將此對話轉為工作台任務」建議卡。" }]);
  const [suggestion, setSuggestion] = useState<Record<string, any> | null>(null);
  const [prefill, setPrefill] = useState<Record<string, any> | null>(null);
  const [taskText, setTaskText] = useState("");
  const [taskType] = useState<TaskType>("general");
  const [task, setTask] = useState<TaskSummary | null>(null);
  const [patchLayer, setPatchLayer] = useState<ScbkrDimensionKey>("B");
  const [patchInstruction, setPatchInstruction] = useState("把這一層改嚴格一點，不要讓模型自行確認日期或入庫。");
  const [pendingPatch, setPendingPatch] = useState<Record<string, any> | null>(null);
  const [eventDate, setEventDate] = useState("");
  const [modelDate, setModelDate] = useState("");
  const [storageSuggestion, setStorageSuggestion] = useState<Record<string, any> | null>(null);
  const [selectedTargets, setSelectedTargets] = useState<string[]>([]);
  const [dataCenter, setDataCenter] = useState<Record<string, any> | null>(null);
  const [dataCenterSectionsData, setDataCenterSectionsData] = useState<Record<string, any[]>>({});
  const [dataCenterView, setDataCenterView] = useState("任務紀錄");
  const [selectedDataItem, setSelectedDataItem] = useState<Record<string, any> | null>(null);
  const [updateInstruction, setUpdateInstruction] = useState("");
  const [updateDraft, setUpdateDraft] = useState<Record<string, any> | null>(null);
  const [ownerSignature, setOwnerSignature] = useState("");
  const [dataCenterOwnerSignature, setDataCenterOwnerSignature] = useState("");
  const [modelForm, setModelForm] = useState({ provider: "lm_studio", mode: "local", base_url: "http://127.0.0.1:1234/v1", api_key: "", model_name: "", temperature: 0.2, max_tokens: 4096, context_length: 8192, timeout: 120 });
  const clearOwnerSignatureForDraftChange = () => { setOwnerSignature(""); setMessage("草案已修改，請重新輸入使用者簽名後再確認責任鏈。舊生成、驗收與入庫資料已作廢。"); };
  const locked = Boolean((task as any)?.physical_write_performed) || task?.status === "completed" || task?.status === "storage_committed";
  const draftSourceLabel = (source?: string) => source === "model_assisted_structured" ? "模型輔助草案" : source === "scbkr_base_logic" ? "SCBKR 基礎邏輯草案" : source === "draft_failed" ? "草案生成失敗" : "尚未建立";
  const sourceLabel = task ? draftSourceLabel(task.scbkr?.draft_source) : "尚未建立";
  const sourceReason = task?.scbkr?.draft_source === "scbkr_base_logic" ? "模型未成功產生可用理解，系統依 SCBKR 基礎語法生成草案。此草案仍需使用者簽名確認。" : task?.scbkr?.draft_source === "draft_failed" ? "使用者指令缺少任務主體，請補充任務主體後重新生成草案。" : "模型已依 SCBKR Grammar Pack 產生任務理解，系統已編譯成合法 S/C/B/K/R。";
  const can = { confirm: task?.status === "waiting_user_confirm" && task?.scbkr?.draft_source !== "draft_failed" && !locked, generate: task?.status === "confirmed", review: task?.status === "waiting_review" && Boolean(task?.generation_result), revise: ["waiting_review", "review_failed", "rollback_requested"].includes(task?.status ?? "") && !locked, suggest: task?.status === "review_passed" || task?.review_passed, storage: task?.status === "waiting_storage_confirm" || Boolean(task?.storage_plan) };

  const refresh = async () => { try { await api("/health", undefined, activeBackendUrl); setHealth("online"); const m = await api<ModelSettings>("/api/settings/model", undefined, activeBackendUrl); setModel(m); setModelForm({ ...modelForm, provider: m.provider || modelForm.provider, mode: m.mode || modelForm.mode, base_url: m.base_url || modelForm.base_url, model_name: m.model_name || modelForm.model_name, api_key: "" }); } catch (e) { setHealth("offline"); setMessage(String(e)); } };
  useEffect(() => { localStorage.setItem(ACTIVE_BACKEND_STORAGE_KEY, activeBackendUrl); void refresh(); }, [activeBackendUrl]);
  const run = async <T,>(label: string, fn: () => Promise<T>) => { try { const r: any = await fn(); if (r?.task_id) setTask(r); if (r?.model_name) setModel(r); setMessage(`${label} 完成`); return r; } catch (e) { const raw = String(e); setMessage(raw.includes("required_permissions_not_enabled") ? "目前權限不足，無法呼叫模型。請確認模型生成權限，或切回 Sandbox。" : raw.includes("task.status must be confirmed") ? "目前責任鏈尚未確認，請先確認責任鏈後再生成。" : raw.includes("completed") || raw.includes("physical_write_performed") ? "此任務已入庫或完成，不能直接修改原任務；請建立新版本或新任務。" : label === "開啟模型生成權限" ? "模型生成權限開啟失敗，請確認後端 API 是否連線。" : `${label} 失敗：${raw}`); } };

  const createConfirmationFromChat = async (user: string) => { const taskInput = cleanWorkbenchCommand(user) || user; setTaskText(taskInput); const created = await run("建立確認單", () => api<TaskSummary>("/api/tasks/create", { method: "POST", body: JSON.stringify({ raw_input: taskInput, task_type: taskType, create_scbkr_draft: true, prefill: { user_original: user, suggested_instruction: taskInput, suggested_type: "工作台任務", suggested_reason: "使用者在聊天中明確要求建立任務確認單。", suggested_write_direction: "暫不入庫" } }) })); if (created?.task_id) { setOwnerSignature(""); setTask(created); setPage("workbench"); setDrawer(false); } return created; };
  const sendChat = async () => { const user = chatInput.trim(); if (!user) return; const next = [...messages, { role: "user", content: user }]; setMessages(next); setChatInput(""); const routed = await run("判斷聊天意圖", () => api<Record<string, any>>("/api/chat/intent", { method: "POST", body: JSON.stringify({ message: user }) })); if (!routed) return; if (routed.intent === "create_confirmation" || routed.intent === "create_new_rule_confirmation") { const created = await createConfirmationFromChat(user); if (created?.task_id) setMessages([...next, { role: "assistant", content: "已建立 SCBKR 確認單草案，請到 Workbench 檢查 S/C/B/K/R。此草案需由使用者簽名確認後才成立。" }]); return; } if (String(routed.intent).startsWith("suggest")) { setSuggestion(routed.suggestion || { user_original: user, suggested_instruction: user }); setMessages([...next, { role: "assistant", content: "這段內容適合建立 SCBKR 確認單。你可以按建議卡的「生成確認單」，或繼續聊天。" }]); return; } if (routed.intent === "data_center_query") { const found = await run("查詢資料中心", () => api<Record<string, any>>("/api/data-center/query", { method: "POST", body: JSON.stringify({ query: user }) })); setMessages([...next, { role: "assistant", content: `已查詢 Data Center，找到 ${found?.count ?? 0} 筆候選資料；更改或刪除仍需確認單。` }]); return; } const r = await run("一般聊天", () => api<Record<string, any>>("/api/chat/general", { method: "POST", body: JSON.stringify({ message: user }) })); if (r) { setMessages([...next, { role: "assistant", content: r.reply }]); setSuggestion(r.suggestion); } };
  const acceptSuggestion = async () => { if (!suggestion) return; const created = await createConfirmationFromChat(suggestion.user_original || suggestion.suggested_instruction || taskText); if (created?.task_id) { setOwnerSignature(""); setSuggestion(null); setMessages([...messages, { role: "assistant", content: "已建立 SCBKR 確認單草案，請到 Workbench 檢查 S/C/B/K/R。此草案需由使用者簽名確認後才成立。" }]); } };
  const createTask = async () => { if (!taskText.trim()) { setMessage("請先輸入任務內容。"); return; } return run("建立確認單", () => api<TaskSummary>("/api/tasks/create", { method: "POST", body: JSON.stringify({ raw_input: taskText.trim(), task_type: taskType, create_scbkr_draft: true, prefill }) })).then((r: any) => r?.task_id && (setOwnerSignature(""), setPage("workbench"))); };
  const resetWorkbench = (notice = "工作台已清空，可以建立下一張確認單。") => { setTask(null); setTaskText(""); setStorageSuggestion(null); setSelectedTargets([]); setPendingPatch(null); setUpdateDraft(null); setOwnerSignature(""); setMessage(notice); };
  const duplicateTask = () => task && task.scbkr && run("複製為新任務", () => api<TaskSummary>("/api/tasks/create", { method: "POST", body: JSON.stringify({ raw_input: task.raw_input || taskText, task_type: task.task_type || taskType, create_scbkr_draft: true }) })).then((r: any) => r?.task_id && (setOwnerSignature(""), setPage("workbench")));
  const regenerateDraft = () => task && !task.confirmed && !locked && run("重新生成草案", () => api<TaskSummary>(`/api/tasks/${task.task_id}/scbkr/regenerate-draft`, { method: "POST", body: JSON.stringify({ raw_input: task.raw_input, mode: "model_first", allow_base_logic: true }) })).then((r: any) => { if (r?.task_id) clearOwnerSignatureForDraftChange(); });
  const cancelTask = () => { if (locked) { setMessage("已入庫任務不得取消或刪除資料，只能關閉工作台或複製為新任務。"); return; } resetWorkbench("已取消此確認單，尚未入庫資料未被刪除。"); };
  const saveFields = () => task?.scbkr && !locked && run("儲存欄位修改", () => api<TaskSummary>(`/api/tasks/${task.task_id}/scbkr`, { method: "PATCH", body: JSON.stringify({ scbkr: task.scbkr, layer: "manual_field_save" }) })).then((r: any) => { if (r?.task_id) clearOwnerSignatureForDraftChange(); });
  const updateField = (d: ScbkrDimensionKey, f: string, v: string) => { if (!task?.scbkr || locked) return; const old = task.scbkr[d]?.[f]; clearOwnerSignatureForDraftChange(); setTask({ ...task, confirmed: false, status: "waiting_user_confirm", generation_result: undefined, review_result: undefined, storage_plan: undefined, storage_suggestion: undefined, scbkr: { ...task.scbkr, confirmation_status: "draft", [d]: { ...task.scbkr[d], [f]: parse(v, old) } } }); };
  const confirm = () => { if (!task) return; if (!ownerSignature.trim()) { setMessage("請先輸入使用者簽名，SCBKR 才能閉環。"); return; } return run("確認責任鏈", () => api<TaskSummary>(`/api/tasks/${task.task_id}/confirm`, { method: "POST", body: JSON.stringify({ scbkr: task.scbkr, confirmed_by: "user", confirmation_statement: "我確認本任務 S/C/B/K/R 五維責任鏈。", signature: ownerSignature.trim() }) })).then((r: any) => { if (r?.scbkr?.signature_status === "owner_signed") setMessage(`使用者已簽名：${ownerSignature.trim().slice(0, 12)}${ownerSignature.trim().length > 12 ? "…" : ""}`); }); };
  const generate = () => task && run("開始生成", () => api<TaskSummary>(`/api/tasks/${task.task_id}/generate`, { method: "POST" }));
  const draftPatch = async () => { if (!task || locked) { setMessage("此任務已入庫或完成，不能直接修改原任務；請建立新版本或新任務。"); return; } const r = await run("產生修改草案", () => api<Record<string, any>>(`/api/tasks/${task.task_id}/scbkr/patch-draft`, { method: "POST", body: JSON.stringify({ layer: patchLayer, instruction: patchInstruction }) })); if (r?.patch) setPendingPatch(r.patch); };
  const applyPatch = () => task && pendingPatch && !locked && run("套用修改", () => api<TaskSummary>(`/api/tasks/${task.task_id}/scbkr/apply-patch`, { method: "POST", body: JSON.stringify({ patch: pendingPatch }) })).then((r: any) => { if (r?.task_id) clearOwnerSignatureForDraftChange(); setPendingPatch(null); });
  const saveDates = () => task && run("確認日期", () => api<TaskSummary>(`/api/tasks/${task.task_id}/dates`, { method: "POST", body: JSON.stringify({ event_date: eventDate, model_inferred_date: modelDate, date_source: "user", user_confirmed: Boolean(eventDate) }) }));
  const review = (decision: "pass" | "fail") => task && run(decision === "pass" ? "通過驗收" : "驗收失敗", () => api<TaskSummary>(`/api/tasks/${task.task_id}/review`, { method: "POST", body: JSON.stringify({ review_decision: decision, review_message: decision === "pass" ? "使用者通過驗收" : "建立記憶規則" }) }));
  const returnToRevision = async () => {
    if (!task || !task.scbkr || locked) return;

    const localRevision = invalidateDownstreamForRevision(task);
    setTask(localRevision);
    setStorageSuggestion(null);
    setSelectedTargets([]);
    setPendingPatch(null);
    setOwnerSignature("");

    const persisted = await run("退回修改", () =>
      api<TaskSummary>(`/api/tasks/${task.task_id}/scbkr`, {
        method: "PATCH",
        body: JSON.stringify({
          scbkr: task.scbkr,
          layer: "return_to_revision",
        }),
      })
    );

    if (persisted?.task_id) {
      setTask(invalidateDownstreamForRevision(persisted));
    }

    setMessage("草案已修改，請重新輸入使用者簽名後再確認責任鏈。舊生成、驗收與入庫資料已作廢。");
  };
  const enableModelGenerate = async () => { const r = await run("開啟模型生成權限", () => api("/api/settings/permissions", { method: "POST", body: JSON.stringify({ model_generate: true }) })); if (r) setMessage("模型生成權限已開啟"); };
  const storageSuggest = async () => { if (!task) return; const r = await run("產生入庫建議", () => api<TaskSummary>(`/api/tasks/${task.task_id}/storage-suggestion`, { method: "POST", body: JSON.stringify({}) })); setStorageSuggestion(r?.storage_suggestion || r); };
  const storageRequest = () => { if (!task) return; if (!ownerSignature.trim()) { setMessage("請先輸入使用者簽名，才能建立入庫請求或二次確認寫入。"); return; } return run("產生入庫請求", () => api<TaskSummary>(`/api/tasks/${task.task_id}/storage-request`, { method: "POST", body: JSON.stringify({ selected_targets: selectedTargets, user_decision: selectedTargets.length ? "custom" : "do_not_store", signature: ownerSignature.trim() }) })); };
  const storageConfirm = async () => { if (!task) return; if (!ownerSignature.trim()) { setMessage("請先輸入使用者簽名，才能建立入庫請求或二次確認寫入。"); return; } let current = task; if (!current.storage_plan) { const requested = await run("建立入庫計畫", () => api<TaskSummary>(`/api/tasks/${current.task_id}/storage-request`, { method: "POST", body: JSON.stringify({ selected_targets: selectedTargets, user_decision: selectedTargets.length ? "custom" : "do_not_store", signature: ownerSignature.trim() }) })); if (!requested?.task_id) { setMessage("入庫計畫建立失敗，尚未寫入資料中心。"); return; } current = requested; } const committed = await run("使用者二次確認寫入", () => api<TaskSummary>(`/api/tasks/${current.task_id}/storage-confirm`, { method: "POST", body: JSON.stringify({ storage_confirmed: true, second_confirm: true, confirmed_by: "user", signature: ownerSignature.trim(), selected_targets: selectedTargets }) })); if (committed?.task_id) { setTask(committed); setMessage("入庫完成。已寫入資料中心，可在資料中心查看寫入項目與回放紀錄。"); } };
  const testBackend = () => run("測試後端 API", async () => { const candidate = normalizeBackendUrl(selectedBackendUrl || backendUrl); const token = companionToken(); const r = await fetch(`${candidate}/health`, { headers: token ? { "X-SCBKR-Companion-Token": token } : {} }); if (!r.ok) throw new Error(await r.text()); const result = await r.json(); setActiveBackendUrl(candidate); localStorage.setItem(ACTIVE_BACKEND_STORAGE_KEY, candidate); setHealth("online"); return result; });
  const saveModelSettings = (extra: Record<string, any> = {}) => run("儲存模型設定", () => api("/api/settings/model", { method: "POST", body: JSON.stringify(modelForm.provider === "sandbox_mock_model" ? { ...modelForm, ...extra, mode: "sandbox", model_name: "sandbox_mock_model", base_url: "", api_key: "" } : { ...modelForm, ...extra }) }));
  const testModel = () => run("測試模型連線", () => api("/api/model/test", { method: "POST", body: JSON.stringify(modelForm) }));
  const clearApiKey = () => saveModelSettings({ api_key: "", clear_api_key: true });
  const switchSandbox = () => { const next = { ...modelForm, provider: "sandbox_mock_model", mode: "sandbox", base_url: "", model_name: "sandbox_mock_model", api_key: "" }; setModelForm(next); return run("切回 Sandbox", () => api("/api/model/test", { method: "POST", body: JSON.stringify(next) })); };
  const loadDataCenterSection = async (view = dataCenterView) => { const section = sectionMap[view]; const result = await api<Record<string, any>>(`/api/data-center/${section}`); setDataCenterSectionsData({ ...dataCenterSectionsData, [view]: result.items || [] }); };
  const loadData = async () => { const overview = await api<Record<string, any>>("/api/data-center/overview"); setDataCenter(overview); await loadDataCenterSection(dataCenterView); };
  const dataItems = (section: string): Record<string, any>[] => dataCenterSectionsData[section] || [];
  const makeUpdateDraft = () => selectedDataItem && setUpdateDraft({ before: itemSummary(selectedDataItem), after: `${itemSummary(selectedDataItem)}\n更新草案：${updateInstruction || "請補充更新指令。"}`, diff: `依更新指令產生草案，尚未寫入；舊資料不得無痕覆蓋。` });
  const navButton = (p: Page, label: string, icon = "") => <button className={page === p ? "active" : ""} onClick={() => { setPage(p); setDrawer(false); }}>{icon}<span>{label}</span></button>;

  const chat = <section className="chat-main" aria-label="一般聊天主視窗"><header className="chat-header"><button className="menu-button" onClick={() => setDrawer(true)}>☰</button><div><strong>聊天</strong><span>一般對話不顯示責任鏈表單、不入庫、不顯示工程除錯資訊</span></div></header><div className="message-list">{messages.map((m, i) => <div key={i} className={`message ${m.role}`}>{m.content}</div>)}{suggestion && <div className="suggestion-card"><h3>可生成 SCBKR 確認單</h3><small>將此對話轉為工作台任務</small><p>這段內容適合建立責任鏈確認單。模型可以先產生草案，之後由使用者在 Workbench 編輯與確認。</p><p><b>使用者原句：</b>{suggestion.user_original}</p><p><b>建議指令：</b>{suggestion.suggested_instruction}</p><div className="button-row"><button onClick={acceptSuggestion}>生成確認單</button><button onClick={() => setSuggestion(null)}>繼續聊天</button><button onClick={() => setSuggestion(null)}>取消</button></div></div>}</div><div className="chat-input"><textarea value={chatInput} onChange={(e: any) => setChatInput(e.target.value)} onKeyDown={(e: any) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void sendChat(); } }} placeholder="輸入訊息…（Enter 送出，Shift+Enter 換行）" /><button onClick={sendChat}>送出</button></div></section>;

  const dataCenterSignatureRequiredMessage = "請先輸入資料中心使用者簽名，才能確認更改或封存資料。";
  const dataCenterUpdateConfirm = () => {
    if (!selectedDataItem?.item_id || !updateDraft) return;
    const signature = dataCenterOwnerSignature.trim();
    if (!signature) { setMessage(dataCenterSignatureRequiredMessage); return; }
    return run("套用為新版本", () => api(`/api/data-center/items/${selectedDataItem.item_id}/update-confirm`, { method: "POST", body: JSON.stringify({ update_confirmed: true, confirmed_by: "user", signature: dataCenterOwnerSignature.trim(), change_reason: updateInstruction, new_payload: { summary: updateDraft.after } }) })).then((r: any) => { if (r) setDataCenterOwnerSignature(""); return r; });
  };
  const dataCenterDeleteConfirm = () => {
    if (!selectedDataItem?.item_id) return;
    const signature = dataCenterOwnerSignature.trim();
    if (!signature) { setMessage(dataCenterSignatureRequiredMessage); return; }
    return run("封存 / 刪除確認", () => api(`/api/data-center/items/${selectedDataItem.item_id}/delete-confirm`, { method: "POST", body: JSON.stringify({ delete_confirmed: true, confirmed_by: "user", signature: dataCenterOwnerSignature.trim(), delete_reason: updateInstruction || "使用者要求封存", mode: "archive" }) })).then((r: any) => { if (r) setDataCenterOwnerSignature(""); return r; });
  };

  const workbench = <aside className={`workbench-panel ${page === "workbench" ? "mobile-open" : ""}`} aria-label="SCBKR 工作台側欄"><div className="panel-head"><div><h2>Workbench / SCBKR 工作台</h2><p>{statusLabel(task)} · {sourceLabel}</p></div><button onClick={() => resetWorkbench("工作台已關閉 / 清空，資料中心既有資料不會被刪除。")}>關閉工作台 / X</button></div>{!task ? <section className="step-card"><p className="eyebrow">尚未建立任務</p><h3>建立責任鏈確認單</h3><p>從聊天建議或下方指令建立任務，建立後才會產生可編輯工作台。</p><label>任務指令<textarea value={taskText} onChange={(e: any) => setTaskText(e.target.value)} placeholder="輸入要建立工作台任務的內容…" /></label>{!taskText.trim() && <p className="warning-card">請先輸入任務內容。</p>}<button disabled={!taskText.trim()} onClick={createTask}>建立 SCBKR 任務 / 建立確認單</button></section> : <><section className="task-hero"><div><p className="eyebrow">任務摘要</p><h3>{humanText(task.scbkr?.S?.task_name) || task.task_name || "未命名任務"}</h3><p>原始指令：{task.raw_input || taskText}</p><p>當前階段：{statusLabel(task)}</p></div><div className="date-card"><b>日期治理</b><label>事件日期<input value={eventDate} onChange={(e: any) => setEventDate(e.target.value)} placeholder="YYYY-MM-DD" /></label><label>模型推測日期<input value={modelDate} onChange={(e: any) => setModelDate(e.target.value)} placeholder="僅供使用者確認" /></label><button onClick={saveDates}>確認日期</button></div></section><section className="step-card"><p className="eyebrow">模型草案來源</p><p>{sourceLabel}</p><p>原因：{sourceReason}</p>{task.scbkr?.draft_source === "scbkr_base_logic" && <p className="warning-card">模型未成功產生可用理解，系統依 SCBKR 基礎語法生成草案。此草案仍需使用者簽名確認。</p>}{task.scbkr?.draft_source === "draft_failed" && <p className="warning-card">草案生成失敗：請補充任務主體後重新生成草案。</p>}<div className="button-row"><button disabled={Boolean(task.confirmed) || Boolean(locked)} onClick={regenerateDraft}>重新生成草案</button><button disabled={Boolean(locked)} onClick={() => setMessage("請直接編輯 S/C/B/K/R 欄位，完成後按儲存欄位修改。")}>手動編輯</button><button disabled={Boolean(locked)} onClick={cancelTask}>取消確認單</button></div>{locked && <p className="warning-card">此任務已入庫或完成，不得直接修改原任務；請建立新版本或新任務。</p>}</section><section className="step-card"><p className="eyebrow">本次引用資料</p><div className="source-grid">{["vector", "corpus", "logic", "memory"].map((k) => <div key={k} className="mini-card"><b>{storeLabels[k]}</b><span>{((task.data_center_context?.hits || task.scbkr?.referenced_sources || []) as any[]).some((h: any) => String(h.source_store).includes(k)) ? "已引用" : "未命中"}</span></div>)}</div><h4>已採用引用</h4>{((task.data_center_context?.hits || task.scbkr?.referenced_sources || []) as any[]).length ? <div className="evidence-list">{((task.data_center_context?.hits || task.scbkr?.referenced_sources || []) as any[]).map((hit: any, i: number) => <div className="mini-card evidence-card" key={i}><b>來源庫：{storeLabels[hit.source_store] || hit.source_store || "未知"} · 狀態：{hit.status || "待確認"}</b><span>摘要：{humanText(hit.rule || hit.summary || hit.retrieval_text)}</span><span>score：{hit.score ?? "—"} · case_id：{hit.case_id ?? "—"}</span><span>storage_item_id：{hit.storage_item_id ?? "—"} · memory_rule_id：{hit.memory_rule_id ?? "—"} · task_id：{hit.task_id ?? "—"}</span><span>rule_confirmed：{String(hit.rule_confirmed ?? false)} · must_cite：{String(hit.must_cite ?? false)} · hash：{hit.hash || hit.content_hash || "—"}</span></div>)}</div> : <p className="warning-card">本次未命中與任務直接相關的已確認資料，模型不得聲稱引用既有資料。</p>}<h4>候選但未採用</h4>{((task.data_center_context?.rejected_hits || []) as any[]).length ? <div className="evidence-list">{((task.data_center_context?.rejected_hits || []) as any[]).map((hit: any, i: number) => <div className="mini-card evidence-card" key={i}><b>來源庫：{storeLabels[hit.source_store] || hit.source_store || "未知"}</b><span>{hit.status || "未採用：相關性不足"}</span><span>原因：{hit.reason || "相關性不足"}</span></div>)}</div> : <p>無候選未採用資料。</p>}<h4>衝突 / 待確認</h4><p>{((task.data_center_context?.conflicts || []) as any[]).length ? "有待確認衝突" : "無衝突。"}</p></section><section className="step-card"><p className="eyebrow">SCBKR 五張摘要卡</p>{dims.map((d) => <details key={d} className="summary-card"><summary><strong>{dimTitles[d]}</strong><span>{humanText(task.scbkr?.[d]?.[dimFieldLabels[d][0][0]] || task.scbkr?.[d]?.pending_questions?.[0]) || "待補齊"}</span><em>編輯</em></summary>{dimFieldLabels[d].map(([f, label]) => <label key={f}>{label}<textarea value={humanText(task.scbkr?.[d]?.[f])} disabled={Boolean(task.confirmed) || Boolean(locked)} onChange={(e: any) => updateField(d, f, e.target.value)} /></label>)}</details>)}</section><section className="step-card"><p className="eyebrow">請模型修改工作台</p><label>選擇修改層<select value={patchLayer} onChange={(e: any) => setPatchLayer(e.target.value as ScbkrDimensionKey)}>{dims.map((d) => <option key={d}>{d}</option>)}</select></label><label>修改指令<textarea value={patchInstruction} onChange={(e: any) => setPatchInstruction(e.target.value)} /></label><div className="button-row"><button disabled={Boolean(locked)} onClick={draftPatch}>產生修改草案</button><button disabled={!pendingPatch || Boolean(locked)} onClick={applyPatch}>套用修改</button><button disabled={!pendingPatch} onClick={() => setPendingPatch(null)}>取消</button></div>{pendingPatch && <div className="patch-card"><h4>修改草案尚未套用</h4><p>人話摘要：{pendingPatch.reason || "模型建議依照指令調整所選層級。"}</p><p>欄位差異：套用後會寫回 task.scbkr，confirmed 會變 false，generation / review / storage plan 會作廢，狀態回到等待責任鏈確認。</p></div>}</section><section className="step-card"><p className="eyebrow">使用者簽名</p><h3>使用者簽名</h3><p>此規則由使用者簽名後才成立。模型只能描述與編譯，模型不能簽名。</p><p>signature_status：{task.scbkr?.signature_status || task.scbkr?.R?.signature_status || "waiting_owner_signature"}</p>{task.scbkr?.signature_status === "owner_signed" && <p className="success-card">使用者已簽名：{ownerSignature ? `${ownerSignature.trim().slice(0, 12)}${ownerSignature.trim().length > 12 ? "…" : ""}` : "owner_signed"}</p>}<label>使用者簽名<input value={ownerSignature} disabled={Boolean(task.confirmed) || Boolean(locked)} onChange={(e: any) => setOwnerSignature(e.target.value)} placeholder="請輸入使用者簽名" /></label>{!ownerSignature.trim() && task.status === "waiting_user_confirm" && <p className="warning-card">請先輸入使用者簽名，SCBKR 才能閉環。</p>}</section><section className="step-card action-card"><p className="eyebrow">目前可操作</p><div className="button-row">{can.confirm && <><button disabled={!ownerSignature.trim()} onClick={confirm}>確認責任鏈</button><button onClick={saveFields}>儲存欄位修改</button></>}{can.generate && <button onClick={generate}>開始生成</button>}{can.review && <><button onClick={() => review("pass")}>通過驗收</button><button onClick={() => review("fail")}>驗收失敗</button></>}{can.revise && <button onClick={returnToRevision}>退回修改</button>}{can.suggest && <button onClick={storageSuggest}>產生入庫建議</button>}{can.storage && <button onClick={storageConfirm}>使用者二次確認寫入</button>}{locked && <><button onClick={() => { setPage("data-center"); void loadData(); }}>查看資料中心</button><button onClick={() => resetWorkbench()}>建立下一張確認單</button><button onClick={duplicateTask}>複製為新任務</button><button onClick={() => resetWorkbench("工作台已關閉 / 清空，資料中心既有資料不會被刪除。")}>關閉工作台</button></>}{!locked && !can.confirm && !can.generate && !can.review && !can.revise && !can.suggest && !can.storage && <button disabled>等待下一步</button>}</div></section>{!locked && (storageSuggestion || task.storage_suggestion) && <section className="step-card"><p className="eyebrow">入庫建議</p><p>模型只能建議，使用者決定；不建議項目仍可手動選擇。尚未實體寫入。按下使用者二次確認寫入後，才會寫入資料中心。</p><div className="storage-options">{["vector", "corpus", "logic", "memory"].map((k) => { const s = (storageSuggestion || task.storage_suggestion)?.suggestions?.[k] || {}; const recommended = s.recommended !== false; const selected = selectedTargets.includes(k); return <button key={k} className={`storage-card ${recommended ? "recommended" : "not-recommended"} ${selected ? "selected" : "unselected"}`} onClick={() => setSelectedTargets(selected ? selectedTargets.filter((x) => x !== k) : [...selectedTargets, k])}><b>{selected ? "✓" : "○"} {storeLabels[k]}</b><span className={`storage-badge ${recommended ? "green" : "red"}`}>{recommended ? "建議" : "不建議"}</span><small>{s.reason || "由使用者二次確認是否寫入。"}</small></button>; })}</div><details><summary>進階操作</summary><button onClick={storageRequest}>產生入庫請求</button></details></section>}<section className="step-card"><p className="eyebrow">模型回覆 / 生成結果</p><div className="model-output">{resultText(task)}</div></section>{task.storage_result && <section className="step-card storage-result"><p className="eyebrow">入庫結果</p><h3>入庫完成</h3><p>written_targets：{humanText(task.storage_result.written_targets)}</p><p>skipped_targets：{humanText(task.storage_result.skipped_targets)}</p><p>skipped_reasons：{humanText(task.storage_result.skipped_reasons)}</p><p>already_committed：{String(task.storage_result.already_committed ?? false)}</p><div className="button-row"><button onClick={() => { setPage("data-center"); void loadData(); }}>查看資料中心</button><button onClick={() => resetWorkbench()}>建立下一張確認單</button><button onClick={duplicateTask}>複製為新任務</button><button onClick={() => resetWorkbench("工作台已關閉 / 清空，資料中心既有資料不會被刪除。")}>關閉 / 清空工作台</button></div>{(task.storage_result.written_items || []).map((item: any, i: number) => <div className="mini-card" key={i}><b>written_items #{i + 1}</b><span>hash / content_hash：{item.hash || item.content_hash || "—"}</span><span>path / relative_path：{item.path || item.relative_path || "—"}</span><span>stored_at：{item.stored_at || "—"}</span></div>)}</section>}<details className="audit-link"><summary>審計資料（預設收合）</summary><JsonBlock value={task} /></details></>}</aside>;

  return <main className="app-shell"><div className="mobile-drawer-backdrop" hidden={!drawer} onClick={() => setDrawer(false)} /><nav className={`mobile-drawer ${drawer ? "open" : ""}`}>{navItems.map(([p, l, i]) => navButton(p, l, i))}<button onClick={() => setDrawer(false)}>關閉</button></nav><nav className="side-nav"><b>SCBKR<br />本地責任鏈模型</b>{navItems.map(([p, l, i]) => navButton(p, l, i))}<span className="user-pill">使用者<br />Online</span></nav><section className="top-status-bar"><span>後端 API：{health} + {activeBackendUrl}</span><span>模型狀態：{model?.provider ?? "未設定"} + {(model?.enabled && model?.last_test_status === "success") ? "connected" : "not connected"} + {model?.model_name || "未設定"}</span><span>執行環境：{runtimeLabel}</span><span>{message}</span></section>{page === "chat" || page === "workbench" ? <div className="split-layout">{chat}{workbench}</div> : null}{page === "data-center" && <section className="panel data-center-panel"><h1>資料中心</h1><button onClick={loadData}>讀回資料中心</button><label>資料中心使用者簽名<input value={dataCenterOwnerSignature} onChange={(e: any) => setDataCenterOwnerSignature(e.target.value)} placeholder="資料中心使用者簽名" /></label><div className="data-grid">{dataCenterSections.map((x) => <button className={dataCenterView === x ? "mini-card selected" : "mini-card"} key={x} onClick={() => { setDataCenterView(x); setSelectedDataItem(null); void loadDataCenterSection(x); }}>{x}</button>)}</div><h2>{dataCenterView}列表</h2>{dataItems(dataCenterView).length === 0 ? <p className="warning-card">目前尚無資料。完成驗收並二次確認寫入後，資料才會出現在這裡。</p> : <div className="data-list">{dataItems(dataCenterView).map((item, i) => <div className="mini-card" key={i}><b>task_id：{itemValue(item, ["task_id", "id"])}</b><span>狀態：{itemValue(item, ["status", "review_status", "target"])}</span><span>摘要：{itemSummary(item)}</span><span>target / source_store：{itemValue(item, ["target", "source_store"])}</span><span>hash / content_hash：{itemValue(item, ["hash", "content_hash"])}</span><span>path / relative_path：{itemValue(item, ["path", "relative_path"])}</span><span>stored_at / created_at / updated_at：{itemValue(item, ["stored_at", "created_at", "updated_at"])}</span><button onClick={() => { setSelectedDataItem(item); setUpdateDraft(null); }}>查看詳情</button></div>)}</div>}{selectedDataItem && <section className="step-card detail-card"><h2>單筆詳情</h2><p>所屬任務 task_id：{itemValue(selectedDataItem, ["task_id", "id"])}</p><p>寫入目標：{itemValue(selectedDataItem, ["target", "source_store"])}</p><p>內容摘要：{itemSummary(selectedDataItem)}</p><p>驗收狀態：{itemValue(selectedDataItem, ["review_status", "status"])}</p><p>寫入時間 stored_at / created_at：{itemValue(selectedDataItem, ["stored_at", "created_at"])}</p><p>hash：{itemValue(selectedDataItem, ["hash", "content_hash"])}</p><p>path / relative_path：{itemValue(selectedDataItem, ["path", "relative_path"])}</p><p>replay / ledger 資訊：{humanText(selectedDataItem.ledger_event_id || selectedDataItem.replay_id || selectedDataItem.ledger)}</p><p>可回放狀態：{String(selectedDataItem.replayable ?? Boolean(selectedDataItem.ledger_event_id || selectedDataItem.replay_id))}</p><div className="update-draft"><h3>請模型產生更新草案</h3><label>更新指令<textarea value={updateInstruction} onChange={(e: any) => setUpdateInstruction(e.target.value)} placeholder="描述要如何更新此資料項目…" /></label><div className="button-row"><button onClick={makeUpdateDraft}>產生更新草案</button><button disabled={!updateDraft || !dataCenterOwnerSignature.trim()} onClick={dataCenterUpdateConfirm}>套用為新版本</button><button disabled={!dataCenterOwnerSignature.trim()} onClick={dataCenterDeleteConfirm}>建立刪除確認並封存</button><button onClick={() => { setUpdateDraft(null); setUpdateInstruction(""); }}>取消</button></div>{updateDraft && <div className="patch-card"><h4>更新草案（尚未覆蓋原資料）</h4><p>修改前：{updateDraft.before}</p><p>修改後：{updateDraft.after}</p><p>差異：{updateDraft.diff}</p><p>目前僅產生更新草案，套用為新版本需要後續版本化寫入接口。</p></div>}</div><details><summary>審計資料明細</summary><JsonBlock value={selectedDataItem} /></details></section>}{dataCenter && <details><summary>審計資料明細</summary><JsonBlock value={dataCenter} /></details>}</section>}{page === "model-settings" && <section className="panel model-settings"><h1>模型設定</h1><p>設定後端 API 與模型連線；API Key 以遮罩顯示，欄位留白會保留舊值。</p><h2>後端 API URL</h2><label>後端 API URL<input value={backendUrl} onChange={(e: any) => { setBackendUrl(e.target.value); setSelectedBackendUrl(e.target.value); }} placeholder="http://127.0.0.1:8787" /></label><button onClick={testBackend}>測試後端 API</button><h2>模型連線</h2><label>Provider<select value={modelForm.provider} onChange={(e: any) => setModelForm({ ...modelForm, provider: e.target.value, mode: e.target.value === "openai_compatible" ? "external" : e.target.value === "sandbox_mock_model" ? "sandbox" : "local" })}><option value="sandbox_mock_model">Sandbox</option><option value="lm_studio">LM Studio</option><option value="ollama">Ollama</option><option value="openai_compatible">OpenAI-compatible</option></select></label><label>Model Base URL<input value={modelForm.base_url} onChange={(e: any) => setModelForm({ ...modelForm, base_url: e.target.value })} placeholder="http://127.0.0.1:1234/v1" /></label><label>Model Name<input value={modelForm.model_name} onChange={(e: any) => setModelForm({ ...modelForm, model_name: e.target.value })} placeholder="model name" /></label><label>API Key（目前：{model?.api_key || "空"}）<input type="password" value={modelForm.api_key} onChange={(e: any) => setModelForm({ ...modelForm, api_key: e.target.value })} placeholder="留白保留舊 key" /></label><div className="button-row"><button onClick={() => saveModelSettings()}>儲存設定</button><button onClick={testModel}>測試模型連線</button><button onClick={clearApiKey}>清除 API Key</button><button onClick={switchSandbox}>切回 Sandbox</button><button onClick={enableModelGenerate}>開啟模型生成權限</button></div></section>}{page === "audit" && <section className="panel"><h1>審計資料</h1><p>Audit Timeline：任務建立 → 模型草案生成 → 草案來源說明 → 使用者修改欄位 → 使用者確認責任鏈 → 開始生成 → 驗收通過 / 失敗 → 產生入庫建議 → 建立入庫計畫 → 使用者二次確認 → 實體寫入完成 → 寫入哪些庫 → 查詢 Data Center → 引用哪些資料 → 更改 / 刪除確認單 → 更新 / 封存資料。</p><ul><li>任務建立：{(task as any)?.created_at || task?.task_id || "尚未選擇任務"}</li><li>模型草案生成：{task?.scbkr ? sourceLabel : "尚未生成"}</li><li>草案來源：{sourceLabel}</li><li>目前狀態：{statusLabel(task)}</li></ul><details><summary>審計資料明細</summary><JsonBlock value={{ task, model }} /></details></section>}</main>;
}
