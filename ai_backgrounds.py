     1	import base64
     2	import hashlib
     3	import io
     4	import json
     5	import os
     6	from pathlib import Path
     7	from typing import Dict, Optional, Tuple
     8	
     9	import requests
    10	from PIL import Image, ImageDraw
    11	
    12	CACHE_DIR = Path("outputs/ai_backgrounds/cache")
    13	RUNTIME_DIR = Path("outputs/ai_backgrounds")
    14	
    15	
    16	def safe_endpoint(endpoint_url: str | None = None) -> str:
    17	    return (endpoint_url or os.getenv("AI_IMAGE_API_URL") or "").strip()
    18	
    19	
    20	def cache_key(endpoint_url: str, prompt: str, negative_prompt: str, seed: int, guidance_scale: float, width: int, height: int) -> str:
    21	    payload = json.dumps(
    22	        {
    23	            "endpoint": endpoint_url,
    24	            "prompt": prompt,
    25	            "negative_prompt": negative_prompt,
    26	            "seed": seed,
    27	            "guidance_scale": guidance_scale,
    28	            "width": width,
    29	            "height": height,
    30	        },
    31	        sort_keys=True,
    32	    )
    33	    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
    34	
    35	
    36	def _strip_data_uri(value: str) -> str:
    37	    if value.startswith("data:image") and "," in value:
    38	        return value.split(",", 1)[1]
    39	    return value
    40	
    41	
    42	def _decode_base64_image(value: str) -> Image.Image:
    43	    raw = base64.b64decode(_strip_data_uri(value), validate=False)
    44	    return Image.open(io.BytesIO(raw)).convert("RGB")
    45	
    46	
    47	def _image_from_json(data: Dict[str, object]) -> Image.Image:
    48	    for key in ("image", "image_base64", "base64", "data"):
    49	        value = data.get(key)
    50	        if isinstance(value, str) and value.strip():
    51	            return _decode_base64_image(value.strip())
    52	    images = data.get("images")
    53	    if isinstance(images, list) and images:
    54	        first = images[0]
    55	        if isinstance(first, str):
    56	            return _decode_base64_image(first)
    57	        if isinstance(first, dict):
    58	            return _image_from_json(first)
    59	    raise ValueError("AI endpoint JSON did not contain image/image_base64/base64/data/images")
    60	
    61	
    62	def fit_vertical(image: Image.Image, size: Tuple[int, int] = (1080, 1920)) -> Image.Image:
    63	    target_w, target_h = size
    64	    image = image.convert("RGB")
    65	    src_w, src_h = image.size
    66	    scale = max(target_w / max(1, src_w), target_h / max(1, src_h))
    67	    resized = image.resize((int(src_w * scale) + 1, int(src_h * scale) + 1), Image.Resampling.LANCZOS)
    68	    left = max(0, (resized.width - target_w) // 2)
    69	    top = max(0, (resized.height - target_h) // 2)
    70	    return resized.crop((left, top, left + target_w, top + target_h))
    71	
    72	
    73	def create_gradient_background(path: str | Path, color_a: str = "#161629", color_b: str = "#ff3b7f", size: Tuple[int, int] = (1080, 1920)) -> str:
    74	    path = Path(path)
    75	    path.parent.mkdir(parents=True, exist_ok=True)
    76	    w, h = size
    77	    def parse(c: str):
    78	        c = (c or "#000000").lstrip("#")
    79	        if len(c) != 6:
    80	            c = "000000"
    81	        return tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
    82	    a, b = parse(color_a), parse(color_b)
    83	    img = Image.new("RGB", size)
    84	    draw = ImageDraw.Draw(img)
    85	    for y in range(h):
    86	        t = y / max(1, h - 1)
    87	        wave = 0.08 * ((y // 90) % 2)
    88	        rgb = tuple(int(a[i] * (1 - t) + b[i] * t + 255 * wave) for i in range(3))
    89	        draw.line([(0, y), (w, y)], fill=rgb)
    90	    img.save(path, "PNG")
    91	    return str(path)
    92	
    93	
    94	def generate_ai_background(
    95	    prompt: str,
    96	    negative_prompt: str = "text, watermark, logo, captions, blurry, low quality, distorted faces",
    97	    endpoint_url: str | None = None,
    98	    seed: int = -1,
    99	    guidance_scale: float = 7.5,
   100	    width: int = 1024,
   101	    height: int = 1024,
   102	    timeout: int = 90,
   103	    output_dir: str | Path = RUNTIME_DIR,
   104	    use_cache: bool = True,
   105	) -> Tuple[Optional[str], str]:
   106	    endpoint = safe_endpoint(endpoint_url)
   107	    if not endpoint:
   108	        return None, "No AI image endpoint configured; using fallback background."
   109	
   110	    CACHE_DIR.mkdir(parents=True, exist_ok=True)
   111	    output_dir = Path(output_dir)
   112	    output_dir.mkdir(parents=True, exist_ok=True)
   113	    key = cache_key(endpoint, prompt, negative_prompt, int(seed), float(guidance_scale), int(width), int(height))
   114	    cached = CACHE_DIR / f"{key}.png"
   115	    if use_cache and cached.exists():
   116	        return str(cached), f"Reused cached AI background {cached.name}."
   117	
   118	    payload = {
   119	        "prompt": prompt,
   120	        "negative_prompt": negative_prompt,
   121	        "seed": int(seed),
   122	        "guidance_scale": float(guidance_scale),
   123	        "width": int(width),
   124	        "height": int(height),
   125	    }
   126	    try:
   127	        response = requests.post(endpoint, json=payload, timeout=timeout)
   128	        response.raise_for_status()
   129	        content_type = response.headers.get("content-type", "").lower()
   130	        if "image/" in content_type:
   131	            image = Image.open(io.BytesIO(response.content)).convert("RGB")
   132	        else:
   133	            image = _image_from_json(response.json())
   134	        fitted = fit_vertical(image)
   135	        fitted.save(cached, "PNG")
   136	        return str(cached), f"Generated AI background via external endpoint and cached {cached.name}."
   137	    except Exception as exc:
   138	        return None, f"AI background request failed: {exc}. Using fallback background."
   139	