# Raven Dev - PsychoPy Stimulus Presentation

This project is designed for stimulus presentation using PsychoPy.

## Project Structure

```
raven-dev/
├── stimuli/          # Stimulus files (images, videos, audio, etc.)
├── data/             # Output data files
├── scripts/          # Python scripts for experiments
├── configs/          # Configuration files
├── results/          # Analysis results
└── docs/             # Documentation
```

## Requirements

- Python 3.8+
- PsychoPy

## Installation

### 方法1：使用 Conda（推荐）

创建并激活专用环境：

```bash
conda env create -f environment.yml
conda activate psychopy-dev
```

### 方法2：使用 pip

```bash
pip install -r requirements.txt
```

## Usage

### Run Raven Task

确保已激活 conda 环境（如果使用方法1）：

```bash
conda activate psychopy-dev
```

或确保已安装依赖（如果使用方法2）：

```bash
pip install -r requirements.txt
```

运行实验（练习集 + 正式集）：

```bash
python scripts/raven_task.py
```

默认：练习 Set I 10 分钟上限，正式 Set II 40 分钟上限。正式阶段顶部展示题号导航，可回看和修改已答题目；最后一题作答后底部出现“提交答案”按钮（不自动提交），点击后保存结果文件到 `data/` 目录，如：`raven_results_20250101_101530.csv`。

你可以通过编辑 `configs/raven_config.json` 添加真实题目与图片路径。每个题目包含：

```jsonc
{
  "id": "F1",
  "question_image": "stimuli/f1_question.png",
  "options": [
    "stimuli/f1_opt1.png",
    "stimuli/f1_opt2.png",
    "stimuli/f1_opt3.png",
    "stimuli/f1_opt4.png",
    "stimuli/f1_opt5.png",
    "stimuli/f1_opt6.png",
    "stimuli/f1_opt7.png",
    "stimuli/f1_opt8.png"
  ]
}
```

### 自定义时间限制

`time_limit_minutes` 字段控制练习与正式阶段时长。

### 数据输出格式

自动根据配置中的模式与 `stimuli/answers.txt` 生成题目。结果包含：

CSV 列：

`participant_id, section, item_id, answer, correct, is_correct, timestamp`

说明：

- `answer` 为被试选择的选项序号（1-8），未作答为空。
- `correct` 为正确选项序号（1-8）。
- `is_correct` 为 1 正确 / 0 错误 / 空 表示未作答或无正确答案定义。
- `timestamp` 为保存时间（统一时间戳）。

会话还生成 JSON：`raven_session_YYYYMMDD_HHMMSS.json`，含：

```jsonc
{
  "participant": {"participant_id": "..."},
  "practice": {"n_items": 12, "correct_count": 9, ...},
  "formal": {"n_items": 36, "correct_count": 28, ...},
  "total_correct": 37,
  "total_items": 48
}
```

### 布局微调 (layout)

在 `configs/raven_config.json` 中可通过 `layout` 段调整显示：

```jsonc
"layout": {
  "scale_question": 1.2,      // 题干区域整体缩放
  "scale_option": 0.9,        // 选项区域缩放（<1 缩小）
  "nav_y": 0.90,              // 顶部导航条的 y 位置
  "timer_y": 0.82,            // 计时器 y 位置
  "option_grid_center_y": -0.425 // 选项网格中心 y
}
```

其它可选键：`option_dx`, `option_dy`, `question_box_w`, `question_box_h` 等，用于进一步控制布局与缩放。如需更复杂的自适应分辨率逻辑，可在代码中扩展。

## License

TBD
