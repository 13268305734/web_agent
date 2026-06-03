#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gradio Web UI for interactive WebAgent demos.

Two execution modes are provided:
1) project_agent_cli: call the original examples/demo_local_llm_planner.py with a
   natural-language --task argument. Use this when your original agent entry has
   been adapted to accept --task.
2) browser_demo_fallback: a lightweight Playwright-based browser operator for
   reliable live demos. It is not used for quantitative evaluation.
"""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Generator, List, Tuple

# Make project root importable when launched as `python webui/app.py`.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from webui.browser_demo_agent import run_browser_demo_agent


def _latest_image(run_dir: str | Path) -> str | None:
    p = Path(run_dir)
    if not p.exists():
        return None
    imgs = sorted(p.glob("step_*.png"))
    return str(imgs[-1]) if imgs else None


def _format_command(cmd: List[str], env: dict) -> str:
    env_prefix = ""
    if env.get("CUDA_VISIBLE_DEVICES"):
        env_prefix = f"CUDA_VISIBLE_DEVICES={env['CUDA_VISIBLE_DEVICES']} "
    return env_prefix + " ".join(shlex.quote(c) for c in cmd)


def run_project_agent_cli(
    task: str,
    model_path: str,
    gpu_id: str,
    headless: bool,
    max_steps: int,
    max_new_tokens: int,
    max_dom_chars: int,
    max_elements: int,
    post_action_sleep: float,
) -> Generator[Tuple[str, str | None], None, None]:
    """Stream output from the original project CLI."""
    script = PROJECT_ROOT / "examples" / "demo_local_llm_planner.py"
    if not script.exists():
        yield (f"❌ 找不到原始入口：`{script}`。请切换到 `browser_demo_fallback` 模式，或确认补丁已覆盖到项目根目录。", None)
        return

    cmd = [
        sys.executable,
        str(script),
        "--task",
        task,
        "--model",
        model_path,
        "--use-screenshot",
        "--max-steps",
        str(max_steps),
        "--max-new-tokens",
        str(max_new_tokens),
        "--max-dom-chars",
        str(max_dom_chars),
        "--max-elements",
        str(max_elements),
        "--post-action-sleep",
        str(post_action_sleep),
    ]
    if headless:
        cmd.append("--headless")

    env = os.environ.copy()
    if model_path:
        env["VLM_MODEL_PATH"] = model_path
    if gpu_id.strip():
        env["CUDA_VISIBLE_DEVICES"] = gpu_id.strip()

    lines = ["## Project Agent CLI", "", "```bash", _format_command(cmd, env), "```", ""]
    yield ("\n".join(lines), None)

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as e:
        yield ("\n".join(lines + [f"❌ 启动失败：{type(e).__name__}: {e}"]), None)
        return

    last_emit = time.time()
    assert proc.stdout is not None
    for raw in proc.stdout:
        lines.append(raw.rstrip())
        if time.time() - last_emit > 0.3:
            yield ("\n".join(lines[-180:]), None)
            last_emit = time.time()
    rc = proc.wait()
    if rc == 0:
        lines.append("\n✅ 原项目 Agent 运行结束。")
    else:
        lines.append(
            "\n❌ 原项目 Agent 返回非零退出码。若看到 `unrecognized arguments: --task`，说明原始入口还没支持自由文本任务；请使用 Browser Demo Fallback 模式演示，或手动把 planner 的任务输入改为 args.task。"
        )
    yield ("\n".join(lines[-220:]), None)


def run_ui_task(
    task: str,
    mode: str,
    model_path: str,
    gpu_id: str,
    headless: bool,
    max_steps: int,
    max_new_tokens: int,
    max_dom_chars: int,
    max_elements: int,
    post_action_sleep: float,
):
    task = (task or "").strip()
    if not task:
        yield "请输入自然语言任务。", None, ""
        return

    if mode == "project_agent_cli":
        for log, img in run_project_agent_cli(
            task, model_path, gpu_id, headless, max_steps, max_new_tokens, max_dom_chars, max_elements, post_action_sleep
        ):
            yield log, img, ""
        return

    # Fallback mode: reliable live browser demo.
    yield "正在启动 Browser Demo Fallback...", None, ""
    result = run_browser_demo_agent(task, headless=headless, slow_mo_ms=int(max(0, post_action_sleep * 1000)))
    latest = _latest_image(result.run_dir)
    artifact_text = f"运行目录：`{result.run_dir}`\n\n结果文件：`{Path(result.run_dir) / 'result.md'}`"
    yield result.to_markdown(), latest, artifact_text


def build_app():
    try:
        import gradio as gr
    except Exception as e:  # pragma: no cover
        raise SystemExit(
            "Gradio is not installed. Install it with:\n"
            "    pip install gradio\n"
            f"Original error: {e}"
        )

    default_model = os.environ.get("VLM_MODEL_PATH", "/data1/xiangkun/MODELS/Qwen2.5-VL-7B-Instruct")

    with gr.Blocks(title="WebAgent Interactive Demo") as demo:
        gr.Markdown(
            "# WebAgent 交互式演示控制台\n"
            "输入自然语言任务，选择原项目 Agent 或稳定演示兜底模式，实时生成操作日志与截图。"
        )
        with gr.Row():
            with gr.Column(scale=1):
                task = gr.Textbox(
                    label="自然语言任务",
                    lines=4,
                    value="在百度搜索 Qwen2.5-VL，并打开第一个可信结果",
                    placeholder="例如：去 Wikipedia 搜索 WebAgent，并打开相关页面总结第一段",
                )
                mode = gr.Radio(
                    choices=["browser_demo_fallback", "project_agent_cli"],
                    value="browser_demo_fallback",
                    label="运行模式",
                    info="project_agent_cli 调原始 VLM/LLM 入口；fallback 用轻量 Playwright 保证演示可见。",
                )
                model_path = gr.Textbox(label="VLM/LLM 模型路径", value=default_model)
                gpu_id = gr.Textbox(label="CUDA_VISIBLE_DEVICES", value=os.environ.get("CUDA_VISIBLE_DEVICES", "1"))
                headless = gr.Checkbox(label="Headless（演示时建议关闭；云服务器可配 noVNC）", value=False)
                with gr.Accordion("高级参数", open=False):
                    max_steps = gr.Slider(1, 30, value=12, step=1, label="max_steps")
                    max_new_tokens = gr.Slider(32, 1024, value=128, step=32, label="max_new_tokens")
                    max_dom_chars = gr.Slider(500, 20000, value=3000, step=500, label="max_dom_chars")
                    max_elements = gr.Slider(5, 100, value=20, step=1, label="max_elements")
                    post_action_sleep = gr.Slider(0, 5, value=1, step=0.1, label="post_action_sleep / slow_mo 秒")
                run_btn = gr.Button("开始运行", variant="primary")
            with gr.Column(scale=2):
                log = gr.Markdown(label="日志 / 动作轨迹")
                screenshot = gr.Image(label="最新截图", type="filepath")
                artifacts = gr.Markdown(label="输出文件")

        examples = [
            ["去 Wikipedia 搜索 WebAgent，并打开相关页面总结第一段", "browser_demo_fallback"],
            ["在百度搜索 Qwen2.5-VL，并打开第一个可信结果", "browser_demo_fallback"],
            ["去 Playwright 官网搜索 locator 文档", "browser_demo_fallback"],
        ]
        gr.Examples(examples=examples, inputs=[task, mode])

        run_btn.click(
            run_ui_task,
            inputs=[task, mode, model_path, gpu_id, headless, max_steps, max_new_tokens, max_dom_chars, max_elements, post_action_sleep],
            outputs=[log, screenshot, artifacts],
        )
    return demo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-name", default=os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0"))
    parser.add_argument("--server-port", type=int, default=int(os.environ.get("GRADIO_SERVER_PORT", "7860")))
    parser.add_argument("--share", action="store_true")
    args = parser.parse_args()
    app = build_app()
    app.launch(server_name=args.server_name, server_port=args.server_port, share=args.share)


if __name__ == "__main__":
    main()
