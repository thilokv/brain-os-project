// Deterministic mock data for the Brain OS dashboard.
//
// A seeded PRNG (not Math.random) keeps every render identical between the
// server and the client -- using Math.random or `new Date()` here would
// produce a React hydration mismatch the moment SSR output and the first
// client render disagree on a single number.

import type {
  Anomaly,
  AnomalySummaryEntry,
  AuditAction,
  AuditEvent,
  ErrorRatePoint,
  PipelineStage,
  RiskTrendPoint,
  SavingsTrendPoint,
  TopFinding,
  WorkflowRecord,
  WorkflowStatus,
} from "@/lib/types";

// Fixed "today" so every relative date (last 90 days, last 12 months, ...)
// resolves to the same calendar dates on every render, forever.
export const ANCHOR_DATE = new Date("2026-08-14T09:00:00Z");

function mulberry32(seed: number) {
  let a = seed;
  return function random() {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const rand = mulberry32(20260814);
const pick = <T,>(arr: readonly T[]): T => arr[Math.floor(rand() * arr.length)];
const int = (min: number, max: number) => Math.floor(rand() * (max - min + 1)) + min;
const float = (min: number, max: number, decimals = 2) => {
  const v = rand() * (max - min) + min;
  const p = 10 ** decimals;
  return Math.round(v * p) / p;
};
const daysAgo = (n: number) => new Date(ANCHOR_DATE.getTime() - n * 86_400_000);

// ---------------------------------------------------------------------------
// Reference data
// ---------------------------------------------------------------------------

const VENDORS: { name: string; department: string }[] = [
  { name: "Acme Logistics", department: "Supply Chain" },
  { name: "Meridian Freight Co.", department: "Supply Chain" },
  { name: "Northwind Office Supply", department: "Operations" },
  { name: "Titan Industrial Parts", department: "Manufacturing" },
  { name: "Beacon Professional Services", department: "Legal" },
  { name: "Crestline Consulting", department: "Strategy" },
  { name: "Harborview IT Solutions", department: "Engineering" },
  { name: "Summit Facilities Group", department: "Facilities" },
  { name: "Blue Ridge Marketing", department: "Marketing" },
  { name: "Cascade Cloud Services", department: "Engineering" },
  { name: "Ironclad Security Systems", department: "Security" },
  { name: "Vantage HR Partners", department: "People" },
  { name: "Redwood Print & Media", department: "Marketing" },
  { name: "Pinnacle Equipment Rental", department: "Manufacturing" },
  { name: "Sterling Legal Group", department: "Legal" },
];

const ANOMALY_LIBRARY: { code: string; label: string; detail: string; severity: Anomaly["severity"] }[] = [
  { code: "missing_vendor", label: "Missing vendor", detail: "No vendor name could be extracted from the invoice text.", severity: "high" },
  { code: "missing_po_number", label: "Missing PO number", detail: "No purchase order number could be extracted from the invoice text.", severity: "medium" },
  { code: "missing_amount", label: "Missing amount", detail: "No invoice amount could be extracted from the invoice text.", severity: "high" },
  { code: "unusually_high_amount", label: "Unusually high amount", detail: "Amount is more than 10x the auto-approval threshold.", severity: "high" },
  { code: "possible_duplicate_invoice", label: "Possible duplicate", detail: "High similarity to a previously processed invoice.", severity: "high" },
];

function workflowId(n: number) {
  return `wf-${n.toString(16).padStart(12, "0")}`;
}

// ---------------------------------------------------------------------------
// Workflow records (120 days of invoice activity)
// ---------------------------------------------------------------------------

const AUTO_APPROVE_THRESHOLD = 5000;
const WORKFLOW_COUNT = 260;

export const workflows: WorkflowRecord[] = Array.from({ length: WORKFLOW_COUNT }, (_, i) => {
  const vendor = pick(VENDORS);
  const ageDays = int(0, 120);
  const submitted = daysAgo(ageDays);

  // Amount distribution: mostly small/routine, a long tail of large invoices.
  const amountRoll = rand();
  const amount =
    amountRoll < 0.55
      ? float(80, 4999, 2)
      : amountRoll < 0.85
        ? float(5001, 25000, 2)
        : float(25001, 180000, 2);

  const anomalies: Anomaly[] = [];
  if (rand() < 0.06) anomalies.push({ ...pick(ANOMALY_LIBRARY.filter((a) => a.code.startsWith("missing"))) });
  if (amount > AUTO_APPROVE_THRESHOLD * 10 && rand() < 0.7) {
    anomalies.push({ ...ANOMALY_LIBRARY.find((a) => a.code === "unusually_high_amount")! });
  }
  if (rand() < 0.05) anomalies.push({ ...ANOMALY_LIBRARY.find((a) => a.code === "possible_duplicate_invoice")! });

  const hasHighSeverity = anomalies.some((a) => a.severity === "high");
  const autoApproved = amount <= AUTO_APPROVE_THRESHOLD && !hasHighSeverity;

  const riskBase = Math.min(70, (amount / AUTO_APPROVE_THRESHOLD) * 35);
  const riskPenalty = anomalies.reduce((sum, a) => sum + (a.severity === "high" ? 20 : a.severity === "medium" ? 10 : 5), 0);
  const riskScore = Math.round(Math.min(100, riskBase + riskPenalty) * 10) / 10;

  // Recent invoices are more likely to still be mid-flight.
  const isRecent = ageDays < 2;
  let status: WorkflowStatus;
  let approvalDecision: WorkflowRecord["approvalDecision"] = null;
  let approvedBy: string | null = null;
  let completedAt: string | null = null;

  if (autoApproved) {
    status = "completed";
    approvalDecision = "approved";
    approvedBy = "system:auto_approval";
  } else if (isRecent && rand() < 0.35) {
    status = "awaiting_approval";
  } else {
    const rejected = rand() < 0.12 || hasHighSeverity && rand() < 0.3;
    status = rejected ? "rejected" : "completed";
    approvalDecision = rejected ? "rejected" : "approved";
    approvedBy = pick(["alice.chen", "marcus.webb", "priya.nair", "d.okafor", "s.rodriguez"]);
  }

  const processingSeconds = status === "awaiting_approval" ? 0 : autoApproved ? float(1.2, 4.5) : float(1800, 172800);
  if (status !== "awaiting_approval") {
    completedAt = new Date(submitted.getTime() + processingSeconds * 1000).toISOString();
  }

  return {
    workflowId: workflowId(i + 1),
    vendor: vendor.name,
    department: vendor.department,
    poNumber: `PO-${int(1000, 9999)}`,
    amount,
    currency: "USD",
    riskScore,
    autoApproved,
    anomalies,
    status,
    approvalDecision,
    approvedBy,
    submittedAt: submitted.toISOString(),
    completedAt,
    processingSeconds,
    briefingGeneratedBy: status === "awaiting_approval" ? null : rand() < 0.72 ? "anthropic" : "deterministic_fallback",
  } satisfies WorkflowRecord;
}).sort((a, b) => new Date(b.submittedAt).getTime() - new Date(a.submittedAt).getTime());

// ---------------------------------------------------------------------------
// Audit trail (derived from workflow lifecycle, mirrors the real action set)
// ---------------------------------------------------------------------------

export const auditLog: AuditEvent[] = (() => {
  const events: AuditEvent[] = [];
  let id = 1;
  for (const wf of workflows) {
    const t0 = new Date(wf.submittedAt).getTime();
    const push = (offsetMs: number, action: AuditAction, status: string, detail: string | null) => {
      events.push({ id: id++, workflowId: wf.workflowId, vendor: wf.vendor, timestamp: new Date(t0 + offsetMs).toISOString(), action, status, detail });
    };

    push(0, "workflow.start", "received", null);
    push(120, "document_intelligence.extract", "completed", `vendor='${wf.vendor}' po_number='${wf.poNumber}' amount=${wf.amount}`);
    push(340, "risk_engine.assess", wf.autoApproved ? "auto_approved" : wf.status === "awaiting_approval" ? "awaiting_approval" : "awaiting_approval", `risk_score=${wf.riskScore} anomalies=${JSON.stringify(wf.anomalies.map((a) => a.code))}`);

    if (!wf.autoApproved) {
      push(410, "notification.slack", rand() < 0.85 ? "sent" : "skipped", null);
    }

    if (wf.status !== "awaiting_approval") {
      const decisionOffset = wf.autoApproved ? 420 : wf.processingSeconds * 1000;
      if (wf.autoApproved) {
        push(decisionOffset, "risk_engine.auto_approve", "approved", null);
      } else {
        push(decisionOffset, "human_in_loop.decision", wf.approvalDecision ?? "approved", wf.approvalDecision === "rejected" ? pick(["budget exceeded", "duplicate submission", "missing supporting documentation", "vendor not on approved list"]) : null);
      }
      push(decisionOffset + 60, "executive_briefing.generate", "completed", wf.briefingGeneratedBy);
    }
  }
  return events.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
})();

// ---------------------------------------------------------------------------
// Executive Dashboard aggregates
// ---------------------------------------------------------------------------

const MANUAL_REVIEW_MINUTES = 18; // assumed manual processing time Brain OS replaces
const ANALYST_COST_PER_HOUR = 42;

export const kpis = (() => {
  const completed = workflows.filter((w) => w.status === "completed" || w.status === "rejected");
  const totalValue = workflows.reduce((s, w) => s + w.amount, 0);
  const autoApprovedCount = workflows.filter((w) => w.autoApproved).length;
  const awaitingCount = workflows.filter((w) => w.status === "awaiting_approval").length;
  const rejectedCount = workflows.filter((w) => w.status === "rejected").length;
  const avgProcessingSeconds =
    completed.reduce((s, w) => s + w.processingSeconds, 0) / Math.max(1, completed.length);

  const hoursSaved = (completed.length * MANUAL_REVIEW_MINUTES) / 60;
  const laborSavings = hoursSaved * ANALYST_COST_PER_HOUR;
  const duplicatesCaught = workflows.filter((w) => w.anomalies.some((a) => a.code === "possible_duplicate_invoice")).length;
  const duplicateSavings = duplicatesCaught * 3200; // avg duplicate invoice value assumption
  const totalSavings = Math.round(laborSavings + duplicateSavings);
  const platformCost = 4800; // monthly assumed platform cost for ROI calc
  const roi = Math.round(((totalSavings - platformCost) / platformCost) * 1000) / 10;

  return {
    totalProcessed: workflows.length,
    totalValue,
    autoApprovalRate: Math.round((autoApprovedCount / workflows.length) * 1000) / 10,
    awaitingCount,
    rejectedCount,
    avgProcessingSeconds: Math.round(avgProcessingSeconds),
    hoursSaved: Math.round(hoursSaved),
    totalSavings,
    laborSavings: Math.round(laborSavings),
    duplicateSavings: Math.round(duplicateSavings),
    platformCost,
    roi,
    duplicatesCaught,
  };
})();

export const savingsTrend: SavingsTrendPoint[] = (() => {
  const months = ["Sep 2025", "Oct 2025", "Nov 2025", "Dec 2025", "Jan 2026", "Feb 2026", "Mar 2026", "Apr 2026", "May 2026", "Jun 2026", "Jul 2026", "Aug 2026"];
  let base = 38000;
  return months.map((month, i) => {
    base += float(1800, 5200);
    const invoiceCount = int(140, 210) + i * 3;
    const processedValue = Math.round(base * 4.4);
    const savedValue = Math.round(base);
    return { month, processedValue, savedValue, invoiceCount };
  });
})();

export const openWorkflowsByDepartment = (() => {
  const open = workflows.filter((w) => w.status === "awaiting_approval");
  const byDept = new Map<string, { department: string; count: number; value: number }>();
  for (const w of open) {
    const entry = byDept.get(w.department) ?? { department: w.department, count: 0, value: 0 };
    entry.count += 1;
    entry.value += w.amount;
    byDept.set(w.department, entry);
  }
  return Array.from(byDept.values()).sort((a, b) => b.value - a.value);
})();

// ---------------------------------------------------------------------------
// Workflow Monitoring aggregates
// ---------------------------------------------------------------------------

export const pipelineStages: PipelineStage[] = [
  { key: "intake", label: "Document Intake", count: 6, avgSeconds: 0.4, status: "good" },
  { key: "extraction", label: "Document Intelligence", count: 4, avgSeconds: 0.6, status: "good" },
  { key: "risk", label: "Risk Assessment", count: 5, avgSeconds: 0.9, status: "good" },
  { key: "approval", label: "Approval Gate", count: kpis.awaitingCount, avgSeconds: 14400, status: kpis.awaitingCount > 40 ? "warning" : "good" },
  { key: "briefing", label: "Executive Briefing", count: 3, avgSeconds: 1.8, status: "good" },
];

export const errorRateTrend: ErrorRatePoint[] = Array.from({ length: 30 }, (_, i) => {
  const d = daysAgo(29 - i);
  const totalRuns = int(35, 95);
  const errors = rand() < 0.15 ? int(2, 6) : int(0, 1);
  return {
    date: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    totalRuns,
    errors,
    errorRate: Math.round((errors / totalRuns) * 1000) / 10,
  };
});

export const statusBreakdown = (() => {
  const counts: Record<WorkflowStatus, number> = {
    auto_approved: 0,
    awaiting_approval: 0,
    approved: 0,
    rejected: 0,
    completed: 0,
  };
  for (const w of workflows) counts[w.status]++;
  return counts;
})();

export const processingMetrics = (() => {
  const trackedDays = 120;
  const throughputPerDay = Math.round((workflows.length / trackedDays) * 10) / 10;
  const totalRuns30d = errorRateTrend.reduce((s, p) => s + p.totalRuns, 0);
  const totalErrors30d = errorRateTrend.reduce((s, p) => s + p.errors, 0);
  const errorRate30d = Math.round((totalErrors30d / totalRuns30d) * 1000) / 10;
  const last7 = errorRateTrend.slice(-7);
  const errorRate7d =
    Math.round((last7.reduce((s, p) => s + p.errors, 0) / last7.reduce((s, p) => s + p.totalRuns, 0)) * 1000) / 10;
  const successRate = Math.round((1 - totalErrors30d / totalRuns30d) * 1000) / 10;

  return {
    throughputPerDay,
    successRate,
    errorRate7d,
    errorRate30d,
    totalErrors30d,
    totalRuns30d,
  };
})();

// ---------------------------------------------------------------------------
// AI Insights aggregates
// ---------------------------------------------------------------------------

export const riskTrend: RiskTrendPoint[] = Array.from({ length: 12 }, (_, i) => {
  const weekStart = daysAgo((11 - i) * 7);
  return {
    week: weekStart.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    avgRiskScore: float(22, 48, 1),
    highSeverityAnomalies: int(1, 14),
  };
});

export const anomalySummary: AnomalySummaryEntry[] = ANOMALY_LIBRARY.map((a) => {
  const count = workflows.filter((w) => w.anomalies.some((x) => x.code === a.code)).length;
  return {
    code: a.code,
    label: a.label,
    severity: a.severity,
    count,
    trend: float(-28, 34, 1),
  };
}).sort((a, b) => b.count - a.count);

export const topFindings: TopFinding[] = workflows
  .filter((w) => w.anomalies.length > 0)
  .sort((a, b) => b.riskScore - a.riskScore)
  .slice(0, 8)
  .map((w) => {
    const primary = w.anomalies[0];
    const titleMap: Record<string, string> = {
      possible_duplicate_invoice: `Likely duplicate submission from ${w.vendor}`,
      unusually_high_amount: `Unusually large invoice from ${w.vendor}`,
      missing_vendor: `Vendor identity could not be verified`,
      missing_po_number: `Invoice submitted without a PO number`,
      missing_amount: `Invoice amount could not be extracted`,
    };
    return {
      id: w.workflowId,
      title: titleMap[primary.code] ?? primary.detail,
      summary: primary.detail,
      severity: primary.severity,
      vendor: w.vendor,
      workflowId: w.workflowId,
      amountAtRisk: w.amount,
      detectedAt: w.submittedAt,
    } satisfies TopFinding;
  });

export const anomalyInsights = (() => {
  const flaggedWorkflows = workflows.filter((w) => w.anomalies.length > 0);
  const highSeverity = workflows.filter((w) => w.anomalies.some((a) => a.severity === "high"));
  const totalAtRisk = flaggedWorkflows.reduce((s, w) => s + w.amount, 0);
  const detectionRate = Math.round((flaggedWorkflows.length / workflows.length) * 1000) / 10;

  return {
    flaggedCount: flaggedWorkflows.length,
    highSeverityCount: highSeverity.length,
    totalAtRisk,
    detectionRate,
  };
})();
