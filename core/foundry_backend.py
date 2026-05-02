#!/usr/bin/env python3
"""Foundry Local backend for offline NPU/QNN AI inference."""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

FOUNDRY_CHAT_URL = os.environ.get("FOUNDRY_CHAT_URL")
FOUNDRY_COMMAND = os.environ.get("FOUNDRY_COMMAND", "foundry")
FOUNDRY_MODEL = os.environ.get("FOUNDRY_MODEL", "phi-3.5-mini-instruct-qnn-npu").strip()
SYSTEM_PROMPT = "You are an AI assistant for video content generation."
NPU_MODEL_PRIORITY = [
    "phi-3.5-mini-instruct-qnn-npu:2",
    "phi-3.5-mini-instruct-qnn-npu",
    "qwen2.5-1.5b-instruct-qnn-npu:2",
    "phi-3-mini-4k-instruct-qnn-npu:3",
    "qwen2.5-7b-instruct-qnn-npu:2",
    "deepseek-r1-distill-qwen-7b-qnn-npu:2",
    "qwen2.5-1.5b-instruct-qnn-npu",
    "deepseek-r1-distill-qwen-7b-qnn-npu",
]
NPU_FAMILY_PRIORITY = ["phi-3.5-mini", "phi-3-mini-4k", "qwen2.5-1.5b", "qwen2.5-7b", "deepseek-r1-7b", "phi", "qwen", "deepseek"]
LANGUAGE_NAMES = {
    "en-US": "English (US)",
    "en-GB": "English (UK)",
    "hi-IN": "Hindi",
    "es-ES": "Spanish",
    "fr-FR": "French",
    "de-DE": "German",
    "it-IT": "Italian",
    "pt-BR": "Portuguese",
    "ja-JP": "Japanese",
    "ko-KR": "Korean",
}


class FoundryError(RuntimeError):
    status_code = 503


class FoundryUnavailableError(FoundryError):
    status_code = 503


class NoNpuModelError(FoundryError):
    status_code = 503


class FoundryApiError(FoundryError):
    status_code = 502


@dataclass(frozen=True)
class FoundryModel:
    name: str
    device: str
    raw: str


def _run_foundry(args: list[str], *, timeout: int = 25) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            [FOUNDRY_COMMAND, *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise FoundryUnavailableError("Foundry Local is not available: the 'foundry' command was not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise FoundryUnavailableError(f"Foundry Local command timed out: foundry {' '.join(args)}") from exc
    except Exception as exc:
        raise FoundryUnavailableError(f"Foundry Local is not available: {exc}") from exc


def _run_model_list() -> str:
    try:
        result = _run_foundry(["model", "list"], timeout=30)
    except FoundryUnavailableError:
        raise
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "unknown error").strip()
        raise FoundryUnavailableError(f"Foundry Local is not available: {detail}")
    return result.stdout


def _extract_json_models(output: str) -> list[FoundryModel]:
    try:
        data = json.loads(output)
    except Exception:
        return []
    if isinstance(data, dict):
        rows = data.get("models") or data.get("data") or data.get("items") or []
    elif isinstance(data, list):
        rows = data
    else:
        rows = []
    models: list[FoundryModel] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or row.get("model") or row.get("id") or "").strip()
        device = str(row.get("device") or row.get("runtime") or row.get("executionProvider") or row.get("execution_provider") or "").strip()
        if name:
            models.append(FoundryModel(name=name, device=device, raw=json.dumps(row, ensure_ascii=False)))
    return models


def _extract_table_models(output: str) -> list[FoundryModel]:
    models: list[FoundryModel] = []
    for line in output.splitlines():
        raw = line.strip()
        if not raw or set(raw) <= {"-", "|", "+", " ", ":"}:
            continue
        lowered = raw.lower()
        if "name" in lowered and "device" in lowered:
            continue
        parts = [part.strip() for part in re.split(r"\s{2,}|\|", raw) if part.strip()]
        match = re.search(r"[\w./:-]*qnn-npu[\w./:-]*", raw, re.IGNORECASE)
        name = match.group(0) if match else next((part for part in parts if any(priority in part.lower() for priority in NPU_MODEL_PRIORITY)), "")
        if not name:
            name = parts[0] if parts else ""
        device = next((part for part in parts if part.upper() == "NPU"), "")
        if not device and re.search(r"\bNPU\b", raw, re.IGNORECASE):
            device = "NPU"
        if name:
            models.append(FoundryModel(name=name, device=device, raw=raw))
    return models


