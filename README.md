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

默认：练习 Set I 10 分钟上限（示例占位题），正式 Set II 40 分钟上限。正式阶段顶部展示题号导航，可回看和修改已答题目；最后一题作答后底部出现“提交答案”按钮（不自动提交），点击后保存结果文件到 `data/` 目录，如：`raven_results_20250101_101530.csv`。

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

CSV 列：`section,item_id,answer`。

## License

TBD
