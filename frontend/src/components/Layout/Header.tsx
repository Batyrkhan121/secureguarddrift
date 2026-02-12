import { useAuthStore } from "@/store/authStore";
import ThemeToggle from "@/components/ThemeToggle";
import type { SnapshotSummary } from "@/api/types";

interface HeaderProps {
  snapshots: SnapshotSummary[];
  baselineId: string;
  currentId: string;
  onBaselineChange: (id: string) => void;
  onCurrentChange: (id: string) => void;
  onAnalyze: () => void;
  onExport: () => void;
}

export default function Header({
  snapshots, baselineId, currentId,
  onBaselineChange, onCurrentChange, onAnalyze, onExport,
}: HeaderProps) {
  const { user, logout, hasRole } = useAuthStore();

  return (
    <header className="flex items-center gap-3 px-5 py-2.5 bg-[#16213e] border-b border-[#0f3460]">
      <h1 className="text-lg font-bold shrink-0">SecureGuard Drift</h1>
      <ThemeToggle />
      <span className="flex-1" />
      <select
        value={baselineId}
        onChange={(e) => onBaselineChange(e.target.value)}
        data-testid="baseline-select"
        className="bg-[#0f3460] text-gray-200 border border-[#0f3460] rounded px-2 py-1 text-sm"
      >
        <option value="">Baseline...</option>
        {snapshots.map((s) => (
          <option key={s.id} value={s.id}>
            {s.id.slice(0, 8)} ({s.timestamp_start})
          </option>
        ))}
      </select>
      <select
        value={currentId}
        onChange={(e) => onCurrentChange(e.target.value)}
        data-testid="current-select"
        className="bg-[#0f3460] text-gray-200 border border-[#0f3460] rounded px-2 py-1 text-sm"
      >
        <option value="">Current...</option>
        {snapshots.map((s) => (
          <option key={s.id} value={s.id}>
            {s.id.slice(0, 8)} ({s.timestamp_start})
          </option>
        ))}
      </select>
      <button onClick={onAnalyze} data-testid="analyze-btn" className="bg-[#0f3460] text-gray-200 border border-[#0f3460] rounded px-3 py-1 text-sm hover:bg-[#1a4a8a]">
        Analyze
      </button>
      {hasRole("operator") && (
        <button onClick={onExport} data-testid="export-btn" className="bg-[#0f3460] text-gray-200 border border-[#0f3460] rounded px-3 py-1 text-sm hover:bg-[#1a4a8a]">
          Export Report
        </button>
      )}
      <span data-testid="user-menu" className="text-sm text-gray-400">{user?.email}</span>
      <span className="text-xs text-gray-500">({user?.role})</span>
      <button onClick={logout} data-testid="logout-btn" className="bg-[#0f3460] text-gray-200 border border-[#0f3460] rounded px-3 py-1 text-sm hover:bg-[#1a4a8a]">
        Logout
      </button>
    </header>
  );
}
