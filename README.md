# RAPM Dev - Raven's Advanced Progressive Matrices Task

[![Test and Build](https://github.com/EF-STUDY-FENG/rapm-dev/actions/workflows/auto-build.yml/badge.svg)](https://github.com/EF-STUDY-FENG/rapm-dev/actions/workflows/auto-build.yml)
[![GitHub release](https://img.shields.io/github/v/release/EF-STUDY-FENG/rapm-dev?include_prereleases)](https://github.com/EF-STUDY-FENG/rapm-dev/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

本项目是基于 PsychoPy 的 Raven 高级推理矩阵（RAPM）实验刺激呈现程序，用于心理学与认知科学研究中测量流体智力和抽象推理能力。

**主要特性：**

- ✅ 练习阶段（Set I）和正式测试（Set II）完整流程
- ✅ 精确的时间控制和倒计时提醒
- ✅ 灵活的题目导航和答案修改
- ✅ 自动数据记录（CSV + JSON 格式）
- ✅ 高度可配置的UI布局和实验参数

## Project Structure

```text
raven-dev/
├── stimuli/          # Stimulus files (images, videos, audio, etc.)
├── data/             # Output data files
├── src/              # Source code for experiments
├── configs/          # Configuration files
├── results/          # Analysis results
└── docs/             # Documentation
```

## 打包为可执行文件（.exe）

以下步骤可将本项目打包为 Windows 下可分发的独立程序。

### 前提条件

已在当前环境中安装 PsychoPy 及依赖（见下文"Installation"章节）。

### 打包步骤

运行一键打包脚本（PowerShell）：

```powershell
# 无控制台窗口、按目录输出（推荐分发）
pwsh -File build_exe.ps1

# 生成单文件 .exe（启动时解压较慢）
pwsh -File build_exe.ps1 -OneFile

# 调试时显示控制台窗口
pwsh -File build_exe.ps1 -Console
```

完成后，产物位于 `dist/` 目录下：`dist/RavenTask/`（目录模式）或 `dist/RavenTask.exe`（单文件模式）。

### 打包细节

- 脚本使用 PyInstaller，自动将 `configs/` 与 `stimuli/` 目录一并打包
- 代码已适配 PyInstaller（自动识别 `sys._MEIPASS` 与 `sys.executable`），运行时能正确定位资源文件
- 自定义图标示例：

```powershell
pwsh -File build_exe.ps1 -Icon .\assets\app.ico
```

### 常见问题

- 若提示未找到 `pyinstaller`，脚本会自动通过 `pip` 安装
- 首次运行单文件模式时启动较慢属于正常现象（需解压临时目录）

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

### 运行 Raven 任务

确保已激活 conda 环境（如果使用方法1）：

```bash
conda activate psychopy-dev
```

或确保已安装依赖（如果使用方法2）。

运行实验（练习集 + 正式集）：

```bash
python src/run_raven.py
```

### 显示模式

- **非 Debug 模式**：默认全屏运行
- **Debug 模式**：窗口化运行（1280x800），便于快速测试与调试

### 配置文件

实验使用两个独立的配置文件：

- **`configs/sequence.json`**: 实验序列配置（练习/正式阶段、题目模式、时间限制等）
- **`configs/layout.json`**: UI 布局配置（缩放、位置、字体等）

详见下文"配置说明"章节。

## 配置说明

### 实验序列配置 (sequence.json)

题目与序列配置通过 `configs/sequence.json` 设置。推荐使用"按模式自动生成"方式：

```jsonc
{
  "practice": {
    "set": "Set I",
    "time_limit_minutes": 10,
    "count": 12,
    "pattern": "stimuli/images/RAPM_t{XX}-{Y}.jpg"
  },
  "formal": {
    "set": "Set II",
    "time_limit_minutes": 40,
    "count": 36,
    "pattern": "stimuli/images/RAPM_{XX}-{Y}.jpg"
  },
  "answers_file": "stimuli/answers.txt",
  "debug_mode": false
}
```

说明：

- **`pattern`**: 使用 `{XX}` 表示两位序号（01, 02...），`{Y}` 表示图片索引（0=题干，1-8=选项）
- **`answers_file`**: 每行一个数字（1-8），前 12 行对应练习题，后续行对应正式题
- **`time_limit_minutes`**: 控制练习与正式阶段时长（默认：练习 10 分钟，正式 40 分钟）
- 若不使用 `pattern`，也可在 `practice/formal` 下提供 `items` 数组（字段：`id`、`question_image`、`options`、可选 `correct`）

### 实验流程

- **练习 Set I**: 10 分钟上限，作答后自动进入下一题
- **正式 Set II**: 40 分钟上限，顶部展示题号导航，可回看和修改已答题目
- **提交**: 最后一题作答后底部出现"提交答案"按钮（不自动提交），点击后保存结果到 `data/` 目录

### 数据输出格式

程序在被试点击"提交答案"后自动保存两个文件到 `data/` 目录：

#### CSV 文件: `raven_results_YYYYMMDD_HHMMSS.csv`

**列定义：** `participant_id, section, item_id, answer, correct, is_correct, time`

- **`participant_id`**: 被试编号
- **`section`**: 阶段名称（`practice` 或 `formal`）
- **`item_id`**: 题目编号
- **`answer`**: 被试选择的选项序号（1-8），未作答为空
- **`correct`**: 正确选项序号（1-8），如果配置中未提供则为空
- **`is_correct`**: 作答正确性
  - `1` = 正确
  - `0` = 错误
  - 空 = 未作答或无正确答案可比对
- **`time`**: 该题目耗时（秒），从该阶段开始计时到最后一次作答/修改的时间差

**示例：**

```csv
participant_id,section,item_id,answer,correct,is_correct,time
P001,practice,t01,3,3,1,5.234
P001,practice,t02,5,5,1,8.127
P001,formal,01,2,2,1,12.456
```

#### JSON 文件: `raven_session_YYYYMMDD_HHMMSS.json`

包含完整会话信息的 JSON 文件，用于后续分析：

```jsonc
{
  "participant": {
    "participant_id": "P001"
  },
  "time_created": "2025-01-09T10:30:00",
  "practice": {
    "set": "Set I",
    "time_limit_minutes": 10,
    "n_items": 12,
    "correct_count": 9
  },
  "formal": {
    "set": "Set II",
    "time_limit_minutes": 40,
    "n_items": 36,
    "correct_count": 28
  },
  "total_correct": 37,
  "total_items": 48
}
```

### 布局微调 (layout)

布局参数位于独立文件 `configs/layout.json`（必须存在）。

#### 外部参数覆盖机制

程序支持灵活的参数覆盖策略：

1. **基准配置**：内置的 `configs/layout.json` 包含所有必需参数（必须存在）
2. **外部覆盖**：可执行文件同目录的 `configs/layout.json` 可以只包含需要修改的参数
3. **自动合并**：外部文件中的参数会覆盖默认值，缺失的参数自动使用默认值

**示例**：如果只想修改字体和题干缩放，外部 `configs/layout.json` 只需：

```jsonc
{
  "font_main": "SimHei",
  "scale_question": 1.7
}
```

所有其他参数（如 `scale_option`、`nav_y` 等）将自动使用内置默认值。

#### 常用布局参数

```jsonc
{
  "scale_question": 1.584,      // 题干区域整体缩放
  "scale_option": 0.81,         // 选项区域缩放
  "nav_y": 0.90,                // 顶部导航条的 y 位置
  "header_y": 0.82,             // 头部信息统一高度（倒计时与进度共用）
  "header_font_size": 0.04,     // 头部信息字号
  "option_grid_center_y": -0.48,// 选项网格中心 y
  "font_main": "Microsoft YaHei" // UI 主字体
}
```

更多键请参考仓库内的 `configs/layout.json` 中的 `_descriptions` 注释。

#### 顶部导航与进度对齐（高级）

为确保“进度”与右侧翻页箭头精确对齐，同时让题号在两箭头之间等间距排布，`layout.json` 提供以下参数：

```jsonc
{
  // 箭头矩形位置与宽度（中心坐标与宽度，单位为 norm）
  "nav_arrow_x_right": 0.98,
  "nav_arrow_x_left": -0.98,
  "nav_arrow_w": 0.09,

  // 进度文本与右箭头矩形左边缘的间距
  "progress_right_margin": 0.01
}
```

进度文本将以 `header_y` 为纵坐标、在右侧显示，并与右箭头矩形左边缘保持 `progress_right_margin` 的水平距离；文本尝试右对齐（若 PsychoPy 版本不支持则忽略）。

### Debug 模式

程序支持 debug 模式用于快速测试倒计时功能：

**启用方式（两种方法任选其一）：**

1. **配置文件启用**：在 `configs/layout.json` 中设置：

   ```json
   "debug_mode": true
   ```

2. **被试编号为 0**：在被试信息对话框中输入 `participant_id` 为 `0`，自动进入 debug 模式

**Debug 模式特性：**

- **练习部分时长**：从 10 分钟缩短为 **10 秒**
- **正式测试时长**：从 40 分钟缩短为 **25 秒**
- **倒计时显示**：正式部分剩余 **20 秒**时开始显示（正常模式为 10 分钟）
- **红色警告**：正式部分剩余 **10 秒**时倒计时变为红色（正常模式为 5 分钟）
- **窗口模式**：自动使用窗口化运行（1280x800），便于调试

此模式便于开发者快速验证倒计时显示逻辑、颜色变化和时间到期提醒功能。

> **注意**：`debug_mode` 参数位于 `layout.json` 而非 `sequence.json`，因为它是运行时行为设置，不影响实验内容本身。用户可以通过外部 `configs/layout.json` 文件轻松启用/禁用调试模式，无需修改实验序列配置。

## CI/CD 与自动发布

本项目使用 GitHub Actions 实现自动化测试和构建：

### 自动测试 (Main 分支)

每次推送到 `main` 分支时自动运行：

- ✅ Python 语法检查
- ✅ 单元测试 (路径解析、配置加载等核心功能)
- ❌ **不构建** exe 文件
- ❌ **不创建** Release

### 自动构建与发布 (Tag)

创建并推送 tag 时触发完整流程：

```bash
# 创建版本标签
git tag v1.0.0
git push origin v1.0.0

# 或使用 release 前缀
git tag release-2025.1
git push origin release-2025.1
```

自动执行：

- ✅ 语法检查和单元测试
- ✅ PyInstaller 构建 Windows exe
- ✅ 上传构建产物 (Artifacts)
- ✅ 创建 GitHub Release 并附带 exe 文件

### Stimuli 目录说明

**重要**: `stimuli/` 目录被 `.gitignore` 排除，不会提交到 Git 仓库。

#### 开发者使用

在项目根目录创建 `stimuli/` 并添加刺激材料：

```text
stimuli/
├── images/
│   ├── RAPM_t01-1.jpg
│   ├── RAPM_t01-2.jpg
│   └── ...
└── answers.txt
```

#### 用户使用（下载 Release）

1. 从 [Releases](https://github.com/EF-STUDY-FENG/rapm-dev/releases) 下载最新的 `RavenTask.exe`
2. 在 exe 所在目录创建 `stimuli/` 文件夹
3. 添加刺激材料文件
4. 运行 exe

#### 智能路径检测

程序自动检测 stimuli 位置：

1. **开发模式**: 使用项目根目录的 `stimuli/`
2. **打包模式**:
   - 优先检查打包内的 `stimuli/` (可能为空)
   - 如果为空，自动回退到 exe 旁边的 `stimuli/` 目录
   - 确保 CI 构建和用户使用都能正常工作

## 测试

### 运行单元测试

```bash
python tests/test_raven_task.py
```

测试覆盖范围：

- 路径解析和资源定位
- 配置文件加载（sequence.json 和 layout.json）
- 布局参数合并机制
- Stimuli 目录空检测
- 答案文件解析
- 工具函数验证

当前测试状态：**9/9 通过** ✅

## License

本项目采用 MIT License 开源许可。详见 [LICENSE](./LICENSE)。
