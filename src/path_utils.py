"""Path resolution and file utilities for RAPM experiment.

This module provides intelligent path resolution with support for:
- PyInstaller frozen builds
- Empty stimuli directory fallback
- Image size caching for performance
"""
from __future__ import annotations

import os
import sys

from config_loader import BASE_DIR


def is_stimuli_dir_empty(dirpath: str) -> bool:
    """Check if stimuli directory is empty or contains only .gitignore.

    Args:
        dirpath: Path to the stimuli directory

    Returns:
        True if directory is empty or only contains .gitignore, False otherwise
    """
    try:
        if not os.path.isdir(dirpath):
            return True
        entries = os.listdir(dirpath)
        # Empty or only .gitignore means we should look elsewhere
        return len(entries) == 0 or (len(entries) == 1 and entries[0] == '.gitignore')
    except Exception:
        return True


def resolve_path(p: str) -> str:
    """Resolve a possibly relative path with intelligent stimuli fallback.

    Priority:
    1. If absolute path exists, use it
    2. Try BASE_DIR / path (bundled resources or dev mode)
       - For stimuli paths: check if directory is empty/only has .gitignore
       - If empty, fallback to exe directory (for frozen builds)
    3. Try executable directory / path (fallback for empty bundled stimuli)

    This allows GitHub Actions to build with empty stimuli/ that users populate later.

    Args:
        p: Path to resolve (absolute or relative)

    Returns:
        Resolved absolute path
    """
    if os.path.isabs(p):
        if os.path.exists(p):
            return p

    # Try bundled/dev resource path first
    candidate = os.path.join(BASE_DIR, p)

    # Special handling for stimuli directory in frozen builds
    if getattr(sys, 'frozen', False) and p.startswith('stimuli'):
        # Check if bundled stimuli is empty
        stimuli_base = os.path.join(BASE_DIR, 'stimuli')
        if is_stimuli_dir_empty(stimuli_base):
            # Bundled stimuli is empty, try exe directory
            try:
                exe_dir = os.path.dirname(sys.executable)
                fallback = os.path.join(exe_dir, p)
                if os.path.exists(fallback):
                    return fallback
            except Exception:
                pass

    # For non-stimuli paths or non-frozen, use normal candidate
    if os.path.exists(candidate):
        return candidate

    # Last resort fallback to exe directory (for any missing files in frozen mode)
    try:
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            fallback = os.path.join(exe_dir, p)
            if os.path.exists(fallback):
                return fallback
    except Exception:
        pass

    # Return first candidate even if not exists (for error messages)
    return candidate


def file_exists_nonempty(path: str) -> bool:
    """Check if a file exists and is not empty.

    Args:
        path: Path to check (will be resolved via resolve_path)

    Returns:
        True if file exists and has size > 0, False otherwise
    """
    try:
        p = resolve_path(path)
        return os.path.isfile(p) and os.path.getsize(p) > 0
    except Exception:
        return False


def load_answers(answer_file: str) -> list[int]:
    """Load answer key from a text file (one integer per line).

    Args:
        answer_file: Path to the answer file

    Returns:
        List of integer answers
    """
    path = resolve_path(answer_file)
    answers: list[int] = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                answers.append(int(s))
            except ValueError:
                continue
    return answers


# Cache for image sizes to avoid re-opening files each frame
_IMG_SIZE_CACHE: dict[str, tuple[int, int]] = {}


def get_image_pixel_size(path: str) -> tuple[int, int] | None:
    """Get pixel dimensions of an image file with caching.

    Args:
        path: Path to the image file

    Returns:
        Tuple of (width, height) in pixels, or None if PIL not available or error
    """
    try:
        from PIL import Image as PILImage  # lazy import
    except Exception:
        return None
    abs_path = resolve_path(path)
    if abs_path in _IMG_SIZE_CACHE:
        return _IMG_SIZE_CACHE[abs_path]
    try:
        with PILImage.open(abs_path) as im:
            size = im.size  # (width, height) in pixels
            _IMG_SIZE_CACHE[abs_path] = size
            return size
    except Exception:
        return None


def fitted_size_keep_aspect(path: str, max_w: float, max_h: float) -> tuple[float, float]:
    """Compute display size (norm units) that fits within max box while preserving aspect ratio.

    Args:
        path: Path to the image file
        max_w: Maximum width in norm units
        max_h: Maximum height in norm units

    Returns:
        Tuple of (width, height) in norm units that fits within max box
    """
    px = get_image_pixel_size(path)
    if not px:
        return max_w, max_h
    pw, ph = px
    if pw <= 0 or ph <= 0:
        return max_w, max_h
    img_ratio = pw / ph
    box_ratio = max_w / max_h if max_h > 0 else img_ratio
    if img_ratio >= box_ratio:
        # width-limited
        w = max_w
        h = w / img_ratio
    else:
        # height-limited
        h = max_h
        w = h * img_ratio
    return w, h
