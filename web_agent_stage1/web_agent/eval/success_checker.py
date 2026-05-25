from __future__ import annotations

from typing import Any, Dict, Iterable


def _norm(value: Any) -> str:
    return str(value or "").casefold()


def _contains(haystack: Any, needle: Any, case_sensitive: bool = False) -> bool:
    if case_sensitive:
        return str(needle or "") in str(haystack or "")
    return _norm(needle) in _norm(haystack)


def _element_texts(observation: Dict[str, Any]) -> Iterable[str]:
    for el in observation.get("clickable_elements", []) or []:
        parts = [
            el.get("text"),
            el.get("aria_label"),
            el.get("placeholder"),
            el.get("title"),
            el.get("href"),
            el.get("selector"),
        ]
        yield " ".join(str(p or "") for p in parts)


def check_success(observation: Dict[str, Any], success_condition: Dict[str, Any]) -> Dict[str, Any]:
    """Check whether a task is successful based on the latest observation.

    Supported conditions:
    - url_contains
    - text_contains
    - title_contains
    - element_text_contains
    - manual_check
    """
    condition_type = success_condition.get("type")
    expected = success_condition.get("value", "")
    case_sensitive = bool(success_condition.get("case_sensitive", False))

    if condition_type == "manual_check":
        return {
            "success": False,
            "reason": "manual_check requires human review; automatically marked as not completed",
            "condition": success_condition,
        }

    if condition_type == "url_contains":
        actual = observation.get("url", "")
        success = _contains(actual, expected, case_sensitive)
        return {
            "success": success,
            "reason": f"URL {'contains' if success else 'does not contain'} expected value: {expected!r}",
            "actual": actual,
            "condition": success_condition,
        }

    if condition_type == "title_contains":
        actual = observation.get("title", "")
        success = _contains(actual, expected, case_sensitive)
        return {
            "success": success,
            "reason": f"Title {'contains' if success else 'does not contain'} expected value: {expected!r}",
            "actual": actual,
            "condition": success_condition,
        }

    if condition_type == "text_contains":
        actual = observation.get("dom_text", "")
        success = _contains(actual, expected, case_sensitive)
        return {
            "success": success,
            "reason": f"Page text {'contains' if success else 'does not contain'} expected value: {expected!r}",
            "actual_preview": str(actual)[:500],
            "condition": success_condition,
        }

    if condition_type == "element_text_contains":
        combined = "\n".join(_element_texts(observation))
        success = _contains(combined, expected, case_sensitive)
        return {
            "success": success,
            "reason": f"Clickable element text {'contains' if success else 'does not contain'} expected value: {expected!r}",
            "actual_preview": combined[:500],
            "condition": success_condition,
        }

    return {
        "success": False,
        "reason": f"Unsupported success condition type: {condition_type!r}",
        "condition": success_condition,
    }
