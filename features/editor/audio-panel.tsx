'use client';

import { Music } from 'lucide-react';
import { analyzeAudioFile } from '@/lib/audio';
import type { AudioMetadata } from '@/lib/types';

export function AudioPanel({ audio, onAudio }: { audio?: AudioMetadata; onAudio: (audio: AudioMetadata) => void }) {
  return <div className="rounded-2xl border border-slate-200 p-3 dark:border-slate-800">
    <label className="flex cursor-pointer items-center gap-2 text-sm font-bold"><Music className="h-4 w-4" /> Narration upload
      <input type="file" accept="audio/*" className="hidden" onChange={async (event) => { const file = event.target.files?.[0]; if (file) onAudio(await analyzeAudioFile(file)); }} />
    </label>
    <p className="mt-1 text-xs text-slate-500">Local-only metadata and waveform. No voice API required.</p>
    <div className="mt-3 flex h-12 items-end gap-1 rounded-xl bg-slate-100 p-2 dark:bg-slate-800">
      {(audio?.waveform ?? Array.from({ length: 48 }, (_, i) => .25 + Math.abs(Math.sin(i * .7)) * .65)).slice(0, 48).map((bar, index) => <span key={index} className="flex-1 rounded-full bg-blue-500/80" style={{ height: `${Math.max(10, bar * 100)}%` }} />)}
    </div>
    {audio && <p className="mt-2 truncate text-xs text-slate-500">{audio.name} {audio.duration ? `· ${audio.duration}s` : ''}</p>}
  </div>;
}
