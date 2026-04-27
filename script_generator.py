import json
import re
from typing import Any, Dict, List


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _normalise_line(item: Dict[str, Any], index: int) -> Dict[str, Any]:
    speaker = _clean_text(item.get("speaker") or item.get("name") or item.get("role") or "NARRATOR")
    text = _clean_text(item.get("text") or item.get("dialogue") or item.get("line") or item.get("content"))
    emotion = _clean_text(item.get("emotion") or "neutral").lower() or "neutral"
    return {"speaker": speaker.upper(), "text": text, "emotion": emotion, "index": index}


def parse_custom_script(script: str) -> List[Dict[str, Any]]:
    """Parse JSON, Speaker: Dialogue, or Speaker [emotion]: Dialogue scripts."""
    script = _clean_text(script)
    if not script:
        return []

    try:
        parsed = json.loads(script)
        if isinstance(parsed, dict):
            parsed = parsed.get("dialogue") or parsed.get("dialogues") or parsed.get("lines") or [parsed]
        if isinstance(parsed, list):
            lines = []
            for i, item in enumerate(parsed):
                if isinstance(item, str):
                    lines.extend(parse_custom_script(item))
                elif isinstance(item, dict):
                    line = _normalise_line(item, len(lines))
                    if line["text"]:
                        lines.append(line)
            if lines:
                return lines
    except Exception:
        pass

    out: List[Dict[str, Any]] = []
    pattern = re.compile(r"^\s*([A-Za-z0-9_ \-]+?)(?:\s*\[([^\]]+)\])?\s*:\s*(.+?)\s*$")
    for raw in script.splitlines():
        raw = raw.strip().strip("-•")
        if not raw:
            continue
        match = pattern.match(raw)
        if match:
            speaker, emotion, text = match.groups()
            out.append({
                "speaker": speaker.strip().upper() or "NARRATOR",
                "text": text.strip(),
                "emotion": (emotion or "neutral").strip().lower(),
                "index": len(out),
            })
        else:
            out.append({"speaker": "NARRATOR", "text": raw, "emotion": "neutral", "index": len(out)})
    return out


def generate_sample_script(kind: str = "Conspiracy") -> Dict[str, str]:
    samples = {
        "Conspiracy": {
            "title": "The Algorithm Knows Too Much",
            "script": "NARRATOR [mysterious]: What if your phone predicts what you want before you do?\nCHARACTER1 [shocked]: Bro, I only thought about pizza and suddenly ads appeared.\nCHARACTER2 [serious]: That is not magic. It is patterns, location, and your scroll history.\nNARRATOR [dramatic]: The scary part is how normal it feels now.",
        },
        "Storytime": {
            "title": "I Accidentally Went Viral",
            "script": "NARRATOR [excited]: I posted one tiny clip before sleeping.\nCHARACTER1 [happy]: When I woke up, it had two million views.\nCHARACTER2 [confused]: The comments were arguing about my toaster.\nNARRATOR [funny]: That was the day I learned the internet chooses its own main character.",
        },
        "AI facts": {
            "title": "AI Facts That Sound Fake",
            "script": "NARRATOR [curious]: AI can now make videos from a few words.\nCHARACTER1 [surprised]: It can clone styles, voices, and scenes with open-source tools.\nCHARACTER2 [calm]: But free tools still sleep, break, and need patience.\nNARRATOR [confident]: The best workflow is simple, cached, and easy to rerun.",
        },
        "Hindi/English mix": {
            "title": "Free AI Reels Ka Secret",
            "script": "NARRATOR [excited]: Aaj main free AI reels workflow dikhane wala hoon.\nCHARACTER1 [happy]: Voice free, captions free, aur backgrounds optional Colab se.\nCHARACTER2 [serious]: Bas paid API key ki zaroorat nahi hai.\nNARRATOR [confident]: Script daalo, style choose karo, aur video generate karo.",
        },
    }
    return samples.get(kind, samples["Conspiracy"])
