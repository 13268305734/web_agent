from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from playwright.sync_api import Page

from web_agent.config.settings import MAX_CLICKABLE_ELEMENTS


CLICKABLE_QUERY = ",".join(
    [
        "a",
        "button",
        "input",
        "textarea",
        "select",
        "[role=button]",
        "[aria-label]",
        "[onclick]",
    ]
)


def _clean_text(value: Optional[str], max_len: int = 120) -> str:
    if not value:
        return ""
    value = re.sub(r"\s+", " ", value).strip()
    return value[:max_len]


def _selector_from_attrs(tag: str, attrs: Dict[str, str]) -> Optional[str]:
    """Build a practical selector from stable-looking attributes.

    This is best-effort. It does not need to be perfect because the action
    executor can fall back to coordinate clicks.
    """
    candidates = []

    element_id = attrs.get("id")
    if element_id:
        candidates.append(f"#{_css_escape(element_id)}")

    name = attrs.get("name")
    if name:
        candidates.append(f'{tag}[name="{_css_attr_escape(name)}"]')

    aria_label = attrs.get("aria_label")
    if aria_label:
        candidates.append(f'{tag}[aria-label="{_css_attr_escape(aria_label)}"]')

    placeholder = attrs.get("placeholder")
    if placeholder:
        candidates.append(f'{tag}[placeholder="{_css_attr_escape(placeholder)}"]')

    title = attrs.get("title")
    if title:
        candidates.append(f'{tag}[title="{_css_attr_escape(title)}"]')

    input_type = attrs.get("input_type")
    if tag == "input" and input_type:
        candidates.append(f'input[type="{_css_attr_escape(input_type)}"]')

    data_testid = attrs.get("data_testid")
    if data_testid:
        candidates.append(f'[data-testid="{_css_attr_escape(data_testid)}"]')

    return candidates[0] if candidates else tag


def _css_attr_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _css_escape(value: str) -> str:
    # Simple CSS identifier escape. For very complex ids, use attribute selector.
    if re.match(r"^[A-Za-z_][A-Za-z0-9_-]*$", value):
        return value
    return value.replace("\\", "\\\\").replace('"', '\\"')


def get_dom_text(page: Page, max_chars: int = 8000) -> str:
    """Return visible-ish page text plus a compact page title/url header."""
    try:
        body_text = page.locator("body").inner_text(timeout=3000)
    except Exception:
        try:
            body_text = page.content()
        except Exception:
            body_text = ""

    body_text = re.sub(r"\n{3,}", "\n\n", body_text).strip()
    title = ""
    try:
        title = page.title()
    except Exception:
        pass

    header = f"Title: {title}\nURL: {page.url}\n\n"
    text = header + body_text
    return text[:max_chars]


def extract_clickable_elements(page: Page, max_elements: int = MAX_CLICKABLE_ELEMENTS) -> List[Dict[str, Any]]:
    """Extract clickable/actionable elements with bounding boxes.

    The output is intentionally LLM-friendly and stable for later stages.
    """
    script = f"""
    () => {{
      const nodes = Array.from(document.querySelectorAll('{CLICKABLE_QUERY}'));
      const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
      const viewportHeight = window.innerHeight || document.documentElement.clientHeight;

      function visible(el) {{
        const style = window.getComputedStyle(el);
        if (!style) return false;
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
        const rect = el.getBoundingClientRect();
        if (!rect || rect.width <= 0 || rect.height <= 0) return false;
        if (rect.bottom < 0 || rect.right < 0 || rect.top > viewportHeight || rect.left > viewportWidth) return false;
        return true;
      }}

      function directText(el) {{
        const clone = el.cloneNode(true);
        Array.from(clone.children).forEach(child => child.remove());
        return (clone.innerText || clone.textContent || '').trim();
      }}

      return nodes
        .filter(visible)
        .slice(0, 300)
        .map((el, index) => {{
          const rect = el.getBoundingClientRect();
          const tag = el.tagName.toLowerCase();
          const attrs = {{
            id: el.getAttribute('id') || '',
            name: el.getAttribute('name') || '',
            aria_label: el.getAttribute('aria-label') || '',
            placeholder: el.getAttribute('placeholder') || '',
            href: el.getAttribute('href') || '',
            title: el.getAttribute('title') || '',
            input_type: el.getAttribute('type') || '',
            role: el.getAttribute('role') || '',
            data_testid: el.getAttribute('data-testid') || '',
          }};
          return {{
            raw_index: index,
            tag,
            text: directText(el) || el.innerText || el.value || '',
            attrs,
            bbox: {{
              x: rect.x,
              y: rect.y,
              width: rect.width,
              height: rect.height
            }}
          }};
        }});
    }}
    """

    try:
        raw_items = page.evaluate(script)
    except Exception:
        return []

    items: List[Dict[str, Any]] = []
    seen = set()

    for raw in raw_items:
        tag = raw.get("tag", "")
        attrs = raw.get("attrs", {}) or {}
        bbox = raw.get("bbox", {}) or {}
        width = float(bbox.get("width") or 0)
        height = float(bbox.get("height") or 0)
        if width <= 0 or height <= 0:
            continue

        text = _clean_text(raw.get("text"))
        aria_label = _clean_text(attrs.get("aria_label"))
        placeholder = _clean_text(attrs.get("placeholder"))
        href = _clean_text(attrs.get("href"), max_len=200)
        title = _clean_text(attrs.get("title"))
        role = _clean_text(attrs.get("role"))
        input_type = _clean_text(attrs.get("input_type"))

        # Deduplicate by approximate bbox + semantics.
        key = (
            tag,
            text,
            aria_label,
            placeholder,
            round(float(bbox.get("x") or 0)),
            round(float(bbox.get("y") or 0)),
            round(width),
            round(height),
        )
        if key in seen:
            continue
        seen.add(key)

        selector = _selector_from_attrs(tag, attrs)

        items.append(
            {
                "element_id": len(items) + 1,
                "tag": tag,
                "text": text,
                "aria_label": aria_label,
                "placeholder": placeholder,
                "href": href,
                "title": title,
                "role": role,
                "input_type": input_type,
                "selector": selector,
                "bbox": {
                    "x": round(float(bbox.get("x") or 0), 2),
                    "y": round(float(bbox.get("y") or 0), 2),
                    "width": round(width, 2),
                    "height": round(height, 2),
                },
            }
        )

        if len(items) >= max_elements:
            break

    return items
