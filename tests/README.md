# Test Suite for YouTube Analyzer Project

This directory contains all automated tests for the YouTube Analyzer application.

## 📁 Test Structure

```
tests/
├── __init__.py                  # Test package initialization
├── test_utilities.py            # Tests for utility functions
├── test_config.py               # Tests for configuration management
├── test_file_operations.py      # Tests for file I/O operations
└── README.md                    # This file
```

## 🚀 Running Tests

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test File
```bash
pytest tests/test_utilities.py -v
```

### Run Specific Test Class
```bash
pytest tests/test_utilities.py::TestSafeFilename -v
```

### Run Specific Test Function
```bash
pytest tests/test_utilities.py::TestSafeFilename::test_simple_text -v
```

## 📊 Coverage Reports

### Generate HTML Coverage Report
```bash
pytest tests/ --cov=. --cov-report=html
```

Then open `htmlcov/index.html` in your browser.

### Terminal Coverage Report
```bash
pytest tests/ --cov=. --cov-report=term-missing
```

### Coverage with Missing Lines
```bash
pytest tests/ --cov=. --cov-report=term-missing:skip-covered
```

## 🎯 Test Categories

### Unit Tests
Tests for individual functions in isolation:
- `test_utilities.py` - Utility function tests
- `test_config.py` - Configuration tests
- `test_file_operations.py` - File operation tests

### Markers
Use pytest markers to selectively run tests:

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

## 📝 Writing New Tests

### Test File Naming
- Test files must start with `test_`
- Example: `test_new_feature.py`

### Test Class Naming
- Test classes must start with `Test`
- Example: `class TestNewFeature:`

### Test Function Naming
- Test functions must start with `test_`
- Example: `def test_feature_works():`

### Example Test Structure
```python
import pytest

class TestMyFeature:
    """Test suite for my feature."""
    
    def test_basic_functionality(self):
        """Test basic feature functionality."""
        result = my_function("input")
        assert result == "expected_output"
    
    def test_edge_case(self):
        """Test edge case handling."""
        with pytest.raises(ValueError):
            my_function(None)
```

## 🔧 Test Fixtures

### Temporary Directory Fixture
```python
@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    # Cleanup
    if temp_path.exists():
        shutil.rmtree(temp_path)

def test_with_temp_dir(temp_dir):
    file_path = temp_dir / "test.txt"
    # Use temp_dir in test
```

### Mocking Environment Variables
```python
def test_with_env_var(monkeypatch):
    monkeypatch.setenv("MY_VAR", "test_value")
    # Test code that uses MY_VAR
```

## 🐛 Debugging Tests

### Run with Print Statements
```bash
pytest tests/ -v -s
```

### Run with Debugging
```bash
pytest tests/ --pdb
```

### Stop at First Failure
```bash
pytest tests/ -x
```

### Show Local Variables on Failure
```bash
pytest tests/ -l
```

## 📈 Current Test Coverage

Run this command to see current coverage:
```bash
pytest tests/ --cov=. --cov-report=term-missing
```

### Coverage Goals
- **Target:** 80% overall coverage
- **Critical functions:** 100% coverage
- **Utility functions:** 100% coverage (achieved ✅)
- **Configuration:** 100% coverage (achieved ✅)

## 🔄 Continuous Integration

Tests run automatically on GitHub Actions for:
- ✅ Every push to master/main
- ✅ Every pull request
- ✅ Multiple Python versions (3.9, 3.10, 3.11)
- ✅ Multiple OS platforms (Ubuntu, Windows, macOS)

See `.github/workflows/tests.yml` for CI configuration.

## 📚 Testing Best Practices

1. **Test One Thing** - Each test should verify one specific behavior
2. **Clear Names** - Test names should describe what they test
3. **Arrange-Act-Assert** - Organize tests in three sections
4. **Independent Tests** - Tests should not depend on each other
5. **Fast Tests** - Keep tests fast; mock slow operations
6. **Descriptive Assertions** - Use clear assertion messages

## 🛠️ Troubleshooting

### Import Errors
If you get import errors, ensure you're running from the project root:
```bash
cd /path/to/YouTube_Analyzer_Project
pytest tests/
```

### Coverage Not Showing
Make sure pytest-cov is installed:
```bash
pip install pytest-cov
```

### Tests Pass Locally but Fail in CI
Check for:
- Environment-specific paths
- Missing environment variables
- Platform-specific behavior (Windows vs Linux)

## 📞 Need Help?

- Check pytest documentation: https://docs.pytest.org/
- Check coverage documentation: https://coverage.readthedocs.io/
- See main project README for setup instructions

