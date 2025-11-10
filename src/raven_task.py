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
from config_loader import get_output_dir
from path_utils import (
    resolve_path,
    file_exists_nonempty,
    load_answers,
    fitted_size_keep_aspect,
)

# Output directory for results
DATA_DIR = get_output_dir()


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
            self._run_section('practice')

            # Run formal (instruction shown inside _run_section)
            self._run_section('formal')

            # Save and show completion message
            self._save_and_exit()
        finally:
            # Always cleanup window
            try:
                if self.win is not None:
                    self.win.close()
            except Exception:
                pass

    def _run_section(self, section: str) -> None:
        """Execute a complete test section with instruction → test loop → timeout.

        Handles:
        - Instruction display with countdown button
        - Deadline initialization
        - Main event loop (draw → input → navigation)
        - Submit button (formal only, when all answered)
        - Auto-advance to next unanswered item

        Args:
            section: 'practice' or 'formal'
        """
        # Resolve configuration and timing object for this section
        timing = self.practice_timing if section == 'practice' else self.formal_timing
        conf = self.practice if section == 'practice' else self.formal
        items = conf['items']
        n_items = len(items)
        if n_items == 0:
            return

        # Show instruction with button
        instruction_text = conf.get('instruction', '')
        button_text = conf.get('button_text', '继续')
        if instruction_text:
            self.renderer.show_instruction(instruction_text, button_text=button_text, debug_mode=self.debug_mode)

        # Initialize timing
        start_time = core.getTime()
        if self.debug_mode:
            duration = 10 if section == 'practice' else 25  # Debug: 10s/25s
        else:
            duration = conf['time_limit_minutes'] * 60
        timing.initialize(start_time, duration)

        # Initialize state
        answers = self.practice_answers if section == 'practice' else self.formal_answers
        # Timer thresholds and submit flag
        if section == 'practice':
            show_threshold = None
            red_threshold = None
            show_submit = False
        else:
            if self.debug_mode:
                show_threshold = self.layout['debug_timer_show_threshold']
                red_threshold = self.layout['debug_timer_red_threshold']
            else:
                show_threshold = self.layout['formal_timer_show_threshold']
                red_threshold = self.layout['timer_red_threshold']
            show_submit = True
        current_index = 0
        nav_offset = 0

        # Main event loop
        while core.getTime() < timing.deadline:
            item = items[current_index]

            # Draw navigation bar (buttons + arrows)
            nav_items, l_rect, l_txt, r_rect, r_txt = self.navigator.build_navigation(
                items, answers, current_index, nav_offset
            )
            for _, rect, label in nav_items:
                rect.draw()
                label.draw()
            if l_rect:
                l_rect.draw()
                l_txt.draw()
            if r_rect:
                r_rect.draw()
                r_txt.draw()

            # Draw header (timer + progress)
            self.renderer.draw_header(
                deadline=timing.deadline,
                show_threshold=show_threshold,
                red_threshold=red_threshold,
                answered_count=len(answers),
                total_count=n_items,
                show_timer=True,
                show_progress=True,
            )

            # Draw question and options
            self.renderer.draw_question(item['id'], item.get('question_image'))
            rects = self.renderer.create_option_rects()
            prev_choice = answers.get(item['id'])
            self.renderer.draw_options(
                item.get('options', []),
                rects,
                selected_index=(prev_choice - 1) if prev_choice else None
            )

            # Draw submit button (formal only, when all answered)
            submit_btn = None
            if show_submit and len(answers) == n_items:
                submit_btn = self.renderer.draw_submit_button()

            self.win.flip()

            # Handle submit button click (formal only)
            if submit_btn:
                mouse_global = event.Mouse(win=self.win)
                if any(mouse_global.getPressed()) and submit_btn.contains(mouse_global):
                    while any(mouse_global.getPressed()):
                        core.wait(0.01)
                    return  # Exit section

            # Handle option click
            choice = self.renderer.detect_click_on_rects(rects)
            if choice is not None:
                answers[item['id']] = choice + 1
                timing.last_times[item['id']] = core.getTime()

                # Check completion
                if len(answers) == n_items:
                    if section == 'practice':
                        break  # Exit practice immediately
                    # Formal: stay in loop to show submit button
                else:
                    # Auto-advance to next unanswered
                    next_index = self.navigator.find_next_unanswered(items, answers, current_index)
                    current_index = next_index
                    nav_offset = self.navigator.center_offset(next_index, n_items)
                continue

            # Handle navigation click
            nav_action, current_index, nav_offset = self.navigator.handle_click(
                nav_items, l_rect, r_rect, items, current_index, nav_offset
            )
            if nav_action == 'jump':
                nav_offset = self.navigator.center_offset(current_index, n_items)
                continue
            if nav_action == 'page':
                continue

            # Timeout check (redundant, but explicit exit)
            if core.getTime() >= timing.deadline:
                break


    # -------------------------------------------------------------------------
    # DATA PERSISTENCE
    # -------------------------------------------------------------------------

    def _save_and_exit(self) -> None:
        """Save results to CSV and JSON, then show completion message.

        Creates two files in DATA_DIR:
        - raven_results_TIMESTAMP.csv: Detailed trial-by-trial data
        - raven_session_TIMESTAMP.json: Session metadata and summary stats
        """
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        os.makedirs(DATA_DIR, exist_ok=True)

        # Save CSV
        out_path = os.path.join(DATA_DIR, f'raven_results_{ts}.csv')
        pid = self.participant_info.get('participant_id', '')
        practice_correct = 0
        formal_correct = 0

        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'participant_id', 'section', 'item_id', 'answer',
                'correct', 'is_correct', 'time'
            ])

            def write_section(section, items, answers, last_times, start_time):
                nonlocal practice_correct, formal_correct
                for item in items:
                    iid = item.get('id')
                    ans = answers.get(iid)
                    correct = item.get('correct')
                    is_correct = (ans == correct) if (ans is not None and correct is not None) else None

                    if is_correct:
                        if section == 'practice':
                            practice_correct += 1
                        else:
                            formal_correct += 1

                    t2 = last_times.get(iid, None)
                    t0 = start_time
                    time_used = ''
                    if t0 is not None and t2 is not None:
                        time_used = f"{t2-t0:.3f}"

                    writer.writerow([
                        pid, section, iid,
                        ans if ans is not None else '',
                        correct if correct is not None else '',
                        '1' if is_correct else ('0' if is_correct is not None else ''),
                        time_used
                    ])

            write_section('practice', self.practice.get('items', []),
                         self.practice_answers, self.practice_timing.last_times,
                         self.practice_timing.start_time)
            write_section('formal', self.formal.get('items', []),
                         self.formal_answers, self.formal_timing.last_times,
                         self.formal_timing.start_time)

        # Save JSON metadata
        meta = {
            'participant': self.participant_info,
            'time_created': datetime.now().isoformat(timespec='seconds'),
            'practice': {
                'set': self.practice.get('set'),
                'time_limit_minutes': self.practice.get('time_limit_minutes'),
                'n_items': len(self.practice.get('items', [])),
                'correct_count': practice_correct
            },
            'formal': {
                'set': self.formal.get('set'),
                'time_limit_minutes': self.formal.get('time_limit_minutes'),
                'n_items': len(self.formal.get('items', [])),
                'correct_count': formal_correct
            },
            'total_correct': practice_correct + formal_correct,
            'total_items': len(self.practice.get('items', [])) + len(self.formal.get('items', []))
        }
        meta_path = os.path.join(DATA_DIR, f'raven_session_{ts}.json')
        try:
            with open(meta_path, 'w', encoding='utf-8') as mf:
                json.dump(meta, mf, ensure_ascii=False, indent=2)
        except Exception:
            pass

        # Show completion message
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
