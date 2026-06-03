# WebAgent Final Submission

本项目实现了一个网页多模态 Agent 系统，用于根据自然语言任务在真实浏览器环境中完成网页搜索、点击、输入、滚动和页面跳转等操作。系统结合本地开源 VLM/LLM、结构化 DOM 信息、页面截图和 Playwright 浏览器自动化工具，形成完整的网页任务执行闭环：

```text
TASK -> OBSERVE -> PLAN -> ACT -> CHECK_SUCCESS -> LOG
```

项目最终使用 Qwen2.5-VL-7B-Instruct 在云服务器上完成批量实验，并额外提供本地 Web UI 演示界面，用于展示自然语言任务到浏览器动作的可视化过程。

## 1. Project Structure

```text
web_agent_final_submission/
  web_agent/
    browser/              # Playwright 浏览器环境、动作执行、页面观察
    agent/                # Planner 与 Agent Runner
    models/               # 本地模型客户端、Prompt 构造、JSON 动作解析
    eval/                 # 任务加载与成功条件判断
    utils/                # 日志与文件工具

  examples/
    demo_local_llm_planner.py    # 本地 Qwen2.5-VL Agent 单任务入口
    run_all_local_llm.py         # 本地模型批量实验入口
    demo_mock_llm_planner.py     # 无 GPU mock 调试入口
    demo_json_parser.py          # JSON 解析器测试
    demo_web_task.py             # WebUI 轻量演示入口

  eval/
    tasks.yaml                   # 实验任务配置

  results/
    qwen25vl_*.csv               # 批量实验统计结果
    figures/                     # 成功率与平均步数图表
    final/                       # 整理后的实验配置、表格与案例
    webui_runs/                  # 本地 Web UI 演示记录

  traces/
    3B失败样例/                  # Qwen2.5-VL-3B 失败案例
    web_agent_traces60次批量实验提取/

  webui/
    app.py                       # Gradio 交互式演示界面
    browser_demo_agent.py        # WebUI fallback 演示执行器

  docs/
    final_experiment_report.md   # 最终实验报告

  requirements.txt
  requirements_webui.txt
  README_final.md
```

## 2. Environment Setup

建议使用 Python 3.10 或以上版本。基础依赖包括 Playwright 和 PyYAML：

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

如果需要运行 Web UI 演示，还需要安装额外依赖：

```bash
pip install -r requirements_webui.txt
```

Windows PowerShell 示例：

```powershell
cd web_agent_final_submission
python -m playwright install chromium
```

## 3. Task Configuration

任务配置位于：

```text
eval/tasks.yaml
```

每个任务包含起始 URL、自然语言指令、成功条件和最大步数。例如：

```yaml
- id: wiki_search_web_agent
  site: wikipedia
  url: "https://en.wikipedia.org/wiki/Main_Page"
  instruction: "On English Wikipedia, search for the exact query 'Web agent' and open the article page for Web agent."
  search_query: "Web agent"
  success_condition:
    type: url_contains
    value: "/wiki/Web_agent"
  max_steps: 15
```

支持的成功条件包括：

```text
url_contains
text_contains
title_contains
element_text_contains
manual_check
```

## 4. Running the Agent

### 4.1 Mock Agent Check

该入口不需要 GPU，用于验证浏览器、任务加载、动作执行和日志保存流程：

```bash
python examples/demo_mock_llm_planner.py --task-id wiki_search_web_agent_results --headless
```

### 4.2 Local Qwen2.5-VL Agent

云服务器批量实验使用 Qwen2.5-VL-7B-Instruct：

```bash
export VLM_MODEL_PATH=/data1/xiangkun/MODELS/Qwen2.5-VL-7B-Instruct

CUDA_VISIBLE_DEVICES=0 python examples/demo_local_llm_planner.py \
  --task-id wiki_search_web_agent_results \
  --model "$VLM_MODEL_PATH" \
  --headless \
  --use-screenshot \
  --max-steps 12 \
  --max-new-tokens 128 \
  --max-dom-chars 3000 \
  --max-elements 20 \
  --post-action-sleep 1
```

运行后会生成：

```text
traces/<run_name>/
  events.jsonl
  summary.json
  screenshots/
```

## 5. Web UI Demo

项目提供 Gradio Web UI，用于最终展示自然语言任务输入、浏览器自动操作、动作日志和截图。

Windows 本地启动：

```powershell
cd web_agent_final_submission
python webui\app.py --server-name 127.0.0.1 --server-port 7860
```

浏览器打开：

```text
http://127.0.0.1:7860
```

演示时建议选择 `browser_demo_fallback`，并取消勾选 Headless，使浏览器窗口可见。Web UI 主要用于可视化展示，不参与最终批量实验成功率统计。

## 6. Experimental Results

最终批量实验使用 Qwen2.5-VL-7B-Instruct，覆盖 Wikipedia 与 GitHub 两类网站、6 个搜索类任务。

### 6.1 Summary by Input Mode

| Input Mode | Runs | Success | Failed | Success Rate | Avg. Steps |
| --- | ---: | ---: | ---: | ---: | ---: |
| screenshot+DOM | 60 | 60 | 0 | 100% | 3.87 |
| DOM-only | 31 | 31 | 0 | 100% | 4.19 |

### 6.2 Notes

- `screenshot+DOM` 是最终主实验设置。
- `DOM-only` 是对照实验，用于分析结构化 DOM 信息本身的有效性。
- `traces/3B失败样例/` 保存了 Qwen2.5-VL-3B-Instruct 的失败案例：模型连续输出 `type Web agent`，未完成点击搜索框和按 Enter 提交流程，最终达到 `max_steps=12`。
- Web UI 中 Playwright locator 文档任务受到真人验证/反爬拦截影响，作为外部环境失败案例记录，不计入批量实验。

详细实验分析见：

```text
docs/final_experiment_report.md
```

## 7. Important Files

```text
docs/final_experiment_report.md
results/final/table_summary_by_mode.md
results/final/table_summary_by_task_and_mode.md
results/figures/success_rate_by_mode.png
results/figures/avg_steps_by_mode.png
results/webui_runs/
traces/3B失败样例/
```

## 8. Reproducibility

本项目不包含模型权重和 Python 虚拟环境。复现实验时需要单独准备 Qwen2.5-VL-7B-Instruct 权重，并通过 `--model` 或 `VLM_MODEL_PATH` 指定模型路径。实验日志、截图、CSV 汇总和最终报告已随项目保留。
