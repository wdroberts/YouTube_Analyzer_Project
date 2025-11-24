"""
YouTube Analyzer - Database Module
Manages SQLite database for project storage, search, and organization.
"""
import json
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Project:
    """Project data model."""
    id: Optional[int] = None
    type: str = ""  # 'youtube' or 'document'
    title: str = ""
    content_title: str = ""
    source: str = ""  # URL for videos, filename for documents
    created_at: str = ""
    word_count: int = 0
    segment_count: int = 0
    project_dir: str = ""
    notes: str = ""
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class DatabaseManager:
    """Manages all database operations for YouTube Analyzer."""
    
    def __init__(self, db_path: Path):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.
        
        Yields:
            sqlite3.Connection: Database connection
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def _init_database(self):
        """Create database tables if they don't exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Projects table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    title TEXT,
                    content_title TEXT,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    word_count INTEGER DEFAULT 0,
                    segment_count INTEGER DEFAULT 0,
                    project_dir TEXT NOT NULL UNIQUE,
                    notes TEXT DEFAULT ''
                )
            """)
            
            # Tags table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                )
            """)
            
            # Project-Tags junction table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project_tags (
                    project_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    PRIMARY KEY (project_id, tag_id),
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
                )
            """)
            
            # Full-text search virtual table
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS project_content_fts USING fts5(
                    project_id UNINDEXED,
                    transcript_text,
                    summary_text,
                    key_factors_text
                )
            """)
            
            # Create indexes for better performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_projects_type ON projects(type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_projects_project_dir ON projects(project_dir)
            """)
            
            logger.info("Database initialized successfully")
    
    def insert_project(self, project: Project, transcript: str = "", 
                      summary: str = "", key_factors: str = "") -> int:
        """
        Insert a new project into the database.
        
        Args:
            project: Project object with metadata
            transcript: Full transcript text for FTS
            summary: Summary text for FTS
            key_factors: Key factors text for FTS
            
        Returns:
            ID of inserted project
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Insert project
            cursor.execute("""
                INSERT INTO projects (
                    type, title, content_title, source, created_at,
                    word_count, segment_count, project_dir, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project.type,
                project.title,
                project.content_title,
                project.source,
                project.created_at or datetime.now().isoformat(),
                project.word_count,
                project.segment_count,
                project.project_dir,
                project.notes
            ))
            
            project_id = cursor.lastrowid
            
            # Insert full-text search content
            if transcript or summary or key_factors:
                cursor.execute("""
                    INSERT INTO project_content_fts (
                        project_id, transcript_text, summary_text, key_factors_text
                    ) VALUES (?, ?, ?, ?)
                """, (project_id, transcript, summary, key_factors))
            
            # Insert tags
            for tag_name in project.tags:
                self._add_tag_to_project(cursor, project_id, tag_name)
            
            logger.info(f"Inserted project {project_id}: {project.title}")
            return project_id
    
    def _add_tag_to_project(self, cursor, project_id: int, tag_name: str):
        """
        Add a tag to a project (internal helper).
        
        Args:
            cursor: Database cursor
            project_id: Project ID
            tag_name: Tag name
        """
        # Get or create tag
        cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        row = cursor.fetchone()
        
        if row:
            tag_id = row[0]
        else:
            cursor.execute("INSERT INTO tags (name) VALUES (?)", (tag_name,))
            tag_id = cursor.lastrowid
        
        # Link tag to project (ignore if already exists)
        cursor.execute("""
            INSERT OR IGNORE INTO project_tags (project_id, tag_id)
            VALUES (?, ?)
        """, (project_id, tag_id))
    
    def update_project(self, project_id: int, **kwargs):
        """
        Update project fields.
        
        Args:
            project_id: Project ID
            **kwargs: Fields to update (title, notes, etc.)
        """
        allowed_fields = {
            'title', 'content_title', 'source', 'word_count',
            'segment_count', 'notes'
        }
        
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not updates:
            return
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [project_id]
            
            cursor.execute(f"""
                UPDATE projects SET {set_clause} WHERE id = ?
            """, values)
            
            logger.info(f"Updated project {project_id}")
    
    def delete_project(self, project_id: int):
        """
        Delete a project from database.
        
        Args:
            project_id: Project ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Delete from FTS table
            cursor.execute("""
                DELETE FROM project_content_fts WHERE project_id = ?
            """, (project_id,))
            
            # Delete project (cascade will handle tags)
            cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            
            logger.info(f"Deleted project {project_id}")
    
    def get_project(self, project_id: int) -> Optional[Project]:
        """
        Get a single project by ID.
        
        Args:
            project_id: Project ID
            
        Returns:
            Project object or None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            # Get tags
            cursor.execute("""
                SELECT t.name FROM tags t
                JOIN project_tags pt ON t.id = pt.tag_id
                WHERE pt.project_id = ?
            """, (project_id,))
            tags = [r[0] for r in cursor.fetchall()]
            
            return Project(
                id=row['id'],
                type=row['type'],
                title=row['title'],
                content_title=row['content_title'],
                source=row['source'],
                created_at=row['created_at'],
                word_count=row['word_count'],
                segment_count=row['segment_count'],
                project_dir=row['project_dir'],
                notes=row['notes'],
                tags=tags
            )
    
    def get_project_by_dir(self, project_dir: str) -> Optional[Project]:
        """
        Get a project by its directory name.
        
        Args:
            project_dir: Project directory name
            
        Returns:
            Project object or None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM projects WHERE project_dir = ?", (project_dir,))
            row = cursor.fetchone()
            
            if row:
                return self.get_project(row['id'])
            return None
    
    def list_projects(self, project_type: Optional[str] = None,
                     tags: Optional[List[str]] = None,
                     search_query: Optional[str] = None,
                     limit: Optional[int] = None,
                     offset: int = 0,
                     order_by: str = "created_at",
                     order_desc: bool = True) -> List[Project]:
        """
        List projects with optional filtering.
        
        Args:
            project_type: Filter by 'youtube' or 'document'
            tags: Filter by tags (AND logic - must have all tags)
            search_query: Search in title and content_title
            limit: Maximum number of results
            offset: Number of results to skip
            order_by: Column to sort by
            order_desc: Sort descending if True
            
        Returns:
            List of Project objects
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT DISTINCT p.* FROM projects p"
            conditions = []
            params = []
            
            # Join with tags if filtering by tags
            if tags:
                query += """
                    JOIN project_tags pt ON p.id = pt.project_id
                    JOIN tags t ON pt.tag_id = t.id
                """
                tag_placeholders = ",".join(["?" for _ in tags])
                conditions.append(f"t.name IN ({tag_placeholders})")
                params.extend(tags)
            
            # Type filter
            if project_type:
                conditions.append("p.type = ?")
                params.append(project_type)
            
            # Search query
            if search_query:
                conditions.append("""
                    (p.title LIKE ? OR p.content_title LIKE ? OR p.source LIKE ?)
                """)
                search_param = f"%{search_query}%"
                params.extend([search_param, search_param, search_param])
            
            # Add WHERE clause
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            # Tag count filter (ensure project has ALL specified tags)
            if tags and len(tags) > 1:
                query += f" GROUP BY p.id HAVING COUNT(DISTINCT t.name) = {len(tags)}"
            
            # Order by
            order_direction = "DESC" if order_desc else "ASC"
            query += f" ORDER BY p.{order_by} {order_direction}"
            
            # Limit and offset
            if limit:
                query += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            projects = []
            for row in rows:
                # Get tags for this project
                cursor.execute("""
                    SELECT t.name FROM tags t
                    JOIN project_tags pt ON t.id = pt.tag_id
                    WHERE pt.project_id = ?
                """, (row['id'],))
                project_tags = [r[0] for r in cursor.fetchall()]
                
                projects.append(Project(
                    id=row['id'],
                    type=row['type'],
                    title=row['title'],
                    content_title=row['content_title'],
                    source=row['source'],
                    created_at=row['created_at'],
                    word_count=row['word_count'],
                    segment_count=row['segment_count'],
                    project_dir=row['project_dir'],
                    notes=row['notes'],
                    tags=project_tags
                ))
            
            return projects
    
    def search_fulltext(self, query: str, limit: int = 50) -> List[Tuple[int, float]]:
        """
        Full-text search in project content.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of (project_id, rank) tuples, sorted by relevance
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT project_id, rank
                FROM project_content_fts
                WHERE project_content_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
            
            return [(row[0], row[1]) for row in cursor.fetchall()]
    
    def add_tag(self, project_id: int, tag_name: str):
        """
        Add a tag to a project.
        
        Args:
            project_id: Project ID
            tag_name: Tag name
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            self._add_tag_to_project(cursor, project_id, tag_name)
            logger.info(f"Added tag '{tag_name}' to project {project_id}")
    
    def remove_tag(self, project_id: int, tag_name: str):
        """
        Remove a tag from a project.
        
        Args:
            project_id: Project ID
            tag_name: Tag name
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM project_tags
                WHERE project_id = ?
                AND tag_id = (SELECT id FROM tags WHERE name = ?)
            """, (project_id, tag_name))
            
            logger.info(f"Removed tag '{tag_name}' from project {project_id}")
    
    def get_all_tags(self) -> List[str]:
        """
        Get all unique tags in the database.
        
        Returns:
            List of tag names
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM tags ORDER BY name")
            return [row[0] for row in cursor.fetchall()]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dictionary with various statistics
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Total projects
            cursor.execute("SELECT COUNT(*) FROM projects")
            stats['total_projects'] = cursor.fetchone()[0]
            
            # Projects by type
            cursor.execute("""
                SELECT type, COUNT(*) FROM projects GROUP BY type
            """)
            stats['by_type'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Total word count
            cursor.execute("SELECT SUM(word_count) FROM projects")
            stats['total_words'] = cursor.fetchone()[0] or 0
            
            # Total tags
            cursor.execute("SELECT COUNT(*) FROM tags")
            stats['total_tags'] = cursor.fetchone()[0]
            
            # Most used tags
            cursor.execute("""
                SELECT t.name, COUNT(pt.project_id) as count
                FROM tags t
                JOIN project_tags pt ON t.id = pt.tag_id
                GROUP BY t.name
                ORDER BY count DESC
                LIMIT 10
            """)
            stats['top_tags'] = [(row[0], row[1]) for row in cursor.fetchall()]
            
            # Projects per month (last 12 months)
            cursor.execute("""
                SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as count
                FROM projects
                WHERE created_at >= date('now', '-12 months')
                GROUP BY month
                ORDER BY month DESC
            """)
            stats['projects_per_month'] = [(row[0], row[1]) for row in cursor.fetchall()]
            
            return stats
    
    def export_to_json(self, output_path: Path):
        """
        Export entire database to JSON.
        
        Args:
            output_path: Path to output JSON file
        """
        projects = self.list_projects()
        
        export_data = {
            'export_date': datetime.now().isoformat(),
            'total_projects': len(projects),
            'projects': [
                {
                    'id': p.id,
                    'type': p.type,
                    'title': p.title,
                    'content_title': p.content_title,
                    'source': p.source,
                    'created_at': p.created_at,
                    'word_count': p.word_count,
                    'segment_count': p.segment_count,
                    'project_dir': p.project_dir,
                    'notes': p.notes,
                    'tags': p.tags
                }
                for p in projects
            ]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported database to {output_path}")
    
    def backup_database(self, backup_path: Path):
        """
        Create a backup copy of the database.
        
        Args:
            backup_path: Path for backup file
        """
        import shutil
        shutil.copy2(self.db_path, backup_path)
        logger.info(f"Database backed up to {backup_path}")

