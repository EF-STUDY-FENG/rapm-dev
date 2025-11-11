from __future__ import annotations
"""SectionRunner: orchestrates a single section flow using Renderer and Navigator.

Responsibilities:
- Show instruction
- Initialize timing (SectionTiming provided by caller)
- Main event loop: draw header/question/options/navigation
- Handle selection, auto-advance, submit button, and timeout

Zero behavior change vs original RavenTask._run_section.
"""
from typing import Any, Optional
from psychopy import event, core


class SectionRunner:
    def __init__(self, win, renderer, navigator, layout: dict, debug_mode: bool) -> None:
        self.win = win
        self.renderer = renderer
        self.navigator = navigator
        self.layout = layout
        self.debug_mode = debug_mode

    def run_section(self, section: str, conf: dict, answers: dict[str, int], timing) -> None:
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
            self.renderer.show_instruction(instruction_text, button_text=button_text, debug_mode=self.debug_mode)

        # Initialize timing
        start_time = core.getTime()
        if self.debug_mode:
            duration = 10 if section == 'practice' else 25  # Debug: 10s/25s
        else:
            duration = conf['time_limit_minutes'] * 60
        timing.initialize(start_time, duration)

        # Timer thresholds and submit flag
        if section == 'practice':
            show_threshold: Optional[int] = None
            red_threshold: Optional[int] = None
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
        while timing.remaining_seconds() > 0:
            item = items[current_index]

            # Draw navigation bar (buttons + arrows)
            nav_items, l_rect, l_txt, r_rect, r_txt = self.navigator.build_navigation(
                items, answers, current_index, nav_offset
            )
            for _, rect, label in nav_items:
                rect.draw(); label.draw()
            if l_rect:
                l_rect.draw(); l_txt.draw()
            if r_rect:
                r_rect.draw(); r_txt.draw()

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
            if timing.remaining_seconds() <= 0:
                break
