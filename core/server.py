#!/usr/bin/env python3
"""Small local HTTP wrapper for the offline video pipeline.

This is the preferred Windows ARM/Snapdragon path: it runs the app from Python
and serves the already-built frontend, avoiding first-run Rust/Tauri compilation.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import threading
import time
import urllib.parse
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from foundry_backend import (
    FoundryError,
    generate_captions,
    generate_hooks_titles,
    generate_script,
    rewrite_viral,
    status as foundry_status,
)
from image_generation import DEFAULT_ENGINE, generate_scene_images, image_engines_status
from pipeline import foundry_plan, project_from_dict, project_to_dict, render_project

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
STORAGE = ROOT / "storage"
JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.end_headers()
    handler.wfile.write(data)


class Handler(BaseHTTPRequestHandler):
    server_version = "LocalAIVideoStudio/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[server] {self.address_string()} - {fmt % args}")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/api/health":
            json_response(self, 200, {"ok": True, "root": str(ROOT), "dist": str(DIST), "ai_backend": "Foundry Local"})
            return
        if self.path == "/api/ai-status":
            self.ai_status()
            return
        if self.path == "/api/image-engines":
            json_response(self, 200, image_engines_status())
            return
        if urllib.parse.urlparse(self.path).path == "/api/render-progress":
            self.render_progress()
            return
        if urllib.parse.urlparse(self.path).path == "/api/asset":
            self.serve_asset()
            return
        self.serve_static()

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8") if length else "{}"
            payload = json.loads(body or "{}")
            if self.path == "/api/generate-scenes":
                self.generate_scenes(payload)
            elif self.path == "/api/generate-script":
                self.generate_script_endpoint(payload)
            elif self.path == "/api/generate-hooks-titles":
                self.generate_hooks_titles_endpoint(payload)
            elif self.path == "/api/generate-captions":
                self.generate_captions_endpoint(payload)
            elif self.path == "/api/rewrite-viral":
                self.rewrite_viral_endpoint(payload)
            elif self.path == "/api/render-video":
                self.render_video(payload)
            elif self.path == "/api/generate-images":
                self.generate_images(payload)
            else:
                json_response(self, 404, {"error": "Unknown endpoint"})
        except FoundryError as exc:
            json_response(self, exc.status_code, {"error": str(exc), "ai_backend": "Foundry Local"})
        except Exception as exc:
            json_response(self, 500, {"error": str(exc)})

    def ai_status(self) -> None:
        try:
            json_response(self, 200, foundry_status())
        except FoundryError as exc:
            json_response(self, exc.status_code, {"ok": False, "backend": "Foundry Local", "error": str(exc)})

    def generate_scenes(self, payload: dict[str, Any]) -> None:
        prompt = str(payload.get("prompt") or "A local AI video")
        video_type = str(payload.get("videoType") or payload.get("video_type") or "explainer")
        duration = int(payload.get("duration") or 24)
        style = str(payload.get("style") or "neon")
        language = str(payload.get("language") or "en")
        voice = str(payload.get("voice") or "auto")
        generate_images = bool(payload.get("generateImages") or payload.get("generate_images"))
        image_engine = str(payload.get("imageEngine") or payload.get("image_engine") or DEFAULT_ENGINE)
        project = foundry_plan(prompt, video_type, duration, style, language, voice, generate_images, image_engine)
        project.voice = voice
        json_response(self, 200, project_to_dict(project))

    def generate_script_endpoint(self, payload: dict[str, Any]) -> None:
        prompt = str(payload.get("prompt") or "A local AI video")
        video_type = str(payload.get("videoType") or payload.get("video_type") or "explainer")
        duration = int(payload.get("duration") or 24)
        style = str(payload.get("style") or "neon")
        language = str(payload.get("language") or "en")
        json_response(self, 200, {"script": generate_script(prompt, video_type, duration, style, language), **foundry_status()})

    def generate_hooks_titles_endpoint(self, payload: dict[str, Any]) -> None:
        prompt = str(payload.get("prompt") or "A local AI video")
        video_type = str(payload.get("videoType") or payload.get("video_type") or "explainer")
        language = str(payload.get("language") or "en")
        json_response(self, 200, {"result": generate_hooks_titles(prompt, video_type, language), **foundry_status()})

    def generate_captions_endpoint(self, payload: dict[str, Any]) -> None:
        script = str(payload.get("script") or payload.get("text") or "")
        language = str(payload.get("language") or "en")
        json_response(self, 200, {"result": generate_captions(script, language), **foundry_status()})

    def rewrite_viral_endpoint(self, payload: dict[str, Any]) -> None:
        text = str(payload.get("text") or payload.get("prompt") or "")
        platform = str(payload.get("platform") or "short-form video")
        language = str(payload.get("language") or "en")
        json_response(self, 200, {"text": rewrite_viral(text, platform, language), **foundry_status()})

    def render_video(self, payload: dict[str, Any]) -> None:
        project_json = payload.get("projectJson") or payload.get("project_json") or payload
        if isinstance(project_json, str):
            project = project_from_dict(json.loads(project_json))
        else:
            project = project_from_dict(project_json)
        job_id = uuid.uuid4().hex
        with JOBS_LOCK:
            JOBS[job_id] = {
                "id": job_id,
                "status": "queued",
                "progress": 0,
                "message": "Queued render job",
                "result": None,
                "error": None,
                "created_at": time.time(),
            }
        threading.Thread(target=run_render_job, args=(job_id, project), daemon=True).start()
        json_response(self, 202, {"job_id": job_id, "status": "queued", "progress": 0, "message": "Queued render job"})

    def generate_images(self, payload: dict[str, Any]) -> None:
        project_json = payload.get("projectJson") or payload.get("project_json") or payload
        if isinstance(project_json, str):
            project = project_from_dict(json.loads(project_json))
        else:
            project = project_from_dict(project_json)
        job_id = uuid.uuid4().hex
        with JOBS_LOCK:
            JOBS[job_id] = {
                "id": job_id,
                "status": "queued",
                "progress": 0,
                "message": "Queued image generation job",
                "result": None,
                "error": None,
                "created_at": time.time(),
            }
        engine = str(payload.get("engine") or payload.get("imageEngine") or getattr(project, "image_engine", DEFAULT_ENGINE))
        threading.Thread(target=run_image_job, args=(job_id, project, engine), daemon=True).start()
        json_response(self, 202, {"job_id": job_id, "status": "queued", "progress": 0, "message": "Queued image generation job"})

    def render_progress(self) -> None:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        job_id = (query.get("id") or [""])[0]
        with JOBS_LOCK:
            job = dict(JOBS.get(job_id) or {})
        if not job:
            json_response(self, 404, {"error": "Render job not found"})
            return
        json_response(self, 200, job)

    def serve_static(self) -> None:
        url_path = urllib.parse.urlparse(self.path).path
        rel = url_path.lstrip("/") or "index.html"
        target = (DIST / rel).resolve()
        if not str(target).startswith(str(DIST.resolve())) or not target.exists() or target.is_dir():
            target = DIST / "index.html"
        if not target.exists():
            json_response(self, 503, {"error": "Frontend dist is missing. Run npm install && npm run build, or use the packaged zip that includes dist/."})
            return
        content = target.read_bytes()
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def serve_asset(self) -> None:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        raw_path = (query.get("path") or [""])[0]
        target = Path(raw_path).resolve()
        storage_root = STORAGE.resolve()
        if not raw_path or not str(target).startswith(str(storage_root)) or not target.exists() or not target.is_file():
            json_response(self, 404, {"error": "Asset not found"})
            return
        content = target.read_bytes()
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def update_job(job_id: str, **updates: Any) -> None:
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(updates)
            JOBS[job_id]["updated_at"] = time.time()


def run_render_job(job_id: str, project: Any) -> None:
    def on_progress(progress: int, message: str) -> None:
        update_job(job_id, status="running", progress=max(0, min(100, int(progress))), message=message)

    try:
        update_job(job_id, status="running", progress=1, message="Starting local render")
        result = render_project(project, progress_callback=on_progress)
        update_job(job_id, status="complete", progress=100, message="Render complete", result=result)
    except Exception as exc:
        update_job(job_id, status="error", progress=100, message="Render failed", error=str(exc))


def run_image_job(job_id: str, project: Any, engine: str = DEFAULT_ENGINE) -> None:
    def on_progress(progress: int, message: str) -> None:
        update_job(job_id, status="running", progress=max(0, min(100, int(progress * 5))), message=message)

    try:
        update_job(job_id, status="running", progress=2, message="Starting image generation")
        project.image_engine = engine
        generate_scene_images(project, engine, progress_callback=on_progress)
        update_job(job_id, status="complete", progress=100, message="Scene images ready", result=project_to_dict(project))
    except Exception as exc:
        update_job(job_id, status="error", progress=100, message="Image generation failed", error=str(exc))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Local AI Video Studio local web app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("LOCAL_AI_VIDEO_PORT", "8765")))
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}"
    print(f"Local AI Video Studio running at {url}")
    print("Outputs are saved under storage/outputs. Press Ctrl+C to stop.")
    if not args.no_open:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")


if __name__ == "__main__":
    main()
