import os
import shutil
import subprocess
from pathlib import Path

ASSETS_DIR = Path("assets")
FONTS_DIR = ASSETS_DIR / "fonts"
MUSIC_DIR = ASSETS_DIR / "music"
FOOTAGE_DIR = ASSETS_DIR / "footage"
OVERLAYS_DIR = ASSETS_DIR / "overlays"


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=False)
    except Exception:
        return None


def _font_match(pattern):
    result = _run(["fc-match", "-f", "%{file}", pattern])
    if result and result.returncode == 0 and result.stdout.strip():
        path = result.stdout.strip()
        if os.path.exists(path):
            return path
    return None


def _copy_font(source, dest):
    if source and os.path.exists(source):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(source, dest)
        return True
    return False


def _create_master_font(font_dir):
    from fontTools.ttLib import TTFont
    from fontTools.merge import Merger
    latin_font_path = os.path.join(font_dir, "NotoSans-Bold.ttf")
    devanagari_font_path = os.path.join(font_dir, "NotoSansDevanagari-Bold.ttf")
    output_path = os.path.join(font_dir, "NotoSans-Master-Bold.ttf")
    try:
        if os.path.exists(latin_font_path) and os.path.exists(devanagari_font_path):
            merger = Merger()
            merged = merger.merge([latin_font_path, devanagari_font_path])
            merged.save(output_path)
            return output_path
    except Exception:
        pass
    fallback = None
    if os.path.exists(latin_font_path):
        fallback = latin_font_path
    elif os.path.exists(devanagari_font_path):
        fallback = devanagari_font_path
    if fallback:
        shutil.copyfile(fallback, output_path)
        try:
            TTFont(output_path).save(output_path)
        except Exception:
            pass
        return output_path
    raise FileNotFoundError("Could not create NotoSans-Master-Bold.ttf; no compatible system font found")


def download_fonts():
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    latin = FONTS_DIR / "NotoSans-Bold.ttf"
    dev = FONTS_DIR / "NotoSansDevanagari-Bold.ttf"
    if not latin.exists():
        _copy_font(_font_match("Noto Sans Bold") or _font_match("DejaVu Sans Bold"), latin)
    if not dev.exists():
        _copy_font(_font_match("Noto Sans Devanagari Bold") or _font_match("Noto Sans Bold") or _font_match("DejaVu Sans Bold"), dev)
    if not latin.exists() and dev.exists():
        shutil.copyfile(dev, latin)
    if not dev.exists() and latin.exists():
        shutil.copyfile(latin, dev)
    return _create_master_font(str(FONTS_DIR))


def download_bg_music():
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    FOOTAGE_DIR.mkdir(parents=True, exist_ok=True)
    OVERLAYS_DIR.mkdir(parents=True, exist_ok=True)
    music_path = MUSIC_DIR / "ambient_loop.mp3"
    if not music_path.exists():
        try:
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=12",
                "-filter:a", "volume=0.05,afade=t=in:st=0:d=1,afade=t=out:st=11:d=1",
                "-c:a", "libmp3lame", str(music_path)
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    return str(music_path) if music_path.exists() else None
