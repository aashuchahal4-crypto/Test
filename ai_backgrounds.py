import base64
import hashlib
import io
import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests
from PIL import Image, ImageDraw

CACHE_DIR = Path("outputs/ai_backgrounds/cache")
RUNTIME_DIR = Path("outputs/ai_backgrounds")


def safe_endpoint(endpoint_url: str | None = None) -> str:
    return (endpoint_url or os.getenv("AI_IMAGE_API_URL") or "").strip()


def cache_key(endpoint_url: str, prompt: str, negative_prompt: str, seed: int, guidance_scale: float, width: int, height: int) -> str:
    payload = json.dumps(
        {
            "endpoint": endpoint_url,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "seed": seed,
            "guidance_scale": guidance_scale,
            "width": width,
            "height": height,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _strip_data_uri(value: str) -> str:
    if value.startswith("data:image") and "," in value:
        return value.split(",", 1)[1]
    return value


def _decode_base64_image(value: str) -> Image.Image:
    raw = base64.b64decode(_strip_data_uri(value), validate=False)
    return Image.open(io.BytesIO(raw)).convert("RGB")


def _image_from_json(data: Dict[str, object]) -> Image.Image:
    for key in ("image", "image_base64", "base64", "data"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return _decode_base64_image(value.strip())
    images = data.get("images")
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, str):
            return _decode_base64_image(first)
        if isinstance(first, dict):
            return _image_from_json(first)
    raise ValueError("AI endpoint JSON did not contain image/image_base64/base64/data/images")


def fit_vertical(image: Image.Image, size: Tuple[int, int] = (1080, 1920)) -> Image.Image:
    target_w, target_h = size
    image = image.convert("RGB")
    src_w, src_h = image.size
    scale = max(target_w / max(1, src_w), target_h / max(1, src_h))
    resized = image.resize((int(src_w * scale) + 1, int(src_h * scale) + 1), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - target_w) // 2)
    top = max(0, (resized.height - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def create_gradient_background(path: str | Path, color_a: str = "#161629", color_b: str = "#ff3b7f", size: Tuple[int, int] = (1080, 1920)) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    w, h = size
    def parse(c: str):
        c = (c or "#000000").lstrip("#")
        if len(c) != 6:
            c = "000000"
        return tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
    a, b = parse(color_a), parse(color_b)
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        wave = 0.08 * ((y // 90) % 2)
        rgb = tuple(max(0, min(255, int(a[i] * (1 - t) + b[i] * t + 255 * wave))) for i in range(3))
        draw.line([(0, y), (w, y)], fill=rgb)
    img.save(path, "PNG")
    return str(path)


def generate_ai_background(
    prompt: str,
    negative_prompt: str = "text, watermark, logo, captions, blurry, low quality, distorted faces",
    endpoint_url: str | None = None,
    seed: int = -1,
    guidance_scale: float = 7.5,
    width: int = 1024,
    height: int = 1024,
    timeout: int = 90,
    output_dir: str | Path = RUNTIME_DIR,
    use_cache: bool = True,
) -> Tuple[Optional[str], str]:
    endpoint = safe_endpoint(endpoint_url)
    if not endpoint:
        return None, "No AI image endpoint configured; using fallback background."

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    key = cache_key(endpoint, prompt, negative_prompt, int(seed), float(guidance_scale), int(width), int(height))
    cached = CACHE_DIR / f"{key}.png"
    if use_cache and cached.exists():
        return str(cached), f"Reused cached AI background {cached.name}."

    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "seed": int(seed),
        "guidance_scale": float(guidance_scale),
        "width": int(width),
        "height": int(height),
    }
    try:
        response = requests.post(endpoint, json=payload, timeout=timeout)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "image/" in content_type:
            image = Image.open(io.BytesIO(response.content)).convert("RGB")
        else:
            image = _image_from_json(response.json())
        fitted = fit_vertical(image)
        fitted.save(cached, "PNG")
        return str(cached), f"Generated AI background via external endpoint and cached {cached.name}."
    except Exception as exc:
        return None, f"AI background request failed: {exc}. Using fallback background."
