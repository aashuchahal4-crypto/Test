import math
import os
import random
import re
from pathlib import Path

ASPECT_DIMENSIONS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}
STOPWORDS = {"the","and","but","with","that","this","from","into","your","their","there","then","than","when","where","what","were","was","are","hai","aur","for","you","she","his","her","they","them","who"}
PALETTES = [
    ((32, 11, 69), (255, 80, 164)),
    ((9, 30, 77), (0, 212, 255)),
    ((16, 74, 54), (246, 211, 101)),
    ((60, 16, 83), (255, 151, 112)),
    ((18, 18, 18), (116, 235, 213)),
]


def dimensions_for_aspect_ratio(aspect_ratio):
    return ASPECT_DIMENSIONS.get(aspect_ratio, ASPECT_DIMENSIONS["9:16"])


def scene_keywords(text, limit=5):
    words = re.findall(r"[\w\u0900-\u097f]{3,}", text.lower())
    out = []
    for word in words:
        if word not in STOPWORDS and word not in out:
            out.append(word)
        if len(out) >= limit:
            break
    return out or ["story", "scene"]


def _font(size, bold=True):
    from PIL import ImageFont
    candidates = [
        "assets/fonts/NotoSans-Master-Bold.ttf",
        "assets/fonts/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def _wrap(draw, text, font, max_width):
    words = text.split()
    lines = []
    line = ""
    for word in words:
        trial = (line + " " + word).strip()
        if draw.textbbox((0, 0), trial, font=font)[2] <= max_width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines[:4]


def generate_visual_card(text, output_path, aspect_ratio="9:16", index=0, title="AI Story"):
    from PIL import Image, ImageDraw, ImageFilter
    width, height = dimensions_for_aspect_ratio(aspect_ratio)
    c1, c2 = PALETTES[index % len(PALETTES)]
    img = Image.new("RGB", (width, height), c1)
    pixels = img.load()
    for y in range(height):
        t = y / max(1, height - 1)
        for x in range(width):
            wave = (math.sin((x / width * math.pi * 2) + index) + 1) * 0.04
            mix = min(1.0, max(0.0, t + wave))
            pixels[x, y] = tuple(int(c1[i] * (1 - mix) + c2[i] * mix) for i in range(3))
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    random.seed(index + len(text))
    for _ in range(18):
        r = random.randint(width // 18, width // 5)
        x = random.randint(-r, width)
        y = random.randint(-r, height)
        color = (255, 255, 255, random.randint(18, 48))
        od.ellipse((x, y, x + r, y + r), fill=color)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=max(6, width // 160)))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    d = ImageDraw.Draw(img)
    title_font = _font(max(34, width // 34))
    text_font = _font(max(46, width // 24))
    chip_font = _font(max(26, width // 48))
    d.rounded_rectangle((width * 0.06, height * 0.07, width * 0.94, height * 0.20), radius=32, fill=(0, 0, 0, 80), outline=(255, 255, 255, 70), width=2)
    d.text((width * 0.09, height * 0.095), title[:50], font=title_font, fill=(255, 255, 255, 235))
    keywords = scene_keywords(text)
    chip_x = width * 0.09
    chip_y = height * 0.23
    for kw in keywords:
        label = kw.upper()
        bbox = d.textbbox((0, 0), label, font=chip_font)
        chip_w = bbox[2] - bbox[0] + 34
        d.rounded_rectangle((chip_x, chip_y, chip_x + chip_w, chip_y + 52), radius=26, fill=(255, 255, 255, 46), outline=(255, 255, 255, 95), width=2)
        d.text((chip_x + 17, chip_y + 9), label, font=chip_font, fill=(255, 255, 255, 230))
        chip_x += chip_w + 14
        if chip_x > width * 0.78:
            chip_x = width * 0.09
            chip_y += 64
    lines = _wrap(d, text, text_font, int(width * 0.78))
    line_h = max(58, int(width // 17))
    block_h = len(lines) * line_h
    y = height * 0.47 - block_h / 2
    for line in lines:
        bbox = d.textbbox((0, 0), line, font=text_font, stroke_width=3)
        x = (width - (bbox[2] - bbox[0])) / 2
        d.text((x, y), line, font=text_font, fill=(255, 255, 255, 245), stroke_width=4, stroke_fill=(0, 0, 0, 150))
        y += line_h
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(output_path, quality=95)
    return output_path


def generate_scene_backgrounds(dialogues, output_dir, aspect_ratio="9:16", title="AI Story"):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    paths = []
    for idx, d in enumerate(dialogues):
        path = os.path.join(output_dir, f"scene_{idx:03d}.png")
        generate_visual_card(d.get("text", ""), path, aspect_ratio=aspect_ratio, index=idx, title=title)
        paths.append(path)
    return paths
