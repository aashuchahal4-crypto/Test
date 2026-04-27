     1	import asyncio
     2	import subprocess
     3	from pathlib import Path
     4	
     5	
     6	def _silent_audio(text: str, output_path: str) -> str:
     7	    words = max(1, len(str(text or "").split()))
     8	    duration = max(1.2, min(20.0, words * 0.36))
     9	    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    10	    subprocess.run(
    11	        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(duration), "-q:a", "9", "-acodec", "libmp3lame", output_path],
    12	        stdout=subprocess.DEVNULL,
    13	        stderr=subprocess.DEVNULL,
    14	        check=True,
    15	    )
    16	    return output_path
    17	
    18	
    19	async def _edge_tts(text: str, output_path: str, voice: str, rate: str, pitch: str) -> str:
    20	    import edge_tts
    21	    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
    22	    await communicate.save(output_path)
    23	    return output_path
    24	
    25	
    26	def generate_hindi_tts_improved(text: str, output_path: str, voice: str = "hi-IN-SwaraNeural", emotion: str = "neutral") -> str:
    27	    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    28	    emotion = (emotion or "neutral").lower()
    29	    rate = "+0%"
    30	    pitch = "+0Hz"
    31	    if emotion in {"excited", "happy", "funny"}:
    32	        rate, pitch = "+12%", "+20Hz"
    33	    elif emotion in {"sad", "serious", "mysterious"}:
    34	        rate, pitch = "-8%", "-15Hz"
    35	    elif emotion in {"angry", "dramatic", "shocked"}:
    36	        rate, pitch = "+6%", "+10Hz"
    37	    try:
    38	        asyncio.run(_edge_tts(text, output_path, voice, rate, pitch))
    39	        return output_path
    40	    except Exception:
    41	        try:
    42	            from gtts import gTTS
    43	            gTTS(text=text, lang="hi").save(output_path)
    44	            return output_path
    45	        except Exception:
    46	            return _silent_audio(text, output_path)
    47	