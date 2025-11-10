from __future__ import annotations

"""Raven Task Core Module - RavenTask class and helper functions

This module contains the core experiment logic:
- RavenTask: Main experiment class handling practice and formal test sections
- build_items_from_pattern: Helper function to build item lists from patterns
"""
from psychopy import visual, event, core
from typing import Any, Optional, Sequence
import json
import os
import csv
from datetime import datetime
from config_loader import get_output_dir
from path_utils import (
    resolve_path,
    file_exists_nonempty,
    load_answers,
    fitted_size_keep_aspect,
)

# Use imported functions from config_loader for consistency
DATA_DIR = get_output_dir()


def build_items_from_pattern(
    pattern: str,
    count: int,
    answers: list[int],
    start_index: int,
    section_prefix: str,
) -> list[dict]:
    """Build items list using pattern like 'stimuli/images/RAPM_t{XX}-{Y}.jpg'.
    - XX: zero-padded item index (01..)
    - Y:  option index (0 for question, 1..8 for options)
    """
    items: list[dict] = []
    for i in range(1, count + 1):
        XX = f"{i:02d}"
        q_path = pattern.replace('{XX}', XX).replace('{Y}', '0')
        option_paths = [pattern.replace('{XX}', XX).replace('{Y}', str(opt)) for opt in range(1, 9)]
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


