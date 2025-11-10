from __future__ import annotations
"""Navigator component: navigation bar construction and interactions."""
from typing import Any, Optional, Tuple, List
from psychopy import visual, event, core

class Navigator:
    def __init__(self, win: visual.Window, layout: dict, max_visible_nav: int = 12):
        self.win = win
        self.layout = layout
        self.max_visible_nav = max_visible_nav

    def build_navigation(
        self,
        items: List[dict],
        answers_dict: dict[str, int],
        current_index: int,
        offset: int,
    ) -> tuple[list[tuple[int, Any, Any]], Any, Any, Any, Any]:
        n = len(items)
        start = offset
        end = min(n, start + self.max_visible_nav)
        visible = list(range(start, end))
        stims = []
        if not visible:
            return stims, None, None, None, None

        count = len(visible)
        nav_y = self.layout['nav_y']
        x_left_edge = self.layout['nav_arrow_x_left']
        x_right_edge = self.layout['nav_arrow_x_right']
        arrow_w = self.layout['nav_arrow_w']
        gap = self.layout['nav_gap']
        x_left = x_left_edge + arrow_w + gap
        x_right = x_right_edge - arrow_w - gap
        span = x_right - x_left
        xs = [x_left + i * span / (count - 1) for i in range(count)] if count > 1 else [(x_left + x_right) / 2.0]
        item_w = self.layout['nav_item_w']
        item_h = self.layout['nav_item_h']
        label_h = self.layout['nav_label_height']

        for i, gi in enumerate(visible):
            answered = items[gi]['id'] in answers_dict
            rect = visual.Rect(
                self.win, width=item_w, height=item_h, pos=(xs[i], nav_y),
                lineColor='yellow' if gi == current_index else 'white', lineWidth=3,
                fillColor=(0, 0.45, 0) if answered else None,
            )
            _raw_id = items[gi]['id'] or ''
            _digits = ''.join([ch for ch in _raw_id if ch.isdigit()])
            _label_txt = str(int(_digits)) if _digits else _raw_id
            label = visual.TextStim(
                self.win, text=_label_txt, pos=(xs[i], nav_y), height=label_h,
                color='black' if answered else 'white', bold=answered, font=self.layout['font_main']
            )
            stims.append((gi, rect, label))

        left_rect = left_txt = right_rect = right_txt = None
        arrow_h = item_h
        arrow_label_h = self.layout['nav_arrow_label_height']

        if start > 0:
            left_rect = visual.Rect(
                self.win, width=arrow_w, height=arrow_h, pos=(x_left_edge, nav_y),
                lineColor='white', lineWidth=3, fillColor=(0.15, 0.15, 0.15),
            )
            left_txt = visual.TextStim(
                self.win, text='◄', pos=(x_left_edge, nav_y), height=arrow_label_h,
                bold=True, font=self.layout['font_main']
            )
        if end < n:
            right_rect = visual.Rect(
                self.win, width=arrow_w, height=arrow_h, pos=(x_right_edge, nav_y),
                lineColor='white', lineWidth=3, fillColor=(0.15, 0.15, 0.15),
            )
            right_txt = visual.TextStim(
                self.win, text='►', pos=(x_right_edge, nav_y), height=arrow_label_h,
                bold=True, font=self.layout['font_main']
            )
        return stims, left_rect, left_txt, right_rect, right_txt

    def handle_click(
        self,
        nav_items: list[tuple[int, Any, Any]],
        left_rect: Any,
        right_rect: Any,
        items: list[dict[str, Any]],
        current_index: int,
        nav_offset: int,
    ) -> tuple[Optional[str], int, int]:
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

    def center_offset(self, index: int, total: int) -> int:
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

    def find_next_unanswered(self, items: list[dict[str, Any]], answers_dict: dict[str, int], current_index: int) -> int:
        n_items = len(items)
        next_index = current_index
        if current_index == n_items - 1:
            for k in range(n_items):
                if items[k]['id'] not in answers_dict:
                    next_index = k
                    break
        else:
            for k in range(current_index + 1, n_items):
                if items[k]['id'] not in answers_dict:
                    next_index = k
                    break
            if next_index == current_index and current_index < n_items - 1:
                next_index += 1
        return next_index
