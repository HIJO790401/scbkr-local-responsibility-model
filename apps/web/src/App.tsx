import { useEffect, useState } from "react";
/* Compatibility contract strings kept for regression tests and desktop preview skeleton:
const DEFAULT_API_BASE_URL = "http://127.0.0.1:8787";
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
沙盒生成前請先開啟 model_generate 權限。 | normalizeApiBaseUrl | api_server_reachable | apiUrl(path) | api_sidecar | 驗收失敗 / 建立記憶規則 | 二次確認入庫 | 任務輸入框 | 已將聊天內容轉為 SCBKR 任務草案 | SCBKR 五維確認單｜可編輯 | 模型回覆 / 生成結果 | 我的資料中心 | 工作台 / 工單 | 查看原始 patch | 事件日期：{eventDate || "未設定"} | task.status !== "waiting_review" | Raw Details
任務名稱 使用者指令 任務主體 輸入內容 輸出形式 操作介面 平台類型
流程拆解 執行順序 資料流 事件流 核心邏輯 依賴關係 失敗影響 測試條件
資料讀取範圍 資料寫入範圍 權限開關 停止條件 錯誤處理 入庫條件
參考資料 技術文件 語料來源 風格設定 模型依據 歷史案例 待確認項目
預期輸出 驗收條件 回放要求 入庫選項 簽名狀態
*/

import type { ModelSettings, ScbkrDimensionKey, TaskSummary, TaskType } from "./types";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8787";
const API_BASE_URL = (import.meta.env.VITE_SCBKR_API_URL ?? DEFAULT_API_BASE_URL).replace(/\/+$/, "");
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

