'use client';

import { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, Cpu, Download, FileVideo, Settings } from 'lucide-react';
import { AppShell } from '@/components/app-shell';
import { Button } from '@/components/ui/button';
import { Card, Badge } from '@/components/ui/card';
import { createRemotionRenderPlan, exportSteps } from '@/lib/exportPipeline';
import { createProject } from '@/lib/projectFactory';
import { getActiveProjectId, loadProject } from '@/lib/storage';
import type { ExportSettings, Project } from '@/lib/types';

export function ExportPage() {
  const [project, setProject] = useState<Project>(() => createProject('Export demo'));
  const [settings, setSettings] = useState<ExportSettings>({ format: 'mp4', resolution: '720p', aspectRatio: '16:9', fps: 30, includeSubtitles: true, renderMode: 'browser-simulated' });
  const [progress, setProgress] = useState(0);
  const [running, setRunning] = useState(false);
  const plan = useMemo(() => createRemotionRenderPlan(project, settings), [project, settings]);
  useEffect(() => { loadProject(getActiveProjectId() ?? '').then((stored) => { if (stored) { setProject(stored); setSettings((s) => ({ ...s, aspectRatio: stored.aspectRatio })); } }); }, []);
  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setProgress((value) => value >= 100 ? 100 : value + 4), 180);
    return () => window.clearInterval(timer);
  }, [running]);
  useEffect(() => { if (progress >= 100) setRunning(false); }, [progress]);
  return <AppShell><main className="mx-auto grid max-w-7xl gap-6 px-4 py-10 lg:grid-cols-[420px_1fr]"><section><p className="text-sm font-black uppercase tracking-[.25em] text-blue-600">Export</p><h1 className="mt-2 text-4xl font-black">MP4 render pipeline</h1><p className="mt-3 text-slate-600 dark:text-slate-300">The MVP simulates local browser progress while preserving a real Remotion/FFmpeg-oriented architecture. No cloud GPU, no diffusion model, no generated images.</p><Card className="mt-6"><h2 className="flex items-center gap-2 text-xl font-black"><Settings className="h-5 w-5" />Settings</h2><div className="mt-5 space-y-4"><label className="block text-sm font-bold">Format<select value={settings.format} onChange={(e) => setSettings({ ...settings, format: e.target.value as 'mp4' })} className="mt-1 w-full rounded-xl border border-slate-200 bg-transparent p-3 dark:border-slate-800"><option value="mp4">MP4</option></select></label><label className="block text-sm font-bold">Resolution<select value={settings.resolution} onChange={(e) => setSettings({ ...settings, resolution: e.target.value as '720p' })} className="mt-1 w-full rounded-xl border border-slate-200 bg-transparent p-3 dark:border-slate-800"><option value="720p">720p MVP</option></select></label><div className="grid grid-cols-2 gap-2"><Button variant={settings.aspectRatio === '16:9' ? 'primary' : 'secondary'} onClick={() => setSettings({ ...settings, aspectRatio: '16:9' })}>16:9</Button><Button variant={settings.aspectRatio === '9:16' ? 'primary' : 'secondary'} onClick={() => setSettings({ ...settings, aspectRatio: '9:16' })}>9:16</Button></div><label className="flex items-center gap-2 text-sm font-bold"><input type="checkbox" checked={settings.includeSubtitles} onChange={(e) => setSettings({ ...settings, includeSubtitles: e.target.checked })} />Include subtitles</label></div><Button onClick={() => { setProgress(0); setRunning(true); }} className="mt-6 w-full"><FileVideo className="h-4 w-4" />Start local export simulation</Button></Card></section>
    <section className="space-y-6"><Card><div className="flex items-center justify-between"><div><h2 className="text-xl font-black">Pipeline progress</h2><p className="text-sm text-slate-500">{project.name} · {project.scenes.length} scenes</p></div><Badge>{progress === 100 ? 'Ready' : running ? 'Rendering' : 'Idle'}</Badge></div><div className="mt-5 h-4 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"><div className="h-full rounded-full bg-blue-600 transition-all" style={{ width: `${progress}%` }} /></div><div className="mt-6 grid gap-3">{exportSteps.map((step, index) => { const done = progress >= ((index + 1) / exportSteps.length) * 100; return <div key={step.id} className="flex gap-3 rounded-2xl border border-slate-200 p-4 dark:border-slate-800"><span className={`mt-1 ${done ? 'text-emerald-500' : 'text-slate-400'}`}>{done ? <CheckCircle2 className="h-5 w-5" /> : <Cpu className="h-5 w-5" />}</span><div><p className="font-black">{step.label}</p><p className="text-sm leading-6 text-slate-600 dark:text-slate-300">{step.detail}</p></div></div>; })}</div>{progress === 100 && <Button variant="secondary" className="mt-6"><Download className="h-4 w-4" />Download placeholder MP4</Button>}</Card><Card><h2 className="text-xl font-black">Remotion render plan</h2><pre className="mt-4 overflow-x-auto rounded-2xl bg-slate-950 p-4 text-xs text-slate-100">{JSON.stringify(plan, null, 2)}</pre></Card></section>
  </main></AppShell>;
}