class RavenTask:
    def __init__(
        self,
        win: Any,
        sequence: dict[str, Any],
        layout: dict[str, Any],
        participant_info: Optional[dict[str, Any]] = None,
    ) -> None:
        self.win = win
        self.sequence = {
            'practice': sequence['practice'],
            'formal': sequence['formal']
        }
        self.practice = self.sequence['practice']
        self.formal = self.sequence['formal']
        self.participant_info = participant_info or {}
        self.practice_answers = {}
        self.formal_answers = {}

        # Layout parameters are automatically merged by load_layout() in config_loader.py
        # All default keys are guaranteed to be present, so no validation needed here
        self.layout = dict(layout)

        # Debug mode: can be set in layout.json or by entering participant_id as '0'
        pid = str(self.participant_info.get('participant_id', '')).strip()
        self.debug_mode = self.layout.get('debug_mode', False) or (pid == '0')

        # Deadlines are set right before each section starts (after showing instructions)
        self.practice_deadline = None
        self.formal_deadline = None  # set when formal starts
        self.max_visible_nav = 12
        # Store timing data for saving
        self.practice_last_times = {}
        self.practice_start_time = None
        self.formal_last_times = {}
        self.formal_start_time = None

        try:
            answers_file = sequence.get('answers_file')
        except AttributeError:
            answers_file = None
        if answers_file:
            answers = load_answers(answers_file)
            # practice
            p_count = int(self.practice.get('count', 0))
            p_pattern = self.practice.get('pattern')
            if p_count and p_pattern:
                self.practice['items'] = build_items_from_pattern(p_pattern, p_count, answers, 0, 'P')
            # formal (offset after practice)
            f_count = int(self.formal.get('count', 0))
            f_pattern = self.formal.get('pattern')
            if f_count and f_pattern:
                self.formal['items'] = build_items_from_pattern(f_pattern, f_count, answers, p_count, 'F')

    # ---------- Layout accessor ----------
    def L(self, key: str) -> Any:
        """Strict accessor for layout values. Missing keys raise a clear error."""
        if key not in self.layout:
            raise KeyError(f"layout.json 缺少必须的键: {key}")
        return self.layout[key]
    def run(self) -> None:
        """Main entry point: run practice then formal test"""
        # Show practice instructions
        self.show_instruction(
            "下面将进行的是瑞文高级推理测验\n"
            "每道题目的上方是一张大图，大图的图案缺了一部分\n"
            "请你从下面8个备选图形中找出大图的缺失部分，并选中它\n"
            "在正式测试之前，有12道练习题目\n"
            "限时10分钟",
            button_text="开始练习"
        )
        # Set practice deadline now
        self.practice_start_time = core.getTime()
        if self.debug_mode:
            # Debug: 10 seconds for practice
            self.practice_deadline = self.practice_start_time + 10
        else:
            self.practice_deadline = self.practice_start_time + self.practice['time_limit_minutes'] * 60
        # Run practice section
        self.practice_last_times = self.run_section('practice')
        # Practice finished
        # Show formal instructions
        self.show_instruction(
            "练习结束，下面将开始正式测试\n"
            "正式测试一共有36道题目\n"
            "题目按从易到难的顺序编排\n"
            "限时40分钟\n"
            "只剩最后10分钟时将倒计时提醒您",
            button_text="开始测试"
        )
        # Set formal deadline (use debug time if in debug mode)
        self.formal_start_time = core.getTime()
        if self.debug_mode:
            # Debug: 25 seconds (show timer at 20s, red at 10s)
            self.formal_deadline = self.formal_start_time + 25
        else:
            self.formal_deadline = self.formal_start_time + self.formal['time_limit_minutes'] * 60
        # Run formal section
        self.formal_last_times = self.run_section('formal')
        # Save results after both sections
        self.save_and_exit()

    # ---------- Generic drawing helpers ----------
    def draw_timer(
        self,
        deadline: Optional[float],
        show_threshold: Optional[int] = None,
        red_threshold: Optional[int] = None,
    ) -> None:
        """Draw countdown timer.

        Args:
            deadline: The deadline timestamp
            show_threshold: Only show timer when remaining time <= this (seconds). None = always show
            red_threshold: Change color to red when remaining time <= this (seconds)
        """
        remaining = max(0, int(deadline - core.getTime()))

        # If show_threshold is set and more time remains, don't draw
        if show_threshold is not None and remaining > show_threshold:
            return

        mins = remaining // 60
        secs = remaining % 60
        timer_text = f"剩余时间: {mins:02d}:{secs:02d}"

        # Change color to red if threshold is set and remaining time is low
        color = 'red' if (red_threshold is not None and remaining <= red_threshold) else 'white'

        timerStim = visual.TextStim(
            self.win,
            text=timer_text,
            pos=(0, self.L('header_y')),
            height=self.L('header_font_size'),
            color=color,
            font=self.L('font_main')
        )
        timerStim.draw()

    def draw_multiline(
        self,
        lines: Sequence[str],
        center_y: float,
        line_height: float,
        spacing: float = 1.5,
        colors: Optional[list[str]] = None,
        bold_idx: Optional[set[int]] = None,
        x: float = 0.0,
    ) -> None:
        """Draw multiple lines with custom line spacing centered vertically around center_y.

        Args:
            lines: sequence of strings to draw in order
            center_y: vertical center in norm units
            line_height: height for each line
            spacing: line spacing multiplier (e.g., 1.5)
            colors: optional list of per-line colors (fallback 'white')
            bold_idx: optional set of line indices to render bold
            x: horizontal position (default center)
        """
        lines = list(lines or [])
        n = len(lines)
        if n == 0:
            return
        total = line_height * spacing * (n - 1) if n > 1 else 0.0
        start_y = center_y + total / 2.0
        for i, text in enumerate(lines):
            y = start_y - i * (line_height * spacing)
            color = (colors[i] if (colors and i < len(colors)) else 'white')
            stim = visual.TextStim(self.win, text=text or '', pos=(x, y), height=line_height, color=color, font=self.L('font_main'))
            # try bold if available
            try:
                if bold_idx and i in bold_idx:
                    stim.bold = True
            except Exception:
                pass
            stim.draw()

    def draw_progress(self, answered_count: int, total_count: int) -> None:
        """Draw answered/total progress indicator at header_y position.

        Green when all answered, white otherwise.
        Right-aligned to navigation arrow with small margin.
        """
        answered_count = max(0, min(answered_count, total_count))
        txt = f"已答 {answered_count} / 总数 {total_count}"
        color = 'green' if total_count > 0 and answered_count >= total_count else 'white'
        # Place at right side on the same height as the timer (i.e., under nav), right-aligned
        y = self.L('header_y')
        # Align progress left edge to the left edge of the right arrow box (with a small margin)
        right_edge_x = self.L('nav_arrow_x_right') - (self.L('nav_arrow_w') / 2.0)
        x = right_edge_x - self.L('progress_right_margin')
        progStim = visual.TextStim(self.win, text=txt, pos=(x, y), height=self.L('header_font_size'), color=color, font=self.L('font_main'))
        try:
            progStim.anchorHoriz = 'right'
        except Exception:
            pass
        progStim.draw()

    def draw_header(
        self,
        deadline: Optional[float],
        show_threshold: Optional[int],
        red_threshold: Optional[int],
        answered_count: int,
        total_count: int,
        show_timer: bool = True,
        show_progress: bool = True,
    ) -> None:
        """Draw the top header info (timer + progress) sharing the same vertical position.

        Args:
            deadline: absolute time for countdown
            show_threshold: timer visibility threshold (None to always show)
            red_threshold: timer red color threshold
            answered_count: number of answered items
            total_count: total number of items
            show_timer: whether to draw the timer
            show_progress: whether to draw the progress
        """
        if show_timer and deadline is not None:
            self.draw_timer(deadline, show_threshold=show_threshold, red_threshold=red_threshold)
        if show_progress and total_count is not None:
            self.draw_progress(answered_count, total_count)

    def show_instruction(self, text: str, button_text: str = "继续") -> None:
        """Display centered multi-line instruction with a styled button.
        In normal mode, the button becomes clickable only after self.instruction_button_delay seconds;
        in debug mode, it's clickable immediately (no countdown).
        """
        lines = (text or "").split("\n")
        center_y = self.L('instruction_center_y')
        line_h = self.L('instruction_line_height')
        spacing = self.L('instruction_line_spacing')
        show_start = core.getTime()
        # In debug mode, make the instruction button immediately clickable (no countdown)
        delay = 0.0 if self.debug_mode else self.L('instruction_button_delay')
        btn_w = self.L('button_width')
        btn_h = self.L('button_height')
        btn_pos = (self.L('button_x'), self.L('instruction_button_y'))
        label_h = self.L('button_label_height')
        line_w = self.L('button_line_width')
        mouse = event.Mouse(win=self.win)
        clickable = False

        while True:
            elapsed = core.getTime() - show_start
            if not clickable and elapsed >= delay:
                clickable = True

            # Draw instruction text
            self.draw_multiline(lines, center_y=center_y, line_height=line_h, spacing=spacing)

            # Determine button colors
            if clickable:
                temp_rect = visual.Rect(self.win, width=btn_w, height=btn_h, pos=btn_pos)
                hovered = temp_rect.contains(mouse)
                fill_col = self.L('button_fill_hover') if hovered else self.L('button_fill_normal')
                outline_col = self.L('button_outline_hover') if hovered else self.L('button_outline_normal')
            else:
                fill_col = self.L('button_fill_disabled')
                outline_col = self.L('button_outline_disabled')

            btn_rect = visual.Rect(self.win, width=btn_w, height=btn_h, pos=btn_pos,
                                    lineColor=outline_col, fillColor=fill_col, lineWidth=line_w)
            remaining = int(max(0, delay - elapsed))
            label_text = button_text if clickable else f"{button_text} ({remaining}s)"
            btn_label = visual.TextStim(self.win, text=label_text, pos=btn_pos, height=label_h, color='white', font=self.L('font_main'))
            btn_rect.draw(); btn_label.draw()
            self.win.flip()

            if clickable and any(mouse.getPressed()) and btn_rect.contains(mouse):
                while any(mouse.getPressed()):
                    core.wait(0.01)
                break

    def draw_question(self, item_id: str, image_path: Optional[str]) -> None:
        # Question area at top center (no border frame)
        q_w = self.L('question_box_w') * self.L('scale_question')
        q_h = self.L('question_box_h') * self.L('scale_question')
        # Remove the white border box - only draw the image
        if image_path and file_exists_nonempty(image_path):
            try:
                max_w = q_w - self.L('question_img_margin_w')
                max_h = q_h - self.L('question_img_margin_h')
                disp_w, disp_h = fitted_size_keep_aspect(image_path, max_w, max_h)
                img = visual.ImageStim(self.win, image=resolve_path(image_path), pos=(0, self.L('question_box_y')), size=(disp_w, disp_h))
                img.draw()
            except Exception:
                txt = visual.TextStim(self.win, text=f"题目 {item_id}\n(图片加载失败)", pos=(0, self.L('question_box_y')), height=0.06, font=self.L('font_main'))
                txt.draw()
        else:
            txt = visual.TextStim(self.win, text=f"题目 {item_id}\n(图片占位)", pos=(0, self.L('question_box_y')), height=0.06, font=self.L('font_main'))
            txt.draw()

    def create_option_rects(self) -> list[Any]:
        """Build option rectangles for the current item.

        Returns:
            list[visual.Rect]: Rectangles mapped to option indices in order.
        """
        cols = int(self.L('option_cols'))
        rows = int(self.L('option_rows'))
        dx = self.L('option_dx')
        dy = self.L('option_dy')
        rect_w = self.L('option_rect_w') * self.L('scale_option')
        rect_h = self.L('option_rect_h') * self.L('scale_option')
        center_y = self.L('option_grid_center_y')

        rects: list[visual.Rect] = []
        total_cells = cols * rows
        for r in range(rows):
            for c in range(cols):
                # Coordinate system: col 0 left, row 0 top
                x = (c - (cols - 1) / 2) * dx
                y = center_y - (r - (rows - 1) / 2) * dy
                rect = visual.Rect(
                    self.win,
                    width=rect_w,
                    height=rect_h,
                    pos=(x, y),
                    lineColor='white',
                    lineWidth=2,
                    fillColor=None
                )
                rects.append(rect)
        return rects[:total_cells]

    def draw_options(
        self,
        option_paths: list[str],
        rects: list[Any],
        selected_index: Optional[int] = None,
    ) -> None:
        """绘制选项矩形与图片。

        Args:
            option_paths: 图片路径列表(最多与 rects 数量相同)。
            rects: create_option_rects 返回的矩形列表。
            selected_index: 已选择的选项索引(0 基),None 表示未选择。
        """
        for i, rect in enumerate(rects):
            # 高亮已选
            if selected_index is not None and i == selected_index:
                rect.lineColor = 'yellow'
                rect.lineWidth = 4
                rect.fillColor = (0, 0.45, 0)
            else:
                rect.lineColor = 'white'
                rect.lineWidth = 2
                rect.fillColor = None
            rect.draw()

            if i < len(option_paths):
                path = option_paths[i]
                if path and file_exists_nonempty(path):
                    max_w = self.L('option_img_w') * self.L('scale_option')
                    max_h = self.L('option_img_h') * self.L('scale_option')
                    disp_w, disp_h = fitted_size_keep_aspect(path, max_w, max_h)
                    img = visual.ImageStim(
                        self.win,
                        image=resolve_path(path),
                        pos=rect.pos,
                        size=(disp_w * self.L('option_img_fill'), disp_h * self.L('option_img_fill'))
                    )
                    img.draw()
                else:
                    placeholder = visual.TextStim(self.win, text=str(i+1), pos=rect.pos, height=0.05, color='gray', font=self.L('font_main'))
                    placeholder.draw()

    def detect_click_on_rects(self, rects: list[Any]) -> Optional[int]:
        """Detect click on any option rectangle.

        Returns:
            int | None: Zero-based index if clicked, else None.
        """
        mouse = event.Mouse(win=self.win)
        if not any(mouse.getPressed()):
            return None
        for i, rect in enumerate(rects):
            if rect.contains(mouse):
                # Wait for release to avoid repeat from hold
                while any(mouse.getPressed()):
                    core.wait(0.01)
                return i
        return None

    def _get_section_config(self, section: str) -> dict[str, Any]:
        """Assemble runtime parameters for a test section."""
        if section == 'practice':
            # Practice: timer always visible, no red warning
            return {
                'config': self.practice,
                'answers': self.practice_answers,
                'deadline': self.practice_deadline,
                'show_submit': False,
                'auto_save_on_timeout': False,
                'timer_show_threshold': None,
                'timer_red_threshold': None,
            }
        # formal
        if self.debug_mode:
            show_t = self.L('debug_timer_show_threshold')
            red_t = self.L('debug_timer_red_threshold')
        else:
            show_t = self.L('formal_timer_show_threshold')
            red_t = self.L('timer_red_threshold')
        return {
            'config': self.formal,
            'answers': self.formal_answers,
            'deadline': self.formal_deadline,
            'show_submit': True,
            'auto_save_on_timeout': True,
            'timer_show_threshold': show_t,
            'timer_red_threshold': red_t,
        }

    def _find_next_unanswered(
        self,
        items: list[dict[str, Any]],
        answers_dict: dict[str, int],
        current_index: int,
    ) -> int:
        """Find the next unanswered item index.

        If on the last item, wraps around to check from the beginning.
        Otherwise, searches forward from current position.

        Returns the index of the next unanswered item, or current_index if none found.
        """
        n_items = len(items)
        next_index = current_index

        # If currently on the last item, check from the beginning for unanswered items
        if current_index == n_items - 1:
            for k in range(n_items):
                if items[k]['id'] not in answers_dict:
                    next_index = k
                    break
        else:
            # Normal flow: look forward from current position
            for k in range(current_index + 1, n_items):
                if items[k]['id'] not in answers_dict:
                    next_index = k
                    break
            # Fallback: if nothing found ahead and not at last item, stay or advance
            if next_index == current_index and current_index < n_items - 1:
                next_index += 1

        return next_index

    def run_section(self, section: str) -> dict[str, float]:
        """Run a test section ('practice' or 'formal') with unified flow.

        Args:
            section: 'practice' or 'formal'
        """
        # Get section configuration
        cfg = self._get_section_config(section)
        items = cfg['config']['items']
        n_items = len(items)
        if n_items == 0:
            return

        answers = cfg['answers']
        deadline = cfg['deadline']
        # Local navigation state (no longer stored as object attributes)
        current_index = 0
        nav_offset = 0

        last_times = {}

        # Main loop
        while core.getTime() < deadline:
            item = items[current_index]

            # Draw navigation bar
            nav_items, l_rect, l_txt, r_rect, r_txt = self._build_navigation(
                items, answers, current_index, nav_offset)
            for _, rect, label in nav_items:
                rect.draw(); label.draw()
            if l_rect: l_rect.draw(); l_txt.draw()
            if r_rect: r_rect.draw(); r_txt.draw()

            # Draw header (timer + progress) - unified logic
            self.draw_header(
                deadline=deadline,
                show_threshold=cfg['timer_show_threshold'],
                red_threshold=cfg['timer_red_threshold'],
                answered_count=len(answers),
                total_count=n_items,
                show_timer=True,
                show_progress=True,
            )

            # Draw question & options
            self.draw_question(item['id'], item.get('question_image'))
            rects = self.create_option_rects()
            prev_choice = answers.get(item['id'])
            self.draw_options(item.get('options', []), rects,
                            selected_index=(prev_choice - 1) if prev_choice else None)

            # Draw submit button (formal only, when all answered)
            submit_btn = None
            if cfg['show_submit'] and len(answers) == n_items:
                submit_btn = self._draw_submit_button()

            self.win.flip()

            # Handle submit button click (formal only)
            if submit_btn:
                mouse_global = event.Mouse(win=self.win)
                if any(mouse_global.getPressed()) and submit_btn.contains(mouse_global):
                    while any(mouse_global.getPressed()):
                        core.wait(0.01)
                    self.formal_last_times = last_times
                        # Return to let run() handle saving
                    return last_times

            # Handle option click
            choice = self.detect_click_on_rects(rects)
            if choice is not None:
                answers[item['id']] = choice + 1
                # 记录该题最后作答时间
                now_sec = core.getTime()
                last_times[item['id']] = now_sec
                # Check if all answered
                if len(answers) == n_items:
                    if section == 'practice':
                        break  # Exit practice loop
                    # For formal, stay in loop to show submit button
                else:
                    # Find next unanswered item
                    next_index = self._find_next_unanswered(items, answers, current_index)
                    current_index = next_index
                    nav_offset = self._center_offset(next_index, n_items)
                continue

            # Handle navigation click
            nav_action, current_index, nav_offset = self._handle_navigation_click(
                nav_items, l_rect, r_rect, items, current_index, nav_offset)
            if nav_action == 'jump':
                # center only when direct jump
                nav_offset = self._center_offset(current_index, n_items)
                continue
            if nav_action == 'page':
                # page only moved the visible window; keep current index unchanged
                continue

            # Check timeout
            if core.getTime() >= deadline:
                break

        # Handle timeout
        if cfg['auto_save_on_timeout']:
            return last_times

        return last_times

    def _draw_submit_button(self) -> Any:
        """Draw the submit button and return the rect for click detection.

        Returns:
            visual.Rect: The submit button rectangle for click detection
        """
        btn_pos = (self.L('button_x'), self.L('submit_button_y'))
        mouse_local = event.Mouse(win=self.win)
        temp_rect = visual.Rect(self.win, width=self.L('button_width'),
                               height=self.L('button_height'), pos=btn_pos)
        hovered = temp_rect.contains(mouse_local)
        fill_col = self.L('button_fill_hover') if hovered else self.L('button_fill_normal')
        outline_col = self.L('button_outline_hover') if hovered else self.L('button_outline_normal')

        submit_rect = visual.Rect(
            self.win,
            width=self.L('button_width'),
            height=self.L('button_height'),
            pos=btn_pos,
            lineColor=outline_col,
            fillColor=fill_col,
            lineWidth=self.L('button_line_width')
        )
        submit_label = visual.TextStim(
            self.win,
            text='提交作答',
            pos=btn_pos,
            height=self.L('button_label_height'),
            color='white',
            font=self.L('font_main')
        )
        submit_rect.draw()
        submit_label.draw()
        return submit_rect

    # (run_practice / run_formal wrappers removed; use run_section('practice'|'formal'))

    # ---------- Navigation Helpers (new) ----------
    def _center_offset(self, index: int, total: int) -> int:
        if total <= self.max_visible_nav:
            return 0
        half = self.max_visible_nav // 2
        offset = index - half
        if offset < 0:
            offset = 0
        max_off = total - self.max_visible_nav
        if offset > max_off:
            offset = max_off
        return offset
    def _build_navigation(
        self,
        items: list[dict[str, Any]],
        answers_dict: dict[str, int],
        current_index: int,
        offset: int,
    ) -> tuple[list[tuple[int, Any, Any]], Any, Any, Any, Any]:
        """Construct navigation stimuli (question number buttons + page arrows)."""
        n = len(items)
        start = offset
        end = min(n, start + self.max_visible_nav)
        visible = list(range(start, end))
        stims = []
        if not visible:
            return stims, None, None, None, None

        count = len(visible)
        nav_y = self.L('nav_y')
        x_left_edge = self.L('nav_arrow_x_left')
        x_right_edge = self.L('nav_arrow_x_right')
        arrow_w = self.L('nav_arrow_w')
        gap = self.L('nav_gap')

        x_left = x_left_edge + arrow_w + gap
        x_right = x_right_edge - arrow_w - gap
        span = x_right - x_left
        xs = [x_left + i * span / (count - 1) for i in range(count)] if count > 1 else [ (x_left + x_right) / 2.0 ]

        item_w = self.L('nav_item_w')
        item_h = self.L('nav_item_h')
        label_h = self.L('nav_label_height')

        for i, gi in enumerate(visible):
            answered = items[gi]['id'] in answers_dict
            rect = visual.Rect(
                self.win,
                width=item_w,
                height=item_h,
                pos=(xs[i], nav_y),
                lineColor='yellow' if gi == current_index else 'white',
                lineWidth=3,
                fillColor=(0, 0.45, 0) if answered else None,
            )
            _raw_id = items[gi]['id'] or ''
            _digits = ''.join([ch for ch in _raw_id if ch.isdigit()])
            _label_txt = str(int(_digits)) if _digits else _raw_id
            label = visual.TextStim(
                self.win,
                text=_label_txt,
                pos=(xs[i], nav_y),
                height=label_h,
                color='black' if answered else 'white',
                bold=answered,
                font=self.L('font_main')
            )
            stims.append((gi, rect, label))

        left_rect = left_txt = right_rect = right_txt = None
        arrow_h = item_h
        arrow_label_h = self.L('nav_arrow_label_height')
        if start > 0:
            left_rect = visual.Rect(
                self.win,
                width=arrow_w,
                height=arrow_h,
                pos=(x_left_edge, nav_y),
                lineColor='white',
                lineWidth=3,
                fillColor=(0.15, 0.15, 0.15),
            )
            left_txt = visual.TextStim(
                self.win,
                text='◄',
                pos=(x_left_edge, nav_y),
                height=arrow_label_h,
                bold=True,
                font=self.L('font_main')
            )
        if end < n:
            right_rect = visual.Rect(
                self.win,
                width=arrow_w,
                height=arrow_h,
                pos=(x_right_edge, nav_y),
                lineColor='white',
                lineWidth=3,
                fillColor=(0.15, 0.15, 0.15),
            )
            right_txt = visual.TextStim(
                self.win,
                text='►',
                pos=(x_right_edge, nav_y),
                height=arrow_label_h,
                bold=True,
                font=self.L('font_main')
            )
        return stims, left_rect, left_txt, right_rect, right_txt

    def _handle_navigation_click(
        self,
        nav_items: list[tuple[int, Any, Any]],
        left_rect: Any,
        right_rect: Any,
        items: list[dict[str, Any]],
        current_index: int,
        nav_offset: int,
    ) -> tuple[Optional[str], int, int]:
        """Handle navigation clicks.

        Returns:
            (action, current_index, nav_offset) where action in {'jump','page',None}
        """
        mouse = event.Mouse(win=self.win)
        if any(mouse.getPressed()):
            if left_rect and left_rect.contains(mouse):
                while any(mouse.getPressed()):
                    core.wait(0.01)
                nav_offset = max(0, nav_offset - self.max_visible_nav)
                return 'page', current_index, nav_offset
            if right_rect and right_rect.contains(mouse):
                while any(mouse.getPressed()):
                    core.wait(0.01)
                max_off = max(0, len(items) - self.max_visible_nav)
                nav_offset = min(max_off, nav_offset + self.max_visible_nav)
                return 'page', current_index, nav_offset
            for gi, rect, label in nav_items:
                if rect.contains(mouse) or label.contains(mouse):
                    while any(mouse.getPressed()):
                        core.wait(0.01)
                    current_index = gi
                    return 'jump', current_index, nav_offset
        return None, current_index, nav_offset

    def save_and_exit(self) -> None:
        """Save results and show completion message."""
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Ensure data directory exists in frozen / portable builds
        os.makedirs(DATA_DIR, exist_ok=True)
        out_path = os.path.join(DATA_DIR, f'raven_results_{ts}.csv')
        pid = self.participant_info.get('participant_id', '')
        practice_correct = 0
        formal_correct = 0
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['participant_id', 'section', 'item_id', 'answer', 'correct', 'is_correct', 'time'])
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
                    writer.writerow([pid, section, iid, ans if ans is not None else '', correct if correct is not None else '', '1' if is_correct else ('0' if is_correct is not None else ''), time_used])
            write_section('practice', self.practice.get('items', []), self.practice_answers, self.practice_last_times, self.practice_start_time)
            write_section('formal', self.formal.get('items', []), self.formal_answers, self.formal_last_times, self.formal_start_time)
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
        lines = ['作答完成！', '感谢您的作答！']
        colors = ['green', 'white']
        for _ in range(300):  # ~5s
            self.draw_multiline(lines, center_y=0.05, line_height=0.065, spacing=1.5,
                                colors=colors, bold_idx={0})
            self.win.flip()
