# Full local machine guide — Foundry Local NPU build

## Windows fastest path

1. Extract the project zip.
2. Confirm Foundry Local is installed and running.
3. Confirm `foundry model list` shows at least one QNN NPU model.
4. Double-click `RUN_WINDOWS.bat` or `RUN_SNAPDRAGON_WINDOWS.bat`.
5. The local web app opens automatically.

## Required tools

- Windows 11 on Snapdragon X / Qualcomm Hexagon NPU.
- Microsoft Foundry Local installed and available as `foundry` in `PATH`.
- One of these QNN NPU models, preferred in order:
  1. `phi-3.5-mini-instruct-qnn-npu`
  2. `qwen2.5-1.5b-instruct-qnn-npu`
  3. `deepseek-r1-distill-qwen-7b-qnn-npu`
- Python 3.10 or newer.
- FFmpeg and FFprobe in `PATH`.
- Node.js 20 or newer only if rebuilding the frontend.
- Windows only: WebView2 runtime, usually preinstalled.

## Verify NPU model selection and service endpoint

```bash
foundry model list
foundry service start
foundry service status
python3 core/pipeline.py status
```

The app accepts only models where `Device = NPU` or the model name contains `qnn-npu`. Foundry Local may use a dynamic port; the app discovers it automatically from the service commands.

## Run the app

```bash
python3 core/server.py
```

Then open the printed local URL. The status card must show:

```text
AI Backend: Foundry Local
Device: NPU (QNN)
```

## Workflow

1. Enter an idea prompt.
2. Pick video type, duration, style, language, and voice.
3. Click `Generate scene JSON on NPU`.
4. Pick an image engine: Worker Image Service, Pollinations, Cloudflare AI, Replicate, Puter.js, or Templates.
5. Edit scene durations, visual prompts, narration, transitions, and effects.
6. Optionally click `Generate image previews` or enable `Generate scene images during render`.
7. Click `Render MP4 on CPU`.
8. Find outputs in `storage/outputs`.

## CLI commands

```bash
python3 core/pipeline.py status
python3 core/pipeline.py plan --prompt "My video idea" --duration 24 --style cinematic
python3 core/pipeline.py script --prompt "My video idea"
python3 core/pipeline.py hooks --prompt "My video idea"
python3 core/pipeline.py captions --text "Short script text"
python3 core/pipeline.py viral --text "Rewrite this hook"
python3 core/pipeline.py images --project storage/projects/example.json --engine worker
python3 core/pipeline.py render --project storage/projects/example.json --out storage/outputs/my-video.mp4
```

## Storage

- `storage/projects/*.json` — editable project files.
- `storage/outputs/*.mp4` — final videos.
- `storage/outputs/*.srt` — subtitles.
- `storage/outputs/*_work/` — temporary CPU render chunks.

## Assets

Place offline assets in `storage/assets`:

```text
storage/assets/footage     background clips or images
storage/assets/characters  transparent PNG avatars/characters
storage/assets/music       local background tracks
storage/assets/fonts       custom TTF/OTF caption fonts
```

The renderer uses these automatically. If folders are empty, it uses generated CPU-rendered templates.

## Image engine credentials

- Worker Image Service: posts each scene prompt to `IMAGE_WORKER_URL`, defaulting to `https://patient-tree-3f33.aashuchahal4.workers.dev`.
- Pollinations: no app-side credentials.
- Cloudflare AI: set `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`.
- Replicate: set `REPLICATE_API_TOKEN`; optionally set `REPLICATE_MODEL`.
- Puter.js: frontend fallback option; backend render jobs use Templates safely.
- Templates: always available offline.

## Troubleshooting

- `foundry command was not found`: install Foundry Local or add it to `PATH`.
- `No NPU model available`: install one of the QNN NPU models listed above.
- `Foundry Local API failed after retry`: run `foundry service restart`, then `python3 core/pipeline.py status`. The app uses the endpoint printed by Foundry Local, including dynamic ports.
- `ffmpeg not found`: install FFmpeg and reopen Terminal.
- Slow rendering: reduce duration or number of scenes. Rendering is intentionally CPU-only.

Temporary render chunks are deleted after the final MP4 is created. To keep them for debugging:

```bat
set KEEP_RENDER_WORKDIR=1
```
