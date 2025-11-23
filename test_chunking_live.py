"""
Live test script for audio chunking functionality.
Tests with the actual YouTube video.
"""
import sys
from pathlib import Path

# Import app module
import importlib.util
spec = importlib.util.spec_from_file_location("app", Path(__file__).parent / "app.py.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

def test_video_chunking():
    """Test chunking with real YouTube video."""
    import tempfile
    import shutil
    
    url = "https://youtu.be/Ht9XtcV7ZYk"
    
    print(f"Testing audio chunking with: {url}")
    print("=" * 60)
    
    # Create temporary directory
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        print("\n1️⃣ Downloading audio...")
        audio_path, video_info = app.download_audio(url, temp_dir)
        
        file_size_mb = audio_path.stat().st_size / (1024 * 1024)
        print(f"   ✅ Audio downloaded: {file_size_mb:.2f} MB")
        print(f"   📹 Video: {video_info.get('title', 'Unknown')}")
        
        print("\n2️⃣ Testing audio chunking...")
        chunks = app.split_audio_file(audio_path)
        
        print(f"   ✅ Split into {len(chunks)} chunk(s)")
        
        for i, chunk in enumerate(chunks):
            chunk_size_mb = chunk.stat().st_size / (1024 * 1024)
            print(f"   📦 Chunk {i+1}: {chunk.name} ({chunk_size_mb:.2f} MB)")
        
        if len(chunks) > 1:
            print(f"\n✅ SUCCESS! Audio chunking works correctly!")
            print(f"   • Original: {file_size_mb:.2f} MB")
            print(f"   • Chunks: {len(chunks)}")
            print(f"   • No infinite loop!")
        else:
            print(f"\n✅ File small enough - no chunking needed")
        
        # Cleanup
        print("\n3️⃣ Cleaning up temporary files...")
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
    print("\n" + "="*60)
    print("🧪 AUDIO CHUNKING LIVE TEST")
    print("="*60)
    
    success = test_video_chunking()
    
    print("\n" + "="*60)
    if success:
        print("✅ TEST PASSED - Chunking works correctly!")
    else:
        print("❌ TEST FAILED - See errors above")
    print("="*60 + "\n")
    
    sys.exit(0 if success else 1)

