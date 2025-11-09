"""Configuration loader for RAPM task.

Separately loads sequence (configs/sequence.json) and layout (configs/layout.json),
with external override precedence for layout when running as a packaged exe.
"""
from __future__ import annotations

import json
import os
import sys


def _get_base_dir() -> str:
    """Return base directory for read-only resources (configs/stimuli)."""
    try:
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass and os.path.isdir(meipass):
            return meipass
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
    except Exception:
        pass
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


BASE_DIR = _get_base_dir()
SEQUENCE_DEFAULT_PATH = os.path.join(BASE_DIR, 'configs', 'sequence.json')
LAYOUT_DEFAULT_PATH = os.path.join(BASE_DIR, 'configs', 'layout.json')


def _get_exe_override_path(rel_path: str) -> str | None:
    """When running as a frozen exe, return the override path next to the exe."""
    try:
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            return os.path.join(exe_dir, rel_path)
    except Exception:
        pass
    return None


def load_sequence(sequence_path: str | None = None) -> dict:
    """Load sequence.json configuration.

    Args:
        sequence_path: Optional absolute path; when None uses default under BASE_DIR.
    """
    path = sequence_path or SEQUENCE_DEFAULT_PATH
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_layout() -> dict:
    """Load layout.json with external-override precedence and parameter merging.

    Search order:
    1) Load defaults from <BASE_DIR>/configs/layout.json (must exist)
    2) If running as frozen exe, load overrides from <exe_dir>/configs/layout.json
    3) Merge: override parameters take precedence, missing ones use defaults
    """
    # Step 1: Load the default layout (required baseline)
    if not os.path.exists(LAYOUT_DEFAULT_PATH):
        raise RuntimeError(
            f"未找到默认布局配置文件: {LAYOUT_DEFAULT_PATH}\n"
            "这是必需的基础配置文件，请确保项目中包含此文件。"
        )

    with open(LAYOUT_DEFAULT_PATH, 'r', encoding='utf-8') as f:
        layout = json.load(f)

    # Step 2: Check for external override (only when frozen)
    override_path = _get_exe_override_path(os.path.join('configs', 'layout.json'))
    if override_path and os.path.exists(override_path):
        try:
            with open(override_path, 'r', encoding='utf-8') as f:
                overrides = json.load(f)
            # Step 3: Merge overrides into defaults (overrides take precedence)
            layout.update(overrides)
        except Exception as e:
            # If override file is malformed, warn but continue with defaults
            import warnings
            warnings.warn(
                f"外部布局配置文件格式错误，将使用默认配置: {override_path}\n错误: {e}"
            )

    return layout
