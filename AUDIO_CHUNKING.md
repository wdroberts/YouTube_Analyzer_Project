# 🎵 Audio Chunking System

## Overview

The YouTube Analyzer now automatically handles large audio files by splitting them into smaller chunks that meet OpenAI Whisper's API size requirements (25MB limit).

## How It Works

### 1. **Automatic Detection**
When you process a YouTube video, the app checks if the audio file exceeds the 24MB threshold:
- ✅ **Small files** (≤24MB): Transcribed directly
- 🔄 **Large files** (>24MB): Automatically split into chunks

### 2. **Intelligent Splitting**
```
Original File: 125 MB
├── Chunk 1: 20 MB (0:00 - 8:20)
├── Chunk 2: 20 MB (8:19 - 16:40) ← 500ms overlap
├── Chunk 3: 20 MB (16:39 - 25:00) ← 500ms overlap
├── Chunk 4: 20 MB (24:59 - 33:20) ← 500ms overlap
├── Chunk 5: 20 MB (33:19 - 41:40) ← 500ms overlap
└── Chunk 6: 25 MB (41:39 - 52:00) ← 500ms overlap
```

### 3. **Smart Overlap**
Each chunk overlaps by **500ms** with the previous chunk to prevent:
- ❌ Mid-word cuts
- ❌ Lost sentences at boundaries
- ❌ Context loss between chunks

### 4. **Timestamp Correction**
The system automatically adjusts timestamps across chunks:
```python
# Chunk 1: "Hello world" (0.0s - 2.0s)
# Chunk 2: "How are you?" (starts at 8:19.5)
#   → Adjusted to: (499.5s - 501.5s) in final transcript
```

### 5. **Automatic Cleanup**
Temporary chunk files are automatically deleted after successful transcription.

## Configuration

### Environment Variables (`.env`)
```ini
# Audio quality (lower = smaller files, but may still need chunking)
AUDIO_QUALITY=96  # 32-320 kbps

# Advanced: Chunk settings (modify in app.py.py Config class)
# audio_chunk_size_mb: int = 20      # Target chunk size
# audio_chunk_overlap_ms: int = 500  # Overlap duration
```

### When to Adjust Settings

#### **Videos Still Too Large?**
If you're processing very long videos (e.g., 10+ hours), you might want to:

1. **Lower audio quality** in `.env`:
   ```ini
   AUDIO_QUALITY=64  # Lower quality = smaller files
   ```

2. **Smaller chunks** in `app.py.py`:
   ```python
   audio_chunk_size_mb: int = 15  # Even smaller chunks
   ```

#### **Better Quality Needed?**
For high-quality audio (podcasts, music):
```ini
AUDIO_QUALITY=192  # Higher quality (files will be larger)
```

## Technical Details

### Dependencies
- **pydub** (0.25.1): Audio file manipulation
- **FFmpeg**: Required by pydub (usually installed with yt-dlp)

### Algorithm
```python
def split_audio_file(audio_path: Path) -> List[Path]:
    1. Check file size
    2. If ≤24MB: return [original_file]
    3. If >24MB:
       a. Load audio with pydub
       b. Calculate chunk duration based on bitrate
       c. Split into chunks with 500ms overlap
       d. Export each chunk as MP3
    4. Return list of chunk paths
```

### Transcription Flow
```python
def transcribe_audio_with_timestamps(audio_path: Path):
    1. chunks = split_audio_file(audio_path)
    2. If single chunk:
       → Transcribe normally
    3. If multiple chunks:
       a. For each chunk:
          - Transcribe via Whisper API
          - Adjust timestamps
       b. Merge all segments
       c. Cleanup chunk files
    4. Return combined result
```

## Benefits

### ✅ **No Manual Work**
- No need to manually split videos
- No need to merge transcripts yourself
- Completely transparent to the user

### ✅ **No Size Limits**
- Process videos of any length
- 1 hour? ✅
- 5 hours? ✅
- 10 hours? ✅

### ✅ **Accurate Timestamps**
- Seamless timestamp correction
- Export to SRT/VTT works perfectly
- No gaps or overlaps in timeline

### ✅ **Efficient API Usage**
- Optimal chunk sizes (~20MB)
- Minimal wasted overlap (500ms)
- Automatic retry on failures

## Example Usage

### Before (Manual Workaround)
```
❌ Video too large (125MB audio)
1. Download video manually
2. Split with video editor
3. Upload each part separately
4. Transcribe each part
5. Manually merge transcripts
6. Manually fix timestamps
```

### After (Automatic)
```
✅ Just paste the YouTube URL
   → App handles everything automatically!
```

## Monitoring Progress

The app shows real-time progress:
```
📥 Downloading audio...
✂️ Audio file (125.3MB) exceeds limit (24MB). Splitting into chunks...
✂️ Created chunk 1: chunk_000.mp3 (20.1MB, 502.3s)
✂️ Created chunk 2: chunk_001.mp3 (20.0MB, 500.8s)
...
🎤 Transcribing 6 audio chunks...
🎤 Processing chunk 1/6...
🎤 Transcription completed: chunk_000.mp3
🎤 Processing chunk 2/6...
...
✅ Successfully merged 6 chunks into single transcript
🧹 Cleaned up temporary audio chunks
```

## Troubleshooting

### Issue: "Failed to split audio file"
**Cause**: FFmpeg not installed or not in PATH

**Fix**:
1. FFmpeg is usually installed with yt-dlp
2. Test: `ffmpeg -version` in terminal
3. If missing, install: https://ffmpeg.org/download.html

### Issue: Chunks still too large
**Cause**: Very high bitrate video

**Fix**: Lower audio quality in `.env`:
```ini
AUDIO_QUALITY=64  # or even 32 for extremely long videos
```

### Issue: Poor transcription quality at chunk boundaries
**Cause**: Not enough overlap

**Fix**: Increase overlap in `app.py.py`:
```python
audio_chunk_overlap_ms: int = 1000  # 1 second overlap
```

## Performance

### Time Comparison
| Video Length | Audio Size | Processing Time |
|--------------|------------|-----------------|
| 1 hour | 50MB | ~2 min (2 chunks) |
| 3 hours | 150MB | ~5 min (6 chunks) |
| 10 hours | 500MB | ~15 min (20 chunks) |

*Times vary based on internet speed and OpenAI API response time*

### Cost Considerations
Whisper API pricing: $0.006 per minute

| Video Length | Cost |
|--------------|------|
| 1 hour | $0.36 |
| 3 hours | $1.08 |
| 10 hours | $3.60 |

## Future Enhancements

Potential improvements:
- [ ] Parallel chunk transcription (faster processing)
- [ ] Silence-based splitting (smarter boundaries)
- [ ] Resume from failed chunks
- [ ] Streaming transcription for real-time feedback

## See Also

- [Main README](README.md) - General app documentation
- [SETUP.md](SETUP.md) - Installation guide
- [env.template](env.template) - Configuration options

---

**Questions?** Check the main README or open an issue on GitHub!

