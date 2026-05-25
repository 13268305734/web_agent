# Stage 3A Fix 2 Overlay

这个补丁修两个新问题：

## 1. 成功条件与 Mock 行为不匹配

原来的 `wiki_search_web_agent` 任务要求 URL 包含 `Web_agent`，但 mock planner 只做到：

```text
click -> type -> press -> wait
```

Wikipedia 实际会进入搜索页，例如：

```text
https://zh.wikipedia.org/wiki/Special:Search?search=Web+agent&go=Go&ns0=1
```

这个 URL 不包含 `Web_agent`，所以 success checker 必然失败。

本补丁新增了专门给 Stage 3A 验证链路用的任务文件：

```text
eval/tasks_stage3a.yaml
```

默认任务为：

```text
wiki_search_web_agent_results
```

成功条件改为：

```yaml
url_contains: "search=Web+agent"
```

这样验证的是“搜索流程是否成功提交并到达结果页”，不是“是否打开词条详情页”。

## 2. trace 目录重名

原来的 `now_id()` 只有秒级精度，快速连续跑 `search/noisy/malformed_once` 时可能写入同一个 trace 目录。

本补丁把 trace 命名改为：

```text
stage3a_mock_{task_id}_{mock_mode}_{YYYYMMDD_HHMMSS_microseconds}
```

并增加 `make_unique_dir()` 防止目录重名。

## 覆盖方式

把压缩包解压到项目根目录，也就是包含这些目录的位置：

```text
web_agent/
examples/
eval/
```

## 推荐验证命令

覆盖后直接运行：

```bash
python examples/demo_mock_llm_planner.py --headless
python examples/demo_mock_llm_planner.py --headless --mock-mode noisy
python examples/demo_mock_llm_planner.py --headless --mock-mode malformed_once
```

也可以显式写：

```bash
python examples/demo_mock_llm_planner.py --tasks-path eval/tasks_stage3a.yaml --task-id wiki_search_web_agent_results --headless
```

如果你想继续用旧的 `eval/tasks.yaml`，也可以：

```bash
python examples/demo_mock_llm_planner.py --tasks-path eval/tasks.yaml --task-id wiki_search_web_agent --headless
```

但要确保旧任务的 success condition 和 mock planner 实际动作一致。
