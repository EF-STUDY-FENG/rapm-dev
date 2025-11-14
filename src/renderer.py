"""Renderer: encapsulates all drawing primitives for the RAPM task.

This class provides a memory-efficient rendering interface that:
- Reuses visual objects to prevent GPU memory leaks
- Accepts state via dependency injection (window, layout)
- Separates concerns: atomic draw_* methods (no flip) vs show_* flows (with flip)

Memory Management:
- Pre-creates reusable objects (timer, progress, placeholders) in __init__
- Minimizes per-frame allocations (ImageStim only for varying paths)
- Caller responsible for window.flip() in main loops
"""
from __future__ import annotations

from typing import Any, Sequence

from psychopy import core, event, visual

from path_utils import file_exists_nonempty, fitted_size_keep_aspect, resolve_path
from rapm_types import LayoutConfig


class Renderer:
    """Handles all visual rendering for RAPM tasks with memory optimization.

    Architecture:
    - __init__: Pre-creates reusable visual objects (prevents memory leaks)
    - show_*: Blocking flows with internal flip loops (instruction, completion)
    - draw_*: Atomic drawing primitives (caller manages flip)
    - Utility: Helper methods (geometry, rect creation)
    """

    def __init__(self, win: visual.Window, layout: LayoutConfig) -> None:
        """Initialize renderer with pre-created reusable visual objects.

        Args:
            win: PsychoPy window for rendering
            layout: Layout configuration dictionary
        """
        self._win = win
        self._layout = layout

        self._timer_stim = visual.TextStim(
            self._win, text='', pos=(0, self._layout['header_y']),
            height=self._layout['header_font_size'], color='white', font=self._layout['font_main']
        )
        self._progress_stim = visual.TextStim(
            self._win, text='', pos=(0, self._layout['header_y']),
            height=self._layout['header_font_size'], color='white', font=self._layout['font_main']
        )

        self._question_stim = visual.TextStim(
            self._win, text='', pos=(0, self._layout['question_box_y']),
            height=0.06, font=self._layout['font_main']
        )

        self._option_placeholders = [
            visual.TextStim(
                self._win, text='', pos=(0, 0), height=0.05,
                color='gray', font=self._layout['font_main']
            )
            for _ in range(8)
        ]

    def show_instruction(self, text: str, button_text: str, debug_mode: bool) -> None:
        """Display instruction screen with delayed clickable button (blocking).

        Internal event loop with edge-detected mouse handling.
        Button activates after configured delay (0s in debug mode).

        Args:
            text: Multi-line instruction text (newline-separated)
            button_text: Label for the continue button
            debug_mode: If True, skip button delay
        """
        lines = (text or '').split('\n')
        layout = self._layout
        delay = 0.0 if debug_mode else layout['instruction_button_delay']
        show_start = core.getTime()

        mouse = event.Mouse(win=self._win)
        clickable = False
        mouse_was_pressed = False  # Edge detection state

        while True:
            elapsed = core.getTime() - show_start
            if not clickable and elapsed >= delay:
                clickable = True

            self._draw_multiline(
                lines,
                center_y=layout['instruction_center_y'],
                line_height=layout['instruction_line_height'],
                spacing=layout['instruction_line_spacing']
            )

            btn_pos = (layout['button_x'], layout['instruction_button_y'])
            temp_rect = visual.Rect(
                self._win,
                width=layout['button_width'],
                height=layout['button_height'],
                pos=btn_pos,
            )
            hovered = temp_rect.contains(mouse)

            if clickable:
                fill_col = (
                    layout['button_fill_hover'] if hovered
                    else layout['button_fill_normal']
                )
                outline_col = (
                    layout['button_outline_hover'] if hovered
                    else layout['button_outline_normal']
                )
            else:
                fill_col = layout['button_fill_disabled']
                outline_col = layout['button_outline_disabled']

            btn_rect = visual.Rect(
                self._win,
                width=layout['button_width'],
                height=layout['button_height'],
                pos=btn_pos,
                lineColor=outline_col,
                fillColor=fill_col,
                lineWidth=layout['button_line_width'],
            )
            remaining = int(max(0, delay - elapsed))
            label_text = button_text if clickable else f"{button_text} ({remaining}s)"
            btn_label = visual.TextStim(
                self._win, text=label_text, pos=btn_pos,
                height=layout['button_label_height'],
                color='white', font=layout['font_main']
            )
            btn_rect.draw()
            btn_label.draw()
            self._win.flip()

            mouse_is_pressed = any(mouse.getPressed())
            mouse_just_released = mouse_was_pressed and not mouse_is_pressed
            mouse_was_pressed = mouse_is_pressed

            if clickable and mouse_just_released and btn_rect.contains(mouse):
                break

    def show_completion(
        self,
        lines: Sequence[str] | None = None,
        colors: list[str] | None = None,
        seconds: float = 5.0,
        center_y: float = 0.05,
        line_height: float = 0.065,
        spacing: float = 1.5,
        bold_idx: set[int] | None = None,
    ) -> None:
        """Display completion screen for fixed duration (blocking).

        Internal flip loop for the specified time period.

        Args:
            lines: Text lines to display (defaults to completion message)
            colors: Per-line color list (defaults to ['green', 'white'])
            seconds: Display duration in seconds
            center_y: Vertical center position
            line_height: Height of each text line
            spacing: Vertical spacing multiplier between lines
            bold_idx: Set of line indices to render bold
        """
        if lines is None:
            lines = ['作答完成！', '感谢您的作答！']
        if colors is None:
            colors = ['green', 'white']
        if bold_idx is None:
            bold_idx = {0}
        end_time = core.getTime() + max(0.0, seconds)
        while core.getTime() < end_time:
            self._draw_multiline(
                lines,
                center_y=center_y,
                line_height=line_height,
                spacing=spacing,
                colors=colors,
                bold_idx=bold_idx,
            )
            self._win.flip()

    def draw_header(
        self,
        remaining_seconds: float | None,
        show_threshold: int | None,
        red_threshold: int | None,
        answered_count: int,
        total_count: int,
    ) -> None:
        """Draw header area with timer and progress indicators.

        Args:
            remaining_seconds: Countdown value (None = don't show timer)
            show_threshold: Timer hidden if remaining > this (None = always show)
            red_threshold: Timer turns red if remaining <= this
            answered_count: Number of completed items
            total_count: Total number of items
        """
        if remaining_seconds is not None:
            self.draw_timer(remaining_seconds, show_threshold, red_threshold)
        self.draw_progress(answered_count, total_count)

    def draw_timer(
        self,
        remaining_seconds: float | None,
        show_threshold: int | None,
        red_threshold: int | None,
    ) -> None:
        """Draw countdown timer (MM:SS format, reuses pre-created TextStim).

        Args:
            remaining_seconds: Countdown value (None = 0)
            show_threshold: Hide timer if remaining > this (None = always show)
            red_threshold: Change color to red if remaining <= this
        """
        remaining = max(0, int(remaining_seconds or 0))
        if show_threshold is not None and remaining > show_threshold:
            return
        mins, secs = divmod(remaining, 60)
        timer_text = f"剩余时间: {mins:02d}:{secs:02d}"
        color = 'red' if (red_threshold is not None and remaining <= red_threshold) else 'white'
        self._timer_stim.text = timer_text
        self._timer_stim.color = color
        self._timer_stim.draw()

    def draw_progress(self, answered_count: int, total_count: int) -> None:
        """Draw progress indicator showing completion status.

        Format: '已答 X / 总数 Y' (turns green when all completed).
        Reuses pre-created TextStim, positioned at right side of header.

        Args:
            answered_count: Number of items answered (clamped to [0, total_count])
            total_count: Total number of items
        """
        answered_count = max(0, min(answered_count, total_count))
        txt = f"已答 {answered_count} / 总数 {total_count}"
        color = 'green' if (total_count > 0 and answered_count >= total_count) else 'white'
        y = self._layout['header_y']
        right_edge_x = self._layout['nav_arrow_x_right'] - (self._layout['nav_arrow_w'] / 2.0)
        x = right_edge_x - self._layout['progress_right_margin']
        self._progress_stim.text = txt
        self._progress_stim.pos = (x, y)
        self._progress_stim.color = color
        try:
            self._progress_stim.anchorHoriz = 'right'
        except Exception:
            pass
        self._progress_stim.draw()

    def draw_question(self, item_id: str, image_path: str | None) -> None:
        """Draw question area with image or fallback placeholder.

        Note: ImageStim must be recreated per unique path (unavoidable),
        but we minimize scope to allow garbage collection.

        Args:
            item_id: Question identifier (used in fallback text)
            image_path: Path to question image (None or invalid = show placeholder)
        """
        layout = self._layout
        q_w = layout['question_box_w'] * layout['scale_question']
        q_h = layout['question_box_h'] * layout['scale_question']
        if image_path and file_exists_nonempty(image_path):
            try:
                max_w = q_w - layout['question_img_margin_w']
                max_h = q_h - layout['question_img_margin_h']
                disp_w, disp_h = fitted_size_keep_aspect(image_path, max_w, max_h)

                img = visual.ImageStim(
                    self._win,
                    image=resolve_path(image_path),
                    pos=(0, layout['question_box_y']),
                    size=(disp_w, disp_h),
                )
                img.draw()
            except Exception:
                self._question_stim.text = f"题目 {item_id}\n(图片加载失败)"
                self._question_stim.draw()
        else:
            self._question_stim.text = f"题目 {item_id}\n(图片占位)"
            self._question_stim.draw()

    def draw_options(
        self,
        option_paths: list[str],
        rects: list[Any],
        selected_index: int | None,
    ) -> None:
        """Draw option grid with selection highlighting.

        For each option: draws rect, then image (if available) or placeholder.
        Reuses pre-created placeholder TextStims where possible.

        Args:
            option_paths: List of image file paths for each option
            rects: Pre-created Rect objects positioned in grid
            selected_index: Index of selected option (None = no selection)
        """
        for i, rect in enumerate(rects):
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
                    layout = self._layout
                    max_w = layout['option_img_w'] * layout['scale_option']
                    max_h = layout['option_img_h'] * layout['scale_option']
                    disp_w, disp_h = fitted_size_keep_aspect(path, max_w, max_h)
                    fill = layout['option_img_fill']
                    img = visual.ImageStim(
                        self._win,
                        image=resolve_path(path),
                        pos=rect.pos,
                        size=(disp_w * fill, disp_h * fill),
                    )
                    img.draw()
                else:
                    if i < len(self._option_placeholders):
                        self._option_placeholders[i].text = str(i+1)
                        self._option_placeholders[i].pos = rect.pos
                        self._option_placeholders[i].draw()

    def draw_submit_button(self, mouse: Any, label: str = '提交作答') -> Any:
        """Draw submit button with hover effect (returns rect for hit testing).

        Args:
            mouse: Pre-created Mouse object from caller
            label: Button text to display

        Returns:
            Rect object for hit testing
        """
        layout = self._layout
        btn_pos = (layout['button_x'], layout['submit_button_y'])
        temp_rect = visual.Rect(
            self._win,
            width=layout['button_width'],
            height=layout['button_height'],
            pos=btn_pos,
        )
        hovered = temp_rect.contains(mouse)
        fill_col = (
            layout['button_fill_hover'] if hovered
            else layout['button_fill_normal']
        )
        outline_col = (
            layout['button_outline_hover'] if hovered
            else layout['button_outline_normal']
        )

        submit_rect = visual.Rect(
            self._win,
            width=layout['button_width'],
            height=layout['button_height'],
            pos=btn_pos,
            lineColor=outline_col,
            fillColor=fill_col,
            lineWidth=layout['button_line_width'],
        )
        submit_label = visual.TextStim(
            self._win, text=label, pos=btn_pos,
            height=layout['button_label_height'],
            color='white', font=layout['font_main']
        )
        submit_rect.draw()
        submit_label.draw()
        return submit_rect

    def _draw_multiline(
        self,
        lines: Sequence[str],
        center_y: float,
        line_height: float,
        spacing: float = 1.5,
        colors: list[str] | None = None,
        bold_idx: set[int] | None = None,
        x: float = 0.0,
    ) -> None:
        """Draw vertically-centered multi-line text (internal helper).

        Used by show_instruction and show_completion for text rendering.
        Creates TextStim per line (acceptable for short-lived screens).

        Args:
            lines: Text lines to render
            center_y: Vertical center position of text block
            line_height: Height of each text line
            spacing: Vertical spacing multiplier between lines
            colors: Per-line color list (defaults to white)
            bold_idx: Set of line indices to render bold
            x: Horizontal position (defaults to center)
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
            stim = visual.TextStim(
                self._win, text=text or '', pos=(x, y), height=line_height,
                color=color, font=self._layout['font_main']
            )
            try:
                if bold_idx and i in bold_idx:
                    stim.bold = True
            except Exception:
                pass
            stim.draw()

    def create_option_rects(self) -> list[Any]:
        """Create positioned Rect objects for option grid layout.

        Generates rects in row-major order (left-to-right, top-to-bottom).
        Caller is responsible for drawing these objects.

        Returns:
            List of visual.Rect objects positioned according to layout config
        """
        layout = self._layout
        cols = int(layout['option_cols'])
        rows = int(layout['option_rows'])
        dx = layout['option_dx']
        dy = layout['option_dy']
        rect_w = layout['option_rect_w'] * layout['scale_option']
        rect_h = layout['option_rect_h'] * layout['scale_option']
        center_y = layout['option_grid_center_y']
        rects: list[Any] = []
        for r in range(rows):
            for c in range(cols):
                x = (c - (cols - 1) / 2) * dx
                y = center_y - (r - (rows - 1) / 2) * dy
                rects.append(visual.Rect(
                    self._win, width=rect_w, height=rect_h, pos=(x, y),
                    lineColor='white', lineWidth=2, fillColor=None
                ))
        total_cells = cols * rows
        return rects[:total_cells]
