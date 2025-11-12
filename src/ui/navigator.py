"""Navigator component: navigation bar construction and interactions."""
from __future__ import annotations

from typing import Any

from psychopy import visual

from rapm_types import LayoutConfig


class Navigator:
    # =========================================================================
    # CONSTRUCTION
    # =========================================================================

    def __init__(self, layout: LayoutConfig, max_visible_nav: int = 12):
        self.layout = layout
        self.max_visible_nav = max_visible_nav

    # =========================================================================
    # UI CONSTRUCTION (builds visual elements, returns for caller to draw)
    # =========================================================================

    def build_navigation(
        self,
        win: visual.Window,
        items: list[dict],
        answers_dict: dict[str, int],
        current_index: int,
        offset: int,
    ) -> tuple[list[tuple[int, Any, Any]], Any, Any, Any, Any]:
        """Build navigation bar with item buttons and arrow controls.

        Returns:
            (nav_items, left_rect, left_txt, right_rect, right_txt)
            - nav_items: list of (global_index, rect, label) tuples
            - arrow components or None if not needed
        """
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
        if count > 1:
            xs = [x_left + i * span / (count - 1) for i in range(count)]
        else:
            xs = [(x_left + x_right) / 2.0]
        item_w = self.layout['nav_item_w']
        item_h = self.layout['nav_item_h']
        label_h = self.layout['nav_label_height']

        for i, gi in enumerate(visible):
            answered = items[gi]['id'] in answers_dict
            rect = visual.Rect(
                win, width=item_w, height=item_h, pos=(xs[i], nav_y),
                lineColor='yellow' if gi == current_index else 'white', lineWidth=3,
                fillColor=(0, 0.45, 0) if answered else None,
            )
            _raw_id = items[gi]['id'] or ''
            _digits = ''.join([ch for ch in _raw_id if ch.isdigit()])
            _label_txt = str(int(_digits)) if _digits else _raw_id
            label = visual.TextStim(
                win, text=_label_txt, pos=(xs[i], nav_y), height=label_h,
                color='black' if answered else 'white', bold=answered, font=self.layout['font_main']
            )
            stims.append((gi, rect, label))

        left_rect = left_txt = right_rect = right_txt = None
        arrow_h = item_h
        arrow_label_h = self.layout['nav_arrow_label_height']

        if start > 0:
            left_rect = visual.Rect(
                win, width=arrow_w, height=arrow_h, pos=(x_left_edge, nav_y),
                lineColor='white', lineWidth=3, fillColor=(0.15, 0.15, 0.15),
            )
            left_txt = visual.TextStim(
                win, text='◄', pos=(x_left_edge, nav_y), height=arrow_label_h,
                bold=True, font=self.layout['font_main']
            )
        if end < n:
            right_rect = visual.Rect(
                win, width=arrow_w, height=arrow_h, pos=(x_right_edge, nav_y),
                lineColor='white', lineWidth=3, fillColor=(0.15, 0.15, 0.15),
            )
            right_txt = visual.TextStim(
                win, text='►', pos=(x_right_edge, nav_y), height=arrow_label_h,
                bold=True, font=self.layout['font_main']
            )
        return stims, left_rect, left_txt, right_rect, right_txt

    # =========================================================================
    # EVENT HANDLING (processes user interactions)
    # =========================================================================

    def handle_click(
        self,
        win: visual.Window,
        nav_items: list[tuple[int, Any, Any]],
        left_rect: Any,
        right_rect: Any,
        items: list[dict[str, Any]],
        current_index: int,
        nav_offset: int,
        mouse: Any,
    ) -> tuple[str | None, int, int]:
        """Handle mouse clicks on navigation elements (non-blocking).

        Requires caller to manage mouse state and debouncing via edge detection.
        Only checks position (contains), assumes valid click already detected.

        Args:
            mouse: Pre-created Mouse object from caller's event loop.

        Returns:
            (action_type, new_current_index, new_nav_offset)
            action_type: 'page' (arrow click), 'jump' (item click), or None
        """
        # Check for clicks (caller handles debouncing via mouse_just_released)
        if left_rect and left_rect.contains(mouse):
            nav_offset = max(0, nav_offset - self.max_visible_nav)
            return 'page', current_index, nav_offset
        if right_rect and right_rect.contains(mouse):
            max_off = max(0, len(items) - self.max_visible_nav)
            nav_offset = min(max_off, nav_offset + self.max_visible_nav)
            return 'page', current_index, nav_offset
        for gi, rect, label in nav_items:
            if rect.contains(mouse) or label.contains(mouse):
                current_index = gi
                return 'jump', current_index, nav_offset
        return None, current_index, nav_offset

    # =========================================================================
    # UTILITY METHODS (calculation helpers)
    # =========================================================================

    def center_offset(self, index: int, total: int) -> int:
        """Calculate offset to center given index in visible window."""
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

    def find_next_unanswered(
        self,
        items: list[dict[str, Any]],
        answers_dict: dict[str, int],
        current_index: int,
    ) -> int:
        """Find next unanswered item index for auto-advance.

        Logic: If at last item, wrap to first unanswered. Otherwise, find
        next unanswered forward, or just advance by 1 if all are answered.
        """
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
