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
from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from psychopy import visual

from models import SectionTiming
from path_utils import load_answers
from rapm_types import LayoutConfig, ParticipantInfo, SectionConfig
from results_writer import ResultsWriter
from section_runner import SectionRunner
from ui.navigator import Navigator
from ui.renderer import Renderer
from utils import build_items_from_pattern

# =============================================================================
# MODULE-LEVEL HELPERS
# =============================================================================

@contextmanager
def create_window(debug_mode: bool):
    """Context manager to create and cleanup a PsychoPy window.

    Args:
        debug_mode: When True, creates a windowed mode for faster debugging.
                    When False, creates a fullscreen window for experiments.

    Yields:
        visual.Window: The created PsychoPy window.
    """
    if debug_mode:
        win = visual.Window(
            size=(1280, 800),
            color='black',
            units='norm',
        )
    else:
        win = visual.Window(
            fullscr=True,
            color='black',
            units='norm',
        )
    try:
        yield win
    finally:
        try:
            win.close()
        except Exception:
            pass


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
    - save_results(): Save experiment data (can be called independently)

    Key features:
    - Config-driven instructions and timing
    - Debug mode for rapid testing
    - Navigation with pagination
    - Auto-advance to next unanswered item
    - Submit button in formal section

    Notes:
    - Window and UI components are local to run() scope
    """

    # =========================================================================
    # CONSTRUCTION
    # =========================================================================

    def __init__(
        self,
        sequence: dict[str, Any],
        layout: LayoutConfig,
    participant_info: ParticipantInfo | None = None,
    ) -> None:
        """Initialize task with configuration and participant info.

        Args:
            sequence: Practice/formal config from configs/sequence.json
            layout: UI layout parameters from configs/layout.json
            participant_info: Participant metadata (id, age, gender, etc.)
        """
        # Section configs (directly assigned, no intermediate dictionary)
        from typing import cast
        self.practice = cast(SectionConfig, sequence['practice'])
        self.formal = cast(SectionConfig, sequence['formal'])

        # Participant and answer tracking
        self.participant_info = cast(ParticipantInfo, participant_info or {})
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

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def run(self) -> None:
        """Main entry point: create window → run sections → save → cleanup.

        Flow:
        1. Create window (context manager ensures cleanup)
        2. Initialize UI components (renderer, navigator, section_runner)
        3. Run practice section
        4. Run formal section
        5. Save results
        6. Show completion message
        """
        # Window is local to the run lifecycle
        with create_window(self.debug_mode) as win:
            # Initialize UI helpers tied to the created window
            renderer = Renderer(win, self.layout)
            navigator = Navigator(self.layout, max_visible_nav=self.max_visible_nav)
            section_runner = SectionRunner(
                win,
                renderer,
                navigator,
                self.layout,
                self.debug_mode,
            )
            # Practice (instruction shown inside SectionRunner)
            section_runner.run_section(
                'practice',
                self.practice,
                self.practice_answers,
                self.practice_timing,
            )

            # Formal (instruction shown inside SectionRunner)
            section_runner.run_section(
                'formal',
                self.formal,
                self.formal_answers,
                self.formal_timing,
            )

            # Save results
            self.save_results()

            # Show completion message
            renderer.show_completion()


    # =========================================================================
    # DATA PERSISTENCE
    # =========================================================================

    def save_results(self) -> None:
        """Save experiment results to CSV and JSON files.

        Delegates to ResultsWriter for actual file I/O.
        Can be called independently if needed (e.g., for testing or manual save).
        """
        ResultsWriter().save(
            self.participant_info,
            self.practice,
            self.formal,
            self.practice_answers,
            self.formal_answers,
            self.practice_timing,
            self.formal_timing,
        )
