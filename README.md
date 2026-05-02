# Local AI Video Studio — Foundry Local NPU Build

Local-first desktop AI content generation system for Snapdragon X PCs. It converts an idea prompt into an editable scene timeline and renders a final MP4.

Text AI uses **Microsoft Foundry Local** on QNN/NPU models. Image generation uses the provider list below plus a safe template fallback.

## NPU model selection

The backend runs `foundry model list`, filters for NPU/QNN models, and selects the best available model in this order:

1. `phi-3.5-mini-instruct-qnn-npu`
2. `qwen2.5-1.5b-instruct-qnn-npu`
3. `deepseek-r1-distill-qwen-7b-qnn-npu`

A model is eligible only when `Device = NPU` or its name contains `qnn-npu`.

## Image engines

The app exposes these image engines in order:

1. Worker Image Service (primary)
2. Pollinations (fast)
3. Cloudflare AI (stable)
4. Replicate (multi-model)
5. Puter.js (frontend fallback)
6. Templates (always safe)

Configuration:

- Worker Image Service posts each scene prompt to `IMAGE_WORKER_URL`, defaulting to `https://patient-tree-3f33.aashuchahal4.workers.dev`.
- Pollinations works without app-side credentials.
- Cloudflare AI requires `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`. Override the model with `CLOUDFLARE_IMAGE_MODEL` if needed.
- Replicate requires `REPLICATE_API_TOKEN`. Override the model with `REPLICATE_MODEL`.
- Puter.js is listed as a frontend fallback option; backend render jobs safely fall back to Templates.
- Templates are generated locally and are always available.

## What it does

- Detects and starts the Foundry Local service when needed.
- Detects the active Foundry REST endpoint dynamically.
- Detects available NPU/QNN models.
- Generates scene JSON with Foundry Local.
- Supports backend endpoints/CLI commands for script generation, scene JSON, hooks/titles, captions, and viral rewrites.
- Lets you edit every scene in the app.
- Generates per-scene preview images through the selected provider, with template fallback.
- Renders visuals, narration, synced subtitles, camera motion, transitions, and final MP4 with FFmpeg on CPU.
- Saves project JSON, assets, subtitles, and videos under `storage/`.

## One-click Windows run

On the Snapdragon X Windows machine, double-click:

```bat
RUN_SNAPDRAGON_WINDOWS.bat
```

`RUN_WINDOWS.bat` calls the same launcher. It installs missing runtime dependencies with `winget`, checks Foundry Local status, then starts the Python local server plus packaged web UI.

## Manual local run

Requirements:

- Windows on Snapdragon X / Qualcomm Hexagon NPU
- Foundry Local installed and running
- At least one QNN NPU model available in `foundry model list`
- Python 3.10+
- Node.js 20+ if rebuilding frontend
- FFmpeg + FFprobe

Start the local web app:

```bash
python3 core/server.py
```

Check selected NPU model and image engine status:

```bash
python3 core/pipeline.py status
```

Generate a scene plan:

```bash
python3 core/pipeline.py plan --prompt "Explain local AI video generation" --duration 24 --style neon
```

Generate image previews:

```bash
python3 core/pipeline.py images --project storage/projects/example.json --engine worker
```

Render from a saved project JSON:

```bash
python3 core/pipeline.py render --project storage/projects/example.json --out storage/outputs/demo.mp4
```

## Architecture

- `src/` — React frontend for prompt input, NPU status, image engine selection, timeline editing, and export.
- `src-tauri/` — optional Tauri desktop shell that calls the Python pipeline.
- `core/foundry_backend.py` — Foundry Local model detection, NPU selection, REST chat calls, retries, and AI feature helpers.
- `core/pipeline.py` — scene project model and CPU FFmpeg rendering pipeline.
- `core/image_generation.py` — provider-based image engine adapter and local template fallback.
- `core/server.py` — local HTTP API for frontend integration.
- `storage/projects/` — editable project JSON.
- `storage/outputs/` — MP4, SRT, and render work directories.