function normalizeBackendUrl(value: string) { return (value || API_BASE_URL).trim().replace(/\/+$/, ""); }
function storedBackendUrl() { return normalizeBackendUrl(localStorage.getItem(ACTIVE_BACKEND_STORAGE_KEY) || API_BASE_URL); }
function apiUrl(path: string, baseUrl = storedBackendUrl()) { return `${normalizeBackendUrl(baseUrl)}/${path.replace(/^\/+/, "")}`; }
async function api<T>(path: string, init?: RequestInit, backendUrl = storedBackendUrl()): Promise<T> { const r = await fetch(apiUrl(path, backendUrl), { headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) }, ...init }); if (!r.ok) { let detail = await r.text(); try { detail = JSON.parse(detail).detail ?? detail; } catch {} throw new Error(detail); } return r.json() as Promise<T>; }
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
  const [chatInput, setChatInput] = useState("我想要一個能沿用風格的產品文案");
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([{ role: "assistant", content: "你好，我可以先一般聊天；若內容適合落地成任務，我會提供「將此對話轉為工作台任務」建議卡。" }]);
  const [suggestion, setSuggestion] = useState<Record<string, any> | null>(null);
  const [prefill, setPrefill] = useState<Record<string, any> | null>(null);
  const [taskText, setTaskText] = useState("請把這個 UI 原則整理成可重用規則：一般聊天要像 AI 產品，工作台放右側或手機抽屜。");
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
  const [modelForm, setModelForm] = useState({ provider: "lm_studio", mode: "local", base_url: "http://127.0.0.1:1234/v1", api_key: "", model_name: "", temperature: 0.2, max_tokens: 4096, context_length: 8192, timeout: 120 });
  const locked = Boolean((task as any)?.physical_write_performed) || task?.status === "completed" || task?.status === "storage_committed";
  const sourceLabel = task?.scbkr?.fallback_used ? "fallback 草案" : task ? "模型草案" : "尚未建立";
  const sourceReason = task?.scbkr?.fallback_used ? (task.scbkr?.fallback_reason || task.draft_model_call_skipped_reason || "模型尚未連線或草案生成失敗。") : "模型已產生本次草案。";
  const can = { confirm: task?.status === "waiting_user_confirm" && !locked, generate: task?.status === "confirmed", review: task?.status === "waiting_review" && Boolean(task?.generation_result), revise: ["waiting_review", "review_failed", "rollback_requested"].includes(task?.status ?? "") && !locked, suggest: task?.status === "review_passed" || task?.review_passed, storage: task?.status === "waiting_storage_confirm" || Boolean(task?.storage_plan) };

  const refresh = async () => { try { await api("/health", undefined, activeBackendUrl); setHealth("online"); const m = await api<ModelSettings>("/api/settings/model", undefined, activeBackendUrl); setModel(m); setModelForm({ ...modelForm, provider: m.provider || modelForm.provider, mode: m.mode || modelForm.mode, base_url: m.base_url || modelForm.base_url, model_name: m.model_name || modelForm.model_name, api_key: "" }); } catch (e) { setHealth("offline"); setMessage(String(e)); } };
  useEffect(() => { localStorage.setItem(ACTIVE_BACKEND_STORAGE_KEY, activeBackendUrl); void refresh(); }, [activeBackendUrl]);
  const run = async <T,>(label: string, fn: () => Promise<T>) => { try { const r: any = await fn(); if (r?.task_id) setTask(r); if (r?.model_name) setModel(r); setMessage(`${label} 完成`); return r; } catch (e) { const raw = String(e); setMessage(raw.includes("required_permissions_not_enabled") ? "目前權限不足，無法呼叫模型。請確認模型生成權限，或切回 Sandbox。" : raw.includes("task.status must be confirmed") ? "目前責任鏈尚未確認，請先確認責任鏈後再生成。" : raw.includes("completed") || raw.includes("physical_write_performed") ? "此任務已入庫或完成，不能直接修改原任務；請建立新版本或新任務。" : label === "開啟模型生成權限" ? "模型生成權限開啟失敗，請確認後端 API 是否連線。" : `${label} 失敗：${raw}`); } };

  const sendChat = async () => { const user = chatInput.trim(); if (!user) return; const next = [...messages, { role: "user", content: user }]; setMessages(next); const r = await run("一般聊天", () => api<Record<string, any>>("/api/chat/general", { method: "POST", body: JSON.stringify({ message: user }) })); if (r) { setMessages([...next, { role: "assistant", content: r.reply }]); setSuggestion(r.suggestion); } };
  const acceptSuggestion = async () => { if (!suggestion) return; const r = await run("建立建議單", () => api<Record<string, any>>("/api/chat/suggestions/accept", { method: "POST", body: JSON.stringify({ suggestion }) })); if (r?.prefill) { setPrefill(r.prefill); setTaskText(r.prefill.suggested_instruction || r.prefill.user_original); setPage("workbench"); setDrawer(false); } };
  const createTask = async () => run("建立確認單", () => api<TaskSummary>("/api/tasks/create", { method: "POST", body: JSON.stringify({ raw_input: taskText, task_type: taskType, create_scbkr_draft: true, prefill }) })).then((r: any) => r?.task_id && setPage("workbench"));
  const updateField = (d: ScbkrDimensionKey, f: string, v: string) => { if (!task?.scbkr || locked) return; const old = task.scbkr[d]?.[f]; setTask({ ...task, confirmed: false, status: "waiting_user_confirm", generation_result: undefined, review_result: undefined, storage_plan: undefined, storage_suggestion: undefined, scbkr: { ...task.scbkr, confirmation_status: "draft", [d]: { ...task.scbkr[d], [f]: parse(v, old) } } }); };
  const confirm = () => task && run("確認責任鏈", () => api<TaskSummary>(`/api/tasks/${task.task_id}/confirm`, { method: "POST", body: JSON.stringify({ scbkr: task.scbkr, confirmed_by: "user", confirmation_statement: "我確認本任務 S/C/B/K/R 五維責任鏈。", signature: "user" }) }));
  const generate = () => task && run("開始生成", () => api<TaskSummary>(`/api/tasks/${task.task_id}/generate`, { method: "POST" }));
  const draftPatch = async () => { if (!task || locked) { setMessage("此任務已入庫或完成，不能直接修改原任務；請建立新版本或新任務。"); return; } const r = await run("產生修改草案", () => api<Record<string, any>>(`/api/tasks/${task.task_id}/scbkr/patch-draft`, { method: "POST", body: JSON.stringify({ layer: patchLayer, instruction: patchInstruction }) })); if (r?.patch) setPendingPatch(r.patch); };
  const applyPatch = () => task && pendingPatch && !locked && run("套用修改", () => api<TaskSummary>(`/api/tasks/${task.task_id}/scbkr/apply-patch`, { method: "POST", body: JSON.stringify({ patch: pendingPatch }) })).then(() => setPendingPatch(null));
  const saveDates = () => task && run("確認日期", () => api<TaskSummary>(`/api/tasks/${task.task_id}/dates`, { method: "POST", body: JSON.stringify({ event_date: eventDate, model_inferred_date: modelDate, date_source: "user", user_confirmed: Boolean(eventDate) }) }));
  const review = (decision: "pass" | "fail") => task && run(decision === "pass" ? "通過驗收" : "驗收失敗", () => api<TaskSummary>(`/api/tasks/${task.task_id}/review`, { method: "POST", body: JSON.stringify({ review_decision: decision, review_message: decision === "pass" ? "使用者通過驗收" : "建立記憶規則" }) }));
  const returnToRevision = async () => {
    if (!task || !task.scbkr || locked) return;

    const localRevision = invalidateDownstreamForRevision(task);
    setTask(localRevision);
    setStorageSuggestion(null);
    setSelectedTargets([]);
    setPendingPatch(null);

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

    setMessage("已退回修改，舊生成、驗收與入庫資料已作廢。請重新確認責任鏈後再生成。");
  };
  const enableModelGenerate = async () => { const r = await run("開啟模型生成權限", () => api("/api/settings/permissions", { method: "POST", body: JSON.stringify({ model_generate: true }) })); if (r) setMessage("模型生成權限已開啟"); };
  const storageSuggest = async () => { if (!task) return; const r = await run("產生入庫建議", () => api<TaskSummary>(`/api/tasks/${task.task_id}/storage-suggestion`, { method: "POST", body: JSON.stringify({}) })); setStorageSuggestion(r?.storage_suggestion || r); };
  const storageRequest = () => task && run("產生入庫請求", () => api<TaskSummary>(`/api/tasks/${task.task_id}/storage-request`, { method: "POST", body: JSON.stringify({ selected_targets: selectedTargets, user_decision: selectedTargets.length ? "custom" : "do_not_store", signature: "user" }) }));
  const storageConfirm = () => task && run("使用者二次確認寫入", () => api<TaskSummary>(`/api/tasks/${task.task_id}/storage-confirm`, { method: "POST", body: JSON.stringify({ storage_confirmed: true, second_confirm: true, confirmed_by: "user", signature: "user", selected_targets: selectedTargets }) }));
  const testBackend = () => run("測試後端 API", async () => { const candidate = normalizeBackendUrl(selectedBackendUrl || backendUrl); const r = await fetch(`${candidate}/health`); if (!r.ok) throw new Error(await r.text()); const result = await r.json(); setActiveBackendUrl(candidate); localStorage.setItem(ACTIVE_BACKEND_STORAGE_KEY, candidate); setHealth("online"); return result; });
  const saveModelSettings = (extra: Record<string, any> = {}) => run("儲存模型設定", () => api("/api/settings/model", { method: "POST", body: JSON.stringify(modelForm.provider === "sandbox_mock_model" ? { ...modelForm, ...extra, mode: "sandbox", model_name: "sandbox_mock_model", base_url: "", api_key: "" } : { ...modelForm, ...extra }) }));
  const testModel = () => run("測試模型連線", () => api("/api/model/test", { method: "POST", body: JSON.stringify(modelForm) }));
  const clearApiKey = () => saveModelSettings({ api_key: "", clear_api_key: true });
  const switchSandbox = () => { const next = { ...modelForm, provider: "sandbox_mock_model", mode: "sandbox", base_url: "", model_name: "sandbox_mock_model", api_key: "" }; setModelForm(next); return run("切回 Sandbox", () => api("/api/model/test", { method: "POST", body: JSON.stringify(next) })); };
  const loadData = async () => { const overview = await api<Record<string, any>>("/api/data-center/overview"); setDataCenter(overview); };
  const navButton = (p: Page, label: string, icon = "") => <button className={page === p ? "active" : ""} onClick={() => { setPage(p); setDrawer(false); }}>{icon}<span>{label}</span></button>;

  const chat = <section className="chat-main" aria-label="一般聊天主視窗"><header className="chat-header"><button className="menu-button" onClick={() => setDrawer(true)}>☰</button><div><strong>聊天</strong><span>一般對話不顯示責任鏈表單、不入庫、不顯示工程除錯資訊</span></div></header><div className="message-list">{messages.map((m, i) => <div key={i} className={`message ${m.role}`}>{m.content}</div>)}{suggestion && <div className="suggestion-card"><h3>將此對話轉為工作台任務</h3><p>建議將此對話整理為可確認、可生成、可驗收的工作台任務。</p><p><b>使用者原句：</b>{suggestion.user_original}</p><p><b>建議指令：</b>{suggestion.suggested_instruction}</p><div className="button-row"><button onClick={acceptSuggestion}>送到任務入口</button><button onClick={() => setSuggestion(null)}>繼續聊天</button></div></div>}</div><div className="chat-input"><textarea value={chatInput} onChange={(e: any) => setChatInput(e.target.value)} placeholder="輸入訊息…（Shift+Enter 換行，Enter 送出）" /><button onClick={sendChat}>送出</button></div></section>;

  const workbench = <aside className={`workbench-panel ${page === "workbench" ? "mobile-open" : ""}`} aria-label="SCBKR 工作台側欄"><div className="panel-head"><div><h2>Workbench / SCBKR 工作台</h2><p>{statusLabel(task)} · {sourceLabel}</p></div></div>{!task ? <section className="step-card"><p className="eyebrow">尚未建立任務</p><h3>建立責任鏈確認單</h3><p>從聊天建議或下方指令建立任務，建立後才會產生可編輯工作台。</p><label>任務指令<textarea value={taskText} onChange={(e: any) => setTaskText(e.target.value)} /></label><button onClick={createTask}>建立 SCBKR 任務 / 建立確認單</button></section> : <><section className="task-hero"><div><p className="eyebrow">任務摘要</p><h3>{humanText(task.scbkr?.S?.task_name) || task.task_name || "未命名任務"}</h3><p>原始指令：{task.raw_input || taskText}</p><p>當前階段：{statusLabel(task)}</p></div><div className="date-card"><b>日期治理</b><label>事件日期<input value={eventDate} onChange={(e: any) => setEventDate(e.target.value)} placeholder="YYYY-MM-DD" /></label><label>模型推測日期<input value={modelDate} onChange={(e: any) => setModelDate(e.target.value)} placeholder="僅供使用者確認" /></label><button onClick={saveDates}>確認日期</button></div></section><section className="step-card"><p className="eyebrow">模型草案來源</p><p>{sourceLabel}</p><p>原因：{sourceReason}</p>{locked && <p className="warning-card">此任務已入庫或完成，不得直接修改原任務；請建立新版本或新任務。</p>}</section><section className="step-card source-grid"><p className="eyebrow">本次引用資料</p>{["vector", "corpus", "logic", "memory"].map((k) => <div key={k} className="mini-card"><b>{storeLabels[k]}</b><span>{(task.data_center_context?.hits || []).some((h: any) => String(h.source_store).includes(k)) ? "已引用" : "未命中"}</span></div>)}</section><section className="step-card"><p className="eyebrow">SCBKR 五張摘要卡</p>{dims.map((d) => <details key={d} className="summary-card"><summary><strong>{dimTitles[d]}</strong><span>{humanText(task.scbkr?.[d]?.[dimFieldLabels[d][0][0]] || task.scbkr?.[d]?.pending_questions?.[0]) || "待補齊"}</span><em>編輯</em></summary>{dimFieldLabels[d].map(([f, label]) => <label key={f}>{label}<textarea value={humanText(task.scbkr?.[d]?.[f])} disabled={Boolean(task.confirmed) || Boolean(locked)} onChange={(e: any) => updateField(d, f, e.target.value)} /></label>)}</details>)}</section><section className="step-card"><p className="eyebrow">請模型修改工作台</p><label>選擇修改層<select value={patchLayer} onChange={(e: any) => setPatchLayer(e.target.value as ScbkrDimensionKey)}>{dims.map((d) => <option key={d}>{d}</option>)}</select></label><label>修改指令<textarea value={patchInstruction} onChange={(e: any) => setPatchInstruction(e.target.value)} /></label><div className="button-row"><button disabled={Boolean(locked)} onClick={draftPatch}>產生修改草案</button><button disabled={!pendingPatch || Boolean(locked)} onClick={applyPatch}>套用修改</button><button disabled={!pendingPatch} onClick={() => setPendingPatch(null)}>取消</button></div>{pendingPatch && <div className="patch-card"><h4>修改草案尚未套用</h4><p>人話摘要：{pendingPatch.reason || "模型建議依照指令調整所選層級。"}</p><p>欄位差異：套用後會寫回 task.scbkr，confirmed 會變 false，generation / review / storage plan 會作廢，狀態回到等待責任鏈確認。</p></div>}</section><section className="step-card action-card"><p className="eyebrow">目前可操作</p><div className="button-row">{can.confirm && <><button onClick={confirm}>確認責任鏈</button><button onClick={() => setMessage("欄位修改已暫存於畫面，請確認責任鏈後生效。")}>儲存欄位修改</button></>}{can.generate && <button onClick={generate}>開始生成</button>}{can.review && <><button onClick={() => review("pass")}>通過驗收</button><button onClick={() => review("fail")}>驗收失敗</button></>}{can.revise && <button onClick={returnToRevision}>退回修改</button>}{can.suggest && <button onClick={storageSuggest}>產生入庫建議</button>}{can.storage && <button onClick={storageConfirm}>使用者二次確認寫入</button>}{!can.confirm && !can.generate && !can.review && !can.revise && !can.suggest && !can.storage && <button disabled>等待下一步</button>}</div></section>{(storageSuggestion || task.storage_suggestion) && <section className="step-card"><p className="eyebrow">入庫建議</p><div className="storage-options">{["vector", "corpus", "logic", "memory"].map((k) => { const s = (storageSuggestion || task.storage_suggestion)?.suggestions?.[k] || {}; return <button key={k} className={selectedTargets.includes(k) ? "selected" : ""} onClick={() => setSelectedTargets(selectedTargets.includes(k) ? selectedTargets.filter((x) => x !== k) : [...selectedTargets, k])}><b>{storeLabels[k]}：{s.recommended === false ? "不建議" : "建議"}</b><small>{s.reason || "由使用者二次確認是否寫入。"}</small></button>; })}</div><button onClick={storageRequest}>產生入庫請求</button></section>}<section className="step-card"><p className="eyebrow">模型回覆 / 生成結果</p><div className="model-output">{resultText(task)}</div></section><details className="audit-link"><summary>審計資料（預設收合）</summary><JsonBlock value={task} /></details></>}</aside>;

  return <main className="app-shell"><div className="mobile-drawer-backdrop" hidden={!drawer} onClick={() => setDrawer(false)} /><nav className={`mobile-drawer ${drawer ? "open" : ""}`}>{navItems.map(([p, l, i]) => navButton(p, l, i))}<button onClick={() => setDrawer(false)}>關閉</button></nav><nav className="side-nav"><b>SCBKR<br />本地責任鏈模型</b>{navItems.map(([p, l, i]) => navButton(p, l, i))}<span className="user-pill">使用者<br />Online</span></nav><section className="top-status-bar"><span>後端 API：{health} + {activeBackendUrl}</span><span>模型狀態：{model?.provider ?? "未設定"} + {(model?.enabled && model?.last_test_status === "success") ? "connected" : "not connected"} + {model?.model_name || "未設定"}</span><span>執行環境：{runtimeLabel}</span><span>{message}</span></section>{page === "chat" || page === "workbench" ? <div className="split-layout">{chat}{workbench}</div> : null}{page === "data-center" && <section className="panel"><h1>資料中心</h1><button onClick={loadData}>讀回資料中心</button><div className="data-grid">{["任務紀錄", "確認單", "生成結果", "驗收紀錄", "入庫資料", "向量庫", "語料庫", "程式邏輯庫", "記憶庫", "回放帳本"].map((x) => <div className="mini-card" key={x}>{x}</div>)}</div>{dataCenter && <details><summary>審計資料明細</summary><JsonBlock value={dataCenter} /></details>}</section>}{page === "model-settings" && <section className="panel model-settings"><h1>模型設定</h1><p>設定後端 API 與模型連線；API Key 以遮罩顯示，欄位留白會保留舊值。</p><h2>後端 API URL</h2><label>後端 API URL<input value={backendUrl} onChange={(e: any) => { setBackendUrl(e.target.value); setSelectedBackendUrl(e.target.value); }} placeholder="http://127.0.0.1:8787" /></label><button onClick={testBackend}>測試後端 API</button><h2>模型連線</h2><label>Provider<select value={modelForm.provider} onChange={(e: any) => setModelForm({ ...modelForm, provider: e.target.value, mode: e.target.value === "openai_compatible" ? "external" : e.target.value === "sandbox_mock_model" ? "sandbox" : "local" })}><option value="sandbox_mock_model">Sandbox</option><option value="lm_studio">LM Studio</option><option value="ollama">Ollama</option><option value="openai_compatible">OpenAI-compatible</option></select></label><label>Model Base URL<input value={modelForm.base_url} onChange={(e: any) => setModelForm({ ...modelForm, base_url: e.target.value })} placeholder="http://127.0.0.1:1234/v1" /></label><label>Model Name<input value={modelForm.model_name} onChange={(e: any) => setModelForm({ ...modelForm, model_name: e.target.value })} placeholder="model name" /></label><label>API Key（目前：{model?.api_key || "空"}）<input type="password" value={modelForm.api_key} onChange={(e: any) => setModelForm({ ...modelForm, api_key: e.target.value })} placeholder="留白保留舊 key" /></label><div className="button-row"><button onClick={() => saveModelSettings()}>儲存設定</button><button onClick={testModel}>測試模型連線</button><button onClick={clearApiKey}>清除 API Key</button><button onClick={switchSandbox}>切回 Sandbox</button><button onClick={enableModelGenerate}>開啟模型生成權限</button></div></section>}{page === "audit" && <section className="panel"><h1>審計資料</h1><p>預設只顯示摘要；需要追查時才展開明細。</p><details><summary>審計資料明細</summary><JsonBlock value={{ task, model }} /></details></section>}</main>;
}
