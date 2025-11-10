"""Raven Advanced Progressive Matrices – Entry Point

This module is the application entry for the Raven APM task. It is responsible for:
- Collecting participant information via a PsychoPy dialog
- Initializing the display window (fullscreen in normal mode, 1280×800 window in debug mode)
- Loading configuration and delegating the experiment flow to `raven_task.RavenTask`

Current behavior (reflects the latest implementation):
- Two sections: Practice (Set I) and Formal (Set II). The section content, item counts and timing are defined in `configs/sequence.json`.
- Navigation bar: a clickable item-number strip is shown at the top in both sections, allowing direct jumps between items.
- Timer and progress in the header: always drawn in a unified header line. In practice the timer is always visible; in formal the timer is shown only when the remaining time is below a configurable threshold (`layout.json`). The timer turns red under a configurable warning threshold.
- Practice: selecting an option records the answer and typically advances to the next item; the section ends when all items are answered or the time limit is reached (no submit button in practice).
- Formal: after all items are answered, a persistent "Submit" button appears at the bottom; data is saved only after the user clicks it. If time runs out, answers are auto-saved.
- Data output: on submit (or timeout in formal), results are written to the `data/` folder as a per-trial CSV and a session-level JSON summary.

Debug mode:
- Enable by setting `"debug_mode": true` in `configs/layout.json`, or by entering participant_id `0` in the dialog.
- Shortened timing: Practice 10 s, Formal 25 s. In formal, the timer becomes visible/red at 20 s/10 s respectively. The window runs in 1280×800 for convenience.

See `config_loader.py` and `path_utils.py` for configuration loading and robust resource resolution suitable for both development and PyInstaller builds.
Dependencies: PsychoPy.
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
