import type { Scene, SubtitleCue, Timeline } from './types';

export function buildTimeline(scenes: Scene[]): Timeline {
  let cursor = 0;
  const subtitles: SubtitleCue[] = [];
  const timelineScenes = scenes.map((scene) => {
    const start = cursor;
    const end = cursor + scene.duration;
    scene.subtitles.forEach((subtitle) => subtitles.push({ ...subtitle, id: `${scene.id}-${subtitle.id}`, start: start + subtitle.start, end: start + subtitle.end }));
    cursor = end;
    return { ...scene, start, end, transitionIn: start === 0 ? 0 : .35, transitionOut: .35 };
  });
  return { scenes: timelineScenes, totalDuration: Number(cursor.toFixed(2)), subtitles };
}

export const formatTime = (seconds: number) => `${Math.floor(seconds / 60)}:${Math.floor(seconds % 60).toString().padStart(2, '0')}`;
export const updateSceneDuration = (scenes: Scene[], sceneId: string, duration: number) => scenes.map((scene) => scene.id === sceneId ? { ...scene, duration: Math.max(3, Math.min(20, duration)) } : scene);
