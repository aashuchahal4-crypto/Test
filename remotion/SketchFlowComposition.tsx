import React from 'react';
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { getAssetById } from '@/lib/assets';
import { getTemplate } from '@/lib/templates';
import { buildTimeline } from '@/lib/timeline';
import type { ExportSettings, Project, TimelineScene } from '@/lib/types';

function Asset({ assetId, x, y, scale, rotation, color }: { assetId: string; x: number; y: number; scale: number; rotation: number; color: string }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const asset = getAssetById(assetId);
  const reveal = spring({ frame, fps, config: { damping: 14 } });
  if (!asset) return null;
  return <div style={{ position: 'absolute', left: `${x}%`, top: `${y}%`, width: 160, color, transform: `translate(-50%, -50%) scale(${scale * reveal}) rotate(${rotation}deg)` }} dangerouslySetInnerHTML={{ __html: asset.inlineSvg }} />;
}

function SceneFrame({ scene, project }: { scene: TimelineScene; project: Project }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const localFrame = frame - scene.start * fps;
  const template = getTemplate(scene.templateId ?? project.templateId);
  const opacity = interpolate(localFrame, [0, 10], [0, 1], { extrapolateRight: 'clamp' });
  return <AbsoluteFill style={{ opacity, background: template.background.type === 'gradient' ? template.background.value : template.background.value, padding: 80, color: template.typography.color }}>
    <div style={{ maxWidth: '64%', marginTop: 40 }}><div style={{ color: template.background.accent, fontWeight: 900, letterSpacing: 5, fontSize: 18 }}>SKETCHFLOW SCENE</div><h1 style={{ fontSize: 58, lineHeight: 1, margin: '20px 0 0', fontWeight: 900 }}>{scene.title}</h1><p style={{ fontSize: 26, lineHeight: 1.45, opacity: .78 }}>{scene.text}</p></div>
    {scene.assets.map((asset) => <Asset key={asset.assetId} {...asset} color={template.strokeStyle.color} />)}
    <div style={{ position: 'absolute', left: '50%', bottom: 42, transform: 'translateX(-50%)', width: '82%', padding: 18, borderRadius: 18, background: 'rgba(15,23,42,.82)', color: 'white', textAlign: 'center', fontSize: 26, fontWeight: 700 }}>{scene.subtitles[0]?.text}</div>
  </AbsoluteFill>;
}

export function SketchFlowComposition({ project, settings }: { project: Project; settings: ExportSettings }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const timeline = buildTimeline(project.scenes);
  const time = frame / fps;
  const active = timeline.scenes.find((scene) => time >= scene.start && time < scene.end) ?? timeline.scenes[0];
  return <AbsoluteFill style={{ background: 'white' }}>{active && <SceneFrame scene={active} project={{ ...project, aspectRatio: settings.aspectRatio }} />}</AbsoluteFill>;
}
