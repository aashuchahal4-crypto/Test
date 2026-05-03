from __future__ import annotations

import os
import platform
from dataclasses import asdict, dataclass


@dataclass
class NPUStatus:
    onnxruntime_available: bool
    available_providers: list[str]
    selected_provider: str
    accelerator: str
    model_path: str | None
    message: str


def available_providers() -> list[str]:
    try:
        import onnxruntime as ort  # type: ignore
        return list(ort.get_available_providers())
    except Exception:
        return []


def preferred_provider(providers: list[str]) -> str:
    preference = ["QNNExecutionProvider", "DmlExecutionProvider", "CUDAExecutionProvider", "CoreMLExecutionProvider", "OpenVINOExecutionProvider", "CPUExecutionProvider"]
    for provider in preference:
        if provider in providers:
            return provider
    return providers[0] if providers else "CPUExecutionProvider"


def get_npu_status(model_path: str | None = None) -> NPUStatus:
    providers = available_providers()
    provider = preferred_provider(providers)
    accelerator = "CPU fallback"
    if provider == "QNNExecutionProvider":
        accelerator = "Qualcomm Snapdragon X / Hexagon NPU via ONNX Runtime QNNExecutionProvider"
    elif provider != "CPUExecutionProvider":
        accelerator = provider
    model = model_path or os.getenv("LOCAL_LLM_ONNX_PATH") or os.getenv("LOCAL_TTS_ONNX_PATH")
    if not providers:
        msg = "onnxruntime is not installed; install ONNX Runtime or vendor build to enable provider detection."
    elif provider == "QNNExecutionProvider":
        msg = "QNNExecutionProvider detected. Use Qualcomm-converted ONNX models and QNN SDK/runtime compatible with the Snapdragon X Hexagon NPU."
    else:
        msg = "No Qualcomm QNN provider detected; local AI adapters will use CPU/rule-based fallback unless a supported provider is configured."
    return NPUStatus(bool(providers), providers or ["CPUExecutionProvider"], provider, accelerator, model, msg)


class OnnxModelAdapter:
    def __init__(self, model_path: str | None = None, providers: list[str] | None = None):
        self.model_path = model_path or os.getenv("LOCAL_LLM_ONNX_PATH")
        self.providers = providers or available_providers() or ["CPUExecutionProvider"]
        self.session = None
        self.error: str | None = None
        if self.model_path:
            self.load()

    def load(self) -> bool:
        if not self.model_path or not os.path.exists(self.model_path):
            self.error = "No ONNX model path configured. Set LOCAL_LLM_ONNX_PATH or use fallback generation."
            return False
        try:
            import onnxruntime as ort  # type: ignore
            ordered = [preferred_provider(self.providers)] + [p for p in self.providers if p != preferred_provider(self.providers)]
            self.session = ort.InferenceSession(self.model_path, providers=ordered)
            return True
        except Exception as exc:
            self.error = str(exc)
            return False

    def status_dict(self) -> dict:
        status = asdict(get_npu_status(self.model_path))
        status["model_loaded"] = self.session is not None
        status["adapter_error"] = self.error
        return status
