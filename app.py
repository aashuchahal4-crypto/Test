from __future__ import annotations

from pathlib import Path

import gradio as gr
from fastapi import FastAPI
from pydantic import BaseModel

from local_ai import generate_script, npu_status_markdown
from npu_runtime import get_npu_status
from script_generator import format_dialogue_preview, parse_dialogue
from video_generator import generate_video, list_music

EXAMPLE_SCRIPT = """NARRATOR: The city went silent.
Alex [shocked]: Wait, why is the sky green?
NARRATOR: Rain started falling sideways as Alex ran toward the park.
Maya [happy]: I found the glowing door!
"""

JSON_EXAMPLE = '[{"speaker":"NARRATOR","text":"The classroom lights flickered.","emotion":"calm"},{"speaker":"Alex","text":"Why is everyone floating?","emotion":"shocked","gender":"male"}]'

app = FastAPI(title="Stickman Brainrot Storyteller", version="1.0.0")


class GenerateRequest(BaseModel):
    script: str
    title: str = "Brainrot Story"
    aspect_ratio: str = "9:16"
    narrator_voice: str = "storyteller"
    caption_style: str = "Bottom captions"
    background_music: str = "None"


class ScriptRequest(BaseModel):
    prompt: str
    character: str = "Alex"


@app.get("/api/status")
def api_status():
    return get_npu_status().__dict__


@app.post("/api/generate-script")
def api_generate_script(request: ScriptRequest):
    return generate_script(request.prompt, request.character)


@app.post("/api/generate")
def api_generate(request: GenerateRequest):
    path, status = generate_video(request.script, request.title, request.aspect_ratio, request.narrator_voice, request.caption_style, request.background_music)
    return {"video_path": path, "status": status}


def _refresh_music():
    return gr.update(choices=list_music(), value="None")


def _preview_parse(script: str) -> str:
    lines = parse_dialogue(script)
    if not lines:
        return "No lines parsed yet."
    return format_dialogue_preview(lines)


def _make_script(prompt: str, character: str) -> tuple[str, str]:
    result = generate_script(prompt, character or "Alex")
    status = result.get("status", {})
    provider = status.get("selected_provider", "CPUExecutionProvider")
    used = "ONNX adapter" if result.get("used_model") else "deterministic local fallback"
    return result["script"], f"Generated with {used}. Provider preference: {provider}."


def _generate(script: str, title: str, aspect_ratio: str, narrator_voice: str, caption_style: str, background_music: str, progress=gr.Progress(track_tqdm=False)):
    return generate_video(script, title, aspect_ratio, narrator_voice, caption_style, background_music, progress)


def build_ui() -> gr.Blocks:
    css = """
    .gradio-container { max-width: 1180px !important; margin: auto !important; }
    #status-box textarea, #parse-preview textarea { font-size: 12px; }
    .compact-panel { border-radius: 16px; padding: 10px; }
    .small-note { color: #9ca3af; font-size: 12px; }
    """
    with gr.Blocks(css=css, title="Stickman Brainrot Storyteller", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# Stickman Brainrot Storyteller\nLocal Python video generator with dynamic stickman scenes, captions, TTS, and NPU-ready ONNX Runtime adapters.")
        with gr.Row():
            npu_status = gr.Markdown(npu_status_markdown(), elem_id="status-box")
            refresh_status = gr.Button("Refresh backend/NPU status", size="sm")
        refresh_status.click(lambda: npu_status_markdown(), outputs=npu_status)

        with gr.Tabs():
            with gr.Tab("Brainrot Video Generator"):
                with gr.Row():
                    with gr.Column(scale=5):
                        title = gr.Textbox(label="Title", value="Brainrot Story", placeholder="Video title overlay")
                        script = gr.Textbox(
                            label="Dialogue Script",
                            value=EXAMPLE_SCRIPT,
                            lines=13,
                            placeholder="NARRATOR: The city went silent.\nAlex [shocked]: Wait, why is the sky green?\nPlain fallback line as narrator.\nOr paste JSON dialogue arrays with speaker/text/emotion/gender fields.",
                        )
                        with gr.Row():
                            parse_btn = gr.Button("Preview parsed dialogue", size="sm")
                            generate_btn = gr.Button("Generate Stickman Video", variant="primary")
                        parse_preview = gr.Textbox(label="Parsed dialogue", lines=6, interactive=False, elem_id="parse-preview")
                    with gr.Column(scale=3):
                        aspect = gr.Dropdown(["9:16", "16:9", "1:1"], value="9:16", label="Aspect Ratio")
                        narrator_voice = gr.Dropdown(["storyteller", "calm", "dramatic", "energetic"], value="storyteller", label="Narrator Voice")
                        captions = gr.Dropdown(["Bottom captions", "Top captions"], value="Bottom captions", label="Caption Style")
                        music = gr.Dropdown(list_music(), value="None", label="Background Music (optional)")
                        with gr.Row():
                            refresh_music = gr.Button("Refresh music", size="sm")
                        gr.Markdown("No gameplay footage or character PNG overlay is required. Visuals are generated stickman scenes driven by dialogue text and emotion tags.", elem_classes=["small-note"])
                video = gr.Video(label="Video Preview / Download", interactive=False)
                status = gr.Textbox(label="Generation Status", lines=5, interactive=False)
                parse_btn.click(_preview_parse, inputs=script, outputs=parse_preview)
                refresh_music.click(_refresh_music, outputs=music)
                generate_btn.click(_generate, inputs=[script, title, aspect, narrator_voice, captions, music], outputs=[video, status])

            with gr.Tab("AI Audio Storyteller"):
                gr.Markdown("Generate a local dialogue draft, then send it to the video tab. If `LOCAL_LLM_ONNX_PATH` is configured, the backend can load an ONNX model through ONNX Runtime providers; otherwise it uses a deterministic fallback.")
                with gr.Row():
                    prompt = gr.Textbox(label="Story Prompt", value="a strange city where the sky turns green", lines=4)
                    character = gr.Textbox(label="Main Character", value="Alex")
                story_btn = gr.Button("Generate Dialogue Draft", variant="primary")
                generated_script = gr.Textbox(label="Generated Dialogue", lines=10, value=JSON_EXAMPLE)
                story_status = gr.Textbox(label="Local AI Status", lines=3, interactive=False)
                story_btn.click(_make_script, inputs=[prompt, character], outputs=[generated_script, story_status])

        gr.Markdown("Supported formats: `NARRATOR: text`, `Alex [shocked]: text`, plain narrator fallback lines, and JSON arrays such as `[{\"speaker\":\"NARRATOR\",\"text\":\"...\",\"emotion\":\"excited\"}]`. Non-narrator voices are assigned from explicit gender fields or inferred names/roles; narrator always uses the selected storyteller voice.")
    return demo


demo = build_ui()
app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    Path("assets/output").mkdir(parents=True, exist_ok=True)
    uvicorn.run("app:app", host="127.0.0.1", port=7860, reload=False)
