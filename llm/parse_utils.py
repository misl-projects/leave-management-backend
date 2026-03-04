import json
import re
from typing import Any


def response_text(content: Any) -> str:
    """
    Normalize LangChain model content to plain text.
    Handles string, list chunks, or dict-like blocks.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()
    return str(content or "")


def _extract_json_candidate(text: str) -> str | None:
    # Strip markdown code fences if present.
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    # Find first balanced JSON object.
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for idx in range(start, len(text)):
        ch = text[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:idx + 1]
    return None


def parse_json_object(content: Any) -> dict:
    """
    Parse JSON object from model output that may include prose/markdown.
    Raises JSONDecodeError when no object can be parsed.
    """
    text = response_text(content).strip()
    if not text:
        raise json.JSONDecodeError("Empty model response", "", 0)

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        raise json.JSONDecodeError("JSON is not an object", text, 0)
    except json.JSONDecodeError:
        candidate = _extract_json_candidate(text)
        if not candidate:
            raise
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
        raise json.JSONDecodeError("Extracted JSON is not an object", candidate, 0)


def parse_choice(content: Any, allowed: set[str], default: str) -> str:
    """
    Parse a single classification token from model output.
    Works even if the model adds extra explanation.
    """
    text = response_text(content).strip().lower()
    if not text:
        return default

    # direct exact
    if text in allowed:
        return text

    # pull first allowed token from text
    for token in allowed:
        if re.search(rf"\b{re.escape(token)}\b", text):
            return token

    # try json fallback with common keys
    try:
        obj = parse_json_object(text)
        for key in ("decision", "result", "answer", "label", "classification"):
            value = obj.get(key)
            if isinstance(value, str):
                value_norm = value.strip().lower()
                if value_norm in allowed:
                    return value_norm
    except Exception:
        pass

    return default
