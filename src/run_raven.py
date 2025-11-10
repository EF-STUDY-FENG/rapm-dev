"""Raven Advanced Reasoning Task - Entry Point

This is the main entry file for the Raven Advanced Reasoning Test.
It handles:
- Participant information collection
- Window initialization (debug vs fullscreen mode)
- Task execution coordination

The core experiment logic is in raven_task.RavenTask.

Features:
- Practice Set I: linear progression, auto-advance after selection, 10 min total cap.
- Formal Set II: user can navigate back to previously answered items to modify answers within 40 min cap.
- Navigation strip at the TOP (formal only): clickable item IDs; current highlighted; answered marked.
- Countdown timer near top.
- After last formal item answered: show a persistent Submit button at bottom (does NOT auto-submit).
- Data saved to data/raven_results_YYYYMMDD_HHMMSS.csv upon submit.

Dependencies: psychopy
"""
from psychopy import visual, gui
from config_loader import load_sequence, load_layout
from raven_task import RavenTask


def get_participant_info():
    """Collect participant information via PsychoPy dialog.

    Returns:
        dict | None: Participant info dict if valid, None if cancelled
    """
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
    """Main entry point for the Raven task."""
    # Load configuration files
    sequence = load_sequence()
    layout = load_layout()

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
    debug_active = bool(layout.get('debug_mode', False) or (pid_str == '0'))

    # In non-debug mode run fullscreen; in debug mode use a window for convenience
    if debug_active:
        win = visual.Window(size=(1280, 800), color='black', units='norm')
    else:
        win = visual.Window(fullscr=True, color='black', units='norm')

    # Create and run the task
    task = RavenTask(win, sequence, layout, participant_info=info)
    try:
        task.run()
    finally:
        # Clean up window
        win.close()
        # In frozen/packaged apps, core.quit() can cause logging errors
        # Just let the program exit normally instead


if __name__ == '__main__':
    main()
