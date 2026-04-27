     1	---
     2	title: Free AI Reel Generator
     3	emoji: 🎬
     4	colorFrom: purple
     5	colorTo: pink
     6	sdk: gradio
     7	sdk_version: 4.44.1
     8	app_file: app.py
     9	pinned: false
    10	---
    11	
    12	# Free AI Reel Generator
    13	
    14	A lightweight Gradio MVP for the Brainrot/AI Reel Generator workflow:
    15	
    16	1. Enter a script.
    17	2. Parse it into dialogue scenes.
    18	3. Create free voice audio with the existing free-ish English path and Hindi Edge TTS/gTTS fallback.
    19	4. Optionally request free user-run AI scene backgrounds from a compatible Colab/FastAPI/tunnel endpoint.
    20	5. Compose a 9:16 reel with FFmpeg captions, character overlays, transitions, music, and gradient/asset fallbacks.
    21	
    22	The app is designed to run without paid API keys. It does not require ElevenLabs, OpenAI, RunPod, AWS, Modal, Replicate, paid Hugging Face Inference API, or local SDXL/diffusers/torch dependencies.
    23	
    24	## Local setup
    25	
    26	```bash
    27	cd /home/Test
    28	python -m venv .venv
    29	source .venv/bin/activate
    30	pip install -r requirements.txt
    31	python download_assets.py
    32	python app.py
    33	```
    34	
    35	FFmpeg and FFprobe must be installed on the system.
    36	
    37	## Asset folders
    38	
    39	The app creates these folders automatically:
    40	
    41	- `assets/footage/` optional `.mp4`, `.mov`, `.webm` background loops
    42	- `assets/music/` optional `.mp3`, `.wav`, `.m4a`, `.aac` music
    43	- `assets/fonts/` optional fonts such as Impact/Inter/Noto
    44	- `assets/characters/` optional reusable character images
    45	- `assets/uploads/` temporary UI uploads
    46	- `outputs/videos/` rendered reels
    47	- `outputs/ai_backgrounds/cache/` cached AI images
    48	
    49	If no footage or music exists, generation still works with a gradient background and narration-only audio.
    50	
    51	## Script formats
    52	
    53	Supported by `script_generator.py`:
    54	
    55	```text
    56	NARRATOR [mysterious]: What if your phone predicts your next thought?
    57	CHARACTER1 [shocked]: Bro, I only thought about pizza.
    58	CHARACTER2 [serious]: That is your data trail.
    59	```
    60	
    61	Also supported:
    62	
    63	- `Speaker: Dialogue`
    64	- `Speaker [emotion]: Dialogue`
    65	- JSON lists/objects with `speaker`, `text`, and optional `emotion`
    66	
    67	## Voices and audio
    68	
    69	The default English voices use a free TikTok-style path with free fallbacks. Hindi/Devanagari text routes to Edge TTS and then gTTS if needed. If network TTS fails, the renderer uses safe silent timing instead of crashing.
    70	
    71	Controls:
    72	
    73	- narrator/character voice assignment
    74	- background music upload or asset dropdown
    75	- background music volume
    76	- voice volume
    77	- basic FFmpeg loudness normalization for narration clarity
    78	
    79	No paid voice provider is required or configured.
    80	
    81	## Captions and visual styles
    82	
    83	Existing styles remain compatible:
    84	
    85	- `Classic`
    86	- `Modern-Dark`
    87	- `Yellow-Pop`
    88	- `TikTok-Blast`
    89	- `Karaoke-Green`
    90	- `Minimal-Shadow`
    91	
    92	Added styles:
    93	
    94	- `MrBeast Yellow`
    95	- `Reddit Story`
    96	- `Neon Glow`
    97	- `Clean Podcast`
    98	- `Horror`
    99	- `Meme Impact`
   100	
   101	Caption controls include position (`Center`, `Lower third`, `Upper third`) and animation (`None`, `Pop`, `Bounce`, `Slide Up`, `Karaoke Highlight`). Hindi/Devanagari readability uses available system fonts when present.
   102	
   103	## Background modes
   104	
   105	- `Asset Video`: loops an optional video from `assets/footage/`
   106	- `Upload Video`: loops an uploaded `.mp4/.mov/.webm`
   107	- `Solid/Gradient`: always-free fallback generated with Pillow
   108	- `Single AI Image`: requests one external image and uses it for the whole reel
   109	- `AI Scene Images`: parses dialogue into scenes and requests one image per scene/group
   110	
   111	If an AI request fails, the app reuses the previous successful scene image. If none exists, it uses a gradient. Rendering should not fail solely because the optional AI endpoint failed.
   112	
   113	## Scene engine and prompt enhancer
   114	
   115	`scene_engine.py` deterministically converts parsed dialogue into scene objects:
   116	
   117	```python
   118	{
   119	    "index": 0,
   120	    "speaker": "NARRATOR",
   121	    "text": "...",
   122	    "emotion": "neutral",
   123	    "prompt": "...",
   124	    "style": "cinematic",
   125	}
   126	```
   127	
   128	Prompt enhancement does not call an LLM. It combines title, speaker, dialogue text, emotion, visual theme, and a style preset:
   129	
   130	```text
   131	Vertical 9:16 cinematic background for a viral short. Topic: {title}. Speaker: {speaker}. Scene: {dialogue_text}. Mood: {emotion}. Style: {visual_theme}, {preset}. No text, no captions, no watermark.
   132	```
   133	
   134	Preset styles:
   135	
   136	- `cinematic`: ultra realistic, dramatic lighting, detailed, depth of field
   137	- `cartoon`: Pixar-like 3D render, colorful, expressive, clean shapes
   138	- `anime`: anime style, vibrant colors, dynamic composition
   139	- `dark meme`: high contrast, surreal viral meme aesthetic, dramatic shadows
   140	- `podcast/reddit`: clean illustrated story background, cozy lighting, no text
   141	
   142	Default negative prompt:
   143	
   144	```text
   145	text, watermark, logo, captions, blurry, low quality, distorted faces
   146	```
   147	
   148	`max_ai_scenes` limits external calls so free Colab/tunnel endpoints are not overloaded.
   149	
   150	## Optional free Colab/FastAPI/ngrok image endpoint
   151	
   152	AI backgrounds are endpoint-based only. This repository does not include local diffusion, SDXL, torch, or diffusers runtime dependencies. Users who want free AI images can run an image model in Google Colab on a free GPU session, expose a small FastAPI endpoint with ngrok/localtunnel/cloudflared, and paste the URL into the Gradio UI.
   153	
   154	Expected request JSON:
   155	
   156	```json
   157	{
   158	  "prompt": "Vertical 9:16 cinematic background...",
   159	  "negative_prompt": "text, watermark, logo, captions, blurry, low quality, distorted faces",
   160	  "seed": -1,
   161	  "guidance_scale": 7.5,
   162	  "width": 1024,
   163	  "height": 1024
   164	}
   165	```
   166	
   167	Accepted response forms:
   168	
   169	```json
   170	{ "image_base64": "..." }
   171	```
   172	
   173	Also accepted: `image`, `base64`, `data`, `images[0]`, `data:image/png;base64,...`, or direct `image/png`/`image/jpeg` bytes.
   174	
   175	Example optional Colab sketch:
   176	
   177	```python
   178	import base64, io
   179	from fastapi import FastAPI
   180	from pydantic import BaseModel
   181	from PIL import Image
   182	
   183	app = FastAPI()
   184	
   185	class Req(BaseModel):
   186	    prompt: str
   187	    negative_prompt: str = ""
   188	    seed: int = -1
   189	    guidance_scale: float = 7.5
   190	    width: int = 1024
   191	    height: int = 1024
   192	
   193	@app.post("/generate")
   194	def generate(req: Req):
   195	    # In Colab, load your preferred open-source image model here.
   196	    # Keep this outside the Gradio repo runtime.
   197	    img = Image.new("RGB", (req.width, req.height), "purple")
   198	    buf = io.BytesIO()
   199	    img.save(buf, format="PNG")
   200	    return {"image_base64": base64.b64encode(buf.getvalue()).decode()}
   201	```
   202	
   203	Run it in Colab with Uvicorn and expose it with a free tunnel. The endpoint URL may change every session.
   204	
   205	## AI image cache
   206	
   207	`ai_backgrounds.py` hashes endpoint URL, prompt, negative prompt, seed, guidance scale, and requested dimensions. Matching images are reused from `outputs/ai_backgrounds/cache/` to reduce repeated Colab calls and speed up rerenders.
   208	
   209	Generated images and videos are ignored by git.
   210	
   211	## Hugging Face Spaces deployment
   212	
   213	This app is suitable for CPU Spaces because the Gradio app itself stays lightweight. It uses FFmpeg and Python packages from `requirements.txt`; no torch/diffusers stack is installed by default.
   214	
   215	Free Spaces and free Colab/tunnel workflows have limitations:
   216	
   217	- CPU Spaces can be slow and may sleep.
   218	- Free Colab sessions can disconnect or lose state.
   219	- ngrok/localtunnel/cloudflared URLs may change.
   220	- There is no uptime SLA.
   221	- External AI image generation latency depends on the user-run endpoint.
   222	
   223	The app remains usable without the AI endpoint via gradient, uploaded, or asset backgrounds.
   224	
   225	## Future architecture
   226	
   227	The code is intentionally split into service-style modules:
   228	
   229	- `app.py`: Gradio entrypoint
   230	- `scene_engine.py`: deterministic scene and prompt generation
   231	- `ai_backgrounds.py`: optional endpoint client, response parsing, image fitting, cache
   232	- `video_generator.py`: FFmpeg render pipeline
   233	- `script_generator.py`: script parsing
   234	- `tiktok_tts.py` / `hindi_tts.py`: free voice paths and fallbacks
   235	
   236	A future React/Next frontend plus FastAPI backend can reuse these modules without changing the free-resource MVP constraints.
   237	