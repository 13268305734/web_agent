from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Mapping, Optional


def get_field(obj: Any, key: str, default: Any = None) -> Any:
    """Get a field from dict-like or object-like task records."""
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def compact_text(text: Any, max_chars: int = 4000) -> str:
    if text is None:
        return ""
    value = str(text)
    if len(value) <= max_chars:
        return value
    return value[:max_chars] + f"\n...[truncated {len(value) - max_chars} chars]"


def format_clickable_elements(
    elements: Optional[Iterable[Dict[str, Any]]],
    max_elements: int = 60,
) -> str:
    if not elements:
        return "(no clickable elements extracted)"

    lines: List[str] = []
    for i, element in enumerate(elements):
        if i >= max_elements:
            lines.append(f"... ({i} shown, more elements omitted)")
            break

        element_id = element.get("element_id", element.get("id", i + 1))
        tag = element.get("tag", "")
        text = compact_text(element.get("text", ""), 80).replace("\n", " ")
        aria_label = compact_text(element.get("aria_label", ""), 80).replace("\n", " ")
        placeholder = compact_text(element.get("placeholder", ""), 80).replace("\n", " ")
        href = compact_text(element.get("href", ""), 80).replace("\n", " ")

        bbox = element.get("bbox") or {}
        bbox_text = ""
        if isinstance(bbox, Mapping):
            bbox_text = (
                f"x={bbox.get('x')}, y={bbox.get('y')}, "
                f"w={bbox.get('width')}, h={bbox.get('height')}"
            )

        lines.append(
            f'- [{element_id}] tag={tag} text="{text}" '
            f'aria_label="{aria_label}" placeholder="{placeholder}" '
            f'href="{href}" bbox=({bbox_text})'
        )

    return "\n".join(lines)


def format_history(history: Optional[List[Dict[str, Any]]], max_items: int = 8) -> str:
    if not history:
        return "(no previous actions)"

    recent = history[-max_items:]
    lines: List[str] = []
    for item in recent:
        safe_item = {
            "step": item.get("step", item.get("step_id")),
            "url": item.get("url"),
            "action": item.get("action"),
            "result": item.get("result"),
            "success_check": item.get("success_check"),
        }
        lines.append(json.dumps(safe_item, ensure_ascii=False, default=str))
    return "\n".join(lines)


def build_planner_prompt(
    task: Any,
    observation: Dict[str, Any],
    history: Optional[List[Dict[str, Any]]] = None,
    *,
    max_dom_chars: int = 3500,
    max_elements: int = 60,
    include_dom: bool = True,
) -> str:
    """Build a strict prompt for a web navigation planner.

    This prompt is designed for both:
    - MockModelClient in Stage 3A
    - real local LLM/VLM clients in later stages
    """
    task_id = get_field(task, "id", "")
    site = get_field(task, "site", "")
    instruction = get_field(task, "instruction", "")
    success_condition = get_field(task, "success_condition", {})

    current_url = observation.get("url", "")
    title = observation.get("title", "")
    screenshot_path = observation.get("screenshot_path", "")
    dom_text = compact_text(observation.get("dom_text", ""), max_dom_chars)
    clickable_elements = format_clickable_elements(
        observation.get("clickable_elements", []),
        max_elements=max_elements,
    )
    history_text = format_history(history)

    dom_block = dom_text if include_dom else "(DOM text omitted by planner setting)"

    return f"""You are a web navigation agent.

Your job is to choose exactly ONE next browser action to help complete the task.

# Strict Output Rules
- Output exactly ONE JSON object.
- Do not output Markdown.
- Do not output explanations outside JSON.
- Do not call APIs.
- Do not write code.
- Do not invent tools.
- Do not output multiple actions in one response.
- Use only one of the allowed actions listed below.
- Prefer element_id over screen coordinates.
- Use click_xy only when no suitable element_id exists.
- If the page already satisfies the task, output finish.
- If you are unsure, output wait.

# Action Decision Rules
- Use the current page, clickable elements, DOM text, and recent history to decide the next step.
- If you need to search, first click the search input, then type the query, then press Enter.
- If the last action clicked a search input, the next action should usually be type.
- If the last action typed a search query, the next action should usually be press Enter or click a Search button.
- Do not repeat the exact same action on the exact same element more than two times.
- When the success condition is satisfied, output finish.

# Task Metadata
task_id: {task_id}
site: {site}

# Task Instruction
{instruction}

# Success Condition
{json.dumps(success_condition, ensure_ascii=False, default=str)}

# Current Page
url: {current_url}
title: {title}
screenshot_path: {screenshot_path}

# Clickable Elements
{clickable_elements}

# DOM Text
{dom_block}

# Recent History
{history_text}

# Allowed Actions

1. Click an extracted element:
{{"thought": "I need to click the search input.", "action": "click", "element_id": 3}}

2. Click coordinates only if no element_id works:
{{"thought": "No extracted element matches, so I will click by coordinates.", "action": "click_xy", "x": 300, "y": 500}}

3. Type into the currently focused input:
{{"thought": "I need to type the search query.", "action": "type", "text": "Web agent"}}

4. Press a keyboard key:
{{"thought": "I need to submit the search.", "action": "press", "key": "Enter"}}

5. Scroll:
{{"thought": "I need to see more results.", "action": "scroll", "direction": "down"}}

6. Wait:
{{"thought": "I need to wait for the page to load.", "action": "wait", "seconds": 2}}

7. Finish when the task is complete:
{{"thought": "The page satisfies the success condition.", "action": "finish", "answer": "Done"}}

# FINAL OUTPUT REQUIREMENT

Your response must start with {{ and end with }}.
Do not explain your reasoning.
Do not describe the page.
Do not list steps.
Do not output Markdown.
Do not output multiple JSON objects.


Now output exactly one JSON object for the next action.
"""

