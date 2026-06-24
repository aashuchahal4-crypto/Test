import asyncio
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import gradio as gr

try:
    from openai import OpenAI
except Exception:  # optional dependency at runtime when no key is used
    OpenAI = None

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
YTDLP_BASE_COMMAND = [sys.executable, "-m", "yt_dlp"]
YTDLP_NETWORK_OPTIONS = [
    "--force-ipv4",
    "--socket-timeout",
    "10",
    "--retries",
    "2",
    "--extractor-retries",
    "2",
    "--fragment-retries",
    "2",
]
YTDLP_YOUTUBE_PROFILES = [
    ["--extractor-args", "youtube:player_client=web"],
    ["--extractor-args", "youtube:player_client=android,web"],
    [],
]

_original_event_loop_del = asyncio.BaseEventLoop.__del__


def _safe_event_loop_del(self) -> None:
    try:
        _original_event_loop_del(self)
    except ValueError as exc:
        if "Invalid file descriptor" not in str(exc):
            raise


asyncio.BaseEventLoop.__del__ = _safe_event_loop_del

POSITIVE_TERMS = {
    "secret", "mistake", "truth", "never", "always", "money", "growth", "viral",
    "important", "crazy", "problem", "solution", "learn", "story", "why", "how",
    "best", "worst", "first", "last", "risk", "win", "fail", "change", "easy",
}
QUESTION_TERMS = {"what", "why", "how", "when", "where", "who", "which"}


@dataclass
class TranscriptEntry:
    start_time: str
    end_time: str
    text: str

    @property
    def start(self) -> float:
        return time_to_sec(self.start_time)

    @property
    def end(self) -> float:
        return time_to_sec(self.end_time)


