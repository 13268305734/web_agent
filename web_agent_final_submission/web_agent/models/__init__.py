"""
Model clients and prompt utilities for Stage 3A.

Stage 3A does not load a real local LLM/VLM yet. It adds:
- BaseModelClient interface
- MockModelClient for offline integration testing
- Prompt builder
- Robust JSON action parser
"""

from .base import BaseModelClient
from .mock_client import MockModelClient
from .prompt_builder import build_planner_prompt
from .json_parser import parse_model_action, fallback_action

__all__ = [
    "BaseModelClient",
    "MockModelClient",
    "build_planner_prompt",
    "parse_model_action",
    "fallback_action",
]
