import asyncio
import subprocess

from hindi_tts import generate_hindi_tts

VOICES = {
    "en_us_001": "English US - Narrator",
    "en_us_006": "English US - Story",
    "en_uk_001": "English UK - Narrator",
    "en_au_001": "English AU - Narrator",
    "hi-IN-SwaraNeural": "Hindi - Swara",
    "hi-IN-MadhurNeural": "Hindi - Madhur",
}

EDGE_VOICE_MAP = {
    "en_us_001": "en-US-AriaNeural",
    "en_us_006": "en-US-GuyNeural",
    "en_uk_001": "en-GB-SoniaNeural",
    "en_au_001": "en-AU-NatashaNeural",
    "hi-IN-SwaraNeural": "hi-IN-SwaraNeural",
    "hi-IN-MadhurNeural": "hi-IN-MadhurNeural",
}


def _looks_hindi(text):
    return any("\u0900" <= ch <= "\u097f" for ch in text)


async def _edge_tts(text, voice, output_path):
    import edge_tts
    communicate = edge_tts.Communicate(text, EDGE_VOICE_MAP.get(voice, "en-US-AriaNeural"))
    await communicate.save(output_path)


def _fallback_tone(text, output_path):
    duration = max(1.0, min(20.0, len(text) / 13.5))
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=275:duration={duration:.2f}",
        "-filter:a", "volume=0.10,afade=t=in:st=0:d=0.08,afade=t=out:st={:.2f}:d=0.15".format(max(0.1, duration - 0.15)),
        "-c:a", "libmp3lame", output_path
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path


def generate_tiktok_tts(text, voice="en_us_001", output_path="tts.mp3"):
    if voice.startswith("hi-") or _looks_hindi(text):
        return generate_hindi_tts(text, voice, output_path)
    try:
        asyncio.run(_edge_tts(text, voice, output_path))
        return output_path
    except Exception:
        pass
    try:
        from gtts import gTTS
        gTTS(text=text, lang="en").save(output_path)
        return output_path
    except Exception:
        return _fallback_tone(text, output_path)
