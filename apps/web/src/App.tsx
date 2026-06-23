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
confirmed=false：請先確認責任鏈，模型不可執行。
只整理不入庫 | 使用者按下建立確認單後才建立 task | 已預填 Chat / 任務入口；尚未建立 task，請確認後按建立確認單。

沙盒生成前請先開啟 model_generate 權限。
normalizeApiBaseUrl
api_server_reachable
clear_api_key: true
任務輸入框
<details><summary>點擊展開 JSON</summary>
disabled={!task?.confirmed}

apiUrl(path)
api_sidecar
清除 API Key
已將聊天內容轉為 SCBKR 任務草案
SCBKR 五維確認單｜可編輯
result?.content ?? result?.generated_text

onChange={(e: any) => updateField(dim, field.key, e.target.value)}
模型回覆 / 生成結果

任務名稱 使用者指令 任務主體 輸入內容 輸出形式 操作介面 平台類型
我的資料中心

流程拆解 執行順序 資料流 事件流 核心邏輯 依賴關係 失敗影響 測試條件
資料讀取範圍 資料寫入範圍 權限開關 停止條件 錯誤處理 入庫條件
參考資料 技術文件 語料來源 風格設定 模型依據 歷史案例 待確認項目
預期輸出 驗收條件 回放要求 入庫選項 簽名狀態
*/

import type { ModelSettings, ScbkrDimensionKey, TaskSummary, TaskType } from "./types";

const API_BASE_URL = (import.meta.env.VITE_SCBKR_API_URL ?? "http://127.0.0.1:8787").replace(/\/+$/, "");
type Page = "chat" | "workbench" | "data-center" | "model-settings" | "audit";
const dims: ScbkrDimensionKey[] = ["S", "C", "B", "K", "R"];
const dimTitles: Record<ScbkrDimensionKey, string> = { S: "S｜任務是什麼", C: "C｜怎麼做", B: "B｜哪些不能做", K: "K｜依據與風格", R: "R｜怎麼驗收與入庫" };
const dimFields: Record<ScbkrDimensionKey, string[]> = { S: ["task_name", "user_instruction", "task_subject", "input_content", "output_format", "interface_type", "platform_type"], C: ["flow_steps", "execution_order", "data_flow", "event_flow", "core_logic", "dependencies", "failure_impact", "test_conditions"], B: ["data_read_scope", "data_write_scope", "local_scope", "external_scope", "permission_switches", "stop_conditions", "error_handling", "storage_conditions"], K: ["references", "technical_docs", "style_settings", "framework_choice", "model_basis", "source_credibility"], R: ["expected_outputs", "acceptance_criteria", "ledger_requirements", "storage_options", "signature_status", "review_status", "replay_requirements"] };

async function api<T>(path: string, init?: RequestInit): Promise<T> { const r = await fetch(`${API_BASE_URL}/${path.replace(/^\/+/, "")}`, { headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) }, ...init }); if (!r.ok) { let detail = await r.text(); try { detail = JSON.parse(detail).detail ?? detail; } catch {} throw new Error(detail); } return r.json() as Promise<T>; }
const text = (v: any) => Array.isArray(v) ? v.join("\n") : typeof v === "object" && v ? JSON.stringify(v, null, 2) : String(v ?? "");
const parse = (value: string, old: any) => Array.isArray(old) ? value.split("\n").map((x) => x.trim()).filter(Boolean) : typeof old === "object" && old ? (() => { try { return JSON.parse(value); } catch { return value; } })() : value;
const resultText = (task: TaskSummary | null) => String(task?.generation_result?.content ?? task?.generation_result?.generated_text ?? "尚未生成。確認責任鏈後才能開始生成。");
const statusLabel = (task: TaskSummary | null) => !task ? "尚未建立 SCBKR 任務" : task.status === "waiting_user_confirm" ? "等待責任鏈確認" : task.status === "confirmed" ? "已確認責任鏈，可開始生成" : task.status === "waiting_review" ? "等待使用者驗收" : task.status === "review_passed" ? "驗收通過，可產生入庫建議" : task.status === "waiting_storage_confirm" ? "等待二次確認入庫" : task.status === "storage_committed" || task.status === "completed" ? "已入庫 / 已完成" : task.status;

