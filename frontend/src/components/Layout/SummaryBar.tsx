import type { DriftSummary } from "@/api/types";

interface SummaryBarProps {
  summary: DriftSummary | undefined;
  policyCount?: number;
}

export default function SummaryBar({ summary, policyCount = 0 }: SummaryBarProps) {
  if (!summary) return null;

  return (
    <div data-testid="summary-bar" className="fixed bottom-0 left-0 right-0 h-10 bg-[#12122a] border-t border-[#0f3460] flex items-center justify-center gap-5 text-sm font-mono z-50">
      <span>Total: {summary.total}</span>
      <span className="text-critical">Critical: {summary.critical}</span>
      <span className="text-high">High: {summary.high}</span>
      <span className="text-medium">Medium: {summary.medium}</span>
      <span className="text-low">Low: {summary.low}</span>
      {policyCount > 0 && (
        <span className="text-gray-400">Policies: {policyCount}</span>
      )}
    </div>
  );
}
