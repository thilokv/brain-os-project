"use client";

import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Download, FileText, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EvidenceDialog } from "@/components/dashboard/evidence-dialog";
import { formatDateTime } from "@/lib/format";
import type { AuditAction, AuditEvent, WorkflowRecord } from "@/lib/types";
import { ANCHOR_DATE } from "@/lib/mock-data";

const ACTION_LABELS: Record<AuditAction, string> = {
  "workflow.start": "Workflow started",
  "document_intelligence.extract": "Fields extracted",
  "risk_engine.assess": "Risk assessed",
  "risk_engine.auto_approve": "Auto-approved",
  "notification.slack": "Slack notified",
  "human_in_loop.decision": "Human decision",
  "executive_briefing.generate": "Briefing generated",
};

const PAGE_SIZE = 20;

function toCsv(rows: AuditEvent[]): string {
  const header = ["id", "timestamp", "workflow_id", "vendor", "action", "status", "detail"];
  const lines = rows.map((r) =>
    [r.id, r.timestamp, r.workflowId, r.vendor, r.action, r.status, r.detail ?? ""]
      .map((v) => `"${String(v).replaceAll('"', '""')}"`)
      .join(","),
  );
  return [header.join(","), ...lines].join("\n");
}

function downloadCsv(csv: string, filename: string) {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function AuditLogTable({ events, workflows }: { events: AuditEvent[]; workflows: WorkflowRecord[] }) {
  const [search, setSearch] = useState("");
  const [actionFilter, setActionFilter] = useState<string>("all");
  const [page, setPage] = useState(0);
  const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowRecord | null>(null);

  const workflowById = useMemo(() => new Map(workflows.map((w) => [w.workflowId, w])), [workflows]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return events.filter((e) => {
      const matchesQuery = !q || e.workflowId.toLowerCase().includes(q) || e.vendor.toLowerCase().includes(q);
      const matchesAction = actionFilter === "all" || e.action === actionFilter;
      return matchesQuery && matchesAction;
    });
  }, [events, search, actionFilter]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount - 1);
  const pageRows = filtered.slice(currentPage * PAGE_SIZE, currentPage * PAGE_SIZE + PAGE_SIZE);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-1 flex-col gap-2 sm:flex-row">
          <div className="relative flex-1 sm:max-w-xs">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search by workflow ID or vendor…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(0);
              }}
              className="h-9 pl-8"
            />
          </div>
          <Select
            value={actionFilter}
            onValueChange={(v) => {
              setActionFilter(v ?? "all");
              setPage(0);
            }}
          >
            <SelectTrigger className="h-9 w-full sm:w-56">
              {/* Base UI's Select.Value renders the raw `value` string by
                  default (unlike Radix) -- it does not auto-resolve to the
                  matching SelectItem's label. The children render-prop is
                  the documented way to map value -> display label. */}
              <SelectValue placeholder="All actions">
                {(value: string) => (value === "all" ? "All actions" : (ACTION_LABELS[value as AuditAction] ?? value))}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All actions</SelectItem>
              {Object.entries(ACTION_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="gap-1.5"
            onClick={() => downloadCsv(toCsv(filtered), `brain-os-audit-log-${filtered.length}-events.csv`)}
          >
            <Download className="size-3.5" />
            Export CSV
          </Button>
          <Button variant="outline" size="sm" className="gap-1.5" onClick={() => window.print()}>
            <FileText className="size-3.5" />
            Export PDF
          </Button>
        </div>
      </div>

      {/* overflow-hidden (not overflow-x-auto) -- Table already wraps itself in
          its own overflow-x-auto container; this div only needs to clip that
          inner container to the rounded border, not add a second scroll region. */}
      <div className="overflow-hidden rounded-lg border border-border">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="whitespace-nowrap">Timestamp</TableHead>
              <TableHead className="whitespace-nowrap">Workflow</TableHead>
              <TableHead>Vendor</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="hidden lg:table-cell">Detail</TableHead>
              <TableHead className="text-right">Evidence</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {pageRows.map((event) => (
              <TableRow key={event.id}>
                <TableCell className="whitespace-nowrap text-xs tabular-nums text-muted-foreground">
                  {formatDateTime(event.timestamp)}
                </TableCell>
                <TableCell className="font-mono text-xs text-foreground">{event.workflowId}</TableCell>
                <TableCell className="max-w-[10rem] truncate text-sm">{event.vendor}</TableCell>
                <TableCell>
                  <Badge variant="secondary" className="font-normal">
                    {ACTION_LABELS[event.action]}
                  </Badge>
                </TableCell>
                <TableCell className="text-xs capitalize text-muted-foreground">{event.status.replaceAll("_", " ")}</TableCell>
                <TableCell className="hidden max-w-xs truncate text-xs text-muted-foreground lg:table-cell">
                  {event.detail ?? "—"}
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => setSelectedWorkflow(workflowById.get(event.workflowId) ?? null)}
                  >
                    View
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {pageRows.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="h-24 text-center text-sm text-muted-foreground">
                  No audit events match your filters.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <p>
          Showing <span className="font-medium text-foreground">{pageRows.length}</span> of{" "}
          <span className="font-medium text-foreground">{filtered.length}</span> events
        </p>
        <div className="flex items-center gap-1.5">
          <Button
            variant="outline"
            size="icon"
            className="size-7"
            disabled={currentPage === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            <ChevronLeft className="size-4" />
          </Button>
          <span className="min-w-16 text-center text-xs tabular-nums">
            Page {currentPage + 1} of {pageCount}
          </span>
          <Button
            variant="outline"
            size="icon"
            className="size-7"
            disabled={currentPage >= pageCount - 1}
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
          >
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>

      <EvidenceDialog
        workflow={selectedWorkflow}
        events={selectedWorkflow ? events.filter((e) => e.workflowId === selectedWorkflow.workflowId).sort((a, b) => a.id - b.id) : []}
        anchor={ANCHOR_DATE}
        onOpenChange={(open) => !open && setSelectedWorkflow(null)}
      />
    </div>
  );
}
