import { useState } from 'react';
import { Search, X } from 'lucide-react';

interface GraphFiltersProps {
  onFilterChange: (filters: GraphFilterState) => void;
}

export interface GraphFilterState {
  nodeTypes: Set<string>;
  severities: Set<string>;
  search: string;
}

const NODE_TYPES = ['service', 'database', 'gateway'] as const;
const SEVERITIES = ['critical', 'high', 'medium', 'low'] as const;
const SEV_COLORS: Record<string, string> = { critical: 'bg-red-600', high: 'bg-orange-500', medium: 'bg-yellow-500', low: 'bg-blue-500' };

export default function GraphFilters({ onFilterChange }: GraphFiltersProps) {
  const [nodeTypes, setNodeTypes] = useState<Set<string>>(new Set(NODE_TYPES));
  const [severities, setSeverities] = useState<Set<string>>(new Set(SEVERITIES));
  const [search, setSearch] = useState('');

  const update = (nt: Set<string>, sev: Set<string>, s: string) => {
    onFilterChange({ nodeTypes: nt, severities: sev, search: s });
  };

  const toggleType = (t: string) => {
    const next = new Set(nodeTypes);
    next.has(t) ? next.delete(t) : next.add(t);
    setNodeTypes(next);
    update(next, severities, search);
  };

  const toggleSev = (s: string) => {
    const next = new Set(severities);
    next.has(s) ? next.delete(s) : next.add(s);
    setSeverities(next);
    update(nodeTypes, next, search);
  };

  const reset = () => {
    const nt = new Set<string>(NODE_TYPES);
    const sev = new Set<string>(SEVERITIES);
    setNodeTypes(nt);
    setSeverities(sev);
    setSearch('');
    update(nt, sev, '');
  };

  return (
    <div className="flex items-center gap-3 bg-gray-800 rounded-lg px-3 py-2 text-sm">
      <div className="flex gap-1">
        {NODE_TYPES.map((t) => (
          <button key={t} onClick={() => toggleType(t)}
            className={`px-2 py-0.5 rounded text-xs capitalize ${nodeTypes.has(t) ? 'bg-gray-600 text-white' : 'bg-gray-900 text-gray-500'}`}>
            {t}
          </button>
        ))}
      </div>
      <div className="w-px h-5 bg-gray-600" />
      <div className="flex gap-1">
        {SEVERITIES.map((s) => (
          <button key={s} onClick={() => toggleSev(s)}
            className={`px-2 py-0.5 rounded text-xs capitalize ${severities.has(s) ? `${SEV_COLORS[s]} text-white` : 'bg-gray-900 text-gray-500'}`}>
            {s}
          </button>
        ))}
      </div>
      <div className="w-px h-5 bg-gray-600" />
      <div className="relative">
        <Search size={14} className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-500" />
        <input id="graph-node-search" value={search} onChange={(e) => { setSearch(e.target.value); update(nodeTypes, severities, e.target.value); }}
          placeholder="Search node..." className="bg-gray-900 text-white text-xs rounded pl-7 pr-2 py-1 w-32 focus:outline-none focus:ring-1 focus:ring-blue-500" />
      </div>
      <button onClick={reset} className="text-gray-500 hover:text-white" title="Reset filters"><X size={14} /></button>
    </div>
  );
}
