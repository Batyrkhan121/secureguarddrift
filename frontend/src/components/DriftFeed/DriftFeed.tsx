import { useState } from "react";
import type { DriftEvent } from "@/api/types";
import DriftCard from "./DriftCard";

interface DriftFeedProps {
  events: DriftEvent[];
  onFeedback?: (eventId: string, verdict: string) => void;
  onHoverEdge?: (source: string, destination: string) => void;
  onLeaveEdge?: () => void;
}

export default function DriftFeed({ events, onFeedback, onHoverEdge, onLeaveEdge }: DriftFeedProps) {
  const [openIdx, setOpenIdx] = useState<number | null>(null);

  if (!events.length) {
    return (
      <div className="text-center py-10 text-gray-500">
        No drift events
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1.5 p-2">
      {events.map((evt, i) => (
        <DriftCard
          key={evt.id}
          event={evt}
          isOpen={openIdx === i}
          onToggle={() => setOpenIdx(openIdx === i ? null : i)}
          onFeedback={onFeedback}
          onHover={onHoverEdge}
          onLeave={onLeaveEdge}
        />
      ))}
    </div>
  );
}
