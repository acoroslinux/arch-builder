from pathlib import Path
from typing import Union

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def project_root() -> Path:
    """Return the absolute root directory of the arch-builder project."""
    return PROJECT_ROOT


def resolve_from_project(path: Union[str, Path]) -> Path:
    """Resolve relative paths against the arch-builder project root."""
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / candidate


def resolve_from_base(base_dir: Union[str, Path], path: Union[str, Path]) -> Path:
    """Resolve relative paths against an explicit base directory."""
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(base_dir) / candidate
