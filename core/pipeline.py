#!/usr/bin/env python3
"""Local-first idea-to-video pipeline.

AI planning uses Microsoft Foundry Local with NPU/QNN models only. Rendering stays
on CPU through FFmpeg so the NPU is reserved for inference.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import shlex
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from foundry_backend import FoundryError, generate_captions, generate_hooks_titles, generate_scene_json, generate_script, rewrite_viral, status as foundry_status
from image_generation import DEFAULT_ENGINE, generate_scene_images, image_engines_status

ROOT = Path(__file__).resolve().parents[1]
STORAGE = ROOT / "storage"
PROJECTS = STORAGE / "projects"
OUTPUTS = STORAGE / "outputs"
ASSETS = STORAGE / "assets"
def default_font() -> str:
    if os.name == "nt":
        candidates = [
            *(str(path) for path in (ASSETS / "fonts").glob("*.ttf")),
            *(str(path) for path in (ASSETS / "fonts").glob("*.otf")),
            r"C:/Windows/Fonts/arialbd.ttf",
            r"C:/Windows/Fonts/segoeuib.ttf",
            r"C:/Windows/Fonts/arial.ttf",
        ]
    else:
        candidates = [
            *(str(path) for path in (ASSETS / "fonts").glob("*.ttf")),
            *(str(path) for path in (ASSETS / "fonts").glob("*.otf")),
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return candidates[0]


def ffmpeg_fontfile(path: str) -> str:
    # FFmpeg filter syntax treats ':' as an option separator, so Windows
    # drive letters must be escaped even when subprocess passes argv safely.
    return path.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


FONT = default_font()

STYLE_PALETTES = {
    "neon": {"bg": "0x0B1026", "accent": "0x00E5FF", "text": "white", "box": "0x111827@0.72"},
    "documentary": {"bg": "0x243447", "accent": "0xF4D35E", "text": "white", "box": "0x0B1320@0.72"},
    "minimal": {"bg": "0xF4F1DE", "accent": "0x3D405B", "text": "0x111111", "box": "white@0.72"},
    "brainrot": {"bg": "0x16161A", "accent": "0xFF006E", "text": "white", "box": "0x000000@0.78"},
    "cinematic": {"bg": "0x101820", "accent": "0xFEE715", "text": "white", "box": "0x000000@0.70"},
}

RENDER_THREADS = os.environ.get("VIDEO_RENDER_THREADS", "4")
RENDER_PRESET = os.environ.get("VIDEO_RENDER_PRESET", "ultrafast")
KEEP_RENDER_WORKDIR = os.environ.get("KEEP_RENDER_WORKDIR", "0").lower() in {"1", "true", "yes"}

TRANSITIONS = ["cut", "fade", "push", "flash"]
CAMERA_MOVEMENTS = ["slow_zoom_in", "slow_zoom_out", "pan_left", "pan_right", "tilt_up", "static"]
EFFECTS = ["slow_zoom", "caption_pop", "pan_left", "pulse", "grain"]
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
MIN_SCENES = 3
MAX_SCENES = 8


@dataclass
class Scene:
    id: int
    duration: float
    visual_prompt: str
    voice_text: str
    subtitle: str
    camera_movement: str
    transition: str
    transition_duration: float
    effects: str
    style: str
    image_path: str | None = None


@dataclass
class Project:
    id: str
    prompt: str
    video_type: str
    duration: int
    style: str
    language: str
    voice: str
    created_at: str
    scenes: list[Scene]
    generate_images: bool = False
    image_engine: str = DEFAULT_ENGINE


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def ffmpeg_exists() -> bool:
    try:
        run(["ffmpeg", "-version"])
        run(["ffprobe", "-version"])
        return True
    except Exception:
        return False


def slug(text: str, max_len: int = 42) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return (value[:max_len].strip("-") or "project")


def clean_text(text: str, fallback: str = "Local AI video") -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return value or fallback


def wrap_text(text: str, width: int = 42, max_lines: int = 4) -> str:
    words = clean_text(text).split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and len(" ".join(words)) > len(" ".join(lines)):
        lines[-1] = lines[-1].rstrip(".") + "..."
    return "\\n".join(lines)


def shell_filter_escape(text: str) -> str:
    # FFmpeg drawtext/flite filter escaping, then pass as a single argv item.
    return str(text).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,").replace("%", "\\%").replace("\n", "\\n")


def write_drawtext_file(workdir: Path, name: str, text: str) -> str:
    path = workdir / f"{name}.txt"
    path.write_text(str(text or ""), encoding="utf-8")
    return filter_path(path)


def drawtext_file(workdir: Path, name: str, text: str, *, x: str, y: str, fontsize: int, fontcolor: str, borderw: int = 2, bordercolor: str = "black", line_spacing: int = 8) -> str:
    textfile = write_drawtext_file(workdir, name, text)
    return f"drawtext=fontfile={ffmpeg_fontfile(FONT)}:textfile='{textfile}':x={x}:y={y}:fontsize={fontsize}:fontcolor={fontcolor}:borderw={borderw}:bordercolor={bordercolor}:line_spacing={line_spacing}:reload=0"


def asset_files(folder: str, extensions: set[str]) -> list[Path]:
    root = ASSETS / folder
    if not root.exists():
        return []
    return sorted(
        [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in extensions],
        key=lambda path: (path.name.lower().startswith("default_"), path.name.lower()),
    )


def pick_asset(folder: str, extensions: set[str], index: int = 1) -> Path | None:
    files = asset_files(folder, extensions)
    if not files:
        return None
    return files[(max(1, index) - 1) % len(files)]


def filter_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def camera_motion_filters(movement: str, duration: float) -> list[str]:
    frames = max(1, int(duration * 30))
    movement = (movement or "slow_zoom_in").lower()
    if movement == "static":
        return []
    if movement == "slow_zoom_out":
        return [f"zoompan=z='max(1.0,1.12-on/{frames}*0.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=720x1280:fps=30"]
    if movement == "pan_left":
        return [f"zoompan=z=1.10:x='(iw-iw/zoom)*(1-on/{frames})':y='ih/2-(ih/zoom/2)':d=1:s=720x1280:fps=30"]
    if movement == "pan_right":
        return [f"zoompan=z=1.10:x='(iw-iw/zoom)*on/{frames}':y='ih/2-(ih/zoom/2)':d=1:s=720x1280:fps=30"]
    if movement == "tilt_up":
        return [f"zoompan=z=1.08:x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(1-on/{frames})':d=1:s=720x1280:fps=30"]
    return ["zoompan=z='min(zoom+0.0015,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=720x1280:fps=30"]


def target_scene_count(duration: int) -> int:
    return max(MIN_SCENES, min(MAX_SCENES, round(max(9, duration) / 6)))


def resize_text(text: str, max_len: int = 170) -> str:
    value = clean_text(text)
    return value if len(value) <= max_len else value[:max_len].rsplit(" ", 1)[0].rstrip(".,;: ") + "..."


def generated_scene_text(prompt: str, step: int, total: int, language: str) -> str:
    if language == "hi-IN":
        templates = [
            "शुरुआत: इस विषय को आसान भाषा में समझते हैं।",
            f"मुख्य बात {step}: यह आपके काम को तेज, निजी और लोकल बनाता है।",
            f"उदाहरण {step}: क्रिएटर इसी से स्क्रिप्ट, सीन और कैप्शन जल्दी बना सकता है।",
            "अंत में: सही सेटअप से ऑफलाइन वीडियो बनाना आसान हो जाता है।",
        ]
        return templates[min(step - 1, len(templates) - 1)]
    if language == "es-ES":
        return f"Parte {step} de {total}: {prompt}, explicado de forma clara y práctica."
    if language == "fr-FR":
        return f"Partie {step} sur {total} : {prompt}, expliqué simplement et concrètement."
    if language == "de-DE":
        return f"Teil {step} von {total}: {prompt}, klar und praktisch erklärt."
    return f"Part {step} of {total}: {prompt}, explained clearly with a practical takeaway."


def normalized_scenes(items: list[Any], prompt: str, video_type: str, duration: int, style: str, language: str) -> list[Scene]:
    desired_count = target_scene_count(duration)
    valid_items = [item for item in items if isinstance(item, dict)]
    if len(valid_items) > MAX_SCENES:
        valid_items = valid_items[:MAX_SCENES]
    while len(valid_items) < desired_count:
        step = len(valid_items) + 1
        fallback_text = generated_scene_text(prompt, step, desired_count, language)
        valid_items.append({
            "id": step,
            "visual_prompt": f"{style} {video_type} scene about {prompt}, part {step}, cinematic composition, readable captions",
            "voice_text": fallback_text,
            "subtitle": fallback_text,
            "camera_movement": CAMERA_MOVEMENTS[step % len(CAMERA_MOVEMENTS)],
            "transition": TRANSITIONS[step % len(TRANSITIONS)],
            "transition_duration": 0.45,
            "effects": EFFECTS[step % len(EFFECTS)],
            "style": style,
        })
    per_scene = round(max(9, duration) / len(valid_items), 2)
    scenes: list[Scene] = []
    for i, item in enumerate(valid_items, start=1):
        transition = clean_text(item.get("transition"), TRANSITIONS[i % len(TRANSITIONS)]).lower()
        camera_movement = clean_text(item.get("camera_movement") or item.get("camera"), CAMERA_MOVEMENTS[i % len(CAMERA_MOVEMENTS)]).lower()
        effects = clean_text(item.get("effects"), EFFECTS[i % len(EFFECTS)]).lower()
        voice_text = resize_text(item.get("voiceover") or item.get("voice_text") or generated_scene_text(prompt, i, len(valid_items), language), 220)
        subtitle = resize_text(item.get("subtitle") or voice_text, 170)
        try:
            transition_duration = float(item.get("transition_duration") or item.get("transitionDuration") or 0.45)
        except Exception:
            transition_duration = 0.45
        scenes.append(Scene(
            id=i,
            duration=per_scene,
            visual_prompt=resize_text(item.get("visual_prompt") or f"{style} {video_type} scene {i} about {prompt}"),
            voice_text=voice_text,
            subtitle=subtitle,
            camera_movement=camera_movement if camera_movement in CAMERA_MOVEMENTS else CAMERA_MOVEMENTS[i % len(CAMERA_MOVEMENTS)],
            transition=transition if transition in TRANSITIONS else TRANSITIONS[i % len(TRANSITIONS)],
            transition_duration=max(0.0, min(1.2, transition_duration)),
            effects=effects if effects in EFFECTS else EFFECTS[i % len(EFFECTS)],
            style=clean_text(item.get("style"), style).lower(),
            image_path=clean_text(item.get("image_path"), "") or None,
        ))
    remaining = round(max(9, duration) - sum(scene.duration for scene in scenes[:-1]), 2)
    scenes[-1].duration = max(2.0, remaining)
    return scenes


def foundry_plan(prompt: str, video_type: str, duration: int, style: str, language: str, voice: str = "auto", generate_images: bool = False, image_engine: str = DEFAULT_ENGINE) -> Project:
    data = generate_scene_json(prompt, video_type, duration, style, language, voice)
    scenes = normalized_scenes(data.get("scenes", []), prompt, video_type, duration, style, language)
    if not scenes:
        raise ValueError("Foundry Local returned no scenes")
    return Project(
        id=f"{slug(prompt)}-{int(time.time())}",
        prompt=prompt,
        video_type=video_type,
        duration=duration,
        style=style,
        language=language,
        voice=voice,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        scenes=scenes,
        generate_images=generate_images,
        image_engine=image_engine,
    )


def project_to_dict(project: Project) -> dict[str, Any]:
    return {
        "id": project.id,
        "prompt": project.prompt,
        "video_type": project.video_type,
        "duration": project.duration,
        "style": project.style,
        "language": project.language,
        "voice": project.voice,
        "created_at": project.created_at,
        "generate_images": project.generate_images,
        "image_engine": project.image_engine,
        "scenes": [asdict(scene) for scene in project.scenes],
    }


def project_from_dict(data: dict[str, Any]) -> Project:
    scenes = [Scene(
        id=int(scene.get("id", i + 1)),
        duration=float(scene.get("duration", 5)),
        visual_prompt=clean_text(scene.get("visual_prompt"), "Generated visual"),
        voice_text=clean_text(scene.get("voiceover") or scene.get("voice_text"), "Generated narration"),
        subtitle=clean_text(scene.get("subtitle") or scene.get("voice_text"), "Generated subtitle"),
        camera_movement=clean_text(scene.get("camera_movement") or scene.get("camera"), "slow_zoom_in"),
        transition=clean_text(scene.get("transition"), "fade"),
        transition_duration=max(0.0, min(1.2, float(scene.get("transition_duration") or scene.get("transitionDuration") or 0.45))),
        effects=clean_text(scene.get("effects"), "slow_zoom"),
        style=clean_text(scene.get("style"), data.get("style", "neon")),
        image_path=clean_text(scene.get("image_path"), "") or None,
    ) for i, scene in enumerate(data.get("scenes", []))]
    if not scenes:
        raise ValueError("Project JSON must include at least one scene before rendering")
    return Project(
        id=data.get("id") or f"{slug(data.get('prompt', 'project'))}-{int(time.time())}",
        prompt=data.get("prompt", "Local AI video"),
        video_type=data.get("video_type", "explainer"),
        duration=int(data.get("duration", sum(s.duration for s in scenes))),
        style=data.get("style", "neon"),
        language=data.get("language", "en"),
        voice=data.get("voice", "auto"),
        created_at=data.get("created_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
        scenes=scenes,
        generate_images=bool(data.get("generate_images") or data.get("generateImages")),
        image_engine=str(data.get("image_engine") or data.get("imageEngine") or DEFAULT_ENGINE),
    )


def save_project(project: Project) -> Path:
    PROJECTS.mkdir(parents=True, exist_ok=True)
    path = PROJECTS / f"{project.id}.json"
    path.write_text(json.dumps(project_to_dict(project), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_project(path: Path) -> Project:
    return project_from_dict(json.loads(path.read_text(encoding="utf-8")))


def audio_duration(path: Path) -> float:
    try:
        result = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)])
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def synthesize_with_coqui(text: str, out: Path, language: str) -> bool:
    model_name = os.environ.get("COQUI_TTS_MODEL")
    if not model_name:
        return False
    try:
        from TTS.api import TTS  # type: ignore
        tts = TTS(model_name=model_name, progress_bar=False, gpu=False)
        kwargs: dict[str, Any] = {"text": text, "file_path": str(out)}
        if "xtts" in model_name.lower():
            kwargs["language"] = language if language != "auto" else "en"
        tts.tts_to_file(**kwargs)
        return out.exists() and out.stat().st_size > 1000
    except Exception as exc:
        print(f"[pipeline] Coqui TTS failed, falling back to FFmpeg flite: {exc}", file=sys.stderr)
        return False


def synthesize_with_windows_sapi(text: str, out: Path, language: str, voice: str) -> bool:
    if os.name != "nt":
        return False
    language_prefix = (language or "en").split("-")[0].lower()
    gender = "Female" if voice == "female" else "Male" if voice == "male" else ""
    explicit_name = voice if voice not in {"", "auto", "female", "male"} else ""
    script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voices = $synth.GetInstalledVoices() | Where-Object {{ $_.Enabled }}
$explicitName = {json.dumps(explicit_name)}
$languagePrefix = {json.dumps(language_prefix)}
$gender = {json.dumps(gender)}
if ($explicitName) {{
  $voice = $voices | Where-Object {{ $_.VoiceInfo.Name -eq $explicitName }} | Select-Object -First 1
  if ($voice) {{ $synth.SelectVoice($voice.VoiceInfo.Name) }}
}} elseif ($languagePrefix -or $gender) {{
  $voice = $voices | Where-Object {{
    (-not $languagePrefix -or $_.VoiceInfo.Culture.Name.ToLower().StartsWith($languagePrefix)) -and
    (-not $gender -or $_.VoiceInfo.Gender.ToString() -eq $gender)
  }} | Select-Object -First 1
  if (-not $voice -and $languagePrefix) {{
    $voice = $voices | Where-Object {{ $_.VoiceInfo.Culture.Name.ToLower().StartsWith($languagePrefix) }} | Select-Object -First 1
  }}
  if (-not $voice -and $gender) {{
    $voice = $voices | Where-Object {{ $_.VoiceInfo.Gender.ToString() -eq $gender }} | Select-Object -First 1
  }}
  if ($voice) {{ $synth.SelectVoice($voice.VoiceInfo.Name) }}
}}
$synth.Rate = 0
$synth.Volume = 100
$synth.SetOutputToWaveFile({json.dumps(str(out))})
$synth.Speak({json.dumps(text[:850])})
$synth.Dispose()
""".strip()
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode == 0 and out.exists() and out.stat().st_size > 1000:
            return True
        print(f"[pipeline] Windows SAPI TTS failed, trying FFmpeg flite: {result.stderr}", file=sys.stderr)
    except Exception as exc:
        print(f"[pipeline] Windows SAPI TTS unavailable, trying FFmpeg flite: {exc}", file=sys.stderr)
    return False


