from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Sequence, Any

import torch
from PIL import Image
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

try:
    from web_agent.models.base import BaseModelClient
except Exception:
    class BaseModelClient:
        pass


class LocalHFModelClient(BaseModelClient):
    """
    Local HuggingFace model client.

    Supports:
    1. Text-only causal LLMs, e.g. Qwen2.5-3B-Instruct
    2. Qwen2.5-VL models, e.g. Qwen2.5-VL-3B-Instruct

    This version does NOT require qwen-vl-utils.
    It reads screenshot files with PIL and passes them directly to AutoProcessor.
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen2.5-3B-Instruct",
        max_new_tokens: int = 256,
        temperature: float = 0.0,
        do_sample: bool = False,
        trust_remote_code: bool = True,
    ):
        self.model_name = model_name
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.do_sample = do_sample
        self.trust_remote_code = trust_remote_code
        self.max_pixels = int(os.environ.get("VLM_MAX_PIXELS", "1000000"))

        print(f"[LocalHFModelClient] Loading config: {model_name}")
        self.config = AutoConfig.from_pretrained(
            model_name,
            trust_remote_code=trust_remote_code,
        )
        self.model_type = str(getattr(self.config, "model_type", "")).lower()
        self.is_vlm = "qwen2_5_vl" in self.model_type or "qwen2_vl" in self.model_type

        if self.is_vlm:
            self._load_qwen_vl()
        else:
            self._load_text_llm()

        self.model.eval()
        print(f"[LocalHFModelClient] Model loaded. is_vlm={self.is_vlm}, model_type={self.model_type}")

    def _load_text_llm(self) -> None:
        print(f"[LocalHFModelClient] Loading tokenizer: {self.model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            trust_remote_code=self.trust_remote_code,
        )
        self.processor = None

        print(f"[LocalHFModelClient] Loading text model: {self.model_name}")
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype="auto",
            device_map="auto",
            trust_remote_code=self.trust_remote_code,
        )

    def _load_qwen_vl(self) -> None:
        try:
            from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
        except Exception as exc:
            raise RuntimeError(
                "Qwen2.5-VL dependencies are missing. Run:\n"
                "pip install -U transformers accelerate pillow\n"
                f"Original error: {exc}"
            )

        print(f"[LocalHFModelClient] Loading Qwen2.5-VL processor: {self.model_name}")
        self.processor = AutoProcessor.from_pretrained(
            self.model_name,
            trust_remote_code=self.trust_remote_code,
        )
        self.tokenizer = getattr(self.processor, "tokenizer", None)

        print(f"[LocalHFModelClient] Loading Qwen2.5-VL model: {self.model_name}")
        self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            self.model_name,
            torch_dtype="auto",
            device_map="auto",
            trust_remote_code=self.trust_remote_code,
        )

    def _model_device(self):
        try:
            return next(self.model.parameters()).device
        except Exception:
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def generate(self, prompt: str, images: Optional[Sequence[str]] = None) -> str:
        if self.is_vlm:
            return self._generate_vlm(prompt, images=images)
        return self._generate_text(prompt, images=images)

    def _generate_text(self, prompt: str, images: Optional[Sequence[str]] = None) -> str:
        if images:
            prompt = (
                prompt
                + "\n\nNote: screenshots were provided, but this is a text-only model. "
                  "Use the DOM and clickable element list."
            )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a web navigation agent. "
                    "You must output exactly one JSON object and no extra text. "
                    "Do not wrap the JSON in markdown."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        if hasattr(self.tokenizer, "apply_chat_template"):
            try:
                text = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
            except TypeError:
                text = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
        else:
            text = (
                "System: " + messages[0]["content"]
                + "\nUser: " + messages[1]["content"]
                + "\nAssistant:"
            )

        inputs = self.tokenizer([text], return_tensors="pt").to(self._model_device())

        generation_kwargs = {
            "max_new_tokens": self.max_new_tokens,
            "do_sample": self.do_sample,
        }
        if self.do_sample:
            generation_kwargs["temperature"] = self.temperature

        with torch.no_grad():
            outputs = self.model.generate(**inputs, **generation_kwargs)

        generated = outputs[0][inputs.input_ids.shape[-1]:]
        return self.tokenizer.decode(generated, skip_special_tokens=True).strip()

    def _load_image(self, image_path: str) -> Image.Image:
        p = Path(str(image_path)).expanduser()
        img = Image.open(p).convert("RGB")

        w, h = img.size
        pixels = w * h
        if pixels > self.max_pixels:
            scale = (self.max_pixels / pixels) ** 0.5
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            img = img.resize((new_w, new_h))

        return img

    def _generate_vlm(self, prompt: str, images: Optional[Sequence[str]] = None) -> str:
        image_paths = list(images or [])
        pil_images = [self._load_image(p) for p in image_paths]

        system_text = (
            "You are a web navigation agent controlling a browser. "
            "You will receive a webpage screenshot plus DOM/clickable element information. "
            "Choose the next browser action. "
            "You must output exactly one JSON object and no extra text. "
            "Do not wrap the JSON in markdown. "
            "Do not only describe the image. "
            "Do not say image loaded. "
            "Prefer using element_id from the clickable element list."
        )

        user_content: list[dict[str, Any]] = []
        for _ in pil_images:
            user_content.append({"type": "image"})
        user_content.append({"type": "text", "text": prompt})

        messages = [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_content},
        ]

        text = self.processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = self.processor(
            text=[text],
            images=pil_images if pil_images else None,
            padding=True,
            return_tensors="pt",
        ).to(self._model_device())

        generation_kwargs = {
            "max_new_tokens": self.max_new_tokens,
            "do_sample": self.do_sample,
        }
        if self.do_sample:
            generation_kwargs["temperature"] = self.temperature

        with torch.no_grad():
            outputs = self.model.generate(**inputs, **generation_kwargs)

        generated_ids = [
            output_ids[len(input_ids):]
            for input_ids, output_ids in zip(inputs.input_ids, outputs)
        ]

        response = self.processor.batch_decode(
            generated_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0].strip()

        return response

