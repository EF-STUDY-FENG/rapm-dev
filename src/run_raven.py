"""Raven Advanced Progressive Matrices – Application entry point.

Responsibilities:
1. Collect participant info (PsychoPy dialog)
2. Create the display window (fullscreen normal, 1280x800 in debug)
3. Load configs and delegate execution to `RavenTask`

Summary:
- Two phases: practice + formal. Content/counts/timing defined in `configs/sequence.json` and `layout.json`.
- Navigation, timer and progress logic live in `raven_task.RavenTask`.
- Debug mode: participant_id '0' or layout flag; shortened timing; windowed mode.

See `raven_task.py` for detailed flow and data saving logic.
"""
from config_loader import load_sequence, load_layout
from raven_task import RavenTask


def get_participant_info():
    """Collect participant information via PsychoPy dialog.

    Returns:
        dict | None: Participant info dict if valid, None if cancelled
    """
    from psychopy import gui
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
    from psychopy import gui
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
    from psychopy import visual
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
