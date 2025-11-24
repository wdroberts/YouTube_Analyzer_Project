"""
Test local GPU-accelerated Whisper transcription.
Compare speed with OpenAI API.
"""
import sys
import time
from pathlib import Path
from faster_whisper import WhisperModel

# Import app module
import importlib.util
spec = importlib.util.spec_from_file_location("app", Path(__file__).parent / "app.py.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

def test_local_whisper():
    """Test local Whisper with the actual video."""
    import tempfile
    import shutil
    
    url = "https://youtu.be/Ht9XtcV7ZYk"
    
    print("="*70)
    print("🧪 LOCAL GPU WHISPER TEST (GTX 1080)")
    print("="*70)
    
    # Create temporary directory
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        # Step 1: Download audio
        print("\n1️⃣ Downloading audio...")
        start_download = time.time()
        audio_path, video_info = app.download_audio(url, temp_dir)
        download_time = time.time() - start_download
        
        file_size_mb = audio_path.stat().st_size / (1024 * 1024)
        duration_sec = video_info.get('duration', 0)
        duration_min = duration_sec / 60
        
        print(f"   ✅ Downloaded: {file_size_mb:.2f} MB")
        print(f"   📹 Video: {video_info.get('title', 'Unknown')}")
        print(f"   ⏱️  Duration: {duration_min:.1f} minutes ({duration_sec:.0f}s)")
        print(f"   ⏱️  Download time: {download_time:.1f}s")
        
        # Step 2: Load Whisper model on GPU
        print("\n2️⃣ Loading Whisper model on GPU...")
        start_load = time.time()
        
        # Try small model with int8 (best for GTX 1080)
        model = WhisperModel("small", device="cuda", compute_type="int8")
        
        load_time = time.time() - start_load
        print(f"   ✅ Model loaded in {load_time:.1f}s")
        print(f"   🎯 Model: small (int8)")
        print(f"   🎮 Device: CUDA (GTX 1080)")
        
        # Step 3: Transcribe with GPU
        print("\n3️⃣ Transcribing audio with local GPU...")
        print(f"   ⏳ Processing {duration_min:.1f} minutes of audio...")
        print(f"   💡 This may take 6-10 minutes - watch your GPU usage!")
        
        start_transcribe = time.time()
        
        segments, info = model.transcribe(
            str(audio_path),
            language="en",
            beam_size=5,
            word_timestamps=False
        )
        
        # Collect segments (this actually processes them)
        segment_list = []
        last_update = time.time()
        
        for i, segment in enumerate(segments):
            segment_list.append(segment)
            
            # Progress update every 10 seconds
            if time.time() - last_update > 10:
                elapsed = time.time() - start_transcribe
                progress = (segment.end / duration_sec) * 100 if duration_sec > 0 else 0
                print(f"   ⏳ Progress: {progress:.1f}% - {elapsed:.0f}s elapsed - at {segment.end/60:.1f} min mark")
                last_update = time.time()
        
        transcribe_time = time.time() - start_transcribe
        
        # Collect full text
        full_text = " ".join([seg.text for seg in segment_list])
        word_count = len(full_text.split())
        
        print(f"\n   ✅ Transcription complete!")
        print(f"   📝 Segments: {len(segment_list)}")
        print(f"   📝 Words: {word_count:,}")
        print(f"   ⏱️  Time: {transcribe_time:.1f}s ({transcribe_time/60:.1f} minutes)")
        
        # Calculate stats
        print("\n" + "="*70)
        print("📊 PERFORMANCE SUMMARY")
        print("="*70)
        
        total_time = download_time + load_time + transcribe_time
        speedup = duration_sec / transcribe_time
        
        print(f"Video Duration:     {duration_min:.1f} minutes")
        print(f"Download Time:      {download_time:.1f}s")
        print(f"Model Load Time:    {load_time:.1f}s")
        print(f"Transcription Time: {transcribe_time:.1f}s ({transcribe_time/60:.1f} min)")
        print(f"Total Time:         {total_time:.1f}s ({total_time/60:.1f} min)")
        print(f"\n🚀 Processing Speed: {speedup:.1f}x real-time")
        print(f"💰 Cost: $0.00 (FREE!)")
        
        # Compare with OpenAI API
        print("\n" + "="*70)
        print("⚖️  COMPARISON: Local GPU vs OpenAI API")
        print("="*70)
        
        openai_time_min = 10  # Estimated from previous test
        openai_cost = duration_min * 0.006
        
        print(f"\n{'Metric':<25} {'Local GPU':<20} {'OpenAI API':<20}")
        print("-" * 70)
        print(f"{'Processing Time':<25} {transcribe_time/60:.1f} min{'':<13} ~{openai_time_min} min")
        print(f"{'Cost':<25} FREE{'':<16} ${openai_cost:.2f}")
        print(f"{'Accuracy':<25} ~90-95%{'':<12} ~98-99%")
        print(f"{'Internet Required':<25} Download only{'':<8} Yes (continuous)")
        print(f"{'Privacy':<25} Local{'':<15} Cloud")
        
        if transcribe_time/60 < openai_time_min:
            print(f"\n✅ LOCAL GPU IS FASTER by {openai_time_min - transcribe_time/60:.1f} minutes!")
        else:
            print(f"\n⚠️  OpenAI API is faster by {transcribe_time/60 - openai_time_min:.1f} minutes")
        
        print("\n" + "="*70)
        
        # Cleanup
        print("\n4️⃣ Cleaning up...")
        shutil.rmtree(temp_dir)
        print("   ✅ Cleanup complete")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        # Cleanup on error
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        
        return False

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🎮 GPU-ACCELERATED WHISPER TEST")
    print("Testing with GTX 1080")
    print("="*70)
    
    success = test_local_whisper()
    
    print("\n" + "="*70)
    if success:
        print("✅ TEST COMPLETE - GPU transcription works!")
        print("\nReady to integrate into your app!")
    else:
        print("❌ TEST FAILED - See errors above")
    print("="*70 + "\n")
    
    sys.exit(0 if success else 1)

