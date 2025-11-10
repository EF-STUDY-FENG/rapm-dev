from __future__ import annotations
"""Renderer component: all drawing logic for RavenTask.

Public methods are intentionally minimal; all state comes from injected
PsychoPy window and layout dict.
"""
from typing import Any, Optional, Sequence, Set, List
from psychopy import visual, event, core
from path_utils import resolve_path, file_exists_nonempty, fitted_size_keep_aspect

class Renderer:
    def __init__(self, win: visual.Window, layout: dict, font_main: Optional[str] = None):
        self.win = win
        self.layout = layout
        # Allow overriding font if needed
        if font_main:
            self.layout['font_main'] = font_main

    # Instruction screen -----------------------------------------------------
    def show_instruction(self, text: str, button_text: str, debug_mode: bool) -> None:
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
        while True:
            elapsed = core.getTime() - show_start
            if not clickable and elapsed >= delay:
                clickable = True

            self.draw_multiline(lines, center_y=center_y, line_height=line_h, spacing=spacing)

            if clickable:
                temp_rect = visual.Rect(self.win, width=btn_w, height=btn_h, pos=btn_pos)
                hovered = temp_rect.contains(mouse)
                fill_col = self.layout['button_fill_hover'] if hovered else self.layout['button_fill_normal']
                outline_col = self.layout['button_outline_hover'] if hovered else self.layout['button_outline_normal']
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
            btn_rect.draw(); btn_label.draw(); self.win.flip()
            if clickable and any(mouse.getPressed()) and btn_rect.contains(mouse):
                while any(mouse.getPressed()):
                    core.wait(0.01)
                break

    # Header / timer / progress ----------------------------------------------
    def draw_header(self, deadline: Optional[float], show_threshold: Optional[int], red_threshold: Optional[int],
                    answered_count: int, total_count: int, show_timer: bool = True, show_progress: bool = True) -> None:
        if show_timer and deadline is not None:
            self.draw_timer(deadline, show_threshold, red_threshold)
        if show_progress and total_count is not None:
            self.draw_progress(answered_count, total_count)

    def draw_timer(self, deadline: Optional[float], show_threshold: Optional[int], red_threshold: Optional[int]) -> None:
        remaining = max(0, int(deadline - core.getTime()))
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
        try: stim.anchorHoriz = 'right'
        except Exception: pass
        stim.draw()

    # Multiline ---------------------------------------------------------------
    def draw_multiline(self, lines: Sequence[str], center_y: float, line_height: float, spacing: float = 1.5,
                       colors: Optional[List[str]] = None, bold_idx: Optional[Set[int]] = None, x: float = 0.0) -> None:
        lines = list(lines or [])
        n = len(lines)
        if n == 0: return
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
                if bold_idx and i in bold_idx: stim.bold = True
            except Exception: pass
            stim.draw()

    # Question & options ------------------------------------------------------
    def draw_question(self, item_id: str, image_path: Optional[str]) -> None:
        q_w = self.layout['question_box_w'] * self.layout['scale_question']
        q_h = self.layout['question_box_h'] * self.layout['scale_question']
        if image_path and file_exists_nonempty(image_path):
            try:
                max_w = q_w - self.layout['question_img_margin_w']
                max_h = q_h - self.layout['question_img_margin_h']
                disp_w, disp_h = fitted_size_keep_aspect(image_path, max_w, max_h)
                visual.ImageStim(
                    self.win, image=resolve_path(image_path), pos=(0, self.layout['question_box_y']),
                    size=(disp_w, disp_h)
                ).draw()
            except Exception:
                visual.TextStim(
                    self.win, text=f"题目 {item_id}\n(图片加载失败)", pos=(0, self.layout['question_box_y']),
                    height=0.06, font=self.layout['font_main']
                ).draw()
        else:
            visual.TextStim(
                self.win, text=f"题目 {item_id}\n(图片占位)", pos=(0, self.layout['question_box_y']),
                height=0.06, font=self.layout['font_main']
            ).draw()

    def create_option_rects(self) -> list[Any]:
        cols = int(self.layout['option_cols']); rows = int(self.layout['option_rows'])
        dx = self.layout['option_dx']; dy = self.layout['option_dy']
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

    def draw_options(self, option_paths: list[str], rects: list[Any], selected_index: Optional[int]) -> None:
        for i, rect in enumerate(rects):
            if selected_index is not None and i == selected_index:
                rect.lineColor = 'yellow'; rect.lineWidth = 4; rect.fillColor = (0, 0.45, 0)
            else:
                rect.lineColor = 'white'; rect.lineWidth = 2; rect.fillColor = None
            rect.draw()
            if i < len(option_paths):
                path = option_paths[i]
                if path and file_exists_nonempty(path):
                    max_w = self.layout['option_img_w'] * self.layout['scale_option']
                    max_h = self.layout['option_img_h'] * self.layout['scale_option']
                    disp_w, disp_h = fitted_size_keep_aspect(path, max_w, max_h)
                    visual.ImageStim(
                        self.win, image=resolve_path(path), pos=rect.pos,
                        size=(disp_w * self.layout['option_img_fill'], disp_h * self.layout['option_img_fill'])
                    ).draw()
                else:
                    visual.TextStim(
                        self.win, text=str(i+1), pos=rect.pos, height=0.05,
                        color='gray', font=self.layout['font_main']
                    ).draw()

    def draw_submit_button(self) -> Any:
        btn_pos = (self.layout['button_x'], self.layout['submit_button_y'])
        mouse_local = event.Mouse(win=self.win)
        temp_rect = visual.Rect(self.win, width=self.layout['button_width'], height=self.layout['button_height'], pos=btn_pos)
        hovered = temp_rect.contains(mouse_local)
        fill_col = self.layout['button_fill_hover'] if hovered else self.layout['button_fill_normal']
        outline_col = self.layout['button_outline_hover'] if hovered else self.layout['button_outline_normal']
        submit_rect = visual.Rect(
            self.win, width=self.layout['button_width'], height=self.layout['button_height'], pos=btn_pos,
            lineColor=outline_col, fillColor=fill_col, lineWidth=self.layout['button_line_width']
        )
        submit_label = visual.TextStim(
            self.win, text='提交作答', pos=btn_pos, height=self.layout['button_label_height'],
            color='white', font=self.layout['font_main']
        )
        submit_rect.draw(); submit_label.draw(); return submit_rect

    # Click detection for option rects ---------------------------------------
    def detect_click_on_rects(self, rects: list[Any]) -> Optional[int]:
        mouse = event.Mouse(win=self.win)
        if not any(mouse.getPressed()): return None
        for i, rect in enumerate(rects):
            if rect.contains(mouse):
                while any(mouse.getPressed()): core.wait(0.01)
                return i
        return None
