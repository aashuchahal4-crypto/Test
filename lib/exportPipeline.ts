import type { ExportSettings, Project } from './types';

export const exportSteps = [
  { id: 'prepare', label: 'Prepare vector scenes', detail: 'Resolve templates, timeline, SVG assets, subtitles, and local narration metadata.' },
  { id: 'composition', label: 'Render Remotion composition', detail: 'Future local/server worker renders frames from remotion/root.tsx without diffusion models.' },
  { id: 'ffmpeg', label: 'Encode with FFmpeg', detail: 'Encode frames and narration into an MP4 artifact.' },
  { id: 'ready', label: 'MP4 ready', detail: 'Downloadable 720p file. Current MVP simulates browser progress.' },
] as const;

export function createRemotionRenderPlan(project: Project, settings: ExportSettings) {
  return {
    entry: 'remotion/root.tsx',
    compositionId: 'SketchFlowExplainer',
    codec: settings.format,
    fps: settings.fps,
    size: settings.aspectRatio === '16:9' ? { width: 1280, height: 720 } : { width: 720, height: 1280 },
    props: { project, settings },
    command: `remotion render remotion/root.tsx SketchFlowExplainer out/${project.id}.mp4 --props=props.json`,
  };
}
