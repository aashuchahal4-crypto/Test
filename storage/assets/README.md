# Offline assets

The CPU renderer automatically uses files placed here:

- `footage/` — `.mp4`, `.mov`, `.mkv`, `.webm`, `.avi`, `.m4v`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`
- `characters/` — transparent `.png`/images overlaid in the lower-right of scenes
- `music/` — `.mp3`, `.wav`, `.m4a`, `.aac`, `.ogg`, `.flac` mixed quietly under narration
- `fonts/` — `.ttf` or `.otf` used for captions before system fonts

Files starting with `default_` are sample fallbacks and are selected after your own files.
AI scene generation uses Foundry Local QNN NPU models; rendering uses these assets through FFmpeg on CPU.
