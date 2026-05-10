import React from 'react';
import { Composition, registerRoot } from 'remotion';
import { createProject } from '@/lib/projectFactory';
import type { ExportSettings, Project } from '@/lib/types';
import { SketchFlowComposition } from './SketchFlowComposition';

const defaultProject = createProject('Remotion sample');
const defaultSettings: ExportSettings = { format: 'mp4', resolution: '720p', aspectRatio: '16:9', fps: 30, includeSubtitles: true, renderMode: 'remotion-local' };

function RemotionRoot() {
  return <Composition
    id="SketchFlowExplainer"
    component={SketchFlowComposition}
    durationInFrames={Math.ceil(defaultProject.scenes.reduce((sum, scene) => sum + scene.duration, 0) * defaultSettings.fps)}
    fps={defaultSettings.fps}
    width={1280}
    height={720}
    defaultProps={{ project: defaultProject, settings: defaultSettings } satisfies { project: Project; settings: ExportSettings }}
    calculateMetadata={({ props }) => {
      const seconds = props.project.scenes.reduce((sum, scene) => sum + scene.duration, 0);
      const vertical = props.settings.aspectRatio === '9:16';
      return { durationInFrames: Math.ceil(seconds * props.settings.fps), fps: props.settings.fps, width: vertical ? 720 : 1280, height: vertical ? 1280 : 720 };
    }}
  />;
}

registerRoot(RemotionRoot);
