---
title: Free AI Reel Generator
emoji: 🎬
colorFrom: purple
colorTo: pink
sdk: gradio
sdk_version: 4.44.1
app_file: app.py
pinned: false
---

# Free AI Reel Generator

A lightweight Gradio MVP for the Brainrot/AI Reel Generator workflow:

1. Enter a script.
2. Parse it into dialogue scenes.
3. Create free voice audio with the existing free-ish English path and Hindi Edge TTS/gTTS fallback.
4. Optionally request free user-run AI scene backgrounds from a compatible Colab/FastAPI/tunnel endpoint.
5. Compose a 9:16 reel with FFmpeg captions, character overlays, transitions, music, and gradient/asset fallbacks.

The app is designed to run without paid API keys. It does not require ElevenLabs, OpenAI, RunPod, AWS, Modal, Replicate, paid Hugging Face Inference API, or local SDXL/diffusers/torch dependencies.

## Local setup

```bash
cd /home/Test
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python download_assets.py
python app.py
```

FFmpeg and FFprobe must be installed on the system.

## Asset folders

The app creates these folders automatically:

- `assets/footage/` optional `.mp4`, `.mov`, `.webm` background loops
- `assets/music/` optional `.mp3`, `.wav`, `.m4a`, `.aac` music
- `assets/fonts/` optional fonts such as Impact/Inter/Noto
- `assets/characters/` optional reusable character images
- `assets/uploads/` temporary UI uploads
- `outputs/videos/` rendered reels
- `outputs/ai_backgrounds/cache/` cached AI images

If no footage or music exists, generation still works with a gradient background and narration-only audio.

## Script formats

Supported by `script_generator.py`:

```text
NARRATOR [mysterious]: What if your phone predicts your next thought?
CHARACTER1 [shocked]: Bro, I only thought about pizza.
CHARACTER2 [serious]: That is your data trail.
```

Also supported:

- `Speaker: Dialogue`
- `Speaker [emotion]: Dialogue`
- JSON lists/objects with `speaker`, `text`, and optional `emotion`

## Voices and audio

The default English voices use a free TikTok-style path with free fallbacks. Hindi/Devanagari text routes to Edge TTS and then gTTS if needed. If network TTS fails, the renderer uses safe silent timing instead of crashing.

Controls:

- narrator/character voice assignment
- background music upload or asset dropdown
- background music volume
- voice volume
- basic FFmpeg loudness normalization for narration clarity

No paid voice provider is required or configured.

## Captions and visual styles

Existing styles remain compatible:

- `Classic`
- `Modern-Dark`
- `Yellow-Pop`
- `TikTok-Blast`
- `Karaoke-Green`
- `Minimal-Shadow`

Added styles:

- `MrBeast Yellow`
- `Reddit Story`
- `Neon Glow`
- `Clean Podcast`
- `Horror`
- `Meme Impact`

Caption controls include position (`Center`, `Lower third`, `Upper third`) and animation (`None`, `Pop`, `Bounce`, `Slide Up`, `Karaoke Highlight`). Hindi/Devanagari readability uses available system fonts when present.

## Background modes

- `Asset Video`: loops an optional video from `assets/footage/`
- `Upload Video`: loops an uploaded `.mp4/.mov/.webm`
- `Solid/Gradient`: always-free fallback generated with Pillow
- `Single AI Image`: requests one external image and uses it for the whole reel
- `AI Scene Images`: parses dialogue into scenes and requests one image per scene/group

If an AI request fails, the app reuses the previous successful scene image. If none exists, it uses a gradient. Rendering should not fail solely because the optional AI endpoint failed.

## Scene engine and prompt enhancer

`scene_engine.py` deterministically converts parsed dialogue into scene objects:

```python
{
    "index": 0,
    "speaker": "NARRATOR",
    "text": "...",
    "emotion": "neutral",
    "prompt": "...",
    "style": "cinematic",
}
```

Prompt enhancement does not call an LLM. It combines title, speaker, dialogue text, emotion, visual theme, and a style preset:

