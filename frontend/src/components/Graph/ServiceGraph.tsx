import { useRef, useCallback } from "react";
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-expect-error react-cytoscapejs has no type declarations
import CytoscapeComponent from "react-cytoscapejs";
import type cytoscape from "cytoscape";
import type { Node, Edge, DriftEvent } from "@/api/types";

interface ServiceGraphProps {
  nodes: Node[];
  edges: Edge[];
  driftEvents?: DriftEvent[];
  onNodeClick?: (name: string) => void;
  onEdgeClick?: (source: string, destination: string) => void;
}

const stylesheet: cytoscape.StylesheetStyle[] = [
  {
    selector: "node",
    style: {
      label: "data(name)",
      "text-valign": "bottom",
      "text-margin-y": 6,
      "font-size": 11,
      color: "#e0e0e0",
      width: 36,
      height: 36,
      "text-outline-width": 2,
      "text-outline-color": "#1a1a2e",
    },
  },
  { selector: 'node[node_type="service"]', style: { "background-color": "#4fc3f7" } },
  { selector: 'node[node_type="database"]', style: { "background-color": "#ff8a65", shape: "barrel" as const } },
  { selector: 'node[node_type="gateway"]', style: { "background-color": "#81c784", shape: "diamond" as const } },
  { selector: "node.hover", style: { width: 42, height: 42 } },
  {
    selector: "edge",
    style: {
      width: "data(w)" as unknown as number,
      "line-color": "#335577",
      "target-arrow-color": "#335577",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
      "arrow-scale": 0.8,
    },
  },
  { selector: "edge.error", style: { "line-color": "#ff4444", "target-arrow-color": "#ff4444" } },
  { selector: "edge.drift-critical", style: { "line-color": "#ff4444", "target-arrow-color": "#ff4444", width: 3 } },
  { selector: "edge.drift-high", style: { "line-color": "#ff8800", "target-arrow-color": "#ff8800", width: 2.5 } },
  { selector: "edge.drift-medium", style: { "line-color": "#ffcc00", "target-arrow-color": "#ffcc00", width: 2 } },
  {
    selector: "edge.highlight",
    style: { "line-color": "#ff4444", "target-arrow-color": "#ff4444", width: 5, "z-index": 999 },
  },
  { selector: "edge.hover-bright", style: { width: 4, "z-index": 10 } },
  { selector: "node.hover-conn", style: { width: 42, height: 42 } },
];

function buildElements(nodes: Node[], edges: Edge[], driftEvents?: DriftEvent[]) {
  const maxReq = Math.max(1, ...edges.map((e) => e.request_count));
  const driftMap = new Map<string, string>();
  driftEvents?.forEach((d) => {
    const key = `${d.source}->${d.destination}`;
    const prev = driftMap.get(key);
    if (!prev || severityRank(d.severity) > severityRank(prev)) driftMap.set(key, d.severity);
  });

  const elems: cytoscape.ElementDefinition[] = [];
  nodes.forEach((n) =>
    elems.push({ data: { id: n.name, name: n.name, node_type: n.node_type, namespace: n.namespace } }),
  );
  edges.forEach((e) => {
    const w = (1 + 4 * (e.request_count / maxReq)).toFixed(1);
    const classes: string[] = [];
    if (e.error_rate > 0.05) classes.push("error");
    const sev = driftMap.get(`${e.source}->${e.destination}`);
    if (sev) classes.push(`drift-${sev}`);
    elems.push({
      data: { id: `${e.source}->${e.destination}`, source: e.source, target: e.destination, w },
      classes: classes.join(" "),
    });
  });
  return elems;
}

function severityRank(s: string): number {
  return { critical: 4, high: 3, medium: 2, low: 1 }[s] ?? 0;
}

export default function ServiceGraph({ nodes, edges, driftEvents, onNodeClick, onEdgeClick }: ServiceGraphProps) {
  const cyRef = useRef<cytoscape.Core | null>(null);

  const handleCy = useCallback(
    (cy: cytoscape.Core) => {
      if (cyRef.current === cy) return;
      cyRef.current = cy;
      cy.on("tap", "node", (e) => onNodeClick?.(e.target.data("name")));
      cy.on("tap", "edge", (e) => {
        const d = e.target.data();
        onEdgeClick?.(d.source, d.target);
      });
      cy.on("mouseover", "node", (e) => e.target.addClass("hover"));
      cy.on("mouseout", "node", (e) => e.target.removeClass("hover"));
      cy.on("mouseover", "edge", (e) => e.target.addClass("hover-bright"));
      cy.on("mouseout", "edge", (e) => e.target.removeClass("hover-bright"));
    },
    [onNodeClick, onEdgeClick],
  );

  const elements = buildElements(nodes, edges, driftEvents);

  return (
    <div data-testid="service-graph" className="w-full h-full">
      <CytoscapeComponent
      elements={elements}
      stylesheet={stylesheet}
      layout={{ name: "cose", animate: false, nodeDimensionsIncludeLabels: true, padding: 30 } as cytoscape.LayoutOptions}
      cy={handleCy}
      className="w-full h-full bg-[#16213e]"
      />
    </div>
  );
}
