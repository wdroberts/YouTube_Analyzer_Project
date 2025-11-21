import json
import yt_dlp
from pathlib import Path

# Update the metadata for the specific project
project_dir = Path("outputs/ce3b8694-0de0-4854-b527-72c5cb2a46bf")
metadata_file = project_dir / "metadata.json"

# Read current metadata
with open(metadata_file, 'r', encoding='utf-8') as f:
    metadata = json.load(f)

# Fetch video title
url = metadata['url']
ydl_opts = {
    'quiet': True,
    'no_warnings': True,
    'skip_download': True,
}

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        video_title = info.get('title', 'Unknown Video')
        
        # Update metadata with title
        metadata['title'] = video_title
        
        # Save updated metadata
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=4)
        
        print(f"✅ Updated project with title: {video_title}")
except Exception as e:
    print(f"❌ Error: {e}")


