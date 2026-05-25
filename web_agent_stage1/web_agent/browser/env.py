from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from web_agent.browser.actions import execute_action as run_action
from web_agent.browser.observation import extract_clickable_elements, get_dom_text
from web_agent.config.settings import (
    DEFAULT_ACTION_TIMEOUT_MS,
    DEFAULT_NAVIGATION_TIMEOUT_MS,
    DEFAULT_TRACE_DIR,
    DEFAULT_VIEWPORT,
    MAX_DOM_TEXT_CHARS,
)
from web_agent.utils.file_utils import ensure_dir, utc_timestamp_for_filename
from web_agent.utils.logger import JsonlLogger


class WebBrowserEnv:
    """Playwright browser environment for Stage 1 web agent.

    This class intentionally avoids any LLM/VLM logic. It only provides
    observation and action execution APIs that can be used by a future agent.
    """

    def __init__(
        self,
        *,
        trace_dir: Optional[str | Path] = None,
        headless: bool = False,
        viewport: Optional[Dict[str, int]] = None,
        slow_mo_ms: int = 100,
        navigation_timeout_ms: int = DEFAULT_NAVIGATION_TIMEOUT_MS,
        action_timeout_ms: int = DEFAULT_ACTION_TIMEOUT_MS,
    ):
        self.headless = headless
        self.viewport = viewport or DEFAULT_VIEWPORT
        self.slow_mo_ms = slow_mo_ms
        self.navigation_timeout_ms = navigation_timeout_ms
        self.action_timeout_ms = action_timeout_ms

        self.trace_dir = ensure_dir(trace_dir or (DEFAULT_TRACE_DIR / f"run_{utc_timestamp_for_filename()}"))
        self.screenshot_dir = ensure_dir(self.trace_dir / "screenshots")
        self.log_path = self.trace_dir / "events.jsonl"
        self.logger = JsonlLogger(self.log_path)

        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        self.step_id = 0
        self.last_clickable_elements: List[Dict[str, Any]] = []

    def start(self, headless: Optional[bool] = None) -> "WebBrowserEnv":
        """Start Chromium and open a blank page."""
        if headless is not None:
            self.headless = headless

        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo_ms,
        )
        self.context = self.browser.new_context(viewport=self.viewport)
        self.context.set_default_timeout(self.action_timeout_ms)
        self.context.set_default_navigation_timeout(self.navigation_timeout_ms)
        self.page = self.context.new_page()

        self.logger.event(
            step_id=self.step_id,
            event="start",
            result={"success": True, "message": "Browser started"},
            extra={"headless": self.headless, "viewport": self.viewport},
        )
        return self

    def open_url(self, url: str) -> Dict[str, Any]:
        page = self._require_page()
        self.step_id += 1
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=self.navigation_timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                # Some pages keep long-polling connections. domcontentloaded is enough for stage 1.
                pass

            screenshot_path = self.get_screenshot(name=f"step_{self.step_id:03d}_open.png")
            result = {"success": True, "message": f"Opened URL: {url}"}
            self.logger.event(
                step_id=self.step_id,
                event="open_url",
                url=self.current_url(),
                title=self.title(),
                action={"action": "open_url", "url": url},
                result=result,
                screenshot_path=screenshot_path,
            )
            return result
        except Exception as exc:
            result = {"success": False, "message": f"Failed to open URL: {url}", "error": repr(exc)}
            self.logger.event(
                step_id=self.step_id,
                event="open_url",
                url=self.current_url(safe=True),
                title=self.title(safe=True),
                action={"action": "open_url", "url": url},
                result=result,
                error=repr(exc),
            )
            return result

    def get_screenshot(self, path: Optional[str | Path] = None, name: Optional[str] = None) -> str:
        page = self._require_page()
        if path is None:
            filename = name or f"step_{self.step_id:03d}.png"
            path = self.screenshot_dir / filename
        path = Path(path)
        ensure_dir(path.parent)
        page.screenshot(path=str(path), full_page=True)
        return str(path)

    def get_dom_text(self, max_chars: int = MAX_DOM_TEXT_CHARS) -> str:
        page = self._require_page()
        return get_dom_text(page, max_chars=max_chars)

    def extract_clickable_elements(self) -> List[Dict[str, Any]]:
        page = self._require_page()
        elements = extract_clickable_elements(page)
        self.last_clickable_elements = elements
        return elements

    def get_observation(self, *, save_screenshot: bool = True) -> Dict[str, Any]:
        page = self._require_page()
        screenshot_path = None
        if save_screenshot:
            screenshot_path = self.get_screenshot(name=f"step_{self.step_id:03d}_observe.png")

        dom_text = self.get_dom_text()
        clickable_elements = self.extract_clickable_elements()

        observation = {
            "url": page.url,
            "title": self.title(),
            "screenshot_path": screenshot_path,
            "dom_text": dom_text,
            "clickable_elements": clickable_elements,
        }

        self.logger.event(
            step_id=self.step_id,
            event="observation",
            url=observation["url"],
            title=observation["title"],
            screenshot_path=screenshot_path,
            result={
                "success": True,
                "message": "Observation captured",
                "dom_text_chars": len(dom_text),
                "clickable_count": len(clickable_elements),
            },
        )
        return observation

    def execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        page = self._require_page()
        self.step_id += 1

        if not self.last_clickable_elements:
            self.last_clickable_elements = self.extract_clickable_elements()

        result = run_action(
            page,
            action,
            clickable_elements=self.last_clickable_elements,
            timeout_ms=self.action_timeout_ms,
        )

        # Let the browser settle a little. This helps screenshots and next observations.
        try:
            page.wait_for_load_state("domcontentloaded", timeout=3000)
        except Exception:
            pass

        try:
            screenshot_path = self.get_screenshot(name=f"step_{self.step_id:03d}_after_{action.get('action', 'action')}.png")
        except Exception:
            screenshot_path = None

        # Refresh elements after the action for the next step.
        try:
            self.last_clickable_elements = self.extract_clickable_elements()
        except Exception:
            pass

        self.logger.event(
            step_id=self.step_id,
            event="execute_action",
            url=self.current_url(safe=True),
            title=self.title(safe=True),
            action=action,
            result=result,
            screenshot_path=screenshot_path,
            error=result.get("error"),
        )
        return result

    def title(self, safe: bool = False) -> str:
        try:
            return self._require_page().title()
        except Exception:
            if safe:
                return ""
            raise

    def current_url(self, safe: bool = False) -> str:
        try:
            return self._require_page().url
        except Exception:
            if safe:
                return ""
            raise

    def close(self) -> None:
        self.step_id += 1
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            self.logger.event(
                step_id=self.step_id,
                event="close",
                result={"success": True, "message": "Browser closed"},
            )
        except Exception as exc:
            self.logger.event(
                step_id=self.step_id,
                event="close",
                result={"success": False, "message": "Failed to close browser", "error": repr(exc)},
                error=repr(exc),
            )

    def _require_page(self) -> Page:
        if self.page is None:
            raise RuntimeError("Browser page is not initialized. Call env.start() first.")
        return self.page

    def __enter__(self) -> "WebBrowserEnv":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
