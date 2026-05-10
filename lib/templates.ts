import type { TemplateConfig } from './types';

export const templates: TemplateConfig[] = [
  {
    id: 'classic-whiteboard', name: 'Classic Whiteboard', description: 'Clean white surface with bold marker strokes for explainers and lessons.', aspectRatios: ['16:9', '9:16'],
    background: { type: 'grid', value: '#fbfdff', accent: '#2563eb' }, strokeStyle: { color: '#111827', width: 4, linecap: 'round', texture: 'sketch' }, typography: { heading: 'Inter', body: 'Inter', color: '#0f172a' }, sceneDefaults: { duration: 7, transition: 'wipe', padding: 64 }, animationPresets: ['draw', 'marker', 'sketch', 'fade', 'pop']
  },
  {
    id: 'chalkboard-explainer', name: 'Chalkboard Explainer', description: 'Dark chalkboard with chalk-textured strokes and classroom energy.', aspectRatios: ['16:9'],
    background: { type: 'chalk', value: '#052e2b', accent: '#d1fae5' }, strokeStyle: { color: '#e5f9ef', width: 5, linecap: 'round', texture: 'chalk' }, typography: { heading: 'Chalk', body: 'Inter', color: '#ecfdf5' }, sceneDefaults: { duration: 8, transition: 'cut', padding: 72 }, animationPresets: ['draw', 'sketch', 'fade', 'slide']
  },
  {
    id: 'modern-canvas', name: 'Modern Canvas', description: 'Premium canvas with soft gradients, product-story layouts, and animated doodles.', aspectRatios: ['16:9', '9:16'],
    background: { type: 'gradient', value: 'linear-gradient(135deg,#f8fafc,#dbeafe)', accent: '#7c3aed' }, strokeStyle: { color: '#1e293b', width: 3, linecap: 'round', texture: 'clean' }, typography: { heading: 'Inter', body: 'Inter', color: '#172554' }, sceneDefaults: { duration: 6, transition: 'slide', padding: 56 }, animationPresets: ['fade', 'slide', 'pop', 'grow', 'pulse']
  },
  {
    id: 'shorts-vertical', name: 'Shorts Vertical', description: 'Fast vertical storytelling for reels, shorts, and mobile-first education.', aspectRatios: ['9:16'],
    background: { type: 'solid', value: '#fff7ed', accent: '#f97316' }, strokeStyle: { color: '#431407', width: 4, linecap: 'round', texture: 'sketch' }, typography: { heading: 'Inter', body: 'Inter', color: '#431407' }, sceneDefaults: { duration: 5, transition: 'wipe', padding: 42 }, animationPresets: ['draw', 'marker', 'bounce', 'dance', 'pop']
  }
];

export const getTemplate = (id?: string) => templates.find((template) => template.id === id) ?? templates[0];
export const compatibleTemplates = (ratio: '16:9' | '9:16') => templates.filter((template) => template.aspectRatios.includes(ratio));
