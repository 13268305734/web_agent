from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError


ActionResult = Dict[str, Any]


def _success(message: str, **extra: Any) -> ActionResult:
    return {"success": True, "message": message, "error": None, **extra}


def _failure(message: str, error: Optional[str] = None, **extra: Any) -> ActionResult:
    return {"success": False, "message": message, "error": error, **extra}


def _find_element(element_id: int, clickable_elements: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for item in clickable_elements:
        if int(item.get("element_id", -1)) == int(element_id):
            return item
    return None


def _bbox_center(element: Dict[str, Any]) -> Optional[tuple[float, float]]:
    bbox = element.get("bbox") or {}
    try:
        x = float(bbox["x"]) + float(bbox["width"]) / 2
        y = float(bbox["y"]) + float(bbox["height"]) / 2
        return x, y
    except Exception:
        return None


def execute_action(
    page: Page,
    action: Dict[str, Any],
    clickable_elements: Optional[List[Dict[str, Any]]] = None,
    timeout_ms: int = 10000,
) -> ActionResult:
    """Execute one browser action and always return a structured result."""
    clickable_elements = clickable_elements or {}
    action_name = (action.get("action") or "").strip().lower()

    try:
        if action_name == "click":
            return _click_by_element_id(page, action, list(clickable_elements), timeout_ms)

        if action_name == "click_xy":
            x = float(action["x"])
            y = float(action["y"])
            page.mouse.click(x, y)
            return _success(f"Clicked coordinate ({x:.1f}, {y:.1f})", x=x, y=y)

        if action_name == "type":
            text = str(action.get("text", ""))
            delay = int(action.get("delay", 0))
            page.keyboard.type(text, delay=delay)
            return _success(f"Typed text with length {len(text)}", text_length=len(text))

        if action_name == "press":
            key = str(action.get("key", ""))
            if not key:
                return _failure("Missing key for press action")
            page.keyboard.press(key)
            return _success(f"Pressed key: {key}", key=key)

        if action_name == "scroll":
            direction = str(action.get("direction", "down")).lower()
            amount = int(action.get("amount", 650))
            if direction == "down":
                page.mouse.wheel(0, amount)
            elif direction == "up":
                page.mouse.wheel(0, -amount)
            else:
                return _failure(f"Unsupported scroll direction: {direction}")
            return _success(f"Scrolled {direction}", direction=direction, amount=amount)

        if action_name == "wait":
            seconds = float(action.get("seconds", 1))
            if seconds < 0:
                return _failure("Wait seconds must be non-negative")
            time.sleep(seconds)
            return _success(f"Waited {seconds:.2f} seconds", seconds=seconds)

        return _failure(f"Unsupported action: {action_name}")

    except PlaywrightTimeoutError as exc:
        return _failure(f"Action timed out: {action_name}", error=str(exc))
    except Exception as exc:
        return _failure(f"Action failed: {action_name}", error=repr(exc))


def _click_by_element_id(
    page: Page,
    action: Dict[str, Any],
    clickable_elements: List[Dict[str, Any]],
    timeout_ms: int,
) -> ActionResult:
    raw_id = action.get("element_id")
    if raw_id is None:
        return _failure("Missing element_id for click action")

    try:
        element_id = int(raw_id)
    except Exception:
        return _failure(f"Invalid element_id: {raw_id}")

    element = _find_element(element_id, clickable_elements)
    if not element:
        return _failure(f"element_id={element_id} not found in current clickable_elements")

    selector = element.get("selector")
    selector_error = None

    if selector:
        try:
            locator = page.locator(selector).first
            locator.click(timeout=timeout_ms)
            return _success(
                f"Clicked element_id={element_id} by selector",
                element_id=element_id,
                selector=selector,
                fallback="none",
            )
        except Exception as exc:
            selector_error = repr(exc)

    center = _bbox_center(element)
    if not center:
        return _failure(
            f"Cannot click element_id={element_id}: no valid selector or bbox",
            error=selector_error,
            element_id=element_id,
        )

    x, y = center
    try:
        page.mouse.click(x, y)
        return _success(
            f"Clicked element_id={element_id} by bbox center after selector fallback",
            element_id=element_id,
            x=round(x, 2),
            y=round(y, 2),
            selector=selector,
            selector_error=selector_error,
            fallback="bbox_center",
        )
    except Exception as exc:
        return _failure(
            f"Failed to click element_id={element_id} by selector and bbox",
            error=f"selector_error={selector_error}; bbox_error={repr(exc)}",
            element_id=element_id,
            selector=selector,
        )
