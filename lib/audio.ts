import type { AudioMetadata } from './types';

export function simulatedWaveform(seed = 1, bars = 64) {
  return Array.from({ length: bars }, (_, index) => Number((0.2 + Math.abs(Math.sin((index + seed) * .47)) * .75).toFixed(2)));
}

export async function analyzeAudioFile(file: File): Promise<AudioMetadata> {
  const fallback: AudioMetadata = { id: `audio-${Date.now().toString(36)}`, name: file.name, size: file.size, waveform: simulatedWaveform(file.size % 17), objectUrl: URL.createObjectURL(file) };
  if (typeof window === 'undefined' || !window.AudioContext) return fallback;
  try {
    const buffer = await file.arrayBuffer();
    const context = new AudioContext();
    const decoded = await context.decodeAudioData(buffer.slice(0));
    const data = decoded.getChannelData(0);
    const bars = 72;
    const step = Math.floor(data.length / bars);
    const waveform = Array.from({ length: bars }, (_, index) => {
      let sum = 0;
      for (let i = 0; i < step; i++) sum += Math.abs(data[index * step + i] ?? 0);
      return Number(Math.min(1, (sum / Math.max(step, 1)) * 4).toFixed(2));
    });
    await context.close();
    return { ...fallback, duration: Number(decoded.duration.toFixed(2)), waveform };
  } catch {
    return fallback;
  }
}
