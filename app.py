     1	import os
     2	import random
     3	import shutil
     4	from pathlib import Path
     5	from typing import Any, Dict, List, Tuple
     6	
     7	import gradio as gr
     8	
     9	from ai_backgrounds import create_gradient_background, generate_ai_background
    10	from presets import BACKGROUND_MODES, CAPTION_ANIMATIONS, CAPTION_POSITIONS, CAPTION_STYLES, PRESET_RECOMMENDATIONS, TRANSITIONS, VISUAL_STYLE_PRESETS
    11	from scene_engine import DEFAULT_NEGATIVE_PROMPT, DEFAULT_VISUAL_THEME, build_scenes, enhance_prompt
    12	from script_generator import generate_sample_script, parse_custom_script
    13	from tiktok_tts import VOICES
    14	from video_generator import generate_video
    15	
    16	ASSETS = Path("assets")
    17	FOOTAGE_DIR = ASSETS / "footage"
    18	MUSIC_DIR = ASSETS / "music"
    19	CHARACTER_DIR = ASSETS / "characters"
    20	UPLOAD_DIR = ASSETS / "uploads"
    21	OUTPUT_AI_DIR = Path("outputs/ai_backgrounds")
    22	
    23	for folder in (FOOTAGE_DIR, MUSIC_DIR, ASSETS / "fonts", CHARACTER_DIR, UPLOAD_DIR, OUTPUT_AI_DIR):
    24	    folder.mkdir(parents=True, exist_ok=True)
    25	
    26	
    27	def _choices_from_folder(folder: Path, extensions: Tuple[str, ...], random_label: str, none_label: str = "None") -> List[str]:
    28	    files = sorted(str(p) for p in folder.glob("*") if p.suffix.lower() in extensions)
    29	    return [random_label, none_label] + files
    30	
    31	
    32	def footage_choices() -> List[str]:
    33	    return _choices_from_folder(FOOTAGE_DIR, (".mp4", ".mov", ".webm"), "🎲 Random asset video")
    34	
    35	
    36	def music_choices() -> List[str]:
    37	    return _choices_from_folder(MUSIC_DIR, (".mp3", ".wav", ".m4a", ".aac"), "🎲 Random music")
    38	
    39	
    40	def character_choices() -> List[str]:
    41	    return _choices_from_folder(CHARACTER_DIR, (".png", ".webp", ".jpg", ".jpeg"), "🎲 Random character")
    42	
    43	
    44	def _pick_asset(value: str, folder: Path, extensions: Tuple[str, ...]) -> str | None:
    45	    if not value or value == "None":
    46	        return None
    47	    files = sorted(str(p) for p in folder.glob("*") if p.suffix.lower() in extensions)
    48	    if value.startswith("🎲 Random"):
    49	        return random.choice(files) if files else None
    50	    return value if Path(value).exists() else None
    51	
    52	
    53	def _file_path(file_obj: Any) -> str | None:
    54	    if not file_obj:
    55	        return None
    56	    if isinstance(file_obj, str):
    57	        return file_obj
    58	    return getattr(file_obj, "name", None) or getattr(file_obj, "path", None)
    59	
    60	
    61	def _save_upload(file_obj: Any, prefix: str) -> str | None:
    62	    src = _file_path(file_obj)
    63	    if not src or not Path(src).exists():
    64	        return None
    65	    dest = UPLOAD_DIR / f"{prefix}_{Path(src).name}"
    66	    shutil.copy(src, dest)
    67	    return str(dest)
    68	
    69	
    70	def _build_ai_backgrounds(
    71	    title: str,
    72	    dialogues: List[Dict[str, Any]],
    73	    background_mode: str,
    74	    ai_endpoint_url: str,
    75	    visual_theme_prompt: str,
    76	    negative_prompt: str,
    77	    visual_style_preset: str,
    78	    seed: int,
    79	    guidance_scale: float,
    80	    max_ai_scenes: int,
    81	    gradient_color_a: str,
    82	    gradient_color_b: str,
    83	) -> Tuple[Any, List[str]]:
    84	    status: List[str] = []
    85	    if background_mode not in {"Single AI Image", "AI Scene Images"}:
    86	        return None, status
    87	    endpoint = (ai_endpoint_url or os.getenv("AI_IMAGE_API_URL") or "").strip()
    88	    if not endpoint:
    89	        status.append("AI endpoint not configured; using gradient/asset fallback.")
    90	        return None, status
    91	    if background_mode == "Single AI Image":
    92	        prompt = enhance_prompt(title, "overall mood of the whole reel", "neutral", visual_theme_prompt, visual_style_preset, "NARRATOR")
    93	        path, msg = generate_ai_background(prompt, negative_prompt, endpoint, int(seed), float(guidance_scale), output_dir=OUTPUT_AI_DIR)
    94	        status.append(msg)
    95	        if path:
    96	            return [{"path": path, "source_indices": [i for i in range(len(dialogues))]}], status
    97	        fallback = create_gradient_background(OUTPUT_AI_DIR / "fallback_single.png", gradient_color_a, gradient_color_b)
    98	        return [{"path": fallback, "source_indices": [i for i in range(len(dialogues))]}], status
    99	    scenes = build_scenes(dialogues, title, visual_theme_prompt, visual_style_preset, max_ai_scenes=max_ai_scenes)
   100	    generated = []
   101	    previous = None
   102	    fallback = create_gradient_background(OUTPUT_AI_DIR / "fallback_scene.png", gradient_color_a, gradient_color_b)
   103	    for scene in scenes:
   104	        path, msg = generate_ai_background(str(scene["prompt"]), negative_prompt, endpoint, int(seed), float(guidance_scale), output_dir=OUTPUT_AI_DIR)
   105	        status.append(f"Scene {scene['index'] + 1}: {msg}")
   106	        if not path:
   107	            path = previous or fallback
   108	        previous = path
   109	        generated.append({"path": path, "source_indices": scene.get("source_indices", [scene["index"]]), "prompt": scene["prompt"]})
   110	    return generated, status
   111	
   112	
   113	def generate_from_custom_script(
   114	    title,
   115	    custom_script,
   116	    voice_narrator,
   117	    voice1,
   118	    voice2,
   119	    bg_video,
   120	    bg_music,
   121	    char_overlay1,
   122	    char_overlay2,
   123	    caption_style,
   124	    background_mode="Solid/Gradient",
   125	    uploaded_bg_video=None,
   126	    uploaded_bg_music=None,
   127	    caption_position="Center",
   128	    caption_animation="None",
   129	    show_title=True,
   130	    transition_style="Cut",
   131	    bg_music_volume=0.16,
   132	    voice_volume=1.0,
   133	    ai_endpoint_url="",
   134	    visual_theme_prompt=DEFAULT_VISUAL_THEME,
   135	    negative_prompt=DEFAULT_NEGATIVE_PROMPT,
   136	    visual_style_preset="cinematic",
   137	    seed=-1,
   138	    guidance_scale=7.5,
   139	    max_ai_scenes=6,
   140	    gradient_color_a="#161629",
   141	    gradient_color_b="#ff3b7f",
   142	    char_asset1="None",
   143	    char_asset2="None",
   144	    progress=gr.Progress(),
   145	):
   146	    try:
   147	        title = (title or "Untitled Reel").strip()
   148	        custom_script = (custom_script or "").strip()
   149	        if not custom_script:
   150	            return None, "Add a script first."
   151	        progress(0.05, desc="Parsing script")
   152	        dialogues = parse_custom_script(custom_script)
   153	        if not dialogues:
   154	            return None, "Script parsing failed. Use JSON, Speaker: Dialogue, or Speaker [emotion]: Dialogue."
   155	
   156	        selected_bg_video = None
   157	        if background_mode == "Upload Video":
   158	            selected_bg_video = _save_upload(uploaded_bg_video, "background")
   159	            if not selected_bg_video:
   160	                background_mode = "Solid/Gradient"
   161	        elif background_mode == "Asset Video":
   162	            selected_bg_video = _pick_asset(bg_video, FOOTAGE_DIR, (".mp4", ".mov", ".webm"))
   163	            if not selected_bg_video:
   164	                background_mode = "Solid/Gradient"
   165	
   166	        selected_music = _save_upload(uploaded_bg_music, "music") or _pick_asset(bg_music, MUSIC_DIR, (".mp3", ".wav", ".m4a", ".aac"))
   167	        char1 = _save_upload(char_overlay1, "character1") or _pick_asset(char_asset1, CHARACTER_DIR, (".png", ".webp", ".jpg", ".jpeg"))
   168	        char2 = _save_upload(char_overlay2, "character2") or _pick_asset(char_asset2, CHARACTER_DIR, (".png", ".webp", ".jpg", ".jpeg"))
   169	
   170	        progress(0.16, desc="Preparing optional AI backgrounds")
   171	        generated_backgrounds, ai_status = _build_ai_backgrounds(
   172	            title,
   173	            dialogues,
   174	            background_mode,
   175	            ai_endpoint_url,
   176	            visual_theme_prompt,
   177	            negative_prompt,
   178	            visual_style_preset,
   179	            int(seed),
   180	            float(guidance_scale),
   181	            int(max_ai_scenes),
   182	            gradient_color_a,
   183	            gradient_color_b,
   184	        )
   185	
   186	        progress(0.36, desc="Generating voices and composing video")
   187	        output = generate_video(
   188	            title,
   189	            custom_script,
   190	            voice_narrator=voice_narrator,
   191	            voice1=voice1,
   192	            voice2=voice2,
   193	            bg_video=selected_bg_video,
   194	            bg_music=selected_music,
   195	            char_overlay1=char1,
   196	            char_overlay2=char2,
   197	            caption_style=caption_style,
   198	            background_mode=background_mode,
   199	            generated_backgrounds=generated_backgrounds,
   200	            caption_position=caption_position,
   201	            caption_animation=caption_animation,
   202	            show_title=show_title,
   203	            transition_style=transition_style,
   204	            bg_music_volume=float(bg_music_volume),
   205	            voice_volume=float(voice_volume),
   206	            gradient_color_a=gradient_color_a,
   207	            gradient_color_b=gradient_color_b,
   208	        )
   209	        progress(1.0, desc="Done")
   210	        status = [f"Generated {len(dialogues)} voiced segment(s).", f"Background mode: {background_mode}."] + ai_status
   211	        if not selected_music:
   212	            status.append("No background music selected; narration-only audio used.")
   213	        return output, "\n".join(status)
   214	    except Exception as exc:
   215	        return None, f"Generation failed: {exc}"
   216	
   217	
   218	def apply_preset(name: str):
   219	    sample = generate_sample_script(name)
   220	    rec = PRESET_RECOMMENDATIONS.get(name, {})
   221	    return sample["title"], sample["script"], rec.get("caption_style", "MrBeast Yellow"), rec.get("background_mode", "Solid/Gradient"), rec.get("visual_style", "cinematic")
   222	
   223	
   224	with gr.Blocks(theme=gr.themes.Soft(), title="Free AI Reel Generator") as demo:
   225	    gr.Markdown(
   226	        """
   227	        # Free AI Reel Generator
   228	        Lightweight Gradio MVP for script → scenes → free TTS → captions → FFmpeg vertical reels. It runs without paid API keys. AI image backgrounds are optional and only call your own free Colab/FastAPI/ngrok-compatible endpoint.
   229	        """
   230	    )
   231	    with gr.Row():
   232	        with gr.Column(scale=5):
   233	            with gr.Tab("1. Script"):
   234	                preset = gr.Dropdown(["Conspiracy", "Storytime", "AI facts", "Hindi/English mix"], value="Conspiracy", label="Sample script preset")
   235	                apply_btn = gr.Button("Load preset")
   236	                title = gr.Textbox(label="Video title", value="The Algorithm Knows Too Much")
   237	                custom_script = gr.Textbox(
   238	                    label="Custom script",
   239	                    lines=12,
   240	                    value=generate_sample_script("Conspiracy")["script"],
   241	                    info="Supports JSON, Speaker: Dialogue, and Speaker [emotion]: Dialogue.",
   242	                )
   243	            with gr.Tab("2. Voices & audio"):
   244	                voice_names = list(VOICES.keys())
   245	                voice_narrator = gr.Dropdown(voice_names, value=voice_names[0], label="Narrator voice")
   246	                voice1 = gr.Dropdown(voice_names, value=voice_names[1], label="Character 1 voice")
   247	                voice2 = gr.Dropdown(voice_names, value=voice_names[2], label="Character 2 voice")
   248	                gr.Markdown("English uses the existing free TikTok-style path with free fallbacks. Hindi/Devanagari routes to Edge TTS/gTTS fallback. Emotion tags influence Hindi rate/pitch.")
   249	                bg_music = gr.Dropdown(music_choices(), value="🎲 Random music", label="Asset background music")
   250	                uploaded_bg_music = gr.File(label="Upload background music (.mp3/.wav)", file_types=[".mp3", ".wav", ".m4a", ".aac"])
   251	                bg_music_volume = gr.Slider(0, 1, value=0.16, step=0.01, label="Background music volume")
   252	                voice_volume = gr.Slider(0.5, 2.0, value=1.0, step=0.05, label="Voice volume")
   253	            with gr.Tab("3. Visual style"):
   254	                caption_style = gr.Dropdown(CAPTION_STYLES, value="MrBeast Yellow", label="Caption style")
   255	                caption_position = gr.Dropdown(CAPTION_POSITIONS, value="Center", label="Caption position")
   256	                caption_animation = gr.Dropdown(CAPTION_ANIMATIONS, value="Pop", label="Caption animation")
   257	                show_title = gr.Checkbox(value=True, label="Show title card overlay")
   258	                transition_style = gr.Dropdown(TRANSITIONS, value="Cut", label="Scene transition")
   259	                gradient_color_a = gr.ColorPicker(value="#161629", label="Gradient color A")
   260	                gradient_color_b = gr.ColorPicker(value="#ff3b7f", label="Gradient color B")
   261	            with gr.Tab("4. Backgrounds"):
   262	                background_mode = gr.Dropdown(BACKGROUND_MODES, value="Solid/Gradient", label="Background mode")
   263	                bg_video = gr.Dropdown(footage_choices(), value="🎲 Random asset video", label="Asset background video")
   264	                uploaded_bg_video = gr.File(label="Upload background video (.mp4/.mov)", file_types=[".mp4", ".mov", ".webm"])
   265	                gr.Markdown("AI backgrounds are optional. Paste a user-run free Colab/FastAPI/ngrok/localtunnel/cloudflared endpoint, or leave blank for gradient/asset fallback.")
   266	                ai_endpoint_url = gr.Textbox(label="AI image endpoint URL", placeholder="https://your-free-tunnel.ngrok-free.app/generate")
   267	                visual_style_preset = gr.Dropdown(VISUAL_STYLE_PRESETS, value="cinematic", label="Prompt style preset")
   268	                visual_theme_prompt = gr.Textbox(label="Visual theme/style prompt", lines=3, value=DEFAULT_VISUAL_THEME)
   269	                negative_prompt = gr.Textbox(label="Negative prompt", lines=2, value=DEFAULT_NEGATIVE_PROMPT)
   270	                with gr.Row():
   271	                    seed = gr.Number(value=-1, precision=0, label="Seed (-1 random)")
   272	                    guidance_scale = gr.Slider(1, 15, value=7.5, step=0.5, label="Guidance scale")
   273	                    max_ai_scenes = gr.Slider(1, 12, value=6, step=1, label="Max AI scenes")
   274	            with gr.Tab("5. Characters"):
   275	                char_asset1 = gr.Dropdown(character_choices(), value="None", label="Character 1 asset")
   276	                char_overlay1 = gr.File(label="Upload Character 1 overlay PNG/WebP (takes priority)", file_types=[".png", ".webp", ".jpg", ".jpeg"])
   277	                char_asset2 = gr.Dropdown(character_choices(), value="None", label="Character 2 asset")
   278	                char_overlay2 = gr.File(label="Upload Character 2 overlay PNG/WebP (takes priority)", file_types=[".png", ".webp", ".jpg", ".jpeg"])
   279	            with gr.Tab("6. Export/output"):
   280	                generate_btn = gr.Button("Generate free AI reel", variant="primary", size="lg")
   281	        with gr.Column(scale=4):
   282	            output_video = gr.Video(label="Generated vertical reel")
   283	            status = gr.Textbox(label="Status", lines=12)
   284	
   285	    apply_btn.click(apply_preset, inputs=[preset], outputs=[title, custom_script, caption_style, background_mode, visual_style_preset])
   286	    generate_btn.click(
   287	        generate_from_custom_script,
   288	        inputs=[
   289	            title,
   290	            custom_script,
   291	            voice_narrator,
   292	            voice1,
   293	            voice2,
   294	            bg_video,
   295	            bg_music,
   296	            char_overlay1,
   297	            char_overlay2,
   298	            caption_style,
   299	            background_mode,
   300	            uploaded_bg_video,
   301	            uploaded_bg_music,
   302	            caption_position,
   303	            caption_animation,
   304	            show_title,
   305	            transition_style,
   306	            bg_music_volume,
   307	            voice_volume,
   308	            ai_endpoint_url,
   309	            visual_theme_prompt,
   310	            negative_prompt,
   311	            visual_style_preset,
   312	            seed,
   313	            guidance_scale,
   314	            max_ai_scenes,
   315	            gradient_color_a,
   316	            gradient_color_b,
   317	            char_asset1,
   318	            char_asset2,
   319	        ],
   320	        outputs=[output_video, status],
   321	    )
   322	
   323	if __name__ == "__main__":
   324	    demo.launch()
   325	