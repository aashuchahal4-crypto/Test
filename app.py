import os
import tempfile
import uuid
from pathlib import Path

import gradio as gr

from backgrounds import generate_scene_backgrounds
from download_assets import download_bg_music, download_fonts
from script_generator import assign_voices_to_characters, detect_language
from story_inputs import combine_inputs, segment_story
from tiktok_tts import VOICES
from video_generator import CAPTION_STYLES, generate_video

ASSETS_DIR = Path("assets")
FONTS_DIR = ASSETS_DIR / "fonts"
MUSIC_DIR = ASSETS_DIR / "music"
FOOTAGE_DIR = ASSETS_DIR / "footage"
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)


def _startup_assets():
    try:
        font_path = download_fonts()
    except Exception:
        font_path = str(FONTS_DIR / "NotoSans-Master-Bold.ttf")
    try:
        download_bg_music()
    except Exception:
        pass
    return font_path


MASTER_FONT_PATH = _startup_assets()
VOICE_CHOICES = [(label, key) for key, label in VOICES.items()]


def _file_path(file_value):
    if not file_value:
        return None
    if isinstance(file_value, str):
        return file_value
    return getattr(file_value, "name", None) or getattr(file_value, "path", None)


def _first_existing(paths):
    for path in paths:
        if path and os.path.exists(path):
            return path
    return None


def _random_footage():
    if not FOOTAGE_DIR.exists():
        return None
    videos = sorted([p for p in FOOTAGE_DIR.iterdir() if p.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}])
    return str(videos[0]) if videos else None


def _music_path(mode, upload):
    uploaded = _file_path(upload)
    if uploaded:
        return uploaded
    if mode == "Default ambient":
        return _first_existing([str(MUSIC_DIR / "ambient_loop.mp3")])
    return None


def _parse_voice_overrides(text):
    mapping = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or "=" not in line:
            continue
        speaker, voice = [p.strip() for p in line.split("=", 1)]
        if speaker and voice in VOICES:
            mapping[speaker.upper()] = voice
    return mapping


def _safe_title(title):
    return (title or "AI Audio Story").strip() or "AI Audio Story"


def build_story_video(docx_file, raw_text, title, custom_script_mode, narrator_voice, voice_override_text, caption_style, aspect_ratio, use_whisper_sync, visual_mode, bg_video_file, music_mode, music_file, character_overlay_file, max_chars):
    status = []

    def note(message):
        status.append(str(message))

    try:
        note("Extraction: reading DOCX/text input")
        story_text, input_note = combine_inputs(_file_path(docx_file), raw_text)
        note(f"Input: {input_note}")
        note("Segmentation: creating line-by-line scenes")
        dialogues, segmentation_note = segment_story(story_text, max_chars=int(max_chars or 110), custom_script_mode=custom_script_mode)
        if not dialogues:
            raise ValueError("No scenes were produced from the input story")
        lang = detect_language(story_text)
        note(f"Segmentation: {len(dialogues)} scenes using {segmentation_note}; language={lang}")
        voice_assignments = assign_voices_to_characters(dialogues, VOICES)
        if narrator_voice:
            voice_assignments["NARRATOR"] = narrator_voice
        voice_assignments.update(_parse_voice_overrides(voice_override_text))
        note("Voice/style: using existing TTS voice assignment system")

        run_id = uuid.uuid4().hex
        output_path = OUTPUT_DIR / f"storyteller_{run_id}.mp4"
        char_overlay = _file_path(character_overlay_file)
        bg_video_path = None
        scene_background_paths = None

        with tempfile.TemporaryDirectory(prefix="story_assets_") as tmp:
            if visual_mode == "Generated scene cards":
                note("Visuals: generating static AI-style background cards per scene")
                scene_background_paths = generate_scene_backgrounds(dialogues, os.path.join(tmp, "backgrounds"), aspect_ratio=aspect_ratio, title=_safe_title(title))
            elif visual_mode == "Uploaded/random video":
                bg_video_path = _file_path(bg_video_file) or _random_footage()
                if bg_video_path:
                    note(f"Visuals: using background video {os.path.basename(bg_video_path)}")
                else:
                    note("Visuals: no background video found; renderer will use a neutral generated color")
            else:
                note("Visuals: using neutral renderer background")

            bg_music_path = _music_path(music_mode, music_file)
            if bg_music_path:
                note(f"Music: {os.path.basename(bg_music_path)}")
            else:
                note("Music: disabled")

            timing_messages = []

            def timing_status(message):
                timing_messages.append(message)
                note(f"Timing: {message}")

            def progress(message):
                note(message)

            result_file = generate_video(
                _safe_title(title), None, None, bg_video_path, bg_music_path, MASTER_FONT_PATH, None, str(output_path),
                dialogues=dialogues, voice_assignments=voice_assignments, video_title=_safe_title(title),
                character_overlay=char_overlay, progress_callback=progress, caption_style=caption_style,
                aspect_ratio=aspect_ratio, scene_background_paths=scene_background_paths,
                use_whisper_sync=bool(use_whisper_sync), timing_status_callback=timing_status,
            )
        if use_whisper_sync and not timing_messages:
            note("Timing: fallback timing used")
        note(f"Complete: exported {result_file}")
        return result_file, "\n".join(status)
    except Exception as exc:
        note(f"Error: {exc}")
        return None, "\n".join(status)


