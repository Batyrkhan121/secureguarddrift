import type { BlastRadiusResponse } from "@/api/types";

interface BlastRadiusPanelProps {
  data: BlastRadiusResponse;
}

const IMPACT_COLORS: Record<string, string> = {
  critical: "bg-red-600",
  high: "bg-orange-500",
  medium: "bg-yellow-500",
  low: "bg-green-500",
};

export default function BlastRadiusPanel({ data }: BlastRadiusPanelProps) {
  return (
    <div className="bg-[#16213e] border border-[#0f3460] rounded-lg p-3">
      <div className="flex items-center justify-between mb-3">
        <h4 className="font-semibold text-sm">
          Blast Radius: <span className="text-red-400">{data.failing_service}</span>
        </h4>
        <span className="text-xs text-gray-400">
          {data.total_blast_radius} services affected
        </span>
      </div>
      <div className="space-y-1.5 mb-3">
        {data.affected.map((a) => (
          <div key={a.service} className="flex items-center justify-between text-xs bg-[#1a1a2e] rounded px-2 py-1.5">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${IMPACT_COLORS[a.impact] ?? "bg-gray-500"}`} />
              <span>{a.service}</span>
            </div>
            <div className="flex items-center gap-3 text-gray-400">
              <span>{Math.round(a.probability * 100)}%</span>
              <span>~{a.time_to_impact_minutes}min</span>
              <span className="capitalize">{a.impact}</span>
            </div>
          </div>
        ))}
      </div>
      {data.affected.length === 0 && (
        <p className="text-xs text-gray-500 text-center py-4">No downstream services affected</p>
      )}
      <div className="text-xs text-gray-500 border-t border-[#0f3460] pt-2">
        Estimated recovery: ~{data.estimated_recovery_minutes} minutes
      </div>
    </div>
  );
}
