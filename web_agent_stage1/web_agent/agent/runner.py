from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from web_agent.agent.base import BasePlanner
from web_agent.browser import WebBrowserEnv
from web_agent.eval.success_checker import check_success
from web_agent.eval.task_loader import TaskConfig
from web_agent.utils.file_utils import ensure_dir, utc_timestamp_for_filename


@dataclass
class AgentRunResult:
    task_id: str
    success: bool
    total_steps: int
    trace_dir: str
    final_url: str = ""
    failure_reason: str = ""
    history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "success": self.success,
            "total_steps": self.total_steps,
            "trace_dir": self.trace_dir,
            "final_url": self.final_url,
            "failure_reason": self.failure_reason,
            "history": self.history,
        }


class AgentRunner:
    """Run an agent planner in an observe-plan-act-check loop."""

    def __init__(
        self,
        *,
        planner: BasePlanner,
        headless: bool = False,
        base_trace_dir: str | Path = "traces",
        slow_mo_ms: int = 100,
    ):
        self.planner = planner
        self.headless = headless
        self.base_trace_dir = Path(base_trace_dir)
        self.slow_mo_ms = slow_mo_ms

    def run_task(self, task: TaskConfig) -> AgentRunResult:
        trace_dir = ensure_dir(self.base_trace_dir / f"{task.id}_{utc_timestamp_for_filename()}")
        env = WebBrowserEnv(trace_dir=trace_dir, headless=self.headless, slow_mo_ms=self.slow_mo_ms)
        history: List[Dict[str, Any]] = []
        self.planner.reset(task)

        try:
            env.start()
            open_result = env.open_url(task.url)
            if not open_result.get("success"):
                return AgentRunResult(
                    task_id=task.id,
                    success=False,
                    total_steps=0,
                    trace_dir=str(trace_dir),
                    final_url=env.current_url(safe=True),
                    failure_reason=f"open_url failed: {open_result}",
                    history=history,
                )

            last_success_check: Dict[str, Any] = {
                "success": False,
                "reason": "not checked yet",
                "condition": task.success_condition,
            }

            for loop_index in range(1, task.max_steps + 1):
                observation = env.get_observation()
                last_success_check = check_success(observation, task.success_condition)

                if last_success_check.get("success"):
                    self._write_summary(
                        trace_dir,
                        task,
                        True,
                        loop_index - 1,
                        env.current_url(safe=True),
                        "success condition satisfied before next action",
                        history,
                    )
                    return AgentRunResult(
                        task_id=task.id,
                        success=True,
                        total_steps=loop_index - 1,
                        trace_dir=str(trace_dir),
                        final_url=env.current_url(safe=True),
                        history=history,
                    )

                planner_output = self.planner.plan(
                    task=task,
                    observation=observation,
                    history=history,
                    success_check=last_success_check,
                )
                action = planner_output.action

                if action.get("action") == "finish":
                    final_observation = env.get_observation()
                    final_check = check_success(final_observation, task.success_condition)
                    success = bool(final_check.get("success"))
                    reason = final_check.get("reason") if success else action.get("reason", "planner finished before success")
                    self._write_summary(
                        trace_dir,
                        task,
                        success,
                        loop_index - 1,
                        env.current_url(safe=True),
                        reason,
                        history,
                    )
                    return AgentRunResult(
                        task_id=task.id,
                        success=success,
                        total_steps=loop_index - 1,
                        trace_dir=str(trace_dir),
                        final_url=env.current_url(safe=True),
                        failure_reason="" if success else str(reason),
                        history=history,
                    )

                result = env.execute_action(action)
                step_record = {
                    "loop_index": loop_index,
                    "thought": planner_output.thought,
                    "confidence": planner_output.confidence,
                    "action": action,
                    "result": result,
                    "success_check_before_action": last_success_check,
                    "url_after_action": env.current_url(safe=True),
                    "title_after_action": env.title(safe=True),
                }
                history.append(step_record)

                env.logger.event(
                    step_id=env.step_id,
                    event="agent_step",
                    url=env.current_url(safe=True),
                    title=env.title(safe=True),
                    action=action,
                    result=result,
                    extra={
                        "loop_index": loop_index,
                        "planner": self.planner.name,
                        "thought": planner_output.thought,
                        "confidence": planner_output.confidence,
                        "success_check_before_action": last_success_check,
                    },
                    error=result.get("error"),
                )

                if not result.get("success"):
                    # Continue once or twice for recoverable failures, but stop on repeated failures.
                    recent_failures = [h for h in history[-3:] if not h.get("result", {}).get("success")]
                    if len(recent_failures) >= 3:
                        reason = "three recent action failures"
                        self._write_summary(
                            trace_dir,
                            task,
                            False,
                            loop_index,
                            env.current_url(safe=True),
                            reason,
                            history,
                        )
                        return AgentRunResult(
                            task_id=task.id,
                            success=False,
                            total_steps=loop_index,
                            trace_dir=str(trace_dir),
                            final_url=env.current_url(safe=True),
                            failure_reason=reason,
                            history=history,
                        )

            final_observation = env.get_observation()
            final_check = check_success(final_observation, task.success_condition)
            success = bool(final_check.get("success"))
            reason = final_check.get("reason", "max steps reached")
            if not success:
                reason = f"max_steps reached; last check: {reason}"

            self._write_summary(
                trace_dir,
                task,
                success,
                task.max_steps,
                env.current_url(safe=True),
                reason,
                history,
            )

            return AgentRunResult(
                task_id=task.id,
                success=success,
                total_steps=task.max_steps,
                trace_dir=str(trace_dir),
                final_url=env.current_url(safe=True),
                failure_reason="" if success else reason,
                history=history,
            )

        finally:
            env.close()

    def _write_summary(
        self,
        trace_dir: Path,
        task: TaskConfig,
        success: bool,
        total_steps: int,
        final_url: str,
        reason: str,
        history: List[Dict[str, Any]],
    ) -> None:
        summary = {
            "task": task.to_dict(),
            "planner": self.planner.name,
            "success": success,
            "total_steps": total_steps,
            "final_url": final_url,
            "reason": reason,
            "history": history,
        }
        with (trace_dir / "summary.json").open("w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
