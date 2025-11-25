"""Test configuration for root-level tests."""
import sys
from pathlib import Path


def _ensure_repo_on_path():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


_ensure_repo_on_path()
