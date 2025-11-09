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

**自动屏幕适配**：首次运行时，程序会自动检测屏幕分辨率，并根据显示器尺寸建议合适的布局参数。如果配置文件中未设置布局，会弹出对话框询问是否应用自动生成的建议参数。接受后会自动写入 `configs/raven_config.json` 并创建备份文件。

默认：练习 Set I 10 分钟上限，正式 Set II 40 分钟上限。正式阶段顶部展示题号导航，可回看和修改已答题目；最后一题作答后底部出现"提交答案"按钮（不自动提交），点击后保存结果文件到 `data/` 目录，如：`raven_results_20250101_101530.csv`。

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

其它可选键：`option_dx`, `option_dy`, `question_box_w`, `question_box_h` 等，用于进一步控制布局与缩放。

**自动布局建议**：程序启动时会自动检测屏幕分辨率（通过 PsychoPy 或 tkinter），并根据以下规则生成建议参数：

- **高分辨率屏幕** (≥2560px): `scale_question=1.4, scale_option=1.0`
- **标准全高清** (≥1920px): `scale_question=1.3, scale_option=0.95`
- **小屏幕** (<1280px): `scale_question=1.0, scale_option=0.8`
- **超宽屏** (宽高比>2.0): 选项网格中心上移至 `-0.3`
- **竖屏/窄屏** (宽高比<1.3): 导航和计时器上移，选项下移至 `-0.5`

首次运行或配置文件无 `layout` 时会弹窗询问是否应用建议，确认后自动写入配置并创建 `.backup` 备份。如需更复杂的自适应分辨率逻辑，可在代码中扩展 `suggest_layout_for_resolution()` 函数。

### Debug 模式

程序支持 debug 模式用于快速测试倒计时功能：

**启用方式（两种方法任选其一）：**

1. **配置文件启用**：在 `configs/raven_config.json` 中设置：

   ```json
   "debug_mode": true
   ```

2. **被试编号为 0**：在被试信息对话框中输入 `participant_id` 为 `0`，自动进入 debug 模式

**Debug 模式特性：**

- **正式测试时长**：从 40 分钟缩短为 **25 秒**
- **倒计时显示**：剩余 **20 秒**时开始显示（正常模式为 10 分钟）
- **红色警告**：剩余 **10 秒**时倒计时变为红色（正常模式为 5 分钟）
- **练习部分**：保持不变（10 分钟）

此模式便于开发者快速验证倒计时显示逻辑、颜色变化和时间到期提醒功能。

## License

TBD
