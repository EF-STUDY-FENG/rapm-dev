"""Raven Advanced Progressive Matrices – Application Entry Point

This module serves as the main entry point for the RAPM experiment.

Responsibilities:
1. Collect participant information via PsychoPy dialog
2. Load configuration files (sequence.json, layout.json)
3. Instantiate and run RavenTask

Flow:
    main() → collect_participant_info() → RavenTask(configs).run()

The actual experiment logic (window management, test sections, data saving)
is delegated to RavenTask in raven_task.py.

Debug mode:
- Triggered by layout.json flag or participant_id == '0'
- Results in: windowed display, shortened timings, immediate buttons
"""
from config_loader import load_sequence, load_layout
from raven_task import RavenTask


# =============================================================================
# PARTICIPANT INFO COLLECTION
# =============================================================================

def get_participant_info():
    """Collect participant information via single PsychoPy dialog.

    Validates that participant_id is provided before returning.
    Loops until a valid ID is entered or user cancels.

    Returns:
        dict | None: Participant info dict with keys:
            - participant_id (required)
            - age, gender, session, notes (optional)
        Returns None if user cancels the dialog.
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
        dlg = gui.DlgFromDict(
            default,
            title='被试信息',
            order=['participant_id', 'age', 'gender', 'session', 'notes']
        )
        if not dlg.OK:
            return None
        pid = (default.get('participant_id') or '').strip()
        if pid:
            return default
        # Show error and loop
        gui.Dlg(title='提示', labelButtonOK='确定').addText(
            '需要填写被试编号 (participant_id)'
        ).show()


def collect_participant_info() -> dict | None:
    """Retry loop wrapper with confirmation dialog on cancel.

    Allows user to retry input or confirm exit if they cancel
    the initial participant info dialog.

    Returns:
        dict | None: Participant info dict if successful, None if user exits
    """
    from psychopy import gui
    while True:
        info = get_participant_info()
        if info is None:
            confirm = gui.Dlg(
                title='确认退出？',
                labelButtonOK='重试',
                labelButtonCancel='退出'
            )
            confirm.addText('未填写信息或已取消。是否重新输入？')
            confirm.show()
            if confirm.OK:
                continue
            else:
                return None
        return info


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point for the Raven task.

    Orchestrates:
    1. Load configuration files from configs/
    2. Collect participant info (with retry logic)
    3. Create RavenTask instance
    4. Execute task (window creation and sections handled internally)
    """
    # Load configuration files
    sequence = load_sequence()
    layout = load_layout()

    # Collect participant info (with retry dialog)
    info = collect_participant_info()
    if info is None:
        return

    # Create and run task (window lifecycle managed inside RavenTask.run())
    task = RavenTask(sequence, layout, participant_info=info)
    task.run()


if __name__ == '__main__':
    main()
