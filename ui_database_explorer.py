"""
YouTube Analyzer - Database Explorer UI
Provides comprehensive database viewing and management interface.
"""
import csv
import io
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from database import DatabaseManager, Project

# Get logger
logger = logging.getLogger(__name__)


def render_database_explorer(db_manager: DatabaseManager, output_dir: Path):
    """
    Render the database explorer page.
    
    Args:
        db_manager: Database manager instance
        output_dir: Path to outputs directory
    """
    st.header("🗄️ Database Explorer")
    st.write("Browse, search, and manage your projects with advanced database tools.")
    
    # Create tabs for different sections
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Table Viewer", 
        "🔍 Advanced Search", 
        "📈 Statistics", 
        "🛠️ Schema & Tools"
    ])
    
    with tab1:
        render_table_viewer(db_manager, output_dir)
    
    with tab2:
        render_advanced_search(db_manager, output_dir)
    
    with tab3:
        render_statistics_dashboard(db_manager)
    
    with tab4:
        render_schema_and_tools(db_manager, output_dir)


def render_table_viewer(db_manager: DatabaseManager, output_dir: Path):
    """Render the table viewer with sorting and pagination."""
    st.subheader("📊 Projects Table")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        filter_type = st.selectbox(
            "Filter by Type",
            options=["All", "YouTube", "Document"],
            key="table_filter_type"
        )
    
    with col2:
        sort_by = st.selectbox(
            "Sort By",
            options=["Date (Newest)", "Date (Oldest)", "Title (A-Z)", "Title (Z-A)", "Word Count"],
            key="table_sort_by"
        )
    
    with col3:
        items_per_page = st.selectbox(
            "Items per Page",
            options=[10, 25, 50, 100],
            index=1,
            key="table_items_per_page"
        )
    
    # Parse sorting
    if sort_by == "Date (Newest)":
        order_by, order_desc = "created_at", True
    elif sort_by == "Date (Oldest)":
        order_by, order_desc = "created_at", False
    elif sort_by == "Title (A-Z)":
        order_by, order_desc = "title", False
    elif sort_by == "Title (Z-A)":
        order_by, order_desc = "title", True
    else:  # Word Count
        order_by, order_desc = "word_count", True
    
    # Get projects
    project_type = None if filter_type == "All" else filter_type.lower()
    all_projects = db_manager.list_projects(
        project_type=project_type,
        order_by=order_by,
        order_desc=order_desc
    )
    
    total_projects = len(all_projects)
    
    if total_projects == 0:
        st.info("No projects found. Process a video or document to get started!")
        return
    
    # Pagination
    if 'table_page' not in st.session_state:
        st.session_state.table_page = 0
    
    total_pages = (total_projects + items_per_page - 1) // items_per_page
    start_idx = st.session_state.table_page * items_per_page
    end_idx = min(start_idx + items_per_page, total_projects)
    
    page_projects = all_projects[start_idx:end_idx]
    
    st.write(f"Showing {start_idx + 1}-{end_idx} of {total_projects} projects")
    
    # Display projects as table
    for project in page_projects:
        with st.expander(f"{'🎥' if project.type == 'youtube' else '📄'} {project.title or project.content_title or 'Untitled'}", expanded=False):
            render_project_details(db_manager, project, output_dir)
    
    # Pagination controls
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("◀ Previous", disabled=st.session_state.table_page == 0):
            st.session_state.table_page -= 1
            st.rerun()
    with col2:
        st.write(f"Page {st.session_state.table_page + 1} of {total_pages}")
    with col3:
        if st.button("Next ▶", disabled=st.session_state.table_page >= total_pages - 1):
            st.session_state.table_page += 1
            st.rerun()


