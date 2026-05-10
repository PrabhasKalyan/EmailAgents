"""Thin wrapper around Gemini for JSON / text completion."""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GEMINI_API_KEY, GEMINI_MODEL


_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")
    from google import genai
    _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def complete_text(prompt, retries=2, json_mode=False):
    last = None
    for i in range(retries + 1):
        try:
            kwargs = {"model": GEMINI_MODEL, "contents": prompt}
            if json_mode:
                kwargs["config"] = {"response_mime_type": "application/json"}
            resp = _get_client().models.generate_content(**kwargs)
            return (resp.text or "").strip()
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def _strip_trailing_commas(s):
    return re.sub(r",(\s*[\]}])", r"\1", s)


def complete_json(prompt, retries=2):
    raw = complete_text(prompt, retries=retries, json_mode=True)
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    for candidate in (cleaned, _strip_trailing_commas(cleaned)):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if m:
        return json.loads(_strip_trailing_commas(m.group(0)))
    raise json.JSONDecodeError("Could not parse Gemini JSON", cleaned, 0)
