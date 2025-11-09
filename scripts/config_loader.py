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
    """Load layout.json with external-override precedence.

    Search order:
    1) <exe_dir>/configs/layout.json (when frozen)
    2) <BASE_DIR>/configs/layout.json
    """
    override_path = _get_exe_override_path(os.path.join('configs', 'layout.json'))
    candidates = [p for p in [override_path, LAYOUT_DEFAULT_PATH] if p]
    for p in candidates:
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                return json.load(f)
    raise RuntimeError(
        "未找到布局配置文件 configs/layout.json。请在以下任一路径提供该文件：\n"
        f"- 可执行文件同目录: {override_path}\n"
        f"- 内置/开发路径: {LAYOUT_DEFAULT_PATH}"
    )
