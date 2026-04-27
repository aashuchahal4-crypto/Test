import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

ASSETS_DIR = Path("assets")
FONTS_DIR = ASSETS_DIR / "fonts"
MUSIC_DIR = ASSETS_DIR / "music"
FOOTAGE_DIR = ASSETS_DIR / "footage"
OVERLAYS_DIR = ASSETS_DIR / "overlays"

FONT_DOWNLOADS = {
    "NotoSans-Bold.ttf": "https://github.com/notofonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Bold.ttf",
    "NotoSansDevanagari-Bold.ttf": "https://github.com/notofonts/noto-fonts/raw/main/hinted/ttf/NotoSansDevanagari/NotoSansDevanagari-Bold.ttf",
}
DEFAULT_MUSIC_DOWNLOADS = {
    "lofi_chill.mp3": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
    "upbeat_energy.mp3": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3",
}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac"}


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=False)
    except Exception:
        return None


def _download_file(url, dest, timeout=45):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.download")
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response, open(tmp, "wb") as handle:
            shutil.copyfileobj(response, handle)
        if tmp.stat().st_size == 0:
            tmp.unlink(missing_ok=True)
            return False
        tmp.replace(dest)
        return True
    except Exception:
        tmp.unlink(missing_ok=True)
        return False


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
    raise FileNotFoundError("Could not create NotoSans-Master-Bold.ttf; no compatible font found")


def download_fonts():
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    latin = FONTS_DIR / "NotoSans-Bold.ttf"
    dev = FONTS_DIR / "NotoSansDevanagari-Bold.ttf"
    if not latin.exists():
        _download_file(FONT_DOWNLOADS[latin.name], latin)
    if not latin.exists():
        _copy_font(_font_match("Noto Sans Bold") or _font_match("DejaVu Sans Bold"), latin)
    if not dev.exists():
        _download_file(FONT_DOWNLOADS[dev.name], dev)
    if not dev.exists():
        _copy_font(_font_match("Noto Sans Devanagari Bold") or _font_match("Noto Sans Bold") or _font_match("DejaVu Sans Bold"), dev)
    if not latin.exists() and dev.exists():
        shutil.copyfile(dev, latin)
    if not dev.exists() and latin.exists():
        shutil.copyfile(latin, dev)
    return _create_master_font(str(FONTS_DIR))


def _available_music_files():
    if not MUSIC_DIR.exists():
        return []
    return sorted([
        path for path in MUSIC_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS and path.stat().st_size > 0
    ])


def _generate_ambient_loop(music_path):
    try:
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=12",
            "-filter:a", "volume=0.05,afade=t=in:st=0:d=1,afade=t=out:st=11:d=1",
            "-c:a", "libmp3lame", str(music_path)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def download_bg_music():
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    FOOTAGE_DIR.mkdir(parents=True, exist_ok=True)
    OVERLAYS_DIR.mkdir(parents=True, exist_ok=True)
    for filename, url in DEFAULT_MUSIC_DOWNLOADS.items():
        music_file = MUSIC_DIR / filename
        if not music_file.exists() or music_file.stat().st_size == 0:
            _download_file(url, music_file, timeout=90)
    available = _available_music_files()
    if available:
        return str(available[0])
    music_path = MUSIC_DIR / "ambient_loop.mp3"
    if not music_path.exists():
        _generate_ambient_loop(music_path)
    return str(music_path) if music_path.exists() and music_path.stat().st_size > 0 else None
