"""Raven Advanced Reasoning Task (Practice Set I and Formal Set II)

Features:
- Practice Set I: linear progression, auto-advance after selection, 10 min total cap.
- Formal Set II: user can navigate back to previously answered items to modify answers within 40 min cap.
- Navigation strip at the TOP (formal only): clickable item IDs; current highlighted; answered marked.
- Countdown timer near top.
- After last formal item answered: show a persistent Submit button at bottom (does NOT auto-submit).
- Data saved to data/raven_results_YYYYMMDD_HHMMSS.csv upon submit.

Dependencies: psychopy
"""
from psychopy import visual, event, core, gui
try:
    from PIL import Image as PILImage  # for reading image size to preserve aspect ratio
except Exception:
    PILImage = None
import json
import os
import csv
from datetime import datetime

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'configs', 'raven_config.json')
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def file_exists_nonempty(path: str) -> bool:
    try:
        p = resolve_path(path)
        return os.path.isfile(p) and os.path.getsize(p) > 0
    except Exception:
        return False


def resolve_path(p: str) -> str:
    """Resolve a possibly relative path to project root."""
    if os.path.isabs(p):
        return p
    return os.path.join(BASE_DIR, p)


def load_answers(answer_file: str) -> list[int]:
    path = resolve_path(answer_file)
    answers: list[int] = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                answers.append(int(s))
            except ValueError:
                continue
    return answers


# Cache for image sizes to avoid re-opening files each frame
_IMG_SIZE_CACHE: dict[str, tuple[int, int]] = {}


def get_image_pixel_size(path: str) -> tuple[int, int] | None:
    if PILImage is None:
        return None
    abs_path = resolve_path(path)
    if abs_path in _IMG_SIZE_CACHE:
        return _IMG_SIZE_CACHE[abs_path]
    try:
        with PILImage.open(abs_path) as im:
            size = im.size  # (width, height) in pixels
            _IMG_SIZE_CACHE[abs_path] = size
            return size
    except Exception:
        return None


def fitted_size_keep_aspect(path: str, max_w: float, max_h: float) -> tuple[float, float]:
    """Compute display size (norm units) that fits within max box while preserving aspect ratio."""
    px = get_image_pixel_size(path)
    if not px:
        return max_w, max_h
    pw, ph = px
    if pw <= 0 or ph <= 0:
        return max_w, max_h
    img_ratio = pw / ph
    box_ratio = max_w / max_h if max_h > 0 else img_ratio
    if img_ratio >= box_ratio:
        # width-limited
        w = max_w
        h = w / img_ratio
    else:
        # height-limited
        h = max_h
        w = h * img_ratio
    return w, h


