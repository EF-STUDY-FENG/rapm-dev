from __future__ import annotations
"""Utility helpers for RAPM experiment."""
from typing import List
from rapm_types import Item

def build_items_from_pattern(
    pattern: str,
    count: int,
    answers: List[int],
    start_index: int,
    section_prefix: str,
) -> List[Item]:
    """Build item list from file pattern template.

    Generates item dictionaries by expanding a pattern template with indices.
    Example pattern: 'stimuli/images/RAPM_t{XX}-{Y}.jpg'
    - {XX}: zero-padded item number (01, 02, ...)
    - {Y}: 0 for question, 1-8 for options

    Args:
        pattern: Path template with {XX} and {Y} placeholders
        count: Number of items to generate
        answers: List of correct answer indices
        start_index: Offset for answer lookup
        section_prefix: Prefix for item IDs ('P' or 'F')

    Returns:
        List of item dicts with id, question_image, options, correct
    """
    items: List[Item] = []
    for i in range(1, count + 1):
        XX = f"{i:02d}"
        q_path = pattern.replace('{XX}', XX).replace('{Y}', '0')
        option_paths = [
            pattern.replace('{XX}', XX).replace('{Y}', str(opt))
            for opt in range(1, 9)
        ]
        correct = None
        idx = start_index + (i - 1)
        if 0 <= idx < len(answers):
            correct = answers[idx]
        items.append({
            'id': f"{section_prefix}{XX}",
            'question_image': q_path,
            'options': option_paths,
            'correct': correct
        })
    return items
