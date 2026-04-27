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
OVERLAY_DIRS = [ASSETS_DIR / "overlays", ASSETS_DIR / "characters"]
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

MUSIC_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
AUTO_ASSET = "Auto / first available"
NONE_ASSET = "None"
AUTO_MUSIC_MODE = "Auto music (downloaded/default)"
SELECTED_MUSIC_MODE = "Uploaded/selected music"
NO_MUSIC_MODE = "No music"


PLAIN_STORY_EXAMPLE = """The old lighthouse blinked through the storm. Mira climbed the spiral stairs with a lantern in her hand. At the top, she found a tiny silver compass pointing toward the sea."""

CUSTOM_SCRIPT_EXAMPLE = """NARRATOR: The city slept under a purple sky.
HERO: I found the map. Now we just need courage.
VILLAIN: Courage will not open that gate.
HERO: Then we will find the key."""


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


def _asset_files(asset_dirs, extensions):
    dirs = asset_dirs if isinstance(asset_dirs, (list, tuple)) else [asset_dirs]
    files = []
    for asset_dir in dirs:
        if not asset_dir.exists():
            continue
        files.extend([
            p for p in asset_dir.iterdir()
            if p.is_file() and p.suffix.lower() in extensions and p.stat().st_size > 0
        ])
    return sorted(files, key=lambda p: p.name.lower())


def _asset_names(asset_dirs, extensions):
    names = []
    seen = set()
    for path in _asset_files(asset_dirs, extensions):
        if path.name not in seen:
            names.append(path.name)
            seen.add(path.name)
    return names


def _background_video_choices():
    return [AUTO_ASSET, NONE_ASSET] + _asset_names(FOOTAGE_DIR, VIDEO_EXTENSIONS)


def _music_choices():
    return [AUTO_ASSET, NONE_ASSET] + _asset_names(MUSIC_DIR, MUSIC_EXTENSIONS)


def _character_choices():
    return [NONE_ASSET] + _asset_names(OVERLAY_DIRS, IMAGE_EXTENSIONS)


def refresh_background_choices():
    return gr.update(choices=_background_video_choices(), value=AUTO_ASSET)


def refresh_music_choices():
    return gr.update(choices=_music_choices(), value=AUTO_ASSET)


def refresh_character_choices():
    return gr.update(choices=_character_choices(), value=NONE_ASSET)


def _resolve_asset(selection, asset_dirs, extensions, auto_first=False):
    files = _asset_files(asset_dirs, extensions)
    if selection == AUTO_ASSET:
        return str(files[0]) if auto_first and files else None
    if not selection or selection == NONE_ASSET:
        return None
    for path in files:
        if path.name == selection:
            return str(path)
    return None


def _background_video_path(upload, selected_background_video):
    uploaded = _file_path(upload)
    if uploaded:
        return uploaded
    return _resolve_asset(selected_background_video, FOOTAGE_DIR, VIDEO_EXTENSIONS, auto_first=True)


def _music_path(mode, upload, selected_music):
    uploaded = _file_path(upload)
    if uploaded:
        return uploaded
    if mode == NO_MUSIC_MODE:
        return None
    if mode == SELECTED_MUSIC_MODE and selected_music == AUTO_ASSET:
        return None
    return _resolve_asset(selected_music, MUSIC_DIR, MUSIC_EXTENSIONS, auto_first=mode == AUTO_MUSIC_MODE)


def _character_overlay_path(upload, selected_character):
    uploaded = _file_path(upload)
    if uploaded:
        return uploaded
    return _resolve_asset(selected_character, OVERLAY_DIRS, IMAGE_EXTENSIONS, auto_first=False)


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


