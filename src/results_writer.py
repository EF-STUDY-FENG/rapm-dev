"""ResultsWriter: handles persistence of Raven task results (CSV + JSON)."""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime

from config_loader import get_output_dir
from rapm_types import ParticipantInfo, SectionConfig

DATA_DIR = get_output_dir()

class ResultsWriter:
    """Handles persistence of RAPM task results to CSV and JSON.

    Saves participant information, answers, and timing data in structured format.
    """

    def __init__(self, output_dir: str | None = None) -> None:
        """Initialize results writer.

        Args:
            output_dir: Custom output directory (defaults to DATA_DIR)
        """
        self.output_dir = output_dir or DATA_DIR

    def save(
        self,
        participant_info: ParticipantInfo,
        practice_conf: SectionConfig,
        formal_conf: SectionConfig,
        practice_answers: dict[str, int],
        formal_answers: dict[str, int],
        practice_timing,
        formal_timing,
    ) -> tuple[str, str]:
        """Persist results.

        Returns:
            (csv_path, json_path)
        """
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        os.makedirs(self.output_dir, exist_ok=True)
        csv_path = os.path.join(self.output_dir, f'raven_results_{ts}.csv')
        pid = participant_info.get('participant_id', '')
        practice_correct = 0
        formal_correct = 0

        def write_section(writer, section: str, items, answers, last_times, start_time):
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
                writer.writerow([
                    pid, section, iid,
                    ans if ans is not None else '',
                    correct if correct is not None else '',
                    '1' if is_correct else ('0' if is_correct is not None else ''),
                    time_used
                ])

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'participant_id', 'section', 'item_id', 'answer', 'correct', 'is_correct', 'time'
            ])
            write_section(
                writer,
                'practice',
                practice_conf.get('items', []),
                practice_answers,
                practice_timing.last_times,
                practice_timing.start_time,
            )
            write_section(
                writer,
                'formal',
                formal_conf.get('items', []),
                formal_answers,
                formal_timing.last_times,
                formal_timing.start_time,
            )

        meta = {
            'participant': participant_info,
            'time_created': datetime.now().isoformat(timespec='seconds'),
            'practice': {
                'set': practice_conf.get('set'),
                'duration_seconds': practice_conf.get('durations', {}).get('normal'),
                'n_items': len(practice_conf.get('items', [])),
                'correct_count': practice_correct,
                'remaining_seconds_at_save': getattr(
                    practice_timing,
                    'remaining_seconds',
                    lambda: None,
                )()
            },
            'formal': {
                'set': formal_conf.get('set'),
                'duration_seconds': formal_conf.get('durations', {}).get('normal'),
                'n_items': len(formal_conf.get('items', [])),
                'correct_count': formal_correct,
                'remaining_seconds_at_save': getattr(
                    formal_timing,
                    'remaining_seconds',
                    lambda: None,
                )()
            },
            'total_correct': practice_correct + formal_correct,
            'total_items': len(practice_conf.get('items', [])) + len(formal_conf.get('items', []))
        }
        json_path = os.path.join(self.output_dir, f'raven_session_{ts}.json')
        try:
            with open(json_path, 'w', encoding='utf-8') as mf:
                json.dump(meta, mf, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return csv_path, json_path
