export type TaskType =
  | "general" | "coding" | "info_search" | "fraud_audit" | "document_audit"
  | "app_design" | "game_design" | "animation" | "music" | "privacy"
  | "workflow" | "private_memory";

export type ScbkrDimensionKey = "S" | "C" | "B" | "K" | "R";

export type ScbkrDimension = {
  content?: string;
  owner_draft_content?: string;
  model_draft_content?: string;
  model_explanation?: string;
  missing_information?: string[];
  needs_user_confirmation?: string[];
  model_cannot_decide?: string[];
  risk_notes?: string[];
  [key: string]: unknown;
};

export type ScbkrDraft = Partial<Record<ScbkrDimensionKey, ScbkrDimension>> & {
  rule_summary?: string;
  missing_information?: string[];
  user_confirmation_items?: string[];
  model_cannot_decide?: string[];
  risk_reminders?: string[];
  next_actions?: string[];
  draft_source?: string;
  model_name?: string;
  model_participated?: boolean;
  model_schema_valid?: boolean;
  model_semantic_valid?: boolean;
  validator_passed?: boolean;
  [key: string]: unknown;
};

export type CurrentRulePackage = {
  package_version?: string;
  task_type?: string;
  matched_rules?: Record<string, unknown>[];
  citable_data?: Record<string, unknown>[];
  user_preferences?: Record<string, unknown>[];
  retrieval_candidates?: Record<string, unknown>[];
  non_citable_data?: Record<string, unknown>[];
  prohibitions?: string[];
  stop_conditions?: string[];
  missing_information?: string[];
  output_constraints?: string[];
  plan_level?: string;
  draft_only?: boolean;
  requires_followup?: boolean;
  chat_context_used?: boolean;
  [key: string]: unknown;
};

export type PostCheck = {
  checked?: boolean;
  allowed?: boolean;
  action?: string;
  violations?: Array<{ code?: string; message?: string } | string>;
};

export type TokenCostAudit = {
  measurement_scope?: string;
  measurement_basis?: string;
  comparison_basis?: string;
  savings_verified?: boolean;
  provider_usage_available?: boolean;
  actual_usage_verified?: boolean;
  actual_prompt_tokens?: number | null;
  actual_completion_tokens?: number | null;
  actual_total_tokens?: number | null;
  baseline_prompt_tokens?: number | null;
  current_rule_package_tokens_est?: number | null;
  tokens_saved?: number | null;
  reduction_percent?: number | null;
  api_cost?: number | null;
  estimated_cost_saved?: number | null;
  price_status?: string;
  currency?: string;
  chat_context_used?: boolean;
  formal_source_summary?: {
    matched_rules?: number;
    citable_data?: number;
    user_preferences?: number;
    vector_candidates?: number;
    non_citable_data?: number;
    vector_recall_only?: boolean;
  };
  [key: string]: unknown;
};

export type ChatResponse = {
  reply: string;
  route_mode?: string;
  current_rule_package?: CurrentRulePackage;
  token_cost_audit?: TokenCostAudit;
  post_check?: PostCheck;
  model_used?: boolean;
  model_connected?: boolean;
  suggestion?: Record<string, unknown> | null;
  rule_state?: Record<string, unknown>;
};

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
  temperature?: number;
  max_tokens?: number;
  context_length?: number;
  timeout?: number;
};

export type Permissions = Record<string, boolean | string | null>;

export type TaskSummary = {
  task_id: string;
  task_name: string;
  task_type: TaskType;
  raw_input?: string;
  status: string;
  confirmed: boolean;
  review_passed: boolean;
  storage_confirmed: boolean;
  runtime: string;
  rule_assist_plan?: string;
  rule_assist?: Record<string, any>;
  scbkr?: ScbkrDraft;
  draft_object?: Record<string, any>;
  generation_result?: Record<string, any>;
  review_result?: Record<string, any>;
  storage_request?: Record<string, any>;
  storage_plan?: Record<string, any>;
  storage_suggestion?: Record<string, any>;
  storage_result?: Record<string, any>;
  memory_rule_draft?: Record<string, any>;
  draft_model_call_skipped_reason?: string;
  data_center_context?: Record<string, any>;
  draft_source?: string;
  model_used?: boolean;
  model_provider?: string;
  model_name?: string;
  model_schema_valid?: boolean;
  model_semantic_valid?: boolean;
  validator_passed?: boolean;
  fallback_used?: boolean;
  fallback_reason?: string | null;
  requires_user_signature?: boolean;
  model_signature_allowed?: boolean;
  next_required_action?: string;
  supersedes_rule_id?: string;
  revision_instruction?: string;
  confirm_time_state_gate?: Record<string, any>;
  storage_conflict?: Record<string, any>;
  current_rule_package?: CurrentRulePackage;
  token_metrics?: TokenCostAudit;
};


export type DesktopStatus = {
  desktop_stage: string;
  desktop_shell: boolean;
  installer_built: boolean;
  preview_package_built?: boolean;
  tauri_skeleton: boolean;
  sidecar_supported?: boolean;
  sidecar_running?: boolean;
  sandbox_available: boolean;
  api_status: string;
  api_server_reachable?: boolean;
  api_url?: string;
  model_mode: string;
  local_model_base_url: string;
  sidecar_host?: string;
  sidecar_port?: number;
  data_dir?: string | null;
  external_call_required: boolean;
  preview?: boolean;
  preview_package?: string;
  production_packaging: boolean;
  production_packaging_status?: string;
  installer?: string;
  release_candidate_package_built?: boolean;
  desktop_release_candidate?: boolean;
  release_candidate_stage?: string;
  release_candidate_package?: string;
  release_candidate_installer?: string;
  store_submission_ready?: boolean;
  store_submission_target?: string;
  store_submission_blockers?: string[];
  public_edition?: string;
};