def build_story_video(docx_file, raw_text, title, custom_script_mode, narrator_voice, voice_override_text, caption_style, aspect_ratio, use_whisper_sync, visual_mode, bg_video_file, selected_background_video, music_mode, music_file, selected_music, character_overlay_file, selected_character, max_chars, progress=gr.Progress(track_tqdm=True)):
    status = []
    progress_state = {"value": 0.0, "tts": 0, "render": 0}

    def note(message):
        status.append(str(message))

    def set_progress(value, description):
        value = max(progress_state["value"], min(1.0, float(value)))
        progress_state["value"] = value
        if progress:
            progress(value, desc=description)

    try:
        note("Started generation… follow the progress bar and detailed status below.")
        set_progress(0.02, "Extracting input")
        story_text, input_note = combine_inputs(_file_path(docx_file), raw_text)
        note(f"Input: {input_note}")
        set_progress(0.10, "Segmenting scenes")
        dialogues, segmentation_note = segment_story(story_text, max_chars=int(max_chars or 110), custom_script_mode=custom_script_mode)
        if not dialogues:
            raise ValueError("No scenes were produced from the input story")
        lang = detect_language(story_text)
        note(f"Segmentation: {len(dialogues)} scenes using {segmentation_note}; language={lang}")
        set_progress(0.18, "Assigning voices and options")
        voice_assignments = assign_voices_to_characters(dialogues, VOICES)
        if narrator_voice:
            voice_assignments["NARRATOR"] = narrator_voice
        voice_assignments.update(_parse_voice_overrides(voice_override_text))
        note("Voice/style: narrator and speaker voices are ready")

        run_id = uuid.uuid4().hex
        output_path = OUTPUT_DIR / f"storyteller_{run_id}.mp4"
        char_overlay = _character_overlay_path(character_overlay_file, selected_character)
        if char_overlay:
            note(f"Character: using {os.path.basename(char_overlay)}")
        else:
            note("Character: no overlay selected")
        bg_video_path = None
        scene_background_paths = None

        with tempfile.TemporaryDirectory(prefix="story_assets_") as tmp:
            set_progress(0.25, "Generating backgrounds or selecting visuals")
            if visual_mode == "Generated scene cards":
                note("Visuals: generating clean visual-only scene cards; captions are rendered once by the caption overlay")
                scene_background_paths = generate_scene_backgrounds(dialogues, os.path.join(tmp, "backgrounds"), aspect_ratio=aspect_ratio, title=_safe_title(title))
            elif visual_mode == "Uploaded/random video":
                bg_video_path = _background_video_path(bg_video_file, selected_background_video)
                if bg_video_path:
                    note(f"Visuals: using background video {os.path.basename(bg_video_path)}")
                else:
                    note("Visuals: no uploaded or existing video found; renderer will use a neutral generated color")
            else:
                note("Visuals: using neutral renderer background")

            set_progress(0.35, "Selecting music and setting timing")
            bg_music_path = _music_path(music_mode, music_file, selected_music)
            if bg_music_path:
                note(f"Music: using {os.path.basename(bg_music_path)}")
            else:
                note("Music: disabled")

            timing_messages = []
            total = max(1, len(dialogues))

            def timing_status(message):
                timing_messages.append(message)
                note(f"Timing: {message}")

            def render_progress_callback(message):
                text = str(message)
                note(text)
                if text.startswith("TTS/audio"):
                    progress_state["tts"] += 1
                    set_progress(0.35 + min(progress_state["tts"], total) / total * 0.25, text)
                elif text.startswith("Timing alignment"):
                    set_progress(0.64, text)
                elif text.startswith("Caption/background render"):
                    progress_state["render"] += 1
                    set_progress(0.65 + min(progress_state["render"], total) / total * 0.23, text)
                elif text.startswith("Final FFmpeg export"):
                    set_progress(0.90, "Final render/export")
                else:
                    set_progress(progress_state["value"] + 0.01, text)

            result_file = generate_video(
                _safe_title(title), None, None, bg_video_path, bg_music_path, MASTER_FONT_PATH, None, str(output_path),
                dialogues=dialogues, voice_assignments=voice_assignments, video_title=_safe_title(title),
                character_overlay=char_overlay, progress_callback=render_progress_callback, caption_style=caption_style,
                aspect_ratio=aspect_ratio, scene_background_paths=scene_background_paths,
                use_whisper_sync=bool(use_whisper_sync), timing_status_callback=timing_status,
            )
        if use_whisper_sync and not timing_messages:
            note("Timing: fallback timing used")
        set_progress(1.0, "Complete")
        note(f"Complete: exported {result_file}")
        note(f"Output saved to: {result_file}")
        return result_file, "\n".join(status)
    except Exception as exc:
        if progress:
            progress(progress_state["value"], desc="Error")
        message = str(exc)
        if "No story text" in message or "Story text is empty" in message or "No scenes" in message:
            note("Error: Add text in Raw story/script or upload a DOCX, then click Generate.")
        else:
            note(f"Error: {message}")
            note("Fix the highlighted input or asset choice, then click Generate again.")
        return None, "\n".join(status)


