from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

from script_generator import DialogueLine

BACKGROUND_KEYWORDS = {
    "rain": ["rain", "storm", "thunder", "umbrella", "wet", "cloud", "lightning"],
    "city": ["city", "street", "traffic", "building", "downtown", "skyline", "road", "car"],
    "park": ["park", "tree", "grass", "garden", "field", "playground", "forest", "woods"],
    "room": ["room", "home", "house", "bed", "sofa", "kitchen", "door", "window"],
    "classroom": ["class", "school", "teacher", "student", "desk", "board", "homework", "exam"],
    "space": ["space", "moon", "planet", "alien", "star", "galaxy", "rocket"],
    "beach": ["beach", "ocean", "sea", "wave", "sand", "island"],
}

ACTION_KEYWORDS = {
    "run": ["run", "ran", "running", "chase", "escape", "sprint", "rush"],
    "walk": ["walk", "walking", "went", "go", "travel", "follow"],
    "jump": ["jump", "leap", "shocked", "surprised", "scared", "scream", "boom"],
    "sit": ["sit", "sat", "chair", "rest", "desk", "classroom", "wait"],
    "point": ["point", "look", "show", "there", "why", "what", "door", "sky", "green"],
    "shake": ["angry", "mad", "rage", "fight", "argue", "furious"],
    "slouch": ["sad", "cry", "tired", "lonely", "sorry", "slow"],
    "bounce": ["happy", "excited", "laugh", "dance", "win", "secret"],
}

CAMERA_KEYWORDS = {
    "close": ["whisper", "secret", "realized", "face", "eyes"],
    "wide": ["city", "park", "classroom", "space", "everyone", "suddenly"],
    "shake": ["boom", "thunder", "angry", "run", "chase", "shocked"],
}

@dataclass
class SceneSegment:
    line: DialogueLine
    start: float
    end: float
    background: str
    action: str
    camera: str


def _contains(text: str, words: Iterable[str]) -> bool:
    text = text.lower()
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


def detect_background(text: str, emotion: str = "neutral", previous: str = "city") -> str:
    combined = f"{text} {emotion}".lower()
    for background, words in BACKGROUND_KEYWORDS.items():
        if _contains(combined, words):
            if background == "forest":
                return "park"
            return background
    return previous or "city"


def detect_action(text: str, emotion: str = "neutral") -> str:
    combined = f"{text} {emotion}".lower()
    if emotion in {"shocked", "surprised", "scared"}:
        return "jump"
    if emotion in {"sad", "tired"}:
        return "slouch"
    if emotion in {"angry", "furious"}:
        return "shake"
    if emotion in {"happy", "excited"}:
        return "bounce"
    if emotion in {"calm", "neutral"} and not any(_contains(combined, words) for words in ACTION_KEYWORDS.values()):
        return "idle"
    for action, words in ACTION_KEYWORDS.items():
        if _contains(combined, words):
            return action
    return "idle"


def detect_camera(text: str, emotion: str = "neutral") -> str:
    combined = f"{text} {emotion}".lower()
    if emotion in {"shocked", "angry"}:
        return "shake"
    for camera, words in CAMERA_KEYWORDS.items():
        if _contains(combined, words):
            return camera
    return "medium"


