# Stage 3A: Mock LLM Planner Integration

这个覆盖包用于在现有 Stage 2 项目上新增“模型 Planner 框架”，但暂时不接真实本地模型。

## 本阶段目标

Stage 3A 完成的是：

```text
任务配置
  ↓
浏览器观察 observation
  ↓
PromptBuilder 构造模型输入
  ↓
MockModelClient 模拟模型输出
  ↓
JSONParser 解析动作
  ↓
LLMPlanner 返回 action
  ↓
Playwright 执行动作
  ↓
success_checker 判断成功
  ↓
日志和截图记录
```

本阶段不需要 GPU，不下载模型，不调用 API。

## 新增文件

```text
web_agent/
  models/
    __init__.py
    base.py
    mock_client.py
    prompt_builder.py
    json_parser.py

  agent/
    llm_planner.py

examples/
  demo_mock_llm_planner.py
  demo_json_parser.py
```

## 覆盖方式

把本压缩包解压到你们当前项目根目录，也就是包含 `web_agent/`、`examples/`、`eval/` 的目录。

例如：

```bash
cd web_agent_stage1
unzip web_agent_stage3a_overlay.zip
```

或者手动把压缩包里的 `web_agent/` 和 `examples/` 合并进去。

## 运行前检查

先确认 Stage 2 仍然能跑：

```bash
python examples/demo_agent_loop.py --task-id wiki_search_web_agent --headless
```

## 运行 Stage 3A

先测试 JSON parser：

```bash
python examples/demo_json_parser.py
```

再运行 Mock LLM Planner：

```bash
python examples/demo_mock_llm_planner.py --task-id wiki_search_web_agent --headless
```

如果想模拟模型输出带 Markdown 代码块：

```bash
python examples/demo_mock_llm_planner.py --task-id wiki_search_web_agent --headless --mock-mode noisy
```

如果想测试模型第一次输出非法文本时 parser 能否兜底：

```bash
python examples/demo_mock_llm_planner.py --task-id wiki_search_web_agent --headless --mock-mode malformed_once
```

运行后查看：

```text
traces/stage3a_mock_xxx/events.jsonl
traces/stage3a_mock_xxx/summary.json
traces/stage3a_mock_xxx/screenshots/
```

## 后续 Stage 3B 怎么接真实模型

只需要新增一个真实模型客户端，例如：

```text
web_agent/models/transformers_vlm_client.py
```

并实现：

```python
class TransformersVLMClient(BaseModelClient):
    def generate(self, prompt: str, images=None, **kwargs) -> str:
        ...
```

然后把：

```python
LLMPlanner(model_client=MockModelClient())
```

替换成：

```python
LLMPlanner(model_client=TransformersVLMClient(...))
```

AgentRunner、PromptBuilder、JSONParser 都不用大改。