with gr.Blocks(title="AI Audio Storyteller", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# AI Audio Storyteller")
    gr.Markdown(
        """
<div style="border:1px solid #d8e1ff;border-radius:16px;padding:16px;background:#f7f9ff">
<b>How to make a story video</b><br>
1. Upload a DOCX or paste your story/script.<br>
2. Choose how the text should be split into scenes.<br>
3. Pick the narrator voice, caption style, and aspect ratio.<br>
4. Choose generated cards, or upload/select background video, music, and character assets.<br>
5. Click <b>Generate story video</b> and watch the progress bar plus status log.
</div>
"""
    )
    with gr.Accordion("What each mode means", open=True):
        gr.Markdown(
            """
- **Segmentation mode**: **Auto** detects speaker lines when your text looks like a script. **Narrator story** treats everything as one narrator. **Custom script** expects lines like `HERO: We made it!`.
- **Background mode**: **Generated scene cards** creates clean visual-only cards for each scene; caption text appears only in the caption overlay. **Uploaded/random video** uses your upload first, then a selected/existing video from `assets/footage`, then a neutral fallback. **Neutral** uses a simple generated background.
- **Whisper timing sync**: Optional. Leave it off for faster generation. If it is unavailable, the app falls back to normal timing.
"""
        )
    with gr.Accordion("Examples you can paste", open=False):
        gr.Markdown(f"**Plain story example**\n\n```text\n{PLAIN_STORY_EXAMPLE}\n```\n\n**Custom script example**\n\n```text\n{CUSTOM_SCRIPT_EXAMPLE}\n```")
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 1. Input")
            docx_file = gr.File(
                label="Upload DOCX story",
                file_types=[".docx"],
                info="Optional. Upload a Word document with readable paragraphs; pasted text below can also be used."
            )
            raw_text = gr.Textbox(
                label="Raw story/script text",
                lines=12,
                placeholder="Paste a plain story, or script lines like HERO: We found the key...",
                info="Use plain paragraphs for narrator mode, or SPEAKER: dialogue lines for custom scripts."
            )
            title = gr.Textbox(label="Video title", value="AI Audio Story", info="Used in generated scene cards and output metadata.")
            custom_script_mode = gr.Radio(
                ["Auto", "Narrator story", "Custom script"],
                value="Auto",
                label="How should the story be split?",
                info="Auto detects speaker scripts; Narrator story forces one narrator; Custom script expects SPEAKER: lines."
            )
            max_chars = gr.Slider(
                70,
                120,
                value=110,
                step=5,
                label="Caption scene length",
                info="Lower values create shorter captions and more scenes."
            )
        with gr.Column(scale=1):
            gr.Markdown("### 2. Voice and captions")
            narrator_voice = gr.Dropdown(
                VOICE_CHOICES,
                value="en_us_001",
                label="Narrator voice",
                info="Main voice used for narrator scenes. Custom speaker voices can override this."
            )
            voice_override_text = gr.Textbox(
                label="Speaker voice overrides",
                lines=3,
                placeholder="NARRATOR=en_us_001\nHERO=hi-IN-SwaraNeural",
                info="Optional. One SPEAKER=voice_id per line; speaker names match your script labels."
            )
            caption_style = gr.Dropdown(CAPTION_STYLES, value="Gradient-Pop", label="Caption style", info="Visual style for subtitles on every scene.")
            aspect_ratio = gr.Radio(["9:16", "16:9", "1:1"], value="9:16", label="Video size", info="9:16 is best for TikTok/Reels/Shorts; 16:9 is landscape; 1:1 is square.")
            use_whisper_sync = gr.Checkbox(label="Use Whisper timing sync", value=False, info="Optional and slower. Leave off unless you need word-level timing improvements.")
            gr.Markdown("### 3. Visuals and assets")
            visual_mode = gr.Radio(
                ["Generated scene cards", "Uploaded/random video", "Neutral"],
                value="Generated scene cards",
                label="Background mode",
                info="Generated cards are visual-only and need no assets. Uploaded/random video uses uploads or existing files from assets/footage."
            )
            bg_video_file = gr.File(label="Upload background video", file_types=[".mp4", ".mov", ".mkv", ".webm"], info="Optional. Uploaded video overrides the existing video dropdown.")
            selected_background_video = gr.Dropdown(
                _background_video_choices(),
                value=AUTO_ASSET,
                label="Existing background video",
                info="Files are loaded from assets/footage. Use None to force no existing video."
            )
            refresh_bg = gr.Button("Refresh background list", size="sm")
            music_mode = gr.Radio(
                [AUTO_MUSIC_MODE, SELECTED_MUSIC_MODE, NO_MUSIC_MODE],
                value=AUTO_MUSIC_MODE,
                label="Background music mode",
                info="Auto uses the first downloaded/default music file when available; uploads override dropdown choices."
            )
            music_file = gr.File(label="Upload music", file_types=[".mp3", ".wav", ".m4a", ".aac"], info="Optional. Uploaded music overrides the existing music dropdown.")
            selected_music = gr.Dropdown(
                _music_choices(),
                value=AUTO_ASSET,
                label="Existing music",
                info="Files are loaded from assets/music. Choose None or No music to disable music."
            )
            refresh_music = gr.Button("Refresh music list", size="sm")
            character_overlay_file = gr.File(label="Upload character image", file_types=[".png", ".jpg", ".jpeg", ".webp"], info="Optional transparent PNG/JPG/WebP overlay. Upload overrides the existing character dropdown.")
            selected_character = gr.Dropdown(
                _character_choices(),
                value=NONE_ASSET,
                label="Existing character image",
                info="Files are loaded from assets/overlays and assets/characters. Choose None for no character overlay."
            )
            refresh_character = gr.Button("Refresh character list", size="sm")
            generate_btn = gr.Button("Generate story video", variant="primary")
    gr.Markdown("### 4. Output")
    status = gr.Textbox(label="Progress/status log", lines=14, info="Detailed step-by-step messages, errors, and the final output path appear here.")
    preview = gr.Video(label="MP4 preview")

    refresh_bg.click(refresh_background_choices, inputs=None, outputs=selected_background_video)
    refresh_music.click(refresh_music_choices, inputs=None, outputs=selected_music)
    refresh_character.click(refresh_character_choices, inputs=None, outputs=selected_character)

    generate_btn.click(
        build_story_video,
        inputs=[docx_file, raw_text, title, custom_script_mode, narrator_voice, voice_override_text, caption_style, aspect_ratio, use_whisper_sync, visual_mode, bg_video_file, selected_background_video, music_mode, music_file, selected_music, character_overlay_file, selected_character, max_chars],
        outputs=[preview, status],
    )


if __name__ == "__main__":
    demo.queue().launch()