def synthesize_voice(scene: Scene, out: Path, language: str, voice: str = "auto") -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    if synthesize_with_coqui(scene.voice_text, out, language):
        return out
    if synthesize_with_windows_sapi(scene.voice_text, out, language, voice):
        return out
    flite_voice = "slt" if voice in {"auto", "female"} else "rms"
    escaped = shell_filter_escape(scene.voice_text[:850])
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", f"flite=text='{escaped}':voice={flite_voice}",
        "-ar", "44100", "-ac", "1", str(out)
    ]
    try:
        run(cmd)
        return out
    except Exception:
        duration = max(1.0, scene.duration)
        run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=420:duration={duration}", "-ar", "44100", "-ac", "1", str(out)])
        return out


def make_subtitles(project: Project, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    cursor = 0.0
    blocks = []
    caption_index = 1
    for scene in project.scenes:
        text = clean_text(scene.subtitle or scene.voice_text)
        words = text.split()
        chunk_size = 7 if len(words) > 12 else max(4, len(words))
        chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)] or [text]
        scene_start = cursor
        scene_duration = float(scene.duration)
        for chunk_idx, chunk in enumerate(chunks):
            start = scene_start + (scene_duration * chunk_idx / len(chunks))
            end = scene_start + (scene_duration * (chunk_idx + 1) / len(chunks))
            blocks.append(f"{caption_index}\n{srt_time(start)} --> {srt_time(end)}\n{chunk}\n")
            caption_index += 1
        cursor = scene_start + scene_duration
    out.write_text("\n".join(blocks), encoding="utf-8")
    return out


