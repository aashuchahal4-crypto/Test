# Stickman Brainrot Storyteller

Local Python web app for generating captioned story videos from dialogue. It keeps the two-tab storyteller workflow (`Brainrot Video Generator` and `AI Audio Storyteller`) while replacing required gameplay footage and character PNG overlays with generated stickman scenes.

## Features

- Gradio UI served by FastAPI at `http://127.0.0.1:7860`.
- No required `assets/footage` input. Videos render dynamic stickman scenes with PIL + ffmpeg.
- Optional background music from `assets/music`; generation continues without music if the folder is empty.
- Narrator/storyteller lines drive scene meaning, captions, action, and camera but are not treated as visual overlay characters.
- Non-narrator speakers become stickman characters. The active speaker is emphasized.
- Scene/action inference supports rain, city, park, room, classroom, beach, and space; actions include idle, walk, run, jump, sit, point, shake, slouch, and bounce.
- Local backend endpoints:
  - `GET /api/status` returns ONNX Runtime/NPU provider status.
  - `POST /api/generate-script` creates a deterministic local dialogue draft or reports ONNX adapter status.
  - `POST /api/generate` generates a video from a script.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:7860`.

System dependency: `ffmpeg` must be available on `PATH`. Optional local TTS uses `pyttsx3` when the host has a speech engine. If TTS fails for a line, the app falls back to a short generated audio tone/silence so video generation does not crash.

## Supported script formats

Line format:

```text
NARRATOR: The city went silent.
Alex [shocked]: Wait, why is the sky green?
Plain text fallback lines are treated as narrator/storyteller lines.
```

JSON dialogue arrays:

```json
[
  {"speaker":"NARRATOR","text":"The classroom lights flickered.","emotion":"calm"},
  {"speaker":"Alex","text":"Why is everyone floating?","emotion":"shocked","gender":"male"},
  {"speaker":"Maya","text":"I found the glowing door!","emotion":"happy","voice_gender":"female"}
]
```

The parser also accepts practical JS-like arrays with unquoted keys where possible. Existing `emotion` fields are preserved.

## Voice assignment

- `NARRATOR`, `Storyteller`, `Voiceover`, and `VO` always use the selected narrator/storyteller voice.
- Character gender is read from `gender`, `sex`, or `voice_gender` JSON fields when present.
- Otherwise the app infers gender from role words (`mother`, `girl`, `woman`, `sister`, `father`, `boy`, `man`, `brother`, etc.) and common names.
- Unknown characters alternate male/female defaults instead of failing.
- Devanagari text is tagged as Hindi (`hi`); other text defaults to English (`en`) for voice selection metadata.

## Assets

```text
assets/music/   optional .mp3/.wav/.m4a/.aac/.ogg background tracks
assets/output/  generated .mp4 files
assets/tmp/     temporary render workspace, cleaned after each generation
```

No `assets/footage` folder is required. Thumbnail uploads are intentionally not required by the generation path.

## Snapdragon X / Qualcomm Hexagon NPU setup

The app is NPU-ready through a small ONNX Runtime abstraction in `npu_runtime.py`. It detects available ONNX Runtime execution providers and prefers:

1. `QNNExecutionProvider` for Qualcomm Snapdragon X / Hexagon NPU
2. other installed acceleration providers such as DirectML/OpenVINO/CUDA/CoreML
3. `CPUExecutionProvider` fallback

This is the realistic local NPU path: convert or export the model to ONNX/TFLite/vendor-supported format, install the matching runtime/provider, then execute through that provider. The app does **not** claim PyTorch, Ollama, or browser JavaScript can directly use the Hexagon NPU.

Environment variables:

```bash
export LOCAL_LLM_ONNX_PATH=/path/to/local/script_model.onnx
export LOCAL_TTS_ONNX_PATH=/path/to/local/tts_model.onnx
```

When `LOCAL_LLM_ONNX_PATH` is supplied, the backend adapter attempts to load the model with ONNX Runtime. Because LLM tokenizer/decoder contracts vary by model, the default script generator remains deterministic unless a project-specific ONNX decoding adapter is added. If no provider/model is configured, all UI and generation features continue on CPU/rule-based fallbacks.

On Windows Snapdragon X systems, install a Qualcomm/QNN-enabled ONNX Runtime build and compatible Qualcomm AI Engine Direct / QNN runtime so `QNNExecutionProvider` appears in `/api/status` and the UI backend status panel.
