import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from emotion_tts import generate_emotion_tts
from backgrounds import dimensions_for_aspect_ratio

CAPTION_STYLES = [
    "Classic", "Modern-Dark", "Yellow-Pop", "TikTok-Blast", "Karaoke-Green", "Minimal-Shadow",
    "Gradient-Pop", "Bold-Keywords", "Word-Highlight"
]


def split_text_into_segments(text, max_chars=70):
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    parts = re.split(r"(?<=[.!?।])\s+", text)
    segments = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(part) <= max_chars:
            segments.append(part)
            continue
        words = part.split()
        line = ""
        for word in words:
            trial = (line + " " + word).strip()
            if len(trial) <= max_chars or not line:
                line = trial
            else:
                segments.append(line)
                line = word
        if line:
            segments.append(line)
    return segments


def select_best_font_for_text(text, available_fonts_dir="assets/fonts"):
    master = os.path.join(available_fonts_dir, "NotoSans-Master-Bold.ttf")
    if os.path.exists(master):
        return master
    for name in ("NotoSansDevanagari-Bold.ttf", "NotoSans-Bold.ttf"):
        path = os.path.join(available_fonts_dir, name)
        if os.path.exists(path):
            return path
    for candidate in (
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        if os.path.exists(candidate):
            return candidate
    return None


def _load_font(font_path, size):
    from PIL import ImageFont
    candidates = [font_path, "assets/fonts/NotoSans-Master-Bold.ttf", "assets/fonts/NotoSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _text_bbox(draw, xy, text, font, stroke_width=0):
    return draw.textbbox(xy, text, font=font, stroke_width=stroke_width)


def _wrap_text(draw, text, font, max_width, max_lines=4):
    words = (text or "").split()
    lines = []
    line = ""
    for word in words:
        trial = (line + " " + word).strip()
        if _text_bbox(draw, (0, 0), trial, font)[2] <= max_width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
            if len(lines) >= max_lines - 1:
                break
    if line and len(lines) < max_lines:
        lines.append(line)
    return lines or [""]


def create_title_image(title, font_path, output_path, width=1080, height=1920, style="Classic"):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _load_font(font_path, max(54, width // 18))
    lines = _wrap_text(draw, title, font, int(width * 0.78), max_lines=3)
    y = height * 0.16
    draw.rounded_rectangle((width * 0.08, y - 36, width * 0.92, y + len(lines) * (width // 14) + 42), radius=32, fill=(0, 0, 0, 118))
    for line in lines:
        bbox = _text_bbox(draw, (0, 0), line, font, stroke_width=3)
        x = (width - (bbox[2] - bbox[0])) / 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 220))
        y += max(64, width // 14)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)
    return output_path


def create_caption_image(text, font_path, output_path, width=1080, height=1920, caption_style="Classic", highlight_fraction=1.0, speaker=None):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    base_size = max(44, min(96, width // 15))
    if caption_style in {"TikTok-Blast", "Gradient-Pop"}:
        base_size = max(base_size, width // 13)
    font = _load_font(font_path, base_size)
    small_font = _load_font(font_path, max(24, width // 42))
    max_width = int(width * (0.84 if width < height else 0.72))
    lines = _wrap_text(draw, text, font, max_width, max_lines=4)
    line_height = int(base_size * 1.18)
    block_width = max((_text_bbox(draw, (0, 0), line, font, stroke_width=4)[2] for line in lines), default=max_width)
    block_height = len(lines) * line_height
    y = int(height * (0.69 if width <= height else 0.72))
    x0 = int((width - min(max_width, block_width + 70)) / 2)
    x1 = int(width - x0)
    pad_y = int(base_size * 0.35)

    panel_fill = None
    fill = (255, 255, 255, 255)
    stroke = (0, 0, 0, 230)
    stroke_width = 4
    if caption_style == "Modern-Dark":
        panel_fill = (0, 0, 0, 165)
    elif caption_style == "Yellow-Pop":
        fill = (255, 230, 0, 255)
        stroke_width = 5
    elif caption_style == "TikTok-Blast":
        panel_fill = (255, 0, 96, 135)
        fill = (255, 255, 255, 255)
        stroke = (0, 221, 255, 230)
    elif caption_style == "Karaoke-Green":
        fill = (171, 255, 64, 255)
        panel_fill = (0, 0, 0, 125)
    elif caption_style == "Minimal-Shadow":
        stroke = (0, 0, 0, 150)
        stroke_width = 2
    elif caption_style == "Gradient-Pop":
        panel_fill = (25, 7, 48, 172)
        fill = (255, 118, 219, 255)
        stroke = (40, 255, 244, 230)
        stroke_width = 3
    elif caption_style == "Bold-Keywords":
        panel_fill = (0, 0, 0, 118)
    elif caption_style == "Word-Highlight":
        panel_fill = (0, 0, 0, 150)
        fill = (235, 235, 235, 255)

    if panel_fill:
        draw.rounded_rectangle((x0 - 18, y - pad_y, x1 + 18, y + block_height + pad_y), radius=max(18, width // 45), fill=panel_fill)
    if speaker and speaker != "NARRATOR":
        draw.text((x0, y - pad_y - max(30, width // 35)), speaker, font=small_font, fill=(255, 255, 255, 210), stroke_width=2, stroke_fill=(0, 0, 0, 160))

    keyword_set = set()
    if caption_style == "Bold-Keywords":
        words = re.findall(r"[\w\u0900-\u097f]{5,}", text)
        keyword_set = set(words[:3])

    for line in lines:
        bbox = _text_bbox(draw, (0, 0), line, font, stroke_width=stroke_width)
        x = int((width - (bbox[2] - bbox[0])) / 2)
        if caption_style in {"Word-Highlight", "Bold-Keywords"}:
            words = line.split()
            cursor = x
            total_words = max(1, len((text or "").split()))
            highlight_count = max(1, int(total_words * max(0.0, min(1.0, highlight_fraction)))) if caption_style == "Word-Highlight" else 0
            seen_before = len(" ".join(" ".join(lines[:lines.index(line)]).split()).split()) if line in lines else 0
            for idx, word in enumerate(words):
                clean = re.sub(r"[^\w\u0900-\u097f]", "", word)
                color = fill
                if caption_style == "Word-Highlight" and seen_before + idx < highlight_count:
                    color = (255, 223, 0, 255)
                    wb = _text_bbox(draw, (cursor, y), word, font, stroke_width=stroke_width)
                    draw.rounded_rectangle((wb[0] - 8, wb[1], wb[2] + 8, wb[3] + 4), radius=10, fill=(255, 223, 0, 55))
                elif caption_style == "Bold-Keywords" and clean in keyword_set:
                    color = (255, 223, 0, 255)
                draw.text((cursor, y), word, font=font, fill=color, stroke_width=stroke_width, stroke_fill=stroke)
                cursor += _text_bbox(draw, (0, 0), word + " ", font, stroke_width=stroke_width)[2]
        else:
            draw.text((x, y), line, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke)
        y += line_height
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)
    return output_path


def generate_line_audio(text, voice, output_path, emotion="neutral"):
    return generate_emotion_tts(text, voice, output_path, emotion=emotion)


def _duration(path):
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path
    ], capture_output=True, text=True, check=False)
    try:
        return max(0.05, float(result.stdout.strip()))
    except Exception:
        return 1.5


def _run_ffmpeg(cmd, label="ffmpeg"):
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip()[-2000:]
        raise RuntimeError(f"{label} failed: {tail}")
    return result


def _pick_overlay(character_overlay, speaker):
    if not character_overlay:
        return None
    if isinstance(character_overlay, dict):
        return character_overlay.get(speaker) or character_overlay.get(speaker.upper()) or character_overlay.get("NARRATOR")
    if isinstance(character_overlay, (list, tuple)):
        return character_overlay[0] if character_overlay else None
    return character_overlay


def _make_segment(bg_path, bg_video_path, audio_path, caption_path, char_path, output_path, duration, width, height):
    cmd = ["ffmpeg", "-y"]
    if bg_path:
        cmd += ["-loop", "1", "-t", f"{duration:.3f}", "-i", bg_path]
    elif bg_video_path:
        cmd += ["-stream_loop", "-1", "-t", f"{duration:.3f}", "-i", bg_video_path]
    else:
        cmd += ["-f", "lavfi", "-t", f"{duration:.3f}", "-i", f"color=c=0x181818:s={width}x{height}:r=30"]
    cmd += ["-i", audio_path, "-i", caption_path]
    filter_parts = [f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1[bg]", "[bg][2:v]overlay=0:0[v0]"]
    last = "v0"
    if char_path and os.path.exists(char_path):
        cmd += ["-i", char_path]
        char_w = max(180, width // 4)
        filter_parts.append(f"[3:v]scale={char_w}:-1[char]")
        filter_parts.append(f"[{last}][char]overlay=W-w-{max(24,width//32)}:H-h-{max(28,height//26)}[v1]")
        last = "v1"
    cmd += [
        "-filter_complex", ";".join(filter_parts),
        "-map", f"[{last}]", "-map", "1:a", "-r", "30", "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", output_path
    ]
    _run_ffmpeg(cmd, "segment render")
    return output_path


def _concat_videos(segment_paths, output_path):
    list_path = os.path.join(os.path.dirname(output_path), "segments.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for path in segment_paths:
            escaped = path.replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", output_path]
    _run_ffmpeg(cmd, "video concat")
    return output_path


def _mix_music(video_path, music_path, output_path):
    if not music_path or not os.path.exists(music_path):
        shutil.copyfile(video_path, output_path)
        return output_path
    cmd = [
        "ffmpeg", "-y", "-i", video_path, "-stream_loop", "-1", "-i", music_path,
        "-filter_complex", "[1:a]volume=0.12[a1];[0:a][a1]amix=inputs=2:duration=first:dropout_transition=2[a]",
        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-shortest", output_path
    ]
    _run_ffmpeg(cmd, "music mix")
    return output_path


def generate_brainrot_video(dialogues, voice_assignments, title, bg_video_path, bg_music_path, font_path, output_path, character_overlay=None, progress_callback=None, caption_style="Classic", aspect_ratio="9:16", scene_background_paths=None, timing_data=None, use_whisper_sync=False, timing_status_callback=None):
    if not dialogues:
        raise ValueError("No dialogue/story scenes were provided")
    width, height = dimensions_for_aspect_ratio(aspect_ratio)
    font_path = font_path or select_best_font_for_text(" ".join(d.get("text", "") for d in dialogues))
    output_path = output_path or f"story_{uuid.uuid4().hex}.mp4"
    final_output = os.path.abspath(output_path)
    Path(final_output).parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="storyteller_") as tmp:
        audio_paths = []
        segment_paths = []
        total = len(dialogues)
        for idx, dialogue in enumerate(dialogues):
            if progress_callback:
                progress_callback(f"TTS/audio {idx + 1}/{total}: {dialogue.get('speaker', 'NARRATOR')}")
            voice = voice_assignments.get(dialogue.get("speaker", "NARRATOR"), next(iter(voice_assignments.values()), "en_us_001")) if voice_assignments else "en_us_001"
            audio_path = os.path.join(tmp, f"line_{idx:03d}.mp3")
            generate_line_audio(dialogue.get("text", ""), voice, audio_path, dialogue.get("emotion", "neutral"))
            audio_paths.append(audio_path)
        if timing_data is None:
            if progress_callback:
                progress_callback("Timing alignment")
            try:
                from timing import align_timings
                combined_audio = os.path.join(tmp, "combined_audio.mp3")
                audio_list = os.path.join(tmp, "audio_segments.txt")
                with open(audio_list, "w", encoding="utf-8") as f:
                    for path in audio_paths:
                        f.write(f"file '{path}'\n")
                _run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", audio_list, "-c", "copy", combined_audio], "audio concat")
                timing_data, timing_message = align_timings(audio_paths, dialogues, use_whisper=use_whisper_sync, combined_audio_path=combined_audio)
                if timing_status_callback:
                    timing_status_callback(timing_message)
            except Exception as exc:
                if timing_status_callback:
                    timing_status_callback(f"fallback timing used ({exc})")
                timing_data = None
        for idx, dialogue in enumerate(dialogues):
            if progress_callback:
                progress_callback(f"Caption/background render {idx + 1}/{total}")
            duration = timing_data[idx].get("duration", _duration(audio_paths[idx])) if timing_data and idx < len(timing_data) else _duration(audio_paths[idx])
            caption_path = os.path.join(tmp, f"caption_{idx:03d}.png")
            highlight = 1.0 if caption_style not in {"Word-Highlight", "Karaoke-Green"} else min(1.0, max(0.35, duration / max(duration, 1.0)))
            create_caption_image(dialogue.get("text", ""), font_path, caption_path, width=width, height=height, caption_style=caption_style, highlight_fraction=highlight, speaker=dialogue.get("speaker"))
            bg_path = scene_background_paths[idx] if scene_background_paths and idx < len(scene_background_paths) else None
            char_path = _pick_overlay(character_overlay, dialogue.get("speaker", "NARRATOR"))
            segment_path = os.path.join(tmp, f"segment_{idx:03d}.mp4")
            _make_segment(bg_path, bg_video_path, audio_paths[idx], caption_path, char_path, segment_path, duration, width, height)
            segment_paths.append(segment_path)
        if progress_callback:
            progress_callback("Final FFmpeg export")
        joined = os.path.join(tmp, "joined.mp4")
        _concat_videos(segment_paths, joined)
        mixed = os.path.join(tmp, "mixed.mp4")
        _mix_music(joined, bg_music_path, mixed)
        shutil.copyfile(mixed, final_output)
    return final_output


def generate_video(title=None, script=None, voice=None, bg_video_path=None, bg_music_path=None, font_path=None, character_image=None, output_path=None, **kwargs):
    dialogues = kwargs.get("dialogues")
    voice_assignments = kwargs.get("voice_assignments")
    video_title = kwargs.get("video_title") or title or "AI Story"
    character_overlay = kwargs.get("character_overlay", character_image)
    progress_callback = kwargs.get("progress_callback")
    caption_style = kwargs.get("caption_style", "Classic")
    aspect_ratio = kwargs.get("aspect_ratio", "9:16")
    scene_background_paths = kwargs.get("scene_background_paths")
    timing_data = kwargs.get("timing_data")
    use_whisper_sync = kwargs.get("use_whisper_sync", False)
    timing_status_callback = kwargs.get("timing_status_callback")
    if dialogues is None:
        from script_generator import parse_custom_script, assign_voices_to_characters
        from tiktok_tts import VOICES
        dialogues = parse_custom_script(script or "")
        voice_assignments = voice_assignments or assign_voices_to_characters(dialogues, VOICES)
    if voice and dialogues:
        voice_assignments = {d.get("speaker", "NARRATOR"): voice for d in dialogues}
    return generate_brainrot_video(
        dialogues, voice_assignments or {}, video_title, bg_video_path, bg_music_path, font_path, output_path,
        character_overlay=character_overlay, progress_callback=progress_callback, caption_style=caption_style,
        aspect_ratio=aspect_ratio, scene_background_paths=scene_background_paths, timing_data=timing_data,
        use_whisper_sync=use_whisper_sync, timing_status_callback=timing_status_callback
    )
