from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple


ALLOWED_ACTIONS = {"click", "click_xy", "type", "press", "scroll", "wait", "finish"}


def fallback_action(reason: str = "Invalid model output") -> Dict[str, Any]:
    return {
        "thought": reason,
        "action": "wait",
        "seconds": 1,
    }


def parse_model_action(
    raw_output: Any,
    clickable_elements: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Parse and normalize a model output into one executable action.

    Handles common real-model output patterns:
    - pure JSON
    - ```json fenced block
    - JSON object surrounded by explanation
    - target_id/value aliases
    - missing optional fields

    Returns a safe fallback wait action on failure.
    """
    try:
        if isinstance(raw_output, Mapping):
            data = dict(raw_output)
        else:
            text = str(raw_output).strip()
            candidate = extract_json_candidate(text)
            if not candidate:
                return fallback_action("No JSON object found in model output")
            data = json.loads(candidate)

        if not isinstance(data, Mapping):
            return fallback_action("Parsed model output is not a JSON object")

        normalized = normalize_action_dict(dict(data), clickable_elements)
        return normalized
    except Exception as exc:
        return fallback_action(f"Failed to parse model output: {exc}")


def extract_json_candidate(text: str) -> Optional[str]:
    """Extract a JSON object from raw text."""
    if not text:
        return None

    # Prefer fenced JSON.
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()

    # If the entire text is JSON.
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    # Otherwise find the first balanced {...} block.
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]

        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1].strip()

    return None


def normalize_action_dict(
    data: Dict[str, Any],
    clickable_elements: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Normalize aliases and validate action-specific fields."""
    # Common aliases from different prompts/models.
    if "action_type" in data and "action" not in data:
        data["action"] = data["action_type"]
    if "target_id" in data and "element_id" not in data:
        data["element_id"] = data["target_id"]
    if "target" in data and "element_id" not in data and is_int_like(data.get("target")):
        data["element_id"] = data["target"]
    if "value" in data and "text" not in data:
        data["text"] = data["value"]
    if "content" in data and "text" not in data:
        data["text"] = data["content"]

    action = str(data.get("action", "")).strip().lower()
    if action not in ALLOWED_ACTIONS:
        return fallback_action(f"Unsupported or missing action: {action!r}")

    thought = str(data.get("thought", data.get("reason", ""))).strip()

    if action == "click":
        element_id = coerce_int(data.get("element_id"))
        if element_id is None:
            # Convert coordinate click to click_xy if possible.
            x = coerce_float(data.get("x"))
            y = coerce_float(data.get("y"))
            if x is not None and y is not None:
                return {"thought": thought or "Click by coordinates.", "action": "click_xy", "x": x, "y": y}
            return fallback_action("Click action missing element_id")

        valid_ids = get_clickable_element_ids(clickable_elements)
        if valid_ids and element_id not in valid_ids:
            return fallback_action(f"element_id {element_id} is not in current clickable elements")

        return {"thought": thought, "action": "click", "element_id": element_id}

    if action == "click_xy":
        x = coerce_float(data.get("x"))
        y = coerce_float(data.get("y"))
        if x is None or y is None:
            return fallback_action("click_xy action missing x or y")
        return {"thought": thought, "action": "click_xy", "x": x, "y": y}

    if action == "type":
        text = data.get("text")
        if text is None:
            return fallback_action("type action missing text")
        return {"thought": thought, "action": "type", "text": str(text)}

    if action == "press":
        key = str(data.get("key", "Enter")).strip() or "Enter"
        return {"thought": thought, "action": "press", "key": key}

    if action == "scroll":
        direction = str(data.get("direction", "down")).strip().lower()
        if direction not in {"up", "down", "left", "right"}:
            direction = "down"
        return {"thought": thought, "action": "scroll", "direction": direction}

    if action == "wait":
        seconds = coerce_float(data.get("seconds"))
        if seconds is None:
            seconds = 1
        seconds = max(0.1, min(float(seconds), 10.0))
        return {"thought": thought, "action": "wait", "seconds": seconds}

    if action == "finish":
        answer = str(data.get("answer", data.get("finish_reason", ""))).strip()
        return {"thought": thought, "action": "finish", "answer": answer}

    return fallback_action("Unknown parser state")


def get_clickable_element_ids(
    clickable_elements: Optional[Iterable[Dict[str, Any]]],
) -> set[int]:
    ids: set[int] = set()
    if not clickable_elements:
        return ids
    for item in clickable_elements:
        if not isinstance(item, Mapping):
            continue
        element_id = coerce_int(item.get("element_id", item.get("id")))
        if element_id is not None:
            ids.add(element_id)
    return ids


def is_int_like(value: Any) -> bool:
    return coerce_int(value) is not None


def coerce_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        if isinstance(value, bool):
            return None
        return int(value)
    except Exception:
        match = re.search(r"-?\d+", str(value))
        return int(match.group(0)) if match else None


def coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        if isinstance(value, bool):
            return None
        return float(value)
    except Exception:
        match = re.search(r"-?\d+(?:\.\d+)?", str(value))
        return float(match.group(0)) if match else None
