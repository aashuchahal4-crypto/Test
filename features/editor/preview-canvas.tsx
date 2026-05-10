'use client';

import { motion } from 'framer-motion';
import { useEffect, useRef } from 'react';
import { PlacedAssetIcon } from './asset-icon';
import { getTemplate } from '@/lib/templates';
import type { Project, Scene } from '@/lib/types';

function animationFor(name: string) {
  if (name === 'dance') return { rotate: [-3, 4, -4, 3], y: [0, -9, 0], transition: { duration: 1.1, repeat: Infinity } };
  if (name === 'bounce') return { y: [0, -14, 0], transition: { duration: .9, repeat: Infinity } };
  if (name === 'pop') return { scale: [0.8, 1.08, 1], transition: { duration: .55 } };
  if (name === 'slide' || name === 'rocket') return { x: [-20, 0], opacity: [0, 1], transition: { duration: .7 } };
  if (name === 'grow') return { scaleY: [0.2, 1], transition: { duration: .8 } };
  if (name === 'pulse') return { scale: [1, 1.06, 1], transition: { duration: 1.2, repeat: Infinity } };
  return { opacity: [0, 1], pathLength: [0, 1], transition: { duration: .8 } };
}

export function PreviewCanvas({ project, scene }: { project: Project; scene: Scene }) {
  const template = getTemplate(scene.templateId ?? project.templateId);
  const handRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let ctx: { revert: () => void } | undefined;
    import('gsap').then(({ gsap }) => {
      if (!handRef.current) return;
      ctx = gsap.context(() => { gsap.to(handRef.current, { x: 32, y: -18, rotate: 7, duration: 1.1, repeat: -1, yoyo: true, ease: 'sine.inOut' }); });
    });
    return () => ctx?.revert();
  }, [scene.id]);
  const bgStyle = template.background.type === 'gradient' ? { background: template.background.value } : { backgroundColor: template.background.value };
  return <div className="flex h-full items-center justify-center p-4">
    <div className={`relative overflow-hidden rounded-[2rem] border border-slate-200 shadow-sketch dark:border-slate-700 ${project.aspectRatio === '16:9' ? 'aspect-video w-full max-w-4xl' : 'aspect-[9/16] h-full max-h-[620px]'}`} style={bgStyle}>
      {template.background.type === 'grid' && <div className="sketch-grid absolute inset-0 opacity-80" />}
      {template.background.type === 'chalk' && <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,rgba(255,255,255,.10),transparent_24%),radial-gradient(circle_at_80%_30%,rgba(255,255,255,.06),transparent_28%)]" />}
      <div className="absolute inset-0 p-8 md:p-12">
        <motion.div key={scene.id + scene.title} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="max-w-[70%]">
          <p className="mb-2 text-xs font-black uppercase tracking-[.28em]" style={{ color: template.background.accent }}>Scene preview</p>
          <h2 className="text-2xl font-black leading-tight md:text-4xl" style={{ color: template.typography.color }}>{scene.title}</h2>
          <p className="mt-3 max-w-xl text-sm font-medium leading-6 opacity-80 md:text-base" style={{ color: template.typography.color }}>{scene.text}</p>
        </motion.div>
        {scene.assets.map((placed) => <motion.div key={`${scene.id}-${placed.assetId}`} className="stroke-reveal absolute w-28 origin-center md:w-36" initial={{ opacity: 0, scale: .7 }} animate={animationFor(placed.animation)} style={{ left: `${placed.x}%`, top: `${placed.y}%`, rotate: placed.rotation, scale: placed.scale, color: template.strokeStyle.color, transform: 'translate(-50%, -50%)' }}>
          <PlacedAssetIcon assetId={placed.assetId} />
        </motion.div>)}
        <div ref={handRef} className="absolute right-16 top-20 rounded-full bg-white/80 px-3 py-2 text-xl shadow-lg dark:bg-slate-900/80">✍︎</div>
        <div className="absolute bottom-6 left-1/2 w-[86%] -translate-x-1/2 rounded-2xl bg-slate-950/80 px-4 py-3 text-center text-sm font-semibold text-white backdrop-blur">{scene.subtitles[0]?.text}</div>
      </div>
    </div>
  </div>;
}
