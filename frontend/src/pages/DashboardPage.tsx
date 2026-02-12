import { useState, useCallback, useEffect } from "react";
import { useSnapshots, useGraph, useDrift, useDriftSummary, usePolicies } from "@/api/hooks";
import { postFeedback } from "@/api/client";
import Header from "@/components/Layout/Header";
import SummaryBar from "@/components/Layout/SummaryBar";
import ServiceGraph from "@/components/Graph/ServiceGraph";
import NodePopup from "@/components/Graph/NodePopup";
import EdgePopup from "@/components/Graph/EdgePopup";
import DriftFeed from "@/components/DriftFeed/DriftFeed";

type Tab = "drift" | "policies";

export default function DashboardPage() {
  const [baselineId, setBaselineId] = useState("");
  const [currentId, setCurrentId] = useState("");
  const [activeTab, setActiveTab] = useState<Tab>("drift");
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<{ source: string; destination: string } | null>(null);
  const [popupPos, setPopupPos] = useState({ x: 300, y: 200 });

  const { data: snapshots = [] } = useSnapshots();
  const { data: graph } = useGraph(currentId || undefined);
  const { data: driftEvents = [] } = useDrift(baselineId || undefined, currentId || undefined);
  const { data: summary } = useDriftSummary();
  const { data: policies = [] } = usePolicies();

  const nodes = graph?.nodes ?? [];
  const edges = graph?.edges ?? [];

  const handleAnalyze = useCallback(() => {
    /* React Query auto-refetches when baselineId/currentId keys change */
  }, []);

  const handleExport = useCallback(() => {
    const data = JSON.stringify({ graph, driftEvents }, null, 2);
    const blob = new Blob([data], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `drift-report-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [graph, driftEvents]);

  const handleFeedback = useCallback((eventId: string, verdict: string) => {
    postFeedback(eventId, verdict);
  }, []);

  const handleNodeClick = useCallback((name: string) => {
    setSelectedEdge(null);
    setSelectedNode(name);
    setPopupPos({ x: 300, y: 200 });
  }, []);

  const handleEdgeClick = useCallback((source: string, destination: string) => {
    setSelectedNode(null);
    setSelectedEdge({ source, destination });
    setPopupPos({ x: 300, y: 200 });
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setSelectedNode(null);
        setSelectedEdge(null);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  const selectedNodeData = nodes.find((n) => n.name === selectedNode);
  const selectedEdgeData = edges.find(
    (e) => selectedEdge && e.source === selectedEdge.source && e.destination === selectedEdge.destination,
  );

  return (
    <div className="flex flex-col h-screen bg-[#1a1a2e] text-gray-200">
      <Header
        snapshots={snapshots}
        baselineId={baselineId}
        currentId={currentId}
        onBaselineChange={setBaselineId}
        onCurrentChange={setCurrentId}
        onAnalyze={handleAnalyze}
        onExport={handleExport}
      />
      <div className="flex flex-1 overflow-hidden relative">
        <div className="flex-1 relative">
          <ServiceGraph
            nodes={nodes}
            edges={edges}
            driftEvents={driftEvents}
            onNodeClick={handleNodeClick}
            onEdgeClick={handleEdgeClick}
          />
          {selectedNodeData && (
            <NodePopup node={selectedNodeData} edges={edges} driftEvents={driftEvents} position={popupPos} onClose={() => setSelectedNode(null)} />
          )}
          {selectedEdgeData && (
            <EdgePopup edge={selectedEdgeData} driftEvents={driftEvents} position={popupPos} onClose={() => setSelectedEdge(null)} />
          )}
        </div>
        <aside className="w-[340px] lg:w-[380px] border-l border-[#0f3460] overflow-y-auto pb-12">
          <div className="flex border-b border-[#0f3460]">
            <button
              className={`flex-1 py-2 text-sm font-semibold ${activeTab === "drift" ? "bg-[#0f3460] text-white" : "text-gray-400 hover:text-gray-200"}`}
              onClick={() => setActiveTab("drift")}
            >
              Drift Feed ({driftEvents.length})
            </button>
            <button
              className={`flex-1 py-2 text-sm font-semibold ${activeTab === "policies" ? "bg-[#0f3460] text-white" : "text-gray-400 hover:text-gray-200"}`}
              onClick={() => setActiveTab("policies")}
            >
              Policies ({policies.length})
            </button>
          </div>
          {activeTab === "drift" && <DriftFeed events={driftEvents} onFeedback={handleFeedback} />}
          {activeTab === "policies" && (
            <div className="p-2 text-sm text-gray-400">
              {policies.length === 0 ? (
                <div className="text-center py-10">No policies</div>
              ) : (
                policies.map((p) => (
                  <div key={p.id} className="bg-[#16213e] border border-[#0f3460] rounded-lg p-3 mb-1.5">
                    <div className="font-semibold">{p.reason}</div>
                    <div className="text-xs mt-1">Status: {p.status} | Risk: {p.risk_score}</div>
                  </div>
                ))
              )}
            </div>
          )}
        </aside>
      </div>
      <SummaryBar summary={summary} policyCount={policies.length} />
    </div>
  );
}
