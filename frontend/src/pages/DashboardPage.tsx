import { useState, useCallback, useMemo } from "react";
import { useSnapshots, useGraph, useDrift, useDriftSummary, usePolicies } from "@/api/hooks";
import { postFeedback } from "@/api/client";
import { useQueryClient } from "@tanstack/react-query";
import Header from "@/components/Layout/Header";
import SummaryBar from "@/components/Layout/SummaryBar";
import ServiceGraph from "@/components/Graph/ServiceGraph";
import NodePopup from "@/components/Graph/NodePopup";
import EdgePopup from "@/components/Graph/EdgePopup";
import DriftFeed from "@/components/DriftFeed/DriftFeed";
import TimelineSlider from "@/components/Graph/TimelineSlider";
import GraphFilters, { type GraphFilterState } from "@/components/Graph/GraphFilters";
import DiffView from "@/components/Graph/DiffView";
import useKeyboard from "@/hooks/useKeyboard";
import { notify } from "@/components/Toast";

type Tab = "drift" | "policies";
type ViewMode = "normal" | "diff";

export default function DashboardPage() {
  const [baselineId, setBaselineId] = useState("");
  const [currentId, setCurrentId] = useState("");
  const [activeTab, setActiveTab] = useState<Tab>("drift");
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<{ source: string; destination: string } | null>(null);
  const [popupPos, setPopupPos] = useState({ x: 300, y: 200 });
  const [viewMode, setViewMode] = useState<ViewMode>("normal");
  const [timelineIdx, setTimelineIdx] = useState(0);
  const [filters, setFilters] = useState<GraphFilterState>({ nodeTypes: new Set(["service", "database", "gateway"]), severities: new Set(["critical", "high", "medium", "low"]), search: "" });
  const [showHelp, setShowHelp] = useState(false);

  const { data: snapshots = [] } = useSnapshots();
  const { data: graph } = useGraph(currentId || undefined);
  const baselineGraph = useGraph(baselineId || undefined).data;
  const { data: driftEvents = [] } = useDrift(baselineId || undefined, currentId || undefined);
  const { data: summary } = useDriftSummary();
  const { data: policies = [] } = usePolicies();

  const allNodes = graph?.nodes ?? [];
  const allEdges = graph?.edges ?? [];
  const queryClient = useQueryClient();

  const filteredNodes = useMemo(() =>
    allNodes.filter((n) => filters.nodeTypes.has(n.node_type) && (!filters.search || n.name.toLowerCase().includes(filters.search.toLowerCase()))),
    [allNodes, filters],
  );
  const filteredEdges = useMemo(() =>
    allEdges.filter((e) => filteredNodes.some((n) => n.name === e.source) && filteredNodes.some((n) => n.name === e.destination)),
    [allEdges, filteredNodes],
  );

  const handleAnalyze = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["graph"] });
    queryClient.invalidateQueries({ queryKey: ["drift"] });
    queryClient.invalidateQueries({ queryKey: ["driftSummary"] });
  }, [queryClient]);

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
    postFeedback(eventId, verdict)
      .then(() => notify.success("Feedback submitted"))
      .catch(() => notify.error("Failed to submit feedback"));
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

  useKeyboard({
    onEscape: () => { setSelectedNode(null); setSelectedEdge(null); setShowHelp(false); },
    onSearch: () => document.getElementById("graph-node-search")?.focus(),
    onHelp: () => setShowHelp((v) => !v),
  });

  const handleTimelineSelect = useCallback((idx: number) => {
    setTimelineIdx(idx);
    if (snapshots[idx]) setCurrentId(snapshots[idx].id);
  }, [snapshots]);

  const selectedNodeData = filteredNodes.find((n) => n.name === selectedNode);
  const selectedEdgeData = filteredEdges.find(
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
        <div className="flex-1 relative flex flex-col">
          <div className="flex items-center gap-2 px-2 py-1.5 bg-[#16213e] border-b border-[#0f3460]">
            <GraphFilters onFilterChange={setFilters} />
            <button
              onClick={() => setViewMode(viewMode === "normal" ? "diff" : "normal")}
              className={`px-2 py-0.5 rounded text-xs ${viewMode === "diff" ? "bg-orange-600 text-white" : "bg-gray-700 text-gray-300"}`}
            >
              {viewMode === "diff" ? "Diff View" : "Normal View"}
            </button>
          </div>
          <div className="flex-1 relative">
            {viewMode === "normal" ? (
              <ServiceGraph
                nodes={filteredNodes}
                edges={filteredEdges}
                driftEvents={driftEvents}
                onNodeClick={handleNodeClick}
                onEdgeClick={handleEdgeClick}
              />
            ) : (
              <DiffView baseline={baselineGraph ?? null} current={graph ?? null} onNodeClick={handleNodeClick} />
            )}
            {selectedNodeData && (
              <NodePopup node={selectedNodeData} edges={filteredEdges} driftEvents={driftEvents} position={popupPos} onClose={() => setSelectedNode(null)} />
            )}
            {selectedEdgeData && (
              <EdgePopup edge={selectedEdgeData} driftEvents={driftEvents} position={popupPos} onClose={() => setSelectedEdge(null)} />
            )}
          </div>
          {snapshots.length > 1 && (
            <div className="px-2 py-1.5 border-t border-[#0f3460]">
              <TimelineSlider snapshots={snapshots} currentIndex={timelineIdx} onSelect={handleTimelineSelect} />
            </div>
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
      {showHelp && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowHelp(false)}>
          <div className="bg-[#16213e] border border-[#0f3460] rounded-lg p-6 text-sm" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold mb-3">Keyboard Shortcuts</h3>
            <div className="grid grid-cols-2 gap-x-8 gap-y-1">
              <span className="text-gray-400">Esc</span><span>Close popups</span>
              <span className="text-gray-400">J / K</span><span>Navigate drift cards</span>
              <span className="text-gray-400">/</span><span>Focus search</span>
              <span className="text-gray-400">?</span><span>Show this help</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
