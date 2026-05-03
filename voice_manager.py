from __future__ import annotations

import math
import os
import re
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

from script_generator import DialogueLine

FEMALE_WORDS = {"mother", "mom", "mum", "girl", "woman", "sister", "aunt", "queen", "wife", "daughter", "lady", "princess", "grandma", "teacher"}
MALE_WORDS = {"father", "dad", "boy", "man", "brother", "uncle", "king", "husband", "son", "sir", "prince", "grandpa", "police"}
FEMALE_NAMES = {"alexa", "alice", "ananya", "anna", "aisha", "emma", "eva", "mia", "sophia", "olivia", "ava", "isabella", "mary", "sarah", "priya", "neha", "riya", "sita", "maria", "jessica"}
MALE_NAMES = {"alex", "aarav", "adam", "ben", "bob", "david", "ethan", "jack", "john", "liam", "michael", "noah", "oliver", "ram", "rahul", "raj", "sam", "tom", "william"}


@dataclass
class VoiceAssignment:
    speaker: str
    gender: str
    language: str
    voice_id: str
    is_narrator: bool = False


def detect_language(text: str) -> str:
    if re.search(r"[\u0900-\u097F]", text or ""):
        return "hi"
    return "en"


def infer_gender(name: str, explicit: str | None = None, index: int = 0) -> str:
    if explicit:
        low = explicit.lower().strip()
        if low in {"female", "woman", "girl", "f", "she", "her"}:
            return "female"
        if low in {"male", "man", "boy", "m", "he", "him"}:
            return "male"
        if low in {"neutral", "unknown", "other", "nonbinary", "non-binary"}:
            return "neutral"
    tokens = set(re.findall(r"[a-z]+", (name or "").lower()))
    if tokens & FEMALE_WORDS or (tokens and next(iter(tokens)) in FEMALE_NAMES) or (name or "").lower() in FEMALE_NAMES:
        return "female"
    if tokens & MALE_WORDS or (tokens and next(iter(tokens)) in MALE_NAMES) or (name or "").lower() in MALE_NAMES:
        return "male"
    return "female" if index % 2 else "male"


def assign_voices(lines: list[DialogueLine], narrator_voice: str = "storyteller") -> dict[str, VoiceAssignment]:
    assignments: dict[str, VoiceAssignment] = {}
    non_narrator_index = 0
    narrator_language = detect_language(" ".join(line.text for line in lines if line.is_narrator) or " ".join(line.text for line in lines))
    assignments["NARRATOR"] = VoiceAssignment("NARRATOR", "neutral", narrator_language, narrator_voice, True)
    for line in lines:
        if line.is_narrator:
            continue
        if line.speaker not in assignments:
            gender = infer_gender(line.speaker, line.gender, non_narrator_index)
            lang = detect_language(line.text)
            assignments[line.speaker] = VoiceAssignment(line.speaker, gender, lang, f"{lang}-{gender}-{non_narrator_index}")
            non_narrator_index += 1
    return assignments


def estimate_duration(text: str) -> float:
    words = max(1, len(re.findall(r"\w+", text or "")))
    return max(1.2, min(9.0, 0.55 + words / 2.45))


def _write_silent_wav(path: str, duration: float, frequency: float = 0.0, volume: float = 0.0) -> None:
    sample_rate = 22050
    frames = int(duration * sample_rate)
    with wave.open(path, "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for i in range(frames):
            value = 0
            if frequency and volume:
                value = int(32767 * volume * math.sin(2 * math.pi * frequency * i / sample_rate))
            wav.writeframesraw(value.to_bytes(2, "little", signed=True))


def synthesize_line(line: DialogueLine, assignment: VoiceAssignment, out_dir: str, index: int) -> tuple[str, float]:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    path = os.path.join(out_dir, f"line_{index:03d}.wav")
    duration = estimate_duration(line.text)
    try:
        import pyttsx3  # type: ignore

        engine = pyttsx3.init()
        rate = 168 if assignment.is_narrator else 182
        if assignment.gender == "female":
            rate += 8
        engine.setProperty("rate", rate)
        for voice in engine.getProperty("voices") or []:
            haystack = f"{getattr(voice, 'name', '')} {getattr(voice, 'id', '')}".lower()
            if assignment.gender == "female" and any(x in haystack for x in ("female", "zira", "samantha", "karen")):
                engine.setProperty("voice", voice.id); break
            if assignment.gender == "male" and any(x in haystack for x in ("male", "david", "mark", "daniel")):
                engine.setProperty("voice", voice.id); break
        engine.save_to_file(line.text, path)
        engine.runAndWait()
        if os.path.exists(path) and os.path.getsize(path) > 44:
            return path, wav_duration(path) or duration
    except Exception:
        pass
    frequency = 330.0 if assignment.is_narrator else (440.0 if assignment.gender == "female" else 260.0)
    _write_silent_wav(path, duration, frequency, 0.03)
    return path, duration


def wav_duration(path: str) -> float:
    try:
        with wave.open(path, "rb") as wav:
            return wav.getnframes() / float(wav.getframerate())
    except Exception:
        return 0.0


def concat_audio(wav_paths: list[str], output_path: str) -> str:
    if not wav_paths:
        _write_silent_wav(output_path, 1.5)
        return output_path
    list_path = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
    try:
        for path in wav_paths:
            list_path.write(f"file '{os.path.abspath(path)}'\n")
        list_path.close()
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list_path.name, "-c", "copy", output_path], check=True)
    finally:
        try: os.unlink(list_path.name)
        except Exception: pass
    return output_path
