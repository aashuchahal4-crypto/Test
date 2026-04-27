import os
import random
import shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple

import gradio as gr

from ai_backgrounds import create_gradient_background, generate_ai_background
from presets import BACKGROUND_MODES, CAPTION_ANIMATIONS, CAPTION_POSITIONS, CAPTION_STYLES, PRESET_RECOMMENDATIONS, TRANSITIONS, VISUAL_STYLE_PRESETS
from scene_engine import DEFAULT_NEGATIVE_PROMPT, DEFAULT_VISUAL_THEME, build_scenes, enhance_prompt
from script_generator import generate_sample_script, parse_custom_script
from tiktok_tts import VOICES
from video_generator import generate_video

ASSETS = Path("assets")
FOOTAGE_DIR = ASSETS / "footage"
MUSIC_DIR = ASSETS / "music"
CHARACTER_DIR = ASSETS / "characters"
UPLOAD_DIR = ASSETS / "uploads"
OUTPUT_AI_DIR = Path("outputs/ai_backgrounds")

for folder in (FOOTAGE_DIR, MUSIC_DIR, ASSETS / "fonts", CHARACTER_DIR, UPLOAD_DIR, OUTPUT_AI_DIR):
    folder.mkdir(parents=True, exist_ok=True)


def _choices_from_folder(folder: Path, extensions: Tuple[str, ...], random_label: str, none_label: str = "None") -> List[str]:
    files = sorted(str(p) for p in folder.glob("*") if p.suffix.lower() in extensions)
    return [random_label, none_label] + files


def footage_choices() -> List[str]:
    return _choices_from_folder(FOOTAGE_DIR, (".mp4", ".mov", ".webm"), "🎲 Random asset video")


def music_choices() -> List[str]:
    return _choices_from_folder(MUSIC_DIR, (".mp3", ".wav", ".m4a", ".aac"), "🎲 Random music")


def character_choices() -> List[str]:
    return _choices_from_folder(CHARACTER_DIR, (".png", ".webp", ".jpg", ".jpeg"), "🎲 Random character")


def _pick_asset(value: str, folder: Path, extensions: Tuple[str, ...]) -> str | None:
    if not value or value == "None":
        return None
    files = sorted(str(p) for p in folder.glob("*") if p.suffix.lower() in extensions)
    if value.startswith("🎲 Random"):
        return random.choice(files) if files else None
    return value if Path(value).exists() else None


def _file_path(file_obj: Any) -> str | None:
    if not file_obj:
        return None
    if isinstance(file_obj, str):
        return file_obj
    return getattr(file_obj, "name", None) or getattr(file_obj, "path", None)


def _save_upload(file_obj: Any, prefix: str) -> str | None:
    src = _file_path(file_obj)
    if not src or not Path(src).exists():
        return None
    dest = UPLOAD_DIR / f"{prefix}_{Path(src).name}"
    shutil.copy(src, dest)
    return str(dest)


