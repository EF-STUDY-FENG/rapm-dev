"""SectionRunner: orchestrates a single section flow using Renderer and Navigator.

Responsibilities:
"""
from __future__ import annotations

from psychopy import core, event

from rapm_types import SectionConfig


class SectionRunner:
    # =========================================================================
    # CONSTRUCTION
    # =========================================================================

    def __init__(self, win, renderer, navigator, layout: dict, debug_mode: bool) -> None:
        self.win = win
        self.renderer = renderer
        self.navigator = navigator
        self.layout = layout
        self.debug_mode = debug_mode

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def run_section(
        self,
        section: str,
        conf: SectionConfig,
        answers: dict[str, int],
        timing,
    ) -> None:
        """Run a single section ('practice'|'formal').

        Args:
            section: section name
            conf: section config dict (items, instruction, time_limit_minutes, ...)
            answers: dict to mutate with user answers
            timing: SectionTiming instance for this section
        """
        items = conf['items']
        n_items = len(items)
        if n_items == 0:
            return

        # Show instruction with button
        instruction_text = conf.get('instruction', '')
        button_text = conf.get('button_text', '继续')
        if instruction_text:
            self.renderer.show_instruction(
                instruction_text,
                button_text=button_text,
                debug_mode=self.debug_mode,
            )

        # Initialize timing
        start_time = core.getTime()
        if self.debug_mode:
            duration = 10 if section == 'practice' else 25  # Debug: 10s/25s
        else:
            duration = conf['time_limit_minutes'] * 60
        timing.initialize(start_time, duration)

        # Timer thresholds and submit button configuration
        if section == 'practice':
            show_threshold: int | None = None
            red_threshold: int | None = None
            show_submit = True  # Now show submit button in practice too
            submit_button_text = '完成练习'
        else:
            if self.debug_mode:
                show_threshold = self.layout['debug_timer_show_threshold']
                red_threshold = self.layout['debug_timer_red_threshold']
            else:
                show_threshold = self.layout['formal_timer_show_threshold']
                red_threshold = self.layout['timer_red_threshold']
            show_submit = True
            submit_button_text = '提交作答'

        current_index = 0
        nav_offset = 0

        # Mouse state tracking (for debouncing without blocking)
        mouse = event.Mouse(win=self.win)
        mouse_was_pressed = False  # Track previous frame state

        # Main event loop
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

            # Draw submit button (when all answered)
            submit_btn = None
            if show_submit and len(answers) == n_items:
                submit_btn = self.renderer.draw_submit_button(label=submit_button_text)

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
                self.win, nav_items, l_rect, r_rect, items, current_index, nav_offset, mouse
            )
            if nav_action == 'jump':
                nav_offset = self.navigator.center_offset(current_index, n_items)
            # Note: No explicit continue needed - loop will naturally proceed
