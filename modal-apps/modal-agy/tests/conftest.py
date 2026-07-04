import importlib.util
import sys
from pathlib import Path

# Load as a uniquely-named module (not plain "modal_app") so this doesn't
# collide with modal-sandbox's own modal_app.py when the whole monorepo's
# tests are collected in a single pytest run.
_app_path = Path(__file__).resolve().parent.parent / "modal_app.py"
_spec = importlib.util.spec_from_file_location("modal_agy_app", _app_path)
modal_agy_app = importlib.util.module_from_spec(_spec)
sys.modules["modal_agy_app"] = modal_agy_app
_spec.loader.exec_module(modal_agy_app)
