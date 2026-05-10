import { enrichScenesWithAssets } from './assetMatcher';
import { demoScript, parseScriptToScenes } from './scriptParser';
import type { AspectRatio, Project, Scene } from './types';

export function createProject(name = 'Untitled SketchFlow', script = demoScript, templateId = 'classic-whiteboard', aspectRatio: AspectRatio = '16:9'): Project {
  const now = new Date().toISOString();
  const scenes = enrichScenesWithAssets(parseScriptToScenes(script));
  return { id: `project-${Date.now().toString(36)}`, name, script, templateId, aspectRatio, scenes, createdAt: now, updatedAt: now };
}

export function projectStats(projects: Project[]) {
  const totalScenes = projects.reduce((sum, project) => sum + project.scenes.length, 0);
  const estimatedMinutes = projects.reduce((sum, project) => sum + project.scenes.reduce((sceneSum, scene) => sceneSum + scene.duration, 0), 0) / 60;
  return { totalScenes, localProjects: projects.length, estimatedMinutes: Number(estimatedMinutes.toFixed(1)) };
}

export const updateScene = (scenes: Scene[], id: string, patch: Partial<Scene>) => scenes.map((scene) => scene.id === id ? { ...scene, ...patch } : scene);
