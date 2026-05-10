'use client';

import { useEffect, useState } from 'react';
import { Clock, Film, FolderOpen, Plus } from 'lucide-react';
import { AppShell } from '@/components/app-shell';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { createProject, projectStats } from '@/lib/projectFactory';
import { loadProjects, saveProject } from '@/lib/storage';
import type { Project } from '@/lib/types';

export function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  useEffect(() => { loadProjects().then(async (stored) => { if (stored.length) setProjects(stored); else { const seed = createProject('Elephant explainer demo'); await saveProject(seed); setProjects([seed]); } }); }, []);
  const stats = projectStats(projects);
  return <AppShell><main className="mx-auto max-w-7xl px-4 py-10"><div className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm font-black uppercase tracking-[.25em] text-blue-600">Dashboard</p><h1 className="mt-2 text-4xl font-black">Local project studio</h1><p className="mt-2 text-slate-600 dark:text-slate-300">Projects are backed by localStorage metadata and IndexedDB payloads when available.</p></div><Button href="/editor"><Plus className="h-4 w-4" />Create whiteboard video</Button></div>
    <div className="mt-8 grid gap-4 md:grid-cols-3">{[{ icon: FolderOpen, label: 'Local projects', value: stats.localProjects }, { icon: Film, label: 'Total scenes', value: stats.totalScenes }, { icon: Clock, label: 'Estimated minutes', value: stats.estimatedMinutes }].map((stat) => <Card key={stat.label}><stat.icon className="h-7 w-7 text-blue-600" /><p className="mt-5 text-3xl font-black">{stat.value}</p><p className="text-sm font-semibold text-slate-500">{stat.label}</p></Card>)}</div>
    <h2 className="mt-10 text-2xl font-black">Recent projects</h2><div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3">{projects.map((project) => <Card key={project.id} className="group"><div className="sketch-grid aspect-video rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"><p className="text-xs font-black uppercase text-blue-600">{project.aspectRatio}</p><h3 className="mt-8 text-xl font-black">{project.name}</h3></div><div className="mt-4 flex items-center justify-between"><div><p className="font-bold">{project.scenes.length} scenes</p><p className="text-xs text-slate-500">Updated {new Date(project.updatedAt).toLocaleDateString()}</p></div><Button href="/editor" variant="secondary">Open</Button></div></Card>)}</div>
  </main></AppShell>;
}
