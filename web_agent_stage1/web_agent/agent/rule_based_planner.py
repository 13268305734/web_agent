from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from web_agent.agent.base import BasePlanner, PlannerOutput
from web_agent.eval.task_loader import TaskConfig


class RuleBasedPlanner(BasePlanner):
    """A simple deterministic planner used to validate the Agent Loop.

    This is not meant to be smart. It only proves that the project can:
    OBSERVE -> PLAN -> ACT -> CHECK_SUCCESS -> LOG.

    It tries to:
    1. click a search input
    2. type the task search_query
    3. press Enter
    4. wait
    5. finish if success checker passes
    """

    name = "rule_based"

    def __init__(self):
        self.phase = "need_click_search"

    def reset(self, task: TaskConfig) -> None:
        self.phase = "need_click_search"

    def plan(
        self,
        *,
        task: TaskConfig,
        observation: Dict[str, Any],
        history: List[Dict[str, Any]],
        success_check: Optional[Dict[str, Any]] = None,
    ) -> PlannerOutput:
        if success_check and success_check.get("success"):
            return PlannerOutput(
                thought="Success condition is already satisfied.",
                action={"action": "finish", "reason": success_check.get("reason", "success")},
            )

        query = self._extract_query(task)

        # Handle phase transitions based on history instead of assuming all actions worked.
        successful_actions = [
            h.get("action", {}).get("action")
            for h in history
            if h.get("result", {}).get("success")
        ]

        if "click" not in successful_actions:
            element_id = self._find_search_element(observation.get("clickable_elements", []), site=task.site)
            if element_id is not None:
                return PlannerOutput(
                    thought=f"Found a likely search input with element_id={element_id}.",
                    action={"action": "click", "element_id": element_id},
                    metadata={"query": query},
                )
            return PlannerOutput(
                thought="Could not find a search input. Scroll down and observe again.",
                action={"action": "scroll", "direction": "down"},
                confidence=0.4,
            )

        if "type" not in successful_actions:
            return PlannerOutput(
                thought=f"Type the search query: {query}",
                action={"action": "type", "text": query},
                metadata={"query": query},
            )

        if "press" not in successful_actions:
            return PlannerOutput(
                thought="Submit the search query with Enter.",
                action={"action": "press", "key": "Enter"},
            )

        wait_count = successful_actions.count("wait")
        if wait_count < 2:
            return PlannerOutput(
                thought="Wait for page navigation or search results to load.",
                action={"action": "wait", "seconds": 2},
            )

        # Some sites need one extra Enter or a click to search, but avoid looping forever.
        return PlannerOutput(
            thought="The simple rule-based planner has completed its fixed search routine.",
            action={"action": "finish", "reason": "rule_based_routine_completed"},
            confidence=0.5,
        )

    def _extract_query(self, task: TaskConfig) -> str:
        if task.search_query:
            return str(task.search_query)

        # Basic fallback: try to infer quoted text or text after "search for".
        instruction = task.instruction
        quoted = re.findall(r"['\"]([^'\"]+)['\"]", instruction)
        if quoted:
            return quoted[0]

        match = re.search(r"search\s+(?:for\s+)?(.+?)(?:\s+on\s+|\s+and\s+|$)", instruction, flags=re.I)
        if match:
            return match.group(1).strip()

        return instruction.strip()

    def _find_search_element(self, elements: List[Dict[str, Any]], site: str = "") -> Optional[int]:
        best_id = None
        best_score = -1

        for el in elements:
            tag = (el.get("tag") or "").lower()
            text = (el.get("text") or "").lower()
            aria = (el.get("aria_label") or "").lower()
            placeholder = (el.get("placeholder") or "").lower()
            input_type = (el.get("input_type") or "").lower()
            role = (el.get("role") or "").lower()
            selector = (el.get("selector") or "").lower()
            title = (el.get("title") or "").lower()

            score = 0

            if tag in {"input", "textarea"}:
                score += 5
            if input_type in {"search", "text"}:
                score += 3
            if "search" in placeholder:
                score += 5
            if "search" in aria:
                score += 5
            if "search" in selector:
                score += 3
            if "search" in text:
                score += 2
            if "search" in title:
                score += 2
            if role == "searchbox":
                score += 5

            # Site-specific small nudges.
            if site.lower() == "github":
                if "search github" in placeholder or "search or jump" in placeholder:
                    score += 5
            if site.lower() == "wikipedia":
                if "wikipedia" in placeholder or "wikipedia" in aria:
                    score += 2

            # Avoid choosing submit buttons before input boxes.
            if tag == "button" and best_score >= 5:
                score -= 3

            if score > best_score:
                best_score = score
                best_id = int(el["element_id"])

        if best_score <= 0:
            return None
        return best_id