def list_models() -> list[FoundryModel]:
    output = _run_model_list()
    models = _extract_json_models(output) or _extract_table_models(output)
    return [model for model in models if is_npu_model(model)]


def is_npu_model(model: FoundryModel) -> bool:
    return model.device.upper() == "NPU" or "qnn-npu" in model.name.lower()


def select_model() -> FoundryModel:
    models = list_models()
    if not models:
        raise NoNpuModelError("No NPU model available")
    by_name = {model.name.lower(): model for model in models}
    if FOUNDRY_MODEL:
        requested = FOUNDRY_MODEL.lower()
        if requested in by_name:
            return by_name[requested]
        for model in models:
            if requested in model.name.lower():
                return model
        raise NoNpuModelError(f"FOUNDRY_MODEL was set to '{FOUNDRY_MODEL}', but that NPU model was not found")
    for preferred in NPU_MODEL_PRIORITY:
        if preferred in by_name:
            return by_name[preferred]
    for preferred in NPU_MODEL_PRIORITY:
        for model in models:
            if preferred in model.name.lower():
                return model
    for family in NPU_FAMILY_PRIORITY:
        for model in models:
            if family in model.name.lower():
                return model
    return models[0]


def _extract_endpoint(text: str) -> str | None:
    match = re.search(r"https?://(?:127\.0\.0\.1|localhost):\d+", text, re.IGNORECASE)
    return match.group(0).rstrip("/") if match else None


def service_endpoint(*, restart: bool = False) -> str:
    if FOUNDRY_CHAT_URL:
        return FOUNDRY_CHAT_URL.rsplit("/v1/chat/completions", 1)[0].rstrip("/")
    commands = [["service", "restart"]] if restart else [["service", "status"], ["service", "start"]]
    last_output = ""
    for args in commands:
        result = _run_foundry(args, timeout=35)
        output = f"{result.stdout}\n{result.stderr}".strip()
        last_output = output or last_output
        endpoint = _extract_endpoint(output)
        if endpoint:
            return endpoint
    raise FoundryUnavailableError(f"Foundry Local service endpoint was not found. Run 'foundry service start'. {last_output}".strip())


def chat_url(*, restart: bool = False) -> str:
    if FOUNDRY_CHAT_URL:
        return FOUNDRY_CHAT_URL
    return f"{service_endpoint(restart=restart)}/v1/chat/completions"


def _best_effort_load_model(model: FoundryModel, endpoint: str) -> None:
    url = f"{endpoint}/openai/load/{urllib.parse.quote(model.name, safe='')}"
    try:
        with urllib.request.urlopen(url, timeout=60):
            return
    except Exception:
        return


def language_label(language: str) -> str:
    return LANGUAGE_NAMES.get(language, language or "English")


def status() -> dict[str, Any]:
    model = select_model()
    endpoint = service_endpoint()
    return {
        "ok": True,
        "backend": "Foundry Local",
        "model": model.name,
        "device": "NPU (QNN)",
        "endpoint": f"{endpoint}/v1/chat/completions",
        "priority": NPU_MODEL_PRIORITY,
    }


def chat(user_prompt: str, *, temperature: float = 0.7, timeout: int = 120) -> str:
    model = select_model()
    payload = {
        "model": model.name,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }
    data = json.dumps(payload).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            url = chat_url(restart=attempt > 0)
            endpoint = url.rsplit("/v1/chat/completions", 1)[0]
            _best_effort_load_model(model, endpoint)
            request = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
            return _message_content(body)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError, FoundryUnavailableError) as exc:
            last_error = exc
            if attempt == 0:
                time.sleep(0.8)
                continue
    raise FoundryApiError(f"Foundry Local API failed after retry: {last_error}")


def _message_content(body: dict[str, Any]) -> str:
    choices = body.get("choices") or []
    if not choices:
        raise ValueError("missing choices in Foundry Local response")
    first = choices[0]
    if isinstance(first, dict):
        message = first.get("message") or {}
        content = message.get("content") if isinstance(message, dict) else None
        if content:
            return str(content)
        if first.get("text"):
            return str(first["text"])
    raise ValueError("missing assistant content in Foundry Local response")


def json_from_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.IGNORECASE | re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    else:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)
    cleaned = cleaned.replace("“", '"').replace("”", '"').replace("’", "'")
    return json.loads(cleaned)


