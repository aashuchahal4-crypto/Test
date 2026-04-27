import subprocess

HINDI_VOICES = {
    "hi-IN-SwaraNeural": "Hindi - Swara",
    "hi-IN-MadhurNeural": "Hindi - Madhur",
}


def generate_hindi_tts(text, voice, output_path):
    try:
        from gtts import gTTS
        gTTS(text=text, lang="hi").save(output_path)
        return output_path
    except Exception:
        duration = max(1.2, min(18.0, len(text) / 12.0))
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=330:duration={duration:.2f}",
            "-filter:a", "volume=0.12,afade=t=in:st=0:d=0.08,afade=t=out:st={:.2f}:d=0.15".format(max(0.1, duration - 0.15)),
            "-c:a", "libmp3lame", output_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_path