def srt_time(seconds: float) -> str:
    millis = int((seconds - int(seconds)) * 1000)
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{millis:03d}"


def render_scene(project: Project, scene: Scene, workdir: Path, index: int) -> Path:
    palette = STYLE_PALETTES.get(project.style, STYLE_PALETTES["neon"])
    wav = workdir / f"scene_{index:02d}.wav"
    mp4 = workdir / f"scene_{index:02d}.mp4"
    synthesize_voice(scene, wav, project.language, project.voice)
    duration = max(float(scene.duration), 2.5)
    scene.duration = round(duration, 2)

    scene_image = Path(scene.image_path) if scene.image_path else None
    background = scene_image if scene_image and scene_image.exists() else pick_asset("footage", VIDEO_EXTS | IMAGE_EXTS, index)
    character = pick_asset("characters", IMAGE_EXTS, index)
    title = wrap_text(scene.visual_prompt, 24, 4)
    caption = wrap_text(scene.subtitle or scene.voice_text, 24, 5)
    effect_label = f"SCENE {scene.id:02d}  •  {scene.effects.upper()}"
    tag = clean_text(project.video_type, "video").upper()

    if background:
        base_filters = []
        if background.suffix.lower() in IMAGE_EXTS:
            base_filters.extend([
                "scale=900:1600:force_original_aspect_ratio=increase",
                "crop=900:1600",
                *camera_motion_filters(scene.camera_movement, duration),
            ])
        else:
            base_filters.extend([
                "scale=720:1280:force_original_aspect_ratio=increase",
                "crop=720:1280",
            ])
        base_filters.extend([
            "setsar=1",
            "eq=contrast=1.12:brightness=-0.05:saturation=1.15",
            "boxblur=1:1",
            "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.22:t=fill",
        ])
    else:
        base_filters = [f"drawbox=x=0:y=0:w=iw:h=ih:color={palette['bg']}:t=fill"]

    draw_filters = base_filters + [
        "drawgrid=width=72:height=72:thickness=1:color=white@0.06",
        f"drawbox=x=0:y=0:w=720:h=1280:color={palette['accent']}@0.08:t=fill",
        f"drawbox=x=-80+mod(t*95\\,880):y=140:w=180:h=180:color={palette['accent']}@0.35:t=fill",
        f"drawbox=x=520-mod(t*70\\,820):y=875:w=260:h=260:color=white@0.11:t=fill",
        f"drawbox=x=36:y=54:w=648:h=72:color=black@0.42:t=fill",
        drawtext_file(workdir, f"scene_{index:02d}_tag", tag, x="60", y="74", fontsize=30, fontcolor=palette['accent'], borderw=2),
        drawtext_file(workdir, f"scene_{index:02d}_effect", effect_label, x="w-text_w-60", y="78", fontsize=22, fontcolor=palette['text'], borderw=2),
        f"drawbox=x=44:y=170:w=632:h=420:color={palette['box']}:t=fill",
        f"drawbox=x=44:y=170:w=12:h=420:color={palette['accent']}:t=fill",
        drawtext_file(workdir, f"scene_{index:02d}_title", title, x="82", y="214", fontsize=42, fontcolor=palette['text'], borderw=3, line_spacing=14),
        f"drawbox=x=38:y=720:w=644:h=360:color=black@0.62:t=fill",
        drawtext_file(workdir, f"scene_{index:02d}_caption", caption, x="(w-text_w)/2", y="760", fontsize=52, fontcolor="white", borderw=5, line_spacing=18),
        f"drawbox=x=58:y=1164:w=604:h=14:color=white@0.22:t=fill",
        f"drawbox=x=58:y=1164:w={int(604 * index / max(1, len(project.scenes)))}:h=14:color={palette['accent']}:t=fill",
        drawtext_file(workdir, f"scene_{index:02d}_template", f"{project.style.upper()} TEMPLATE", x="58", y="1192", fontsize=22, fontcolor=palette['text'], borderw=2),
        f"fade=t=in:st=0:d=0.25,fade=t=out:st={max(duration - 0.35, 0)}:d=0.35",
    ]

    if background:
        if background.suffix.lower() in VIDEO_EXTS:
            input_args = ["-stream_loop", "-1", "-i", str(background)]
        else:
            input_args = ["-loop", "1", "-i", str(background)]
    else:
        input_args = ["-f", "lavfi", "-i", f"color=c={palette['bg']}:s=720x1280:r=30:d={duration}"]

    character_args: list[str] = []
    audio_input_index = 1
    filter_arg_name = "-vf"
    filter_value = ",".join(draw_filters)
    map_args: list[str] = []
    if character:
        character_args = ["-loop", "1", "-i", str(character)]
        audio_input_index = 2
        filter_arg_name = "-filter_complex"
        filter_value = (
            f"[0:v]{','.join(draw_filters)}[base];"
            f"[1:v]scale=260:-1:force_original_aspect_ratio=decrease[char];"
            f"[base][char]overlay=x=W-w-34:y=H-h-156:format=auto[v]"
        )
        map_args = ["-map", "[v]", "-map", f"{audio_input_index}:a"]
    else:
        map_args = ["-map", "0:v", "-map", "1:a"]

    try:
        run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            *input_args, *character_args, "-i", str(wav), filter_arg_name, filter_value, *map_args, "-t", f"{duration:.2f}",
            "-c:v", "libx264", "-preset", RENDER_PRESET, "-threads", RENDER_THREADS, "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(mp4)
        ])
    except subprocess.CalledProcessError as exc:
        print(f"[pipeline] Styled scene render failed, using safe fallback scene renderer: {exc.stderr or exc}", file=sys.stderr)
        safe_vf = ",".join([
            f"drawbox=x=0:y=0:w=iw:h=ih:color={palette['bg']}:t=fill",
            "drawgrid=width=72:height=72:thickness=1:color=white@0.07",
            f"drawbox=x=44:y=170:w=632:h=420:color={palette['box']}:t=fill",
            f"drawbox=x=44:y=170:w=12:h=420:color={palette['accent']}:t=fill",
            drawtext_file(workdir, f"scene_{index:02d}_safe_title", title, x="82", y="214", fontsize=42, fontcolor=palette['text'], borderw=3, line_spacing=14),
            f"drawbox=x=38:y=720:w=644:h=360:color=black@0.62:t=fill",
            drawtext_file(workdir, f"scene_{index:02d}_safe_caption", caption, x="(w-text_w)/2", y="760", fontsize=52, fontcolor="white", borderw=5, line_spacing=18),
            f"drawbox=x=58:y=1164:w={int(604 * index / max(1, len(project.scenes)))}:h=14:color={palette['accent']}:t=fill",
        ])
        try:
            run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", f"color=c={palette['bg']}:s=720x1280:r=30:d={duration}",
                "-i", str(wav), "-vf", safe_vf, "-t", f"{duration:.2f}",
                "-c:v", "libx264", "-preset", "ultrafast", "-threads", RENDER_THREADS, "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(mp4)
            ])
        except subprocess.CalledProcessError as fallback_exc:
            print(f"[pipeline] Text scene fallback failed, rendering no-text CPU-safe scene: {fallback_exc.stderr or fallback_exc}", file=sys.stderr)
            no_text_vf = ",".join([
                f"drawbox=x=0:y=0:w=iw:h=ih:color={palette['bg']}:t=fill",
                "drawgrid=width=72:height=72:thickness=1:color=white@0.07",
                f"drawbox=x=44:y=170:w=632:h=420:color={palette['box']}:t=fill",
                f"drawbox=x=44:y=170:w=12:h=420:color={palette['accent']}:t=fill",
                f"drawbox=x=38:y=720:w=644:h=360:color=black@0.62:t=fill",
                f"drawbox=x=58:y=1164:w={int(604 * index / max(1, len(project.scenes)))}:h=14:color={palette['accent']}:t=fill",
            ])
            run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", f"color=c={palette['bg']}:s=720x1280:r=30:d={duration}",
                "-i", str(wav), "-vf", no_text_vf, "-t", f"{duration:.2f}",
                "-c:v", "libx264", "-preset", "ultrafast", "-threads", RENDER_THREADS, "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(mp4)
            ])
    return mp4


