'use client';

import type { Project } from './types';

const META_KEY = 'sketchflow.projects.meta.v1';
const ACTIVE_KEY = 'sketchflow.activeProject.v1';
const DB_NAME = 'sketchflow-ai-db';
const STORE = 'projects';

function hasWindow() { return typeof window !== 'undefined'; }

function openDb(): Promise<IDBDatabase | null> {
  if (!hasWindow() || !('indexedDB' in window)) return Promise.resolve(null);
  return new Promise((resolve) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE, { keyPath: 'id' });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => resolve(null);
  });
}

export async function saveProject(project: Project) {
  if (!hasWindow()) return;
  const updated = { ...project, updatedAt: new Date().toISOString() };
  const existing = getProjectMetadata();
  localStorage.setItem(META_KEY, JSON.stringify([{ id: updated.id, name: updated.name, templateId: updated.templateId, aspectRatio: updated.aspectRatio, updatedAt: updated.updatedAt, scenes: updated.scenes.length }, ...existing.filter((item) => item.id !== updated.id)].slice(0, 24)));
  localStorage.setItem(ACTIVE_KEY, updated.id);
  const db = await openDb();
  if (!db) {
    localStorage.setItem(`sketchflow.project.${updated.id}`, JSON.stringify(updated));
    return;
  }
  const tx = db.transaction(STORE, 'readwrite');
  tx.objectStore(STORE).put(updated);
}

export function getProjectMetadata(): Array<{ id: string; name: string; templateId: string; aspectRatio: string; updatedAt: string; scenes: number }> {
  if (!hasWindow()) return [];
  try { return JSON.parse(localStorage.getItem(META_KEY) ?? '[]'); } catch { return []; }
}

export async function loadProject(id: string): Promise<Project | null> {
  if (!hasWindow()) return null;
  const db = await openDb();
  if (db) {
    const project = await new Promise<Project | null>((resolve) => {
      const request = db.transaction(STORE, 'readonly').objectStore(STORE).get(id);
      request.onsuccess = () => resolve(request.result ?? null);
      request.onerror = () => resolve(null);
    });
    if (project) return project;
  }
  try { return JSON.parse(localStorage.getItem(`sketchflow.project.${id}`) ?? 'null'); } catch { return null; }
}

export async function loadProjects(): Promise<Project[]> {
  const metas = getProjectMetadata();
  const projects = await Promise.all(metas.map((meta) => loadProject(meta.id)));
  return projects.filter(Boolean) as Project[];
}

export const getActiveProjectId = () => hasWindow() ? localStorage.getItem(ACTIVE_KEY) : null;
