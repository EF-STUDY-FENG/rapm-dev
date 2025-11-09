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
import json
import os
import csv
from datetime import datetime

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'configs', 'raven_config.json')
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def file_exists_nonempty(path: str) -> bool:
    try:
        return os.path.isfile(path) and os.path.getsize(path) > 0
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
        self.practice_deadline = self.start_time + self.practice['time_limit_minutes'] * 60
        self.formal_deadline = None  # set when formal starts
        self.submit_visible = False
        # top navigation pagination offset (for many items)
        self.nav_offset = 0
        self.max_visible_nav = 12

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
        self.run_practice()
        self.in_practice = False
        self.formal_deadline = core.getTime() + self.formal['time_limit_minutes'] * 60
        self.run_formal()

    # ---------- Generic drawing helpers ----------
    def draw_timer(self, deadline):
        remaining = max(0, int(deadline - core.getTime()))
        mins = remaining // 60
        secs = remaining % 60
        timer_text = f"剩余时间: {mins:02d}:{secs:02d}"
        timerStim = visual.TextStim(self.win, text=timer_text, pos=(0, 0.82), height=0.04, color='white')
        timerStim.draw()

    def draw_question(self, item_id: str, image_path: str | None):
        # Question area at top center
        rect = visual.Rect(self.win, width=1.4, height=0.5, pos=(0, 0.35), lineColor='white', fillColor=None)
        rect.draw()
        if image_path and file_exists_nonempty(image_path):
            try:
                img = visual.ImageStim(self.win, image=image_path, pos=(0, 0.35), size=(1.35, 0.45))
                img.draw()
            except Exception:
                txt = visual.TextStim(self.win, text=f"题目 {item_id}\n(图片加载失败)", pos=(0, 0.35), height=0.06)
                txt.draw()
        else:
            txt = visual.TextStim(self.win, text=f"题目 {item_id}\n(图片占位)", pos=(0, 0.35), height=0.06)
            txt.draw()

    def create_option_rects(self):
        rects = []
        for i in range(8):
            x = -0.7 + (i % 4) * 0.45
            y = -0.2 - (i // 4) * 0.45
            rect = visual.Rect(self.win, width=0.4, height=0.35, pos=(x, y), lineColor='white', fillColor=None)
            label = visual.TextStim(self.win, text=str(i+1), pos=(x, y-0.14), height=0.06)
            rects.append((rect, label))
        return rects

    def draw_options(self, option_paths, rects, selected_index=None):
        """Draw option rectangles; highlight selected with thicker yellow border."""
        for idx, (rect, label) in enumerate(rects):
            # highlight previously selected
            if selected_index is not None and idx == selected_index:
                rect.lineColor = 'yellow'
                rect.lineWidth = 6
            else:
                rect.lineColor = 'white'
                rect.lineWidth = 2
            if idx < len(option_paths) and file_exists_nonempty(option_paths[idx]):
                try:
                    img = visual.ImageStim(self.win, image=option_paths[idx], pos=rect.pos, size=(0.36, 0.28))
                    img.draw()
                except Exception:
                    pass
            rect.draw()
            label.draw()

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
                instruction = visual.TextStim(self.win, text='练习：请点击一个选项 (自动进入下一题)', pos=(0, -0.85), height=0.04)
                instruction.draw()
                self.win.flip()
                choice = self.detect_click_on_rects(rects)
                if choice is not None:
                    self.practice_answers[item['id']] = choice + 1
                    answered = True
            if core.getTime() >= self.practice_deadline:
                break
        # brief transition
        trans = visual.TextStim(self.win, text='练习结束，进入正式测试...', height=0.05)
        for _ in range(60):
            self.draw_timer(core.getTime()+5)  # dummy visual
            trans.draw(); self.win.flip()

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
        # Evenly space within [-0.9, 0.9] at y=0.92
        x_left, x_right = -0.9, 0.9
        span = x_right - x_left
        if count == 1:
            xs = [0.0]
        else:
            xs = [x_left + i * span / (count - 1) for i in range(count)]
        for i, gi in enumerate(visible):
            item = items[gi]
            answered = item['id'] in self.formal_answers
            rect = visual.Rect(self.win, width=0.11, height=0.07, pos=(xs[i], 0.92),
                               lineColor='yellow' if gi == self.current_formal_index else 'white',
                               fillColor=(0, 0.4, 0) if answered else None)
            label = visual.TextStim(self.win, text=item['id'], pos=(xs[i], 0.92), height=0.035,
                                    color='black' if answered else 'white')
            stims.append((gi, rect, label))
        left_arrow = right_arrow = None
        if self.nav_offset > 0:
            left_arrow = visual.TextStim(self.win, text='⟵', pos=(-0.98, 0.92), height=0.06, color='white')
        if end < n:
            right_arrow = visual.TextStim(self.win, text='⟶', pos=(0.98, 0.92), height=0.06, color='white')
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
        # write CSV answers with participant id and timestamp
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['participant_id', 'section', 'item_id', 'answer', 'timestamp'])
            pid = self.participant_info.get('participant_id', '')
            tnow = datetime.now().isoformat(timespec='seconds')
            for k, v in self.practice_answers.items():
                writer.writerow([pid, 'practice', k, v, tnow])
            for k, v in self.formal_answers.items():
                writer.writerow([pid, 'formal', k, v, tnow])
        # write a metadata json as well
        meta = {
            'participant': self.participant_info,
            'time_created': datetime.now().isoformat(timespec='seconds'),
            'practice': {'set': self.practice.get('set'), 'time_limit_minutes': self.practice.get('time_limit_minutes'), 'n_items': len(self.practice.get('items', []))},
            'formal': {'set': self.formal.get('set'), 'time_limit_minutes': self.formal.get('time_limit_minutes'), 'n_items': len(self.formal.get('items', []))}
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


def main():
    config = load_config(CONFIG_PATH)
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
