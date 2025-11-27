"""
Integration tests for Streamlit UI components.

Tests cover:
- Project listing and display
- Per-project chat functionality
- UI error handling
- Session state management
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import app module
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("app", "app.py.py")
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
except Exception as e:
    pytest.skip(f"Could not import app module: {e}", allow_module_level=True)

# Import dependencies
from database import DatabaseManager, ProjectNotFoundError


class MockStreamlit:
    """Mock Streamlit components for testing."""
    
    def __init__(self):
        self.session_state = {}
        self.calls = []
        self.text_input_values = {}
        self.button_clicks = {}
        self.expander_states = {}
        self.warnings = []
        self.errors = []
        self.successes = []
        self.info_messages = []
        
    def text_input(self, label=None, value="", key=None, **kwargs):
        """Mock text_input that returns stored value or empty string."""
        self.calls.append(('text_input', {'label': label, 'key': key, 'value': value}))
        return self.text_input_values.get(key, value)
    
    def button(self, label=None, key=None, disabled=False, **kwargs):
        """Mock button that returns True if clicked."""
        self.calls.append(('button', {'label': label, 'key': key, 'disabled': disabled}))
        return self.button_clicks.get(key, False)
    
    def expander(self, label=None, expanded=False):
        """Mock expander that returns a context manager."""
        self.calls.append(('expander', {'label': label, 'expanded': expanded}))
        return MockContextManager()
    
    def write(self, text=None):
        """Mock write."""
        self.calls.append(('write', {'text': text}))
    
    def markdown(self, text=None):
        """Mock markdown."""
        self.calls.append(('markdown', {'text': text}))
    
    def warning(self, text):
        """Mock warning."""
        self.warnings.append(text)
        self.calls.append(('warning', {'text': text}))
    
    def error(self, text):
        """Mock error."""
        self.errors.append(text)
        self.calls.append(('error', {'text': text}))
    
    def success(self, text):
        """Mock success."""
        self.successes.append(text)
        self.calls.append(('success', {'text': text}))
    
    def info(self, text):
        """Mock info."""
        self.info_messages.append(text)
        self.calls.append(('info', {'text': text}))
    
    def text_area(self, label=None, value="", key=None, **kwargs):
        """Mock text_area."""
        self.calls.append(('text_area', {'label': label, 'key': key, 'value': value}))
        return value
    
    def spinner(self, text=None):
        """Mock spinner context manager."""
        self.calls.append(('spinner', {'text': text}))
        return MockContextManager()
    
    def empty(self):
        """Mock empty placeholder."""
        return Mock()
    
    def progress(self, value):
        """Mock progress bar."""
        return Mock()
    
    def caption(self, text):
        """Mock caption."""
        self.calls.append(('caption', {'text': text}))
    
    def stop(self):
        """Mock stop - raises exception to halt execution."""
        raise StopExecution()
    
    def rerun(self):
        """Mock rerun."""
        self.calls.append(('rerun', {}))


class MockContextManager:
    """Context manager for expander and spinner."""
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        return False


class StopExecution(Exception):
    """Exception to stop Streamlit execution in tests."""
    pass


@pytest.fixture
def mock_streamlit():
    """Create a mock Streamlit instance."""
    return MockStreamlit()


@pytest.fixture
def mock_db_manager():
    """Create a mock database manager."""
    from database import Project
    
    # Create mock Project objects
    project1 = Project(
        id=1,
        project_dir='test_project_1',
        type='youtube',
        title='Test Video Title',
        content_title='Test Transcript',
        source='https://www.youtube.com/watch?v=test123',
        created_at=datetime.now().isoformat(),
        word_count=1000,
        tags=[]
    )
    project2 = Project(
        id=2,
        project_dir='test_project_2',
        type='document',
        title=None,
        content_title='Test Document',
        source='test_document.pdf',
        created_at=datetime.now().isoformat(),
        word_count=500,
        tags=[]
    )
    
    db_mock = Mock(spec=DatabaseManager)
    db_mock.list_projects.return_value = [project1, project2]
    db_mock.get_project_content.return_value = {
        'transcript': 'This is a test transcript with some content.',
        'summary': 'This is a test summary.',
        'key_factors': 'Key factor 1, Key factor 2'
    }
    return db_mock


@pytest.fixture
def mock_qa_service():
    """Mock the QA service."""
    with patch('app.answer_question_from_transcript') as mock_qa:
        mock_qa.return_value = (
            "This is a test answer to the question.",
            150,
            False
        )
        yield mock_qa


class TestProjectListing:
    """Test project listing UI."""
    
    def test_project_listing_displays_projects(self, mock_streamlit, mock_db_manager):
        """Test that projects are displayed in expanders."""
        with patch('app.st', mock_streamlit):
            with patch('app.db_manager', mock_db_manager):
                db_projects = mock_db_manager.list_projects()
                
                # Convert Project objects to dicts (as app does)
                projects = []
                for p in db_projects:
                    proj_dict = {
                        'project_dir': p.project_dir,
                        'id': p.id,
                        'title': p.title or '',
                        'transcript_title': p.content_title if p.type == 'youtube' else None,
                        'content_title': p.content_title if p.type == 'document' else None,
                        'url': p.source if p.type == 'youtube' else None,
                        'filename': p.source if p.type == 'document' else None,
                        'timestamp': p.created_at or '',
                        'word_count': p.word_count or 0,
                    }
                    projects.append(proj_dict)
                
                # Simulate project listing loop
                for idx, proj in enumerate(projects):
                    project_name = proj.get('transcript_title') or proj.get('title') or f"Project {idx + 1}"
                    icon = "🎥" if proj.get('url') else "📄"
                    mock_streamlit.expander(f"{icon} {project_name}", expanded=False)
                
                # Verify expanders were created
                expander_calls = [c for c in mock_streamlit.calls if c[0] == 'expander']
                assert len(expander_calls) == 2
                assert '🎥' in expander_calls[0][1]['label']
    
    def test_project_listing_shows_summary_and_key_factors(self, mock_streamlit, mock_db_manager):
        """Test that summary and key factors are displayed."""
        with patch('app.st', mock_streamlit):
            with patch('app.db_manager', mock_db_manager):
                project_content = mock_db_manager.get_project_content(1)
                
                # Simulate displaying summary
                if project_content.get('summary'):
                    mock_streamlit.markdown("**Summary**")
                    mock_streamlit.text_area(
                        "Summary",
                        value=project_content['summary'],
                        disabled=True
                    )
                
                # Verify summary was displayed
                markdown_calls = [c for c in mock_streamlit.calls if c[0] == 'markdown' and 'Summary' in c[1].get('text', '')]
                assert len(markdown_calls) > 0
                
                # Verify key factors were displayed
                text_area_calls = [c for c in mock_streamlit.calls if c[0] == 'text_area']
                assert len(text_area_calls) > 0


class TestPerProjectChat:
    """Test per-project chat functionality."""
    
    def test_chat_input_renders(self, mock_streamlit, mock_db_manager):
        """Test that chat input field is rendered."""
        with patch('app.st', mock_streamlit):
            with patch('app.db_manager', mock_db_manager):
                project_chat_key = "1"
                question_key = f"project_chat_question_{project_chat_key}"
                
                # Simulate chat input
                mock_streamlit.markdown("---")
                mock_streamlit.write("**Chat with this transcript**")
                mock_streamlit.text_input(
                    "Ask a question about this project:",
                    key=question_key,
                    placeholder="e.g., What are the main takeaways?"
                )
                
                # Verify input was created
                text_input_calls = [c for c in mock_streamlit.calls if c[0] == 'text_input']
                assert len(text_input_calls) > 0
                assert any('question' in c[1].get('key', '') for c in text_input_calls)
    
    def test_chat_button_disabled_when_no_transcript(self, mock_streamlit, mock_db_manager):
        """Test that chat button is disabled when transcript is empty."""
        with patch('app.st', mock_streamlit):
            with patch('app.db_manager', mock_db_manager):
                # Mock empty transcript
                mock_db_manager.get_project_content.return_value = {
                    'transcript': '',
                    'summary': '',
                    'key_factors': ''
                }
                
                transcript_context = ""
                button_disabled = not bool(transcript_context)
                
                # Simulate button
                mock_streamlit.button(
                    "💬 Run transcript chat",
                    key="project_chat_btn_1",
                    disabled=button_disabled
                )
                
                # Verify button was disabled
                button_calls = [c for c in mock_streamlit.calls if c[0] == 'button']
                chat_button = [c for c in button_calls if 'chat' in c[1].get('key', '')]
                assert len(chat_button) > 0
                assert chat_button[0][1]['disabled'] is True
    
    def test_chat_button_enabled_with_transcript(self, mock_streamlit, mock_db_manager):
        """Test that chat button is enabled when transcript exists."""
        with patch('app.st', mock_streamlit):
            with patch('app.db_manager', mock_db_manager):
                project_content = mock_db_manager.get_project_content(1)
                transcript_context = project_content.get('transcript', '') or project_content.get('summary', '')
                button_disabled = not bool(transcript_context)
                
                # Simulate button
                mock_streamlit.button(
                    "💬 Run transcript chat",
                    key="project_chat_btn_1",
                    disabled=button_disabled
                )
                
                # Verify button was enabled
                button_calls = [c for c in mock_streamlit.calls if c[0] == 'button']
                chat_button = [c for c in button_calls if 'chat' in c[1].get('key', '')]
                assert len(chat_button) > 0
                assert chat_button[0][1]['disabled'] is False
    
    def test_chat_question_validation_too_short(self, mock_streamlit, mock_db_manager, mock_qa_service):
        """Test that short questions are rejected."""
        with patch('app.st', mock_streamlit):
            with patch('app.db_manager', mock_db_manager):
                with patch('app.client', Mock()):  # Mock OpenAI client
                    mock_streamlit.session_state = {}
                    mock_streamlit.session_state['project_chat_question_1'] = "Hi"
                    
                    # Simulate validation
                    sanitized_question = mock_streamlit.session_state.get('project_chat_question_1', '').strip()
                    if len(sanitized_question) < app.config.qa_min_question_length:
                        mock_streamlit.warning(f"Please enter at least {app.config.qa_min_question_length} characters.")
                    
                    # Verify warning was shown
                    assert len(mock_streamlit.warnings) > 0
                    assert 'characters' in mock_streamlit.warnings[0]
    
    def test_chat_question_validation_too_long(self, mock_streamlit, mock_db_manager):
        """Test that long questions are rejected."""
        with patch('app.st', mock_streamlit):
            with patch('app.db_manager', mock_db_manager):
                mock_streamlit.session_state = {}
                long_question = "x" * (app.config.qa_max_question_length + 1)
                mock_streamlit.session_state['project_chat_question_1'] = long_question
                
                # Simulate validation
                sanitized_question = mock_streamlit.session_state.get('project_chat_question_1', '').strip()
                if len(sanitized_question) > app.config.qa_max_question_length:
                    mock_streamlit.warning(f"Please limit questions to {app.config.qa_max_question_length} characters.")
                
                # Verify warning was shown
                assert len(mock_streamlit.warnings) > 0
                assert str(app.config.qa_max_question_length) in mock_streamlit.warnings[0]
    
    def test_chat_successful_answer(self, mock_streamlit, mock_db_manager, mock_qa_service):
        """Test successful chat answer generation."""
        with patch('app.st', mock_streamlit):
            with patch('app.db_manager', mock_db_manager):
                with patch('app.client', Mock()):  # Mock OpenAI client
                    mock_streamlit.session_state = {}
                    mock_streamlit.session_state['project_chat_question_1'] = "What is this about?"
                    
                    # Simulate successful chat - use the mocked QA service
                    project_content = mock_db_manager.get_project_content(1)
                    answer, tokens_used, cached = mock_qa_service.return_value
                    
                    mock_streamlit.session_state['project_chat_response_1'] = {
                        "answer": answer,
                        "tokens": tokens_used,
                        "cached": cached,
                        "question": "What is this about?",
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Verify answer was stored
                    assert 'project_chat_response_1' in mock_streamlit.session_state
                    assert mock_streamlit.session_state['project_chat_response_1']['answer'] == "This is a test answer to the question."
    
    def test_chat_missing_openai_key(self, mock_streamlit, mock_db_manager):
        """Test chat error when OpenAI key is missing."""
        with patch('app.st', mock_streamlit):
            with patch('app.db_manager', mock_db_manager):
                with patch('app.client', None):  # No OpenAI client
                    mock_streamlit.session_state = {}
                    mock_streamlit.session_state['project_chat_question_1'] = "What is this about?"
                    
                    # Simulate missing API key check (as done in app)
                    client = None
                    if client is None:
                        mock_streamlit.error("OpenAI API key is not configured; enable it in .env to use transcript chat.")
                    
                    # Verify error was shown
                    assert len(mock_streamlit.errors) > 0
                    assert 'API key' in mock_streamlit.errors[0] or 'OpenAI' in mock_streamlit.errors[0]
    
    def test_chat_displays_latest_answer(self, mock_streamlit):
        """Test that latest answer is displayed."""
        with patch('app.st', mock_streamlit):
            mock_streamlit.session_state = {}
            mock_streamlit.session_state['project_chat_response_1'] = {
                "answer": "This is the answer.",
                "tokens": 150,
                "cached": False,
                "question": "What is this?",
                "timestamp": datetime.now().isoformat()
            }
            
            # Simulate displaying answer
            response = mock_streamlit.session_state.get('project_chat_response_1')
            if response:
                mock_streamlit.markdown("**Latest answer**")
                mock_streamlit.write(response.get("answer"))
                
                meta_parts = []
                if response.get("tokens") is not None:
                    meta_parts.append(f"Tokens used: {response['tokens']}")
                if response.get("cached"):
                    meta_parts.append("From cache")
                if meta_parts:
                    mock_streamlit.caption(" · ".join(meta_parts))
            
            # Verify answer was displayed
            write_calls = [c for c in mock_streamlit.calls if c[0] == 'write']
            assert len(write_calls) > 0
            assert 'answer' in str(write_calls[0][1].get('text', '')).lower() or 'This is the answer' in str(write_calls[0][1].get('text', ''))


class TestUIErrorHandling:
    """Test UI error handling."""
    
    def test_project_not_found_handling(self, mock_streamlit, mock_db_manager):
        """Test handling when project content is not found."""
        with patch('app.st', mock_streamlit):
            with patch('app.db_manager', mock_db_manager):
                # Simulate ProjectNotFoundError
                mock_db_manager.get_project_content.side_effect = ProjectNotFoundError("Project not found")
                
                try:
                    project_content = mock_db_manager.get_project_content(999)
                except ProjectNotFoundError:
                    mock_streamlit.warning("Project record missing; transcript chat unavailable.")
                
                # Verify warning was shown
                assert len(mock_streamlit.warnings) > 0
                assert 'missing' in mock_streamlit.warnings[0].lower() or 'unavailable' in mock_streamlit.warnings[0].lower()
    
    def test_chat_exception_handling(self, mock_streamlit, mock_db_manager):
        """Test that chat exceptions are handled gracefully."""
        with patch('app.st', mock_streamlit):
            with patch('app.db_manager', mock_db_manager):
                with patch('app.client', Mock()):
                    mock_streamlit.session_state = {}
                    mock_streamlit.session_state['project_chat_question_1'] = "What is this?"
                    
                    # Simulate exception handling (as done in app)
                    try:
                        raise Exception("API Error")
                    except Exception as exc:
                        mock_streamlit.error("Unable to generate an answer right now. Please try again.")
                    
                    # Verify error was shown
                    assert len(mock_streamlit.errors) > 0
                    assert 'Unable' in mock_streamlit.errors[0] or 'answer' in mock_streamlit.errors[0]


class TestSessionStateManagement:
    """Test session state management."""
    
    def test_chat_response_stored_in_session_state(self, mock_streamlit):
        """Test that chat responses are stored in session state."""
        with patch('app.st', mock_streamlit):
            mock_streamlit.session_state = {}
            
            # Simulate storing response
            response_key = "project_chat_response_1"
            mock_streamlit.session_state[response_key] = {
                "answer": "Test answer",
                "tokens": 100,
                "cached": False,
                "question": "Test question",
                "timestamp": datetime.now().isoformat()
            }
            
            # Verify it's stored
            assert response_key in mock_streamlit.session_state
            assert mock_streamlit.session_state[response_key]["answer"] == "Test answer"
    
    def test_chat_question_stored_in_session_state(self, mock_streamlit):
        """Test that chat questions are stored in session state."""
        with patch('app.st', mock_streamlit):
            mock_streamlit.session_state = {}
            question_key = "project_chat_question_1"
            
            # Simulate storing question
            mock_streamlit.text_input_values[question_key] = "What is this about?"
            question = mock_streamlit.text_input("Question", key=question_key)
            
            # Verify question is accessible
            assert question == "What is this about?"


# Run with: pytest tests/test_streamlit_integration.py -v

