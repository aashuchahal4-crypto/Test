import math
import os
import shutil
import subprocess
import tempfile
import textwrap
import uuid
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ai_backgrounds import create_gradient_background
from script_generator import parse_custom_script
from tiktok_tts import VOICES, text_to_speech

WIDTH, HEIGHT = 1080, 1920
FPS = 30

STYLE_REGISTRY = {
    "Classic": {"fill": "white", "stroke": "black", "stroke_width": 5, "card": None, "upper": False},
    "Modern-Dark": {"fill": "white", "stroke": "#111111", "stroke_width": 4, "card": (0, 0, 0, 155), "upper": False},
    "Yellow-Pop": {"fill": "#ffe934", "stroke": "black", "stroke_width": 7, "card": None, "upper": True},
    "TikTok-Blast": {"fill": "white", "stroke": "#ff0050", "stroke_width": 5, "shadow": "#00f2ea", "upper": True},
    "Karaoke-Green": {"fill": "white", "stroke": "black", "stroke_width": 5, "card": (0, 180, 95, 145), "upper": False},
    "Minimal-Shadow": {"fill": "white", "stroke": "#222222", "stroke_width": 2, "shadow": "#000000", "upper": False},
    "MrBeast Yellow": {"fill": "#fff200", "accent": "white", "stroke": "black", "stroke_width": 9, "upper": True},
    "Reddit Story": {"fill": "white", "stroke": "#111111", "stroke_width": 2, "card": (12, 16, 25, 205), "upper": False},
    "Neon Glow": {"fill": "#dffcff", "stroke": "#0ff0fc", "stroke_width": 4, "glow": "#ff00ff", "upper": False},
    "Clean Podcast": {"fill": "white", "stroke": "#1d1d1d", "stroke_width": 2, "shadow": "#000000", "upper": False},
    "Horror": {"fill": "#f4f4f4", "accent": "#ff2020", "stroke": "#120000", "stroke_width": 7, "upper": True},
    "Meme Impact": {"fill": "white", "stroke": "black", "stroke_width": 9, "upper": True},
}

FONT_CANDIDATES = [
    "assets/fonts/Impact.ttf",
    "assets/fonts/Inter-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
    "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf",
]


def _run(cmd: List[str], label: str) -> None:
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout)[-3000:]
        raise RuntimeError(f"{label} failed: {tail}")


def _font_path() -> str:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return path
    return ""


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = _font_path()
    if path:
        return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
    words = str(text or "").replace("\n", " ").split()
    if not words:
        return [""]
    lines: List[str] = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font, stroke_width=0)[2] <= max_width or not line:
            line = candidate
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _rounded_rectangle(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int], radius: int, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def create_caption_image(text: str, output_path: str, style: str = "Classic", position: str = "Center", animation: str = "None") -> str:
    cfg = STYLE_REGISTRY.get(style, STYLE_REGISTRY["Classic"])
    img = Image.new("RGBA", (WIDTH, 520), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    clean = str(text or "").strip()
    if cfg.get("upper"):
        clean = clean.upper()
    max_width = 920
    font_size = 82 if len(clean) < 80 else 70
    while font_size >= 40:
        font = _load_font(font_size)
        lines = _wrap_text(draw, clean, font, max_width)
        line_h = int(font_size * 1.14)
        total_h = len(lines) * line_h
        widest = max(draw.textbbox((0, 0), line, font=font, stroke_width=int(cfg.get("stroke_width", 0)))[2] for line in lines)
        if total_h <= 410 and widest <= max_width:
            break
        font_size -= 4
    font = _load_font(font_size)
    lines = _wrap_text(draw, clean, font, max_width)
    line_h = int(font_size * 1.16)
    total_h = len(lines) * line_h
    y = (img.height - total_h) // 2
    card = cfg.get("card")
    if animation == "Karaoke Highlight" and not card:
        card = (255, 230, 0, 120)
    if card:
        _rounded_rectangle(draw, (52, max(20, y - 34), WIDTH - 52, min(img.height - 20, y + total_h + 34)), 36, card)
    if cfg.get("glow"):
        glow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_layer)
        gy = y
        for line in lines:
            bbox = glow_draw.textbbox((0, 0), line, font=font, stroke_width=8)
            x = (WIDTH - (bbox[2] - bbox[0])) // 2
            glow_draw.text((x, gy), line, font=font, fill=cfg["glow"], stroke_width=10, stroke_fill=cfg["glow"])
            gy += line_h
        img.alpha_composite(glow_layer.filter(ImageFilter.GaussianBlur(11)))
        draw = ImageDraw.Draw(img)
    shadow = cfg.get("shadow")
    for idx, line in enumerate(lines):
        accent = cfg.get("accent") if idx == 0 and cfg.get("accent") else cfg.get("fill", "white")
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=int(cfg.get("stroke_width", 0)))
        x = (WIDTH - (bbox[2] - bbox[0])) // 2
        line_y = y + idx * line_h
        if shadow:
            draw.text((x + 4, line_y + 5), line, font=font, fill=shadow, stroke_width=int(cfg.get("stroke_width", 0)), stroke_fill=shadow)
        draw.text(
            (x, line_y),
            line,
            font=font,
            fill=accent,
            stroke_width=int(cfg.get("stroke_width", 4)),
            stroke_fill=cfg.get("stroke", "black"),
        )
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    return output_path


