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
import sys
from datetime import datetime

def _get_base_dir() -> str:
    """Return base directory for read-only resources (configs/stimuli).

    Note: In PyInstaller onefile, resources are unpacked to a temporary
    extraction directory (sys._MEIPASS). That location is read-only and may be
    deleted after exit, so DO NOT write output files there.
    """
    try:
        # PyInstaller onefile provides a temporary extraction dir
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass and os.path.isdir(meipass):
            return meipass
        # Onedir: use the executable directory so bundled folders like 'configs/' work
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
    except Exception:
        pass
    # Normal dev mode: project root (scripts/..)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def _get_output_dir() -> str:
    """Return a persistent, user-writable directory for saving results.

    - For frozen apps (onefile/onedir), use the directory next to the executable.
    - For dev, use the project-level 'data' directory.
    """
    try:
        if getattr(sys, 'frozen', False):
            return os.path.join(os.path.dirname(sys.executable), 'data')
    except Exception:
        pass
    # Dev mode: project root /data
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))

BASE_DIR = _get_base_dir()
CONFIG_PATH = os.path.join(BASE_DIR, 'configs', 'items.json')
DATA_DIR = _get_output_dir()
LAYOUT_CONFIG_PATH = os.path.join(BASE_DIR, 'configs', 'layout.json')


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
        self.items = {
            'practice': config['practice'],
            'formal': config['formal']
        }
        self.practice = self.items['practice']
        self.formal = self.items['formal']
        self.participant_info = participant_info or {}
        self.practice_answers = {}
        self.formal_answers = {}
        pid = str(self.participant_info.get('participant_id', '')).strip()
        self.debug_mode = config.get('debug_mode', False) or (pid == '0')
        # Deadlines are set right before each section starts (after showing instructions)
        self.practice_deadline = None
        self.formal_deadline = None  # set when formal starts
        self.max_visible_nav = 12
        # Store timing data for saving
        self.practice_last_times = {}
        self.practice_start_time = None
        self.formal_last_times = {}
        self.formal_start_time = None
        layout_cfg = config.get('layout', {}) if isinstance(config, dict) else {}
        self.layout = dict(layout_cfg)  # layout overrides

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

    # ---------- Layout accessor ----------
    def L(self, key, default=None):
        """Convenience accessor for layout values with defaults."""
        try:
            return self.layout.get(key, default)
        except Exception:
            return default
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
        self.practice_start_time = core.getTime()
        if self.debug_mode:
            # Debug: 10 seconds for practice
            self.practice_deadline = self.practice_start_time + 10
        else:
            self.practice_deadline = self.practice_start_time + self.practice['time_limit_minutes'] * 60
        # Run practice section
        self.practice_last_times = self.run_section('practice', start_time=self.practice_start_time)
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
        self.formal_last_times = self.run_section('formal', start_time=self.formal_start_time)
        # Save results after both sections
        self.save_and_exit()

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

        timerStim = visual.TextStim(
            self.win,
            text=timer_text,
            pos=(0, self.L('header_y', 0.82)),
            height=self.L('header_font_size', 0.04),
            color=color
        )
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
        y = self.L('header_y', 0.82)
        # Align progress left edge to the left edge of the right arrow box (with a small margin)
        right_edge_x = self.L('nav_arrow_x_right', 0.98) - (self.L('nav_arrow_w', 0.09) / 2.0)
        x = right_edge_x - self.L('progress_right_margin', 0.01)
        progStim = visual.TextStim(self.win, text=txt, pos=(x, y), height=self.L('header_font_size', 0.04), color=color)
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
        center_y = self.L('instruction_center_y', 0.15)
        line_h = self.L('instruction_line_height', 0.055)
        spacing = self.L('instruction_line_spacing', 1.5)
        show_start = core.getTime()
        # In debug mode, make the instruction button immediately clickable (no countdown)
        delay = 0.0 if self.debug_mode else self.L('instruction_button_delay', 5.0)
        btn_w = self.L('button_width', 0.52)
        btn_h = self.L('button_height', 0.14)
        btn_pos = (self.L('button_x', 0.0), self.L('instruction_button_y', -0.38))
        label_h = self.L('button_label_height', 0.055)
        line_w = self.L('button_line_width', 4)
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
                fill_col = self.L('button_fill_hover', [0, 0.6, 0]) if hovered else self.L('button_fill_normal', [0, 0.4, 0])
                outline_col = self.L('button_outline_hover', 'yellow') if hovered else self.L('button_outline_normal', [0, 0.8, 0])
            else:
                fill_col = self.L('button_fill_disabled', [0.15, 0.15, 0.15])
                outline_col = self.L('button_outline_disabled', [0.5, 0.5, 0.5])

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
        q_w = self.L('question_box_w', 1.4) * self.L('scale_question', 1.584)
        q_h = self.L('question_box_h', 0.5) * self.L('scale_question', 1.584)
        # Remove the white border box - only draw the image
        if image_path and file_exists_nonempty(image_path):
            try:
                max_w = q_w - self.L('question_img_margin_w', 0.05)
                max_h = q_h - self.L('question_img_margin_h', 0.05)
                disp_w, disp_h = fitted_size_keep_aspect(image_path, max_w, max_h)
                img = visual.ImageStim(self.win, image=resolve_path(image_path), pos=(0, self.L('question_box_y', 0.35)), size=(disp_w, disp_h))
                img.draw()
            except Exception:
                txt = visual.TextStim(self.win, text=f"题目 {item_id}\n(图片加载失败)", pos=(0, self.L('question_box_y', 0.35)), height=0.06)
                txt.draw()
        else:
            txt = visual.TextStim(self.win, text=f"题目 {item_id}\n(图片占位)", pos=(0, self.L('question_box_y', 0.35)), height=0.06)
            txt.draw()

    def create_option_rects(self):
        """Build option rectangles for the current item.

        Returns:
            list[visual.Rect]: Rectangles mapped to option indices in order.
        """
        cols = int(self.L('option_cols', 4))
        rows = int(self.L('option_rows', 2))
        dx = self.L('option_dx', 0.45)
        dy = self.L('option_dy', 0.45)
        rect_w = self.L('option_rect_w', 0.4) * self.L('scale_option', 0.749)
        rect_h = self.L('option_rect_h', 0.35) * self.L('scale_option', 0.749)
        center_y = self.L('option_grid_center_y', -0.425)

        rects: list[visual.Rect] = []
        total_cells = cols * rows
        for r in range(rows):
            for c in range(cols):
                idx = r * cols + c
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

    def draw_options(self, option_paths, rects, selected_index=None):
        """绘制选项矩形与图片。

        Args:
            option_paths: 图片路径列表（最多与 rects 数量相同）。
            rects: create_option_rects 返回的矩形列表。
            selected_index: 已选择的选项索引（0 基），None 表示未选择。
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
                    max_w = self.L('option_img_w', 0.36) * self.L('scale_option', 0.749)
                    max_h = self.L('option_img_h', 0.28) * self.L('scale_option', 0.749)
                    disp_w, disp_h = fitted_size_keep_aspect(path, max_w, max_h)
                    img = visual.ImageStim(
                        self.win,
                        image=resolve_path(path),
                        pos=rect.pos,
                        size=(disp_w * self.L('option_img_fill', 0.92), disp_h * self.L('option_img_fill', 0.92))
                    )
                    img.draw()
                else:
                    placeholder = visual.TextStim(self.win, text=str(i+1), pos=rect.pos, height=0.05, color='gray')
                    placeholder.draw()

    def detect_click_on_rects(self, rects):
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

    def _get_section_config(self, section: str):
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
            show_t = self.L('debug_timer_show_threshold', 20)
            red_t = self.L('debug_timer_red_threshold', 10)
        else:
            show_t = self.L('formal_timer_show_threshold', 600)
            red_t = self.L('timer_red_threshold', 300)
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

    def run_section(self, section: str, start_time=None):
        """Run a test section ('practice' or 'formal') with unified flow.

        Args:
            section: 'practice' or 'formal'
            start_time: section start time (float)
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
        if start_time is None:
            start_time = core.getTime()

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
                nav_items, l_rect, r_rect, section, items, current_index, nav_offset)
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

    def _draw_submit_button(self):
        """Draw the submit button and return the rect for click detection.

        Returns:
            visual.Rect: The submit button rectangle for click detection
        """
        btn_pos = (self.L('button_x', 0.0), self.L('submit_button_y', -0.88))
        mouse_local = event.Mouse(win=self.win)
        temp_rect = visual.Rect(self.win, width=self.L('button_width', 0.52),
                               height=self.L('button_height', 0.14), pos=btn_pos)
        hovered = temp_rect.contains(mouse_local)
        fill_col = self.L('button_fill_hover', [0,0.6,0]) if hovered else self.L('button_fill_normal', [0,0.4,0])
        outline_col = self.L('button_outline_hover', 'yellow') if hovered else self.L('button_outline_normal', [0,0.8,0])

        submit_rect = visual.Rect(
            self.win,
            width=self.L('button_width', 0.52),
            height=self.L('button_height', 0.14),
            pos=btn_pos,
            lineColor=outline_col,
            fillColor=fill_col,
            lineWidth=self.L('button_line_width', 4)
        )
        submit_label = visual.TextStim(
            self.win,
            text='提交作答',
            pos=btn_pos,
            height=self.L('button_label_height', 0.055),
            color='white'
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
    def _build_navigation(self, items, answers_dict, current_index, offset):
        """Construct navigation stimuli (question number buttons + page arrows)."""
        n = len(items)
        start = offset
        end = min(n, start + self.max_visible_nav)
        visible = list(range(start, end))
        stims = []
        if not visible:
            return stims, None, None, None, None

        count = len(visible)
        nav_y = self.L('nav_y', 0.90)
        x_left_edge = self.L('nav_arrow_x_left', -0.98)
        x_right_edge = self.L('nav_arrow_x_right', 0.98)
        arrow_w = self.L('nav_arrow_w', 0.09)
        gap = self.L('nav_gap', 0.02)

        x_left = x_left_edge + arrow_w + gap
        x_right = x_right_edge - arrow_w - gap
        span = x_right - x_left
        xs = [x_left + i * span / (count - 1) for i in range(count)] if count > 1 else [ (x_left + x_right) / 2.0 ]

        item_w = self.L('nav_item_w', 0.11)
        item_h = self.L('nav_item_h', 0.07)
        label_h = self.L('nav_label_height', 0.036)

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
            )
            stims.append((gi, rect, label))

        left_rect = left_txt = right_rect = right_txt = None
        arrow_h = item_h
        arrow_label_h = self.L('nav_arrow_label_height', 0.05)
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
            )
        return stims, left_rect, left_txt, right_rect, right_txt

    def _handle_navigation_click(self, nav_items, left_rect, right_rect, section: str, items, current_index, nav_offset):
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

    def save_and_exit(self):
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


