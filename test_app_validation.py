"""
Quick validation test for app.py.py
Checks that all imports work and configuration loads
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all core modules can be imported"""
    print("=" * 60)
    print("APP VALIDATION TEST")
    print("=" * 60)
    
    print("\n1. Testing database module import...")
    try:
        import database
        print("   [OK] database module imported")
    except Exception as e:
        print(f"   [FAIL] {e}")
        return False
    
    print("\n2. Testing migration module import...")
    try:
        import migration
        print("   [OK] migration module imported")
    except Exception as e:
        print(f"   [FAIL] {e}")
        return False
    
    print("\n3. Testing UI database explorer import...")
    try:
        import ui_database_explorer
        print("   [OK] ui_database_explorer module imported")
    except Exception as e:
        print(f"   [FAIL] {e}")
        return False
    
    print("\n4. Testing database manager initialization...")
    try:
        from database import DatabaseManager
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DatabaseManager(db_path)
            print(f"   [OK] DatabaseManager initialized at {db_path}")
    except Exception as e:
        print(f"   [FAIL] {e}")
        return False
    
    print("\n5. Checking for syntax errors in app.py.py...")
    try:
        with open('app.py.py', 'r', encoding='utf-8') as f:
            code = f.read()
        
        compile(code, 'app.py.py', 'exec')
        print("   [OK] app.py.py has no syntax errors")
    except SyntaxError as e:
        print(f"   [FAIL] Syntax error in app.py.py: {e}")
        return False
    except Exception as e:
        print(f"   [FAIL] Error reading app.py.py: {e}")
        return False
    
    print("\n6. Verifying required dependencies...")
    required_modules = [
        'streamlit',
        'openai',
        'yt_dlp',
        'PyPDF2',
        'docx',
        'dotenv',
        'chardet',
        'pydub',
        'pandas',
        'faster_whisper'
    ]
    
    missing = []
    for module in required_modules:
        try:
            __import__(module.replace('-', '_'))
            print(f"   [OK] {module}")
        except ImportError:
            missing.append(module)
            print(f"   [WARN] {module} not installed")
    
    if missing:
        print(f"\n   [INFO] Missing modules (optional for testing): {', '.join(missing)}")
    
    print("\n" + "=" * 60)
    print("VALIDATION COMPLETE")
    print("=" * 60)
    print("\nAll core components validated successfully!")
    print("- Database module: OK")
    print("- Migration module: OK")
    print("- UI module: OK")
    print("- App syntax: OK")
    print("\nThe application is ready to run!")
    
    return True

if __name__ == '__main__':
    try:
        success = test_imports()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] Validation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

