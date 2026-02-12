// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-expect-error react-cytoscapejs has no type declarations
import CytoscapeComponent from 'react-cytoscapejs';
import type { Node, Edge, Snapshot } from '../../api/types';

/* eslint-disable @typescript-eslint/no-explicit-any */

interface DiffViewProps {
  baseline: Snapshot | null;
  current: Snapshot | null;
  onNodeClick?: (name: string) => void;
}

function edgeKey(e: Edge) {
  return `${e.source}→${e.destination}`;
}

export default function DiffView({ baseline, current, onNodeClick }: DiffViewProps) {
  if (!baseline || !current) {
    return <div className="flex items-center justify-center h-full text-gray-500">Select two snapshots to compare</div>;
  }

  const baseEdges = new Map((baseline.edges || []).map((e: Edge) => [edgeKey(e), e]));
  const currEdges = new Map((current.edges || []).map((e: Edge) => [edgeKey(e), e]));

  const allNodes = new Map<string, Node>();
  for (const n of [...(baseline.nodes || []), ...(current.nodes || [])]) {
    allNodes.set(n.name, n);
  }

  const elements: any[] = [];

  for (const [, n] of allNodes) {
    elements.push({ data: { id: n.name, label: n.name, type: n.node_type }, classes: 'node' });
  }

  for (const [key, e] of currEdges) {
    const status = baseEdges.has(key) ? 'changed' : 'added';
    elements.push({
      data: { id: `e-${key}`, source: e.source, target: e.destination, label: `${e.request_count}req` },
      classes: `edge-${status}`,
    });
  }

  for (const [key, e] of baseEdges) {
    if (!currEdges.has(key)) {
      elements.push({
        data: { id: `e-${key}`, source: e.source, target: e.destination, label: 'removed' },
        classes: 'edge-removed',
      });
    }
  }

  const stylesheet: any[] = [
    { selector: 'node', style: { label: 'data(label)', 'background-color': '#4B5563', color: '#fff', 'font-size': '10px', 'text-valign': 'bottom', width: 30, height: 30 } },
    { selector: '.edge-added', style: { 'line-color': '#22c55e', 'line-style': 'dashed', 'target-arrow-color': '#22c55e', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier', label: 'data(label)', 'font-size': '8px', color: '#22c55e' } },
    { selector: '.edge-removed', style: { 'line-color': '#ef4444', 'line-style': 'dashed', 'target-arrow-color': '#ef4444', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier', label: 'data(label)', 'font-size': '8px', color: '#ef4444' } },
    { selector: '.edge-changed', style: { 'line-color': '#f97316', 'target-arrow-color': '#f97316', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier', label: 'data(label)', 'font-size': '8px', color: '#f97316' } },
  ];

  return (
    <div className="relative h-full">
      <div className="absolute top-2 right-2 z-10 flex gap-2 text-xs">
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-green-500 inline-block border-dashed" /> Added</span>
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-red-500 inline-block border-dashed" /> Removed</span>
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-orange-500 inline-block" /> Changed</span>
      </div>
      <CytoscapeComponent
        elements={elements}
        stylesheet={stylesheet}
        layout={{ name: 'cose', animate: false }}
        style={{ width: '100%', height: '100%' }}
        cy={(cy: any) => {
          cy.on('tap', 'node', (e: any) => onNodeClick?.(e.target.id()));
        }}
      />
    </div>
  );
}
