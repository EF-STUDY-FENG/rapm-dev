from __future__ import annotations
"""Data models for RAPM experiment."""
from typing import Optional
from psychopy import core

class SectionTiming:
    """Encapsulates timing state for a test section.

    Attributes:
        start_time: Section start timestamp (from core.getTime())
        deadline: Section timeout timestamp
        last_times: Dict mapping item_id → answer timestamp
    """
    def __init__(self):
        self.start_time: Optional[float] = None
        self.deadline: Optional[float] = None
        self.last_times: dict[str, float] = {}

    def initialize(self, start_time: float, duration_seconds: float) -> None:
        """Set start time and calculate deadline.

        Args:
            start_time: Current timestamp from core.getTime()
            duration_seconds: Section duration in seconds
        """
        self.start_time = start_time
        self.deadline = start_time + duration_seconds

    def is_initialized(self) -> bool:
        return self.start_time is not None and self.deadline is not None
