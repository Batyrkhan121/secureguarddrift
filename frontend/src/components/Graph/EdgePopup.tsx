import { useEffect, useRef } from "react";
import type { Edge, DriftEvent } from "@/api/types";

interface EdgePopupProps {
  edge: Edge;
  driftEvents: DriftEvent[];
  position: { x: number; y: number };
  onClose: () => void;
}

export default function EdgePopup({ edge, driftEvents, position, onClose }: EdgePopupProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as HTMLElement)) onClose();
    }
    document.addEventListener("keydown", handleKey);
    document.addEventListener("mousedown", handleClick);
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.removeEventListener("mousedown", handleClick);
    };
  }, [onClose]);

  const related = driftEvents.filter(
    (e) => e.source === edge.source && e.destination === edge.destination,
  );

  const badgeClass: Record<string, string> = {
    critical: "bg-critical text-white",
    high: "bg-high text-black",
    medium: "bg-medium text-black",
    low: "bg-low text-black",
  };

  return (
    <div
      ref={ref}
      className="absolute bg-[#2a2a4a] border border-svc rounded-lg p-3 max-w-[300px] text-sm z-50"
      style={{ left: position.x, top: position.y }}
    >
      <div className="font-bold mb-1">{edge.source} → {edge.destination}</div>
      <div className="text-gray-400">Requests: {edge.request_count}</div>
      <div className={edge.error_rate > 0.05 ? "text-critical" : "text-gray-400"}>
        Errors: {edge.error_count} ({(edge.error_rate * 100).toFixed(1)}%)
      </div>
      <div className="text-gray-400">Avg latency: {edge.avg_latency_ms.toFixed(1)}ms</div>
      <div className="text-gray-400">P99 latency: {edge.p99_latency_ms.toFixed(1)}ms</div>
      {related.length > 0 && (
        <div className="mt-2 border-t border-gray-600 pt-2">
          {related.map((evt) => (
            <span key={evt.id} className={`inline-block text-xs font-bold px-2 py-0.5 rounded-full mr-1 mt-1 ${badgeClass[evt.severity] ?? ""}`}>
              {evt.severity}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
