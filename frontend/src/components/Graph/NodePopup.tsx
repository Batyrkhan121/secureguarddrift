import { useEffect, useRef } from "react";
import type { Node, Edge, DriftEvent } from "@/api/types";

interface NodePopupProps {
  node: Node;
  edges: Edge[];
  driftEvents: DriftEvent[];
  position: { x: number; y: number };
  onClose: () => void;
  onEventClick?: (eventId: string) => void;
}

export default function NodePopup({ node, edges, driftEvents, position, onClose, onEventClick }: NodePopupProps) {
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

  const incoming = edges.filter((e) => e.destination === node.name);
  const outgoing = edges.filter((e) => e.source === node.name);
  const related = driftEvents.filter((e) => e.source === node.name || e.destination === node.name);

  return (
    <div
      ref={ref}
      className="absolute bg-[#2a2a4a] border border-svc rounded-lg p-3 max-w-[300px] text-sm z-50"
      style={{ left: position.x, top: position.y }}
    >
      <div className="font-bold mb-1">{node.name}</div>
      <div className="text-gray-400">Type: {node.node_type}</div>
      <div className="text-gray-400 mb-2">Namespace: {node.namespace}</div>
      <div className="text-gray-400">Incoming: {incoming.length} | Outgoing: {outgoing.length}</div>
      {related.length > 0 && (
        <div className="mt-2 border-t border-gray-600 pt-2">
          <div className="font-semibold text-xs mb-1">Drift Events:</div>
          {related.map((evt) => (
            <div
              key={evt.id}
              className="text-svc cursor-pointer underline text-xs"
              onClick={() => onEventClick?.(evt.id)}
            >
              {evt.title} ({evt.severity})
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
