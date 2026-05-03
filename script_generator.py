from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from typing import Any

NARRATOR_NAMES = {"narrator", "storyteller", "voiceover", "voice over", "vo"}


@dataclass
class DialogueLine:
    speaker: str
    text: str
    emotion: str = "neutral"
    gender: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_narrator(self) -> bool:
        return is_narrator(self.speaker)


def is_narrator(speaker: str | None) -> bool:
    return (speaker or "").strip().lower() in NARRATOR_NAMES


def normalize_speaker(speaker: str | None) -> str:
    value = (speaker or "NARRATOR").strip()
    return "NARRATOR" if is_narrator(value) else value


def _strip_code_fence(text: str) -> str:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json|javascript|js)?\s*", "", value, flags=re.I)
        value = re.sub(r"\s*```$", "", value)
    return value.strip()


def _quote_js_keys(value: str) -> str:
    return re.sub(r"([\{,]\s*)([A-Za-z_][\w-]*)(\s*:)", r'\1"\2"\3', value)


def _parse_jsonish(script: str) -> list[dict[str, Any]] | None:
    value = _strip_code_fence(script)
    if not value.startswith("[") and not value.startswith("{"):
        return None
    candidates = [value, _quote_js_keys(value)]
    for candidate in candidates:
        normalized = re.sub(r"\btrue\b", "true", candidate, flags=re.I)
        normalized = re.sub(r"\bfalse\b", "false", normalized, flags=re.I)
        normalized = re.sub(r"\bnull\b", "null", normalized, flags=re.I)
        try:
            data = json.loads(normalized)
            if isinstance(data, dict):
                for key in ("dialogue", "dialogues", "lines", "script"):
                    if isinstance(data.get(key), list):
                        data = data[key]
                        break
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)]
        except Exception:
            pass
    pyish = value.replace("null", "None").replace("true", "True").replace("false", "False")
    try:
        data = ast.literal_eval(pyish)
        if isinstance(data, dict):
            for key in ("dialogue", "dialogues", "lines", "script"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    except Exception:
        return None
    return None


def _dict_to_line(item: dict[str, Any]) -> DialogueLine:
    speaker = item.get("speaker") or item.get("name") or item.get("character") or item.get("role") or "NARRATOR"
    text = item.get("text") or item.get("line") or item.get("dialogue") or item.get("content") or ""
    emotion = item.get("emotion") or item.get("mood") or "neutral"
    gender = item.get("gender") or item.get("sex") or item.get("voice_gender")
    return DialogueLine(normalize_speaker(str(speaker)), str(text).strip(), str(emotion).strip().lower() or "neutral", str(gender).strip().lower() if gender else None, item)


def parse_dialogue(script: str) -> list[DialogueLine]:
    script = (script or "").strip()
    if not script:
        return []
    json_lines = _parse_jsonish(script)
    if json_lines is not None:
        return [line for line in (_dict_to_line(item) for item in json_lines) if line.text]

    lines: list[DialogueLine] = []
    pattern = re.compile(r"^\s*([^:\n\[]+?)(?:\s*\[([^\]]+)\])?\s*:\s*(.+?)\s*$")
    for raw_line in script.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        match = pattern.match(raw_line)
        if match:
            speaker, emotion, text = match.groups()
            lines.append(DialogueLine(normalize_speaker(speaker), text.strip(), (emotion or "neutral").strip().lower()))
        else:
            lines.append(DialogueLine("NARRATOR", raw_line, "neutral"))
    return lines


def format_dialogue_preview(lines: list[DialogueLine]) -> str:
    return "\n".join(f"{line.speaker} [{line.emotion}]: {line.text}" for line in lines)
