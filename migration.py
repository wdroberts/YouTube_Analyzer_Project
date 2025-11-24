"""
YouTube Analyzer - Migration Script
Migrates existing file-based projects to database and D: drive.
"""
import json
import logging
import shutil
from pathlib import Path
from typing import List, Tuple

from database import DatabaseManager, Project

logger = logging.getLogger(__name__)


class MigrationManager:
    """Manages migration of existing projects to new database system."""
    
    def __init__(self, db_manager: DatabaseManager, old_output_dir: Path, new_output_dir: Path):
        """
        Initialize migration manager.
        
        Args:
            db_manager: Database manager instance
            old_output_dir: Current outputs directory (usually ./outputs)
            new_output_dir: New outputs directory on D: drive
        """
        self.db_manager = db_manager
        self.old_output_dir = old_output_dir
        self.new_output_dir = new_output_dir
    
    def needs_migration(self) -> bool:
        """
        Check if migration is needed.
        
        Returns:
            True if old projects exist and haven't been migrated
        """
        if not self.old_output_dir.exists():
            return False
        
        # Check if there are any metadata.json files in old directory
        old_projects = list(self.old_output_dir.glob("*/metadata.json"))
        return len(old_projects) > 0
    
    def find_old_projects(self) -> List[Path]:
        """
        Find all project directories in old output folder.
        
        Returns:
            List of project directory paths
        """
        if not self.old_output_dir.exists():
            return []
        
        projects = []
        for project_dir in self.old_output_dir.iterdir():
            if project_dir.is_dir():
                metadata_file = project_dir / "metadata.json"
                if metadata_file.exists():
                    projects.append(project_dir)
        
        return projects
    
    def migrate_project(self, old_project_dir: Path) -> Tuple[bool, str]:
        """
        Migrate a single project to database and new location.
        
        Args:
            old_project_dir: Path to old project directory
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            metadata_file = old_project_dir / "metadata.json"
            
            # Read metadata
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            project_dir_name = old_project_dir.name
            
            # Check if already migrated
            existing = self.db_manager.get_project_by_dir(project_dir_name)
            if existing:
                return False, f"Already migrated: {project_dir_name}"
            
            # Determine project type
            project_type = 'youtube' if 'url' in metadata else 'document'
            
            # Create project object
            project = Project(
                type=project_type,
                title=metadata.get('title', ''),
                content_title=metadata.get('transcript_title') or metadata.get('content_title', ''),
                source=metadata.get('url') or metadata.get('filename', ''),
                created_at=metadata.get('timestamp', ''),
                word_count=metadata.get('word_count', 0),
                segment_count=metadata.get('segment_count', 0),
                project_dir=project_dir_name,
                notes='',
                tags=[]
            )
            
            # Read content for full-text search
            transcript = ""
            summary = ""
            key_factors = ""
            
            transcript_file = old_project_dir / "transcript.txt"
            extracted_text_file = old_project_dir / "extracted_text.txt"
            summary_file = old_project_dir / "summary.txt"
            key_factors_file = old_project_dir / "key_factors.txt"
            
            if transcript_file.exists():
                with open(transcript_file, 'r', encoding='utf-8') as f:
                    transcript = f.read()
            elif extracted_text_file.exists():
                with open(extracted_text_file, 'r', encoding='utf-8') as f:
                    transcript = f.read()
            
            if summary_file.exists():
                with open(summary_file, 'r', encoding='utf-8') as f:
                    summary = f.read()
            
            if key_factors_file.exists():
                with open(key_factors_file, 'r', encoding='utf-8') as f:
                    key_factors = f.read()
            
            # Insert into database
            project_id = self.db_manager.insert_project(
                project, 
                transcript=transcript,
                summary=summary,
                key_factors=key_factors
            )
            
            # Copy files to new location
            new_project_dir = self.new_output_dir / project_dir_name
            
            if not new_project_dir.exists():
                shutil.copytree(old_project_dir, new_project_dir)
                logger.info(f"Copied files from {old_project_dir} to {new_project_dir}")
            
            return True, f"Migrated: {project.title or project_dir_name}"
            
        except Exception as e:
            logger.error(f"Failed to migrate {old_project_dir.name}: {e}")
            return False, f"Error: {old_project_dir.name} - {str(e)}"
    
    def migrate_all(self, progress_callback=None) -> Tuple[int, int, List[str]]:
        """
        Migrate all old projects.
        
        Args:
            progress_callback: Optional callback(current, total, message) for progress updates
            
        Returns:
            Tuple of (success_count, fail_count, error_messages)
        """
        old_projects = self.find_old_projects()
        total = len(old_projects)
        
        if total == 0:
            return 0, 0, []
        
        success_count = 0
        fail_count = 0
        error_messages = []
        
        for i, old_project_dir in enumerate(old_projects, 1):
            if progress_callback:
                progress_callback(i, total, f"Migrating {old_project_dir.name}...")
            
            success, message = self.migrate_project(old_project_dir)
            
            if success:
                success_count += 1
            else:
                fail_count += 1
                error_messages.append(message)
        
        return success_count, fail_count, error_messages
    
    def cleanup_old_files(self, confirm: bool = False):
        """
        Delete old project files after successful migration.
        
        Args:
            confirm: Must be True to actually delete files
        """
        if not confirm:
            raise ValueError("Must confirm cleanup by passing confirm=True")
        
        if self.old_output_dir.exists():
            shutil.rmtree(self.old_output_dir)
            logger.info(f"Deleted old output directory: {self.old_output_dir}")
    
    def create_backup(self, backup_dir: Path):
        """
        Create a backup of old files before migration.
        
        Args:
            backup_dir: Directory to store backup
        """
        if not self.old_output_dir.exists():
            return
        
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"outputs_backup_{Path.cwd().name}"
        
        if backup_path.exists():
            # Add timestamp to make unique
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"outputs_backup_{timestamp}"
        
        shutil.copytree(self.old_output_dir, backup_path)
        logger.info(f"Created backup at {backup_path}")
        
        return backup_path


def perform_migration_check_and_migrate(db_manager: DatabaseManager, 
                                       old_output_dir: Path, 
                                       new_output_dir: Path,
                                       progress_callback=None) -> Tuple[bool, str]:
    """
    Check if migration is needed and perform it automatically.
    
    Args:
        db_manager: Database manager instance
        old_output_dir: Current outputs directory
        new_output_dir: New outputs directory on D: drive
        progress_callback: Optional callback for progress updates
        
    Returns:
        Tuple of (migrated: bool, message: str)
    """
    migration_manager = MigrationManager(db_manager, old_output_dir, new_output_dir)
    
    if not migration_manager.needs_migration():
        return False, "No migration needed"
    
    # Create backup before migration
    try:
        backup_dir = Path.cwd() / "backups"
        backup_path = migration_manager.create_backup(backup_dir)
        logger.info(f"Backup created: {backup_path}")
    except Exception as e:
        logger.warning(f"Failed to create backup: {e}")
    
    # Perform migration
    success_count, fail_count, errors = migration_manager.migrate_all(progress_callback)
    
    total = success_count + fail_count
    message = f"Migration complete: {success_count}/{total} projects migrated successfully"
    
    if errors:
        message += f"\n{fail_count} errors occurred"
        for error in errors[:5]:  # Show first 5 errors
            message += f"\n  - {error}"
    
    return True, message