def _build_ai_backgrounds(
    title: str,
    dialogues: List[Dict[str, Any]],
    background_mode: str,
    ai_endpoint_url: str,
    visual_theme_prompt: str,
    negative_prompt: str,
    visual_style_preset: str,
    seed: int,
    guidance_scale: float,
    max_ai_scenes: int,
    gradient_color_a: str,
    gradient_color_b: str,
) -> Tuple[Any, List[str]]:
    status: List[str] = []
    if background_mode not in {"Single AI Image", "AI Scene Images"}:
        return None, status
    endpoint = (ai_endpoint_url or os.getenv("AI_IMAGE_API_URL") or "").strip()
    if not endpoint:
        status.append("AI endpoint not configured; using gradient/asset fallback.")
        return None, status
    if background_mode == "Single AI Image":
        prompt = enhance_prompt(title, "overall mood of the whole reel", "neutral", visual_theme_prompt, visual_style_preset, "NARRATOR")
        path, msg = generate_ai_background(prompt, negative_prompt, endpoint, int(seed), float(guidance_scale), output_dir=OUTPUT_AI_DIR)
        status.append(msg)
        if path:
            return [{"path": path, "source_indices": [i for i in range(len(dialogues))]}], status
        fallback = create_gradient_background(OUTPUT_AI_DIR / "fallback_single.png", gradient_color_a, gradient_color_b)
        return [{"path": fallback, "source_indices": [i for i in range(len(dialogues))]}], status
    scenes = build_scenes(dialogues, title, visual_theme_prompt, visual_style_preset, max_ai_scenes=max_ai_scenes)
    generated = []
    previous = None
    fallback = create_gradient_background(OUTPUT_AI_DIR / "fallback_scene.png", gradient_color_a, gradient_color_b)
    for scene in scenes:
        path, msg = generate_ai_background(str(scene["prompt"]), negative_prompt, endpoint, int(seed), float(guidance_scale), output_dir=OUTPUT_AI_DIR)
        status.append(f"Scene {scene['index'] + 1}: {msg}")
        if not path:
            path = previous or fallback
        previous = path
        generated.append({"path": path, "source_indices": scene.get("source_indices", [scene["index"]]), "prompt": scene["prompt"]})
    return generated, status


def generate_from_custom_script(
    title,
    custom_script,
    voice_narrator,
    voice1,
    voice2,
    bg_video,
    bg_music,
    char_overlay1,
    char_overlay2,
    caption_style,
    background_mode="Solid/Gradient",
    uploaded_bg_video=None,
    uploaded_bg_music=None,
    caption_position="Center",
    caption_animation="None",
    show_title=True,
    transition_style="Cut",
    bg_music_volume=0.16,
    voice_volume=1.0,
    ai_endpoint_url="",
    visual_theme_prompt=DEFAULT_VISUAL_THEME,
    negative_prompt=DEFAULT_NEGATIVE_PROMPT,
    visual_style_preset="cinematic",
    seed=-1,
    guidance_scale=7.5,
    max_ai_scenes=6,
    gradient_color_a="#161629",
    gradient_color_b="#ff3b7f",
    char_asset1="None",
    char_asset2="None",
    progress=gr.Progress(),
):
    try:
        title = (title or "Untitled Reel").strip()
        custom_script = (custom_script or "").strip()
        if not custom_script:
            return None, "Add a script first."
        progress(0.05, desc="Parsing script")
        dialogues = parse_custom_script(custom_script)
        if not dialogues:
            return None, "Script parsing failed. Use JSON, Speaker: Dialogue, or Speaker [emotion]: Dialogue."

        selected_bg_video = None
        if background_mode == "Upload Video":
            selected_bg_video = _save_upload(uploaded_bg_video, "background")
            if not selected_bg_video:
                background_mode = "Solid/Gradient"
        elif background_mode == "Asset Video":
            selected_bg_video = _pick_asset(bg_video, FOOTAGE_DIR, (".mp4", ".mov", ".webm"))
            if not selected_bg_video:
                background_mode = "Solid/Gradient"

        selected_music = _save_upload(uploaded_bg_music, "music") or _pick_asset(bg_music, MUSIC_DIR, (".mp3", ".wav", ".m4a", ".aac"))
        char1 = _save_upload(char_overlay1, "character1") or _pick_asset(char_asset1, CHARACTER_DIR, (".png", ".webp", ".jpg", ".jpeg"))
        char2 = _save_upload(char_overlay2, "character2") or _pick_asset(char_asset2, CHARACTER_DIR, (".png", ".webp", ".jpg", ".jpeg"))

        progress(0.16, desc="Preparing optional AI backgrounds")
        generated_backgrounds, ai_status = _build_ai_backgrounds(
            title,
            dialogues,
            background_mode,
            ai_endpoint_url,
            visual_theme_prompt,
            negative_prompt,
            visual_style_preset,
            int(seed),
            float(guidance_scale),
            int(max_ai_scenes),
            gradient_color_a,
            gradient_color_b,
        )

        progress(0.36, desc="Generating voices and composing video")
        output = generate_video(
            title,
            custom_script,
            voice_narrator=voice_narrator,
            voice1=voice1,
            voice2=voice2,
            bg_video=selected_bg_video,
            bg_music=selected_music,
            char_overlay1=char1,
            char_overlay2=char2,
            caption_style=caption_style,
            background_mode=background_mode,
            generated_backgrounds=generated_backgrounds,
            caption_position=caption_position,
            caption_animation=caption_animation,
            show_title=show_title,
            transition_style=transition_style,
            bg_music_volume=float(bg_music_volume),
            voice_volume=float(voice_volume),
            gradient_color_a=gradient_color_a,
            gradient_color_b=gradient_color_b,
        )
        progress(1.0, desc="Done")
        status = [f"Generated {len(dialogues)} voiced segment(s).", f"Background mode: {background_mode}."] + ai_status
        if not selected_music:
            status.append("No background music selected; narration-only audio used.")
        return output, "\n".join(status)
    except Exception as exc:
        return None, f"Generation failed: {exc}"


