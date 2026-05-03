from __future__ import annotations

import os
from npu_runtime import OnnxModelAdapter, get_npu_status


def deterministic_script(prompt: str, character: str = "Alex") -> str:
    subject = (prompt or "a strange city mystery").strip().rstrip(".")
    return "\n".join([
        f"NARRATOR: The story begins with {subject}.",
        f"{character} [curious]: Something feels different today.",
        "NARRATOR: The city went silent as rain started falling sideways.",
        f"{character} [shocked]: Wait, why is the sky green?",
        "NARRATOR [excited]: They ran through the park, pointing at a glowing door.",
        f"{character} [happy]: I think we found the secret!",
    ])


def generate_script(prompt: str, character: str = "Alex") -> dict:
    adapter = OnnxModelAdapter(os.getenv("LOCAL_LLM_ONNX_PATH"))
    if adapter.session is None:
        return {"script": deterministic_script(prompt, character), "used_model": False, "status": adapter.status_dict()}
    return {
        "script": deterministic_script(prompt, character),
        "used_model": False,
        "status": {**adapter.status_dict(), "note": "ONNX model loaded, but no tokenizer/decoder contract is bundled. Add a project-specific adapter to run real LLM decoding."},
    }


def npu_status_markdown() -> str:
    status = get_npu_status()
    providers = ", ".join(status.available_providers)
    return f"Provider: **{status.selected_provider}**  \nAccelerator: **{status.accelerator}**  \nAvailable providers: `{providers}`  \nModel: `{status.model_path or 'not configured'}`  \n{status.message}"
