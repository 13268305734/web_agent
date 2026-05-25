# Web Multimodal Agent - Stage 2 Agent Loop Base

这是网页多模态 Agent 项目的阶段二代码：在阶段一浏览器自动化底座上，新增 **任务配置、成功判断、规则 Planner、Agent Runner**。

当前阶段仍然不接入具体大模型、不调用任何 API。目标是先完成完整工程闭环：

```text
TASK -> OBSERVE -> PLAN -> ACT -> CHECK_SUCCESS -> LOG
```

---

## 1. 建议你如何使用这个包

如果你已经有 `web_agent_stage1` 文件夹，推荐做法是：

1. 先备份或 git commit 阶段一。
2. 把 `web_agent_stage2_overlay.zip` 解压覆盖到 `web_agent_stage1` 里面。
3. 继续在同一个项目里开发，不要长期维护两个重复项目。

也可以直接使用 `web_agent_stage2_full.zip`，它是阶段一 + 阶段二的完整项目。

---

## 2. Project Structure

阶段二新增内容：

```text
web_agent/
  agent/
    __init__.py
    base.py
    rule_based_planner.py
    runner.py
  eval/
    __init__.py
    task_loader.py
    success_checker.py
eval/
  tasks.yaml
examples/
  run_task_config.py
  demo_success_check.py
  demo_agent_loop.py
  run_all_rule_based.py
```

阶段一已有内容仍保留：

```text
web_agent/
  browser/
    env.py
    actions.py
    observation.py
  utils/
    logger.py
    file_utils.py
  config/
    settings.py
examples/
  demo_search.py
  inspect_page.py
```

---

## 3. Environment Setup

建议使用 Python 3.10 或以上版本。

```bash
cd web_agent_stage2

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Windows PowerShell:

```powershell
cd web_agent_stage2

python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

Linux 服务器缺浏览器依赖时：

```bash
playwright install --with-deps chromium
```

---

## 4. Stage 1 Checks

先确认阶段一能力还在：

```bash
python examples/demo_search.py --headless
python examples/inspect_page.py https://www.wikipedia.org/ --headless
```

---

## 5. Stage 2 Checks

### 5.1 检查任务配置

```bash
python examples/run_task_config.py
```

查看单个任务：

```bash
python examples/run_task_config.py --task-id wiki_search_web_agent
```

### 5.2 检查成功条件

```bash
python examples/demo_success_check.py --headless
```

### 5.3 跑一个规则 Agent Loop

有图形界面：

```bash
python examples/demo_agent_loop.py --task-id wiki_search_web_agent
```

无图形界面服务器：

```bash
python examples/demo_agent_loop.py --task-id wiki_search_web_agent --headless
```

### 5.4 批量跑全部规则任务

```bash
python examples/run_all_rule_based.py --headless
```

---

## 6. Task YAML Format

任务配置文件在：

```text
eval/tasks.yaml
```

格式：

```yaml
- id: wiki_search_web_agent
  site: wikipedia
  url: "https://www.wikipedia.org/"
  instruction: "Search for Web agent on Wikipedia and open the result page."
  search_query: "Web agent"
  success_condition:
    type: "url_contains"
    value: "Web_agent"
  max_steps: 12
```

支持的成功条件：

```text
url_contains
text_contains
title_contains
element_text_contains
manual_check
```

---

## 7. Agent Runner

阶段二的运行逻辑：

```text
1. 打开任务起始 URL
2. get_observation()
3. check_success()
4. planner.plan()
5. env.execute_action()
6. 保存日志和截图
7. 循环直到成功 / finish / max_steps
```

规则 Planner 只是 baseline，用来验证完整闭环，不代表最终智能效果。

---

## 8. Outputs

运行后重点查看：

```text
traces/<task_id>_<timestamp>/
  events.jsonl
  summary.json
  screenshots/
```

批量运行会生成：

```text
traces/batch_rule_based_<timestamp>/
  batch_summary.json
  batch_summary.csv
```

---

## 9. 接下来第三阶段怎么接模型

后面接本地模型时，不需要改浏览器底座和任务系统，只需要新增 Planner：

```text
web_agent/agent/llm_planner.py
web_agent/models/local_model_client.py
```

建议接口：

```python
class BasePlanner:
    def plan(self, task, observation, history, success_check=None):
        ...
```

也就是让本地模型替代 `RuleBasedPlanner.plan()`，输出同样的动作 JSON：

```json
{
  "action": "click",
  "element_id": 3
}
```

支持动作仍然是：

```text
click
click_xy
type
press
scroll
wait
finish
```

---

## 10. 人工验收清单

阶段二完成后，你需要人工确认：

1. `eval/tasks.yaml` 是否符合你们真实实验设计。
2. 每个任务的 `success_condition` 是否合理。
3. `demo_agent_loop.py` 是否能跑完至少一个任务。
4. `traces/` 里是否有截图序列。
5. `events.jsonl` 是否记录了 action/result/success_check。
6. `summary.json` 是否能说明成功或失败原因。
7. 规则 Planner 成功率不用很高，但工程闭环必须完整。

