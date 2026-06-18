import type { DatabaseStatus, ScbkrDimension, TaskSummary, TaskType } from "./types";

const taskTypes: { value: TaskType; label: string }[] = [
  { value: "general", label: "一般任務" },
  { value: "coding", label: "程式開發" },
  { value: "info_search", label: "資訊查詢" },
  { value: "fraud_audit", label: "詐騙稽核" },
  { value: "document_audit", label: "文件稽核" },
  { value: "app_design", label: "應用設計" },
  { value: "game_design", label: "遊戲設計" },
  { value: "animation", label: "動畫" },
  { value: "music", label: "音樂" },
  { value: "privacy", label: "隱私" },
  { value: "workflow", label: "工作流程" },
  { value: "private_memory", label: "私人記憶" },
];

const mockTask: TaskSummary = {
  name: "P3 前端主畫面 mock 任務",
  taskId: "mock-task-p3-local",
  taskType: "workflow",
  status: "waiting_user_confirm",
  confirmed: false,
  reviewPassed: false,
  storageConfirmed: false,
  ledgerId: "mock-ledger-p3-local",
  traceId: "mock-trace-p3-local",
};

const dimensions: ScbkrDimension[] = [
  {
    key: "S",
    title: "S｜介面 / 主體",
    summary: "確認任務主體、使用者輸入、輸出形式與操作介面。",
    status: "待確認",
  },
  {
    key: "C",
    title: "C｜後端 / 因果",
    summary: "整理流程順序、資料流、事件流、依賴與失敗影響。",
    status: "待確認",
  },
  {
    key: "B",
    title: "B｜邊界 / 行為",
    summary: "標示資料讀寫範圍、停止條件、敏感操作與入庫邊界。",
    status: "待確認",
  },
  {
    key: "K",
    title: "K｜依據 / 風格",
    summary: "列出依據、參考來源、風格設定、技術選擇與可信度。",
    status: "待確認",
  },
  {
    key: "R",
    title: "R｜回放 / 簽名",
    summary: "定義驗收條件、ledger 要求、簽名狀態與回放需求。",
    status: "待確認",
  },
];

const databaseStatuses: DatabaseStatus[] = [
  { name: "向量庫", status: "未連線" },
  { name: "語料庫", status: "未連線" },
  { name: "程式邏輯庫", status: "未連線" },
  { name: "記憶庫", status: "未連線" },
  { name: "回放帳本", status: "本地 JSONL 尚未接入 UI" },
];

const startGenerationDisabled = !mockTask.confirmed;
const confirmStorageDisabled = !mockTask.reviewPassed;

function App() {
  return (
    <main className="app-shell">
      <section className="top-status-bar" aria-label="系統狀態列">
        <div className="product-name">SCBKR 本地責任鏈模型</div>
        <div className="status-grid">
          <span>模型狀態：未連線</span>
          <span>後端狀態：未連線</span>
          <span>任務狀態：等待任務</span>
          <span>本機：localhost:5500</span>
          <span>API：localhost:8787</span>
        </div>
      </section>

      <section className="hero-card">
        <div>
          <p className="eyebrow">本地責任鏈工作台</p>
          <h1>先確認五維責任鏈，再允許模型執行。</h1>
          <p className="hero-text">
            P3 僅展示靜態前端與 mock state；目前未連線後端、未建立真任務、未寫 ledger、未啟用模型。
          </p>
        </div>
      </section>

      <section className="layout-grid">
        <div className="panel input-panel">
          <div className="section-heading">
            <p className="eyebrow">任務輸入區</p>
            <h2>建立目前任務草稿</h2>
          </div>
          <textarea
            placeholder="請輸入你的任務。系統會先建立 SCBKR 五維確認單，確認後才執行。"
            aria-label="任務內容"
          />
          <label className="field-label" htmlFor="task-type">
            任務類型
          </label>
          <select id="task-type" defaultValue={mockTask.taskType}>
            {taskTypes.map((taskType) => (
              <option key={taskType.value} value={taskType.value}>
                {taskType.label}
              </option>
            ))}
          </select>
          <div className="checkbox-row">
            <label>
              <input type="checkbox" defaultChecked /> dry_run
            </label>
            <label>
              <input type="checkbox" /> simulated
            </label>
          </div>
          <button className="primary-button" type="button">
            建立目前任務
          </button>
        </div>

        <div className="panel task-card">
          <div className="section-heading">
            <p className="eyebrow">目前任務卡片</p>
            <h2>{mockTask.name}</h2>
          </div>
          <dl className="detail-list">
            <div><dt>task_id</dt><dd>{mockTask.taskId}</dd></div>
            <div><dt>task_type</dt><dd>{mockTask.taskType}</dd></div>
            <div><dt>status</dt><dd>{mockTask.status}</dd></div>
            <div><dt>confirmed</dt><dd>{String(mockTask.confirmed)}</dd></div>
            <div><dt>review_passed</dt><dd>{String(mockTask.reviewPassed)}</dd></div>
            <div><dt>storage_confirmed</dt><dd>{String(mockTask.storageConfirmed)}</dd></div>
            <div><dt>ledger_id</dt><dd>{mockTask.ledgerId}</dd></div>
            <div><dt>trace_id</dt><dd>{mockTask.traceId}</dd></div>
          </dl>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <p className="eyebrow">SCBKR 五維確認區</p>
          <h2>五張責任鏈卡片</h2>
        </div>
        <div className="dimension-grid">
          {dimensions.map((dimension) => (
            <article className="dimension-card" key={dimension.key}>
              <div className="dimension-header">
                <h3>{dimension.title}</h3>
                <span className="status-chip">{dimension.status}</span>
              </div>
              <p>{dimension.summary}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="layout-grid bottom-grid">
        <div className="panel">
          <div className="section-heading">
            <p className="eyebrow">四庫狀態區</p>
            <h2>本地資料能力</h2>
          </div>
          <ul className="database-list">
            {databaseStatuses.map((databaseStatus) => (
              <li key={databaseStatus.name}>
                <span>{databaseStatus.name}</span>
                <strong>{databaseStatus.status}</strong>
              </li>
            ))}
          </ul>
          {!mockTask.storageConfirmed && (
            <p className="lock-note">storage_confirmed = false，因此不顯示任何「已寫入四庫」狀態。</p>
          )}
        </div>

        <div className="panel">
          <div className="section-heading">
            <p className="eyebrow">操作按鈕區</p>
            <h2>三層硬鎖展示</h2>
          </div>
          <div className="action-grid">
            <button type="button">確認責任鏈</button>
            <button type="button" disabled={startGenerationDisabled}>開始生成</button>
            <button type="button" disabled>通過驗收</button>
            <button type="button" disabled={confirmStorageDisabled}>確認入庫</button>
            <button type="button">回到 S 修改</button>
            <button type="button">回到 C 修改</button>
            <button type="button">回到 B 修改</button>
            <button type="button">回到 K 修改</button>
            <button type="button">回到 R 修改</button>
          </div>
          <p className="lock-note">confirmed = false 時開始生成 disabled；review_passed = false 時確認入庫 disabled。</p>
        </div>
      </section>
    </main>
  );
}

export default App;
