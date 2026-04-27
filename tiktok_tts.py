import os
import subprocess
from pathlib import Path
from urllib.parse import quote

import requests

from hindi_tts import generate_hindi_tts_improved

VOICES = {
    "Narrator - TikTok English (free)": "en_us_001",
    "Jessie - TikTok English (free)": "en_us_002",
    "Guy - TikTok English (free)": "en_us_006",
    "Story - TikTok English (free)": "en_uk_001",
    "Hindi Female - Edge/gTTS (free)": "hi-IN-SwaraNeural",
    "Hindi Male - Edge/gTTS (free)": "hi-IN-MadhurNeural",
    "English - Male (Professional)": "en_us_006",
    "English - Female (Narrator)": "en_us_002",
    "English - Female (Warm)": "en_us_002",
    "English - Male (Deep)": "en_us_001",
    "English - Ghost Face (Spooky)": "en_us_ghostface",
    "English - Rocket (Sarcastic)": "en_us_rocket",
    "English - Stitch (Cute)": "en_us_stitch",
    "English - C3PO (Robot)": "en_us_c3po",
    "English - Chewbacca (Funny)": "en_us_chewbacca",
    "English - Stormtrooper (Meme)": "en_us_stormtrooper",
    "English (UK) - Male (Formal)": "en_uk_001",
    "English (UK) - Female (Formal)": "en_uk_003",
    "English (AU) - Female": "en_au_001",
    "English (AU) - Male": "en_au_002",
    "Hindi - Male (Natural)": "hi-IN-MadhurNeural",
    "Hindi - Female (Natural)": "hi-IN-SwaraNeural",
    "Hindi - Male (Professional)": "hi-IN-MadhurNeural",
    "Hindi - Female (Professional)": "hi-IN-SwaraNeural",
    "Hindi Male": "hi-IN-MadhurNeural",
    "Hindi Female": "hi-IN-SwaraNeural",
}

VOICE_ALIASES = {
    "en_us_001": "Brian",
    "en_us_002": "Joanna",
    "en_us_006": "Matthew",
    "en_uk_001": "Amy",
    "en_uk_003": "Emma",
    "en_au_001": "Nicole",
    "en_au_002": "Russell",
    "en_us_ghostface": "Brian",
    "en_us_rocket": "Matthew",
    "en_us_stitch": "Joanna",
    "en_us_c3po": "Brian",
    "en_us_chewbacca": "Matthew",
    "en_us_stormtrooper": "Matthew",
}


def _silent_audio(text: str, output_path: str) -> str:
    words = max(1, len(str(text or "").split()))
    duration = max(1.2, min(20.0, words * 0.34))
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(duration), "-q:a", "9", "-acodec", "libmp3lame", output_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    return output_path


def _normalise_voice(voice: str) -> str:
    return VOICES.get(voice, voice or "en_us_001")


def _is_hindi(text: str, voice: str) -> bool:
    return "hi-IN" in voice or any("\u0900" <= ch <= "\u097F" for ch in str(text or ""))


def generate_tiktok_tts(text: str, output_path: str, voice: str = "en_us_001", emotion: str = "neutral") -> str:
    voice = _normalise_voice(voice)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    if _is_hindi(text, voice):
        hindi_voice = voice if "hi-IN" in voice else "hi-IN-SwaraNeural"
        return generate_hindi_tts_improved(text, output_path, hindi_voice, emotion)

    try:
        se_voice = VOICE_ALIASES.get(voice, "Brian")
        url = f"https://api.streamelements.com/kappa/v2/speech?voice={quote(se_voice)}&text={quote(text[:450])}"
        response = requests.get(url, timeout=25)
        response.raise_for_status()
        if response.content and response.headers.get("content-type", "").startswith("audio"):
            Path(output_path).write_bytes(response.content)
            return output_path
    except Exception:
        pass

    try:
        from gtts import gTTS
        gTTS(text=text, lang="en").save(output_path)
        return output_path
    except Exception:
        return _silent_audio(text, output_path)


def text_to_speech(text: str, voice: str, output_path: str, emotion: str = "neutral") -> str:
    return generate_tiktok_tts(text, output_path, voice, emotion)
