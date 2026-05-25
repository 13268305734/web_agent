# Stage 3A Fix Overlay

这个补丁只修两个问题：

1. `MockModelClient` 第一步误判 `finish`
   - 原因：旧版 `_extract_history_actions()` 在整个 prompt 里搜 `"action": "..."`。
   - 但 prompt 后面的 `Allowed Actions` 示例里本来就有 `"press"` 和 `"wait"`。
   - 所以第一步会误以为已经执行过 press/wait，直接 finish。
   - 新版只从 `# Recent History` 区块解析历史动作。

2. `demo_mock_llm_planner.py` 的 `open_url` 失败处理
   - 旧版打开 URL 后只写日志，不判断是否失败。
   - 新版如果 `open_url` 明确返回 `{"success": false}` 或抛异常，会立即停止，并把问题记为 `open_url failed`。
   - 如果 `open_url` 返回 `None`，按 Stage 1 兼容逻辑视为成功。

## 覆盖方式

把本压缩包解压到项目根目录，也就是包含 `web_agent/`、`examples/`、`eval/` 的目录。

## 覆盖后验证

```bash
python examples/demo_json_parser.py
python examples/demo_mock_llm_planner.py --task-id wiki_search_web_agent --headless
python examples/demo_mock_llm_planner.py --task-id wiki_search_web_agent --headless --mock-mode noisy
python examples/demo_mock_llm_planner.py --task-id wiki_search_web_agent --headless --mock-mode malformed_once
```

正常情况下，第一步不应该再直接 `finish`，而应该先输出类似：

```json
{"action": "click", "element_id": ...}
```
