'use client';

import { motion } from 'framer-motion';
import { Wand2, Plus, SplitSquareHorizontal, Save, MonitorPlay, Smartphone } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Badge, Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { vectorAssets } from '@/lib/assets';
import { enrichScenesWithAssets } from '@/lib/assetMatcher';
import { createProject, updateScene } from '@/lib/projectFactory';
import { demoScript, parseScriptToScenes } from '@/lib/scriptParser';
import { saveProject, getActiveProjectId, loadProject } from '@/lib/storage';
import { compatibleTemplates, getTemplate, templates } from '@/lib/templates';
import { updateSceneDuration } from '@/lib/timeline';
import type { Project } from '@/lib/types';
import { AssetIcon } from './asset-icon';
import { AudioPanel } from './audio-panel';
import { PreviewCanvas } from './preview-canvas';
import { TimelineView } from './timeline-view';

export function EditorApp() {
  const [project, setProject] = useState<Project>(() => createProject('Elephant Product Story', demoScript));
  const [selectedId, setSelectedId] = useState(project.scenes[0]?.id ?? '');
  const [scriptDraft, setScriptDraft] = useState(demoScript);
  const selected = useMemo(() => project.scenes.find((scene) => scene.id === selectedId) ?? project.scenes[0], [project.scenes, selectedId]);
  const template = getTemplate(project.templateId);

  useEffect(() => { loadProject(getActiveProjectId() ?? '').then((stored) => { if (stored) { setProject(stored); setScriptDraft(stored.script); setSelectedId(stored.scenes[0]?.id ?? ''); } }); }, []);
  useEffect(() => { if (!selected && project.scenes[0]) setSelectedId(project.scenes[0].id); }, [project.scenes, selected]);

  function splitScenes() {
    const scenes = enrichScenesWithAssets(parseScriptToScenes(scriptDraft));
    setProject((current) => ({ ...current, script: scriptDraft, scenes, updatedAt: new Date().toISOString() }));
    setSelectedId(scenes[0]?.id ?? '');
  }

  function patchSelected(patch: Parameters<typeof updateScene>[2]) {
    if (!selected) return;
    setProject((current) => ({ ...current, scenes: updateScene(current.scenes, selected.id, patch) }));
  }

  if (!selected) return null;
  return <div className="flex h-[calc(100vh-65px)] flex-col overflow-hidden bg-slate-100 dark:bg-slate-950">
    <div className="grid min-h-0 flex-1 grid-cols-1 gap-0 lg:grid-cols-[300px_minmax(0,1fr)_330px]">
      <aside className="hidden overflow-y-auto border-r border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950 lg:block">
        <div className="mb-4 flex items-center justify-between"><h2 className="font-black">Scenes</h2><Button variant="secondary" className="px-3"><Plus className="h-4 w-4" /></Button></div>
        <div className="space-y-2">
          {project.scenes.map((scene, index) => <button key={scene.id} onClick={() => setSelectedId(scene.id)} className={`w-full rounded-2xl border p-3 text-left text-sm transition ${scene.id === selected.id ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/40' : 'border-slate-200 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-900'}`}>
            <div className="mb-1 flex justify-between text-xs font-black text-slate-500"><span>Scene {index + 1}</span><span>{scene.duration}s</span></div><p className="line-clamp-2 font-semibold">{scene.title}</p>
          </button>)}
        </div>
        <div className="mt-6"><h3 className="mb-3 text-sm font-black">Local vector assets</h3><div className="grid grid-cols-3 gap-2">{vectorAssets.slice(0, 18).map((asset) => <div key={asset.id} className="rounded-2xl border border-slate-200 p-2 text-slate-700 dark:border-slate-800 dark:text-slate-200"><AssetIcon asset={asset} /><p className="truncate text-[10px] font-bold">{asset.name}</p></div>)}</div></div>
      </aside>
      <main className="min-h-0 overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-950">
          <div><p className="text-xs font-bold uppercase tracking-[.2em] text-blue-600">Professional editor</p><h1 className="text-lg font-black">{project.name}</h1></div>
          <div className="flex flex-wrap gap-2"><Button variant={project.aspectRatio === '16:9' ? 'primary' : 'secondary'} onClick={() => setProject((p) => ({ ...p, aspectRatio: '16:9' }))}><MonitorPlay className="h-4 w-4" />16:9</Button><Button variant={project.aspectRatio === '9:16' ? 'primary' : 'secondary'} onClick={() => setProject((p) => ({ ...p, aspectRatio: '9:16', templateId: compatibleTemplates('9:16')[0].id }))}><Smartphone className="h-4 w-4" />9:16</Button><Button onClick={() => saveProject(project)}><Save className="h-4 w-4" />Save local</Button></div>
        </div>
        <PreviewCanvas project={project} scene={selected} />
      </main>
      <aside className="hidden overflow-y-auto border-l border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950 xl:block">
        <div className="space-y-4">
          <Card className="p-4"><h3 className="font-black">Script input</h3><textarea value={scriptDraft} onChange={(e) => setScriptDraft(e.target.value)} className="mt-3 h-36 w-full rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm outline-none focus:border-blue-500 dark:border-slate-800 dark:bg-slate-900" /><Button onClick={splitScenes} className="mt-3 w-full"><SplitSquareHorizontal className="h-4 w-4" />Auto split and match assets</Button></Card>
          <Card className="p-4"><h3 className="font-black">Scene properties</h3><label className="mt-3 block text-xs font-bold uppercase text-slate-500">Title</label><input value={selected.title} onChange={(e) => patchSelected({ title: e.target.value })} className="mt-1 w-full rounded-xl border border-slate-200 bg-transparent p-2 text-sm dark:border-slate-800" />
            <label className="mt-3 block text-xs font-bold uppercase text-slate-500">Duration: {selected.duration}s</label><input type="range" min={3} max={20} value={selected.duration} onChange={(e) => setProject((p) => ({ ...p, scenes: updateSceneDuration(p.scenes, selected.id, Number(e.target.value)) }))} className="w-full" />
            <label className="mt-3 block text-xs font-bold uppercase text-slate-500">Template</label><select value={project.templateId} onChange={(e) => setProject((p) => ({ ...p, templateId: e.target.value }))} className="mt-1 w-full rounded-xl border border-slate-200 bg-transparent p-2 text-sm dark:border-slate-800">{templates.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
          </Card>
          <Card className="p-4"><h3 className="font-black">Animation controls</h3><div className="mt-3 flex flex-wrap gap-2">{template.animationPresets.map((preset) => <Badge key={preset}>{preset}</Badge>)}</div><Button variant="secondary" onClick={() => patchSelected({ assets: enrichScenesWithAssets([{ ...selected, assets: [] }])[0].assets })} className="mt-3 w-full"><Wand2 className="h-4 w-4" />Re-match assets</Button></Card>
          <AudioPanel audio={project.audio} onAudio={(audio) => setProject((p) => ({ ...p, audio }))} />
        </div>
      </aside>
    </div>
    <TimelineView scenes={project.scenes} selectedId={selected.id} onSelect={setSelectedId} />
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="pointer-events-none fixed bottom-24 left-4 rounded-full bg-slate-950 px-4 py-2 text-xs font-bold text-white shadow-lg dark:bg-white dark:text-slate-950">Local SVG + browser storage + Remotion-ready</motion.div>
  </div>;
}