def run_command(command: list[str], timeout: int = 180, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(message or f"Command failed with exit status {result.returncode}.")
    return result


def ytdlp_command(options: list[str], profile: list[str] | None = None) -> list[str]:
    return [*YTDLP_BASE_COMMAND, *YTDLP_NETWORK_OPTIONS, *(profile or YTDLP_YOUTUBE_PROFILES[0]), *options]


def command_error_message(command: list[str], exc: subprocess.TimeoutExpired) -> str:
    return f"{Path(command[0]).name} timed out after {int(exc.timeout or 0)} seconds."


def run_ytdlp_with_fallback(options: list[str], timeout: int, check: bool = True) -> subprocess.CompletedProcess:
    deadline = time.monotonic() + timeout
    per_attempt_timeout = max(8, min(25, timeout // max(1, len(YTDLP_YOUTUBE_PROFILES))))
    last_result: subprocess.CompletedProcess | None = None
    last_error = ""
    for profile in YTDLP_YOUTUBE_PROFILES:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        command = ytdlp_command(options, profile)
        try:
            result = run_command(command, timeout=int(min(per_attempt_timeout, remaining)), check=False)
        except subprocess.TimeoutExpired as exc:
            last_error = command_error_message(command, exc)
            continue
        if result.returncode == 0:
            return result
        last_result = result
        last_error = (result.stderr or result.stdout or "").strip()
    if not check and last_result is not None:
        return last_result
    raise RuntimeError(last_error or "yt-dlp failed for all YouTube client profiles.")


def extract_youtube_id(youtube_url: str) -> str | None:
    text = (youtube_url or "").strip()
    if not text:
        return None
    parsed = urllib.parse.urlparse(text)
    host = parsed.netloc.lower().removeprefix("www.")
    if host == "youtu.be":
        return parsed.path.strip("/") or None
    if host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
        if parsed.path == "/watch":
            return urllib.parse.parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith(("/shorts/", "/embed/")):
            return parsed.path.split("/")[2] or None
    match = re.search(r"(?<![A-Za-z0-9_-])([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])", text)
    return match.group(1) if match else None


def fetch_oembed_metadata(youtube_url: str) -> dict[str, Any]:
    request_url = "https://www.youtube.com/oembed?" + urllib.parse.urlencode(
        {"format": "json", "url": youtube_url}
    )
    request = urllib.request.Request(request_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=10) as response:
        data = json.loads(response.read().decode("utf-8"))

    video_id = extract_youtube_id(youtube_url)
    thumbnail = data.get("thumbnail_url")
    if video_id:
        thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    return {
        "id": video_id,
        "title": data.get("title") or "YouTube Video",
        "uploader": data.get("author_name") or "Unknown",
        "channel": data.get("author_name") or "Unknown",
        "duration": 0,
        "thumbnail": thumbnail,
        "webpage_url": youtube_url,
        "_metadata_source": "YouTube oEmbed",
    }


def sec_to_timestamp(sec: float) -> str:
    sec = max(0.0, float(sec or 0))
    hours = int(sec // 3600)
    minutes = int((sec % 3600) // 60)
    seconds = int(sec % 60)
    millis = int(round((sec - int(sec)) * 1000))
    if millis == 1000:
        seconds += 1
        millis = 0
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def time_to_sec(value: str | float | int | None) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return max(0.0, float(value))

    text = str(value).strip().replace(",", ".")
    if not text:
        return 0.0

    parts = text.split(":")
    try:
        if len(parts) == 3:
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            return max(0.0, hours * 3600 + minutes * 60 + seconds)
        if len(parts) == 2:
            minutes = float(parts[0])
            seconds = float(parts[1])
            return max(0.0, minutes * 60 + seconds)
        return max(0.0, float(text))
    except ValueError:
        return 0.0


def clean_caption_text(line: str) -> str:
    line = re.sub(r"<[^>]+>", "", line)
    line = re.sub(r"&amp;", "&", line)
    line = re.sub(r"&quot;", '"', line)
    line = re.sub(r"&#39;", "'", line)
    line = re.sub(r"\s+", " ", line)
    return line.strip()


def parse_vtt(vtt_path: str | Path) -> list[TranscriptEntry]:
    path = Path(vtt_path)
    if not path.exists():
        return []

    content = path.read_text(encoding="utf-8", errors="ignore")
    blocks = re.split(r"\n\s*\n", content)
    entries: list[TranscriptEntry] = []
    timestamp_pattern = re.compile(
        r"(?P<start>\d{1,2}:\d{2}:\d{2}[\.,]\d{3}|\d{1,2}:\d{2}[\.,]\d{3})\s*-->\s*"
        r"(?P<end>\d{1,2}:\d{2}:\d{2}[\.,]\d{3}|\d{1,2}:\d{2}[\.,]\d{3})"
    )

    for block in blocks:
        lines = [line.strip() for line in block.strip().splitlines() if line.strip()]
        if not lines or lines[0].upper() == "WEBVTT":
            continue

        match_index = next((i for i, line in enumerate(lines) if timestamp_pattern.search(line)), -1)
        if match_index == -1:
            continue

        match = timestamp_pattern.search(lines[match_index])
        if not match:
            continue

        text = " ".join(clean_caption_text(line) for line in lines[match_index + 1 :])
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue

        start = sec_to_timestamp(time_to_sec(match.group("start")))
        end = sec_to_timestamp(time_to_sec(match.group("end")))
        if entries and entries[-1].text == text:
            entries[-1].end_time = end
        else:
            entries.append(TranscriptEntry(start, end, text))

    return entries


def fetch_metadata(youtube_url: str) -> dict[str, Any]:
    oembed_info: dict[str, Any] | None = None
    try:
        oembed_info = fetch_oembed_metadata(youtube_url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        oembed_info = None

    options = [
        "--skip-download",
        "--dump-single-json",
        "--no-playlist",
        youtube_url,
    ]
    try:
        result = run_ytdlp_with_fallback(options, timeout=35)
        info = json.loads(result.stdout)
        if oembed_info:
            for key in ("title", "uploader", "channel", "thumbnail"):
                info[key] = info.get(key) or oembed_info.get(key)
        info["_metadata_source"] = "yt-dlp"
        return info
    except Exception:
        if oembed_info:
            return oembed_info
        raise RuntimeError(
            "Could not read YouTube metadata from yt-dlp or YouTube oEmbed. "
            "Check that the URL is public and try again."
        )


def fetch_transcript(youtube_url: str, temp_dir: Path) -> list[TranscriptEntry]:
    options = [
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        "en.*,en",
        "--sub-format",
        "vtt",
        "--no-playlist",
        "-o",
        str(temp_dir / "subs"),
        youtube_url,
    ]
    try:
        run_ytdlp_with_fallback(options, timeout=60, check=False)
    except Exception:
        return []
    sub_files = sorted(glob.glob(str(temp_dir / "subs*.vtt"))) or sorted(glob.glob(str(temp_dir / "subs*")))
    for sub_file in sub_files:
        parsed = parse_vtt(sub_file)
        if parsed:
            return parsed
    return []


def whisper_transcript(youtube_url: str, temp_dir: Path) -> tuple[list[TranscriptEntry], bool]:
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key or OpenAI is None:
        return [], False

    audio_path = temp_dir / "audio.%(ext)s"
    options = [
        "-f",
        "ba[ext=m4a]/ba/bestaudio",
        "--download-sections",
        "*00:00:00-00:10:00",
        "--no-playlist",
        "-o",
        str(audio_path),
        youtube_url,
    ]
    run_ytdlp_with_fallback(options, timeout=240)
    audio_files = list(temp_dir.glob("audio.*"))
    if not audio_files:
        return [], False

    client = OpenAI(api_key=openai_key)
    with audio_files[0].open("rb") as audio_file:
        transcript_obj = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

    entries: list[TranscriptEntry] = []
    for segment in getattr(transcript_obj, "segments", []) or []:
        start = segment.get("start", 0) if isinstance(segment, dict) else getattr(segment, "start", 0)
        end = segment.get("end", 0) if isinstance(segment, dict) else getattr(segment, "end", 0)
        text = segment.get("text", "") if isinstance(segment, dict) else getattr(segment, "text", "")
        if text:
            entries.append(TranscriptEntry(sec_to_timestamp(start), sec_to_timestamp(end), text.strip()))
    return entries, bool(entries)


def transcript_to_prompt(transcript: list[TranscriptEntry]) -> str:
    return "\n".join(f"[{entry.start_time} -> {entry.end_time}] {entry.text}" for entry in transcript)[:25000]


def openai_highlights(transcript: list[TranscriptEntry]) -> list[dict[str, Any]]:
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key or OpenAI is None or not transcript:
        return []

    prompt = f"""
Identify exactly 3 highly engaging, self-contained 30-50 second YouTube Shorts segments.
Return only valid JSON with this shape:
{{"highlights":[{{"id":1,"title":"Short catchy title","start_time":"HH:MM:SS.mmm","end_time":"HH:MM:SS.mmm","hook":"First 5 seconds hook","rationale":"Why it works","tags":["tag"]}}]}}

Transcript:
{transcript_to_prompt(transcript)}
"""
    client = OpenAI(api_key=openai_key)
    completion = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    content = completion.choices[0].message.content or "{}"
    return normalize_highlights(json.loads(content).get("highlights", []), transcript[-1].end if transcript else 0)


def score_entry(entry: TranscriptEntry) -> float:
    words = re.findall(r"[a-zA-Z']+", entry.text.lower())
    if not words:
        return 0.0
    unique = set(words)
    score = min(len(words), 35) / 35
    score += sum(1 for word in unique if word in POSITIVE_TERMS) * 0.7
    score += sum(1 for word in unique if word in QUESTION_TERMS) * 0.4
    if "?" in entry.text:
        score += 0.9
    if any(token in entry.text.lower() for token in ["but", "because", "actually", "here's", "this is"]):
        score += 0.5
    return score


def local_highlights(transcript: list[TranscriptEntry], duration: float) -> list[dict[str, Any]]:
    if not transcript:
        return structural_highlights(duration)

    windows: list[tuple[float, float, float, str]] = []
    for entry in transcript:
        start = max(0.0, entry.start - 2.0)
        end_target = min(duration or transcript[-1].end, start + 45.0)
        window_entries = [item for item in transcript if item.start >= start and item.start <= end_target]
        if not window_entries:
            continue
        end = min(duration or window_entries[-1].end, max(window_entries[-1].end, start + 30.0))
        end = min(end, start + 50.0)
        text = " ".join(item.text for item in window_entries)
        score = sum(score_entry(item) for item in window_entries) / max(1, len(window_entries))
        if 25 <= end - start <= 55:
            windows.append((score, start, end, text))

    windows.sort(reverse=True, key=lambda row: row[0])
    selected: list[tuple[float, float, float, str]] = []
    for candidate in windows:
        _, start, end, _ = candidate
        overlaps = any(max(start, used_start) < min(end, used_end) for _, used_start, used_end, _ in selected)
        if not overlaps:
            selected.append(candidate)
        if len(selected) == 3:
            break

    if len(selected) < 3:
        selected.extend((0.0, item["start"], item["end"], item["title"]) for item in structural_intervals(duration, len(selected)))

    selected = sorted(selected[:3], key=lambda row: row[1])
    highlights: list[dict[str, Any]] = []
    for index, (_, start, end, text) in enumerate(selected, start=1):
        words = re.findall(r"[A-Za-z0-9']+", text)
        title = " ".join(words[:7]).strip() or f"Highlight {index}"
        highlights.append(
            {
                "id": index,
                "title": title[:60],
                "start_time": sec_to_timestamp(start),
                "end_time": sec_to_timestamp(end),
                "hook": (text[:120].strip() + "…") if len(text) > 120 else text.strip(),
                "rationale": "Selected by local transcript scoring for questions, hooks, contrast words, and dense speech.",
                "tags": ["shorts", "highlight", "auto"],
            }
        )
    return normalize_highlights(highlights, duration)


def structural_intervals(duration: float, existing_count: int = 0) -> list[dict[str, Any]]:
    safe_duration = max(float(duration or 180), 60.0)
    starts = [safe_duration * 0.08, safe_duration * 0.38, safe_duration * 0.68]
    names = ["Opening Hook", "Core Moment", "Closing Payoff"]
    intervals = []
    for start, name in zip(starts[existing_count:], names[existing_count:]):
        start = min(max(0.0, start), max(0.0, safe_duration - 35.0))
        intervals.append({"start": start, "end": min(safe_duration, start + 40.0), "title": name})
    return intervals


def structural_highlights(duration: float) -> list[dict[str, Any]]:
    highlights = []
    for index, item in enumerate(structural_intervals(duration), start=1):
        highlights.append(
            {
                "id": index,
                "title": item["title"],
                "start_time": sec_to_timestamp(item["start"]),
                "end_time": sec_to_timestamp(item["end"]),
                "hook": "No captions were available, so this uses a strong timeline-based segment.",
                "rationale": "Fallback clip selected from common long-form pacing positions.",
                "tags": ["fallback", "timeline"],
            }
        )
    return highlights


def normalize_highlights(highlights: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    normalized = []
    for index, highlight in enumerate(highlights[:3], start=1):
        start = time_to_sec(highlight.get("start_time"))
        end = time_to_sec(highlight.get("end_time"))
        if end <= start:
            end = start + 40.0
        if end - start > 90:
            end = start + 50.0
        if duration:
            start = min(start, max(0.0, duration - 5.0))
            end = min(end, duration)
        if end - start < 10:
            end = min(duration or start + 40.0, start + 40.0)
        normalized.append(
            {
                "id": index,
                "title": str(highlight.get("title") or f"Highlight {index}")[:80],
                "start_time": sec_to_timestamp(start),
                "end_time": sec_to_timestamp(end),
                "hook": str(highlight.get("hook") or "Engaging moment selected from the transcript.")[:180],
                "rationale": str(highlight.get("rationale") or "Selected as a self-contained short candidate.")[:220],
                "tags": [str(tag)[:24] for tag in highlight.get("tags", ["shorts"])][:5],
            }
        )
    return normalized or structural_highlights(duration)


def analyze_video(youtube_url: str) -> tuple[str, str | None, list[dict[str, Any]], str]:
    youtube_url = (youtube_url or "").strip()
    if not youtube_url:
        return "Enter a YouTube URL first.", None, [], ""

    with tempfile.TemporaryDirectory(prefix="shorts_analysis_") as temp_name:
        temp_dir = Path(temp_name)
        try:
            info = fetch_metadata(youtube_url)
        except Exception as exc:
            return f"Could not read YouTube metadata: {exc}", None, [], ""

        title = info.get("title", "Unknown Video")
        duration = float(info.get("duration") or 0)
        thumbnail = info.get("thumbnail")
        uploader = info.get("uploader") or info.get("channel") or "Unknown"
        metadata_source = info.get("_metadata_source", "YouTube metadata")

        transcript = fetch_transcript(youtube_url, temp_dir)
        whisper_used = False
        if not transcript:
            try:
                transcript, whisper_used = whisper_transcript(youtube_url, temp_dir)
            except Exception:
                transcript, whisper_used = [], False

        highlights: list[dict[str, Any]] = []
        source = "local transcript scoring"
        if transcript and os.getenv("OPENAI_API_KEY"):
            try:
                highlights = openai_highlights(transcript)
                source = "OpenAI GPT transcript analysis"
            except Exception:
                highlights = []
        if not highlights:
            highlights = local_highlights(transcript, duration)

        caption_status = "OpenAI Whisper fallback" if whisper_used else ("YouTube captions" if transcript else "timeline fallback")
        duration_text = f"{int(duration // 60):02d}:{int(duration % 60):02d}" if duration else "unknown"
        summary = (
            f"### {title}\n"
            f"**Creator:** {uploader}\n\n"
            f"**Duration:** {duration_text}\n\n"
            f"**Metadata:** {metadata_source}\n\n"
            f"**Analysis:** {source} using {caption_status}. No paid API key is required unless you add `OPENAI_API_KEY`."
        )
        return summary, thumbnail, highlights, youtube_url


def download_segment(youtube_url: str, start: float, duration: float, target: Path) -> None:
    section = f"*{sec_to_timestamp(start)}-{sec_to_timestamp(start + duration)}"
    options = [
        "--download-sections",
        section,
        "--force-keyframes-at-cuts",
        "--no-playlist",
        "-f",
        "bv*[height<=720]+ba/b[height<=720]/best",
        "--merge-output-format",
        "mp4",
        "-o",
        str(target),
        youtube_url,
    ]
    run_ytdlp_with_fallback(options, timeout=420)


def render_vertical_video(input_path: Path, output_path: Path, crop_style: str) -> None:
    if crop_style == "Center Crop (9:16)":
        filter_args = ["-vf", "scale=-2:960,crop=540:960:(iw-ow)/2:(ih-oh)/2"]
    else:
        filter_args = [
            "-filter_complex",
            (
                "[0:v]split=2[base][front];"
                "[base]scale=540:960:force_original_aspect_ratio=increase,crop=540:960,boxblur=20:1[bg];"
                "[front]scale=540:-2:force_original_aspect_ratio=decrease[fg];"
                "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[v]"
            ),
            "-map",
            "[v]",
            "-map",
            "0:a?",
        ]

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        *filter_args,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    run_command(command, timeout=420)


def generate_short(youtube_url: str, start_time: str, end_time: str, crop_style: str, short_title: str) -> tuple[str | None, str]:
    youtube_url = (youtube_url or "").strip()
    if not youtube_url:
        return None, "Missing YouTube URL."

    start = time_to_sec(start_time)
    end = time_to_sec(end_time)
    duration = end - start
    if duration <= 0:
        duration = 35.0
    duration = min(max(duration, 5.0), 90.0)

    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", (short_title or "short").strip()).strip("_")[:40] or "short"
    final_path = OUTPUT_DIR / f"{safe_name}.mp4"

    with tempfile.TemporaryDirectory(prefix="shorts_render_") as temp_name:
        temp_dir = Path(temp_name)
        downloaded = temp_dir / "source.mp4"
        try:
            download_segment(youtube_url, start, duration, downloaded)
            candidates = [downloaded, *temp_dir.glob("source.*")]
            source = next((path for path in candidates if path.exists() and path.stat().st_size > 0), None)
            if source is None:
                return None, "Video download produced no file."
            render_vertical_video(source, final_path, crop_style)
        except Exception as exc:
            return None, f"Render failed: {exc}"

    if final_path.exists() and final_path.stat().st_size > 0:
        return str(final_path), f"Rendered {duration:.1f}s vertical short: {final_path.name}"
    return None, "Render failed: output MP4 was not created."


def select_highlight(highlights: list[dict[str, Any]], event: gr.SelectData) -> tuple[str, str, str]:
    if not highlights or event.index is None:
        return "", "", ""
    index = event.index[0] if isinstance(event.index, (list, tuple)) else int(event.index)
    highlight = highlights[index]
    return highlight["title"], highlight["start_time"], highlight["end_time"]


def build_highlight_table(highlights: list[dict[str, Any]]) -> list[list[str]]:
    return [
        [
            highlight["id"],
            highlight["title"],
            highlight["start_time"],
            highlight["end_time"],
            highlight["hook"],
            ", ".join(highlight.get("tags", [])),
        ]
        for highlight in highlights
    ]


def analyze_for_ui(youtube_url: str) -> tuple[str, str | None, list[list[str]], list[dict[str, Any]], str]:
    summary, thumbnail, highlights, stored_url = analyze_video(youtube_url)
    return summary, thumbnail, build_highlight_table(highlights), highlights, stored_url


def generate_for_ui(youtube_url: str, title: str, start: str, end: str, crop_style: str) -> tuple[str | None, str]:
    return generate_short(youtube_url, start, end, crop_style, title)


custom_css = """
#shorts-table td { white-space: normal !important; vertical-align: top; }
.gradio-container { max-width: 1180px !important; }
"""

app_theme = gr.themes.Soft(primary_hue="red", secondary_hue="slate")

with gr.Blocks(title="AI YouTube Shorts Generator") as demo:
    gr.Markdown(
        "# AI YouTube Shorts Generator\n"
        "Paste a YouTube URL, pick an auto-detected segment, and render a vertical MP4 for Shorts/Reels/TikTok. "
        "The app works without a paid AI key by using local transcript scoring; add `OPENAI_API_KEY` in Hugging Face Space secrets for GPT/Whisper upgrades."
    )

    stored_highlights = gr.State([])
    stored_url = gr.State("")

    with gr.Row():
        youtube_url = gr.Textbox(label="YouTube URL", placeholder="https://www.youtube.com/watch?v=...", scale=5)
        analyze_button = gr.Button("Extract Highlights", variant="primary", scale=1)

    with gr.Row():
        summary_output = gr.Markdown()
        thumbnail_output = gr.Image(label="Thumbnail", height=220)

    highlights_table = gr.Dataframe(
        headers=["#", "Title", "Start", "End", "Hook", "Tags"],
        datatype=["number", "str", "str", "str", "str", "str"],
        label="Recommended Shorts Segments (click a row to load it below)",
        interactive=False,
        elem_id="shorts-table",
    )

    with gr.Row():
        short_title = gr.Textbox(label="Short Title")
        start_time = gr.Textbox(label="Start Time", placeholder="00:01:23.000")
        end_time = gr.Textbox(label="End Time", placeholder="00:02:03.000")
        crop_style = gr.Radio(["Split Blur Frame", "Center Crop (9:16)"], value="Split Blur Frame", label="Crop Style")

    generate_button = gr.Button("Generate Vertical Short", variant="primary")
    with gr.Row():
        output_video = gr.Video(label="Rendered Short")
        status_output = gr.Markdown()

    analyze_button.click(
        analyze_for_ui,
        inputs=[youtube_url],
        outputs=[summary_output, thumbnail_output, highlights_table, stored_highlights, stored_url],
    )
    highlights_table.select(select_highlight, inputs=[stored_highlights], outputs=[short_title, start_time, end_time])
    generate_button.click(
        generate_for_ui,
        inputs=[stored_url, short_title, start_time, end_time, crop_style],
        outputs=[output_video, status_output],
    )

if __name__ == "__main__":
    if shutil.which("ffmpeg") is None:
        print("Warning: ffmpeg is not installed. Hugging Face installs it from packages.txt.")
    try:
        subprocess.run([*YTDLP_BASE_COMMAND, "--version"], capture_output=True, check=True)
    except Exception:
        print("Warning: yt-dlp is not installed. Run: pip install -r requirements.txt")
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("PORT", "7860")),
        ssr_mode=False,
        theme=app_theme,
        css=custom_css,
    )
