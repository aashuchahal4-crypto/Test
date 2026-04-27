import subprocess


def audio_duration(path):
    try:
        result = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", path
        ], check=True, capture_output=True, text=True)
        return max(0.05, float(result.stdout.strip()))
    except Exception:
        return 1.5


def heuristic_timings(audio_paths, dialogues):
    cursor = 0.0
    timings = []
    for idx, path in enumerate(audio_paths):
        duration = audio_duration(path)
        timings.append({
            "index": idx,
            "start": cursor,
            "end": cursor + duration,
            "duration": duration,
            "text": dialogues[idx].get("text", "") if idx < len(dialogues) else "",
            "words": []
        })
        cursor += duration
    return timings


def whisper_timings(audio_path, dialogues, model_name="base"):
    try:
        import whisper
    except ImportError as exc:
        raise RuntimeError("Whisper is not installed") from exc
    model = whisper.load_model(model_name)
    result = model.transcribe(audio_path, word_timestamps=True)
    segments = result.get("segments") or []
    if not segments:
        raise RuntimeError("Whisper returned no segments")
    timings = []
    for idx, dialogue in enumerate(dialogues):
        if idx < len(segments):
            seg = segments[idx]
            timings.append({
                "index": idx,
                "start": float(seg.get("start", 0.0)),
                "end": float(seg.get("end", 0.0)),
                "duration": max(0.05, float(seg.get("end", 0.0)) - float(seg.get("start", 0.0))),
                "text": dialogue.get("text", ""),
                "words": seg.get("words") or [],
            })
    return timings


def align_timings(audio_paths, dialogues, use_whisper=False, combined_audio_path=None):
    if use_whisper and combined_audio_path:
        try:
            timings = whisper_timings(combined_audio_path, dialogues)
            if len(timings) >= len(dialogues):
                return timings[:len(dialogues)], "Whisper sync used"
        except Exception as exc:
            return heuristic_timings(audio_paths, dialogues), f"Whisper unavailable; fallback timing used ({exc})"
    return heuristic_timings(audio_paths, dialogues), "fallback timing used"