def build_items_from_pattern(pattern: str, count: int, answers: list[int], start_index: int, section_prefix: str) -> list[dict]:
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
    def __init__(self, win, config, participant_info=None):
        self.win = win
        self.practice = config['practice']
        self.formal = config['formal']
        self.participant_info = participant_info or {}
        self.practice_answers = {}
        self.formal_answers = {}
        self.in_practice = True
        # Enable debug mode if configured OR if participant_id is "0"
        pid = str(self.participant_info.get('participant_id', '')).strip()
        self.debug_mode = config.get('debug_mode', False) or (pid == '0')
        self.start_time = core.getTime()
        # Deadlines are set right before each section starts (after showing instructions)
        self.practice_deadline = None
        self.formal_deadline = None  # set when formal starts
        self.submit_visible = False
        # navigation state (unified for both practice and formal)
        self.current_index = 0
        self.nav_offset = 0
        self.max_visible_nav = 12
        # Layout tuning (can be overridden in config.layout)
        layout_cfg = config.get('layout', {}) if isinstance(config, dict) else {}
        self.scale_question = float(layout_cfg.get('scale_question', 1.584))  # enlarge question area (1.2 * 1.32)
        self.scale_option = float(layout_cfg.get('scale_option', 0.749))      # options +5% from previous 0.713
        self.nav_y = float(layout_cfg.get('nav_y', 0.90))
        # Unified header (timer + progress) vertical position and font size
        self.header_y = float(layout_cfg.get('header_y', 0.82))
        self.header_font_size = float(layout_cfg.get('header_font_size', 0.04))
        # Navigation arrow placement (used to align progress to right arrow)
        self.nav_arrow_x_right = float(layout_cfg.get('nav_arrow_x_right', 0.98))
        self.nav_arrow_x_left = float(layout_cfg.get('nav_arrow_x_left', -0.98))
        self.nav_arrow_w = float(layout_cfg.get('nav_arrow_w', 0.09))
        self.progress_right_margin = float(layout_cfg.get('progress_right_margin', 0.01))
        self.option_grid_center_y = float(layout_cfg.get('option_grid_center_y', -0.425))
        self.option_cols = int(layout_cfg.get('option_cols', 4))
        self.option_rows = int(layout_cfg.get('option_rows', 2))
        self.dx_base = float(layout_cfg.get('option_dx', 0.45))
        self.dy_base = float(layout_cfg.get('option_dy', 0.45))
        self.option_rect_w_base = float(layout_cfg.get('option_rect_w', 0.4))
        self.option_rect_h_base = float(layout_cfg.get('option_rect_h', 0.35))
        self.option_img_max_w_base = float(layout_cfg.get('option_img_w', 0.36))
        self.option_img_max_h_base = float(layout_cfg.get('option_img_h', 0.28))
        # Option image fill ratio inside rect (0-1). Higher -> fills more, keep some border visible.
        self.option_img_fill = float(layout_cfg.get('option_img_fill', 0.92))
        # Instruction line spacing multiplier
        self.instruction_line_spacing = float(layout_cfg.get('instruction_line_spacing', 1.5))
        # Instruction button delay (seconds) before enabling click
        self.instruction_button_delay = float(layout_cfg.get('instruction_button_delay', 5.0))
        # Instruction screen layout (reduce magic numbers in show_instruction)
        self.instruction_center_y = float(layout_cfg.get('instruction_center_y', 0.15))
        self.instruction_line_height = float(layout_cfg.get('instruction_line_height', 0.055))
        self.instruction_button_width = float(layout_cfg.get('instruction_button_width', 0.52))
        self.instruction_button_height = float(layout_cfg.get('instruction_button_height', 0.14))
        self.instruction_button_x = float(layout_cfg.get('instruction_button_x', 0.0))
        self.instruction_button_y = float(layout_cfg.get('instruction_button_y', -0.38))
        self.instruction_button_label_height = float(layout_cfg.get('instruction_button_label_height', 0.055))
        self.instruction_button_line_width = int(layout_cfg.get('instruction_button_line_width', 4))
        # Instruction button color set (accept lists or strings)
        def _col(name, default):
            val = layout_cfg.get(name, default)
            return val
        self.instruction_button_fill_disabled = _col('instruction_button_fill_disabled', [0.15, 0.15, 0.15])
        self.instruction_button_fill_enabled = _col('instruction_button_fill_enabled', [0, 0.4, 0])
        self.instruction_button_fill_hover = _col('instruction_button_fill_hover', [0, 0.6, 0])
        self.instruction_button_outline_disabled = _col('instruction_button_outline_disabled', [0.5, 0.5, 0.5])
        self.instruction_button_outline_enabled = _col('instruction_button_outline_enabled', [0, 0.8, 0])
        self.instruction_button_outline_hover = _col('instruction_button_outline_hover', 'yellow')
        self.question_box_w_base = float(layout_cfg.get('question_box_w', 1.4))
        self.question_box_h_base = float(layout_cfg.get('question_box_h', 0.5))
        self.question_box_y = float(layout_cfg.get('question_box_y', 0.35))
        self.question_img_margin_w = float(layout_cfg.get('question_img_margin_w', 0.05))
        self.question_img_margin_h = float(layout_cfg.get('question_img_margin_h', 0.05))

        # Timer thresholds (for formal test only; practice always shows and never turns red)
        self.timer_show_threshold = layout_cfg.get('timer_show_threshold', 600)  # Formal: show at 10 min remaining
        self.timer_red_threshold = float(layout_cfg.get('timer_red_threshold', 300))  # Formal: red at 5 min
        # Section-specific override for formal show threshold (optional)
        self.formal_timer_show_threshold = layout_cfg.get('formal_timer_show_threshold', self.timer_show_threshold)
        # Debug mode overrides (apply to both practice and formal)
        self.debug_timer_show_threshold = float(layout_cfg.get('debug_timer_show_threshold', 20))
        self.debug_timer_red_threshold = float(layout_cfg.get('debug_timer_red_threshold', 10))

        # Submit button layout (formal only)
        self.submit_button_width = float(layout_cfg.get('submit_button_width', 0.5))
        self.submit_button_height = float(layout_cfg.get('submit_button_height', 0.12))
        self.submit_button_x = float(layout_cfg.get('submit_button_x', 0.0))
        self.submit_button_y = float(layout_cfg.get('submit_button_y', -0.88))
        self.submit_button_label_height = float(layout_cfg.get('submit_button_label_height', 0.055))
        self.submit_button_line_width = int(layout_cfg.get('submit_button_line_width', 4))
        self.submit_button_fill_normal = _col('submit_button_fill_normal', [0, 0.45, 0])
        self.submit_button_fill_hover = _col('submit_button_fill_hover', [0, 0.6, 0])
        self.submit_button_outline_normal = _col('submit_button_outline_normal', [0, 0.8, 0])
        self.submit_button_outline_hover = _col('submit_button_outline_hover', 'yellow')

        # If config uses patterns + answers, generate items accordingly
        try:
            answers_file = config.get('answers_file')
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

    def run(self):
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
        if self.debug_mode:
            # Debug: 10 seconds for practice
            self.practice_deadline = core.getTime() + 10
        else:
            self.practice_deadline = core.getTime() + self.practice['time_limit_minutes'] * 60
        self.run_practice()
        # Practice finished
        self.in_practice = False
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
        if self.debug_mode:
            # Debug: 25 seconds (show timer at 20s, red at 10s)
            self.formal_deadline = core.getTime() + 25
        else:
            self.formal_deadline = core.getTime() + self.formal['time_limit_minutes'] * 60
        self.run_formal()

    # ---------- Generic drawing helpers ----------
    def draw_timer(self, deadline, show_threshold=None, red_threshold=None):
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

        timerStim = visual.TextStim(self.win, text=timer_text, pos=(0, self.header_y), height=self.header_font_size, color=color)
        timerStim.draw()

    def draw_multiline(self, lines, center_y: float, line_height: float, spacing: float = 1.5,
                       colors: list | None = None, bold_idx: set[int] | None = None,
                       x: float = 0.0):
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
            stim = visual.TextStim(self.win, text=text or '', pos=(x, y), height=line_height, color=color)
            # try bold if available
            try:
                if bold_idx and i in bold_idx:
                    stim.bold = True
            except Exception:
                pass
            stim.draw()

    def draw_progress(self, answered_count: int, total_count: int):
        """Draw answered/total progress indicator at header_y position.

        Green when all answered, white otherwise.
        Right-aligned to navigation arrow with small margin.
        """
        answered_count = max(0, min(answered_count, total_count))
        txt = f"已答 {answered_count} / 总数 {total_count}"
        color = 'green' if total_count > 0 and answered_count >= total_count else 'white'
        # Place at right side on the same height as the timer (i.e., under nav), right-aligned
        y = self.header_y
        # Align progress left edge to the left edge of the right arrow box (with a small margin)
        right_edge_x = self.nav_arrow_x_right - (self.nav_arrow_w / 2.0)
        x = right_edge_x - self.progress_right_margin
        progStim = visual.TextStim(self.win, text=txt, pos=(x, y), height=self.header_font_size, color=color)
        try:
            progStim.anchorHoriz = 'right'
        except Exception:
            pass
        progStim.draw()

    def draw_header(self, deadline, show_threshold, red_threshold, answered_count, total_count,
                    show_timer=True, show_progress=True):
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

    def show_instruction(self, text: str, button_text: str = "继续"):
        """Display centered multi-line instruction with a styled button.
        In normal mode, the button becomes clickable only after self.instruction_button_delay seconds;
        in debug mode, it's clickable immediately (no countdown).
        """
        lines = (text or "").split("\n")
        center_y = self.instruction_center_y
        line_h = self.instruction_line_height
        spacing = self.instruction_line_spacing
        show_start = core.getTime()
        # In debug mode, make the instruction button immediately clickable (no countdown)
        delay = 0.0 if self.debug_mode else self.instruction_button_delay
        btn_w = self.instruction_button_width
        btn_h = self.instruction_button_height
        btn_pos = (self.instruction_button_x, self.instruction_button_y)
        label_h = self.instruction_button_label_height
        line_w = self.instruction_button_line_width
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
                fill_col = self.instruction_button_fill_hover if hovered else self.instruction_button_fill_enabled
                outline_col = self.instruction_button_outline_hover if hovered else self.instruction_button_outline_enabled
            else:
                fill_col = self.instruction_button_fill_disabled
                outline_col = self.instruction_button_outline_disabled

            btn_rect = visual.Rect(self.win, width=btn_w, height=btn_h, pos=btn_pos,
                                    lineColor=outline_col, fillColor=fill_col, lineWidth=line_w)
            remaining = int(max(0, delay - elapsed))
            label_text = button_text if clickable else f"{button_text} ({remaining}s)"
            btn_label = visual.TextStim(self.win, text=label_text, pos=btn_pos, height=label_h, color='white')
            btn_rect.draw(); btn_label.draw()
            self.win.flip()

            if clickable and any(mouse.getPressed()) and btn_rect.contains(mouse):
                while any(mouse.getPressed()):
                    core.wait(0.01)
                break

    def draw_question(self, item_id: str, image_path: str | None):
        # Question area at top center (no border frame)
        q_w = self.question_box_w_base * self.scale_question
        q_h = self.question_box_h_base * self.scale_question
        # Remove the white border box - only draw the image
        if image_path and file_exists_nonempty(image_path):
            try:
                max_w = q_w - self.question_img_margin_w
                max_h = q_h - self.question_img_margin_h
                disp_w, disp_h = fitted_size_keep_aspect(image_path, max_w, max_h)
                img = visual.ImageStim(self.win, image=resolve_path(image_path), pos=(0, self.question_box_y), size=(disp_w, disp_h))
                img.draw()
            except Exception:
                txt = visual.TextStim(self.win, text=f"题目 {item_id}\n(图片加载失败)", pos=(0, self.question_box_y), height=0.06)
                txt.draw()
        else:
            txt = visual.TextStim(self.win, text=f"题目 {item_id}\n(图片占位)", pos=(0, self.question_box_y), height=0.06)
            txt.draw()

    def create_option_rects(self):
        rects = []
        # Use absolute spacing so shrinking options doesn't make grid too tight
        dx = self.dx_base
        dy = self.dy_base
        cols = self.option_cols
        rows = self.option_rows
        total_w = dx * (cols - 1)
        left = - total_w / 2.0
        center_y = self.option_grid_center_y
        rect_w = self.option_rect_w_base * self.scale_option
        rect_h = self.option_rect_h_base * self.scale_option
        for i in range(8):
            c = i % cols
            r = i // cols
            x = left + c * dx
            y = center_y + ((rows - 1) / 2.0 - r) * dy
            rect = visual.Rect(self.win, width=rect_w, height=rect_h, pos=(x, y), lineColor='white', fillColor=None)
            # No numeric labels on options; keep placeholder None for compatibility
            rects.append((rect, None))
        return rects

    def draw_options(self, option_paths, rects, selected_index=None):
        """Draw option rectangles; highlight selected with thicker yellow border."""
        for idx, (rect, _label) in enumerate(rects):
            # highlight previously selected
            if selected_index is not None and idx == selected_index:
                rect.lineColor = 'yellow'
                rect.lineWidth = 6
            else:
                rect.lineColor = 'white'
                rect.lineWidth = 2
            if idx < len(option_paths) and file_exists_nonempty(option_paths[idx]):
                try:
                    # Fill image up to configured ratio of rect size, preserving aspect ratio
                    ratio = max(0.5, min(self.option_img_fill, 0.98))
                    max_w = rect.width * ratio
                    max_h = rect.height * ratio
                    disp_w, disp_h = fitted_size_keep_aspect(option_paths[idx], max_w, max_h)
                    img = visual.ImageStim(self.win, image=resolve_path(option_paths[idx]), pos=rect.pos, size=(disp_w, disp_h))
                    img.draw()
                except Exception:
                    pass
            rect.draw()

    def detect_click_on_rects(self, rects):
        mouse = event.Mouse(win=self.win)
        if any(mouse.getPressed()):
            for idx, (rect, _) in enumerate(rects):
                if rect.contains(mouse):
                    while any(mouse.getPressed()):
                        core.wait(0.01)
                    return idx
        return None

    # ---------- Shared test flow logic ----------
    def _get_section_config(self, section: str):
        """Get configuration for a test section.

        Args:
            section: 'practice' or 'formal'

        Returns:
            dict with keys: config, answers, deadline, show_submit, auto_save_on_timeout,
                           timer_show_threshold, timer_red_threshold
        """
        if section == 'practice':
            # Practice: timer always visible, never turns red (unless debug mode)
            if self.debug_mode:
                show_t = self.debug_timer_show_threshold
                red_t = self.debug_timer_red_threshold
            else:
                show_t = None  # Always show
                red_t = None   # Never turn red

            return {
                'config': self.practice,
                'answers': self.practice_answers,
                'deadline': self.practice_deadline,
                'show_submit': False,
                'auto_save_on_timeout': False,
                'timer_show_threshold': show_t,
                'timer_red_threshold': red_t,
            }
        else:  # formal
            # Formal: configurable thresholds
            if self.debug_mode:
                show_t = self.debug_timer_show_threshold
                red_t = self.debug_timer_red_threshold
            else:
                show_t = self.formal_timer_show_threshold  # Default 600 (10 min)
                red_t = self.timer_red_threshold  # Default 300 (5 min)

            return {
                'config': self.formal,
                'answers': self.formal_answers,
                'deadline': self.formal_deadline,
                'show_submit': True,
                'auto_save_on_timeout': True,
                'timer_show_threshold': show_t,
                'timer_red_threshold': red_t,
            }

    def _find_next_unanswered(self, items, answers_dict, current_index):
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

    def _run_test_section(self, section: str):
        """Unified test flow for both practice and formal sections.

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

        # Main loop
        while core.getTime() < deadline:
            item = items[self.current_index]

            # Draw navigation bar
            nav_items, l_rect, l_txt, r_rect, r_txt = self._build_navigation(
                items, answers, self.current_index, self.nav_offset)
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
                    self.save_and_exit()
                    return

            # Handle option click
            choice = self.detect_click_on_rects(rects)
            if choice is not None:
                answers[item['id']] = choice + 1
                # Check if all answered
                if len(answers) == n_items:
                    if section == 'practice':
                        break  # Exit practice loop
                    # For formal, stay in loop to show submit button
                else:
                    # Find next unanswered item
                    next_index = self._find_next_unanswered(items, answers, self.current_index)
                    self.current_index = next_index
                    self.nav_offset = self._center_offset(next_index, n_items)
                continue

            # Handle navigation click
            nav_action = self._handle_navigation_click(nav_items, l_rect, r_rect, section)
            if nav_action == 'jump':
                # center only when direct jump
                self.nav_offset = self._center_offset(self.current_index, n_items)
                continue
            if nav_action == 'page':
                # page only moved the visible window; keep current index unchanged
                continue

            # Check timeout
            if core.getTime() >= deadline:
                break

        # Handle timeout
        if cfg['auto_save_on_timeout']:
            self.save_and_exit()

    def _draw_submit_button(self):
        """Draw the submit button and return the rect for click detection.

        Returns:
            visual.Rect: The submit button rectangle for click detection
        """
        btn_pos = (self.submit_button_x, self.submit_button_y)
        mouse_local = event.Mouse(win=self.win)
        temp_rect = visual.Rect(self.win, width=self.submit_button_width,
                               height=self.submit_button_height, pos=btn_pos)
        hovered = temp_rect.contains(mouse_local)

        fill_col = self.submit_button_fill_hover if hovered else self.submit_button_fill_normal
        outline_col = self.submit_button_outline_hover if hovered else self.submit_button_outline_normal

        submit_rect = visual.Rect(self.win, width=self.submit_button_width,
                                 height=self.submit_button_height, pos=btn_pos,
                                 lineColor=outline_col, fillColor=fill_col,
                                 lineWidth=self.submit_button_line_width)
        submit_label = visual.TextStim(self.win, text='提交作答', pos=btn_pos,
                                      height=self.submit_button_label_height, color='white')
        submit_rect.draw()
        submit_label.draw()
        return submit_rect

    # ---------- Practice and Formal wrappers ----------
    def run_practice(self):
        self.current_index = 0
        self.nav_offset = 0
        self._run_test_section('practice')

    def run_formal(self):
        # Reset navigation so formal starts from the first item
        self.current_index = 0
        self.nav_offset = 0
        self._run_test_section('formal')

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

    def _build_navigation(self, items, answers_dict, current_index, offset):
        n = len(items)
        stims = []
        start = offset
        end = min(n, start + self.max_visible_nav)
        visible = list(range(start, end))
        if not visible:
            return stims, None, None, None, None
        count = len(visible)
        # Reserve horizontal space between left/right arrows according to configured positions/width
        x_left = self.nav_arrow_x_left + self.nav_arrow_w
        x_right = self.nav_arrow_x_right - self.nav_arrow_w
        span = x_right - x_left
        xs = [x_left + i * span / (count - 1) for i in range(count)] if count > 1 else [0.0]
        for i, gi in enumerate(visible):
            answered = items[gi]['id'] in answers_dict
            rect = visual.Rect(self.win, width=0.11, height=0.07, pos=(xs[i], self.nav_y),
                               lineColor='yellow' if gi == current_index else 'white',
                               lineWidth=3,
                               fillColor=(0, 0.45, 0) if answered else None)
            label = visual.TextStim(self.win, text=items[gi]['id'], pos=(xs[i], self.nav_y), height=0.036,
                                    color='black' if answered else 'white', bold=answered)
            stims.append((gi, rect, label))
        left_rect = left_txt = right_rect = right_txt = None
        if start > 0:
            left_rect = visual.Rect(self.win, width=self.nav_arrow_w, height=0.07, pos=(self.nav_arrow_x_left, self.nav_y),
                                    lineColor='white', lineWidth=3, fillColor=(0.15, 0.15, 0.15))
            left_txt = visual.TextStim(self.win, text='◄', pos=(self.nav_arrow_x_left, self.nav_y), height=0.05, bold=True)
        if end < n:
            right_rect = visual.Rect(self.win, width=self.nav_arrow_w, height=0.07, pos=(self.nav_arrow_x_right, self.nav_y),
                                     lineColor='white', lineWidth=3, fillColor=(0.15, 0.15, 0.15))
            right_txt = visual.TextStim(self.win, text='►', pos=(self.nav_arrow_x_right, self.nav_y), height=0.05, bold=True)
        return stims, left_rect, left_txt, right_rect, right_txt

    def _handle_navigation_click(self, nav_items, left_rect, right_rect, section: str):
        mouse = event.Mouse(win=self.win)
        if any(mouse.getPressed()):
            if left_rect and left_rect.contains(mouse):
                while any(mouse.getPressed()): core.wait(0.01)
                self.nav_offset = max(0, self.nav_offset - self.max_visible_nav)
                return 'page'
            if right_rect and right_rect.contains(mouse):
                while any(mouse.getPressed()): core.wait(0.01)
                items = self.formal['items'] if section == 'formal' else self.practice['items']
                max_off = max(0, len(items) - self.max_visible_nav)
                self.nav_offset = min(max_off, self.nav_offset + self.max_visible_nav)
                return 'page'
            for gi, rect, label in nav_items:
                if rect.contains(mouse) or label.contains(mouse):
                    while any(mouse.getPressed()): core.wait(0.01)
                    self.current_index = gi
                    items = self.formal['items'] if section == 'formal' else self.practice['items']
                    self.nav_offset = self._center_offset(self.current_index, len(items))
                    return 'jump'
        return None

    # ---------- End states ----------
    def save_and_exit(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_path = os.path.join(DATA_DIR, f'raven_results_{ts}.csv')
        # write CSV answers with correctness info
        pid = self.participant_info.get('participant_id', '')
        tnow = datetime.now().isoformat(timespec='seconds')
        practice_correct = 0
        formal_correct = 0
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['participant_id', 'section', 'item_id', 'answer', 'correct', 'is_correct', 'timestamp'])
            # practice items
            for item in self.practice.get('items', []):
                iid = item.get('id')
                ans = self.practice_answers.get(iid)
                correct = item.get('correct')
                is_correct = (ans == correct) if (ans is not None and correct is not None) else None
                if is_correct:
                    practice_correct += 1
                writer.writerow([pid, 'practice', iid, ans if ans is not None else '', correct if correct is not None else '', '1' if is_correct else ('0' if is_correct is not None else ''), tnow])
            # formal items
            for item in self.formal.get('items', []):
                iid = item.get('id')
                ans = self.formal_answers.get(iid)
                correct = item.get('correct')
                is_correct = (ans == correct) if (ans is not None and correct is not None) else None
                if is_correct:
                    formal_correct += 1
                writer.writerow([pid, 'formal', iid, ans if ans is not None else '', correct if correct is not None else '', '1' if is_correct else ('0' if is_correct is not None else ''), tnow])
        # write a metadata json as well
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
        # Display final completion message (two lines, 1.5x line spacing) via unified helper
        lines = ['作答完成！', '感谢您的作答！']
        colors = ['green', 'white']
        for _ in range(300):  # ~5s
            self.draw_multiline(lines, center_y=0.05, line_height=0.065, spacing=1.5,
                                colors=colors, bold_idx={0})
            self.win.flip()


def load_config(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_participant_info():
    default = {
        'participant_id': '',
        'age': '',
        'gender': '',
        'session': 'S1',
        'notes': ''
    }
    while True:
        dlg = gui.DlgFromDict(default, title='被试信息', order=['participant_id', 'age', 'gender', 'session', 'notes'])
        if not dlg.OK:
            return None
        pid = (default.get('participant_id') or '').strip()
        if pid:
            return default
        # prompt and loop again
        gui.Dlg(title='提示', labelButtonOK='确定').addText('需要填写被试编号 (participant_id)').show()


def detect_screen_resolution():
    """
    Detect the primary screen resolution.
    Returns (width, height) tuple or None if detection fails.
    """
    try:
        # Try using PsychoPy's built-in monitor info first
        from psychopy import monitors
        mon_names = monitors.getAllMonitors()
        if mon_names:
            mon = monitors.Monitor(mon_names[0])
            size = mon.getSizePix()
            if size and len(size) >= 2 and size[0] > 0:
                return int(size[0]), int(size[1])
    except Exception:
        pass

    # Fallback: try tkinter
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        root.destroy()
        if width > 0 and height > 0:
            return width, height
    except Exception:
        pass

    return None


def suggest_layout_for_resolution(width, height):
    """
    Generate suggested layout parameters based on screen resolution.

    Args:
        width: screen width in pixels
        height: screen height in pixels

    Returns:
        dict with layout parameters
    """
    aspect_ratio = width / height if height > 0 else 1.0

    # Base suggestions (updated: question +32%, options -~20% from original baseline, with +10% tweak)
    layout = {
        "scale_question": 1.584,
        "scale_option": 0.749,  # baseline options enlarged additional ~5%
        "nav_y": 0.90,
        "header_y": 0.82,
        "option_grid_center_y": -0.425
    }

    # Adjust for different screen sizes
    # High resolution (>1920px width): can use larger elements
    if width >= 2560:
        layout["scale_question"] = 1.848  # unchanged question high-res
        layout["scale_option"] = 0.832    # 0.792 * 1.05
    elif width >= 1920:
        layout["scale_question"] = 1.716
        layout["scale_option"] = 0.79    # 0.752 * 1.05
    elif width < 1280:
        # Small screen: reduce sizes while keeping slight enlargement
        layout["scale_question"] = 1.32
        layout["scale_option"] = 0.665   # 0.633 * 1.05
        layout["option_grid_center_y"] = -0.35

    # Adjust for ultra-wide screens (aspect ratio > 2.0)
        if aspect_ratio > 2.0:
            layout["option_grid_center_y"] = -0.3
        elif aspect_ratio < 1.3:
            # Adjust for narrow/portrait screens
            layout["nav_y"] = 0.92
            layout["header_y"] = 0.85
            layout["option_grid_center_y"] = -0.5

    return layout


def update_config_with_layout(config_path, layout_params):
    """
    Update the config file with suggested layout parameters.
    Creates a backup of the original config.
    """
    # Read existing config
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # Backup original if layout section exists
    if 'layout' in config:
        backup_path = config_path + '.backup'
        if not os.path.exists(backup_path):
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

    # Update layout section
    config['layout'] = layout_params

    # Write updated config
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    return config


def check_and_suggest_layout(config_path):
    """
    Check screen resolution and suggest layout if needed.
    Returns updated config.
    """
    resolution = detect_screen_resolution()

    if resolution:
        width, height = resolution
        print(f"检测到屏幕分辨率: {width}x{height}")

        # Check if config has layout section
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        if 'layout' not in config or not config['layout']:
            # No layout configured, suggest one
            print("配置文件中未找到布局设置，正在生成建议参数...")
            suggested = suggest_layout_for_resolution(width, height)
            print(f"建议的布局参数:\n{json.dumps(suggested, indent=2, ensure_ascii=False)}")

            # Ask user if they want to apply
            dlg = gui.Dlg(title='布局建议')
            dlg.addText(f'检测到屏幕分辨率: {width}x{height}')
            dlg.addText(f'建议应用自动优化的布局参数')
            dlg.addText(f'scale_question: {suggested["scale_question"]}')
            dlg.addText(f'scale_option: {suggested["scale_option"]}')
            dlg.addField('应用建议布局?', initial=True)
            result = dlg.show()

            if dlg.OK and result and result[0]:
                config = update_config_with_layout(config_path, suggested)
                print("✓ 已将建议布局参数写入配置文件")
            else:
                print("已跳过布局优化")
        else:
            print(f"配置文件已包含布局设置，使用现有配置")
    else:
        print("无法检测屏幕分辨率，使用配置文件中的默认布局")
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

    return config


def main():
    # Check and suggest layout based on screen resolution
    config = check_and_suggest_layout(CONFIG_PATH)

    # Retry loop for participant info
    while True:
        info = get_participant_info()
        if info is None:
            confirm = gui.Dlg(title='确认退出？', labelButtonOK='重试', labelButtonCancel='退出')
            confirm.addText('未填写信息或已取消。是否重新输入？')
            confirm.show()
            if confirm.OK:
                continue
            else:
                return
        break
    # Determine debug flag before creating the window
    pid_str = str((info or {}).get('participant_id', '')).strip()
    debug_active = bool(config.get('debug_mode', False) or (pid_str == '0'))

    # In non-debug mode run fullscreen; in debug mode use a window for convenience
    if debug_active:
        win = visual.Window(size=(1280, 800), color='black', units='norm')
    else:
        win = visual.Window(fullscr=True, color='black', units='norm')
    task = RavenTask(win, config, participant_info=info)
    task.run()
    win.close()
    core.quit()

if __name__ == '__main__':
    main()
