from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from .base import BaseModelClient


class MockModelClient(BaseModelClient):
    """A fake model client for Stage 3A integration testing.

    It reads the prompt and returns JSON-like actions. This lets us test:
    - prompt construction
    - JSON parsing
    - planner integration
    - observe -> plan -> act loop

    No real model, GPU, API, or network access is required.

    Modes:
        search:
            Try to complete a search workflow:
            click search input -> type query -> press Enter -> wait -> finish.
        noisy:
            Same as search, but sometimes wraps JSON in Markdown code fences,
            simulating real model outputs.
        malformed_once:
            The first call returns malformed text to test parser fallback.
    """

    def __init__(self, mode: str = "search") -> None:
        self.mode = mode
        self.call_count = 0

    def generate(
        self,
        prompt: str,
        images: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> str:
        self.call_count += 1

        if self.mode == "malformed_once" and self.call_count == 1:
            return "I think we should click the search box first. action = click target 1"

        action = self._decide_search_action(prompt)

        raw = json.dumps(action, ensure_ascii=False)
        if self.mode == "noisy" and self.call_count % 2 == 0:
            return f"Here is the next action:\n```json\n{raw}\n```"
        return raw

    def _decide_search_action(self, prompt: str) -> Dict[str, Any]:
        query = self._extract_query(prompt)
        history_actions = self._extract_history_actions(prompt)

        # Important:
        # Do NOT scan the whole prompt for action names, because the "Allowed Actions"
        # section also contains examples such as {"action": "press"} and {"action": "wait"}.
        # We only read the JSON lines inside the "# Recent History" block.

        if "click" not in history_actions:
            search_element_id = self._find_search_element_id(prompt)
            if search_element_id is not None:
                return {
                    "thought": "I need to focus the search input first.",
                    "action": "click",
                    "element_id": search_element_id,
                }
            return {
                "thought": "I cannot find a clear search input, so I will scroll down to inspect more elements.",
                "action": "scroll",
                "direction": "down",
            }

        if "type" not in history_actions:
            return {
                "thought": f"I should type the search query: {query}",
                "action": "type",
                "text": query,
            }

        if "press" not in history_actions:
            return {
                "thought": "I should submit the search by pressing Enter.",
                "action": "press",
                "key": "Enter",
            }

        if "wait" not in history_actions:
            return {
                "thought": "I should wait for the page to load after submitting the search.",
                "action": "wait",
                "seconds": 2,
            }

        return {
            "thought": "The search was submitted and we have already waited for the result page.",
            "action": "finish",
            "answer": "Search workflow appears complete.",
        }

    @staticmethod
    def _extract_history_actions(prompt: str) -> List[str]:
        """Extract action names only from the '# Recent History' block.

        Previous version used a regex on the whole prompt. That accidentally matched
        the JSON examples in '# Allowed Actions', so the first step could be judged
        as if 'press' and 'wait' had already happened, causing immediate finish.
        """
        history_match = re.search(
            r"(?is)#\s*Recent\s+History\s*(.*?)(?:\n#\s*Allowed\s+Actions|\Z)",
            prompt,
        )
        if not history_match:
            return []

        history_block = history_match.group(1).strip()
        if not history_block or "no previous actions" in history_block.lower():
            return []

        actions: List[str] = []

        # Prefer parsing each history line as JSON because PromptBuilder writes
        # one compact JSON object per previous step.
        for line in history_block.splitlines():
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                item = json.loads(line)
                action_obj = item.get("action")
                if isinstance(action_obj, dict):
                    action = action_obj.get("action")
                    if action:
                        actions.append(str(action).strip().lower())
            except Exception:
                # Fall back to regex for partially malformed history lines.
                for action in re.findall(r'"action"\s*:\s*"([^"]+)"', line):
                    actions.append(action.strip().lower())

        return actions

    @staticmethod
    def _extract_query(prompt: str) -> str:
        """Extract a likely search query from the task instruction."""
        task_match = re.search(
            r"(?is)#\s*Task\s*Instruction\s*(.+?)(?:\n#|\Z)",
            prompt,
        )
        instruction = task_match.group(1).strip() if task_match else prompt

        patterns = [
            r'(?i)search\s+for\s+["“]?([^"\n“”]+?)["”]?(?:\s+on|\s+and|\.|$)',
            r'(?i)search\s+["“]?([^"\n“”]+?)["”]?(?:\s+on|\s+and|\.|$)',
            r'搜索\s*[“"]?([^。；;，,\n"”]+)[”"]?',
            r'查询\s*[“"]?([^。；;，,\n"”]+)[”"]?',
        ]
        for pattern in patterns:
            match = re.search(pattern, instruction)
            if match:
                query = match.group(1).strip()
                if query:
                    return query

        # Common fallback for the Stage 2 default task.
        if "web agent" in instruction.lower():
            return "Web agent"

        return "Web agent"

    @staticmethod
    def _find_search_element_id(prompt: str) -> Optional[int]:
        """Find the best search input element ID from prompt text.

        The prompt lines look like:
        - [3] tag=input text="..." aria_label="..." placeholder="Search" ...
        """
        candidate_lines = []
        for line in prompt.splitlines():
            if re.search(r"\[\d+\]", line) and "tag=" in line:
                candidate_lines.append(line)

        # Prefer input/textarea with search-related attributes.
        scored = []
        for line in candidate_lines:
            id_match = re.search(r"\[(\d+)\]", line)
            if not id_match:
                continue
            element_id = int(id_match.group(1))
            lower = line.lower()

            score = 0
            if "tag=input" in lower or "tag=textarea" in lower:
                score += 5
            if "search" in lower or "搜索" in lower:
                score += 4
            if "placeholder" in lower:
                score += 1
            if "button" in lower:
                score -= 2

            scored.append((score, element_id))

        if not scored:
            return None

        scored.sort(reverse=True)
        best_score, best_id = scored[0]
        return best_id if best_score > 0 else None
