"""Typed structures for RAPM task configuration and data models.

Defines TypedDict schemas for:
- Item: Question and options data structure
- SectionConfig: Practice/formal section configuration
- ParticipantInfo: User demographic information
- LayoutConfig: Visual layout parameters
- SequenceConfig: Overall experiment sequence
"""
from __future__ import annotations

from typing import TypedDict


class Item(TypedDict):
    id: str
    question_image: str
    options: list[str]
    correct: int | None

class SectionConfig(TypedDict, total=False):
    set: str
    count: int
    pattern: str
    instruction: str
    button_text: str
    time_limit_minutes: int
    debug_duration: int
    items: list[Item]

class ParticipantInfo(TypedDict, total=False):
    participant_id: str
    age: str
    gender: str
    session: str
    notes: str

class LayoutConfig(TypedDict, total=False):
    # Fonts
    font_main: str
    # Instruction screen
    instruction_center_y: float
    instruction_line_height: float
    instruction_line_spacing: float
    instruction_button_y: float
    instruction_button_delay: float
    # Buttons
    button_width: float
    button_height: float
    button_x: float
    button_label_height: float
    button_line_width: float
    button_fill_hover: object
    button_fill_normal: object
    button_fill_disabled: object
    button_outline_hover: object
    button_outline_normal: object
    button_outline_disabled: object
    # Header (timer/progress)
    header_y: float
    header_font_size: float
    progress_right_margin: float
    # Question
    question_box_y: float
    question_box_w: float
    question_box_h: float
    question_img_margin_w: float
    question_img_margin_h: float
    scale_question: float
    # Options grid
    option_cols: int
    option_rows: int
    option_dx: float
    option_dy: float
    option_rect_w: float
    option_rect_h: float
    option_img_w: float
    option_img_h: float
    option_img_fill: float
    option_grid_center_y: float
    scale_option: float
    # Navigation bar
    nav_y: float
    nav_gap: float
    nav_item_w: float
    nav_item_h: float
    nav_label_height: float
    nav_arrow_x_left: float
    nav_arrow_x_right: float
    nav_arrow_w: float
    nav_arrow_label_height: float
    # Timers
    formal_timer_show_threshold: int
    timer_red_threshold: int
    debug_timer_show_threshold: int
    debug_timer_red_threshold: int
    # Submit button
    submit_button_y: float
    # Misc
    debug_mode: bool

class SequenceConfig(TypedDict, total=False):
    practice: SectionConfig
    formal: SectionConfig
    answers_file: str