def apply_preset(name: str):
    sample = generate_sample_script(name)
    rec = PRESET_RECOMMENDATIONS.get(name, {})
    return sample["title"], sample["script"], rec.get("caption_style", "MrBeast Yellow"), rec.get("background_mode", "Solid/Gradient"), rec.get("visual_style", "cinematic")


with gr.Blocks(theme=gr.themes.Soft(), title="Free AI Reel Generator") as demo:
    gr.Markdown(
        """
        # Free AI Reel Generator
        Lightweight Gradio MVP for script → scenes → free TTS → captions → FFmpeg vertical reels. It runs without paid API keys. AI image backgrounds are optional and only call your own free Colab/FastAPI/ngrok-compatible endpoint.
        """
    )
    with gr.Row():
        with gr.Column(scale=5):
            with gr.Tab("1. Script"):
                preset = gr.Dropdown(["Conspiracy", "Storytime", "AI facts", "Hindi/English mix"], value="Conspiracy", label="Sample script preset")
                apply_btn = gr.Button("Load preset")
                title = gr.Textbox(label="Video title", value="The Algorithm Knows Too Much")
                custom_script = gr.Textbox(
                    label="Custom script",
                    lines=12,
                    value=generate_sample_script("Conspiracy")["script"],
                    info="Supports JSON, Speaker: Dialogue, and Speaker [emotion]: Dialogue.",
                )
            with gr.Tab("2. Voices & audio"):
                voice_names = list(VOICES.keys())
                voice_narrator = gr.Dropdown(voice_names, value=voice_names[0], label="Narrator voice")
                voice1 = gr.Dropdown(voice_names, value=voice_names[1], label="Character 1 voice")
                voice2 = gr.Dropdown(voice_names, value=voice_names[2], label="Character 2 voice")
                gr.Markdown("English uses the existing free TikTok-style path with free fallbacks. Hindi/Devanagari routes to Edge TTS/gTTS fallback. Emotion tags influence Hindi rate/pitch.")
                bg_music = gr.Dropdown(music_choices(), value="🎲 Random music", label="Asset background music")
                uploaded_bg_music = gr.File(label="Upload background music (.mp3/.wav)", file_types=[".mp3", ".wav", ".m4a", ".aac"])
                bg_music_volume = gr.Slider(0, 1, value=0.16, step=0.01, label="Background music volume")
                voice_volume = gr.Slider(0.5, 2.0, value=1.0, step=0.05, label="Voice volume")
            with gr.Tab("3. Visual style"):
                caption_style = gr.Dropdown(CAPTION_STYLES, value="MrBeast Yellow", label="Caption style")
                caption_position = gr.Dropdown(CAPTION_POSITIONS, value="Center", label="Caption position")
                caption_animation = gr.Dropdown(CAPTION_ANIMATIONS, value="Pop", label="Caption animation")
                show_title = gr.Checkbox(value=True, label="Show title card overlay")
                transition_style = gr.Dropdown(TRANSITIONS, value="Cut", label="Scene transition")
                gradient_color_a = gr.ColorPicker(value="#161629", label="Gradient color A")
                gradient_color_b = gr.ColorPicker(value="#ff3b7f", label="Gradient color B")
            with gr.Tab("4. Backgrounds"):
                background_mode = gr.Dropdown(BACKGROUND_MODES, value="Solid/Gradient", label="Background mode")
                bg_video = gr.Dropdown(footage_choices(), value="🎲 Random asset video", label="Asset background video")
                uploaded_bg_video = gr.File(label="Upload background video (.mp4/.mov)", file_types=[".mp4", ".mov", ".webm"])
                gr.Markdown("AI backgrounds are optional. Paste a user-run free Colab/FastAPI/ngrok/localtunnel/cloudflared endpoint, or leave blank for gradient/asset fallback.")
                ai_endpoint_url = gr.Textbox(label="AI image endpoint URL", placeholder="https://your-free-tunnel.ngrok-free.app/generate")
                visual_style_preset = gr.Dropdown(VISUAL_STYLE_PRESETS, value="cinematic", label="Prompt style preset")
                visual_theme_prompt = gr.Textbox(label="Visual theme/style prompt", lines=3, value=DEFAULT_VISUAL_THEME)
                negative_prompt = gr.Textbox(label="Negative prompt", lines=2, value=DEFAULT_NEGATIVE_PROMPT)
                with gr.Row():
                    seed = gr.Number(value=-1, precision=0, label="Seed (-1 random)")
                    guidance_scale = gr.Slider(1, 15, value=7.5, step=0.5, label="Guidance scale")
                    max_ai_scenes = gr.Slider(1, 12, value=6, step=1, label="Max AI scenes")
            with gr.Tab("5. Characters"):
                char_asset1 = gr.Dropdown(character_choices(), value="None", label="Character 1 asset")
                char_overlay1 = gr.File(label="Upload Character 1 overlay PNG/WebP (takes priority)", file_types=[".png", ".webp", ".jpg", ".jpeg"])
                char_asset2 = gr.Dropdown(character_choices(), value="None", label="Character 2 asset")
                char_overlay2 = gr.File(label="Upload Character 2 overlay PNG/WebP (takes priority)", file_types=[".png", ".webp", ".jpg", ".jpeg"])
            with gr.Tab("6. Export/output"):
                generate_btn = gr.Button("Generate free AI reel", variant="primary", size="lg")
        with gr.Column(scale=4):
            output_video = gr.Video(label="Generated vertical reel")
            status = gr.Textbox(label="Status", lines=12)

    apply_btn.click(apply_preset, inputs=[preset], outputs=[title, custom_script, caption_style, background_mode, visual_style_preset])
    generate_btn.click(
        generate_from_custom_script,
        inputs=[
            title,
            custom_script,
            voice_narrator,
            voice1,
            voice2,
            bg_video,
            bg_music,
            char_overlay1,
            char_overlay2,
            caption_style,
            background_mode,
            uploaded_bg_video,
            uploaded_bg_music,
            caption_position,
            caption_animation,
            show_title,
            transition_style,
            bg_music_volume,
            voice_volume,
            ai_endpoint_url,
            visual_theme_prompt,
            negative_prompt,
            visual_style_preset,
            seed,
            guidance_scale,
            max_ai_scenes,
            gradient_color_a,
            gradient_color_b,
            char_asset1,
            char_asset2,
        ],
        outputs=[output_video, status],
    )

if __name__ == "__main__":
    demo.launch()
