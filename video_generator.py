from __future__ import annotations

import os
import random
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from script_generator import DialogueLine, parse_dialogue
from stickman_scene import render_stickman_video
from voice_manager import assign_voices, concat_audio, synthesize_line

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "assets" / "output"
MUSIC_DIR = ROOT / "assets" / "music"
TMP_DIR = ROOT / "assets" / "tmp"
SUPPORTED_MUSIC = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}


def list_music() -> list[str]:
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    items = [p.name for p in MUSIC_DIR.iterdir() if p.suffix.lower() in SUPPORTED_MUSIC]
    return ["None", "Random"] + sorted(items)


def _ffmpeg_duration(path: str) -> float:
    try:
        result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path], capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _mux(video_path: str, audio_path: str, output_path: str, music_choice: str = "None", music_volume: float = 0.12) -> str:
    music_file = None
    music_items = [p for p in MUSIC_DIR.iterdir() if p.suffix.lower() in SUPPORTED_MUSIC] if MUSIC_DIR.exists() else []
    if music_choice == "Random" and music_items:
        music_file = str(random.choice(music_items))
    elif music_choice and music_choice not in {"None", "Random"}:
        candidate = MUSIC_DIR / music_choice
        if candidate.exists():
            music_file = str(candidate)
    if music_file:
        subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", video_path, "-i", audio_path, "-stream_loop", "-1", "-i", music_file,
            "-filter_complex", f"[2:a]volume={music_volume}[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=2[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-shortest", output_path,
        ], check=True)
    else:
        subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", video_path, "-i", audio_path,
            "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest", output_path,
        ], check=True)
    return output_path


def generate_video(script: str, title: str = "Brainrot Story", aspect_ratio: str = "9:16", narrator_voice: str = "storyteller", caption_style: str = "Bottom captions", background_music: str = "None", progress_callback=None) -> tuple[str | None, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    lines = parse_dialogue(script)
    if not lines:
        return None, "No dialogue lines found. Paste narrator, character, or JSON dialogue lines."
    run_id = f"story_{int(time.time())}_{random.randint(1000,9999)}"
    final_path = str(OUTPUT_DIR / f"{run_id}.mp4")
    work_dir = tempfile.mkdtemp(prefix=f"{run_id}_", dir=str(TMP_DIR))
    try:
        if progress_callback:
            progress_callback(0.10, desc="Assigning voices")
        assignments = assign_voices(lines, narrator_voice)
        wav_paths: list[str] = []
        timings: list[tuple[float, float]] = []
        cursor = 0.0
        for i, line in enumerate(lines):
            assignment = assignments.get("NARRATOR" if line.is_narrator else line.speaker, assignments["NARRATOR"])
            wav, duration = synthesize_line(line, assignment, work_dir, i)
            wav_paths.append(wav)
            timings.append((cursor, cursor + max(0.5, duration)))
            cursor = timings[-1][1]
            if progress_callback:
                progress_callback(0.10 + 0.35 * ((i + 1) / len(lines)), desc=f"Rendering audio line {i+1}/{len(lines)}")
        audio_path = os.path.join(work_dir, "dialogue.wav")
        concat_audio(wav_paths, audio_path)
        audio_duration = _ffmpeg_duration(audio_path)
        if audio_duration > 0 and timings:
            timings[-1] = (timings[-1][0], max(timings[-1][1], audio_duration))
        if progress_callback:
            progress_callback(0.52, desc="Rendering stickman scenes")
        scene_video = os.path.join(work_dir, "stickman.mp4")
        render_stickman_video(lines, timings, scene_video, title=title, aspect_ratio=aspect_ratio, caption_style=caption_style)
        if progress_callback:
            progress_callback(0.88, desc="Muxing final video")
        _mux(scene_video, audio_path, final_path, background_music)
        summary = [f"Generated {len(lines)} dialogue segments with stickman scenes.", f"Output: {final_path}"]
        voices = ", ".join(f"{k}={v.gender}/{v.language}" for k, v in assignments.items())
        summary.append(f"Voices: {voices}")
        return final_path, "\n".join(summary)
    except Exception as exc:
        return None, f"Generation failed: {exc}"
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def generate_video_gradio(script: str, title: str, aspect_ratio: str, narrator_voice: str, caption_style: str, background_music: str, progress=None):
    cb = None
    if progress is not None:
        cb = lambda value, desc="": progress(value, desc=desc)
    return generate_video(script, title, aspect_ratio, narrator_voice, caption_style, background_music, cb)