def create_title_image(title: str, output_path: str, style: str = "MrBeast Yellow") -> str:
    img = Image.new("RGBA", (WIDTH, 360), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font_size = 92
    clean = str(title or "Untitled Reel").strip().upper()
    while font_size >= 44:
        font = _load_font(font_size)
        lines = _wrap_text(draw, clean, font, 940)
        if len(lines) * int(font_size * 1.1) <= 300:
            break
        font_size -= 5
    font = _load_font(font_size)
    lines = _wrap_text(draw, clean, font, 940)
    y = (img.height - len(lines) * int(font_size * 1.1)) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=9)
        x = (WIDTH - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, font=font, fill="#fff200", stroke_width=9, stroke_fill="black")
        y += int(font_size * 1.1)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    return output_path


def _ffprobe_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        return max(0.05, float(result.stdout.strip()))
    except Exception:
        return 1.0


def _resolve_voice(voice_name: str) -> str:
    return VOICES.get(voice_name, voice_name or "en_us_001")


def _line_voice(line: Dict[str, object], voice_narrator: str, voice1: str, voice2: str) -> str:
    speaker = str(line.get("speaker", "NARRATOR")).upper()
    if "CHARACTER2" in speaker or speaker.endswith("2") or "SPEAKER2" in speaker:
        return _resolve_voice(voice2)
    if "CHARACTER1" in speaker or speaker.endswith("1") or "SPEAKER1" in speaker:
        return _resolve_voice(voice1)
    return _resolve_voice(voice_narrator)


def _prepare_audio(dialogues: List[Dict[str, object]], tmp: Path, voice_narrator: str, voice1: str, voice2: str, voice_volume: float) -> Tuple[str, List[Dict[str, object]], float]:
    audio_dir = tmp / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    concat_lines = []
    timestamps: List[Dict[str, object]] = []
    current = 0.0
    gap = 0.18
    for i, line in enumerate(dialogues):
        raw = audio_dir / f"raw_{i}.mp3"
        wav = audio_dir / f"line_{i}.wav"
        text_to_speech(str(line.get("text", "")), _line_voice(line, voice_narrator, voice1, voice2), str(raw), str(line.get("emotion", "neutral")))
        _run([
            "ffmpeg", "-y", "-i", str(raw), "-af", f"volume={voice_volume},loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "44100", "-ac", "2", str(wav)
        ], "voice processing")
        dur = _ffprobe_duration(str(wav))
        start, end = current, current + dur
        enriched = dict(line)
        enriched.update({"start": start, "end": end, "duration": dur, "index": i})
        timestamps.append(enriched)
        concat_lines.append(f"file '{wav.as_posix()}'")
        current = end
        if i != len(dialogues) - 1:
            silent = audio_dir / f"gap_{i}.wav"
            _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", str(gap), str(silent)], "silence gap")
            concat_lines.append(f"file '{silent.as_posix()}'")
            current += gap
    concat_file = audio_dir / "concat.txt"
    concat_file.write_text("\n".join(concat_lines), encoding="utf-8")
    out = audio_dir / "narration.wav"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(out)], "audio concat")
    return str(out), timestamps, max(current, 1.0)


def _scale_crop_filter() -> str:
    return f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},setsar=1,fps={FPS}"


def _image_clip(image_path: str, output_path: str, duration: float, transition_style: str = "Cut") -> str:
    vf = _scale_crop_filter()
    if transition_style == "Fade" and duration > 0.8:
        vf += f",fade=t=in:st=0:d=0.18,fade=t=out:st={max(0, duration - 0.22):.3f}:d=0.18"
    elif transition_style == "Zoom/Pan":
        vf = f"scale={WIDTH*2}:-1,zoompan=z='min(zoom+0.0008,1.08)':d={max(1, int(duration*FPS))}:s={WIDTH}x{HEIGHT}:fps={FPS},setsar=1"
    elif transition_style == "Slide":
        vf = f"scale={int(WIDTH*1.12)}:{int(HEIGHT*1.12)}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT}:x='(iw-ow)*min(t/{max(duration, 0.1):.3f}\\,1)':y=(ih-oh)/2,setsar=1,fps={FPS}"
    _run(["ffmpeg", "-y", "-loop", "1", "-i", image_path, "-t", f"{duration:.3f}", "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", output_path], "image background clip")
    return output_path


