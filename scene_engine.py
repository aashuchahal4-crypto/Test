import hashlib
import re
from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Sequence

STYLE_PRESETS: Dict[str, str] = {
    "cinematic": "ultra realistic, dramatic lighting, detailed, depth of field",
    "cartoon": "Pixar-like 3D render, colorful, expressive, clean shapes",
    "anime": "anime style, vibrant colors, dynamic composition",
    "dark meme": "high contrast, surreal viral meme aesthetic, dramatic shadows",
    "podcast/reddit": "clean illustrated story background, cozy lighting, no text",
}

DEFAULT_NEGATIVE_PROMPT = "text, watermark, logo, captions, blurry, low quality, distorted faces"
DEFAULT_VISUAL_THEME = "vertical 9:16 cinematic mobile video background, colorful viral YouTube Shorts style, high contrast, no text, no watermark"


@dataclass
class Scene:
    index: int
    speaker: str
    text: str
    emotion: str = "neutral"
    prompt: str = ""
    style: str = "cinematic"
    source_indices: List[int] | None = None

    def to_dict(self) -> Dict[str, object]:
        data = asdict(self)
        if data["source_indices"] is None:
            data["source_indices"] = [self.index]
        return data


def truncate_text(text: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "…"


def select_style_preset(style: str) -> str:
    key = (style or "cinematic").strip().lower()
    return STYLE_PRESETS.get(key, style or STYLE_PRESETS["cinematic"])


def enhance_prompt(
    title: str,
    dialogue_text: str,
    emotion: str = "neutral",
    visual_theme: str = DEFAULT_VISUAL_THEME,
    style: str = "cinematic",
    speaker: str = "NARRATOR",
) -> str:
    style_text = select_style_preset(style)
    title = truncate_text(title or "Untitled reel", 90)
    dialogue_text = truncate_text(dialogue_text, 220)
    emotion = (emotion or "neutral").strip().lower()
    speaker = (speaker or "NARRATOR").strip().upper()
    visual_theme = (visual_theme or DEFAULT_VISUAL_THEME).strip()
    return (
        f"Vertical 9:16 cinematic background for a viral short. "
        f"Topic: {title}. Speaker: {speaker}. Scene: {dialogue_text}. "
        f"Mood: {emotion}. Style: {visual_theme}, {style_text}. "
        "No text, no captions, no watermark."
    )


def group_dialogues(dialogues: Sequence[Dict[str, object]], max_ai_scenes: int = 6) -> List[List[Dict[str, object]]]:
    valid: List[Dict[str, object]] = []
    for original_index, dialogue in enumerate(dialogues):
        if not str(dialogue.get("text", "")).strip():
            continue
        item = dict(dialogue)
        try:
            item["index"] = int(item.get("index", original_index))
        except Exception:
            item["index"] = original_index
        item["original_index"] = item["index"]
        valid.append(item)
    if not valid:
        return []
    max_ai_scenes = max(1, int(max_ai_scenes or 1))
    if len(valid) <= max_ai_scenes:
        return [[d] for d in valid]
    groups: List[List[Dict[str, object]]] = []
    size = (len(valid) + max_ai_scenes - 1) // max_ai_scenes
    for i in range(0, len(valid), size):
        groups.append(valid[i : i + size])
    return groups[:max_ai_scenes]


def build_scenes(
    dialogues: Sequence[Dict[str, object]],
    title: str = "",
    visual_theme: str = DEFAULT_VISUAL_THEME,
    style: str = "cinematic",
    max_ai_scenes: int = 6,
) -> List[Dict[str, object]]:
    scenes: List[Dict[str, object]] = []
    for scene_index, group in enumerate(group_dialogues(dialogues, max_ai_scenes=max_ai_scenes)):
        first = group[0]
        text = " ".join(str(item.get("text", "")).strip() for item in group if str(item.get("text", "")).strip())
        emotion = str(first.get("emotion") or "neutral")
        speaker = str(first.get("speaker") or "NARRATOR")
        prompt = enhance_prompt(title, text, emotion, visual_theme, style, speaker)
        source_indices = [int(item.get("original_index", item.get("index", 0))) for item in group]
        scenes.append(Scene(scene_index, speaker, truncate_text(text, 360), emotion, prompt, style, source_indices).to_dict())
    return scenes


def scene_prompt_hash(scene: Dict[str, object]) -> str:
    raw = "|".join(str(scene.get(k, "")) for k in ("prompt", "style", "speaker", "emotion"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
