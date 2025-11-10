from __future__ import annotations

"""Raven Advanced Progressive Matrices Task - Core Module

This module implements the complete RAPM experiment flow with:
- Practice and formal test sections
- Configurable timing and layout
- Navigation and progress tracking
- Results persistence

Architecture:
    - build_items_from_pattern(): Module-level helper for item generation
    - RavenTask: Main experiment class with organized method groups
"""

from typing import Any, Optional, Sequence
import json
import os
import csv
from datetime import datetime
from psychopy import visual, event, core
from ui.renderer import Renderer
from ui.navigator import Navigator
from section_runner import SectionRunner
from path_utils import (
    resolve_path,
    file_exists_nonempty,
    load_answers,
    fitted_size_keep_aspect,
)

from results_writer import ResultsWriter


# =============================================================================
# MODULE-LEVEL HELPERS
# =============================================================================

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
        """Check if timing has been initialized."""
        return self.start_time is not None and self.deadline is not None

def build_items_from_pattern(
    pattern: str,
    count: int,
    answers: list[int],
    start_index: int,
    section_prefix: str,
) -> list[dict]:
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
    items: list[dict] = []
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


# =============================================================================
# MAIN TASK CLASS
# =============================================================================

class RavenTask:
    """Raven's Advanced Progressive Matrices experiment controller.

    Manages the complete experiment lifecycle:
    1. Window creation (debug: 1280x800, normal: fullscreen)
    2. Practice section with instruction
    3. Formal section with instruction
    4. Results persistence (CSV + JSON metadata)
    5. Window cleanup

    Public API:
    - run(): Execute the full task lifecycle (create window → run sections → save → cleanup)

    Key features:
    - Config-driven instructions and timing
    - Debug mode for rapid testing
    - Navigation with pagination
    - Auto-advance to next unanswered item
    - Submit button in formal section

    Notes:
    - All non-public methods are internal and prefixed with an underscore (_).
    """

    # -------------------------------------------------------------------------
    # LIFECYCLE & CORE (construction and section orchestration)
    # -------------------------------------------------------------------------

    def __init__(
        self,
        sequence: dict[str, Any],
        layout: dict[str, Any],
        participant_info: Optional[dict[str, Any]] = None,
    ) -> None:
        """Initialize task with configuration and participant info.

        Args:
            sequence: Practice/formal config from configs/sequence.json
            layout: UI layout parameters from configs/layout.json
            participant_info: Participant metadata (id, age, gender, etc.)
        """
        # Window managed by run() method
        self.win = None

        # Section configs (directly assigned, no intermediate dictionary)
        self.practice = sequence['practice']
        self.formal = sequence['formal']

        # Participant and answer tracking
        self.participant_info = participant_info or {}
        self.practice_answers = {}
        self.formal_answers = {}

        # Layout parameters (direct reference, guaranteed complete by config_loader)
        self.layout = layout

        # Debug mode: layout flag OR participant_id == '0'
        pid = str(self.participant_info.get('participant_id', '')).strip()
        self.debug_mode = self.layout.get('debug_mode', False) or (pid == '0')

        # Timing management (initialized in run_section)
        self.practice_timing = SectionTiming()
        self.formal_timing = SectionTiming()

        # Navigation constants
        self.max_visible_nav = 12

        # Build item lists from patterns if answers file provided
        answers_file = sequence.get('answers_file') if isinstance(sequence, dict) else None
        if answers_file:
            try:
                answers = load_answers(answers_file)
            except Exception:
                answers = []

            p_count = int(self.practice.get('count', 0))
            p_pattern = self.practice.get('pattern')
            if p_count and p_pattern:
                self.practice['items'] = build_items_from_pattern(
                    p_pattern, p_count, answers, 0, 'P'
                )

            f_count = int(self.formal.get('count', 0))
            f_pattern = self.formal.get('pattern')
            if f_count and f_pattern:
                self.formal['items'] = build_items_from_pattern(
                    f_pattern, f_count, answers, p_count, 'F'
                )

    # -------------------------------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------------------------------

    def run(self) -> None:
        """Main entry point: create window → run sections → save → cleanup."""
        # Create window based on debug mode
        if self.debug_mode:
            self.win = visual.Window(
                size=(1280, 800),
                color='black',
                units='norm'
            )
        else:
            self.win = visual.Window(
                fullscr=True,
                color='black',
                units='norm'
            )

        try:
            # Run practice (instruction shown inside _run_section)
            # Initialize UI helpers tied to the created window
            self.renderer = Renderer(self.win, self.layout)
            self.navigator = Navigator(self.win, self.layout, max_visible_nav=self.max_visible_nav)
            self.section_runner = SectionRunner(self.win, self.renderer, self.navigator, self.layout, self.debug_mode)
            self.section_runner.run_section('practice', self.practice, self.practice_answers, self.practice_timing)

            # Run formal (instruction shown inside _run_section)
            self.section_runner.run_section('formal', self.formal, self.formal_answers, self.formal_timing)

            # Save and show completion message
            self._save_and_exit()
        finally:
            # Always cleanup window
            try:
                if self.win is not None:
                    self.win.close()
            except Exception:
                pass


    # -------------------------------------------------------------------------
    # DATA PERSISTENCE
    # -------------------------------------------------------------------------

    def _save_and_exit(self) -> None:
        """Delegate persistence to ResultsWriter then show completion message."""
        # Lazy instantiate writer (can be injected later if needed)
        if not hasattr(self, 'results_writer'):
            self.results_writer = ResultsWriter()
        self.results_writer.save(
            self.participant_info,
            self.practice,
            self.formal,
            self.practice_answers,
            self.formal_answers,
            self.practice_timing,
            self.formal_timing,
        )
        # Completion splash
        lines = ['作答完成！', '感谢您的作答！']
        colors = ['green', 'white']
        for _ in range(300):  # ~5 seconds
            self.renderer.draw_multiline(
                lines,
                center_y=0.05,
                line_height=0.065,
                spacing=1.5,
                colors=colors,
                bold_idx={0}
            )
            self.win.flip()