def stitch_with_transitions(scene_files: list[Path], scenes: list[Scene], out: Path) -> bool:
    if len(scene_files) < 2:
        shutil.copyfile(scene_files[0], out)
        return True
    durations = [max(0.1, audio_duration(path)) for path in scene_files]
    inputs: list[str] = []
    for path in scene_files:
        inputs.extend(["-i", str(path)])
    video_label = "0:v"
    audio_label = "0:a"
    video_filters: list[str] = []
    audio_filters: list[str] = []
    elapsed = durations[0]
    transition_map = {"fade": "fade", "push": "slideright", "flash": "fadewhite", "cut": "fade"}
    for idx in range(1, len(scene_files)):
        duration = min(max(float(scenes[idx].transition_duration or 0.35), 0.08), min(durations[idx - 1], durations[idx]) / 2)
        offset = max(0.02, elapsed - duration)
        transition = transition_map.get((scenes[idx].transition or "fade").lower(), "fade")
        next_video = f"v{idx}"
        next_audio = f"a{idx}"
        video_filters.append(f"[{video_label}][{idx}:v]xfade=transition={transition}:duration={duration:.2f}:offset={offset:.2f}[{next_video}]")
        audio_filters.append(f"[{audio_label}][{idx}:a]acrossfade=d={duration:.2f}:c1=tri:c2=tri[{next_audio}]")
        video_label = next_video
        audio_label = next_audio
        elapsed += durations[idx] - duration
    filter_complex = ";".join(video_filters + audio_filters)
    try:
        run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            *inputs, "-filter_complex", filter_complex,
            "-map", f"[{video_label}]", "-map", f"[{audio_label}]",
            "-c:v", "libx264", "-preset", RENDER_PRESET, "-threads", RENDER_THREADS, "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)
        ])
        return True
    except subprocess.CalledProcessError as exc:
        print(f"[pipeline] Transition stitch failed, falling back to concat: {exc.stderr or exc}", file=sys.stderr)
        return False