```text
Vertical 9:16 cinematic background for a viral short. Topic: {title}. Speaker: {speaker}. Scene: {dialogue_text}. Mood: {emotion}. Style: {visual_theme}, {preset}. No text, no captions, no watermark.
```

Preset styles:

- `cinematic`: ultra realistic, dramatic lighting, detailed, depth of field
- `cartoon`: Pixar-like 3D render, colorful, expressive, clean shapes
- `anime`: anime style, vibrant colors, dynamic composition
- `dark meme`: high contrast, surreal viral meme aesthetic, dramatic shadows
- `podcast/reddit`: clean illustrated story background, cozy lighting, no text

Default negative prompt:

```text
text, watermark, logo, captions, blurry, low quality, distorted faces
```

`max_ai_scenes` limits external calls so free Colab/tunnel endpoints are not overloaded.

## Optional free Colab/FastAPI/ngrok image endpoint

AI backgrounds are endpoint-based only. This repository does not include local diffusion, SDXL, torch, or diffusers runtime dependencies. Users who want free AI images can run an image model in Google Colab on a free GPU session, expose a small FastAPI endpoint with ngrok/localtunnel/cloudflared, and paste the URL into the Gradio UI.

Expected request JSON:

```json
{
  "prompt": "Vertical 9:16 cinematic background...",
  "negative_prompt": "text, watermark, logo, captions, blurry, low quality, distorted faces",
  "seed": -1,
  "guidance_scale": 7.5,
  "width": 1024,
  "height": 1024
}
```

Accepted response forms:

```json
{ "image_base64": "..." }
```

Also accepted: `image`, `base64`, `data`, `images[0]`, `data:image/png;base64,...`, or direct `image/png`/`image/jpeg` bytes.

Example optional Colab sketch:

```python
import base64, io
from fastapi import FastAPI
from pydantic import BaseModel
from PIL import Image

app = FastAPI()

class Req(BaseModel):
    prompt: str
    negative_prompt: str = ""
    seed: int = -1
    guidance_scale: float = 7.5
    width: int = 1024
    height: int = 1024

@app.post("/generate")
def generate(req: Req):
    # In Colab, load your preferred open-source image model here.
    # Keep this outside the Gradio repo runtime.
    img = Image.new("RGB", (req.width, req.height), "purple")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return {"image_base64": base64.b64encode(buf.getvalue()).decode()}
```

Run it in Colab with Uvicorn and expose it with a free tunnel. The endpoint URL may change every session.

## AI image cache

`ai_backgrounds.py` hashes endpoint URL, prompt, negative prompt, seed, guidance scale, and requested dimensions. Matching images are reused from `outputs/ai_backgrounds/cache/` to reduce repeated Colab calls and speed up rerenders.

Generated images and videos are ignored by git.

## Hugging Face Spaces deployment

This app is suitable for CPU Spaces because the Gradio app itself stays lightweight. It uses FFmpeg and Python packages from `requirements.txt`; no torch/diffusers stack is installed by default.

Free Spaces and free Colab/tunnel workflows have limitations:

- CPU Spaces can be slow and may sleep.
- Free Colab sessions can disconnect or lose state.
- ngrok/localtunnel/cloudflared URLs may change.
- There is no uptime SLA.
- External AI image generation latency depends on the user-run endpoint.

The app remains usable without the AI endpoint via gradient, uploaded, or asset backgrounds.

## Future architecture

The code is intentionally split into service-style modules:

- `app.py`: Gradio entrypoint
- `scene_engine.py`: deterministic scene and prompt generation
- `ai_backgrounds.py`: optional endpoint client, response parsing, image fitting, cache
- `video_generator.py`: FFmpeg render pipeline
- `script_generator.py`: script parsing
- `tiktok_tts.py` / `hindi_tts.py`: free voice paths and fallbacks

A future React/Next frontend plus FastAPI backend can reuse these modules without changing the free-resource MVP constraints.
