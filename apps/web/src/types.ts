export type TaskType =
  | "general" | "coding" | "info_search" | "fraud_audit" | "document_audit"
  | "app_design" | "game_design" | "animation" | "music" | "privacy"
  | "workflow" | "private_memory";

export type ScbkrDimensionKey = "S" | "C" | "B" | "K" | "R";

export type ModelSettings = {
  provider: string;
  mode: string;
  base_url: string;
  api_key: string;
  model_name: string;
  enabled: boolean;
  last_test_status: string;
  last_test_message: string;
  sandbox?: boolean;
  external_call_performed?: boolean;
};

export type Permissions = Record<string, boolean | string | null>;

export type TaskSummary = {
  task_id: string;
  task_name: string;
  task_type: TaskType;
  status: string;
  confirmed: boolean;
  review_passed: boolean;
  storage_confirmed: boolean;
  runtime: string;
  scbkr?: Record<string, any>;
  generation_result?: Record<string, any>;
  review_result?: Record<string, any>;
  storage_request?: Record<string, any>;
  storage_plan?: Record<string, any>;
  memory_rule_draft?: Record<string, any>;
};


export type DesktopStatus = {
  desktop_stage: string;
  desktop_shell: boolean;
  installer_built: boolean;
  tauri_skeleton: boolean;
  sandbox_available: boolean;
  api_status: string;
  model_mode: string;
  local_model_base_url: string;
  external_call_required: boolean;
  production_packaging: boolean;
};
