from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from web_agent.eval.task_loader import TaskConfig


@dataclass
class PlannerOutput:
    """One planner decision.

    The action is passed directly to WebBrowserEnv.execute_action unless action is finish.
    """

    action: Dict[str, Any]
    thought: str = ""
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thought": self.thought,
            "confidence": self.confidence,
            "action": self.action,
            "metadata": self.metadata,
        }


class BasePlanner:
    """Planner interface for rule-based, local LLM, and local VLM planners."""

    name = "base"

    def reset(self, task: TaskConfig) -> None:
        """Reset planner state before running a new task."""

    def plan(
        self,
        *,
        task: TaskConfig,
        observation: Dict[str, Any],
        history: List[Dict[str, Any]],
        success_check: Optional[Dict[str, Any]] = None,
    ) -> PlannerOutput:
        raise NotImplementedError
