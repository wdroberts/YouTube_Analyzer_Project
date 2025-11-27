"""
Backward compatibility shim that exposes a module named `app`.

The main application lives in `app.py.py`, but various tests (and commands) import
`app`. This shim loads `app.py.py` under the name `app` so that imports and patches
targeting `app` continue to work.
"""
from importlib import util
from pathlib import Path
import sys

_ROOT_APP_PATH = Path(__file__).resolve().with_name("app.py.py")
_SPEC = util.spec_from_file_location("app", _ROOT_APP_PATH)
_MODULE = util.module_from_spec(_SPEC)
sys.modules["app"] = _MODULE
_SPEC.loader.exec_module(_MODULE)