def make_segments(lines: list[DialogueLine], timings: list[tuple[float, float]]) -> list[SceneSegment]:
    segments: list[SceneSegment] = []
    previous = "city"
    for line, timing in zip(lines, timings):
        bg = detect_background(line.text, line.emotion, previous)
        previous = bg
        segments.append(SceneSegment(line, timing[0], timing[1], bg, detect_action(line.text, line.emotion), detect_camera(line.text, line.emotion)))
    return segments


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _gradient(draw: ImageDraw.ImageDraw, w: int, h: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> None:
    for y in range(h):
        t = y / max(1, h - 1)
        color = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        draw.line([(0, y), (w, y)], fill=color)


def draw_background(draw: ImageDraw.ImageDraw, w: int, h: int, bg: str, t: float) -> None:
    if bg == "rain":
        _gradient(draw, w, h, (45, 58, 86), (15, 19, 34))
        draw.rectangle([0, int(h * .72), w, h], fill=(34, 42, 50))
        for i in range(48):
            x = (i * 73 + int(t * 260)) % (w + 80) - 40
            y = (i * 41 + int(t * 420)) % h
            draw.line([(x, y), (x - 16, y + 36)], fill=(155, 190, 235), width=2)
        if int(t * 2) % 5 == 0:
            draw.line([(w * .72, 30), (w * .66, 95), (w * .71, 92), (w * .62, 170)], fill=(255, 244, 155), width=4)
    elif bg == "park":
        _gradient(draw, w, h, (126, 198, 255), (207, 236, 255))
        draw.rectangle([0, int(h * .66), w, h], fill=(75, 170, 83))
        for x in range(-40, w, max(90, w // 7)):
            draw.rectangle([x + 34, int(h * .48), x + 48, int(h * .68)], fill=(95, 58, 35))
            draw.ellipse([x, int(h * .35), x + 86, int(h * .55)], fill=(45, 142, 63))
    elif bg == "room":
        _gradient(draw, w, h, (236, 207, 171), (220, 178, 132))
        draw.rectangle([0, int(h * .70), w, h], fill=(132, 94, 69))
        draw.rectangle([int(w * .68), int(h * .28), int(w * .90), int(h * .62)], fill=(120, 76, 45), outline=(80, 45, 28), width=4)
        draw.rectangle([int(w * .10), int(h * .18), int(w * .36), int(h * .42)], fill=(134, 202, 245), outline=(250, 250, 250), width=5)
    elif bg == "classroom":
        _gradient(draw, w, h, (244, 224, 183), (226, 202, 155))
        draw.rectangle([int(w * .12), int(h * .12), int(w * .88), int(h * .42)], fill=(39, 100, 72), outline=(93, 54, 24), width=8)
        draw.text((int(w * .20), int(h * .22)), "TODAY'S STORY", fill=(230, 245, 230), font=_font(max(18, w // 38), True))
        for x in (int(w*.25), int(w*.55)):
            draw.rectangle([x, int(h*.67), x+int(w*.16), int(h*.73)], fill=(145, 91, 55))
            draw.line([(x+15, int(h*.73)), (x+5, int(h*.88))], fill=(83, 55, 36), width=4)
            draw.line([(x+int(w*.16)-15, int(h*.73)), (x+int(w*.16)-5, int(h*.88))], fill=(83, 55, 36), width=4)
    elif bg == "space":
        _gradient(draw, w, h, (8, 8, 30), (20, 5, 44))
        for i in range(80):
            x = (i * 137) % w
            y = (i * 71) % int(h * .72)
            r = 1 + (i % 3 == 0)
            draw.ellipse([x-r, y-r, x+r, y+r], fill=(255, 255, 220))
        draw.ellipse([int(w*.70), int(h*.16), int(w*.88), int(h*.34)], fill=(124, 94, 210))
        draw.rectangle([0, int(h*.76), w, h], fill=(42, 42, 62))
    elif bg == "beach":
        _gradient(draw, w, h, (90, 190, 245), (210, 240, 255))
        draw.rectangle([0, int(h*.58), w, int(h*.76)], fill=(48, 145, 202))
        draw.rectangle([0, int(h*.76), w, h], fill=(232, 203, 135))
        for x in range(0, w, 90):
            draw.arc([x, int(h*.61), x+90, int(h*.70)], 0, 180, fill=(240, 252, 255), width=3)
    else:
        _gradient(draw, w, h, (92, 163, 230), (182, 218, 247))
        draw.rectangle([0, int(h * .68), w, h], fill=(54, 65, 82))
        for i, x in enumerate(range(-20, w, max(70, w // 10))):
            height = int(h * (.22 + .22 * ((i % 4) / 3)))
            draw.rectangle([x, int(h*.68)-height, x + int(w*.08), int(h*.68)], fill=(48, 58, 82), outline=(35, 42, 60))
            for wy in range(int(h*.68)-height+15, int(h*.68)-10, 28):
                draw.rectangle([x+12, wy, x+24, wy+12], fill=(255, 218, 105))


def character_positions(count: int, w: int, h: int) -> list[tuple[int, int]]:
    if count <= 1:
        return [(w // 2, int(h * .70))]
    margin = int(w * .18)
    span = w - margin * 2
    return [(margin + int(span * i / max(1, count - 1)), int(h * .70)) for i in range(count)]


def draw_stickman(draw: ImageDraw.ImageDraw, x: int, ground_y: int, scale: float, action: str, active: bool, color: tuple[int, int, int], phase: float, name: str) -> None:
    shake = math.sin(phase * 28) * 7 if action == "shake" and active else 0
    bounce = abs(math.sin(phase * 6)) * 16 if action in {"bounce", "jump"} and active else 0
    walk = math.sin(phase * 8) if action in {"walk", "run"} else 0
    if action == "run":
        walk = math.sin(phase * 13) * 1.4
    slouch = 12 * scale if action == "slouch" else 0
    sit = action == "sit"
    sx = x + shake
    hip_y = ground_y - (44 * scale if sit else 72 * scale) - bounce
    head_r = int(22 * scale)
    head_y = hip_y - int(76 * scale) + slouch
    body_y1 = head_y + head_r
    body_y2 = hip_y
    width = max(3, int(5 * scale))
    outline = (255, 238, 96) if active else color
    draw.ellipse([sx-head_r, head_y-head_r, sx+head_r, head_y+head_r], outline=outline, width=width, fill=(248, 224, 184) if active else None)
    draw.line([(sx, body_y1), (sx, body_y2)], fill=outline, width=width)
    arm_y = body_y1 + int(22 * scale)
    if action == "point" and active:
        draw.line([(sx, arm_y), (sx + 48 * scale, arm_y - 28 * scale)], fill=outline, width=width)
        draw.line([(sx, arm_y), (sx - 30 * scale, arm_y + 24 * scale)], fill=outline, width=width)
    elif action == "slouch":
        draw.line([(sx, arm_y), (sx + 32 * scale, arm_y + 34 * scale)], fill=outline, width=width)
        draw.line([(sx, arm_y), (sx - 32 * scale, arm_y + 34 * scale)], fill=outline, width=width)
    else:
        draw.line([(sx, arm_y), (sx + (32 + 16*walk) * scale, arm_y + (18 - 14*walk) * scale)], fill=outline, width=width)
        draw.line([(sx, arm_y), (sx - (32 + 16*walk) * scale, arm_y + (18 + 14*walk) * scale)], fill=outline, width=width)
    if sit:
        draw.line([(sx, body_y2), (sx + 42*scale, ground_y - 28*scale)], fill=outline, width=width)
        draw.line([(sx, body_y2), (sx - 42*scale, ground_y - 28*scale)], fill=outline, width=width)
        draw.line([(sx + 42*scale, ground_y - 28*scale), (sx + 52*scale, ground_y)], fill=outline, width=width)
        draw.line([(sx - 42*scale, ground_y - 28*scale), (sx - 52*scale, ground_y)], fill=outline, width=width)
    else:
        draw.line([(sx, body_y2), (sx + (30 + 18*walk)*scale, ground_y)], fill=outline, width=width)
        draw.line([(sx, body_y2), (sx - (30 + 18*walk)*scale, ground_y)], fill=outline, width=width)
    if active:
        draw.arc([sx-head_r*.45, head_y-head_r*.05, sx+head_r*.45, head_y+head_r*.55], 0, 180 if action == "slouch" else -180, fill=(50, 50, 50), width=max(2, int(2*scale)))
        bubble = [sx - 78*scale, head_y - 82*scale, sx + 78*scale, head_y - 44*scale]
        draw.rounded_rectangle(bubble, radius=int(16*scale), fill=(255,255,255), outline=(25,25,25), width=2)
        draw.text((bubble[0]+10, bubble[1]+8), "speaking", fill=(20,20,20), font=_font(max(12, int(14*scale)), True))
    label_font = _font(max(12, int(17*scale)), True)
    label = name[:14]
    bbox = draw.textbbox((0, 0), label, font=label_font)
    draw.rounded_rectangle([sx - (bbox[2]-bbox[0])/2 - 8, ground_y + 8, sx + (bbox[2]-bbox[0])/2 + 8, ground_y + 32], radius=8, fill=(0,0,0,135))
    draw.text((sx - (bbox[2]-bbox[0])/2, ground_y + 10), label, fill=(255,255,255), font=label_font)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width or not current:
            current = test
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:3]


def draw_caption(draw: ImageDraw.ImageDraw, w: int, h: int, line: DialogueLine, style: str) -> None:
    font = _font(max(24, w // 28), True)
    speaker_font = _font(max(16, w // 48), True)
    lines = wrap_text(draw, line.text, font, int(w * .82))
    line_h = max(32, int(w // 24))
    box_h = line_h * len(lines) + 58
    y = int(h * .82) - box_h // 2
    if style.lower().startswith("top"):
        y = int(h * .09)
    fill = (0, 0, 0, 178)
    outline = (255, 238, 96) if not line.is_narrator else (130, 220, 255)
    draw.rounded_rectangle([int(w*.07), y, int(w*.93), y + box_h], radius=22, fill=fill, outline=outline, width=3)
    speaker = "STORYTELLER" if line.is_narrator else line.speaker.upper()
    draw.text((int(w*.10), y + 12), speaker, fill=outline, font=speaker_font)
    yy = y + 36
    for txt in lines:
        bbox = draw.textbbox((0, 0), txt, font=font)
        draw.text(((w - (bbox[2]-bbox[0])) / 2, yy), txt, fill=(255, 255, 255), font=font, stroke_width=2, stroke_fill=(0,0,0))
        yy += line_h


def draw_title(draw: ImageDraw.ImageDraw, w: int, title: str) -> None:
    if not title:
        return
    font = _font(max(24, w // 30), True)
    text = title[:70]
    bbox = draw.textbbox((0, 0), text, font=font)
    x = (w - (bbox[2] - bbox[0])) / 2
    y = 18
    draw.rounded_rectangle([x-18, y-8, x+(bbox[2]-bbox[0])+18, y+(bbox[3]-bbox[1])+16], radius=16, fill=(0,0,0,145))
    draw.text((x, y), text, font=font, fill=(255,255,255), stroke_width=2, stroke_fill=(0,0,0))


def render_frame(w: int, h: int, segment: SceneSegment, all_speakers: list[str], title: str, caption_style: str, t: float) -> Image.Image:
    img = Image.new("RGB", (w, h), (20, 20, 30))
    draw = ImageDraw.Draw(img, "RGBA")
    dx = int(math.sin(t * 15) * 5) if segment.camera == "shake" else 0
    draw_background(draw, w, h, segment.background, t)
    scale = 1.0
    if segment.camera == "close":
        scale = 1.16
    elif segment.camera == "wide":
        scale = .86
    speakers = all_speakers or ["Hero"]
    positions = character_positions(len(speakers), w, h)
    palette = [(24,24,28), (25,64,130), (80,32,120), (120,55,24), (30,95,70)]
    active = segment.line.speaker if not segment.line.is_narrator else (speakers[0] if speakers else "Hero")
    for i, speaker in enumerate(speakers):
        x, y = positions[i]
        draw_stickman(draw, x + dx, y, scale, segment.action if speaker == active else "idle", speaker == active, palette[i % len(palette)], t + i * .37, speaker)
    draw_title(draw, w, title)
    draw_caption(draw, w, h, segment.line, caption_style)
    return img


def render_stickman_video(lines: list[DialogueLine], timings: list[tuple[float, float]], output_path: str, title: str = "", aspect_ratio: str = "9:16", caption_style: str = "Bottom captions", fps: int = 12) -> str:
    if aspect_ratio == "16:9":
        w, h = 1280, 720
    elif aspect_ratio == "1:1":
        w, h = 900, 900
    else:
        w, h = 720, 1280
    total = max((end for _, end in timings), default=2.0)
    segments = make_segments(lines, timings)
    if not segments:
        from script_generator import DialogueLine
        segments = [SceneSegment(DialogueLine("NARRATOR", "Your story begins here.", "neutral"), 0, total, "city", "idle", "medium")]
    speakers = []
    for line in lines:
        if not line.is_narrator and line.speaker not in speakers:
            speakers.append(line.speaker)
    if not speakers:
        speakers = ["Hero"]
    frame_dir = tempfile.mkdtemp(prefix="stickman_frames_")
    try:
        frame_count = max(1, int(math.ceil(total * fps)))
        seg_index = 0
        for n in range(frame_count):
            t = n / fps
            while seg_index < len(segments) - 1 and t >= segments[seg_index].end:
                seg_index += 1
            frame = render_frame(w, h, segments[seg_index], speakers, title, caption_style, t)
            frame.save(os.path.join(frame_dir, f"frame_{n:05d}.png"), optimize=True)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(frame_dir, "frame_%05d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps), "-t", f"{total:.3f}", output_path,
        ], check=True)
    finally:
        shutil.rmtree(frame_dir, ignore_errors=True)
    return output_path
