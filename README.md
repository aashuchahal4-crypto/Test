---
title: AI YouTube Shorts Generator
emoji: 🎬
colorFrom: yellow
colorTo: red
sdk: gradio
sdk_version: 6.19.0
python_version: "3.12"
app_file: app.py
pinned: false
---

# AI YouTube Shorts Generator

A Gradio app for Hugging Face Spaces that analyzes a YouTube video, recommends short-form segments, and renders a vertical MP4.

The app does not block the whole analysis on slow `yt-dlp` metadata extraction. It first loads fast YouTube oEmbed metadata, then only uses `yt-dlp` as an enrichment/download tool with short network timeouts and fallbacks.

## Run locally

```bash
python -m pip install -r requirements.txt
python app.py
```

Open `http://localhost:7860`.

## Hugging Face Spaces

Create a Space with SDK **Gradio** and upload:

- `app.py`
- `requirements.txt`
- `packages.txt`

The app works without an AI key by using YouTube captions plus local transcript scoring. Optionally add `OPENAI_API_KEY` as a Space Secret to use GPT highlight ranking and Whisper fallback when captions are missing.
