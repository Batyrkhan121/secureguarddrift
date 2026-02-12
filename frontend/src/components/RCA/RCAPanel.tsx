import { useState } from "react";
import { useRootCause, useBlastRadius } from "@/api/hooks";
import { predictDrift } from "@/api/client";
import { notify } from "@/components/Toast";
import RootCauseCard from "./RootCauseCard";
import BlastRadiusPanel from "./BlastRadiusPanel";
import type { DriftPrediction } from "@/api/types";

interface RCAPanelProps {
  snapshotId?: string;
  nodes: { name: string; node_type: string }[];
}

export default function RCAPanel({ snapshotId, nodes }: RCAPanelProps) {
  const [blastService, setBlastService] = useState("");
  const [predictJson, setPredictJson] = useState("");
  const [predictions, setPredictions] = useState<DriftPrediction[]>([]);
  const { data: rootCause, isLoading: rcaLoading } = useRootCause(snapshotId);
  const { data: blastData } = useBlastRadius(blastService || undefined, snapshotId);

  const handlePredict = () => {
    try {
      const changes = JSON.parse(predictJson || "{}");
      predictDrift(changes)
        .then((r) => { setPredictions(r.predictions); notify.success("Prediction complete"); })
        .catch(() => notify.error("Prediction failed"));
    } catch {
      notify.error("Invalid JSON");
    }
  };

  return (
    <div data-testid="rca-panel" className="p-2 space-y-4 text-sm">
      {/* Root Cause Analysis */}
      <div>
        <h3 className="font-bold text-xs uppercase text-gray-500 mb-2">Root Cause Analysis</h3>
        {!snapshotId && <p className="text-xs text-gray-500">Select a snapshot to analyze</p>}
        {rcaLoading && <p className="text-xs text-gray-500">Analyzing...</p>}
        {rootCause?.root_causes.map((c, i) => (
          <RootCauseCard key={c.service} candidate={c} rank={i + 1} />
        ))}
        {rootCause && rootCause.root_causes.length === 0 && (
          <p className="text-xs text-gray-500">No root causes identified</p>
        )}
      </div>

      {/* Blast Radius */}
      <div>
        <h3 className="font-bold text-xs uppercase text-gray-500 mb-2">Blast Radius</h3>
        <select
          value={blastService}
          onChange={(e) => setBlastService(e.target.value)}
          className="w-full bg-[#1a1a2e] border border-[#0f3460] rounded px-2 py-1 text-xs mb-2"
        >
          <option value="">Select a service...</option>
          {nodes.map((n) => <option key={n.name} value={n.name}>{n.name}</option>)}
        </select>
        {blastData && <BlastRadiusPanel data={blastData} />}
      </div>

      {/* Predict Drift */}
      <div>
        <h3 className="font-bold text-xs uppercase text-gray-500 mb-2">Predict Drift</h3>
        <textarea
          value={predictJson}
          onChange={(e) => setPredictJson(e.target.value)}
          placeholder='{"add_services": ["new-svc"], "add_edges": [{"source": "api-gw", "destination": "new-svc"}]}'
          className="w-full bg-[#1a1a2e] border border-[#0f3460] rounded px-2 py-1.5 text-xs h-20 resize-none mb-2"
        />
        <button onClick={handlePredict} className="bg-blue-600 hover:bg-blue-700 text-white text-xs px-3 py-1 rounded w-full">
          Predict
        </button>
        {predictions.length > 0 && (
          <div className="mt-2 space-y-1">
            {predictions.map((p, i) => (
              <div key={i} className="bg-[#16213e] border border-[#0f3460] rounded p-2 text-xs">
                <div className="flex justify-between">
                  <span className="font-semibold">{p.predicted_event}</span>
                  <span className="capitalize text-yellow-400">{p.predicted_severity}</span>
                </div>
                <div className="text-gray-400">{p.source} → {p.destination}</div>
                <div className="text-gray-500 mt-1">{p.recommendation}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
