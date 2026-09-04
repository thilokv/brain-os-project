// Types mirror the real Brain OS FastAPI backend schema (app/models/schemas.py)
// so this dashboard's mock data reads as a faithful view of the actual system.

export type ApprovalDecision = "approved" | "rejected";

export type WorkflowStatus =
  | "auto_approved"
  | "awaiting_approval"
  | "approved"
  | "rejected"
  | "completed";

export type AnomalySeverity = "low" | "medium" | "high";

export interface Anomaly {
  code: string;
  detail: string;
  severity: AnomalySeverity;
}

export interface WorkflowRecord {
  workflowId: string;
  vendor: string;
  department: string;
  poNumber: string;
  amount: number;
  currency: "USD";
  riskScore: number;
  autoApproved: boolean;
  anomalies: Anomaly[];
  status: WorkflowStatus;
  approvalDecision: ApprovalDecision | null;
  approvedBy: string | null;
  submittedAt: string; // ISO timestamp
  completedAt: string | null; // ISO timestamp
  processingSeconds: number;
  briefingGeneratedBy: "anthropic" | "deterministic_fallback" | null;
}

export type AuditAction =
  | "workflow.start"
  | "document_intelligence.extract"
  | "risk_engine.assess"
  | "risk_engine.auto_approve"
  | "notification.slack"
  | "human_in_loop.decision"
  | "executive_briefing.generate";

export interface AuditEvent {
  id: number;
  workflowId: string;
  vendor: string;
  timestamp: string;
  action: AuditAction;
  status: string;
  detail: string | null;
}

export interface SavingsTrendPoint {
  month: string; // "Jan 2026"
  processedValue: number;
  savedValue: number;
  invoiceCount: number;
}

export interface PipelineStage {
  key: string;
  label: string;
  count: number;
  avgSeconds: number;
  status: "good" | "warning" | "serious" | "critical";
}

export interface ErrorRatePoint {
  date: string; // "Aug 1"
  totalRuns: number;
  errors: number;
  errorRate: number;
}

export interface RiskTrendPoint {
  week: string;
  avgRiskScore: number;
  highSeverityAnomalies: number;
}

export interface AnomalySummaryEntry {
  code: string;
  label: string;
  severity: AnomalySeverity;
  count: number;
  trend: number; // % change vs prior period
}

export interface TopFinding {
  id: string;
  title: string;
  summary: string;
  severity: AnomalySeverity;
  vendor: string;
  workflowId: string;
  amountAtRisk: number;
  detectedAt: string;
}
