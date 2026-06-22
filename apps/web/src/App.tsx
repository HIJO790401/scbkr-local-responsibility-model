import { useEffect, useState } from "react";
import type { DesktopStatus, ModelSettings, Permissions, ScbkrDimensionKey, TaskSummary, TaskType } from "./types";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8787";
const API_BASE_URL = normalizeApiBaseUrl(import.meta.env.VITE_SCBKR_API_URL ?? DEFAULT_API_BASE_URL);

function normalizeApiBaseUrl(value: string): string {
  return value.replace(/\/+$/, "");
}

function apiUrl(path: string): string {
  return `${API_BASE_URL}/${path.replace(/^\/+/, "")}`;
}
const dimensions: ScbkrDimensionKey[] = ["S", "C", "B", "K", "R"];
const taskTypes: TaskType[] = ["general", "coding", "info_search", "fraud_audit", "document_audit", "app_design", "game_design", "animation", "music", "privacy", "workflow", "private_memory"];

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    const errorText = await response.text();
    if (errorText.includes("model_generate permission is required before sandbox generation")) {
      throw new Error("沙盒生成前請先開啟 model_generate 權限。");
    }
    throw new Error(errorText);
  }
  return response.json() as Promise<T>;
}

function JsonBlock({ value }: { value: unknown }) {
  return <pre className="json-block">{JSON.stringify(value, null, 2)}</pre>;
}

