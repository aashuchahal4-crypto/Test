     1	from pathlib import Path
     2	
     3	
     4	def ensure_asset_folders() -> None:
     5	    for folder in ("assets/footage", "assets/music", "assets/fonts", "assets/characters", "assets/uploads", "outputs/videos", "outputs/ai_backgrounds/cache"):
     6	        Path(folder).mkdir(parents=True, exist_ok=True)
     7	
     8	
     9	if __name__ == "__main__":
    10	    ensure_asset_folders()
    11	    print("Asset folders ready. Add optional free videos/music/fonts to assets/.")
    12	