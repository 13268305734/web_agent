from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseModelClient(ABC):
    """Base interface for local model clients.

    Later stages can implement this interface with:
    - Transformers local Qwen/InternVL/LLaVA client
    - vLLM HTTP client
    - Ollama client
    - FastAPI model service client

    Stage 3A only uses MockModelClient, so no GPU/model dependency is needed.
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        images: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> str:
        """Generate model text from a prompt and optional image paths.

        Args:
            prompt: Text prompt passed to the model.
            images: Optional local image paths. VLM clients may use these.
            **kwargs: Future generation parameters, e.g. temperature, max_tokens.

        Returns:
            Raw model output text. The caller is responsible for JSON parsing.
        """
        raise NotImplementedError
