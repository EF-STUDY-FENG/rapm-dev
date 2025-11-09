# Raven Dev - PsychoPy Stimulus Presentation

This project is designed for stimulus presentation using PsychoPy.

## Project Structure

```text
raven-dev/
├── stimuli/          # Stimulus files (images, videos, audio, etc.)
├── data/             # Output data files
├── scripts/          # Python scripts for experiments
├── configs/          # Configuration files
├── results/          # Analysis results
└── docs/             # Documentation
```

## 打包为可执行文件（.exe）

以下步骤可将本项目打包为 Windows 下可分发的独立程序：

前提：已在当前环境中安装 PsychoPy 及依赖（见上文安装）。

1. 运行一键打包脚本（PowerShell）：

```powershell
# 无控制台窗口、按目录输出（推荐分发）
pwsh -File scripts/build_exe.ps1

# 生成单文件 .exe（启动时解压较慢）
pwsh -File scripts/build_exe.ps1 -OneFile

# 调试时显示控制台窗口
pwsh -File scripts/build_exe.ps1 -Console
```

完成后，产物位于 `dist/` 目录下：

- `dist/RavenTask/`（目录模式）或 `dist/RavenTask.exe`（单文件模式）。

1. 打包细节

- 脚本使用 PyInstaller，自动将 `configs/` 与 `stimuli/` 目录一并打包。
- 代码已适配 PyInstaller（自动识别 `sys._MEIPASS` 与 `sys.executable`），运行时能正确定位资源文件。
- 如需自定义图标，可执行：

```powershell
pwsh -File scripts/build_exe.ps1 -Icon .\assets\app.ico
```

1. 常见问题

- 若提示未找到 `pyinstaller`，脚本会自动通过 `pip` 安装。
- 首次运行单文件模式时启动较慢属于正常现象（需解压临时目录）。
- 如果你在 Builder/standalone PsychoPy 中遇到缺字库或声音模块问题，本项目未使用声音模块；如需加入，请在 `build_exe.ps1` 中添加相应 `--hidden-import`。


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

显示模式：

- 非 Debug 模式：默认全屏运行（full screen）。
- Debug 模式：默认窗口化（1280x800），便于快速测试与调试。

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
  "practice": {"n_items": 12, "correct_count": 9, /* ... */},
  "formal": {"n_items": 36, "correct_count": 28, /* ... */},
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
  "timer_y": 0.82,            // 计时器 y 位置（与 header_y 统一建议）
  "header_y": 0.82,           // 头部信息统一高度（倒计时与进度共用）
  "header_font_size": 0.04,   // 头部信息字号（倒计时与进度共用）
  "option_grid_center_y": -0.425 // 选项网格中心 y
}
```

其它可选键：`option_dx`, `option_dy`, `question_box_w`, `question_box_h` 等，用于进一步控制布局与缩放。

#### 顶部导航与进度对齐（高级）

为确保“进度”与右侧翻页箭头精确对齐，同时让题号在两箭头之间等间距排布，提供以下参数：

```jsonc
"layout": {
  // 箭头矩形位置与宽度（中心坐标与宽度，单位为 norm）
  "nav_arrow_x_right": 0.98,
  "nav_arrow_x_left": -0.98,
  "nav_arrow_w": 0.09,

  // 进度文本与右箭头矩形左边缘的间距
  "progress_right_margin": 0.01
}
```

进度文本将以 `header_y` 为纵坐标、在右侧显示，并与右箭头矩形左边缘保持 `progress_right_margin` 的水平距离；文本尝试右对齐（若 PsychoPy 版本不支持则忽略）。

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

- **练习部分时长**：从 10 分钟缩短为 **10 秒**
- **正式测试时长**：从 40 分钟缩短为 **25 秒**
- **倒计时显示**：正式部分剩余 **20 秒**时开始显示（正常模式为 10 分钟）
- **红色警告**：正式部分剩余 **10 秒**时倒计时变为红色（正常模式为 5 分钟）

此模式便于开发者快速验证倒计时显示逻辑、颜色变化和时间到期提醒功能。

## License

TBD
