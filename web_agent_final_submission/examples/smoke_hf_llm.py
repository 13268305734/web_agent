import argparse
import json
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-3B-Instruct")
    parser.add_argument("--max-new-tokens", type=int, default=256)
    args = parser.parse_args()

    print(f"Loading model: {args.model}")
    print("CUDA available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("GPU:", torch.cuda.get_device_name(0))

    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        trust_remote_code=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype="auto",
        device_map="auto",
        trust_remote_code=True,
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a web navigation agent. "
                "You must output exactly one JSON object and no extra text."
            ),
        },
        {
            "role": "user",
            "content": """
Task: Search for Web agent on Wikipedia and reach the Web agent page.

Current URL: https://www.wikipedia.org/
Clickable elements:
[12] input placeholder="Search Wikipedia" selector="#searchInput"
[13] button text="Search"

History: []

Allowed actions:
click, type, press, scroll, wait, finish

Output JSON format:
{
  "thought": "...",
  "action": "click | type | press | scroll | wait | finish",
  "element_id": 12,
  "text": "...",
  "key": "Enter",
  "seconds": 1
}
""",
        },
    ]

    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = tokenizer([text], return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=args.max_new_tokens,
            do_sample=False,
        )

    generated = outputs[0][inputs.input_ids.shape[-1]:]
    response = tokenizer.decode(generated, skip_special_tokens=True)

    print("\n=== MODEL OUTPUT ===")
    print(response)

    # 尝试粗略解析 JSON
    start = response.find("{")
    end = response.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            obj = json.loads(response[start:end+1])
            print("\n=== PARSED JSON ===")
            print(json.dumps(obj, ensure_ascii=False, indent=2))
        except Exception as e:
            print("\nJSON parse failed:", repr(e))


if __name__ == "__main__":
    main()