def json_chat(instruction: str, *, temperature: float = 0.4, fallback: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    first = chat(instruction, temperature=temperature, timeout=timeout)
    try:
        return json_from_response(first)
    except Exception as first_error:
        repair_prompt = f"""
Convert the following model output into valid JSON only. Do not add markdown or explanation.
Required JSON output must be an object.
Model output:
{first}
""".strip()
        try:
            return json_from_response(chat(repair_prompt, temperature=0.1, timeout=min(timeout, 30)))
        except Exception:
            if fallback is not None:
                return fallback
            raise first_error


def validate_scene_payload(data: dict[str, Any], scene_count: int, duration: int) -> tuple[bool, str]:
    scenes = data.get("scenes")
    if not isinstance(scenes, list):
        return False, "root.scenes must be an array"
    if len(scenes) != scene_count:
        return False, f"expected exactly {scene_count} scenes, got {len(scenes)}"
    total = 0.0
    required = ["id", "duration", "visual_prompt", "camera_movement", "voice_text", "subtitle", "transition", "transition_duration", "effects", "style"]
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            return False, f"scene {index} must be an object"
        missing = [field for field in required if field not in scene]
        if missing:
            return False, f"scene {index} missing fields: {', '.join(missing)}"
        try:
            total += float(scene["duration"])
        except Exception:
            return False, f"scene {index} duration must be numeric"
        if len(str(scene.get("visual_prompt") or "")) < 35:
            return False, f"scene {index} visual_prompt is too short"
        if len(str(scene.get("voice_text") or "")) < 10:
            return False, f"scene {index} voice_text is too short"
    if abs(total - float(duration)) > 0.75:
        return False, f"scene durations must sum to {duration}, got {round(total, 2)}"
    return True, "ok"


def fallback_scene_payload(prompt: str, video_type: str, duration: int, style: str, language: str, voice: str = "auto") -> dict[str, Any]:
    lang = language_label(language)
    scene_count = max(3, min(8, round(duration / 6)))
    base_duration = round(duration / scene_count, 2)
    camera = ["slow_zoom_in", "pan_right", "slow_zoom_out", "pan_left", "tilt_up", "static", "slow_zoom_in", "pan_right"]
    transitions = ["fade", "push", "flash", "fade", "cut", "push", "fade", "flash"]
    effects = ["caption_pop", "slow_zoom", "pulse", "grain", "caption_pop", "pan_left", "slow_zoom", "pulse"]
    if language == "hi-IN":
        lines = [
            f"ध्यान दीजिए: {prompt} आपके काम को तुरंत बदल सकता है।",
            "सबसे पहले, लोकल AI आपकी स्क्रिप्ट और सीन बिना क्लाउड के तैयार करता है।",
            "फिर हर सीन के लिए साफ विजुअल, आवाज़ और सबटाइटल बनाए जाते हैं।",
            "इससे क्रिएटर तेज़ी से निजी और ऑफलाइन वीडियो बना सकता है।",
            "अंत में, CPU रेंडरिंग सब कुछ MP4 वीडियो में जोड़ देती है।",
            "यही लोकल AI वीडियो वर्कफ़्लो को व्यावहारिक बनाता है।",
        ]
    else:
        lines = [
            f"Here is the hook: {prompt} can change how creators work locally.",
            "First, local AI turns the idea into a clear script and scene plan.",
            "Each scene gets a visual, voiceover, subtitle, camera move, and transition.",
            "Then the image engine creates reusable local previews before rendering.",
            "Finally, FFmpeg combines motion, voice, music, and subtitles into an MP4.",
            "The result is a practical offline workflow for fast video creation.",
        ]
    scenes: list[dict[str, Any]] = []
    for index in range(scene_count):
        scene_duration = base_duration if index < scene_count - 1 else round(duration - (base_duration * (scene_count - 1)), 2)
        line = lines[index % len(lines)]
        scenes.append({
            "id": index + 1,
            "duration": scene_duration,
            "visual_prompt": f"{style} {video_type} vertical video keyframe about {prompt}, scene {index + 1}, strong subject, clear foreground, cinematic lighting, consistent color palette, professional composition, no text, no watermark",
            "camera_movement": camera[index],
            "voice_text": line,
            "subtitle": line[:95].rstrip(" .,;:") + ("..." if len(line) > 95 else ""),
            "transition": transitions[index],
            "transition_duration": 0.35,
            "effects": effects[index],
            "style": style,
        })
    return {"scenes": scenes, "fallback": True, "fallback_reason": "Local model did not return valid scene JSON quickly enough"}


def generate_script(prompt: str, video_type: str, duration: int, style: str, language: str) -> str:
    lang = language_label(language)
    instruction = f"""
Write the exact script requested by the user.
User request/topic: {prompt}
Video type: {video_type}
Target length: about {duration} seconds
Style: {style}
Language: {lang}
Requirements:
- Follow the user's topic directly.
- Do not mention AI internals, Foundry, NPU, or rendering unless the user asked for that topic.
- Make the first sentence a strong hook.
- Keep narration concise and ready for voiceover.
Return only the script text.
""".strip()
    return chat(instruction, temperature=0.7)


def generate_scene_json(prompt: str, video_type: str, duration: int, style: str, language: str, voice: str = "auto") -> dict[str, Any]:
    lang = language_label(language)
    voice_label = {"auto": "natural voice", "male": "male voice", "female": "female voice"}.get(voice, voice or "natural voice")
    scene_count = max(3, min(8, round(duration / 6)))
    schema = f"""
{{
  "scenes": [
    {{
      "id": 1,
      "duration": 5,
      "visual_prompt": "image prompt: subject, environment, composition, lighting, color palette, era, wardrobe/props, no text inside image",
      "camera_movement": "slow_zoom_in|slow_zoom_out|pan_left|pan_right|tilt_up|static",
      "voice_text": "voiceover text in {lang}",
      "subtitle": "short readable subtitle in {lang}",
      "transition": "cut|fade|push|flash",
      "transition_duration": 0.45,
      "effects": "slow_zoom|caption_pop|pan_left|pulse|grain",
      "style": "{style}"
    }}
  ]
}}
""".strip()
    base_instruction = f"""
You are generating scenes for the user's requested video. Follow the user's topic exactly.

User request/topic:
{prompt}

Video settings:
- Type: {video_type}
- Target total duration: {duration} seconds
- Required scene count: exactly {scene_count} scenes
- Visual style: {style}
- Narration/caption language: {lang}
- Voice direction: {voice_label}

Return ONLY valid JSON. No markdown. No explanation. The JSON must match this schema exactly:
{schema}

Rules:
- Every scene must be about the user's request/topic, not generic local AI content.
- Use {lang} for every voice_text value.
- subtitle must be shorter than voice_text and readable in under 2 seconds.
- Write voice_text so it sounds natural for a {voice_label}.
- visual_prompt must be optimized for image generation: concrete nouns, subject, setting, lighting, lens/composition, style words, no logos, no embedded text, no UI labels.
- Return exactly {scene_count} scenes.
- Each scene duration should be about {round(duration / scene_count, 2)} seconds.
- All durations combined must sum to exactly {duration} seconds.
- Keep voice_text short enough for the scene duration.
""".strip()
    last_error = ""
    for attempt in range(2):
        instruction = base_instruction if not last_error else f"{base_instruction}\n\nPrevious output failed validation: {last_error}. Regenerate the full JSON object only."
        try:
            data = json_chat(instruction, temperature=0.25 if attempt else 0.35, fallback={"scenes": []}, timeout=45)
        except Exception as exc:
            last_error = str(exc)
            break
        ok, detail = validate_scene_payload(data, scene_count, duration)
        if ok:
            return data
        last_error = detail
    return fallback_scene_payload(prompt, video_type, duration, style, language, voice)


def generate_hooks_titles(prompt: str, video_type: str, language: str) -> dict[str, Any]:
    lang = language_label(language)
    instruction = f"""
Create hooks and titles for the user's requested video.
User request/topic: {prompt}
Video type: {video_type}
Language: {lang}
Return ONLY valid JSON with this schema: {{"hooks":["..."],"titles":["..."]}}.
Rules:
- 5 hooks and 5 titles.
- All text must be in {lang}.
- Make them specific to the user's topic.
""".strip()
    return json_chat(instruction, temperature=0.65, fallback={"hooks": [], "titles": []})


def generate_captions(script: str, language: str) -> dict[str, Any]:
    lang = language_label(language)
    instruction = f"""
Break this script into short readable captions.
Language: {lang}
Script:
{script}
Return ONLY valid JSON with this schema: {{"captions":[{{"text":"...","emphasis":"normal|strong"}}]}}.
Rules:
- Preserve the script meaning.
- Each caption should be short and readable on a video.
- All caption text must be in {lang}.
""".strip()
    return json_chat(instruction, temperature=0.35, fallback={"captions": []})


def rewrite_viral(text: str, platform: str, language: str) -> str:
    lang = language_label(language)
    instruction = f"""
Rewrite the user's text for stronger retention and shareability.
Platform: {platform}
Language: {lang}
Original text:
{text}
Rules:
- Keep the original meaning.
- Improve the hook, pacing, clarity, and emotional pull.
- Do not add unrelated facts.
- Return only the rewritten text in {lang}.
""".strip()
    return chat(instruction, temperature=0.75)
