"""Configuration loader for RAPM task.

Separately loads sequence (configs/sequence.json) and layout (configs/layout.json),
with external override precedence for layout when running as a packaged exe.
"""
from __future__ import annotations

import json
import os
import sys
from typing import cast


def get_base_dir() -> str:
    """Return base directory for read-only resources (configs/stimuli).

    Note: In PyInstaller onefile, resources are unpacked to a temporary
    extraction directory (sys._MEIPASS). That location is read-only and may be
    deleted after exit, so DO NOT write output files there.
    """
    try:
        # PyInstaller onefile provides a temporary extraction dir
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass and os.path.isdir(meipass):
            return meipass
        # Onedir: use the executable directory so bundled folders like 'configs/' work
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
    except Exception:
        pass
    # Normal dev mode: project root (scripts/..)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def get_output_dir() -> str:
    """Return a persistent, user-writable directory for saving results.

    - For frozen apps (onefile/onedir), use the directory next to the executable.
    - For dev, use the project-level 'data' directory.
    """
    try:
        if getattr(sys, 'frozen', False):
            return os.path.join(os.path.dirname(sys.executable), 'data')
    except Exception:
        pass
    # Dev mode: project root /data
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))


def get_exe_override_path(rel_path: str) -> str | None:
    """When running as a frozen exe, return the override path next to the exe.

    Example: rel_path='configs/layout.json' -> '<exe_dir>/configs/layout.json'
    Returns None if not frozen.
    """
    try:
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            return os.path.join(exe_dir, rel_path)
    except Exception:
        pass
    return None


# Module-level constants
BASE_DIR = get_base_dir()
SEQUENCE_DEFAULT_PATH = os.path.join(BASE_DIR, 'configs', 'sequence.json')
LAYOUT_DEFAULT_PATH = os.path.join(BASE_DIR, 'configs', 'layout.json')


from rapm_types import SequenceConfig, LayoutConfig

def load_sequence() -> SequenceConfig:
    """Load sequence.json configuration.

    Returns:
        SequenceConfig: practice/formal section configs and optional answers_file.
    """
    with open(SEQUENCE_DEFAULT_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # Best‑effort cast (run‑time validation could be added if needed)
    return cast(SequenceConfig, data)


def load_layout() -> LayoutConfig:
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
        layout_raw = json.load(f)
    layout: LayoutConfig = cast(LayoutConfig, layout_raw)

    # Step 2: Check for external override (only when frozen)
    override_path = get_exe_override_path(os.path.join('configs', 'layout.json'))
    if override_path and os.path.exists(override_path):
        try:
            with open(override_path, 'r', encoding='utf-8') as f:
                overrides_raw = json.load(f)
            overrides = cast(LayoutConfig, overrides_raw)
            layout.update(overrides)  # overrides take precedence
        except Exception as e:
            # If override file is malformed, warn but continue with defaults
            import warnings
            warnings.warn(
                f"外部布局配置文件格式错误，将使用默认配置: {override_path}\n错误: {e}"
            )

    return layout