def render_project_details(db_manager: DatabaseManager, project: Project, output_dir: Path):
    """Render detailed view of a single project."""
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Type:** {project.type.capitalize()}")
        st.write(f"**Title:** {project.title}")
        if project.content_title:
            st.write(f"**Content Title:** {project.content_title}")
        st.write(f"**Source:** {project.source}")
    
    with col2:
        st.write(f"**Created:** {project.created_at[:10] if project.created_at else 'Unknown'}")
        st.write(f"**Words:** {project.word_count:,}")
        if project.segment_count:
            st.write(f"**Segments:** {project.segment_count}")
        st.write(f"**Tags:** {', '.join(project.tags) if project.tags else 'None'}")
    
    # Notes section
    st.write("**Notes:**")
    notes_key = f"notes_{project.id}"
    current_notes = st.text_area(
        "Edit notes",
        value=project.notes,
        height=100,
        key=notes_key,
        label_visibility="collapsed"
    )
    
    if current_notes != project.notes:
        if st.button("💾 Save Notes", key=f"save_notes_{project.id}"):
            db_manager.update_project(project.id, notes=current_notes)
            st.success("Notes saved!")
            st.rerun()
    
    # Tags management
    st.write("**Manage Tags:**")
    col1, col2 = st.columns(2)
    
    with col1:
        new_tag = st.text_input(
            "Add new tag",
            key=f"new_tag_{project.id}",
            placeholder="Enter tag name"
        )
        if st.button("➕ Add Tag", key=f"add_tag_{project.id}"):
            if new_tag and new_tag.strip():
                db_manager.add_tag(project.id, new_tag.strip())
                st.success(f"Added tag: {new_tag}")
                st.rerun()
    
    with col2:
        if project.tags:
            tag_to_remove = st.selectbox(
                "Remove tag",
                options=project.tags,
                key=f"remove_tag_{project.id}"
            )
            if st.button("➖ Remove Tag", key=f"remove_tag_btn_{project.id}"):
                db_manager.remove_tag(project.id, tag_to_remove)
                st.success(f"Removed tag: {tag_to_remove}")
                st.rerun()
    
    # Q&A Section
    st.write("---")
    st.write("**💬 Ask Questions About This Content:**")
    
    qa_key = f"qa_mode_{project.id}"
    if qa_key not in st.session_state:
        st.session_state[qa_key] = False
    
    if not st.session_state[qa_key]:
        if st.button("💬 Start Q&A", key=f"start_qa_{project.id}", use_container_width=True):
            st.session_state[qa_key] = True
            st.rerun()
    else:
        # Q&A interface is active
        question_key = f"question_{project.id}"
        question = st.text_input(
            "Your question:",
            key=question_key,
            placeholder="e.g., What are the main topics discussed?"
        )
        
        col1, col2 = st.columns([4, 1])
        
        with col1:
            ask_clicked = st.button("🤔 Ask", key=f"ask_{project.id}", type="primary")
        
        with col2:
            if st.button("Close", key=f"close_qa_{project.id}"):
                st.session_state[qa_key] = False
                st.session_state.pop(f"answer_{project.id}", None)
                st.rerun()
        
        # Process question
        if ask_clicked and question and question.strip():
            with st.spinner("🤔 Thinking..."):
                try:
                    # Import Q&A service - now from dedicated module
                    from qa_service import answer_question_from_transcript
                    
                    # Get OpenAI client from main module
                    import sys
                    main_module = sys.modules.get('__main__')
                    if main_module and hasattr(main_module, 'client'):
                        openai_client = main_module.client
                        openai_model = getattr(main_module.config, 'openai_model', 'gpt-4o-mini')
                    else:
                        st.error("❌ OpenAI client not available. Please restart the app.")
                        return
                    
                    # Get project content
                    content = db_manager.get_project_content(project.id)
                    transcript = content.get('transcript', '')
                    summary = content.get('summary', '')
                    
                    if not transcript:
                        st.error("❌ No transcript available for this project.")
                    else:
                        # Get answer from Q&A service
                        answer = answer_question_from_transcript(
                            question=question,
                            transcript=transcript,
                            title=project.title or project.content_title or "Untitled",
                            summary=summary,
                            client=openai_client,
                            model=openai_model
                        )
                        
                        # Store answer in session state
                        st.session_state[f"answer_{project.id}"] = answer
                        st.rerun()
                        
                except Exception as e:
                    logger.error(f"Q&A error for project {project.id}: {e}")
                    st.error(f"❌ Error: {str(e)}")
        
        # Display stored answer if available
        if f"answer_{project.id}" in st.session_state:
            st.write("---")
            st.write("**Answer:**")
            st.markdown(st.session_state[f"answer_{project.id}"])
            st.write("---")
            st.caption("💡 Tip: Ask another question or click 'Close' to exit Q&A mode.")
    
    # Delete project
    st.write("---")
    if st.button("🗑️ Delete Project", key=f"delete_{project.id}", type="secondary"):
        st.session_state[f"confirm_delete_{project.id}"] = True
    
    if st.session_state.get(f"confirm_delete_{project.id}", False):
        st.warning("⚠️ Are you sure? This will delete the project from the database (files will remain on disk).")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Yes, Delete", key=f"confirm_yes_{project.id}"):
                db_manager.delete_project(project.id)
                st.success("Project deleted!")
                st.session_state.pop(f"confirm_delete_{project.id}", None)
                st.rerun()
        with col2:
            if st.button("❌ Cancel", key=f"confirm_no_{project.id}"):
                st.session_state.pop(f"confirm_delete_{project.id}", None)
                st.rerun()


