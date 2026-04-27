import asyncio
import subprocess
from pathlib import Path


def _silent_audio(text: str, output_path: str) -> str:
    words = max(1, len(str(text or "").split()))
    duration = max(1.2, min(20.0, words * 0.36))
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(duration), "-q:a", "9", "-acodec", "libmp3lame", output_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    return output_path


async def _edge_tts(text: str, output_path: str, voice: str, rate: str, pitch: str) -> str:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(output_path)
    return output_path


def generate_hindi_tts_improved(text: str, output_path: str, voice: str = "hi-IN-SwaraNeural", emotion: str = "neutral") -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    emotion = (emotion or "neutral").lower()
    rate = "+0%"
    pitch = "+0Hz"
    if emotion in {"excited", "happy", "funny"}:
        rate, pitch = "+12%", "+20Hz"
    elif emotion in {"sad", "serious", "mysterious"}:
        rate, pitch = "-8%", "-15Hz"
    elif emotion in {"angry", "dramatic", "shocked"}:
        rate, pitch = "+6%", "+10Hz"
    try:
        asyncio.run(_edge_tts(text, output_path, voice, rate, pitch))
        return output_path
    except Exception:
        try:
            from gtts import gTTS
            gTTS(text=text, lang="hi").save(output_path)
            return output_path
        except Exception:
            return _silent_audio(text, output_path)
