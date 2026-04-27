     1	import hashlib
     2	import re
     3	from dataclasses import dataclass, asdict
     4	from typing import Dict, Iterable, List, Sequence
     5	
     6	STYLE_PRESETS: Dict[str, str] = {
     7	    "cinematic": "ultra realistic, dramatic lighting, detailed, depth of field",
     8	    "cartoon": "Pixar-like 3D render, colorful, expressive, clean shapes",
     9	    "anime": "anime style, vibrant colors, dynamic composition",
    10	    "dark meme": "high contrast, surreal viral meme aesthetic, dramatic shadows",
    11	    "podcast/reddit": "clean illustrated story background, cozy lighting, no text",
    12	}
    13	
    14	DEFAULT_NEGATIVE_PROMPT = "text, watermark, logo, captions, blurry, low quality, distorted faces"
    15	DEFAULT_VISUAL_THEME = "vertical 9:16 cinematic mobile video background, colorful viral YouTube Shorts style, high contrast, no text, no watermark"
    16	
    17	
    18	@dataclass
    19	class Scene:
    20	    index: int
    21	    speaker: str
    22	    text: str
    23	    emotion: str = "neutral"
    24	    prompt: str = ""
    25	    style: str = "cinematic"
    26	    source_indices: List[int] | None = None
    27	
    28	    def to_dict(self) -> Dict[str, object]:
    29	        data = asdict(self)
    30	        if data["source_indices"] is None:
    31	            data["source_indices"] = [self.index]
    32	        return data
    33	
    34	
    35	def truncate_text(text: str, limit: int = 220) -> str:
    36	    text = re.sub(r"\s+", " ", str(text or "")).strip()
    37	    if len(text) <= limit:
    38	        return text
    39	    return text[: limit - 1].rsplit(" ", 1)[0] + "…"
    40	
    41	
    42	def select_style_preset(style: str) -> str:
    43	    key = (style or "cinematic").strip().lower()
    44	    return STYLE_PRESETS.get(key, style or STYLE_PRESETS["cinematic"])
    45	
    46	
    47	def enhance_prompt(
    48	    title: str,
    49	    dialogue_text: str,
    50	    emotion: str = "neutral",
    51	    visual_theme: str = DEFAULT_VISUAL_THEME,
    52	    style: str = "cinematic",
    53	    speaker: str = "NARRATOR",
    54	) -> str:
    55	    style_text = select_style_preset(style)
    56	    title = truncate_text(title or "Untitled reel", 90)
    57	    dialogue_text = truncate_text(dialogue_text, 220)
    58	    emotion = (emotion or "neutral").strip().lower()
    59	    speaker = (speaker or "NARRATOR").strip().upper()
    60	    visual_theme = (visual_theme or DEFAULT_VISUAL_THEME).strip()
    61	    return (
    62	        f"Vertical 9:16 cinematic background for a viral short. "
    63	        f"Topic: {title}. Speaker: {speaker}. Scene: {dialogue_text}. "
    64	        f"Mood: {emotion}. Style: {visual_theme}, {style_text}. "
    65	        "No text, no captions, no watermark."
    66	    )
    67	
    68	
    69	def group_dialogues(dialogues: Sequence[Dict[str, object]], max_ai_scenes: int = 6) -> List[List[Dict[str, object]]]:
    70	    valid: List[Dict[str, object]] = []
    71	    for original_index, dialogue in enumerate(dialogues):
    72	        if not str(dialogue.get("text", "")).strip():
    73	            continue
    74	        item = dict(dialogue)
    75	        try:
    76	            item["index"] = int(item.get("index", original_index))
    77	        except Exception:
    78	            item["index"] = original_index
    79	        item["original_index"] = item["index"]
    80	        valid.append(item)
    81	    if not valid:
    82	        return []
    83	    max_ai_scenes = max(1, int(max_ai_scenes or 1))
    84	    if len(valid) <= max_ai_scenes:
    85	        return [[d] for d in valid]
    86	    groups: List[List[Dict[str, object]]] = []
    87	    size = (len(valid) + max_ai_scenes - 1) // max_ai_scenes
    88	    for i in range(0, len(valid), size):
    89	        groups.append(valid[i : i + size])
    90	    return groups[:max_ai_scenes]
    91	
    92	
    93	def build_scenes(
    94	    dialogues: Sequence[Dict[str, object]],
    95	    title: str = "",
    96	    visual_theme: str = DEFAULT_VISUAL_THEME,
    97	    style: str = "cinematic",
    98	    max_ai_scenes: int = 6,
    99	) -> List[Dict[str, object]]:
   100	    scenes: List[Dict[str, object]] = []
   101	    for scene_index, group in enumerate(group_dialogues(dialogues, max_ai_scenes=max_ai_scenes)):
   102	        first = group[0]
   103	        text = " ".join(str(item.get("text", "")).strip() for item in group if str(item.get("text", "")).strip())
   104	        emotion = str(first.get("emotion") or "neutral")
   105	        speaker = str(first.get("speaker") or "NARRATOR")
   106	        prompt = enhance_prompt(title, text, emotion, visual_theme, style, speaker)
   107	        source_indices = [int(item.get("original_index", item.get("index", 0))) for item in group]
   108	        scenes.append(Scene(scene_index, speaker, truncate_text(text, 360), emotion, prompt, style, source_indices).to_dict())
   109	    return scenes
   110	
   111	
   112	def scene_prompt_hash(scene: Dict[str, object]) -> str:
   113	    raw = "|".join(str(scene.get(k, "")) for k in ("prompt", "style", "speaker", "emotion"))
   114	    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
   115	