def _video_background(video_path: str, output_path: str, duration: float) -> str:
    _run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", video_path, "-t", f"{duration:.3f}", "-vf", _scale_crop_filter(), "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", output_path], "video background")
    return output_path


def _normalise_bg_item(item):
    if isinstance(item, str):
        return {"path": item}
    if isinstance(item, dict):
        path = item.get("path") or item.get("image_path") or item.get("file")
        return {"path": path, "start": item.get("start"), "end": item.get("end")}
    return {"path": None}


def _prepare_background(
    tmp: Path,
    duration: float,
    background_mode: str,
    bg_video: Optional[str],
    generated_backgrounds=None,
    gradient_color_a: str = "#161629",
    gradient_color_b: str = "#ff3b7f",
    transition_style: str = "Cut",
) -> str:
    bg_dir = tmp / "background"
    bg_dir.mkdir(parents=True, exist_ok=True)
    fallback = create_gradient_background(bg_dir / "fallback.png", gradient_color_a, gradient_color_b)
    mode = background_mode or "Solid/Gradient"
    if mode in {"Asset Video", "Upload Video"} and bg_video and Path(str(bg_video)).exists():
        return _video_background(str(bg_video), str(bg_dir / "base.mp4"), duration)

    if mode == "AI Scene Images" and generated_backgrounds:
        items = [_normalise_bg_item(x) for x in generated_backgrounds]
        clips = []
        cursor = 0.0
        previous = fallback
        for i, item in enumerate(items):
            image = item.get("path") if item.get("path") and Path(str(item.get("path"))).exists() else previous
            previous = image or previous
            start = float(item.get("start") if item.get("start") is not None else cursor)
            end = float(item.get("end") if item.get("end") is not None else duration)
            if start > cursor + 0.03:
                gap_clip = bg_dir / f"gap_{i}.mp4"
                _image_clip(previous, str(gap_clip), start - cursor, transition_style)
                clips.append(gap_clip)
            clip_duration = max(0.1, min(duration, end) - max(0, start))
            clip = bg_dir / f"scene_{i}.mp4"
            _image_clip(image or fallback, str(clip), clip_duration, transition_style)
            clips.append(clip)
            cursor = max(cursor, end)
        if cursor < duration - 0.03:
            tail = bg_dir / "tail.mp4"
            _image_clip(previous, str(tail), duration - cursor, transition_style)
            clips.append(tail)
        concat = bg_dir / "concat.txt"
        concat.write_text("\n".join(f"file '{clip.as_posix()}'" for clip in clips), encoding="utf-8")
        out = bg_dir / "base.mp4"
        _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(out)], "scene background concat")
        return str(out)

    image = fallback
    if generated_backgrounds:
        first = _normalise_bg_item(generated_backgrounds[0] if isinstance(generated_backgrounds, list) else generated_backgrounds)
        if first.get("path") and Path(str(first.get("path"))).exists():
            image = str(first.get("path"))
    return _image_clip(image, str(bg_dir / "base.mp4"), duration, transition_style)


def _caption_y(position: str) -> int:
    return {"Upper third": 355, "Lower third": 1180, "Center": 720}.get(position or "Center", 720)


def _caption_y_expr(position: str, animation: str, start: float) -> str:
    y = _caption_y(position)
    if animation == "Bounce":
        return f"{y}+12*abs(sin(16*(t-{start:.3f})))"
    if animation == "Slide Up":
        return f"if(lt(t-{start:.3f}\\,0.25)\\,{y}+120-480*(t-{start:.3f})\\,{y})"
    if animation == "Pop":
        return f"if(lt(t-{start:.3f}\\,0.16)\\,{y}+20\\,{y})"
    return str(y)


