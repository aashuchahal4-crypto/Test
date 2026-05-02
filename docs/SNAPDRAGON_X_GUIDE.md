# Snapdragon X / Qualcomm Hexagon NPU guide

Your system shows:

- Snapdragon X CPU
- Qualcomm Hexagon NPU
- Qualcomm Adreno GPU
- 16 GB RAM
- NVMe SSD

This build is configured specifically for that machine.

## AI inference

AI generation uses Microsoft Foundry Local with QNN NPU models only. The backend runs:

```bat
foundry model list
```

It selects only models where `Device = NPU` or the model name contains `qnn-npu`.

Priority order:

1. `phi-3.5-mini-instruct-qnn-npu`
2. `qwen2.5-1.5b-instruct-qnn-npu`
3. `deepseek-r1-distill-qwen-7b-qnn-npu`

If none are available, generation stops with `No NPU model available`.

## Rendering

Rendering is intentionally CPU-only:

```text
Foundry Local QNN model → NPU for AI text/scene generation
FFmpeg → CPU for MP4 rendering
```

The NPU is not used for video rendering, filters, subtitles, or FFmpeg.

## Recommended settings

- Style: `minimal`, `documentary`, or `neon`
- Duration: 15-45 seconds for fast iteration
- Scenes: 3-6
- Render threads: 4 by default
- Render preset: `ultrafast` by default

## Launcher

Use:

```bat
RUN_SNAPDRAGON_WINDOWS.bat
```

The launcher checks Foundry Local, prints available models, starts/discovers the Foundry service endpoint, sets CPU render limits, and starts the local app.

## Performance knobs

The launcher sets:

```bat
set VIDEO_RENDER_THREADS=4
set VIDEO_RENDER_PRESET=ultrafast
```

For faster CPU rendering:

```bat
set VIDEO_RENDER_THREADS=6
```

For smaller files but slower CPU rendering:

```bat
set VIDEO_RENDER_PRESET=veryfast
```
