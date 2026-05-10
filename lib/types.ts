export type AspectRatio = '16:9' | '9:16';
export type AssetCategory = 'animals' | 'people' | 'education' | 'science' | 'business' | 'objects' | 'arrows' | 'charts' | 'emojis' | 'doodles';
export type AnimationPreset = 'draw' | 'marker' | 'sketch' | 'fade' | 'slide' | 'pop' | 'bounce' | 'dance' | 'rocket' | 'grow' | 'pulse';

export interface TemplateConfig {
  id: string;
  name: string;
  description: string;
  aspectRatios: AspectRatio[];
  background: { type: 'solid' | 'grid' | 'chalk' | 'gradient'; value: string; accent: string };
  strokeStyle: { color: string; width: number; linecap: 'round' | 'square'; texture: 'clean' | 'sketch' | 'chalk' };
  typography: { heading: string; body: string; color: string };
  sceneDefaults: { duration: number; transition: 'cut' | 'wipe' | 'slide'; padding: number };
  animationPresets: AnimationPreset[];
}

export interface VectorAsset {
  id: string;
  name: string;
  keywords: string[];
  category: AssetCategory;
  inlineSvg: string;
  animationPresets: AnimationPreset[];
}

export interface AssetMatch {
  asset: VectorAsset;
  score: number;
  reasons: string[];
  preset: AnimationPreset;
}

export interface PlacedAsset {
  assetId: string;
  x: number;
  y: number;
  scale: number;
  rotation: number;
  animation: AnimationPreset;
}

export interface Scene {
  id: string;
  title: string;
  text: string;
  duration: number;
  keywords: string[];
  subtitles: SubtitleCue[];
  assets: PlacedAsset[];
  templateId?: string;
  transition?: 'cut' | 'wipe' | 'slide';
}

export interface SubtitleCue {
  id: string;
  text: string;
  start: number;
  end: number;
}

export interface Project {
  id: string;
  name: string;
  script: string;
  templateId: string;
  aspectRatio: AspectRatio;
  scenes: Scene[];
  createdAt: string;
  updatedAt: string;
  audio?: AudioMetadata;
}

export interface AudioMetadata {
  id: string;
  name: string;
  size: number;
  duration?: number;
  waveform: number[];
  objectUrl?: string;
}

export interface TimelineScene extends Scene {
  start: number;
  end: number;
  transitionIn: number;
  transitionOut: number;
}

export interface Timeline {
  scenes: TimelineScene[];
  totalDuration: number;
  subtitles: SubtitleCue[];
}

export interface ExportSettings {
  format: 'mp4';
  resolution: '720p';
  aspectRatio: AspectRatio;
  fps: 24 | 30;
  includeSubtitles: boolean;
  renderMode: 'browser-simulated' | 'remotion-local';
}
