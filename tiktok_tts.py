     1	import os
     2	import subprocess
     3	from pathlib import Path
     4	from urllib.parse import quote
     5	
     6	import requests
     7	
     8	from hindi_tts import generate_hindi_tts_improved
     9	
    10	VOICES = {
    11	    "Narrator - TikTok English (free)": "en_us_001",
    12	    "Jessie - TikTok English (free)": "en_us_002",
    13	    "Guy - TikTok English (free)": "en_us_006",
    14	    "Story - TikTok English (free)": "en_uk_001",
    15	    "Hindi Female - Edge/gTTS (free)": "hi-IN-SwaraNeural",
    16	    "Hindi Male - Edge/gTTS (free)": "hi-IN-MadhurNeural",
    17	    "English - Male (Professional)": "en_us_006",
    18	    "English - Female (Narrator)": "en_us_002",
    19	    "English - Female (Warm)": "en_us_002",
    20	    "English - Male (Deep)": "en_us_001",
    21	    "English - Ghost Face (Spooky)": "en_us_ghostface",
    22	    "English - Rocket (Sarcastic)": "en_us_rocket",
    23	    "English - Stitch (Cute)": "en_us_stitch",
    24	    "English - C3PO (Robot)": "en_us_c3po",
    25	    "English - Chewbacca (Funny)": "en_us_chewbacca",
    26	    "English - Stormtrooper (Meme)": "en_us_stormtrooper",
    27	    "English (UK) - Male (Formal)": "en_uk_001",
    28	    "English (UK) - Female (Formal)": "en_uk_003",
    29	    "English (AU) - Female": "en_au_001",
    30	    "English (AU) - Male": "en_au_002",
    31	    "Hindi - Male (Natural)": "hi-IN-MadhurNeural",
    32	    "Hindi - Female (Natural)": "hi-IN-SwaraNeural",
    33	    "Hindi - Male (Professional)": "hi-IN-MadhurNeural",
    34	    "Hindi - Female (Professional)": "hi-IN-SwaraNeural",
    35	    "Hindi Male": "hi-IN-MadhurNeural",
    36	    "Hindi Female": "hi-IN-SwaraNeural",
    37	}
    38	
    39	VOICE_ALIASES = {
    40	    "en_us_001": "Brian",
    41	    "en_us_002": "Joanna",
    42	    "en_us_006": "Matthew",
    43	    "en_uk_001": "Amy",
    44	    "en_uk_003": "Emma",
    45	    "en_au_001": "Nicole",
    46	    "en_au_002": "Russell",
    47	    "en_us_ghostface": "Brian",
    48	    "en_us_rocket": "Matthew",
    49	    "en_us_stitch": "Joanna",
    50	    "en_us_c3po": "Brian",
    51	    "en_us_chewbacca": "Matthew",
    52	    "en_us_stormtrooper": "Matthew",
    53	}
    54	
    55	
    56	def _silent_audio(text: str, output_path: str) -> str:
    57	    words = max(1, len(str(text or "").split()))
    58	    duration = max(1.2, min(20.0, words * 0.34))
    59	    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    60	    subprocess.run(
    61	        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(duration), "-q:a", "9", "-acodec", "libmp3lame", output_path],
    62	        stdout=subprocess.DEVNULL,
    63	        stderr=subprocess.DEVNULL,
    64	        check=True,
    65	    )
    66	    return output_path
    67	
    68	
    69	def _normalise_voice(voice: str) -> str:
    70	    return VOICES.get(voice, voice or "en_us_001")
    71	
    72	
    73	def _is_hindi(text: str, voice: str) -> bool:
    74	    return "hi-IN" in voice or any("\u0900" <= ch <= "\u097F" for ch in str(text or ""))
    75	
    76	
    77	def generate_tiktok_tts(text: str, output_path: str, voice: str = "en_us_001", emotion: str = "neutral") -> str:
    78	    voice = _normalise_voice(voice)
    79	    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    80	    if _is_hindi(text, voice):
    81	        hindi_voice = voice if "hi-IN" in voice else "hi-IN-SwaraNeural"
    82	        return generate_hindi_tts_improved(text, output_path, hindi_voice, emotion)
    83	
    84	    try:
    85	        se_voice = VOICE_ALIASES.get(voice, "Brian")
    86	        url = f"https://api.streamelements.com/kappa/v2/speech?voice={quote(se_voice)}&text={quote(text[:450])}"
    87	        response = requests.get(url, timeout=25)
    88	        response.raise_for_status()
    89	        if response.content and response.headers.get("content-type", "").startswith("audio"):
    90	            Path(output_path).write_bytes(response.content)
    91	            return output_path
    92	    except Exception:
    93	        pass
    94	
    95	    try:
    96	        from gtts import gTTS
    97	        gTTS(text=text, lang="en").save(output_path)
    98	        return output_path
    99	    except Exception:
   100	        return _silent_audio(text, output_path)
   101	
   102	
   103	def text_to_speech(text: str, voice: str, output_path: str, emotion: str = "neutral") -> str:
   104	    return generate_tiktok_tts(text, output_path, voice, emotion)
   105	