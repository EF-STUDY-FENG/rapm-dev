"""SectionRunner: orchestrates a single section flow using Renderer and Navigator.

Responsibilities:
- Manages event loop for practice/formal sections
- Coordinates rendering (Renderer) and navigation (Navigator)
- Handles mouse interactions with edge detection (debouncing)
- Tracks timing and auto-advance logic
"""
from __future__ import annotations

from typing import Any

from psychopy import core, event

from rapm_types import SectionConfig

DEBUG_PRACTICE_DURATION = 10
DEBUG_FORMAL_DURATION = 25


class SectionRunner:

    def __init__(
        self,
        win: Any,
        renderer: Any,
        navigator: Any,
        layout: dict,
        debug_mode: bool,
    ) -> None:
        """Initialize section runner.

        Args:
            win: PsychoPy window instance
            renderer: Renderer instance for drawing
            navigator: Navigator instance for navigation bar
            layout: Layout configuration dictionary
            debug_mode: If True, shorter timers for testing
        """
        self.win = win
        self.renderer = renderer
        self.navigator = navigator
        self.layout = layout
        self.debug_mode = debug_mode

    def _get_timer_config(self, section: str) -> tuple[int | None, int | None]:
        """Get timer display thresholds based on section and debug mode.

        Returns:
            (show_threshold, red_threshold) tuple
        """
        if section == 'practice':
            return None, None

        if self.debug_mode:
            return (
                self.layout['debug_timer_show_threshold'],
                self.layout['debug_timer_red_threshold']
            )

        return (
            self.layout['formal_timer_show_threshold'],
            self.layout['timer_red_threshold']
        )

    def run_section(
        self,
        section: str,
        conf: SectionConfig,
        answers: dict[str, int],
        timing,
    ) -> None:
        """Run a single section ('practice' or 'formal').

        Args:
            section: Section name ('practice' or 'formal')
            conf: Section configuration (items, instruction, time_limit_minutes)
            answers: Dictionary to store user answers (mutated in-place)
            timing: SectionTiming instance for tracking time and responses
        """
        items = conf['items']
        n_items = len(items)
        if n_items == 0:
            return

        instruction_text = conf.get('instruction', '')
        button_text = conf.get('button_text', '继续')
        if instruction_text:
            self.renderer.show_instruction(
                instruction_text,
                button_text=button_text,
                debug_mode=self.debug_mode,
            )

        start_time = core.getTime()
        if self.debug_mode:
            duration = DEBUG_PRACTICE_DURATION if section == 'practice' else DEBUG_FORMAL_DURATION
        else:
            duration = conf['time_limit_minutes'] * 60
        timing.initialize(start_time, duration)

        show_threshold, red_threshold = self._get_timer_config(section)
        show_submit = True
        submit_button_text = '完成练习' if section == 'practice' else '提交作答'

        current_index = 0
        nav_offset = 0

        mouse = event.Mouse(win=self.win)
        mouse_was_pressed = False

        while timing.remaining_seconds() > 0:
            item = items[current_index]

            # Draw navigation bar (buttons + arrows)
            nav_items, l_rect, l_txt, r_rect, r_txt = self.navigator.build_navigation(
                self.win, items, answers, current_index, nav_offset
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
                remaining_seconds=timing.remaining_seconds(),
                show_threshold=show_threshold,
                red_threshold=red_threshold,
                answered_count=len(answers),
                total_count=n_items,
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

            # Draw submit button (when all answered)
            submit_btn = None
            if show_submit and len(answers) == n_items:
                submit_btn = self.renderer.draw_submit_button(mouse, label=submit_button_text)

            self.win.flip()

            # Detect mouse state: only trigger on press→release transition (debounce)
            mouse_is_pressed = any(mouse.getPressed())
            mouse_just_released = mouse_was_pressed and not mouse_is_pressed
            mouse_was_pressed = mouse_is_pressed

            # Skip interaction detection if mouse still held or not just released
            if not mouse_just_released:
                continue

            # Handle submit button click (formal only)
            if submit_btn and submit_btn.contains(mouse):
                return  # Exit section

            # Handle option click
            for i, rect in enumerate(rects):
                if rect.contains(mouse):
                    answers[item['id']] = i + 1
                    timing.last_times[item['id']] = core.getTime()

                    # Auto-advance to next unanswered (if not all complete)
                    if len(answers) < n_items:
                        next_index = self.navigator.find_next_unanswered(
                            items, answers, current_index
                        )
                        current_index = next_index
                        nav_offset = self.navigator.center_offset(next_index, n_items)
                    # If all answered, stay in loop to show submit button
                    break  # Found clicked rect, exit for loop

            # Handle navigation click
            nav_action, current_index, nav_offset = self.navigator.handle_click(
                nav_items, l_rect, r_rect, items, current_index, nav_offset, mouse
            )
            if nav_action == 'jump':
                nav_offset = self.navigator.center_offset(current_index, n_items)
            # Note: No explicit continue needed - loop will naturally proceed
