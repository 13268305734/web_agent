#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Lightweight browser demo agent for WebAgent project demos.

This module is intentionally self-contained. It provides a reliable live-browser
fallback for classroom/demo scenarios where the full VLM/LLM planner is slow,
GPU-heavy, or temporarily unavailable. It does NOT replace the original
multi-modal planner used for quantitative experiments.

Typical use:
    python examples/demo_web_task.py --task "在百度搜索 Qwen2.5-VL，并打开第一个可信结果" --headed
"""
from __future__ import annotations

import json
import os
import re
import time
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus


@dataclass
class DemoStep:
    step: int
    action: str
    detail: str
    url: str = ""
    screenshot: str = ""
    ok: bool = True
    error: str = ""


@dataclass
class DemoResult:
    task: str
    mode: str
    ok: bool
    run_dir: str
    final_url: str
    final_answer: str
    steps: List[DemoStep]

    def to_markdown(self) -> str:
        lines = [
            f"# Web UI Demo Run",
            "",
            f"- Task: `{self.task}`",
            f"- Mode: `{self.mode}`",
            f"- Status: {'SUCCESS' if self.ok else 'FAILED'}",
            f"- Final URL: {self.final_url or '(none)'}",
            "",
            "## Steps",
        ]
        for s in self.steps:
            status = "✅" if s.ok else "❌"
            shot = f" | screenshot: `{Path(s.screenshot).name}`" if s.screenshot else ""
            lines.append(f"{s.step}. {status} **{s.action}** — {s.detail}{shot}")
        lines += ["", "## Final answer", "", self.final_answer or "(no final answer)"]
        return "\n".join(lines)


def _now_run_dir(root: str | Path = "results/webui_runs") -> Path:
    ts = time.strftime("%Y%m%d_%H%M%S")
    run_dir = Path(root) / f"run_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _normalize_task(task: str) -> str:
    return re.sub(r"\s+", " ", (task or "").strip())


def _extract_between_keywords(task: str, keys: List[str]) -> Optional[str]:
    # Match patterns like "搜索 XXX，并..." or "search XXX and ...".
    for key in keys:
        pattern = rf"{re.escape(key)}\s*[:：]?\s*(.+?)(?:，|,|。|；|;|并|然后|再| and | then |$)"
        m = re.search(pattern, task, flags=re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            candidate = re.sub(r"^(一下|一下子|内容|东西|相关|关于)", "", candidate).strip()
            candidate = re.sub(r"(的内容|相关页面|相关资料|官网|文档)$", "", candidate).strip()
            if candidate:
                return candidate
    return None


def infer_demo_plan(task: str) -> Dict[str, Any]:
    """Infer a simple browser plan from a natural-language demo task."""
    t = _normalize_task(task)
    low = t.lower()

    query = _extract_between_keywords(t, ["搜索", "查找", "检索", "search", "look up", "find"])
    if not query:
        # Remove common instruction words as a best-effort query.
        query = re.sub(
            r"(请|帮我|帮忙|打开|进入|去|在|用|搜索|查找|检索|并|然后|总结|第一段|第一个|可信结果|相关页面|官网|文档|内容)",
            " ",
            t,
            flags=re.IGNORECASE,
        )
        query = re.sub(r"\s+", " ", query).strip() or t

    # Target site / search engine selection.
    site = "bing"
    if any(k in low for k in ["wikipedia", "维基", "wiki"]):
        site = "wikipedia"
    elif "百度" in t or "baidu" in low:
        site = "baidu"
    elif "playwright" in low:
        site = "playwright_docs"
        if "playwright" not in query.lower():
            query = f"Playwright {query}"

    open_first = any(k in low for k in ["打开第一个", "第一个结果", "first result", "open first", "打开相关页面", "打开页面"])
    summarize = any(k in low for k in ["总结", "摘要", "第一段", "summarize", "summary", "归纳"])

    if site == "wikipedia":
        start_url = f"https://en.wikipedia.org/wiki/Special:Search?search={quote_plus(query)}"
    elif site == "baidu":
        start_url = f"https://www.baidu.com/s?wd={quote_plus(query)}"
    elif site == "playwright_docs":
        # Avoid Google CAPTCHA; Bing works better on servers.
        start_url = f"https://www.bing.com/search?q={quote_plus('site:playwright.dev/docs ' + query)}"
        open_first = True if "文档" in t or "docs" in low or "官网" in t else open_first
    else:
        start_url = f"https://www.bing.com/search?q={quote_plus(query)}"

    return {
        "task": t,
        "query": query,
        "site": site,
        "start_url": start_url,
        "open_first": open_first,
        "summarize": summarize,
    }


def _safe_screenshot(page: Any, run_dir: Path, step_no: int) -> str:
    path = run_dir / f"step_{step_no:02d}.png"
    try:
        page.screenshot(path=str(path), full_page=False)
        return str(path)
    except Exception:
        return ""


def _record(steps: List[DemoStep], page: Any, run_dir: Path, action: str, detail: str, ok: bool = True, error: str = "") -> None:
    step_no = len(steps) + 1
    shot = _safe_screenshot(page, run_dir, step_no)
    url = ""
    try:
        url = page.url
    except Exception:
        pass
    steps.append(DemoStep(step=step_no, action=action, detail=detail, url=url, screenshot=shot, ok=ok, error=error))


def _click_first_search_result(page: Any, site: str) -> bool:
    selectors = []
    if site == "bing" or site == "playwright_docs":
        selectors += ["li.b_algo h2 a", "#b_results h2 a"]
    if site == "baidu":
        selectors += ["#content_left h3 a", "h3.t a", "div.result h3 a"]
    if site == "wikipedia":
        selectors += [".mw-search-result-heading a", ".searchresult a", "ul.mw-search-results li a"]
    selectors += ["main a:visible", "a:visible"]

    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                href = loc.get_attribute("href") or ""
                text = (loc.inner_text(timeout=2000) or "").strip()
                if href.startswith("javascript") or href == "#":
                    continue
                loc.click(timeout=6000)
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                page.wait_for_timeout(1000)
                return True
        except Exception:
            continue
    return False


def _extract_readable_text(page: Any, limit_chars: int = 1200) -> str:
    try:
        # Prefer article-like paragraphs.
        texts = page.locator("article p, main p, #content p, .mw-parser-output > p, p").all_inner_texts(timeout=5000)
    except Exception:
        texts = []
    cleaned: List[str] = []
    for text in texts:
        text = re.sub(r"\s+", " ", text or "").strip()
        if len(text) >= 50 and not text.lower().startswith(("cookie", "privacy", "advertisement")):
            cleaned.append(text)
        if sum(len(x) for x in cleaned) > limit_chars:
            break
    if cleaned:
        return "\n\n".join(cleaned)[:limit_chars]
    try:
        body = page.locator("body").inner_text(timeout=5000)
        return re.sub(r"\s+", " ", body).strip()[:limit_chars]
    except Exception:
        return ""


def run_browser_demo_agent(
    task: str,
    headless: bool = False,
    slow_mo_ms: int = 300,
    timeout_ms: int = 30000,
    run_root: str | Path = "results/webui_runs",
    browser: str = "chromium",
) -> DemoResult:
    """Run a small natural-language browser demo with Playwright."""
    task = _normalize_task(task)
    run_dir = _now_run_dir(run_root)
    steps: List[DemoStep] = []
    final_answer = ""
    final_url = ""
    ok = False

    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        msg = (
            "Playwright is not installed or browsers are missing. Install with:\n"
            "    pip install playwright\n"
            "    python -m playwright install chromium\n"
            f"\nOriginal error: {e}"
        )
        result = DemoResult(task, "browser_demo_fallback", False, str(run_dir), "", msg, steps)
        _write_result(run_dir, result)
        return result

    plan = infer_demo_plan(task)
    page = None
    try:
        with sync_playwright() as p:
            browser_type = getattr(p, browser)
            br = browser_type.launch(headless=headless, slow_mo=slow_mo_ms)
            context = br.new_context(viewport={"width": 1366, "height": 820}, locale="zh-CN")
            page = context.new_page()
            page.set_default_timeout(timeout_ms)

            page.goto(plan["start_url"], wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(1000)
            _record(steps, page, run_dir, "open/search", f"打开搜索页：{plan['site']}；关键词：{plan['query']}")

            if plan["open_first"]:
                clicked = _click_first_search_result(page, plan["site"])
                _record(steps, page, run_dir, "click", "打开第一个搜索结果" if clicked else "未找到可点击的第一个结果", ok=clicked)

            # Small scroll to make live operation visible.
            try:
                page.mouse.wheel(0, 650)
                page.wait_for_timeout(600)
                _record(steps, page, run_dir, "scroll", "向下滚动页面，展示页面内容")
            except Exception as e:
                _record(steps, page, run_dir, "scroll", "滚动失败", ok=False, error=str(e))

            text = _extract_readable_text(page)
            final_url = page.url
            if plan["summarize"]:
                first_para = text.split("\n\n")[0] if text else "未能提取到可读正文。"
                final_answer = f"已完成搜索并打开页面。页面首段/主要内容摘要：\n\n{first_para[:900]}"
            else:
                final_answer = f"已完成任务。搜索关键词：{plan['query']}。当前页面：{final_url}"

            _record(steps, page, run_dir, "finish", "任务流程结束")
            ok = True
            context.close()
            br.close()
    except Exception as e:
        err = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        if page is not None:
            try:
                final_url = page.url
                _record(steps, page, run_dir, "error", "执行过程中出错", ok=False, error=err[:1000])
            except Exception:
                pass
        final_answer = "执行失败：" + err[:1500]
        ok = False

    result = DemoResult(task, "browser_demo_fallback", ok, str(run_dir), final_url, final_answer, steps)
    _write_result(run_dir, result)
    return result


def _write_result(run_dir: Path, result: DemoResult) -> None:
    with open(run_dir / "result.json", "w", encoding="utf-8") as f:
        json.dump(asdict(result), f, ensure_ascii=False, indent=2)
    with open(run_dir / "result.md", "w", encoding="utf-8") as f:
        f.write(result.to_markdown())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the lightweight WebAgent browser demo fallback.")
    parser.add_argument("--task", required=True, help="Natural-language browser task")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--headed", dest="headless", action="store_false", help="Show browser window")
    parser.set_defaults(headless=False)
    parser.add_argument("--slow-mo-ms", type=int, default=300)
    parser.add_argument("--run-root", default="results/webui_runs")
    args = parser.parse_args()

    r = run_browser_demo_agent(args.task, headless=args.headless, slow_mo_ms=args.slow_mo_ms, run_root=args.run_root)
    print(r.to_markdown())