def render_advanced_search(db_manager: DatabaseManager, output_dir: Path):
    """Render advanced search interface."""
    st.subheader("🔍 Advanced Search")
    
    # Search mode selection
    search_mode = st.radio(
        "Search Mode",
        options=["Metadata Search", "Full-Text Content Search", "Combined Search"],
        horizontal=True
    )
    
    # Metadata search
    if search_mode in ["Metadata Search", "Combined Search"]:
        st.write("**Metadata Filters:**")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            search_title = st.text_input("Search in titles", placeholder="Enter keywords")
        
        with col2:
            search_type = st.selectbox("Type", options=["All", "YouTube", "Document"])
        
        with col3:
            all_tags = db_manager.get_all_tags()
            selected_tags = st.multiselect("Tags", options=all_tags)
    
    # Full-text search
    if search_mode in ["Full-Text Content Search", "Combined Search"]:
        st.write("**Content Search:**")
        fulltext_query = st.text_input(
            "Search within transcripts and summaries",
            placeholder="Enter search terms (supports FTS5 syntax)"
        )
        st.caption("💡 Tip: Use quotes for exact phrases, OR for alternatives, - to exclude terms")
    
    # Execute search
    if st.button("🔍 Search", type="primary"):
        results = []
        
        if search_mode == "Metadata Search":
            # Metadata only
            project_type = None if search_type == "All" else search_type.lower()
            results = db_manager.list_projects(
                project_type=project_type,
                tags=selected_tags if selected_tags else None,
                search_query=search_title if search_title else None
            )
        
        elif search_mode == "Full-Text Content Search":
            # Full-text only
            if fulltext_query:
                fts_results = db_manager.search_fulltext(fulltext_query)
                project_ids = [pid for pid, rank in fts_results]
                results = [db_manager.get_project(pid) for pid in project_ids]
                results = [p for p in results if p is not None]
        
        else:  # Combined
            # Get both and merge
            project_type = None if search_type == "All" else search_type.lower()
            metadata_results = db_manager.list_projects(
                project_type=project_type,
                tags=selected_tags if selected_tags else None,
                search_query=search_title if search_title else None
            )
            
            if fulltext_query:
                fts_results = db_manager.search_fulltext(fulltext_query)
                project_ids = [pid for pid, rank in fts_results]
                fts_projects = [db_manager.get_project(pid) for pid in project_ids]
                fts_projects = [p for p in fts_projects if p is not None]
                
                # Merge (intersection)
                metadata_ids = {p.id for p in metadata_results}
                results = [p for p in fts_projects if p.id in metadata_ids]
            else:
                results = metadata_results
        
        # Display results
        st.write(f"### Found {len(results)} project(s)")
        
        if results:
            for project in results:
                with st.expander(f"{'🎥' if project.type == 'youtube' else '📄'} {project.title or project.content_title}", expanded=False):
                    render_project_details(db_manager, project, output_dir)
        else:
            st.info("No projects found matching your search criteria.")