with gr.Blocks(title="AI Audio Storyteller", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# AI Audio Storyteller\nBuild narrated caption videos from DOCX or text while preserving the existing captions/TTS/video core.")
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### Input")
            docx_file = gr.File(label="DOCX upload", file_types=[".docx"])
            raw_text = gr.Textbox(label="Raw text / custom script", lines=12, placeholder="Paste story text, or Speaker: dialogue lines...")
            title = gr.Textbox(label="Video title", value="AI Audio Story")
            custom_script_mode = gr.Radio(["Auto", "Narrator story", "Custom script"], value="Auto", label="Segmentation mode")
            max_chars = gr.Slider(70, 120, value=110, step=5, label="Caption scene length")
        with gr.Column(scale=1):
            gr.Markdown("### Voice/style")
            narrator_voice = gr.Dropdown(VOICE_CHOICES, value="en_us_001", label="Narrator voice override")
            voice_override_text = gr.Textbox(label="Speaker voice overrides", lines=3, placeholder="NARRATOR=en_us_001\nHERO=hi-IN-SwaraNeural")
            caption_style = gr.Dropdown(CAPTION_STYLES, value="Gradient-Pop", label="Caption style")
            aspect_ratio = gr.Radio(["9:16", "16:9", "1:1"], value="9:16", label="Aspect ratio")
            use_whisper_sync = gr.Checkbox(label="Try Whisper timing sync (optional fallback if unavailable)", value=False)
            gr.Markdown("### Visuals")
            visual_mode = gr.Radio(["Generated scene cards", "Uploaded/random video", "Neutral"], value="Generated scene cards", label="Background mode")
            bg_video_file = gr.File(label="Uploaded background video", file_types=[".mp4", ".mov", ".mkv", ".webm"])
            music_mode = gr.Radio(["Default ambient", "Uploaded only", "None"], value="Default ambient", label="Background music")
            music_file = gr.File(label="Uploaded music", file_types=[".mp3", ".wav", ".m4a", ".aac"])
            character_overlay_file = gr.File(label="Character overlay image", file_types=[".png", ".jpg", ".jpeg", ".webp"])
            generate_btn = gr.Button("Generate story video", variant="primary")
    gr.Markdown("### Output")
    status = gr.Textbox(label="Progress/status", lines=14)
    preview = gr.Video(label="MP4 preview")

    generate_btn.click(
        build_story_video,
        inputs=[docx_file, raw_text, title, custom_script_mode, narrator_voice, voice_override_text, caption_style, aspect_ratio, use_whisper_sync, visual_mode, bg_video_file, music_mode, music_file, character_overlay_file, max_chars],
        outputs=[preview, status],
    )


if __name__ == "__main__":
    demo.queue().launch()
