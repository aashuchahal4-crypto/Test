'use client';

import { buildTimeline, formatTime } from '@/lib/timeline';
import type { Scene } from '@/lib/types';
import { cn } from '@/components/ui/cn';

export function TimelineView({ scenes, selectedId, onSelect }: { scenes: Scene[]; selectedId: string; onSelect: (id: string) => void }) {
  const timeline = buildTimeline(scenes);
  return <div className="border-t border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950">
    <div className="mb-3 flex items-center justify-between text-xs font-semibold uppercase tracking-[.2em] text-slate-500"><span>Timeline sequencing</span><span>{formatTime(timeline.totalDuration)} total</span></div>
    <div className="flex gap-2 overflow-x-auto pb-2">
      {timeline.scenes.map((scene, index) => <button key={scene.id} onClick={() => onSelect(scene.id)} className={cn('min-w-48 rounded-2xl border p-3 text-left transition', selectedId === scene.id ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/40' : 'border-slate-200 bg-slate-50 hover:bg-white dark:border-slate-800 dark:bg-slate-900')} style={{ width: `${Math.max(180, scene.duration * 36)}px` }}>
        <div className="flex items-center justify-between"><span className="text-xs font-black text-slate-500">S{index + 1}</span><span className="text-xs text-slate-500">{formatTime(scene.start)}–{formatTime(scene.end)}</span></div>
        <p className="mt-2 truncate text-sm font-bold">{scene.title}</p>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700"><div className="h-full rounded-full bg-blue-600" style={{ width: `${Math.min(100, scene.duration * 9)}%` }} /></div>
      </button>)}
    </div>
  </div>;
}
