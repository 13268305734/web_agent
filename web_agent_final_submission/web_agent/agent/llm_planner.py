from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from web_agent.models.base import BaseModelClient
from web_agent.models.mock_client import MockModelClient
from web_agent.models.prompt_builder import build_planner_prompt
from web_agent.models.json_parser import parse_model_action


class LLMPlanner:
    """Planner that asks a model client for the next JSON action.

    Stage 3A uses MockModelClient by default. Later, replace it with a real
    local model client while keeping the same planner interface.

    Expected public interface:
        plan(task, observation, history) -> action dict

    This mirrors RuleBasedPlanner so it can be plugged into the existing
    AgentRunner or used directly in examples/demo_mock_llm_planner.py.
    """

    def __init__(
        self,
        model_client: Optional[BaseModelClient] = None,
        *,
        include_dom: bool = True,
        use_screenshot: bool = False,
        max_dom_chars: int = 3500,
        max_elements: int = 60,
    ) -> None:
        self.model_client = model_client or MockModelClient()
        self.include_dom = include_dom
        self.use_screenshot = use_screenshot
        self.max_dom_chars = max_dom_chars
        self.max_elements = max_elements

        self.last_prompt: str = ""
        self.last_raw_output: str = ""

    def plan(
        self,
        task: Any,
        observation: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        history = history or []

        prompt = build_planner_prompt(
            task,
            observation,
            history,
            max_dom_chars=self.max_dom_chars,
            max_elements=self.max_elements,
            include_dom=self.include_dom,
        )
        self.last_prompt = prompt

        images: Optional[List[str]] = None
        screenshot_path = observation.get("screenshot_path")
        if self.use_screenshot and screenshot_path and Path(str(screenshot_path)).exists():
            images = [str(screenshot_path)]

        raw_output = self.model_client.generate(prompt, images=images)
        self.last_raw_output = str(raw_output)

        action = parse_model_action(
            raw_output,
            clickable_elements=observation.get("clickable_elements", []),
        )
        return action

    # Compatibility aliases for possible runner variants.
    def decide(
        self,
        task: Any,
        observation: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        return self.plan(task, observation, history)

    def __call__(
        self,
        task: Any,
        observation: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        return self.plan(task, observation, history)
