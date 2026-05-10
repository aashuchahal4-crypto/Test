# SketchFlow AI

SketchFlow AI is a modern local-first whiteboard explainer video builder. It is inspired by automated video tools, but it is explicitly **not** a diffusion/GPU AI video generator. The product uses typed templates, local SVG/vector assets, script parsing, deterministic asset matching, browser storage, timeline sequencing, hand-drawn animation previews, and a Remotion/FFmpeg-oriented export path.

## Product direction

SketchFlow AI should feel like **Canva + Whiteboard Animation + Automated Video Builder**:

- Write or paste a full script.
- Split it into timed scenes automatically.
- Extract keywords and match local vector doodles/icons.
- Preview whiteboard draw, marker, sketch, pop, slide, bounce, and other animation presets.
- Sequence scenes on a timeline with subtitles and narration metadata.
- Export through a future-ready Remotion composition and FFmpeg pipeline.

The app avoids cloud GPU assumptions, diffusion models, expensive external APIs, generated image calls, and secret API keys.

## Stack

- Next.js 15 App Router
- React + TypeScript
- TailwindCSS with dark mode
- Framer Motion for UI and preview transitions
- GSAP adapter in a contained client preview component
- Local SVG asset database plus `lucide-react` icons
- Browser `localStorage` metadata + IndexedDB project payload abstraction with fallback
- Remotion composition registration under `remotion/`

## App structure

- `app/` — Next.js routes for landing, dashboard, templates, editor, and export.
- `components/` — reusable shell, button, card, badge, theme toggle, and utilities.
- `features/` — route-level UI modules for dashboard, editor, export, landing, and templates.
- `lib/` — pure engines and shared types:
  - `types.ts` defines `Project`, `Scene`, `VectorAsset`, `TemplateConfig`, `Timeline`, and `ExportSettings`.
  - `templates.ts` provides typed reusable templates: Classic Whiteboard, Chalkboard Explainer, Modern Canvas, and Shorts Vertical.
  - `assets.ts` contains the local vector library for animals, people, education, science, business, objects, arrows, emojis, and doodles.
  - `scriptParser.ts` detects scene separators, blank lines, numbered sections, and sentence chunks; assigns duration, keywords, and subtitles.
  - `assetMatcher.ts` ranks assets by exact keyword, synonym, category, and name matches, then auto-places selected assets.
  - `timeline.ts` calculates scene start/end times, subtitle timing, and total duration.
  - `audio.ts` reads local audio metadata and generates waveform data with a simulated fallback.
  - `storage.ts` stores project metadata in localStorage and larger payloads in IndexedDB when available.
  - `exportPipeline.ts` describes Remotion/FFmpeg export steps and render plans.
- `remotion/` — root composition and scene renderer for future real MP4 rendering.

## Local vector and matching model

SketchFlow AI does not generate images. It selects from local vector metadata shaped like:

```ts
{
  id: string,
  name: string,
  keywords: string[],
  category: 'animals' | 'people' | 'education' | 'science' | 'business' | 'objects' | 'arrows' | 'charts' | 'emojis' | 'doodles',
  inlineSvg: string,
  animationPresets: string[]
}
```

For example, the input `An elephant dances happily` extracts useful tokens, expands synonyms such as `happy`, `happily`, `lively`, and `dance`, ranks the elephant asset highly, and selects a lively `dance`/`bounce` style preset when available. The output is deterministic and low-cost because it relies on local metadata and SVG paths.

## Timeline and rendering approach

The editor and Remotion composition share the same project, scene, asset, subtitle, template, and timeline types. This keeps the MVP preview aligned with the eventual export renderer:

1. Prepare vector scenes, templates, subtitles, narration metadata, and timeline.
2. Render a Remotion composition from `remotion/root.tsx`.
3. Encode frames and optional audio through FFmpeg.
4. Produce a 720p MP4 for 16:9 YouTube or 9:16 Shorts.

The current export screen simulates browser/local progress while exposing the render plan and composition path for future production rendering.

## Current MVP features

- Polished landing page with local-first and no-diffusion positioning.
- Dashboard with local project cards and stats.
- Template gallery with typed reusable configurations.
- Professional editor layout:
  - Left asset panel and scene list.
  - Center live preview canvas.
  - Right script, properties, animations, template, and audio controls.
  - Bottom visual timeline.
- Script auto-splitting and duration assignment.
- Automatic local asset matching and placement.
- Whiteboard/sketch animation preview using SVG, CSS, Framer Motion, and a contained GSAP adapter.
- Narration upload metadata and waveform placeholder/analysis.
- Dark mode support.
- Remotion root composition and export architecture.

## Future extension points

- Optional local or user-provided LLM scene suggestions.
- Voice generation or imported narration alignment.
- Auto-subtitle refinement.
- Asset packs and custom SVG imports.
- Server or desktop worker that invokes Remotion and FFmpeg.
- APK/mobile wrapper using the same local-first project model.
