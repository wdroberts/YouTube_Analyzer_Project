"""
Test script for database integration
Tests all core database functionality
"""
import sys
import tempfile
from pathlib import Path
from datetime import datetime

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from database import DatabaseManager, Project, ProjectNotFoundError

def test_database():
    """Test all database operations"""
    print("=" * 60)
    print("DATABASE INTEGRATION TEST")
    print("=" * 60)
    
    # Create temporary database for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        print(f"\n1. Creating test database at: {db_path}")
        
        db_manager = DatabaseManager(db_path)
        print("   [OK] Database created and initialized")
        
        # Test 1: Insert a YouTube project
        print("\n2. Testing project insertion (YouTube video)...")
        project1 = Project(
            type='youtube',
            title='Test Video Title',
            content_title='AI and Machine Learning Basics',
            source='https://youtube.com/watch?v=test123',
            created_at=datetime.now().isoformat(),
            word_count=1500,
            segment_count=45,
            project_dir='test_video_123',
            notes='This is a test video',
            tags=['tutorial', 'AI', 'beginner']
        )
        
        transcript = "This is a sample transcript about machine learning and artificial intelligence."
        summary = "A comprehensive introduction to AI and ML concepts."
        key_factors = "Main ideas: Neural networks, Deep learning, Training models"
        
        project1_id = db_manager.insert_project(project1, transcript, summary, key_factors)
        print(f"   [OK] YouTube project inserted with ID: {project1_id}")
        
        # Test 2: Insert a document project
        print("\n3. Testing project insertion (Document)...")
        project2 = Project(
            type='document',
            title='Research Paper.pdf',
            content_title='Climate Change Analysis',
            source='Research Paper.pdf',
            created_at=datetime.now().isoformat(),
            word_count=3200,
            segment_count=0,
            project_dir='doc_uuid_456',
            notes='Important research',
            tags=['research', 'climate', 'science']
        )
        
        doc_text = "Climate change is affecting global temperatures and weather patterns."
        doc_summary = "Analysis of climate change impacts on global ecosystems."
        doc_factors = "Key points: Temperature rise, Sea level changes, Policy recommendations"
        
        project2_id = db_manager.insert_project(project2, doc_text, doc_summary, doc_factors)
        print(f"   [OK] Document project inserted with ID: {project2_id}")
        
        # Test 3: Retrieve project
        print("\n4. Testing project retrieval...")
        retrieved = db_manager.get_project(project1_id)
        assert retrieved is not None, "Project should be retrieved"
        assert retrieved.title == 'Test Video Title', "Title should match"
        assert len(retrieved.tags) == 3, "Should have 3 tags"
        print(f"   [OK] Retrieved project: {retrieved.title}")
        print(f"   [OK] Tags: {', '.join(retrieved.tags)}")
        
        # Test 4: List projects
        print("\n5. Testing project listing...")
        all_projects = db_manager.list_projects()
        assert len(all_projects) == 2, "Should have 2 projects"
        print(f"   [OK] Found {len(all_projects)} projects")
        
        # Test 5: Filter by type
        print("\n6. Testing filtering by type...")
        youtube_projects = db_manager.list_projects(project_type='youtube')
        assert len(youtube_projects) == 1, "Should have 1 YouTube project"
        print(f"   [OK] Found {len(youtube_projects)} YouTube projects")
        
        # Test 6: Filter by tags
        print("\n7. Testing filtering by tags...")
        ai_projects = db_manager.list_projects(tags=['AI'])
        assert len(ai_projects) == 1, "Should have 1 project with AI tag"
        print(f"   [OK] Found {len(ai_projects)} projects with 'AI' tag")
        
        # Test 7: Search by title
        print("\n8. Testing metadata search...")
        search_results = db_manager.list_projects(search_query='Climate')
        assert len(search_results) == 1, "Should find climate project"
        print(f"   [OK] Search for 'Climate' found {len(search_results)} project(s)")
        
        # Test 8: Full-text search
        print("\n9. Testing full-text search...")
        fts_results = db_manager.search_fulltext('machine learning')
        assert len(fts_results) >= 1, "Should find project with 'machine learning'"
        print(f"   [OK] Full-text search found {len(fts_results)} result(s)")
        
        # Test 9: Add tag
        print("\n10. Testing tag addition...")
        db_manager.add_tag(project1_id, 'advanced')
        updated = db_manager.get_project(project1_id)
        assert 'advanced' in updated.tags, "New tag should be added"
        print(f"   [OK] Added 'advanced' tag. Total tags: {len(updated.tags)}")
        
        # Test 10: Remove tag
        print("\n11. Testing tag removal...")
        db_manager.remove_tag(project1_id, 'beginner')
        updated = db_manager.get_project(project1_id)
        assert 'beginner' not in updated.tags, "Tag should be removed"
        print(f"   [OK] Removed 'beginner' tag. Remaining tags: {', '.join(updated.tags)}")
        
        # Test 11: Update project
        print("\n12. Testing project update...")
        db_manager.update_project(project1_id, notes='Updated notes for testing')
        updated = db_manager.get_project(project1_id)
        assert updated.notes == 'Updated notes for testing', "Notes should be updated"
        print(f"   [OK] Updated notes: '{updated.notes}'")
        
        # Test 12: Get all tags
        print("\n13. Testing get all tags...")
        all_tags = db_manager.get_all_tags()
        print(f"   [OK] Found {len(all_tags)} unique tags: {', '.join(all_tags)}")
        
        # Test 13: Statistics
        print("\n14. Testing statistics...")
        stats = db_manager.get_statistics()
        print(f"   [OK] Total projects: {stats['total_projects']}")
        print(f"   [OK] Total words: {stats['total_words']}")
        print(f"   [OK] Projects by type: {stats['by_type']}")
        if stats['top_tags']:
            print(f"   [OK] Top tags: {stats['top_tags'][:3]}")
        
        # Test 14: Export to JSON
        print("\n15. Testing JSON export...")
        export_path = Path(tmpdir) / "export.json"
        db_manager.export_to_json(export_path)
        assert export_path.exists(), "Export file should be created"
        print(f"   [OK] Exported database to {export_path}")
        
        # Test 15: Database backup
        print("\n16. Testing database backup...")
        backup_path = Path(tmpdir) / "backup.db"
        db_manager.backup_database(backup_path)
        assert backup_path.exists(), "Backup file should be created"
        print(f"   [OK] Created backup at {backup_path}")
        
        # Test 16: Delete project
        print("\n17. Testing project deletion...")
        db_manager.delete_project(project2_id)
        try:
            deleted = db_manager.get_project(project2_id)
            assert False, "Should have raised ProjectNotFoundError"
        except ProjectNotFoundError:
            print(f"   [OK] Deleted project not found (as expected)")
        
        remaining = db_manager.list_projects()
        assert len(remaining) == 1, "Should have 1 project remaining"
        print(f"   [OK] Remaining projects: {len(remaining)}")
        
        # Test 17: Get project by directory
        print("\n18. Testing get project by directory...")
        by_dir = db_manager.get_project_by_dir('test_video_123')
        assert by_dir is not None, "Should find project by directory name"
        assert by_dir.id == project1_id, "Should be the same project"
        print(f"   [OK] Found project by directory: {by_dir.title}")
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        print("\nDatabase integration is working correctly!")
        print("- Project insertion: OK")
        print("- Project retrieval: OK")
        print("- Filtering and search: OK")
        print("- Tag management: OK")
        print("- Full-text search: OK")
        print("- Statistics: OK")
        print("- Export/backup: OK")
        print("- Delete operations: OK")
        
        return True

if __name__ == '__main__':
    try:
        success = test_database()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