def _compose_video(
    tmp: Path,
    background_video: str,
    narration_audio: str,
    timestamps: List[Dict[str, object]],
    output_path: str,
    title: str,
    caption_style: str,
    caption_position: str,
    caption_animation: str,
    show_title: bool,
    bg_music: Optional[str],
    char_overlay1: Optional[str],
    char_overlay2: Optional[str],
    bg_music_volume: float,
) -> str:
    inputs = ["-i", background_video]
    caption_paths = []
    for line in timestamps:
        cap = tmp / "captions" / f"caption_{int(line['index'])}.png"
        create_caption_image(str(line.get("text", "")), str(cap), caption_style, caption_position, caption_animation)
        caption_paths.append(str(cap))
        inputs += ["-i", str(cap)]
    title_path = None
    if show_title:
        title_path = tmp / "title.png"
        create_title_image(title, str(title_path), caption_style)
        inputs += ["-i", str(title_path)]
    char_inputs = []
    for char in (char_overlay1, char_overlay2):
        if char and Path(str(char)).exists():
            inputs += ["-i", str(char)]
            char_inputs.append(str(char))
        else:
            char_inputs.append(None)
    audio_index = 1 + len(caption_paths) + (1 if title_path else 0) + sum(1 for c in char_inputs if c)
    inputs += ["-i", narration_audio]
    music_index = None
    if bg_music and Path(str(bg_music)).exists():
        music_index = audio_index + 1
        inputs += ["-stream_loop", "-1", "-i", str(bg_music)]

    filters = []
    current = "[0:v]"
    out_label = "v0"
    for i, line in enumerate(timestamps):
        inp = i + 1
        start = float(line.get("start", 0))
        end = float(line.get("end", start + 1))
        yexpr = _caption_y_expr(caption_position, caption_animation, start)
        label = f"v{i+1}"
        filters.append(f"{current}[{inp}:v]overlay=x=(W-w)/2:y='{yexpr}':enable='between(t\\,{start:.3f}\\,{end:.3f})'[{label}]")
        current = f"[{label}]"
        out_label = label
    next_input = 1 + len(caption_paths)
    if title_path:
        label = f"vtitle"
        filters.append(f"{current}[{next_input}:v]overlay=x=(W-w)/2:y=130:enable='between(t\\,0\\,3.8)'[{label}]")
        current = f"[{label}]"
        out_label = label
        next_input += 1
    char_slot = 0
    for char in char_inputs:
        if not char:
            char_slot += 1
            continue
        scaled = f"char{char_slot}"
        filters.append(f"[{next_input}:v]scale=360:-1[{scaled}]")
        enables = []
        for line in timestamps:
            speaker = str(line.get("speaker", "")).upper()
            if (char_slot == 0 and ("CHARACTER1" in speaker or speaker.endswith("1") or "SPEAKER1" in speaker)) or (char_slot == 1 and ("CHARACTER2" in speaker or speaker.endswith("2") or "SPEAKER2" in speaker)):
                enables.append(f"between(t\\,{float(line['start']):.3f}\\,{float(line['end']):.3f})")
        enable = "+".join(enables) if enables else "0"
        x = "60" if char_slot == 0 else "W-w-60"
        label = f"vchar{char_slot}"
        filters.append(f"{current}[{scaled}]overlay=x={x}:y=H-h-90:enable='{enable}'[{label}]")
        current = f"[{label}]"
        out_label = label
        next_input += 1
        char_slot += 1

    if music_index is not None:
        filters.append(f"[{audio_index}:a]aresample=44100,volume=1.0[narr];[{music_index}:a]aresample=44100,volume={bg_music_volume}[music];[narr][music]amix=inputs=2:duration=first:dropout_transition=2[aout]")
    else:
        filters.append(f"[{audio_index}:a]aresample=44100[aout]")
    filter_complex = ";".join(filters)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filter_complex, "-map", f"[{out_label}]", "-map", "[aout]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", "-movflags", "+faststart", output_path]
    _run(cmd, "final FFmpeg compose")
    return output_path


def _default_dialogues(custom_script: str) -> List[Dict[str, object]]:
    lines = parse_custom_script(custom_script)
    if lines:
        return lines
    return [{"speaker": "NARRATOR", "text": "Add a script to generate your free AI reel.", "emotion": "neutral", "index": 0}]


def _align_generated_backgrounds(generated_backgrounds, timestamps: List[Dict[str, object]]):
    if not generated_backgrounds:
        return generated_backgrounds
    if not isinstance(generated_backgrounds, list):
        generated_backgrounds = [generated_backgrounds]
    aligned = []
    for i, item in enumerate(generated_backgrounds):
        if isinstance(item, str):
            idxs = [min(i, len(timestamps) - 1)] if timestamps else []
            path = item
            base = {"path": path}
        elif isinstance(item, dict):
            base = dict(item)
            path = base.get("path") or base.get("image_path") or base.get("file")
            base["path"] = path
            idxs = base.get("source_indices") or base.get("line_indices") or base.get("indices")
            if idxs is None and "index" in base:
                idxs = [base.get("index")]
            if idxs is None:
                idxs = [min(i, len(timestamps) - 1)] if timestamps else []
        else:
            continue
        if base.get("start") is None or base.get("end") is None:
            valid = []
            for idx in idxs or []:
                try:
                    valid.append(timestamps[int(idx)])
                except Exception:
                    pass
            if valid:
                base["start"] = min(float(v.get("start", 0)) for v in valid)
                base["end"] = max(float(v.get("end", base["start"] + 1)) for v in valid)
        aligned.append(base)
    return aligned


