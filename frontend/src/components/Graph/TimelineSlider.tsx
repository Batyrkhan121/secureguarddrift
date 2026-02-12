import { useState, useEffect, useCallback } from 'react';
import { Play, Pause, SkipBack, SkipForward } from 'lucide-react';

interface Snapshot {
  id: string;
  timestamp_start: string;
}

interface TimelineSliderProps {
  snapshots: Snapshot[];
  currentIndex: number;
  onSelect: (index: number) => void;
}

const AUTOPLAY_INTERVAL_MS = 2000;

export default function TimelineSlider({ snapshots, currentIndex, onSelect }: TimelineSliderProps) {
  const [playing, setPlaying] = useState(false);

  const next = useCallback(() => {
    if (currentIndex < snapshots.length - 1) onSelect(currentIndex + 1);
    else setPlaying(false);
  }, [currentIndex, snapshots.length, onSelect]);

  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(next, AUTOPLAY_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [playing, next]);

  if (snapshots.length === 0) return null;

  const current = snapshots[currentIndex];
  const label = current ? new Date(current.timestamp_start).toLocaleString() : '';

  return (
    <div className="flex items-center gap-3 bg-gray-800 rounded-lg px-4 py-2">
      <button onClick={() => onSelect(0)} className="text-gray-400 hover:text-white" title="First">
        <SkipBack size={16} />
      </button>
      <button onClick={() => setPlaying(!playing)} className="text-gray-400 hover:text-white" title={playing ? 'Pause' : 'Play'}>
        {playing ? <Pause size={16} /> : <Play size={16} />}
      </button>
      <button onClick={() => onSelect(snapshots.length - 1)} className="text-gray-400 hover:text-white" title="Last">
        <SkipForward size={16} />
      </button>
      <input
        type="range"
        min={0}
        max={snapshots.length - 1}
        value={currentIndex}
        onChange={(e) => onSelect(Number(e.target.value))}
        className="flex-1 accent-blue-500"
      />
      <span className="text-xs text-gray-400 min-w-[140px] text-right">{label}</span>
    </div>
  );
}