def render_project(project: Project, out: Path | None = None, progress_callback: Callable[[int, str], None] | None = None) -> dict[str, Any]:
    if not ffmpeg_exists():
        raise RuntimeError("FFmpeg and FFprobe are required. Install them locally and retry.")
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    workdir = OUTPUTS / f"{project.id}_work"
    workdir.mkdir(parents=True, exist_ok=True)
    if project.generate_images:
        generate_scene_images(project, project.image_engine, progress_callback)
    scene_files = []
    total = max(1, len(project.scenes))
    if progress_callback:
        progress_callback(3, "Preparing render workspace")
    for index, scene in enumerate(project.scenes, start=1):
        if progress_callback:
            progress_callback(int(5 + ((index - 1) / total) * 78), f"Rendering scene {index} of {total}")
        scene_files.append(render_scene(project, scene, workdir, index))
        if progress_callback:
            progress_callback(int(5 + (index / total) * 78), f"Finished scene {index} of {total}")
    concat = workdir / "concat.txt"
    concat.write_text("".join(f"file {shlex.quote(str(path))}\n" for path in scene_files), encoding="utf-8")
    out = out or (OUTPUTS / f"{project.id}.mp4")
    if progress_callback:
        progress_callback(88, "Stitching scenes with transitions")
    stitched = workdir / "stitched.mp4"
    if not stitch_with_transitions(scene_files, project.scenes, stitched):
        run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(concat),
            "-c", "copy", "-movflags", "+faststart", str(stitched)
        ])
    music = pick_asset("music", AUDIO_EXTS, 1)
    if music:
        if progress_callback:
            progress_callback(92, "Mixing local background music")
        run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(stitched), "-stream_loop", "-1", "-i", str(music),
            "-filter_complex", "[0:a]volume=1.0[a0];[1:a]volume=0.14[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=2[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)
        ])
    else:
        shutil.copyfile(stitched, out)
    if progress_callback:
        progress_callback(96, "Writing subtitles and project file")
    srt = make_subtitles(project, OUTPUTS / f"{project.id}.srt")
    project_file = save_project(project)
    if progress_callback:
        progress_callback(100, "Render complete")
    temp_cleaned = False
    if not KEEP_RENDER_WORKDIR:
        shutil.rmtree(workdir, ignore_errors=True)
        temp_cleaned = True
    return {"video": str(out), "subtitles": str(srt), "project": str(project_file), "scenes": len(project.scenes), "temp_cleaned": temp_cleaned}


