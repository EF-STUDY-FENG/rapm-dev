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
        self.current_formal_index = 0
        self.in_practice = True
        self.start_time = core.getTime()
        # Deadlines are set right before each section starts (after showing instructions)
        self.practice_deadline = None
        self.formal_deadline = None  # set when formal starts
        self.submit_visible = False
        # top navigation pagination offset (for many items)
        self.nav_offset = 0
        self.max_visible_nav = 12
        # Layout tuning (can be overridden in config.layout)
        layout_cfg = config.get('layout', {}) if isinstance(config, dict) else {}
        self.scale_question = float(layout_cfg.get('scale_question', 1.584))  # enlarge question area (1.2 * 1.32)
        self.scale_option = float(layout_cfg.get('scale_option', 0.749))      # options +5% from previous 0.713
        self.nav_y = float(layout_cfg.get('nav_y', 0.90))
        self.timer_y = float(layout_cfg.get('timer_y', 0.82))
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
        self.question_box_w_base = float(layout_cfg.get('question_box_w', 1.4))
        self.question_box_h_base = float(layout_cfg.get('question_box_h', 0.5))
        self.question_box_y = float(layout_cfg.get('question_box_y', 0.35))
        self.question_img_margin_w = float(layout_cfg.get('question_img_margin_w', 0.05))
        self.question_img_margin_h = float(layout_cfg.get('question_img_margin_h', 0.05))

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
        self.formal_deadline = core.getTime() + self.formal['time_limit_minutes'] * 60
        self.run_formal()

    # ---------- Generic drawing helpers ----------
    def draw_timer(self, deadline):
        remaining = max(0, int(deadline - core.getTime()))
        mins = remaining // 60
        secs = remaining % 60
        timer_text = f"剩余时间: {mins:02d}:{secs:02d}"
        timerStim = visual.TextStim(self.win, text=timer_text, pos=(0, self.timer_y), height=0.04, color='white')
        timerStim.draw()

    def show_instruction(self, text: str, button_text: str = "继续"):
        """Display centered multi-line instruction with a clickable button below.
        PsychoPy TextStim lacks a lineSpacing kwarg in some versions; we render lines manually.
        """
        # Precompute lines layout
        center_y = 0.15
        line_h = 0.055
        spacing = self.instruction_line_spacing
        lines = (text or "").split("\n")
        n = len(lines)
        total = line_h * spacing * (n - 1) if n > 1 else 0.0
        start_y = center_y + total / 2.0

        # Button setup
        btn_w, btn_h = 0.48, 0.12
        btn_pos = (0, -0.35)
        btn_rect = visual.Rect(self.win, width=btn_w, height=btn_h, pos=btn_pos, lineColor='white', fillColor=None)
        btn_label = visual.TextStim(self.win, text=button_text, pos=btn_pos, height=0.05, color='white')
        mouse = event.Mouse(win=self.win)
        while True:
            # Draw multi-line instruction centered
            for i, line in enumerate(lines):
                y = start_y - i * (line_h * spacing)
                visual.TextStim(self.win, text=line, pos=(0, y), height=line_h, color='white').draw()
            btn_rect.draw()
            btn_label.draw()
            self.win.flip()
            if any(mouse.getPressed()) and btn_rect.contains(mouse):
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

    # ---------- Practice flow ----------
    def run_practice(self):
        items = self.practice['items']
        for item in items:
            answered = False
            while not answered and core.getTime() < self.practice_deadline:
                self.draw_timer(self.practice_deadline)
                self.draw_question(item['id'], item.get('question_image'))
                rects = self.create_option_rects()
                self.draw_options(item.get('options', []), rects)
                self.win.flip()
                choice = self.detect_click_on_rects(rects)
                if choice is not None:
                    self.practice_answers[item['id']] = choice + 1
                    answered = True
            if core.getTime() >= self.practice_deadline:
                break
        # brief transition
        # Removed transitional text; formal instructions appear separately

    # ---------- Formal flow with TOP navigation ----------
    def build_top_navigation(self):
        items = self.formal['items']
        n = len(items)
        stims = []  # list of tuples (global_index, rect, label)
        # Determine visible window
        start = self.nav_offset
        end = min(n, start + self.max_visible_nav)
        visible = list(range(start, end))
        count = len(visible)
        if count == 0:
            return stims, None, None
        # Evenly space within [-0.9, 0.9] at nav_y
        x_left, x_right = -0.9, 0.9
        span = x_right - x_left
        if count == 1:
            xs = [0.0]
        else:
            xs = [x_left + i * span / (count - 1) for i in range(count)]
        for i, gi in enumerate(visible):
            item = items[gi]
            answered = item['id'] in self.formal_answers
            rect = visual.Rect(self.win, width=0.11, height=0.07, pos=(xs[i], self.nav_y),
                               lineColor='yellow' if gi == self.current_formal_index else 'white',
                               fillColor=(0, 0.4, 0) if answered else None)
            label = visual.TextStim(self.win, text=item['id'], pos=(xs[i], self.nav_y), height=0.035,
                                    color='black' if answered else 'white')
            stims.append((gi, rect, label))
        left_arrow = right_arrow = None
        if self.nav_offset > 0:
            left_arrow = visual.TextStim(self.win, text='⟵', pos=(-0.98, self.nav_y), height=0.06, color='white')
        if end < n:
            right_arrow = visual.TextStim(self.win, text='⟶', pos=(0.98, self.nav_y), height=0.06, color='white')
        return stims, left_arrow, right_arrow

    def handle_top_navigation_click(self, nav_items, left_arrow, right_arrow):
        mouse = event.Mouse(win=self.win)
        if any(mouse.getPressed()):
            # Arrows
            if left_arrow and left_arrow.contains(mouse):
                while any(mouse.getPressed()):
                    core.wait(0.01)
                self.nav_offset = max(0, self.nav_offset - self.max_visible_nav)
                return 'page'
            if right_arrow and right_arrow.contains(mouse):
                while any(mouse.getPressed()):
                    core.wait(0.01)
                self.nav_offset = min(max(0, len(self.formal['items']) - self.max_visible_nav), self.nav_offset + self.max_visible_nav)
                return 'page'
            # Items
            for gi, rect, label in nav_items:
                if rect.contains(mouse) or label.contains(mouse):
                    while any(mouse.getPressed()):
                        core.wait(0.01)
                    self.current_formal_index = gi
                    return 'jump'
        return None

    def run_formal(self):
        items = self.formal['items']
        n_items = len(items)
        if n_items == 0:
            return
        while core.getTime() < self.formal_deadline:
            item = items[self.current_formal_index]
            # Top navigation bar
            nav_items, left_arrow, right_arrow = self.build_top_navigation()
            for _, rect, label in nav_items:
                rect.draw(); label.draw()
            if left_arrow:
                left_arrow.draw()
            if right_arrow:
                right_arrow.draw()
            # Timer below nav bar
            self.draw_timer(self.formal_deadline)
            # Question + options
            self.draw_question(item['id'], item.get('question_image'))
            rects = self.create_option_rects()
            prev_choice = None
            if item['id'] in self.formal_answers:
                # stored answers are 1-based
                prev_choice = self.formal_answers[item['id']] - 1
            self.draw_options(item.get('options', []), rects, selected_index=prev_choice)
            # Bottom instructions and submit
            bottom_text = '正式测试：请选择一个选项。可点击上方题号回看/修改。'
            if self.current_formal_index == n_items - 1:
                bottom_text += ' 最后一题完成后将显示提交按钮。'
            instruction = visual.TextStim(self.win, text=bottom_text, pos=(0, -0.85), height=0.04)
            instruction.draw()
            submit_btn = None
            if self.submit_visible:
                submit_btn = visual.TextStim(self.win, text='提交答案', pos=(0, -0.9), height=0.06, color='green')
                submit_btn.draw()
            self.win.flip()

            mouse = event.Mouse(win=self.win)
            # Submit click
            if submit_btn and any(mouse.getPressed()) and submit_btn.contains(mouse):
                while any(mouse.getPressed()):
                    core.wait(0.01)
                self.save_and_exit()
                return

            # Option click
            choice = self.detect_click_on_rects(rects)
            if choice is not None:
                self.formal_answers[item['id']] = choice + 1
                if self.current_formal_index == n_items - 1:
                    self.submit_visible = True
                else:
                    self.current_formal_index += 1
                continue

            # Navigation click
            nav_action = self.handle_top_navigation_click(nav_items, left_arrow, right_arrow)
            if nav_action in ('page', 'jump'):
                continue

            # Check time
            if core.getTime() >= self.formal_deadline:
                break
        # Time over or manual exit (not submitted)
        self.show_time_up()

    # ---------- End states ----------
    def show_time_up(self):
        msg = visual.TextStim(self.win, text='时间结束，未提交。', height=0.07, color='red')
        for _ in range(180):
            msg.draw(); self.win.flip()

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
        confirm = visual.TextStim(self.win, text=f'提交成功! 保存于 {out_path}', height=0.05, color='green')
        for _ in range(240):
            confirm.draw(); self.win.flip()


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
        "timer_y": 0.82,
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
    # Adjust for narrow/portrait screens
    elif aspect_ratio < 1.3:
        layout["nav_y"] = 0.92
        layout["timer_y"] = 0.85
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
    win = visual.Window(size=(1280, 800), color='black', units='norm')
    task = RavenTask(win, config, participant_info=info)
    task.run()
    win.close()
    core.quit()

if __name__ == '__main__':
    main()
