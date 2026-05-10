import type { Scene, SubtitleCue } from './types';

const stopWords = new Set(['the','a','an','and','or','but','to','of','in','on','for','with','as','is','are','was','were','be','by','this','that','it','we','you','they','our','your','from','into','about','then','than','can','will','must']);

export const normalizeToken = (token: string) => token.toLowerCase().replace(/[^a-z0-9-]/g, '').replace(/(ing|ed|ly|ies|s)$/i, (suffix) => suffix === 'ies' ? 'y' : '');

export function extractKeywords(text: string): string[] {
  const counts = new Map<string, number>();
  text.split(/\s+/).map(normalizeToken).filter(Boolean).filter((token) => token.length > 2 && !stopWords.has(token)).forEach((token) => counts.set(token, (counts.get(token) ?? 0) + 1));
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12).map(([token]) => token);
}

function durationFor(text: string) {
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  return Math.max(4, Math.min(12, Math.ceil(words / 2.4)));
}

function titleFor(text: string, index: number) {
  const first = text.replace(/^scene\s*\d+\s*[:.-]?/i, '').trim().split(/[.!?]/)[0]?.trim();
  return first ? first.slice(0, 46) : `Scene ${index + 1}`;
}

function subtitleCues(text: string, duration: number): SubtitleCue[] {
  const sentences = text.match(/[^.!?]+[.!?]?/g)?.map((part) => part.trim()).filter(Boolean) ?? [text];
  const slot = duration / Math.max(sentences.length, 1);
  return sentences.map((sentence, index) => ({ id: `sub-${index + 1}`, text: sentence, start: Number((index * slot).toFixed(2)), end: Number(((index + 1) * slot).toFixed(2)) }));
}

function splitBySentences(script: string) {
  const sentences = script.match(/[^.!?]+[.!?]+|[^.!?]+$/g)?.map((sentence) => sentence.trim()).filter(Boolean) ?? [];
  const chunks: string[] = [];
  let buffer: string[] = [];
  let words = 0;
  for (const sentence of sentences) {
    const count = sentence.split(/\s+/).length;
    if (buffer.length && words + count > 34) {
      chunks.push(buffer.join(' '));
      buffer = [];
      words = 0;
    }
    buffer.push(sentence);
    words += count;
  }
  if (buffer.length) chunks.push(buffer.join(' '));
  return chunks;
}

export function parseScriptToScenes(script: string): Scene[] {
  const clean = script.trim();
  if (!clean) return [];
  const scenePattern = /(?:^|\n)\s*(?:scene\s*\d+|\d+[.)-])\s*[:.-]?\s*/gi;
  let chunks = clean.split(/\n\s*\n+/).map((part) => part.trim()).filter(Boolean);
  if (scenePattern.test(clean)) {
    chunks = clean.replace(scenePattern, '\n@@SCENE@@').split('@@SCENE@@').map((part) => part.trim()).filter(Boolean);
  }
  if (chunks.length <= 1) chunks = splitBySentences(clean);
  return chunks.map((text, index) => {
    const duration = durationFor(text);
    return {
      id: `scene-${Date.now().toString(36)}-${index + 1}`,
      title: titleFor(text, index),
      text,
      duration,
      keywords: extractKeywords(text),
      subtitles: subtitleCues(text, duration),
      assets: [],
      transition: 'wipe',
    } satisfies Scene;
  });
}

export const demoScript = 'Scene 1: An elephant dances happily while a presenter introduces a big idea.\n\nScene 2: A student opens a book and discovers how simple visual lessons make learning easier.\n\nScene 3: A growth chart rises as the team launches the project with a rocket-fast plan.';