def command_plan(args: argparse.Namespace) -> None:
    project = foundry_plan(args.prompt, args.video_type, args.duration, args.style, args.language, args.voice, args.generate_images, args.image_engine)
    if args.save:
        save_project(project)
    print(json.dumps(project_to_dict(project), indent=2, ensure_ascii=False))


def command_status(args: argparse.Namespace) -> None:
    try:
        foundry = foundry_status()
    except FoundryError as exc:
        foundry = {"ok": False, "backend": "Foundry Local", "error": str(exc)}
    print(json.dumps({"foundry": foundry, "image_engines": image_engines_status()}, indent=2, ensure_ascii=False))


def command_script(args: argparse.Namespace) -> None:
    print(json.dumps({"script": generate_script(args.prompt, args.video_type, args.duration, args.style, args.language), **foundry_status()}, indent=2, ensure_ascii=False))


def command_hooks(args: argparse.Namespace) -> None:
    print(json.dumps({"result": generate_hooks_titles(args.prompt, args.video_type, args.language), **foundry_status()}, indent=2, ensure_ascii=False))


def command_captions(args: argparse.Namespace) -> None:
    print(json.dumps({"result": generate_captions(args.text, args.language), **foundry_status()}, indent=2, ensure_ascii=False))


def command_viral(args: argparse.Namespace) -> None:
    print(json.dumps({"text": rewrite_viral(args.text, args.platform, args.language), **foundry_status()}, indent=2, ensure_ascii=False))


