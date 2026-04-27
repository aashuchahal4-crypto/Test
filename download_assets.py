from pathlib import Path


def ensure_asset_folders() -> None:
    for folder in ("assets/footage", "assets/music", "assets/fonts", "assets/characters", "assets/uploads", "outputs/videos", "outputs/ai_backgrounds/cache"):
        Path(folder).mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    ensure_asset_folders()
    print("Asset folders ready. Add optional free videos/music/fonts to assets/.")
