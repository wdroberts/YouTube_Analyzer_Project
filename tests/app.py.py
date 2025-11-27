"""
Test shim that re-exports the root application module.

Some tests (e.g., `tests/test_local_whisper.py`) expect a module named `tests/app.py.py`,
so this lightweight proxy loads the real `app.py.py` from the repository root and exposes
its symbols while keeping pytest happy.
"""
from importlib import util
import sys
from pathlib import Path

ROOT_APP_PATH = Path(__file__).resolve().parent.parent / "app.py.py"
_CORE_MODULE_NAME = "app_main"


def _load_root_module():
    """Load the root app module once and reuse it."""
    if _CORE_MODULE_NAME in sys.modules:
        return sys.modules[_CORE_MODULE_NAME]

    spec = util.spec_from_file_location(_CORE_MODULE_NAME, ROOT_APP_PATH)
    module = util.module_from_spec(spec)
    sys.modules[_CORE_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


_core_app = _load_root_module()

# Re-export the core module symbols so callers can use `import tests.app as app`.
globals().update(
    {
        name: getattr(_core_app, name)
        for name in dir(_core_app)
        if not name.startswith("__")
    }
)

__all__ = [name for name in dir(_core_app) if not name.startswith("__")]