function JsonBlock({ value }: { value: unknown }) { return <pre className="json-block raw-json">{JSON.stringify(value, null, 2)}</pre>; }

export default function App() {
  const [page, setPage] = useState<Page>("chat");
  const [drawer, setDrawer] = useState(false);
  const [workbenchOpen, setWorkbenchOpen] = useState(false);
  const [health, setHealth] = useState("checking");
  const [backendUrl, setBackendUrl] = useState(API_BASE_URL);
  const runtimeLabel = backendUrl.includes("127.0.0.1") || backendUrl.includes("localhost") ? "desktop sidecar" : "mobile remote";
  const [model, setModel] = useState<ModelSettings | null>(null);
  const [message, setMessage] = useState("");
  const [chatInput, setChatInput] = useState("你好");
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([{ role: "assistant", content: "你好，我可以一般聊天；需要時我只會提出建立 SCBKR 規則 / 任務的建議卡片。" }]);
  const [suggestion, setSuggestion] = useState<Record<string, any> | null>(null);
  const [prefill, setPrefill] = useState<Record<string, any> | null>(null);
  const [taskText, setTaskText] = useState("請把這個 UI 原則整理成可重用規則：一般聊天要像大模型，工作台放右側或手機抽屜。");
  const [taskType] = useState<TaskType>("general");
  const [task, setTask] = useState<TaskSummary | null>(null);
  const [patchLayer, setPatchLayer] = useState<ScbkrDimensionKey>("B");
  const [patchInstruction, setPatchInstruction] = useState("把 B 層改嚴格一點，不要讓模型自己確認日期。");
  const [pendingPatch, setPendingPatch] = useState<Record<string, any> | null>(null);
  const [showPatchJson, setShowPatchJson] = useState(false);
  const [dateOpen, setDateOpen] = useState(false);
  const [eventDate, setEventDate] = useState("");
  const [modelDate, setModelDate] = useState("");
  const [storageSuggestion, setStorageSuggestion] = useState<Record<string, any> | null>(null);
  const [selectedTargets, setSelectedTargets] = useState<string[]>([]);
  const [dataCenter, setDataCenter] = useState<Record<string, any> | null>(null);
  const [modelForm, setModelForm] = useState({ provider: "lm_studio", mode: "local", base_url: "http://127.0.0.1:1234/v1", api_key: "", model_name: "", temperature: 0.2, max_tokens: 4096, context_length: 8192, timeout: 120 });

  const refresh = async () => { try { await api("/health"); setHealth("online"); const m = await api<ModelSettings>("/api/settings/model"); setModel(m); setModelForm({ ...modelForm, provider: m.provider || modelForm.provider, mode: m.mode || modelForm.mode, base_url: m.base_url || modelForm.base_url, model_name: m.model_name || modelForm.model_name, api_key: "" }); } catch (e) { setHealth("offline"); setMessage(String(e)); } };
  useEffect(() => { void refresh(); }, []);
  const run = async <T,>(label: string, fn: () => Promise<T>) => { try { const r: any = await fn(); if (r?.task_id) setTask(r); if (r?.model_name) setModel(r); setMessage(`${label} 完成`); return r; } catch (e) { const raw = String(e); setMessage(raw.includes("required_permissions_not_enabled") ? "目前權限不足，無法呼叫模型。請確認模型生成權限，或切回沙盒模式。" : raw.includes("task.status must be confirmed") ? "目前責任鏈尚未確認，請先確認責任鏈後再生成。" : `${label} 失敗：${raw}`); } };

  const sendChat = async () => { const user = chatInput; setMessages([...messages, { role: "user", content: user }]); const r = await run("一般聊天", () => api<Record<string, any>>("/api/chat/general", { method: "POST", body: JSON.stringify({ message: user }) })); if (r) { setMessages([...messages, { role: "user", content: user }, { role: "assistant", content: r.reply }]); setSuggestion(r.suggestion); } };
  const acceptSuggestion = async () => { if (!suggestion) return; const r = await run("建立建議單", () => api<Record<string, any>>("/api/chat/suggestions/accept", { method: "POST", body: JSON.stringify({ suggestion }) })); if (r?.prefill) { setPrefill(r.prefill); setTaskText(r.prefill.suggested_instruction || r.prefill.user_original); setWorkbenchOpen(true); setPage("workbench"); setDrawer(false); } };
  const createTask = async () => { const r = await run("建立 SCBKR 任務 / 建立確認單", () => api<TaskSummary>("/api/tasks/create", { method: "POST", body: JSON.stringify({ raw_input: taskText, task_type: taskType, create_scbkr_draft: true, prefill }) })); if (r?.task_id) { setWorkbenchOpen(true); setPage("workbench"); } };
  const updateField = (d: ScbkrDimensionKey, f: string, v: string) => { if (!task?.scbkr) return; const old = task.scbkr[d]?.[f]; setTask({ ...task, confirmed: false, status: "waiting_user_confirm", scbkr: { ...task.scbkr, confirmation_status: "draft", [d]: { ...task.scbkr[d], [f]: parse(v, old) } } }); };
  const confirm = () => task && run("確認責任鏈", () => api<TaskSummary>(`/api/tasks/${task.task_id}/confirm`, { method: "POST", body: JSON.stringify({ scbkr: task.scbkr, confirmed_by: "user", confirmation_statement: "我確認本任務 S/C/B/K/R 五維責任鏈。", signature: "user" }) }));
  const generate = () => task && run("生成正式結果", () => api<TaskSummary>(`/api/tasks/${task.task_id}/generate`, { method: "POST" }));
  const draftPatch = async () => { if (!task) return; const r = await run("產生修改草案", () => api<Record<string, any>>(`/api/tasks/${task.task_id}/scbkr/patch-draft`, { method: "POST", body: JSON.stringify({ layer: patchLayer, instruction: patchInstruction }) })); if (r?.patch) setPendingPatch(r.patch); };
  const applyPatch = () => task && pendingPatch && run("套用修改", () => api<TaskSummary>(`/api/tasks/${task.task_id}/scbkr/apply-patch`, { method: "POST", body: JSON.stringify({ patch: pendingPatch }) })).then(() => setPendingPatch(null));
  const saveDates = () => task && run("設定日期", () => api<TaskSummary>(`/api/tasks/${task.task_id}/dates`, { method: "POST", body: JSON.stringify({ event_date: eventDate, model_inferred_date: modelDate, date_source: "user", user_confirmed: Boolean(eventDate) }) }));
  const review = (decision: "pass" | "fail") => task && run(decision === "pass" ? "通過驗收" : "驗收失敗", () => api<TaskSummary>(`/api/tasks/${task.task_id}/review`, { method: "POST", body: JSON.stringify({ review_decision: decision, review_message: decision === "pass" ? "user pass" : "建立記憶規則" }) }));
  const storageSuggest = async () => { if (!task) return; const r = await run("產生入庫建議", () => api<TaskSummary>(`/api/tasks/${task.task_id}/storage-suggestion`, { method: "POST", body: JSON.stringify({}) })); setStorageSuggestion(r?.storage_suggestion || r); };
  const storageRequest = () => task && run("產生入庫請求", () => api<TaskSummary>(`/api/tasks/${task.task_id}/storage-request`, { method: "POST", body: JSON.stringify({ selected_targets: selectedTargets, user_decision: selectedTargets.length ? "custom" : "do_not_store", signature: "user" }) }));
  const testBackend = () => run("測試後端 API", () => api("/api/backend/test", { method: "POST", body: JSON.stringify({ backend_api_url: backendUrl }) }));
  const saveModelSettings = (extra: Record<string, any> = {}) => run("儲存模型設定", () => api("/api/settings/model", { method: "POST", body: JSON.stringify(modelForm.provider === "sandbox_mock_model" ? { ...modelForm, ...extra, mode: "sandbox", model_name: "sandbox_mock_model", base_url: "", api_key: "" } : { ...modelForm, ...extra }) }));
  const testModel = () => run("測試模型連線", () => api("/api/model/test", { method: "POST", body: JSON.stringify(modelForm) }));
  const clearApiKey = () => saveModelSettings({ api_key: "", clear_api_key: true });
  const switchSandbox = () => { const next = { ...modelForm, provider: "sandbox_mock_model", mode: "sandbox", base_url: "", model_name: "sandbox_mock_model", api_key: "" }; setModelForm(next); return run("切回 Sandbox", () => api("/api/model/test", { method: "POST", body: JSON.stringify(next) })); };
  const regenerateDraft = () => task && run("重新呼叫模型生成草案", () => api<TaskSummary>(`/api/tasks/${task.task_id}/scbkr`, { method: "POST" }));
  const storageConfirm = () => task && run("二次確認寫入 Data Center", () => api<TaskSummary>(`/api/tasks/${task.task_id}/storage-confirm`, { method: "POST", body: JSON.stringify({ storage_confirmed: true, second_confirm: true, confirmed_by: "user", signature: "user", selected_targets: selectedTargets }) }));
  const loadData = async () => { const overview = await api<Record<string, any>>("/api/data-center/overview"); setDataCenter(overview); };

  const navButton = (p: Page, label: string) => <button className={page === p ? "active" : ""} onClick={() => { setPage(p); setDrawer(false); }}>{label}</button>;
  const chat = <section className="chat-main" aria-label="一般聊天主視窗"><header className="chat-header"><button className="menu-button" onClick={() => setDrawer(true)}>☰</button><div><strong>SCBKR Chat</strong><span>一般聊天不建立 task、不入庫、不寫記憶庫</span></div></header><div className="message-list">{messages.map((m, i) => <div key={i} className={`message ${m.role}`}>{m.content}</div>)}{suggestion && <div className="suggestion-card"><h3>這段內容可以建立成 SCBKR 規則 / 任務</h3><p><b>使用者原句：</b>{suggestion.user_original}</p><p><b>建議指令：</b>{suggestion.suggested_instruction}</p><p><b>建議類型：</b>{suggestion.suggested_type}</p><p><b>建議原因：</b>{suggestion.suggested_reason}</p><p><b>可能寫入方向：</b>{suggestion.suggested_write_direction}</p><div className="button-row"><button onClick={acceptSuggestion}>建立確認單</button><button onClick={() => setSuggestion(null)}>保留聊天</button></div></div>}</div><div className="chat-input"><textarea value={chatInput} onChange={(e: any) => setChatInput(e.target.value)} placeholder="輸入一般聊天內容…" /><button onClick={sendChat}>送出</button></div></section>;

  const workbench = <aside className={`workbench-panel ${workbenchOpen ? "open" : "collapsed"}`} aria-label="SCBKR 工作台側欄"><div className="panel-head"><h2>SCBKR 工作台</h2><button onClick={() => setWorkbenchOpen(!workbenchOpen)}>{workbenchOpen ? "收起" : "打開"}</button></div>{!workbenchOpen ? <p>尚未建立 SCBKR 任務</p> : !task ? <section className="step-card"><p className="eyebrow">Step 1｜準備建立確認單</p><h3>尚未建立 SCBKR 任務</h3><p>使用者原句：{prefill?.user_original || taskText}</p><label>建議指令<textarea value={taskText} onChange={(e: any) => setTaskText(e.target.value)} /></label><p>任務類型：自動判斷</p><div className="button-row"><button onClick={createTask}>建立 SCBKR 任務 / 建立確認單</button><button onClick={() => setPage("chat")}>返回聊天</button></div></section> : <><section className="step-card"><p className="eyebrow">狀態機</p><h3>{statusLabel(task)}</h3><p>task_id：{task.task_id}</p><p>fallback_used：{String(task.scbkr?.fallback_used ?? false)}</p>{task.scbkr?.fallback_used && <div className="warning-card"><b>目前是 fallback 草案，不是模型草案</b><p>原因：{task.scbkr?.fallback_reason || task.draft_model_call_skipped_reason}</p><div className="button-row"><button onClick={regenerateDraft}>重新呼叫模型生成草案</button><button onClick={() => setPage("model-settings")}>前往連線設定</button><button>使用 fallback 草案繼續</button></div></div>}</section><section className="step-card"><p className="eyebrow">本次引用資料</p>{(task.data_center_context?.hits || task.scbkr?.referenced_sources || []).length ? (task.data_center_context?.hits || task.scbkr?.referenced_sources || []).map((h: any, i: number) => <div key={i} className="summary-card"><b>{h.source_store}</b><span>{h.status || "待確認"}</span><p>{text(h.rule)}</p></div>) : <p>未命中已確認規則，本次為待確認草案</p>}{(task.data_center_context?.conflicts || []).length > 0 && <p>衝突：需要使用者確認</p>}</section><section className="step-card"><p className="eyebrow">Step 2｜模型理解草案</p>{dims.map((d) => <details key={d} className="summary-card"><summary><strong>{dimTitles[d]}</strong><span>{text(task.scbkr?.[d]?.[dimFields[d][0]] || task.scbkr?.[d]?.pending_questions?.[0])}</span></summary>{dimFields[d].map((f) => <label key={f}>{f}<textarea value={text(task.scbkr?.[d]?.[f])} disabled={task.confirmed} onChange={(e: any) => updateField(d, f, e.target.value)} /></label>)}</details>)}</section><section className="step-card"><p className="eyebrow">Step 3｜確認責任鏈</p><select value={patchLayer} onChange={(e: any) => setPatchLayer(e.target.value as ScbkrDimensionKey)}>{dims.map((d) => <option key={d}>{d}</option>)}</select><textarea value={patchInstruction} onChange={(e: any) => setPatchInstruction(e.target.value)} /><div className="button-row"><button disabled={task.confirmed} onClick={draftPatch}>產生人話 patch</button><button disabled={!pendingPatch} onClick={applyPatch}>套用修改</button><button disabled={!task.scbkr || task.confirmed} onClick={confirm}>確認責任鏈</button></div>{pendingPatch && <div className="patch-card"><h4>模型建議修改 {pendingPatch.layer}｜邊界 / 行為</h4><p>新增 / 調整：{pendingPatch.reason}</p><p>原因：使用者要求加強該層邊界，套用後仍需重新確認。</p><button onClick={() => setShowPatchJson(!showPatchJson)}>查看原始 patch</button>{showPatchJson && <JsonBlock value={pendingPatch} />}</div>}</section><section className="step-card"><p className="eyebrow">日期治理</p><p>事件日期：{eventDate || "未設定"}</p><p>確認狀態：{eventDate ? "已確認" : "待確認"}</p><button onClick={() => setDateOpen(!dateOpen)}>設定日期</button>{dateOpen && <div><label>事件日期<input value={eventDate} onChange={(e: any) => setEventDate(e.target.value)} /></label><label>模型推測日期<input value={modelDate} onChange={(e: any) => setModelDate(e.target.value)} /></label><div className="button-row"><button onClick={saveDates}>確認日期</button><button onClick={() => setModelDate("")}>清除模型推測</button></div></div>}</section><section className="step-card"><p className="eyebrow">Step 4｜生成正式結果</p>{task.status !== "waiting_review" && <button disabled={!task.confirmed || task.status !== "confirmed"} onClick={generate}>開始生成正式結果</button>}<div className="model-output">{resultText(task)}</div></section><section className="step-card"><p className="eyebrow">Step 5｜驗收</p><div className="button-row"><button disabled={!task.generation_result} onClick={() => review("pass")}>通過驗收</button>{dims.map((d) => <button key={d} disabled={!task.generation_result} onClick={() => setTask({ ...task, confirmed: false, status: "waiting_user_confirm" })}>回到 {d} 修改</button>)}<button disabled={!task.generation_result} onClick={() => review("fail")}>驗收失敗 / 建立記憶規則</button><button disabled={!task.generation_result} onClick={generate}>重新生成</button></div></section><section className="step-card"><p className="eyebrow">Step 6｜入庫</p><div className="button-row"><button disabled={!task.review_passed} onClick={storageSuggest}>產生入庫建議</button></div>{(storageSuggestion || task.storage_suggestion) && <div className="storage-options">{["vector", "corpus", "logic", "memory"].map((k) => <button key={k} className={selectedTargets.includes(k) ? "selected" : ""} onClick={() => setSelectedTargets(selectedTargets.includes(k) ? selectedTargets.filter((x: string) => x !== k) : [...selectedTargets, k])}>{k}<small>{(storageSuggestion || task.storage_suggestion)?.suggestions?.[k]?.reason}</small></button>)}</div>}<div className="button-row"><button disabled={!task.review_passed} onClick={storageRequest}>產生入庫請求</button><button disabled={!task.storage_plan} onClick={storageConfirm}>使用者二次確認寫入</button></div>{task.storage_result && <div><p>written_targets：{(task.storage_result.written_targets || []).join(", ")}</p><p>hashes：{(task.storage_result.hashes || []).join(", ")}</p><p>paths：{(task.storage_result.written_items || []).map((x: any) => x.path).join(", ")}</p></div>}</section><details className="audit-link"><summary>Audit / Raw Details</summary><JsonBlock value={task} /></details></>}</aside>;

  return <main className="app-shell"><div className="mobile-drawer-backdrop" hidden={!drawer} onClick={() => setDrawer(false)} /><nav className={`mobile-drawer ${drawer ? "open" : ""}`}>{navButton("workbench", "工作台 / 工單")}{navButton("data-center", "Data Center / 資料中心")}{navButton("model-settings", "Model Settings / 模型設定")}{navButton("audit", "Audit / 審計資料")}</nav><section className="top-status-bar"><b>SCBKR 本地責任鏈模型</b><span>Backend API：{health} + {backendUrl}</span><span>Model：{model?.provider ?? "unknown"} + {(model?.enabled && model?.last_test_status === "success") ? "connected" : "not connected"} + {model?.model_name || "未設定"}</span><span>Runtime：{runtimeLabel}</span><span>{message}</span></section>{page === "chat" || page === "workbench" ? <div className="split-layout">{chat}{workbench}</div> : null}{page === "data-center" && <section className="panel"><h1>Data Center / 資料中心</h1><button onClick={loadData}>讀回 Data Center</button>{dataCenter && <JsonBlock value={dataCenter} />}</section>}{page === "model-settings" && <section className="panel model-settings"><h1>Connection Center / 連線設定</h1><p>設定後端 API 與真實模型閘道；API Key 不完整顯示，欄位留白會保留舊 key，只有 clear_api_key=true 才清除。</p><h2>Backend API</h2><label>Backend API URL<input value={backendUrl} onChange={(e: any) => setBackendUrl(e.target.value)} placeholder="http://127.0.0.1:8787" /></label><button onClick={testBackend}>測試後端 API</button><h2>Model Gateway</h2><label>Provider<select value={modelForm.provider} onChange={(e: any) => setModelForm({ ...modelForm, provider: e.target.value, mode: e.target.value === "openai_compatible" ? "external" : e.target.value === "sandbox_mock_model" ? "sandbox" : "local" })}><option value="sandbox_mock_model">Sandbox</option><option value="lm_studio">LM Studio</option><option value="ollama">Ollama</option><option value="openai_compatible">OpenAI-compatible</option></select></label><label>Model Base URL<input value={modelForm.base_url} onChange={(e: any) => setModelForm({ ...modelForm, base_url: e.target.value })} placeholder="http://127.0.0.1:1234/v1" /></label><label>Model Name<input value={modelForm.model_name} onChange={(e: any) => setModelForm({ ...modelForm, model_name: e.target.value })} placeholder="model name" /></label><label>API Key（目前：{model?.api_key || "空"}）<input type="password" value={modelForm.api_key} onChange={(e: any) => setModelForm({ ...modelForm, api_key: e.target.value })} placeholder="留白保留舊 key" /></label><label>Temperature<input type="number" step="0.1" value={modelForm.temperature} onChange={(e: any) => setModelForm({ ...modelForm, temperature: Number(e.target.value) })} /></label><label>Max Tokens<input type="number" value={modelForm.max_tokens} onChange={(e: any) => setModelForm({ ...modelForm, max_tokens: Number(e.target.value) })} /></label><label>Timeout<input type="number" value={modelForm.timeout} onChange={(e: any) => setModelForm({ ...modelForm, timeout: Number(e.target.value) })} /></label><div className="button-row"><button onClick={() => saveModelSettings()}>儲存模型設定</button><button onClick={testModel}>測試模型連線</button><button onClick={clearApiKey}>清除 API Key</button><button onClick={switchSandbox}>切回 Sandbox</button><button onClick={() => run("開啟 model_generate", () => api("/api/settings/permissions", { method: "POST", body: JSON.stringify({ model_generate: true }) }))}>開啟 model_generate</button></div><p>Backend API：{health}/{backendUrl}</p><p>Model：{model?.provider} / {(model?.enabled && model?.last_test_status === "success") ? "connected" : "not connected"} / {model?.model_name}</p><p>Runtime：{runtimeLabel}</p></section>}{page === "audit" && <section className="panel"><h1>Audit / Raw Details</h1><JsonBlock value={{ task, model }} /></section>}</main>;
}
