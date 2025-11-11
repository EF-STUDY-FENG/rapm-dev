from __future__ import annotations
"""Typed structures for RAPM task configuration and items."""
from typing import TypedDict, List, Optional

class Item(TypedDict):
    id: str
    question_image: str
    options: List[str]
    correct: Optional[int]

class SectionConfig(TypedDict, total=False):
    set: str
    count: int
    pattern: str
    instruction: str
    button_text: str
    time_limit_minutes: int
    items: List[Item]

class ParticipantInfo(TypedDict, total=False):
    participant_id: str
    age: str
    gender: str
    session: str
    notes: str
