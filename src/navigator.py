"""Navigator: builds and handles navigation bar interactions.

This component manages the navigation bar UI with memory-optimized object pooling:
- Lazy initialization: creates visual objects only when first needed
- Object reuse: reconfigures existing objects instead of creating new ones
- Event handling: processes mouse interactions (non-blocking, caller manages debouncing)
"""
from __future__ import annotations

from typing import Any

from psychopy import visual

from rapm_types import LayoutConfig


class Navigator:
    """Manages navigation bar construction and interaction handling.

    Architecture:
    - __init__: Declares lazy-init placeholders (no visual objects yet)
    - build_navigation: Constructs button/arrow visuals (reuses objects after first call)
    - handle_click: Processes mouse interactions (non-blocking)
    - Helper methods: Configure individual buttons and arrows
    """

    def __init__(self, layout: LayoutConfig, max_visible_nav: int = 12) -> None:
        """Initialize navigator with configuration (visual objects created lazily).

        Args:
            layout: Layout configuration dictionary
            max_visible_nav: Maximum number of visible navigation buttons
        """
        self._layout = layout
        self._max_visible_nav = max_visible_nav

        self._nav_rects = None
        self._nav_labels = None
        self._left_arrow_rect = None
        self._left_arrow_label = None
        self._right_arrow_rect = None
        self._right_arrow_label = None
        self._initialized_win = None

    def _ensure_initialized(self, win: visual.Window) -> None:
        """Lazy initialization: create reusable visual objects on first use.

        This prevents memory leaks by reusing objects instead of creating new ones
        every frame. Objects are created once per window and then reconfigured.

        Args:
            win: PsychoPy window to bind visual objects to
        """
        if self._nav_rects is not None and self._initialized_win == win:
            return

        self._nav_rects = [
            visual.Rect(win, width=0, height=0) for _ in range(self._max_visible_nav)
        ]
        self._nav_labels = [
            visual.TextStim(win, text='', font=self._layout['font_main'])
            for _ in range(self._max_visible_nav)
        ]

        self._left_arrow_rect = visual.Rect(win, width=0, height=0)
        self._left_arrow_label = visual.TextStim(
            win, text='◄', font=self._layout['font_main']
        )
        self._right_arrow_rect = visual.Rect(win, width=0, height=0)
        self._right_arrow_label = visual.TextStim(
            win, text='►', font=self._layout['font_main']
        )

        self._initialized_win = win

    def build_navigation(
        self,
        win: visual.Window,
        items: list[dict],
        answers_dict: dict[str, int],
        current_index: int,
        offset: int,
    ) -> tuple[list[tuple[int, Any, Any]], Any, Any, Any, Any]:
        """Build navigation bar with item buttons and pagination arrows.

        Lazily initializes visual objects on first call, then reuses them.
        Configures visible range based on offset and max_visible_nav.

        Args:
            win: PsychoPy window for object binding
            items: List of item dictionaries (must have 'id' key)
            answers_dict: Mapping of item_id -> answer (determines button styling)
            current_index: Index of currently displayed item (highlighted)
            offset: Starting index for visible button range

        Returns:
            Tuple of (nav_items, left_rect, left_txt, right_rect, right_txt):
            - nav_items: List of (global_index, rect, label) tuples for visible buttons
            - left/right rect/txt: Arrow components (None if pagination not needed)
        """
        self._ensure_initialized(win)

        # Calculate visible button range
        n = len(items)
        start = offset
        end = min(n, start + self._max_visible_nav)
        visible = list(range(start, end))
        stims = []
        if not visible:
            return stims, None, None, None, None

        # Calculate button positions (evenly spaced between arrows)
        layout = self._layout
        count = len(visible)
        nav_y = layout['nav_y']
        x_left_edge = layout['nav_arrow_x_left']
        x_right_edge = layout['nav_arrow_x_right']
        arrow_w = layout['nav_arrow_w']
        gap = layout['nav_gap']
        x_left = x_left_edge + arrow_w + gap
        x_right = x_right_edge - arrow_w - gap
        span = x_right - x_left
        if count > 1:
            xs = [x_left + i * span / (count - 1) for i in range(count)]
        else:
            xs = [(x_left + x_right) / 2.0]
        item_w = layout['nav_item_w']
        item_h = layout['nav_item_h']
        label_h = layout['nav_label_height']

        # Configure navigation buttons (reuses pre-created objects)
        for i, gi in enumerate(visible):
            is_answered = items[gi]['id'] in answers_dict
            is_current = (gi == current_index)

            rect, label = self._configure_nav_button(
                i, gi, items[gi]['id'],
                xs[i], nav_y, item_w, item_h, label_h,
                is_answered, is_current
            )
            stims.append((gi, rect, label))

        # Configure pagination arrows (if needed)
        arrow_h = item_h
        arrow_label_h = layout['nav_arrow_label_height']

        left_rect = left_txt = None
        if start > 0:
            left_rect, left_txt = self._configure_arrow(
                self._left_arrow_rect, self._left_arrow_label,
                x_left_edge, nav_y, arrow_w, arrow_h, arrow_label_h
            )

        right_rect = right_txt = None
        if end < n:
            right_rect, right_txt = self._configure_arrow(
                self._right_arrow_rect, self._right_arrow_label,
                x_right_edge, nav_y, arrow_w, arrow_h, arrow_label_h
            )

        return stims, left_rect, left_txt, right_rect, right_txt

    def _configure_nav_button(
        self,
        index: int,
        global_index: int,
        item_id: str,
        x: float,
        y: float,
        width: float,
        height: float,
        label_height: float,
        is_answered: bool,
        is_current: bool,
    ) -> tuple[Any, Any]:
        """Configure navigation button appearance (updates existing objects).

        Styling rules:
        - Current item: yellow border, width 3
        - Answered item: green fill, black bold text
        - Unanswered item: no fill, white normal text

        Args:
            index: Position in visible navigation list (0 to max_visible_nav-1)
            global_index: Global item index in full item list
            item_id: Item identifier string
            x, y: Button center position
            width, height: Button dimensions
            label_height: Text height
            is_answered: Whether this item has been answered
            is_current: Whether this is the currently displayed item

        Returns:
            (rect, label) tuple of configured visual objects
        """
        # Configure button rectangle
        rect = self._nav_rects[index]
        rect.width = width
        rect.height = height
        rect.pos = (x, y)
        rect.lineColor = 'yellow' if is_current else 'white'
        rect.lineWidth = 3
        rect.fillColor = (0, 0.45, 0) if is_answered else None

        # Update label text and appearance
        # Extract numeric ID from item_id (e.g., 'item_05' -> '5')
        digits = ''.join([ch for ch in (item_id or '') if ch.isdigit()])
        label_text = str(int(digits)) if digits else item_id

        label = self._nav_labels[index]
        label.text = label_text
        label.pos = (x, y)
        label.height = label_height
        label.color = 'black' if is_answered else 'white'
        label.bold = is_answered

        return rect, label

    def _configure_arrow(
        self,
        arrow_rect: Any,
        arrow_label: Any,
        x: float,
        y: float,
        width: float,
        height: float,
        label_height: float,
    ) -> tuple[Any, Any]:
        """Configure pagination arrow appearance (updates existing objects).

        Styling: white border (width 3), no fill, white label (◄ or ►).

        Args:
            arrow_rect: Pre-created rectangle object to update
            arrow_label: Pre-created label object to update
            x, y: Arrow center position
            width, height: Arrow button dimensions
            label_height: Text height

        Returns:
            (rect, label) tuple of configured visual objects
        """
        arrow_rect.width = width
        arrow_rect.height = height
        arrow_rect.pos = (x, y)
        arrow_rect.lineColor = 'white'
        arrow_rect.lineWidth = 3
        arrow_rect.fillColor = None

        arrow_label.pos = (x, y)
        arrow_label.height = label_height
        arrow_label.color = 'white'

        return arrow_rect, arrow_label

    # =========================================================================
    # PUBLIC UTILITIES (navigation calculation helpers)
    # =========================================================================

    def center_offset(self, index: int, total: int) -> int:
        """Calculate pagination offset to center given index in visible window.

        Args:
            index: Item index to center
            total: Total number of items

        Returns:
            Pagination offset (clamped to valid range)
        """
        if total <= self._max_visible_nav:
            return 0
        half = self._max_visible_nav // 2
        offset = index - half
        if offset < 0:
            offset = 0
        max_off = total - self._max_visible_nav
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

        Strategy: If at last item, wrap to first unanswered. Otherwise,
        search forward for next unanswered item, or advance by 1 if all answered.

        Args:
            items: Full item list
            answers_dict: Mapping of item_id -> answer
            current_index: Current item index

        Returns:
            Next item index to navigate to
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

    # =========================================================================
    # EVENT HANDLING (processes user interactions)
    # =========================================================================

    def handle_click(
        self,
        nav_items: list[tuple[int, Any, Any]],
        left_rect: Any,
        right_rect: Any,
        items: list[dict[str, Any]],
        current_index: int,
        nav_offset: int,
        mouse: Any,
    ) -> tuple[str | None, int, int]:
        """Process mouse click on navigation elements (non-blocking).

        Caller manages mouse state and edge detection (debouncing).
        This method only performs hit testing and computes new state.

        Args:
            nav_items: List of (global_index, rect, label) from build_navigation
            left_rect: Left arrow rectangle (None if not visible)
            right_rect: Right arrow rectangle (None if not visible)
            items: Full item list
            current_index: Currently displayed item index
            nav_offset: Current pagination offset
            mouse: Pre-created Mouse object with current state

        Returns:
            (action_type, new_current_index, new_nav_offset) where:
            - action_type: 'page' (arrow), 'jump' (button), or None (no hit)
            - new_current_index: Updated current item index
            - new_nav_offset: Updated pagination offset
        """
        # Check for clicks (caller handles debouncing via mouse_just_released)
        if left_rect and left_rect.contains(mouse):
            nav_offset = max(0, nav_offset - self._max_visible_nav)
            return 'page', current_index, nav_offset
        if right_rect and right_rect.contains(mouse):
            max_off = max(0, len(items) - self._max_visible_nav)
            nav_offset = min(max_off, nav_offset + self._max_visible_nav)
            return 'page', current_index, nav_offset
        for gi, rect, label in nav_items:
            if rect.contains(mouse) or label.contains(mouse):
                current_index = gi
                return 'jump', current_index, nav_offset
        return None, current_index, nav_offset
