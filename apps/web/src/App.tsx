import { useEffect, useState } from "react";
import type { DesktopStatus, ModelSettings, Permissions, ScbkrDimensionKey, TaskSummary, TaskType } from "./types";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8787";
const API_BASE_URL = normalizeApiBaseUrl(import.meta.env.VITE_SCBKR_API_URL ?? DEFAULT_API_BASE_URL);

type Page = "workbench" | "model-settings";
type Provider = "sandbox_mock_model" | "lm_studio" | "ollama" | "openai_compatible";

type ModelForm = {
  provider: Provider;
  mode: string;
  base_url: string;
  api_key: string;
  model_name: string;
  temperature: number;
  max_tokens: number;
  context_length: number;
  timeout: number;
};

const providerLabels: Record<Provider, string> = {
  sandbox_mock_model: "沙盒模式 / Sandbox Mode",
  lm_studio: "LM Studio 本地模型 / LM Studio Local Model",
  ollama: "Ollama 本地模型 / Ollama Local Model",
  openai_compatible: "API 模型 / API Model",
};

const providerDefaults: Record<Provider, Pick<ModelForm, "mode" | "base_url" | "api_key" | "model_name">> = {
  sandbox_mock_model: { mode: "sandbox", base_url: "", api_key: "", model_name: "sandbox_mock_model" },
  lm_studio: { mode: "local", base_url: "http://127.0.0.1:1234/v1", api_key: "local", model_name: "" },
  ollama: { mode: "local", base_url: "http://127.0.0.1:11434/v1", api_key: "local", model_name: "" },
  openai_compatible: { mode: "external", base_url: "", api_key: "", model_name: "" },
};

function normalizeApiBaseUrl(value: string): string { return value.replace(/\/+$/, ""); }
function apiUrl(path: string): string { return `${API_BASE_URL}/${path.replace(/^\/+/, "")}`; }
const dimensions: ScbkrDimensionKey[] = ["S", "C", "B", "K", "R"];
const taskTypes: TaskType[] = ["general", "coding", "info_search", "fraud_audit", "document_audit", "app_design", "game_design", "animation", "music", "privacy", "workflow", "private_memory"];

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), { headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) }, ...init });
  if (!response.ok) {
    const errorText = await response.text();
    if (errorText.includes("model gateway is not enabled") || errorText.includes("model_generate permission is required")) {
      throw new Error("目前模型尚未連線，請先到「模型設定」完成測試連線，或切回沙盒模式。");
    }
    throw new Error(errorText);
  }
  return response.json() as Promise<T>;
}

function JsonBlock({ value }: { value: unknown }) { return <pre className="json-block">{JSON.stringify(value, null, 2)}</pre>; }
function providerFromModel(model: ModelSettings | null): Provider { return (model?.provider as Provider) || (model?.mode === "sandbox" ? "sandbox_mock_model" : "lm_studio"); }
function formFromModel(model: ModelSettings | null): ModelForm {
  const provider = providerFromModel(model);
  return { provider, mode: model?.mode ?? providerDefaults[provider].mode, base_url: model?.base_url ?? providerDefaults[provider].base_url, api_key: "", model_name: model?.model_name ?? providerDefaults[provider].model_name, temperature: model?.temperature ?? 0.2, max_tokens: model?.max_tokens ?? 4096, context_length: model?.context_length ?? 8192, timeout: model?.timeout ?? 120 };
}
function modelHumanStatus(model: ModelSettings | null): string {
  if (!model) return "目前模型：未知｜狀態：尚未讀取";
  if (model.mode === "sandbox") return "目前模式：沙盒模式｜狀態：可用｜外部模型：未呼叫｜API Key：不需要";
  const label = model.provider === "ollama" ? "Ollama 本地模型" : model.provider === "lm_studio" ? "LM Studio 本地模型" : "API 模型";
  const status = model.enabled ? "已連線，可生成：是" : "尚未連線";
  const key = model.provider === "openai_compatible" ? `｜API Key：${model.api_key ? "已設定（已遮罩）" : "未設定"}` : "";
  return `目前模式：${label}｜Base URL：${model.base_url || "未設定"}｜模型名稱：${model.model_name || "未設定"}｜狀態：${status}${key}`;
}

