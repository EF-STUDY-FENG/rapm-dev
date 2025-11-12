"""Renderer: encapsulates all drawing primitives for the RAPM task.

All state (fonts, colors, positions) comes from the injected PsychoPy window
and layout dict. Methods are side-effect only (draw + flip done outside).
"""
from __future__ import annotations

from typing import Any, Sequence

from psychopy import core, event, visual

from path_utils import file_exists_nonempty, fitted_size_keep_aspect, resolve_path
from rapm_types import LayoutConfig


class Renderer:
    # =========================================================================
    # CONSTRUCTION
    # =========================================================================

    def __init__(self, win: visual.Window, layout: LayoutConfig, font_main: str | None = None):
        self.win = win
        self.layout = layout
        # Allow overriding font via argument
        if font_main:
            self.layout['font_main'] = font_main

    # =========================================================================
    # COMPLETE SCREEN FLOWS (show_* methods with internal flip loops)
    # =========================================================================

    def show_instruction(self, text: str, button_text: str, debug_mode: bool) -> None:
        """Blocking: Display instruction screen with timed button.

        Performs internal flip loop until user clicks the button.
        Button becomes clickable after delay (0s in debug, configurable otherwise).
        """
        lines = (text or '').split('\n')
        center_y = self.layout['instruction_center_y']
        line_h = self.layout['instruction_line_height']
        spacing = self.layout['instruction_line_spacing']
        show_start = core.getTime()
        delay = 0.0 if debug_mode else self.layout['instruction_button_delay']

        btn_w = self.layout['button_width']
        btn_h = self.layout['button_height']
        btn_pos = (self.layout['button_x'], self.layout['instruction_button_y'])
        label_h = self.layout['button_label_height']
        line_w = self.layout['button_line_width']

        mouse = event.Mouse(win=self.win)
        clickable = False
        mouse_was_pressed = False  # Edge detection state

        while True:
            elapsed = core.getTime() - show_start
            if not clickable and elapsed >= delay:
                clickable = True

            self.draw_multiline(lines, center_y=center_y, line_height=line_h, spacing=spacing)

            if clickable:
                temp_rect = visual.Rect(
                    self.win,
                    width=btn_w,
                    height=btn_h,
                    pos=btn_pos,
                )
                hovered = temp_rect.contains(mouse)
                fill_col = (
                    self.layout['button_fill_hover']
                    if hovered
                    else self.layout['button_fill_normal']
                )
                outline_col = (
                    self.layout['button_outline_hover']
                    if hovered
                    else self.layout['button_outline_normal']
                )
            else:
                fill_col = self.layout['button_fill_disabled']
                outline_col = self.layout['button_outline_disabled']

            btn_rect = visual.Rect(
                self.win, width=btn_w, height=btn_h, pos=btn_pos,
                lineColor=outline_col, fillColor=fill_col, lineWidth=line_w
            )
            remaining = int(max(0, delay - elapsed))
            label_text = button_text if clickable else f"{button_text} ({remaining}s)"
            btn_label = visual.TextStim(
                self.win, text=label_text, pos=btn_pos, height=label_h,
                color='white', font=self.layout['font_main']
            )
            btn_rect.draw()
            btn_label.draw()
            self.win.flip()

            # Edge detection: only trigger on release
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
        """Blocking: Render completion message for a given duration.

        Performs internal flip loop for the specified duration.
        Defaults match previous hardcoded values in RavenTask.
        """
        if lines is None:
            lines = ['作答完成！', '感谢您的作答！']
        if colors is None:
            colors = ['green', 'white']
        if bold_idx is None:
            bold_idx = {0}
        end_time = core.getTime() + max(0.0, seconds)
        while core.getTime() < end_time:
            self.draw_multiline(
                lines,
                center_y=center_y,
                line_height=line_height,
                spacing=spacing,
                colors=colors,
                bold_idx=bold_idx,
            )
            self.win.flip()

    # =========================================================================
    # ATOMIC DRAWING METHODS (draw_* - no flip, caller manages refresh)
    # =========================================================================

    def draw_header(
        self,
        remaining_seconds: float | None,
        show_threshold: int | None,
        red_threshold: int | None,
        answered_count: int,
        total_count: int,
        show_timer: bool = True,
        show_progress: bool = True,
    ) -> None:
        """Draw header area: timer and/or progress bar."""
        if show_timer and remaining_seconds is not None:
            self.draw_timer(remaining_seconds, show_threshold, red_threshold)
        if show_progress and total_count is not None:
            self.draw_progress(answered_count, total_count)

    def draw_timer(
        self,
        remaining_seconds: float | None,
        show_threshold: int | None,
        red_threshold: int | None,
    ) -> None:
        """Draw countdown timer (hides if above show_threshold)."""
        remaining = max(0, int(remaining_seconds or 0))
        if show_threshold is not None and remaining > show_threshold:
            return
        mins, secs = divmod(remaining, 60)
        timer_text = f"剩余时间: {mins:02d}:{secs:02d}"
        color = 'red' if (red_threshold is not None and remaining <= red_threshold) else 'white'
        visual.TextStim(
            self.win, text=timer_text, pos=(0, self.layout['header_y']),
            height=self.layout['header_font_size'], color=color, font=self.layout['font_main']
        ).draw()

    def draw_progress(self, answered_count: int, total_count: int) -> None:
        """Draw progress indicator (e.g., 'Answered 3 / Total 12')."""
        answered_count = max(0, min(answered_count, total_count))
        txt = f"已答 {answered_count} / 总数 {total_count}"
        color = 'green' if (total_count > 0 and answered_count >= total_count) else 'white'
        y = self.layout['header_y']
        right_edge_x = self.layout['nav_arrow_x_right'] - (self.layout['nav_arrow_w'] / 2.0)
        x = right_edge_x - self.layout['progress_right_margin']
        stim = visual.TextStim(
            self.win, text=txt, pos=(x, y), height=self.layout['header_font_size'],
            color=color, font=self.layout['font_main']
        )
        try:
            stim.anchorHoriz = 'right'
        except Exception:
            pass
        stim.draw()

    def draw_question(self, item_id: str, image_path: str | None) -> None:
        """Draw question image or fallback text."""
        q_w = self.layout['question_box_w'] * self.layout['scale_question']
        q_h = self.layout['question_box_h'] * self.layout['scale_question']
        if image_path and file_exists_nonempty(image_path):
            try:
                max_w = q_w - self.layout['question_img_margin_w']
                max_h = q_h - self.layout['question_img_margin_h']
                disp_w, disp_h = fitted_size_keep_aspect(image_path, max_w, max_h)
                visual.ImageStim(
                    self.win,
                    image=resolve_path(image_path),
                    pos=(0, self.layout['question_box_y']),
                    size=(disp_w, disp_h),
                ).draw()
            except Exception:
                visual.TextStim(
                    self.win,
                    text=f"题目 {item_id}\n(图片加载失败)",
                    pos=(0, self.layout['question_box_y']),
                    height=0.06,
                    font=self.layout['font_main'],
                ).draw()
        else:
            visual.TextStim(
                self.win,
                text=f"题目 {item_id}\n(图片占位)",
                pos=(0, self.layout['question_box_y']),
                height=0.06,
                font=self.layout['font_main'],
            ).draw()

    def draw_options(
        self,
        option_paths: list[str],
        rects: list[Any],
        selected_index: int | None,
    ) -> None:
        """Draw option grid with images or fallback labels."""
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
                    max_w = self.layout['option_img_w'] * self.layout['scale_option']
                    max_h = self.layout['option_img_h'] * self.layout['scale_option']
                    disp_w, disp_h = fitted_size_keep_aspect(path, max_w, max_h)
                    fill = self.layout['option_img_fill']
                    visual.ImageStim(
                        self.win,
                        image=resolve_path(path),
                        pos=rect.pos,
                        size=(disp_w * fill, disp_h * fill),
                    ).draw()
                else:
                    visual.TextStim(
                        self.win, text=str(i+1), pos=rect.pos, height=0.05,
                        color='gray', font=self.layout['font_main']
                    ).draw()

    def draw_submit_button(self) -> Any:
        """Draw submit button (returns rect for hit testing)."""
        btn_pos = (self.layout['button_x'], self.layout['submit_button_y'])
        mouse_local = event.Mouse(win=self.win)
        temp_rect = visual.Rect(
            self.win,
            width=self.layout['button_width'],
            height=self.layout['button_height'],
            pos=btn_pos,
        )
        hovered = temp_rect.contains(mouse_local)
        fill_col = (
            self.layout['button_fill_hover']
            if hovered
            else self.layout['button_fill_normal']
        )
        outline_col = (
            self.layout['button_outline_hover']
            if hovered
            else self.layout['button_outline_normal']
        )
        submit_rect = visual.Rect(
            self.win,
            width=self.layout['button_width'],
            height=self.layout['button_height'],
            pos=btn_pos,
            lineColor=outline_col,
            fillColor=fill_col,
            lineWidth=self.layout['button_line_width'],
        )
        submit_label = visual.TextStim(
            self.win, text='提交作答', pos=btn_pos, height=self.layout['button_label_height'],
            color='white', font=self.layout['font_main']
        )
        submit_rect.draw()
        submit_label.draw()
        return submit_rect

    def draw_multiline(
        self,
        lines: Sequence[str],
        center_y: float,
        line_height: float,
        spacing: float = 1.5,
        colors: list[str] | None = None,
        bold_idx: set[int] | None = None,
        x: float = 0.0,
    ) -> None:
        """Draw centered multi-line text with optional colors and bold lines."""
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
                self.win, text=text or '', pos=(x, y), height=line_height,
                color=color, font=self.layout['font_main']
            )
            try:
                if bold_idx and i in bold_idx:
                    stim.bold = True
            except Exception:
                pass
            stim.draw()

    # =========================================================================
    # UTILITY METHODS (geometry, hit testing)
    # =========================================================================

    def create_option_rects(self) -> list[Any]:
        """Create rect objects for option grid (caller draws them)."""
        cols = int(self.layout['option_cols'])
        rows = int(self.layout['option_rows'])
        dx = self.layout['option_dx']
        dy = self.layout['option_dy']
        rect_w = self.layout['option_rect_w'] * self.layout['scale_option']
        rect_h = self.layout['option_rect_h'] * self.layout['scale_option']
        center_y = self.layout['option_grid_center_y']
        rects: list[Any] = []
        for r in range(rows):
            for c in range(cols):
                x = (c - (cols - 1) / 2) * dx
                y = center_y - (r - (rows - 1) / 2) * dy
                rects.append(visual.Rect(
                    self.win, width=rect_w, height=rect_h, pos=(x, y),
                    lineColor='white', lineWidth=2, fillColor=None
                ))
        total_cells = cols * rows
        return rects[:total_cells]
