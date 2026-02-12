import type { DriftEvent } from "@/api/types";

interface DriftCardProps {
  event: DriftEvent;
  isOpen: boolean;
  onToggle: () => void;
  onFeedback?: (eventId: string, verdict: string) => void;
  onHover?: (source: string, destination: string) => void;
  onLeave?: () => void;
}

const severityColors: Record<string, string> = {
  critical: "border-l-critical",
  high: "border-l-high",
  medium: "border-l-medium",
  low: "border-l-low",
};

const badgeColors: Record<string, string> = {
  critical: "bg-critical text-white",
  high: "bg-high text-black",
  medium: "bg-medium text-black",
  low: "bg-low text-black",
};

export default function DriftCard({ event, isOpen, onToggle, onFeedback, onHover, onLeave }: DriftCardProps) {
  const hasMl = event.ml_modifiers && Object.keys(event.ml_modifiers).length > 0;

  return (
    <div
      className={`bg-[#16213e] border border-[#0f3460] rounded-lg px-3 py-2.5 cursor-pointer border-l-4 transition-colors hover:border-[#5588cc] ${severityColors[event.severity] ?? ""}`}
      onClick={onToggle}
      onMouseEnter={() => onHover?.(event.source, event.destination)}
      onMouseLeave={() => onLeave?.()}
    >
      <div className="flex justify-between items-center">
        <span className="text-sm font-semibold">{event.title}</span>
        <div className="flex gap-1.5 items-center">
          {hasMl && (
            <span className="text-[10px] font-mono bg-purple-600 text-white px-1.5 py-0.5 rounded-full">ML</span>
          )}
          <span className={`font-mono text-xs px-2 py-0.5 rounded-full font-bold ${badgeColors[event.severity] ?? ""}`}>
            {event.risk_score}
          </span>
        </div>
      </div>
      {isOpen && (
        <div className="mt-2 text-xs leading-relaxed text-gray-400">
          <p><b className="text-gray-200">What changed:</b> {event.what_changed}</p>
          <p className="mt-1"><b className="text-gray-200">Why risk:</b></p>
          <ul className="list-disc ml-5 mt-0.5">
            {event.why_risk.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
          <p className="mt-1"><b className="text-gray-200">Affected:</b> {event.affected.join(", ")}</p>
          <p className="mt-1"><b className="text-gray-200">Recommendation:</b> {event.recommendation}</p>
          {onFeedback && (
            <div className="flex gap-2 mt-2">
              <button onClick={(e) => { e.stopPropagation(); onFeedback(event.id, "true_positive"); }}
                className="bg-[#0f3460] border border-[#0f3460] rounded px-2 py-0.5 hover:bg-[#1a4a8a]">👍</button>
              <button onClick={(e) => { e.stopPropagation(); onFeedback(event.id, "false_positive"); }}
                className="bg-[#0f3460] border border-[#0f3460] rounded px-2 py-0.5 hover:bg-[#1a4a8a]">👎</button>
              <button onClick={(e) => { e.stopPropagation(); onFeedback(event.id, "needs_review"); }}
                className="bg-[#0f3460] border border-[#0f3460] rounded px-2 py-0.5 hover:bg-[#1a4a8a]">⏭</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