function App() {
  const [page, setPage] = useState<Page>("workbench");
  const [health, setHealth] = useState("checking");
  const [taskText, setTaskText] = useState("請建立一個 SCBKR 本地 MVP 測試任務。");
  const [taskType, setTaskType] = useState<TaskType>("workflow");
  const [task, setTask] = useState<TaskSummary | null>(null);
  const [model, setModel] = useState<ModelSettings | null>(null);
  const [form, setForm] = useState<ModelForm>(formFromModel(null));
  const [permissions, setPermissions] = useState<Permissions | null>(null);
  const [desktopStatus, setDesktopStatus] = useState<DesktopStatus | null>(null);
  const [message, setMessage] = useState("");
  const modelStatus = modelHumanStatus(model);

  const refresh = async () => {
    try { await api("/health"); setHealth("online"); const nextModel = await api<ModelSettings>("/api/settings/model"); setModel(nextModel); setForm(formFromModel(nextModel)); setPermissions(await api<Permissions>("/api/settings/permissions")); setDesktopStatus(await api<DesktopStatus>("/api/desktop/status")); }
    catch (error) { setHealth("offline"); setMessage(`API 尚未連線，請確認桌面預覽包的 sidecar 是否已啟動。 (${String(error)})`); }
  };
  useEffect(() => { void refresh(); }, []);

  const run = async (label: string, action: () => Promise<TaskSummary | ModelSettings | Permissions>) => {
    try { const result = await action(); if ("task_id" in result) setTask(result as TaskSummary); if ("model_name" in result) { setModel(result as ModelSettings); setForm(formFromModel(result as ModelSettings)); } if ("model_generate" in result) setPermissions(result as Permissions); setMessage(`${label} 完成`); }
    catch (error) { setMessage(`${label} 失敗：${String(error)}`); }
  };
  const selectProvider = (provider: Provider) => setForm({ ...form, provider, ...providerDefaults[provider] });
  const modelPayload = () => ({ ...form, api_key: form.api_key || (form.provider === "openai_compatible" ? "" : providerDefaults[form.provider].api_key) });
  const switchSandbox = () => run("切回沙盒模式", () => api("/api/settings/model", { method: "POST", body: JSON.stringify(providerDefaults.sandbox_mock_model) }));
  const generate = () => {
    if (model?.mode !== "sandbox" && model?.enabled !== true) { setMessage("目前模型尚未連線，請先到「模型設定」完成測試連線，或切回沙盒模式。"); setPage("model-settings"); return; }
    if (model?.mode === "sandbox" && permissions?.model_generate !== true) { setMessage("沙盒生成前請先開啟 model_generate 權限。"); return; }
    void run("模型生成", () => api(`/api/tasks/${task?.task_id}/generate`, { method: "POST" }));
  };

  return <main className="app-shell">
    <section className="top-status-bar" aria-label="系統狀態列"><div className="product-name">SCBKR 本地責任鏈模型｜自接入 MVP App</div><div className="status-grid"><span>API：{health}</span><span>Base：{API_BASE_URL}</span><span>模型：{model?.last_test_status ?? "unknown"}</span><span>Mode：{model?.mode ?? "unknown"}</span><span>Runtime：P14-D</span></div></section>
    <nav className="nav-tabs" aria-label="主導覽"><button className={page === "workbench" ? "active" : ""} onClick={() => setPage("workbench")}>工作台 / Workbench</button><button className={page === "model-settings" ? "active" : ""} onClick={() => setPage("model-settings")}>模型設定 / Model Settings</button></nav>

    {page === "model-settings" ? <section className="panel model-settings"><div className="section-heading"><p className="eyebrow">P14-D Model Settings</p><h2>模型設定 / Model Settings</h2></div><p className="lock-note">{modelStatus}</p>
      <label className="field-label">模式 / Mode</label><select value={form.provider} onChange={(event: any) => selectProvider(event.target.value as Provider)}>{(Object.keys(providerLabels) as Provider[]).map((provider) => <option key={provider} value={provider}>{providerLabels[provider]}</option>)}</select>
      <label className="field-label">Provider</label><input value={form.provider} readOnly />
      <label className="field-label">Base URL</label><input value={form.base_url} placeholder={form.provider === "openai_compatible" ? "https://api.example.com/v1" : ""} disabled={form.provider === "sandbox_mock_model"} onChange={(event: any) => setForm({ ...form, base_url: event.target.value })} />
      <label className="field-label">API Key <span className="muted">{form.provider === "sandbox_mock_model" ? "不需要 API key" : model?.api_key ? `目前：${model.api_key}` : "未設定"}</span></label><input type="password" value={form.api_key} placeholder={form.provider === "sandbox_mock_model" ? "不需要 API key" : form.provider === "openai_compatible" ? "輸入 API key" : "local"} disabled={form.provider === "sandbox_mock_model"} onChange={(event: any) => setForm({ ...form, api_key: event.target.value })} />
      <label className="field-label">Model Name</label><input value={form.model_name} placeholder={form.provider === "lm_studio" ? "例如 qwen2.5-vl-7b-instruct" : form.provider === "ollama" ? "例如 llama3.1" : form.provider === "openai_compatible" ? "例如 gpt-4.1-mini" : "sandbox_mock_model"} onChange={(event: any) => setForm({ ...form, model_name: event.target.value })} />
      <details><summary>進階設定</summary><div className="advanced-grid"><label>temperature<input type="number" step="0.1" value={form.temperature} onChange={(e: any) => setForm({ ...form, temperature: Number(e.target.value) })} /></label><label>max_tokens<input type="number" value={form.max_tokens} onChange={(e: any) => setForm({ ...form, max_tokens: Number(e.target.value) })} /></label><label>context_length<input type="number" value={form.context_length} onChange={(e: any) => setForm({ ...form, context_length: Number(e.target.value) })} /></label><label>timeout<input type="number" value={form.timeout} onChange={(e: any) => setForm({ ...form, timeout: Number(e.target.value) })} /></label></div></details>
      <div className="action-grid"><button type="button" onClick={() => run("儲存設定", () => api("/api/settings/model", { method: "POST", body: JSON.stringify(modelPayload()) }))}>儲存設定</button><button type="button" onClick={() => run("測試連線", () => api("/api/model/test", { method: "POST", body: JSON.stringify(modelPayload()) }))}>測試連線</button><button type="button" onClick={switchSandbox}>切回沙盒模式</button></div><p className="lock-note">{message || "沙盒模式已啟用時，不呼叫外部模型，不需要 API key。API key 只以遮罩狀態顯示。"}</p></section> : <>
      <section className="hero-card"><p className="eyebrow">Workbench</p><h1>模型不是先回答，而是先交代、先確認、再生成。</h1><p className="hero-text">{modelStatus}</p>{model?.mode !== "sandbox" && model?.enabled !== true ? <p className="lock-note">目前模型尚未連線，請先到「模型設定」完成測試連線，或切回沙盒模式。 <button type="button" className="link-button" onClick={() => setPage("model-settings")}>前往模型設定</button></p> : null}</section>
      <section className="layout-grid"><div className="panel input-panel"><div className="section-heading"><p className="eyebrow">任務輸入</p><h2>建立任務與 SCBKR</h2></div><textarea value={taskText} onChange={(event: any) => setTaskText(event.target.value)} /><label className="field-label">任務類型</label><select value={taskType} onChange={(event: any) => setTaskType(event.target.value as TaskType)}>{taskTypes.map((type) => <option key={type}>{type}</option>)}</select><div className="action-grid"><button type="button" onClick={() => run("建立任務", () => api("/api/tasks/create", { method: "POST", body: JSON.stringify({ raw_input: taskText, task_type: taskType }) }))}>建立任務</button><button type="button" disabled={!task} onClick={() => run("產生 SCBKR", () => api(`/api/tasks/${task?.task_id}/scbkr`, { method: "POST" }))}>產生 SCBKR</button><button type="button" disabled={!task?.scbkr} onClick={() => run("確認 SCBKR", () => api(`/api/tasks/${task?.task_id}/confirm`, { method: "POST", body: JSON.stringify({ confirmed_by: "user", confirmation_statement: "我確認本任務 S/C/B/K/R 五維責任鏈。", signature: "user" }) }))}>確認責任鏈</button></div></div><div className="panel task-card"><div className="section-heading"><p className="eyebrow">目前任務</p><h2>{task?.task_name ?? "尚未建立"}</h2></div>{task ? <JsonBlock value={{ task_id: task.task_id, status: task.status, confirmed: task.confirmed, review_passed: task.review_passed, storage_confirmed: task.storage_confirmed }} /> : <p>請先建立任務。</p>}</div></section>
      <section className="panel"><div className="section-heading"><p className="eyebrow">SCBKR 五維確認單</p><h2>S / C / B / K / R</h2></div><div className="dimension-grid">{dimensions.map((key) => { const dimension = task?.scbkr?.[key]; return <article className="dimension-card" key={key}><div className="dimension-header"><h3>{key}</h3><span className="status-chip">{dimension?.confirmation_status ?? "draft"}</span></div><JsonBlock value={dimension ? { confirmation_status: dimension.confirmation_status ?? "draft", confirmed: dimension.confirmed ?? false, snapshot_hash: dimension.snapshot_hash ? String(dimension.snapshot_hash).slice(0, 12) : undefined, ...dimension } : "尚未產生"} /></article>; })}</div></section>
      <section className="panel"><div className="section-heading"><p className="eyebrow">Desktop Readiness / 桌面模式準備狀態</p><h2>P14-C Windows Desktop Preview</h2></div><JsonBlock value={{ desktop_stage: desktopStatus?.desktop_stage, api_server_reachable: desktopStatus?.api_server_reachable ?? desktopStatus?.api_status === "running", sidecar_running: desktopStatus?.sidecar_running, sandbox_available: desktopStatus?.sandbox_available, local_model_endpoint_setting: desktopStatus?.local_model_base_url, api_sidecar: `${desktopStatus?.sidecar_host ?? "127.0.0.1"}:${desktopStatus?.sidecar_port ?? 8787}`, data_dir: desktopStatus?.data_dir ?? "app data / dev data", production_packaging: desktopStatus?.production_packaging_status ?? "future stage pending" }} /></section>
      <section className="layout-grid bottom-grid"><div className="panel"><div className="section-heading"><p className="eyebrow">模型與權限</p><h2>目前模型狀態</h2></div><p>{modelStatus}</p><div className="action-grid"><button type="button" onClick={switchSandbox}>切回沙盒模式</button><button type="button" onClick={() => setPage("model-settings")}>前往模型設定</button><button type="button" onClick={() => run("開啟模型生成權限", () => api("/api/settings/permissions", { method: "POST", body: JSON.stringify({ model_generate: true }) }))}>開啟 model_generate</button></div></div><div className="panel"><div className="section-heading"><p className="eyebrow">生成 / 驗收 / 入庫計畫</p><h2>操作閉環</h2></div><div className="action-grid"><button type="button" disabled={!task?.confirmed} onClick={generate}>開始生成</button><button type="button" disabled={!task?.generation_result} onClick={() => run("通過驗收", () => api(`/api/tasks/${task?.task_id}/review`, { method: "POST", body: JSON.stringify({ review_decision: "pass", review_message: "P12 UI pass" }) }))}>通過驗收</button><button type="button" disabled={!task?.generation_result} onClick={() => run("驗收失敗", () => api(`/api/tasks/${task?.task_id}/review`, { method: "POST", body: JSON.stringify({ review_decision: "fail", review_message: "P12 UI fail" }) }))}>驗收失敗 / P11 草案</button><button type="button" disabled={task?.status !== "review_passed"} onClick={() => run("入庫請求", () => api(`/api/tasks/${task?.task_id}/storage-request`, { method: "POST" }))}>產生入庫請求</button><button type="button" disabled={!task?.storage_request} onClick={() => run("入庫計畫", () => api(`/api/tasks/${task?.task_id}/storage-confirm`, { method: "POST", body: JSON.stringify({ storage_confirmed: true, confirmed_by: "user", signature: "user", selected_targets: ["corpus", "logic", "exports"] }) }))}>確認入庫計畫</button><button type="button" disabled={task?.status !== "storage_committed"} onClick={() => run("確認 SCBKR 完成", () => api(`/api/tasks/${task?.task_id}/complete`, { method: "POST", body: JSON.stringify({ confirmed_by: "user" }) }))}>確認 SCBKR 完成</button></div><p className="lock-note">{message}</p><details open><summary>審計原始資料 / Raw Audit Details</summary><JsonBlock value={{ generation_result: task?.generation_result, review_result: task?.review_result, storage_request: task?.storage_request, storage_plan: task?.storage_plan, memory_rule_draft: task?.memory_rule_draft }} /></details></div></section>
    </>}
  </main>;
}
export default App;
