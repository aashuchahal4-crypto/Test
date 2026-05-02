#!/usr/bin/env python3
"""Provider-based scene image generation with template fallback."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
import struct
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
STORAGE = ROOT / "storage"
GENERATED = STORAGE / "assets" / "generated"
WIDTH = int(os.environ.get("IMAGE_WIDTH", "720"))
HEIGHT = int(os.environ.get("IMAGE_HEIGHT", "1280"))

IMAGE_ENGINES = [
    {
        "id": "pollinations",
        "name": "Pollinations",
        "label": "Pollinations (fast)",
        "kind": "cloud",
        "requires": [],
        "description": "Fast hosted image generation without an app-side API key.",
    },
    {
        "id": "cloudflare",
        "name": "Cloudflare AI",
        "label": "Cloudflare AI (stable)",
        "kind": "cloud",
        "requires": ["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"],
        "description": "Stable Workers AI image generation when Cloudflare credentials are configured.",
    },
    {
        "id": "replicate",
        "name": "Replicate",
        "label": "Replicate (multi-model)",
        "kind": "cloud",
        "requires": ["REPLICATE_API_TOKEN"],
        "description": "Replicate-hosted image models. Set REPLICATE_MODEL to override the default model.",
    },
    {
        "id": "puter",
        "name": "Puter.js",
        "label": "Puter.js (frontend fallback)",
        "kind": "frontend",
        "requires": [],
        "description": "Frontend-only fallback option; backend rendering safely falls back to templates.",
    },
    {
        "id": "templates",
        "name": "Templates",
        "label": "Templates (always safe)",
        "kind": "local-template",
        "requires": [],
        "description": "Offline generated visual templates. Always available.",
    },
]

DEFAULT_ENGINE = os.environ.get("IMAGE_ENGINE", "pollinations").strip().lower() or "pollinations"
CLOUDFLARE_MODEL = os.environ.get("CLOUDFLARE_IMAGE_MODEL", "@cf/bytedance/stable-diffusion-xl-lightning")
REPLICATE_MODEL = os.environ.get("REPLICATE_MODEL", "black-forest-labs/flux-schnell")


class ImageGenerationError(RuntimeError):
    pass


def _configured(required: list[str]) -> bool:
    return all(os.environ.get(name) for name in required)


def image_engines_status() -> dict[str, Any]:
    engines = []
    for engine in IMAGE_ENGINES:
        missing = [name for name in engine["requires"] if not os.environ.get(name)]
        available = not missing and engine["id"] != "puter"
        if engine["id"] == "puter":
            available = True
        engines.append({
            **engine,
            "available": available,
            "missing": missing,
            "selected": engine["id"] == DEFAULT_ENGINE,
        })
    return {"default": DEFAULT_ENGINE if _engine(DEFAULT_ENGINE) else "pollinations", "engines": engines}


def _engine(engine_id: str | None) -> dict[str, Any] | None:
    requested = (engine_id or DEFAULT_ENGINE or "pollinations").strip().lower()
    return next((engine for engine in IMAGE_ENGINES if engine["id"] == requested), None)


def _prompt(scene: Any, style: str) -> str:
    base = str(getattr(scene, "visual_prompt", "") or "cinematic video scene")
    scene_style = str(getattr(scene, "style", "") or style)
    camera = str(getattr(scene, "camera_movement", "slow_zoom_in") or "slow_zoom_in").replace("_", " ")
    return (
        f"{base}, {scene_style} style, vertical 9:16 video keyframe, {camera}, cinematic lighting, "
        "high detail, sharp focus, clean composition, professional digital art, consistent color palette, "
        "no text, no watermark, no logo, no UI, no captions inside the image"
    )


def _urlopen(request: urllib.request.Request | str, timeout: int = 90) -> bytes:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _download(url: str, out: Path, headers: dict[str, str] | None = None, timeout: int = 120) -> None:
    request = urllib.request.Request(url, headers=headers or {})
    data = _urlopen(request, timeout=timeout)
    if len(data) < 100:
        raise ImageGenerationError("Image response was empty")
    out.write_bytes(data)


def _pollinations(prompt: str, out: Path, seed: int) -> None:
    query = urllib.parse.urlencode({
        "width": WIDTH,
        "height": HEIGHT,
        "seed": seed,
        "nologo": "true",
        "private": "true",
        "enhance": "true",
    })
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?{query}"
    _download(url, out, timeout=180)


def _cloudflare(prompt: str, out: Path, seed: int) -> None:
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not account or not token:
        raise ImageGenerationError("Cloudflare AI requires CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{CLOUDFLARE_MODEL}"
    payload = json.dumps({"prompt": prompt, "num_steps": 8, "guidance": 3.5, "seed": seed}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    data = _urlopen(request, timeout=180)
    try:
        parsed = json.loads(data.decode("utf-8"))
        result = parsed.get("result") or {}
        image_b64 = result.get("image") or result.get("b64_json") or result.get("base64")
        if image_b64:
            out.write_bytes(base64.b64decode(image_b64))
            return
        image_url = result.get("url") or result.get("image_url")
        if image_url:
            _download(image_url, out)
            return
        raise ImageGenerationError(parsed.get("errors") or "Cloudflare AI did not return an image")
    except UnicodeDecodeError:
        out.write_bytes(data)


def _replicate(prompt: str, out: Path, seed: int) -> None:
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise ImageGenerationError("Replicate requires REPLICATE_API_TOKEN")
    owner, model = REPLICATE_MODEL.split("/", 1) if "/" in REPLICATE_MODEL else ("black-forest-labs", "flux-schnell")
    url = f"https://api.replicate.com/v1/models/{owner}/{model}/predictions"
    payload = {
        "input": {
            "prompt": prompt,
            "width": WIDTH,
            "height": HEIGHT,
            "num_outputs": 1,
            "output_format": "png",
            "seed": seed,
        }
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Prefer": "wait=60"},
        method="POST",
    )
    prediction = json.loads(_urlopen(request, timeout=90).decode("utf-8"))
    deadline = time.time() + 300
    while prediction.get("status") not in {"succeeded", "failed", "canceled"} and time.time() < deadline:
        time.sleep(1.5)
        get = urllib.request.Request(prediction["urls"]["get"], headers={"Authorization": f"Bearer {token}"})
        prediction = json.loads(_urlopen(get, timeout=30).decode("utf-8"))
    if prediction.get("status") != "succeeded":
        raise ImageGenerationError(prediction.get("error") or f"Replicate prediction {prediction.get('status')}")
    output = prediction.get("output")
    image_url = output[0] if isinstance(output, list) else output
    if not image_url:
        raise ImageGenerationError("Replicate did not return an image URL")
    _download(str(image_url), out)


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def _template(scene: Any, out: Path, seed: int) -> None:
    colors = [
        (11, 16, 38),
        (16, 24, 39),
        (31, 41, 55),
        (49, 46, 129),
        (88, 28, 135),
        (15, 118, 110),
    ]
    accent = colors[seed % len(colors)]
    raw = bytearray()
    for y in range(HEIGHT):
        raw.append(0)
        band = 32 if (y // 96) % 2 else 0
        for x in range(WIDTH):
            glow = int(40 * (x / max(1, WIDTH - 1)))
            raw.extend((min(255, accent[0] + glow + band), min(255, accent[1] + glow), min(255, accent[2] + band)))
    png = b"\x89PNG\r\n\x1a\n"
    png += _png_chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0))
    png += _png_chunk(b"IDAT", zlib.compress(bytes(raw), level=6))
    png += _png_chunk(b"IEND", b"")
    out.write_bytes(png)


def _write_with_engine(engine_id: str, prompt: str, out: Path, seed: int, scene: Any) -> str:
    if engine_id == "pollinations":
        _pollinations(prompt, out, seed)
    elif engine_id == "cloudflare":
        _cloudflare(prompt, out, seed)
    elif engine_id == "replicate":
        _replicate(prompt, out, seed)
    elif engine_id == "templates" or engine_id == "puter":
        _template(scene, out, seed)
        return "templates" if engine_id == "puter" else "templates"
    else:
        raise ImageGenerationError(f"Unknown image engine: {engine_id}")
    return engine_id


def generate_scene_images(project: Any, engine: str | None = None, progress_callback: Callable[[int, str], None] | None = None) -> None:
    selected = _engine(engine or getattr(project, "image_engine", None)) or _engine(DEFAULT_ENGINE) or _engine("pollinations")
    engine_id = str(selected["id"])
    scenes = list(getattr(project, "scenes", []) or [])
    if not scenes:
        return
    out_dir = GENERATED / str(getattr(project, "id", "project"))
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(scenes)
    for index, scene in enumerate(scenes, start=1):
        prompt = _prompt(scene, str(getattr(project, "style", "cinematic")))
        seed = int(hashlib.sha256(f"{getattr(project, 'id', 'project')}|{index}|{prompt}".encode("utf-8")).hexdigest()[:8], 16)
        cache_key = hashlib.sha256(f"{engine_id}|{prompt}|{WIDTH}|{HEIGHT}|{seed}".encode("utf-8")).hexdigest()[:16]
        cached = out_dir / f"scene_{index:02d}_{engine_id}_{cache_key}.png"
        if progress_callback:
            progress_callback(int(3 + ((index - 1) / total) * 12), f"Generating image {index} of {total} with {selected['label']}")
        if not cached.exists() or cached.stat().st_size < 100:
            try:
                used_engine = _write_with_engine(engine_id, prompt, cached, seed, scene)
            except Exception as exc:
                if engine_id == "templates":
                    raise
                if progress_callback:
                    progress_callback(int(3 + ((index - 1) / total) * 12), f"{selected['label']} failed; using Templates fallback")
                _template(scene, cached, seed)
                used_engine = "templates"
            setattr(scene, "image_engine", used_engine)
        setattr(scene, "image_path", str(cached))
    if progress_callback:
        progress_callback(15, "Scene images ready")


if __name__ == "__main__":
    print(json.dumps(image_engines_status(), indent=2, ensure_ascii=False))
