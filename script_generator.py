import re
from collections import OrderedDict

SPEAKER_RE = re.compile(r"^\s*([^:\n]{1,40})\s*:\s*(.+?)\s*$")


def detect_language(text):
    devanagari = sum(1 for ch in text if "\u0900" <= ch <= "\u097f")
    latin = sum(1 for ch in text if "a" <= ch.lower() <= "z")
    if devanagari and devanagari >= latin * 0.25:
        return "hi"
    if devanagari:
        return "mixed"
    return "en"


def parse_custom_script(script_text):
    dialogues = []
    current = None
    for raw in (script_text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        match = SPEAKER_RE.match(line)
        if match:
            speaker, text = match.group(1).strip(), match.group(2).strip()
            current = {"speaker": speaker.upper(), "text": text, "emotion": "neutral"}
            dialogues.append(current)
        elif current:
            current["text"] += " " + line
        else:
            dialogues.append({"speaker": "NARRATOR", "text": line, "emotion": "neutral"})
    return dialogues


def assign_voices_to_characters(dialogues, voices):
    voice_keys = list(voices.keys()) if isinstance(voices, dict) else list(voices)
    if not voice_keys:
        voice_keys = ["en_us_001"]
    speakers = OrderedDict()
    for d in dialogues:
        speaker = d.get("speaker", "NARRATOR").upper()
        if speaker not in speakers:
            lang = detect_language(d.get("text", ""))
            preferred = [v for v in voice_keys if v.startswith("hi-")] if lang in {"hi", "mixed"} else [v for v in voice_keys if not v.startswith("hi-")]
            pool = preferred or voice_keys
            speakers[speaker] = pool[(len(speakers)) % len(pool)]
    return dict(speakers)
