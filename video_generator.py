     1	import math
     2	import os
     3	import shutil
     4	import subprocess
     5	import tempfile
     6	import textwrap
     7	import uuid
     8	from pathlib import Path
     9	from typing import Dict, Iterable, List, Optional, Sequence, Tuple
    10	
    11	from PIL import Image, ImageDraw, ImageFilter, ImageFont
    12	
    13	from ai_backgrounds import create_gradient_background
    14	from script_generator import parse_custom_script
    15	from tiktok_tts import VOICES, text_to_speech
    16	
    17	WIDTH, HEIGHT = 1080, 1920
    18	FPS = 30
    19	
    20	STYLE_REGISTRY = {
    21	    "Classic": {"fill": "white", "stroke": "black", "stroke_width": 5, "card": None, "upper": False},
    22	    "Modern-Dark": {"fill": "white", "stroke": "#111111", "stroke_width": 4, "card": (0, 0, 0, 155), "upper": False},
    23	    "Yellow-Pop": {"fill": "#ffe934", "stroke": "black", "stroke_width": 7, "card": None, "upper": True},
    24	    "TikTok-Blast": {"fill": "white", "stroke": "#ff0050", "stroke_width": 5, "shadow": "#00f2ea", "upper": True},
    25	    "Karaoke-Green": {"fill": "white", "stroke": "black", "stroke_width": 5, "card": (0, 180, 95, 145), "upper": False},
    26	    "Minimal-Shadow": {"fill": "white", "stroke": "#222222", "stroke_width": 2, "shadow": "#000000", "upper": False},
    27	    "MrBeast Yellow": {"fill": "#fff200", "accent": "white", "stroke": "black", "stroke_width": 9, "upper": True},
    28	    "Reddit Story": {"fill": "white", "stroke": "#111111", "stroke_width": 2, "card": (12, 16, 25, 205), "upper": False},
    29	    "Neon Glow": {"fill": "#dffcff", "stroke": "#0ff0fc", "stroke_width": 4, "glow": "#ff00ff", "upper": False},
    30	    "Clean Podcast": {"fill": "white", "stroke": "#1d1d1d", "stroke_width": 2, "shadow": "#000000", "upper": False},
    31	    "Horror": {"fill": "#f4f4f4", "accent": "#ff2020", "stroke": "#120000", "stroke_width": 7, "upper": True},
    32	    "Meme Impact": {"fill": "white", "stroke": "black", "stroke_width": 9, "upper": True},
    33	}
    34	
    35	FONT_CANDIDATES = [
    36	    "assets/fonts/Impact.ttf",
    37	    "assets/fonts/Inter-Bold.ttf",
    38	    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    39	    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
    40	    "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf",
    41	]
    42	
    43	
    44	def _run(cmd: List[str], label: str) -> None:
    45	    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    46	    if result.returncode != 0:
    47	        tail = (result.stderr or result.stdout)[-3000:]
    48	        raise RuntimeError(f"{label} failed: {tail}")
    49	
    50	
    51	def _font_path() -> str:
    52	    for path in FONT_CANDIDATES:
    53	        if Path(path).exists():
    54	            return path
    55	    return ""
    56	
    57	
    58	def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    59	    path = _font_path()
    60	    if path:
    61	        return ImageFont.truetype(path, size=size)
    62	    return ImageFont.load_default()
    63	
    64	
    65	def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
    66	    words = str(text or "").replace("\n", " ").split()
    67	    if not words:
    68	        return [""]
    69	    lines: List[str] = []
    70	    line = ""
    71	    for word in words:
    72	        candidate = f"{line} {word}".strip()
    73	        if draw.textbbox((0, 0), candidate, font=font, stroke_width=0)[2] <= max_width or not line:
    74	            line = candidate
    75	        else:
    76	            lines.append(line)
    77	            line = word
    78	    if line:
    79	        lines.append(line)
    80	    return lines
    81	
    82	
    83	def _rounded_rectangle(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int], radius: int, fill):
    84	    draw.rounded_rectangle(box, radius=radius, fill=fill)
    85	
    86	
    87	def create_caption_image(text: str, output_path: str, style: str = "Classic", position: str = "Center", animation: str = "None") -> str:
    88	    cfg = STYLE_REGISTRY.get(style, STYLE_REGISTRY["Classic"])
    89	    img = Image.new("RGBA", (WIDTH, 520), (0, 0, 0, 0))
    90	    draw = ImageDraw.Draw(img)
    91	    clean = str(text or "").strip()
    92	    if cfg.get("upper"):
    93	        clean = clean.upper()
    94	    max_width = 920
    95	    font_size = 82 if len(clean) < 80 else 70
    96	    while font_size >= 40:
    97	        font = _load_font(font_size)
    98	        lines = _wrap_text(draw, clean, font, max_width)
    99	        line_h = int(font_size * 1.14)
   100	        total_h = len(lines) * line_h
   101	        widest = max(draw.textbbox((0, 0), line, font=font, stroke_width=int(cfg.get("stroke_width", 0)))[2] for line in lines)
   102	        if total_h <= 410 and widest <= max_width:
   103	            break
   104	        font_size -= 4
   105	    font = _load_font(font_size)
   106	    lines = _wrap_text(draw, clean, font, max_width)
   107	    line_h = int(font_size * 1.16)
   108	    total_h = len(lines) * line_h
   109	    y = (img.height - total_h) // 2
   110	    card = cfg.get("card")
   111	    if animation == "Karaoke Highlight" and not card:
   112	        card = (255, 230, 0, 120)
   113	    if card:
   114	        _rounded_rectangle(draw, (52, max(20, y - 34), WIDTH - 52, min(img.height - 20, y + total_h + 34)), 36, card)
   115	    if cfg.get("glow"):
   116	        glow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
   117	        glow_draw = ImageDraw.Draw(glow_layer)
   118	        gy = y
   119	        for line in lines:
   120	            bbox = glow_draw.textbbox((0, 0), line, font=font, stroke_width=8)
   121	            x = (WIDTH - (bbox[2] - bbox[0])) // 2
   122	            glow_draw.text((x, gy), line, font=font, fill=cfg["glow"], stroke_width=10, stroke_fill=cfg["glow"])
   123	            gy += line_h
   124	        img.alpha_composite(glow_layer.filter(ImageFilter.GaussianBlur(11)))
   125	        draw = ImageDraw.Draw(img)
   126	    shadow = cfg.get("shadow")
   127	    for idx, line in enumerate(lines):
   128	        accent = cfg.get("accent") if idx == 0 and cfg.get("accent") else cfg.get("fill", "white")
   129	        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=int(cfg.get("stroke_width", 0)))
   130	        x = (WIDTH - (bbox[2] - bbox[0])) // 2
   131	        line_y = y + idx * line_h
   132	        if shadow:
   133	            draw.text((x + 4, line_y + 5), line, font=font, fill=shadow, stroke_width=int(cfg.get("stroke_width", 0)), stroke_fill=shadow)
   134	        draw.text(
   135	            (x, line_y),
   136	            line,
   137	            font=font,
   138	            fill=accent,
   139	            stroke_width=int(cfg.get("stroke_width", 4)),
   140	            stroke_fill=cfg.get("stroke", "black"),
   141	        )
   142	    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
   143	    img.save(output_path, "PNG")
   144	    return output_path
   145	
   146	
   147	def create_title_image(title: str, output_path: str, style: str = "MrBeast Yellow") -> str:
   148	    img = Image.new("RGBA", (WIDTH, 360), (0, 0, 0, 0))
   149	    draw = ImageDraw.Draw(img)
   150	    font_size = 92
   151	    clean = str(title or "Untitled Reel").strip().upper()
   152	    while font_size >= 44:
   153	        font = _load_font(font_size)
   154	        lines = _wrap_text(draw, clean, font, 940)
   155	        if len(lines) * int(font_size * 1.1) <= 300:
   156	            break
   157	        font_size -= 5
   158	    font = _load_font(font_size)
   159	    lines = _wrap_text(draw, clean, font, 940)
   160	    y = (img.height - len(lines) * int(font_size * 1.1)) // 2
   161	    for line in lines:
   162	        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=9)
   163	        x = (WIDTH - (bbox[2] - bbox[0])) // 2
   164	        draw.text((x, y), line, font=font, fill="#fff200", stroke_width=9, stroke_fill="black")
   165	        y += int(font_size * 1.1)
   166	    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
   167	    img.save(output_path, "PNG")
   168	    return output_path
   169	
   170	
   171	def _ffprobe_duration(path: str) -> float:
   172	    result = subprocess.run(
   173	        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
   174	        stdout=subprocess.PIPE,
   175	        stderr=subprocess.PIPE,
   176	        text=True,
   177	    )
   178	    try:
   179	        return max(0.05, float(result.stdout.strip()))
   180	    except Exception:
   181	        return 1.0
   182	
   183	
   184	def _resolve_voice(voice_name: str) -> str:
   185	    return VOICES.get(voice_name, voice_name or "en_us_001")
   186	
   187	
   188	def _line_voice(line: Dict[str, object], voice_narrator: str, voice1: str, voice2: str) -> str:
   189	    speaker = str(line.get("speaker", "NARRATOR")).upper()
   190	    if "CHARACTER2" in speaker or speaker.endswith("2") or "SPEAKER2" in speaker:
   191	        return _resolve_voice(voice2)
   192	    if "CHARACTER1" in speaker or speaker.endswith("1") or "SPEAKER1" in speaker:
   193	        return _resolve_voice(voice1)
   194	    return _resolve_voice(voice_narrator)
   195	
   196	
   197	def _prepare_audio(dialogues: List[Dict[str, object]], tmp: Path, voice_narrator: str, voice1: str, voice2: str, voice_volume: float) -> Tuple[str, List[Dict[str, object]], float]:
   198	    audio_dir = tmp / "audio"
   199	    audio_dir.mkdir(parents=True, exist_ok=True)
   200	    concat_lines = []
   201	    timestamps: List[Dict[str, object]] = []
   202	    current = 0.0
   203	    gap = 0.18
   204	    for i, line in enumerate(dialogues):
   205	        raw = audio_dir / f"raw_{i}.mp3"
   206	        wav = audio_dir / f"line_{i}.wav"
   207	        text_to_speech(str(line.get("text", "")), _line_voice(line, voice_narrator, voice1, voice2), str(raw), str(line.get("emotion", "neutral")))
   208	        _run([
   209	            "ffmpeg", "-y", "-i", str(raw), "-af", f"volume={voice_volume},loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "44100", "-ac", "2", str(wav)
   210	        ], "voice processing")
   211	        dur = _ffprobe_duration(str(wav))
   212	        start, end = current, current + dur
   213	        enriched = dict(line)
   214	        enriched.update({"start": start, "end": end, "duration": dur, "index": i})
   215	        timestamps.append(enriched)
   216	        concat_lines.append(f"file '{wav.as_posix()}'")
   217	        current = end
   218	        if i != len(dialogues) - 1:
   219	            silent = audio_dir / f"gap_{i}.wav"
   220	            _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", str(gap), str(silent)], "silence gap")
   221	            concat_lines.append(f"file '{silent.as_posix()}'")
   222	            current += gap
   223	    concat_file = audio_dir / "concat.txt"
   224	    concat_file.write_text("\n".join(concat_lines), encoding="utf-8")
   225	    out = audio_dir / "narration.wav"
   226	    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(out)], "audio concat")
   227	    return str(out), timestamps, max(current, 1.0)
   228	
   229	
   230	def _scale_crop_filter() -> str:
   231	    return f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},setsar=1,fps={FPS}"
   232	
   233	
   234	def _image_clip(image_path: str, output_path: str, duration: float, transition_style: str = "Cut") -> str:
   235	    vf = _scale_crop_filter()
   236	    if transition_style == "Fade" and duration > 0.8:
   237	        vf += f",fade=t=in:st=0:d=0.18,fade=t=out:st={max(0, duration - 0.22):.3f}:d=0.18"
   238	    elif transition_style == "Zoom/Pan":
   239	        vf = f"scale={WIDTH*2}:-1,zoompan=z='min(zoom+0.0008,1.08)':d={max(1, int(duration*FPS))}:s={WIDTH}x{HEIGHT}:fps={FPS},setsar=1"
   240	    _run(["ffmpeg", "-y", "-loop", "1", "-i", image_path, "-t", f"{duration:.3f}", "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", output_path], "image background clip")
   241	    return output_path
   242	
   243	
   244	def _video_background(video_path: str, output_path: str, duration: float) -> str:
   245	    _run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", video_path, "-t", f"{duration:.3f}", "-vf", _scale_crop_filter(), "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", output_path], "video background")
   246	    return output_path
   247	
   248	
   249	def _normalise_bg_item(item):
   250	    if isinstance(item, str):
   251	        return {"path": item}
   252	    if isinstance(item, dict):
   253	        path = item.get("path") or item.get("image_path") or item.get("file")
   254	        return {"path": path, "start": item.get("start"), "end": item.get("end")}
   255	    return {"path": None}
   256	
   257	
   258	def _prepare_background(
   259	    tmp: Path,
   260	    duration: float,
   261	    background_mode: str,
   262	    bg_video: Optional[str],
   263	    generated_backgrounds=None,
   264	    gradient_color_a: str = "#161629",
   265	    gradient_color_b: str = "#ff3b7f",
   266	    transition_style: str = "Cut",
   267	) -> str:
   268	    bg_dir = tmp / "background"
   269	    bg_dir.mkdir(parents=True, exist_ok=True)
   270	    fallback = create_gradient_background(bg_dir / "fallback.png", gradient_color_a, gradient_color_b)
   271	    mode = background_mode or "Solid/Gradient"
   272	    if mode in {"Asset Video", "Upload Video"} and bg_video and Path(str(bg_video)).exists():
   273	        return _video_background(str(bg_video), str(bg_dir / "base.mp4"), duration)
   274	
   275	    if mode == "AI Scene Images" and generated_backgrounds:
   276	        items = [_normalise_bg_item(x) for x in generated_backgrounds]
   277	        clips = []
   278	        cursor = 0.0
   279	        previous = fallback
   280	        for i, item in enumerate(items):
   281	            image = item.get("path") if item.get("path") and Path(str(item.get("path"))).exists() else previous
   282	            previous = image or previous
   283	            start = float(item.get("start") if item.get("start") is not None else cursor)
   284	            end = float(item.get("end") if item.get("end") is not None else duration)
   285	            if start > cursor + 0.03:
   286	                gap_clip = bg_dir / f"gap_{i}.mp4"
   287	                _image_clip(previous, str(gap_clip), start - cursor, transition_style)
   288	                clips.append(gap_clip)
   289	            clip_duration = max(0.1, min(duration, end) - max(0, start))
   290	            clip = bg_dir / f"scene_{i}.mp4"
   291	            _image_clip(image or fallback, str(clip), clip_duration, transition_style)
   292	            clips.append(clip)
   293	            cursor = max(cursor, end)
   294	        if cursor < duration - 0.03:
   295	            tail = bg_dir / "tail.mp4"
   296	            _image_clip(previous, str(tail), duration - cursor, transition_style)
   297	            clips.append(tail)
   298	        concat = bg_dir / "concat.txt"
   299	        concat.write_text("\n".join(f"file '{clip.as_posix()}'" for clip in clips), encoding="utf-8")
   300	        out = bg_dir / "base.mp4"
   301	        _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(out)], "scene background concat")
   302	        return str(out)
   303	
   304	    image = fallback
   305	    if generated_backgrounds:
   306	        first = _normalise_bg_item(generated_backgrounds[0] if isinstance(generated_backgrounds, list) else generated_backgrounds)
   307	        if first.get("path") and Path(str(first.get("path"))).exists():
   308	            image = str(first.get("path"))
   309	    return _image_clip(image, str(bg_dir / "base.mp4"), duration, transition_style)
   310	
   311	
   312	def _caption_y(position: str) -> int:
   313	    return {"Upper third": 355, "Lower third": 1180, "Center": 720}.get(position or "Center", 720)
   314	
   315	
   316	def _caption_y_expr(position: str, animation: str, start: float) -> str:
   317	    y = _caption_y(position)
   318	    if animation == "Bounce":
   319	        return f"{y}+12*abs(sin(16*(t-{start:.3f})))"
   320	    if animation == "Slide Up":
   321	        return f"if(lt(t-{start:.3f}\\,0.25)\\,{y}+120-480*(t-{start:.3f})\\,{y})"
   322	    if animation == "Pop":
   323	        return f"if(lt(t-{start:.3f}\\,0.16)\\,{y}+20\\,{y})"
   324	    return str(y)
   325	
   326	
   327	def _compose_video(
   328	    tmp: Path,
   329	    background_video: str,
   330	    narration_audio: str,
   331	    timestamps: List[Dict[str, object]],
   332	    output_path: str,
   333	    title: str,
   334	    caption_style: str,
   335	    caption_position: str,
   336	    caption_animation: str,
   337	    show_title: bool,
   338	    bg_music: Optional[str],
   339	    char_overlay1: Optional[str],
   340	    char_overlay2: Optional[str],
   341	    bg_music_volume: float,
   342	) -> str:
   343	    inputs = ["-i", background_video]
   344	    caption_paths = []
   345	    for line in timestamps:
   346	        cap = tmp / "captions" / f"caption_{int(line['index'])}.png"
   347	        create_caption_image(str(line.get("text", "")), str(cap), caption_style, caption_position, caption_animation)
   348	        caption_paths.append(str(cap))
   349	        inputs += ["-i", str(cap)]
   350	    title_path = None
   351	    if show_title:
   352	        title_path = tmp / "title.png"
   353	        create_title_image(title, str(title_path), caption_style)
   354	        inputs += ["-i", str(title_path)]
   355	    char_inputs = []
   356	    for char in (char_overlay1, char_overlay2):
   357	        if char and Path(str(char)).exists():
   358	            inputs += ["-i", str(char)]
   359	            char_inputs.append(str(char))
   360	        else:
   361	            char_inputs.append(None)
   362	    audio_index = 1 + len(caption_paths) + (1 if title_path else 0) + sum(1 for c in char_inputs if c)
   363	    inputs += ["-i", narration_audio]
   364	    music_index = None
   365	    if bg_music and Path(str(bg_music)).exists():
   366	        music_index = audio_index + 1
   367	        inputs += ["-stream_loop", "-1", "-i", str(bg_music)]
   368	
   369	    filters = []
   370	    current = "[0:v]"
   371	    out_label = "v0"
   372	    for i, line in enumerate(timestamps):
   373	        inp = i + 1
   374	        start = float(line.get("start", 0))
   375	        end = float(line.get("end", start + 1))
   376	        yexpr = _caption_y_expr(caption_position, caption_animation, start)
   377	        label = f"v{i+1}"
   378	        filters.append(f"{current}[{inp}:v]overlay=x=(W-w)/2:y='{yexpr}':enable='between(t\\,{start:.3f}\\,{end:.3f})'[{label}]")
   379	        current = f"[{label}]"
   380	        out_label = label
   381	    next_input = 1 + len(caption_paths)
   382	    if title_path:
   383	        label = f"vtitle"
   384	        filters.append(f"{current}[{next_input}:v]overlay=x=(W-w)/2:y=130:enable='between(t\\,0\\,3.8)'[{label}]")
   385	        current = f"[{label}]"
   386	        out_label = label
   387	        next_input += 1
   388	    char_slot = 0
   389	    for char in char_inputs:
   390	        if not char:
   391	            char_slot += 1
   392	            continue
   393	        scaled = f"char{char_slot}"
   394	        filters.append(f"[{next_input}:v]scale=360:-1[{scaled}]")
   395	        enables = []
   396	        for line in timestamps:
   397	            speaker = str(line.get("speaker", "")).upper()
   398	            if (char_slot == 0 and ("CHARACTER1" in speaker or speaker.endswith("1") or "SPEAKER1" in speaker)) or (char_slot == 1 and ("CHARACTER2" in speaker or speaker.endswith("2") or "SPEAKER2" in speaker)):
   399	                enables.append(f"between(t\\,{float(line['start']):.3f}\\,{float(line['end']):.3f})")
   400	        enable = "+".join(enables) if enables else "0"
   401	        x = "60" if char_slot == 0 else "W-w-60"
   402	        label = f"vchar{char_slot}"
   403	        filters.append(f"{current}[{scaled}]overlay=x={x}:y=H-h-90:enable='{enable}'[{label}]")
   404	        current = f"[{label}]"
   405	        out_label = label
   406	        next_input += 1
   407	        char_slot += 1
   408	
   409	    if music_index is not None:
   410	        filters.append(f"[{audio_index}:a]aresample=44100,volume=1.0[narr];[{music_index}:a]aresample=44100,volume={bg_music_volume}[music];[narr][music]amix=inputs=2:duration=first:dropout_transition=2[aout]")
   411	    else:
   412	        filters.append(f"[{audio_index}:a]aresample=44100[aout]")
   413	    filter_complex = ";".join(filters)
   414	    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
   415	    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filter_complex, "-map", f"[{out_label}]", "-map", "[aout]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", "-movflags", "+faststart", output_path]
   416	    _run(cmd, "final FFmpeg compose")
   417	    return output_path
   418	
   419	
   420	def _default_dialogues(custom_script: str) -> List[Dict[str, object]]:
   421	    lines = parse_custom_script(custom_script)
   422	    if lines:
   423	        return lines
   424	    return [{"speaker": "NARRATOR", "text": "Add a script to generate your free AI reel.", "emotion": "neutral", "index": 0}]
   425	
   426	
   427	def _align_generated_backgrounds(generated_backgrounds, timestamps: List[Dict[str, object]]):
   428	    if not generated_backgrounds:
   429	        return generated_backgrounds
   430	    if not isinstance(generated_backgrounds, list):
   431	        generated_backgrounds = [generated_backgrounds]
   432	    aligned = []
   433	    for i, item in enumerate(generated_backgrounds):
   434	        if isinstance(item, str):
   435	            idxs = [min(i, len(timestamps) - 1)] if timestamps else []
   436	            path = item
   437	            base = {"path": path}
   438	        elif isinstance(item, dict):
   439	            base = dict(item)
   440	            path = base.get("path") or base.get("image_path") or base.get("file")
   441	            base["path"] = path
   442	            idxs = base.get("source_indices") or base.get("line_indices") or base.get("indices")
   443	            if idxs is None and "index" in base:
   444	                idxs = [base.get("index")]
   445	            if idxs is None:
   446	                idxs = [min(i, len(timestamps) - 1)] if timestamps else []
   447	        else:
   448	            continue
   449	        if base.get("start") is None or base.get("end") is None:
   450	            valid = []
   451	            for idx in idxs or []:
   452	                try:
   453	                    valid.append(timestamps[int(idx)])
   454	                except Exception:
   455	                    pass
   456	            if valid:
   457	                base["start"] = min(float(v.get("start", 0)) for v in valid)
   458	                base["end"] = max(float(v.get("end", base["start"] + 1)) for v in valid)
   459	        aligned.append(base)
   460	    return aligned
   461	
   462	
   463	def generate_brainrot_video(
   464	    title: str,
   465	    dialogues: Sequence[Dict[str, object]],
   466	    voice_narrator: str = "Narrator - TikTok English (free)",
   467	    voice1: str = "Jessie - TikTok English (free)",
   468	    voice2: str = "Guy - TikTok English (free)",
   469	    bg_video: Optional[str] = None,
   470	    bg_music: Optional[str] = None,
   471	    char_overlay1: Optional[str] = None,
   472	    char_overlay2: Optional[str] = None,
   473	    caption_style: str = "Classic",
   474	    background_mode: str = "Solid/Gradient",
   475	    generated_backgrounds=None,
   476	    caption_position: str = "Center",
   477	    caption_animation: str = "None",
   478	    show_title: bool = True,
   479	    transition_style: str = "Cut",
   480	    bg_music_volume: float = 0.16,
   481	    voice_volume: float = 1.0,
   482	    gradient_color_a: str = "#161629",
   483	    gradient_color_b: str = "#ff3b7f",
   484	    output_path: Optional[str] = None,
   485	    cleanup: bool = True,
   486	) -> str:
   487	    tmp_path = Path(tempfile.mkdtemp(prefix="brainrot_render_", dir="/tmp"))
   488	    try:
   489	        output_path = output_path or str(Path("outputs/videos") / f"reel_{uuid.uuid4().hex[:10]}.mp4")
   490	        lines = [dict(d) for d in dialogues] or _default_dialogues("")
   491	        narration, timestamps, duration = _prepare_audio(lines, tmp_path, voice_narrator, voice1, voice2, voice_volume)
   492	        aligned_backgrounds = _align_generated_backgrounds(generated_backgrounds, timestamps) if background_mode == "AI Scene Images" else generated_backgrounds
   493	        background = _prepare_background(tmp_path, duration, background_mode, bg_video, aligned_backgrounds, gradient_color_a, gradient_color_b, transition_style)
   494	        return _compose_video(tmp_path, background, narration, timestamps, output_path, title, caption_style, caption_position, caption_animation, show_title, bg_music, char_overlay1, char_overlay2, bg_music_volume)
   495	    finally:
   496	        if cleanup:
   497	            shutil.rmtree(tmp_path, ignore_errors=True)
   498	
   499	
   500	def generate_video_simple(
   501	    title: str,
   502	    script: str,
   503	    voice_narrator: str = "Narrator - TikTok English (free)",
   504	    bg_video: Optional[str] = None,
   505	    bg_music: Optional[str] = None,
   506	    caption_style: str = "Classic",
   507	    **kwargs,
   508	) -> str:
   509	    return generate_brainrot_video(title, _default_dialogues(script), voice_narrator=voice_narrator, bg_video=bg_video, bg_music=bg_music, caption_style=caption_style, **kwargs)
   510	
   511	
   512	def generate_video(
   513	    title: str,
   514	    custom_script: str,
   515	    voice_narrator: str = "Narrator - TikTok English (free)",
   516	    voice1: str = "Jessie - TikTok English (free)",
   517	    voice2: str = "Guy - TikTok English (free)",
   518	    bg_video: Optional[str] = None,
   519	    bg_music: Optional[str] = None,
   520	    char_overlay1: Optional[str] = None,
   521	    char_overlay2: Optional[str] = None,
   522	    caption_style: str = "Classic",
   523	    background_mode: str = "Solid/Gradient",
   524	    generated_backgrounds=None,
   525	    caption_position: str = "Center",
   526	    caption_animation: str = "None",
   527	    show_title: bool = True,
   528	    transition_style: str = "Cut",
   529	    bg_music_volume: float = 0.16,
   530	    voice_volume: float = 1.0,
   531	    gradient_color_a: str = "#161629",
   532	    gradient_color_b: str = "#ff3b7f",
   533	    **kwargs,
   534	) -> str:
   535	    return generate_brainrot_video(
   536	        title,
   537	        _default_dialogues(custom_script),
   538	        voice_narrator=voice_narrator,
   539	        voice1=voice1,
   540	        voice2=voice2,
   541	        bg_video=bg_video,
   542	        bg_music=bg_music,
   543	        char_overlay1=char_overlay1,
   544	        char_overlay2=char_overlay2,
   545	        caption_style=caption_style,
   546	        background_mode=background_mode,
   547	        generated_backgrounds=generated_backgrounds,
   548	        caption_position=caption_position,
   549	        caption_animation=caption_animation,
   550	        show_title=show_title,
   551	        transition_style=transition_style,
   552	        bg_music_volume=bg_music_volume,
   553	        voice_volume=voice_volume,
   554	        gradient_color_a=gradient_color_a,
   555	        gradient_color_b=gradient_color_b,
   556	    )
   557	