def command_render(args: argparse.Namespace) -> None:
    if args.project:
        project = load_project(Path(args.project))
    else:
        project = foundry_plan(args.prompt, args.video_type, args.duration, args.style, args.language, args.voice, args.generate_images, args.image_engine)
    result = render_project(project, Path(args.out) if args.out else None)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def command_images(args: argparse.Namespace) -> None:
    project = load_project(Path(args.project))
    generate_scene_images(project, args.engine)
    save_project(project)
    print(json.dumps(project_to_dict(project), indent=2, ensure_ascii=False))


def add_ai_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--prompt", default="A local AI video about efficient content creation")
    parser.add_argument("--video-type", default="explainer")
    parser.add_argument("--duration", type=int, default=24)
    parser.add_argument("--style", choices=sorted(STYLE_PALETTES), default="neon")
    parser.add_argument("--language", default="en")
    parser.add_argument("--voice", choices=["auto", "male", "female"], default="auto")
    parser.add_argument("--generate-images", action="store_true", help="Generate per-scene images before rendering")
    parser.add_argument("--image-engine", default=DEFAULT_ENGINE, choices=["pollinations", "cloudflare", "replicate", "puter", "templates"], help="Image engine to use when --generate-images is enabled")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local-first AI video pipeline using Foundry Local NPU/QNN models")
    sub = parser.add_subparsers(required=True)
    status_parser = sub.add_parser("status")
    status_parser.set_defaults(func=command_status)
    for name in ("plan", "render", "script", "hooks"):
        p = sub.add_parser(name)
        add_ai_args(p)
        command = {"plan": command_plan, "render": command_render, "script": command_script, "hooks": command_hooks}[name]
        p.set_defaults(func=command)
    captions = sub.add_parser("captions")
    captions.add_argument("--text", required=True)
    captions.add_argument("--language", default="en")
    captions.set_defaults(func=command_captions)
    viral = sub.add_parser("viral")
    viral.add_argument("--text", required=True)
    viral.add_argument("--platform", default="short-form video")
    viral.add_argument("--language", default="en")
    viral.set_defaults(func=command_viral)
    sub.choices["plan"].add_argument("--save", action="store_true")
    sub.choices["render"].add_argument("--project", help="Path to editable project JSON")
    sub.choices["render"].add_argument("--out", help="Output MP4 path")
    images = sub.add_parser("images")
    images.add_argument("--project", required=True, help="Path to editable project JSON")
    images.add_argument("--engine", default=DEFAULT_ENGINE, choices=["pollinations", "cloudflare", "replicate", "puter", "templates"], help="Image engine for scene previews")
    images.set_defaults(func=command_images)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
