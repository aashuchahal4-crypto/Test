---
title: 🎬 Brainrot Video Generator
emoji: 🎬
colorFrom: purple
colorTo: blue
sdk: gradio
sdk_version: 6.13.0
app_file: app.py
pinned: false
---

# AI Audio Storyteller

This repository contains an upgraded Gradio app that keeps the existing brainrot/captions generator core concepts and adds an AI Audio Storyteller layer on top.

## What it does

- Accepts a `.docx` upload and/or pasted text.
- Extracts DOCX text with `python-docx`, with a safe ZIP/XML fallback for environments without `python-docx`.
- Appends raw text after DOCX text when both are provided, and reports that behavior in the UI status.
- Segments prose into short line-by-line scenes for captions.
- Preserves custom `Speaker: text` workflows by routing speaker-prefixed input through `parse_custom_script(...)`.
- Reuses the existing TTS/voice assignment flow through `VOICES`, `assign_voices_to_characters(...)`, `generate_video(...)`, and `generate_brainrot_video(...)`.
- Supports English, Hindi, and mixed text. Hindi-looking text is assigned Hindi voices when possible.
- Renders caption videos through FFmpeg using the same core renderer path.
- Generates local static AI-style background cards per scene with Pillow, so no paid image API key is required.
- Also supports uploaded/random background video mode through `assets/footage` or an uploaded video.
- Exports playable MP4 files to `outputs/` with UUID filenames.

## Preserved core modules

The app keeps the original module layout and public function names expected by the previous generator:

- `app.py` launches the Gradio UI.
- `download_assets.py` creates `assets/fonts/NotoSans-Master-Bold.ttf` through the master-font merge/copy system.
- `video_generator.py` exposes:
  - `split_text_into_segments(...)`
  - `select_best_font_for_text(...)`
  - `create_title_image(...)`
  - `create_caption_image(...)`
  - `generate_line_audio(...)`
  - `generate_brainrot_video(...)`
  - `generate_video(...)`
- `tiktok_tts.py` exposes `VOICES` and `generate_tiktok_tts(...)`.
- `hindi_tts.py`, `emotion_tts.py`, and `script_generator.py` keep the language/voice/custom-script flow.

## New storyteller modules

- `story_inputs.py` handles DOCX/text extraction and story segmentation.
- `timing.py` handles optional Whisper timing and safe heuristic fallback.
- `backgrounds.py` creates per-scene static visual cards and aspect-ratio dimensions.

## Caption styles

Existing styles are retained:

- `Classic`
- `Modern-Dark`
- `Yellow-Pop`
- `TikTok-Blast`
- `Karaoke-Green`
- `Minimal-Shadow`

New styles added:

- `Gradient-Pop`
- `Bold-Keywords`
- `Word-Highlight`

Every caption path prefers `assets/fonts/NotoSans-Master-Bold.ttf` when it exists.

Missing hosted TTF files auto-download from the official Noto Fonts GitHub raw URLs. If hosted downloads fail, the app falls back to compatible system fonts found with `fc-match` and still creates the master font when at least one source font is available.

## Aspect ratios

The UI supports:

- `9:16` → `1080x1920`
- `16:9` → `1920x1080`
- `1:1` → `1080x1080`

Caption placement and background rendering adapt to the selected dimensions.

## Optional Whisper timing

The UI includes a “Try Whisper timing sync” checkbox. If Whisper is installed and usable, the timing layer attempts Whisper alignment. If Whisper or a model is unavailable, the app continues with heuristic per-audio-segment durations and reports the fallback in the status box.

Core functionality does not require Whisper or paid API keys.

## Setup

```bash
cd /home/Test
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

FFmpeg and FFprobe must be available on `PATH`.

## Assets

The app creates these folders automatically:

- `assets/fonts/` — font files and `NotoSans-Master-Bold.ttf`.
- `assets/music/` — default background music auto-downloaded when missing, with a generated ambient loop fallback if downloads fail.
- `assets/footage/` — optional stock/background videos for random-video mode.
- `assets/overlays/` — optional character overlays.
- `outputs/` — rendered MP4 exports.

You can upload background video, music, and character overlays directly in the UI without manually placing files in these folders.

## Running workflow

1. Upload a DOCX or paste story text.
2. Choose automatic narrator segmentation or custom script mode.
3. Pick narrator voice, optional speaker voice overrides, caption style, aspect ratio, and optional Whisper sync.
4. Choose generated scene cards or uploaded/random video background.
5. Generate the story video and preview the MP4 in Gradio.

If generation fails, the status box reports the extraction, segmentation, TTS, timing, background, or FFmpeg step that failed.