def render_statistics_dashboard(db_manager: DatabaseManager):
    """Render statistics and analytics dashboard."""
    st.subheader("📈 Statistics Dashboard")
    
    stats = db_manager.get_statistics()
    
    # Overview metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Projects", stats['total_projects'])
    
    with col2:
        youtube_count = stats['by_type'].get('youtube', 0)
        st.metric("YouTube Videos", youtube_count)
    
    with col3:
        doc_count = stats['by_type'].get('document', 0)
        st.metric("Documents", doc_count)
    
    with col4:
        st.metric("Total Words", f"{stats['total_words']:,}")
    
    st.write("---")
    
    # Top tags
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Most Used Tags:**")
        if stats['top_tags']:
            tag_df = pd.DataFrame(stats['top_tags'], columns=['Tag', 'Count'])
            st.bar_chart(tag_df.set_index('Tag'))
        else:
            st.info("No tags yet. Start tagging your projects!")
    
    with col2:
        st.write("**Projects Over Time:**")
        if stats['projects_per_month']:
            month_df = pd.DataFrame(stats['projects_per_month'], columns=['Month', 'Count'])
            st.line_chart(month_df.set_index('Month'))
        else:
            st.info("Not enough data yet.")


def render_schema_and_tools(db_manager: DatabaseManager, output_dir: Path):
    """Render schema explorer and utility tools."""
    st.subheader("🛠️ Schema & Tools")
    
    # Schema explorer
    with st.expander("📋 Database Schema", expanded=True):
        st.write("**Tables and Structure:**")
        
        st.write("**1. `projects` (Main table)**")
        st.code("""
        - id: INTEGER PRIMARY KEY
        - type: TEXT (youtube/document)
        - title: TEXT
        - content_title: TEXT
        - source: TEXT (URL or filename)
        - created_at: TEXT (ISO datetime)
        - word_count: INTEGER
        - segment_count: INTEGER
        - project_dir: TEXT (unique folder name)
        - notes: TEXT
        """, language="sql")
        
        st.write("**2. `tags` (Tag definitions)**")
        st.code("""
        - id: INTEGER PRIMARY KEY
        - name: TEXT (unique)
        """, language="sql")
        
        st.write("**3. `project_tags` (Many-to-many junction)**")
        st.code("""
        - project_id: INTEGER (FK to projects)
        - tag_id: INTEGER (FK to tags)
        """, language="sql")
        
        st.write("**4. `project_content_fts` (Full-text search - FTS5 virtual table)**")
        st.code("""
        - project_id: INTEGER
        - transcript_text: TEXT
        - summary_text: TEXT
        - key_factors_text: TEXT
        """, language="sql")
    
    # Export tools
    st.write("---")
    st.write("**Export Data:**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📥 Export Database to JSON", use_container_width=True):
            export_path = Path("database_export.json")
            db_manager.export_to_json(export_path)
            
            with open(export_path, 'r', encoding='utf-8') as f:
                json_data = f.read()
            
            st.download_button(
                "⬇️ Download JSON",
                data=json_data,
                file_name=f"youtube_analyzer_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
    
    with col2:
        if st.button("📊 Export Projects to CSV", use_container_width=True):
            projects = db_manager.list_projects()
            
            # Convert to CSV
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['ID', 'Type', 'Title', 'Content Title', 'Source', 'Created', 'Words', 'Tags', 'Notes'])
            
            for p in projects:
                writer.writerow([
                    p.id,
                    p.type,
                    p.title,
                    p.content_title,
                    p.source,
                    p.created_at,
                    p.word_count,
                    ', '.join(p.tags),
                    p.notes
                ])
            
            csv_data = output.getvalue()
            
            st.download_button(
                "⬇️ Download CSV",
                data=csv_data,
                file_name=f"youtube_analyzer_projects_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    
    # Database backup
    st.write("---")
    st.write("**Database Maintenance:**")
    
    if st.button("💾 Create Database Backup", use_container_width=True):
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)
        backup_path = backup_dir / f"youtube_analyzer_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        
        db_manager.backup_database(backup_path)
        st.success(f"✅ Backup created: {backup_path}")
        
        with open(backup_path, 'rb') as f:
            backup_data = f.read()
        
        st.download_button(
            "⬇️ Download Backup",
            data=backup_data,
            file_name=backup_path.name,
            mime="application/octet-stream"
        )

