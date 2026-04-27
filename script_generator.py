     1	import json
     2	import re
     3	from typing import Any, Dict, List
     4	
     5	
     6	def _clean_text(value: Any) -> str:
     7	    return str(value or "").strip()
     8	
     9	
    10	def _normalise_line(item: Dict[str, Any], index: int) -> Dict[str, Any]:
    11	    speaker = _clean_text(item.get("speaker") or item.get("name") or item.get("role") or "NARRATOR")
    12	    text = _clean_text(item.get("text") or item.get("dialogue") or item.get("line") or item.get("content"))
    13	    emotion = _clean_text(item.get("emotion") or "neutral").lower() or "neutral"
    14	    return {"speaker": speaker.upper(), "text": text, "emotion": emotion, "index": index}
    15	
    16	
    17	def parse_custom_script(script: str) -> List[Dict[str, Any]]:
    18	    """Parse JSON, Speaker: Dialogue, or Speaker [emotion]: Dialogue scripts."""
    19	    script = _clean_text(script)
    20	    if not script:
    21	        return []
    22	
    23	    try:
    24	        parsed = json.loads(script)
    25	        if isinstance(parsed, dict):
    26	            parsed = parsed.get("dialogue") or parsed.get("dialogues") or parsed.get("lines") or [parsed]
    27	        if isinstance(parsed, list):
    28	            lines = []
    29	            for i, item in enumerate(parsed):
    30	                if isinstance(item, str):
    31	                    lines.extend(parse_custom_script(item))
    32	                elif isinstance(item, dict):
    33	                    line = _normalise_line(item, len(lines))
    34	                    if line["text"]:
    35	                        lines.append(line)
    36	            if lines:
    37	                return lines
    38	    except Exception:
    39	        pass
    40	
    41	    out: List[Dict[str, Any]] = []
    42	    pattern = re.compile(r"^\s*([A-Za-z0-9_ \-]+?)(?:\s*\[([^\]]+)\])?\s*:\s*(.+?)\s*$")
    43	    for raw in script.splitlines():
    44	        raw = raw.strip().strip("-•")
    45	        if not raw:
    46	            continue
    47	        match = pattern.match(raw)
    48	        if match:
    49	            speaker, emotion, text = match.groups()
    50	            out.append({
    51	                "speaker": speaker.strip().upper() or "NARRATOR",
    52	                "text": text.strip(),
    53	                "emotion": (emotion or "neutral").strip().lower(),
    54	                "index": len(out),
    55	            })
    56	        else:
    57	            out.append({"speaker": "NARRATOR", "text": raw, "emotion": "neutral", "index": len(out)})
    58	    return out
    59	
    60	
    61	def generate_sample_script(kind: str = "Conspiracy") -> Dict[str, str]:
    62	    samples = {
    63	        "Conspiracy": {
    64	            "title": "The Algorithm Knows Too Much",
    65	            "script": "NARRATOR [mysterious]: What if your phone predicts what you want before you do?\nCHARACTER1 [shocked]: Bro, I only thought about pizza and suddenly ads appeared.\nCHARACTER2 [serious]: That is not magic. It is patterns, location, and your scroll history.\nNARRATOR [dramatic]: The scary part is how normal it feels now.",
    66	        },
    67	        "Storytime": {
    68	            "title": "I Accidentally Went Viral",
    69	            "script": "NARRATOR [excited]: I posted one tiny clip before sleeping.\nCHARACTER1 [happy]: When I woke up, it had two million views.\nCHARACTER2 [confused]: The comments were arguing about my toaster.\nNARRATOR [funny]: That was the day I learned the internet chooses its own main character.",
    70	        },
    71	        "AI facts": {
    72	            "title": "AI Facts That Sound Fake",
    73	            "script": "NARRATOR [curious]: AI can now make videos from a few words.\nCHARACTER1 [surprised]: It can clone styles, voices, and scenes with open-source tools.\nCHARACTER2 [calm]: But free tools still sleep, break, and need patience.\nNARRATOR [confident]: The best workflow is simple, cached, and easy to rerun.",
    74	        },
    75	        "Hindi/English mix": {
    76	            "title": "Free AI Reels Ka Secret",
    77	            "script": "NARRATOR [excited]: Aaj main free AI reels workflow dikhane wala hoon.\nCHARACTER1 [happy]: Voice free, captions free, aur backgrounds optional Colab se.\nCHARACTER2 [serious]: Bas paid API key ki zaroorat nahi hai.\nNARRATOR [confident]: Script daalo, style choose karo, aur video generate karo.",
    78	        },
    79	    }
    80	    return samples.get(kind, samples["Conspiracy"])
    81	