function App() {
  const [health, setHealth] = useState("checking");
  const [taskText, setTaskText] = useState("請建立一個 SCBKR 本地 MVP 測試任務。");
  const [taskType, setTaskType] = useState<TaskType>("workflow");
  const [task, setTask] = useState<TaskSummary | null>(null);
  const [model, setModel] = useState<ModelSettings | null>(null);
  const [permissions, setPermissions] = useState<Permissions | null>(null);
  const [desktopStatus, setDesktopStatus] = useState<DesktopStatus | null>(null);
  const [message, setMessage] = useState("");

  const refresh = async () => {
    try {
      await api("/health");
      setHealth("online");
      setModel(await api<ModelSettings>("/api/settings/model"));
      setPermissions(await api<Permissions>("/api/settings/permissions"));
      setDesktopStatus(await api<DesktopStatus>("/api/desktop/status"));
    } catch (error) {
      setHealth("offline");
      setMessage(`API 尚未連線，請確認桌面預覽包的 sidecar 是否已啟動。 (${String(error)})`);
    }
  };

  useEffect(() => { void refresh(); }, []);

  const run = async (label: string, action: () => Promise<TaskSummary | ModelSettings | Permissions>) => {
    try {
      const result = await action();
      if ("task_id" in result) setTask(result as TaskSummary);
      if ("model_name" in result) setModel(result as ModelSettings);
      if ("model_generate" in result) setPermissions(result as Permissions);
      setMessage(`${label} 完成`);
    } catch (error) {
      setMessage(`${label} 失敗：${String(error)}`);
    }
  };

  return (
    <main className="app-shell">
      <section className="top-status-bar" aria-label="系統狀態列">
        <div className="product-name">SCBKR 本地責任鏈模型｜自接入 MVP App</div>
        <div className="status-grid">
          <span>API：{health === "online" ? "online" : "offline"}</span><span>Health：{health}</span><span>Base：{API_BASE_URL}</span>
          <span>模型：{model?.last_test_status ?? "unknown"}</span><span>Mode：{model?.mode ?? "unknown"}</span><span>Runtime：P14-C Windows Desktop Preview</span>
        </div>
      </section>

      <section className="hero-card"><p className="eyebrow">P14-A Sandbox Mode</p><h1>模型不是先回答，而是先交代、先確認、再生成。</h1><p className="hero-text">Sandbox Mode / 沙盒模式：不用真模型或 API key，跑完整 SCBKR 責任鏈流程。Sandbox active 時不呼叫外部模型、不需要 API key，僅供 workflow testing，不是正式模型結果。</p>{model?.mode === "sandbox" ? <p className="lock-note">沙盒模式已啟用：不呼叫外部模型，不需要 API key。</p> : null}{model?.mode === "local" && model.enabled !== true ? <p className="lock-note">目前是本地模型模式，但模型尚未連線。請先完成模型接入設定或切回沙盒模式。</p> : null}</section>

      <section className="layout-grid">
        <div className="panel input-panel"><div className="section-heading"><p className="eyebrow">任務輸入</p><h2>建立任務與 SCBKR</h2></div>
          <textarea value={taskText} onChange={(event: any) => setTaskText(event.target.value)} />
          <label className="field-label">任務類型</label><select value={taskType} onChange={(event: any) => setTaskType(event.target.value as TaskType)}>{taskTypes.map((type) => <option key={type}>{type}</option>)}</select>
          <div className="action-grid"><button type="button" onClick={() => run("建立任務", () => api("/api/tasks/create", { method: "POST", body: JSON.stringify({ raw_input: taskText, task_type: taskType }) }))}>建立任務</button><button type="button" disabled={!task} onClick={() => run("產生 SCBKR", () => api(`/api/tasks/${task?.task_id}/scbkr`, { method: "POST" }))}>產生 SCBKR</button><button type="button" disabled={!task?.scbkr} onClick={() => run("確認 SCBKR", () => api(`/api/tasks/${task?.task_id}/confirm`, { method: "POST", body: JSON.stringify({ confirmed_by: "user", confirmation_statement: "我確認本任務 S/C/B/K/R 五維責任鏈。", signature: "user" }) }))}>確認責任鏈</button></div>
        </div>
        <div className="panel task-card"><div className="section-heading"><p className="eyebrow">目前任務</p><h2>{task?.task_name ?? "尚未建立"}</h2></div>{task ? <JsonBlock value={{ task_id: task.task_id, status: task.status, confirmed: task.confirmed, review_passed: task.review_passed, storage_confirmed: task.storage_confirmed }} /> : <p>請先建立任務。</p>}</div>
      </section>

      <section className="panel"><div className="section-heading"><p className="eyebrow">SCBKR 五維確認單</p><h2>S / C / B / K / R</h2></div><div className="dimension-grid">{dimensions.map((key) => { const dimension = task?.scbkr?.[key]; return <article className="dimension-card" key={key}><div className="dimension-header"><h3>{key}</h3><span className="status-chip">{dimension?.confirmation_status ?? "draft"}</span></div><JsonBlock value={dimension ? { confirmation_status: dimension.confirmation_status ?? "draft", confirmed: dimension.confirmed ?? false, snapshot_hash: dimension.snapshot_hash ? String(dimension.snapshot_hash).slice(0, 12) : undefined, ...dimension } : "尚未產生"} /></article>; })}</div></section>



      <section className="panel"><div className="section-heading"><p className="eyebrow">Desktop Readiness / 桌面模式準備狀態</p><h2>P14-C Windows Desktop Preview</h2></div><JsonBlock value={{ desktop_stage: desktopStatus?.desktop_stage, api_server_reachable: desktopStatus?.api_server_reachable ?? desktopStatus?.api_status === "running", sidecar_running: desktopStatus?.sidecar_running, sandbox_available: desktopStatus?.sandbox_available, local_model_endpoint_setting: desktopStatus?.local_model_base_url, api_sidecar: `${desktopStatus?.sidecar_host ?? "127.0.0.1"}:${desktopStatus?.sidecar_port ?? 8787}`, data_dir: desktopStatus?.data_dir ?? "app data / dev data", preview_package: desktopStatus?.preview_package_built ? "built" : "preview runtime", installer: desktopStatus?.installer_built ? "built" : "not a production installer", production_packaging: desktopStatus?.production_packaging_status ?? (desktopStatus?.production_packaging ? "ready" : "future stage pending") }} /></section>

      <section className="layout-grid bottom-grid"><div className="panel"><div className="section-heading"><p className="eyebrow">模型與權限</p><h2>自接入設定狀態</h2></div><JsonBlock value={{ model, permissions, sandbox_active: model?.mode === "sandbox", no_external_model_called: model?.mode === "sandbox", no_api_key_required: model?.mode === "sandbox", workflow_testing_only: model?.mode === "sandbox" }} /><div className="action-grid"><button type="button" onClick={() => run("啟用 Sandbox Mode", () => api("/api/settings/model", { method: "POST", body: JSON.stringify({ mode: "sandbox" }) }))}>Sandbox Mode｜沙盒模式</button><button type="button" onClick={() => run("測試模型", () => api("/api/model/test", { method: "POST" }))}>測試模型連線</button><button type="button" onClick={() => run("開啟模型生成權限", () => api("/api/settings/permissions", { method: "POST", body: JSON.stringify({ model_generate: true }) }))}>開啟 model_generate</button></div><p className="lock-note">Sandbox Mode: Run the full SCBKR workflow without a real model or API key. No external model called. Workflow testing only.</p></div>
        <div className="panel"><div className="section-heading"><p className="eyebrow">生成 / 驗收 / 入庫計畫</p><h2>操作閉環</h2></div><div className="action-grid"><button type="button" disabled={!task?.confirmed} onClick={() => { if (model?.mode === "sandbox" && permissions?.model_generate !== true) { setMessage("請先開啟 model_generate 權限。"); return; } void run("模型生成", () => api(`/api/tasks/${task?.task_id}/generate`, { method: "POST" })); }}>開始生成</button><button type="button" disabled={!task?.generation_result} onClick={() => run("通過驗收", () => api(`/api/tasks/${task?.task_id}/review`, { method: "POST", body: JSON.stringify({ review_decision: "pass", review_message: "P12 UI pass" }) }))}>通過驗收</button><button type="button" disabled={!task?.generation_result} onClick={() => run("驗收失敗", () => api(`/api/tasks/${task?.task_id}/review`, { method: "POST", body: JSON.stringify({ review_decision: "fail", review_message: "P12 UI fail" }) }))}>驗收失敗 / P11 草案</button><button type="button" disabled={task?.status !== "review_passed"} onClick={() => run("入庫請求", () => api(`/api/tasks/${task?.task_id}/storage-request`, { method: "POST" }))}>產生入庫請求</button><button type="button" disabled={!task?.storage_request} onClick={() => run("入庫計畫", () => api(`/api/tasks/${task?.task_id}/storage-confirm`, { method: "POST", body: JSON.stringify({ storage_confirmed: true, confirmed_by: "user", signature: "user", selected_targets: ["corpus", "logic", "exports"] }) }))}>確認入庫計畫</button><button type="button" disabled={task?.status !== "storage_committed"} onClick={() => run("確認 SCBKR 完成", () => api(`/api/tasks/${task?.task_id}/complete`, { method: "POST", body: JSON.stringify({ confirmed_by: "user" }) }))}>確認 SCBKR 完成</button></div><p className="lock-note">{message}</p><details open><summary>審計原始資料 / Raw Audit Details</summary><JsonBlock value={{ generation_result: task?.generation_result, review_result: task?.review_result, storage_request: task?.storage_request, storage_plan: task?.storage_plan, memory_rule_draft: task?.memory_rule_draft }} /></details></div></section>
    </main>
  );
}

export default App;
