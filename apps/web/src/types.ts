export type TaskStatus =
  | "draft"
  | "waiting_scbkr"
  | "waiting_user_confirm"
  | "confirmed"
  | "generating"
  | "waiting_review"
  | "review_passed"
  | "review_failed"
  | "rollback_requested"
  | "waiting_storage_request"
  | "waiting_storage_confirm"
  | "memory_rule_waiting_confirm"
  | "memory_rule_stored"
  | "completed"
  | "paused"
  | "error";

export type TaskType =
  | "general"
  | "coding"
  | "info_search"
  | "fraud_audit"
  | "document_audit"
  | "app_design"
  | "game_design"
  | "animation"
  | "music"
  | "privacy"
  | "workflow"
  | "private_memory";

export type TaskSummary = {
  name: string;
  taskId: string;
  taskType: TaskType;
  status: TaskStatus;
  confirmed: boolean;
  reviewPassed: boolean;
  storageConfirmed: boolean;
  ledgerId: string;
  traceId: string;
};

export type ScbkrDimension = {
  key: "S" | "C" | "B" | "K" | "R";
  title: string;
  summary: string;
  status: "待確認";
};

export type DatabaseStatus = {
  name: string;
  status: string;
};
