import type { RootCauseCandidate } from "@/api/types";

interface RootCauseCardProps {
  candidate: RootCauseCandidate;
  rank: number;
}

const CONFIDENCE_COLORS: Record<string, string> = {
  high: "text-red-400",
  medium: "text-yellow-400",
  low: "text-green-400",
};

function getConfidenceLevel(c: number): string {
  if (c >= 0.7) return "high";
  if (c >= 0.4) return "medium";
  return "low";
}

export default function RootCauseCard({ candidate, rank }: RootCauseCardProps) {
  const level = getConfidenceLevel(candidate.confidence);
  return (
    <div className="bg-[#16213e] border border-[#0f3460] rounded-lg p-3 mb-2">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="bg-red-600 text-white text-xs font-bold px-1.5 py-0.5 rounded">#{rank}</span>
          <span className="font-semibold text-sm">{candidate.service}</span>
        </div>
        <span className={`text-xs font-bold ${CONFIDENCE_COLORS[level]}`}>
          {Math.round(candidate.confidence * 100)}% confidence
        </span>
      </div>
      <p className="text-xs text-gray-400 mb-2">{candidate.reason}</p>
      {candidate.affected_downstream.length > 0 && (
        <div className="mb-2">
          <span className="text-xs text-gray-500">Affected downstream: </span>
          <span className="text-xs text-gray-300">{candidate.affected_downstream.join(", ")}</span>
        </div>
      )}
      {candidate.evidence.length > 0 && (
        <div>
          <span className="text-xs text-gray-500">Evidence:</span>
          <ul className="list-disc list-inside text-xs text-gray-400 mt-1">
            {candidate.evidence.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