def update_config_with_layout(layout_path, layout_params):
    """
    Write layout parameters to a dedicated layout config file.
    Creates a backup of the original layout file if present.
    Returns the layout dict that was written.
    """
    os.makedirs(os.path.dirname(layout_path), exist_ok=True)

    # Backup existing layout file once
    if os.path.exists(layout_path):
        try:
            with open(layout_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except Exception:
            existing = None
        if existing is not None:
            backup_path = layout_path + '.backup'
            if not os.path.exists(backup_path):
                with open(backup_path, 'w', encoding='utf-8') as bf:
                    json.dump(existing, bf, indent=2, ensure_ascii=False)

    with open(layout_path, 'w', encoding='utf-8') as f:
        json.dump(layout_params, f, indent=2, ensure_ascii=False)

    return layout_params


def check_and_suggest_layout(config_path):
    """
    Load base config and a separate layout config file if present.
    If layout file is missing, optionally suggest one based on screen resolution.
    Returns combined config dict with a 'layout' key populated from the layout file.
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # Try load layout file
    layout = None
    if os.path.exists(LAYOUT_CONFIG_PATH):
        try:
            with open(LAYOUT_CONFIG_PATH, 'r', encoding='utf-8') as lf:
                layout = json.load(lf)
            print(f"使用独立布局文件: {os.path.basename(LAYOUT_CONFIG_PATH)}")
        except Exception:
            layout = None
    # Legacy fallback: raven_layout.json -> migrate to layout.json
    if layout is None:
        legacy = os.path.join(os.path.dirname(LAYOUT_CONFIG_PATH), 'raven_layout.json')
        if os.path.exists(legacy):
            try:
                with open(legacy, 'r', encoding='utf-8') as lf:
                    layout = json.load(lf)
                # write to new path for future runs
                update_config_with_layout(LAYOUT_CONFIG_PATH, layout)
                print("已从 raven_layout.json 迁移到 layout.json")
            except Exception:
                layout = None

    # Backward compatibility: fallback to embedded layout
    if layout is None:
        embedded = config.get('layout')
        if embedded:
            layout = embedded
            # Optional: migrate to standalone file
            try:
                update_config_with_layout(LAYOUT_CONFIG_PATH, layout)
                print("已从主配置迁移布局到独立文件")
            except Exception:
                pass

    # If still no layout, suggest based on resolution
    if not layout:
        resolution = detect_screen_resolution()
        if resolution:
            width, height = resolution
            print(f"检测到屏幕分辨率: {width}x{height}")
            print("未找到布局文件，正在生成建议参数...")
            suggested = suggest_layout_for_resolution(width, height)
            print(f"建议的布局参数:\n{json.dumps(suggested, indent=2, ensure_ascii=False)}")

            dlg = gui.Dlg(title='布局建议')
            dlg.addText(f'检测到屏幕分辨率: {width}x{height}')
            dlg.addText('建议应用自动优化的布局参数')
            dlg.addText(f'scale_question: {suggested["scale_question"]}')
            dlg.addText(f'scale_option: {suggested["scale_option"]}')
            dlg.addField('应用建议布局?', initial=True)
            result = dlg.show()

            if dlg.OK and result and result[0]:
                layout = update_config_with_layout(LAYOUT_CONFIG_PATH, suggested)
                print("✓ 已将建议布局参数写入独立布局文件")
            else:
                print("已跳过布局优化，使用内置默认参数")
                layout = suggested  # still use suggested for current run
        else:
            print("无法检测屏幕分辨率，使用默认布局参数")
            layout = suggest_layout_for_resolution(1920, 1080)

    # Compose combined config for downstream code
    config['layout'] = layout
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
    try:
        task.run()
    finally:
        # Clean up window（不再用 try 包裹，之前的退出错误已修复）
        win.close()
        # In frozen/packaged apps, core.quit() can cause logging errors
        # Just let the program exit normally instead

if __name__ == '__main__':
    main()