def generate_brainrot_video(
    title: str,
    dialogues: Sequence[Dict[str, object]],
    voice_narrator: str = "Narrator - TikTok English (free)",
    voice1: str = "Jessie - TikTok English (free)",
    voice2: str = "Guy - TikTok English (free)",
    bg_video: Optional[str] = None,
    bg_music: Optional[str] = None,
    char_overlay1: Optional[str] = None,
    char_overlay2: Optional[str] = None,
    caption_style: str = "Classic",
    background_mode: str = "Solid/Gradient",
    generated_backgrounds=None,
    caption_position: str = "Center",
    caption_animation: str = "None",
    show_title: bool = True,
    transition_style: str = "Cut",
    bg_music_volume: float = 0.16,
    voice_volume: float = 1.0,
    gradient_color_a: str = "#161629",
    gradient_color_b: str = "#ff3b7f",
    output_path: Optional[str] = None,
    cleanup: bool = True,
) -> str:
    tmp_path = Path(tempfile.mkdtemp(prefix="brainrot_render_", dir="/tmp"))
    try:
        output_path = output_path or str(Path("outputs/videos") / f"reel_{uuid.uuid4().hex[:10]}.mp4")
        lines = [dict(d) for d in dialogues] or _default_dialogues("")
        narration, timestamps, duration = _prepare_audio(lines, tmp_path, voice_narrator, voice1, voice2, voice_volume)
        aligned_backgrounds = _align_generated_backgrounds(generated_backgrounds, timestamps) if background_mode == "AI Scene Images" else generated_backgrounds
        background = _prepare_background(tmp_path, duration, background_mode, bg_video, aligned_backgrounds, gradient_color_a, gradient_color_b, transition_style)
        return _compose_video(tmp_path, background, narration, timestamps, output_path, title, caption_style, caption_position, caption_animation, show_title, bg_music, char_overlay1, char_overlay2, bg_music_volume)
    finally:
        if cleanup:
            shutil.rmtree(tmp_path, ignore_errors=True)


def generate_video_simple(
    title: str,
    script: str,
    voice_narrator: str = "Narrator - TikTok English (free)",
    bg_video: Optional[str] = None,
    bg_music: Optional[str] = None,
    caption_style: str = "Classic",
    **kwargs,
) -> str:
    return generate_brainrot_video(title, _default_dialogues(script), voice_narrator=voice_narrator, bg_video=bg_video, bg_music=bg_music, caption_style=caption_style, **kwargs)


def generate_video(
    title: str,
    custom_script: str,
    voice_narrator: str = "Narrator - TikTok English (free)",
    voice1: str = "Jessie - TikTok English (free)",
    voice2: str = "Guy - TikTok English (free)",
    bg_video: Optional[str] = None,
    bg_music: Optional[str] = None,
    char_overlay1: Optional[str] = None,
    char_overlay2: Optional[str] = None,
    caption_style: str = "Classic",
    background_mode: str = "Solid/Gradient",
    generated_backgrounds=None,
    caption_position: str = "Center",
    caption_animation: str = "None",
    show_title: bool = True,
    transition_style: str = "Cut",
    bg_music_volume: float = 0.16,
    voice_volume: float = 1.0,
    gradient_color_a: str = "#161629",
    gradient_color_b: str = "#ff3b7f",
    **kwargs,
) -> str:
    return generate_brainrot_video(
        title,
        _default_dialogues(custom_script),
        voice_narrator=voice_narrator,
        voice1=voice1,
        voice2=voice2,
        bg_video=bg_video,
        bg_music=bg_music,
        char_overlay1=char_overlay1,
        char_overlay2=char_overlay2,
        caption_style=caption_style,
        background_mode=background_mode,
        generated_backgrounds=generated_backgrounds,
        caption_position=caption_position,
        caption_animation=caption_animation,
        show_title=show_title,
        transition_style=transition_style,
        bg_music_volume=bg_music_volume,
        voice_volume=voice_volume,
        gradient_color_a=gradient_color_a,
        gradient_color_b=gradient_color_b,
    )
