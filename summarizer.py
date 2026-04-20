import json
import logging
import os
import re
import hashlib
import time
from pathlib import Path

from google import genai
from google.genai import types
from google.genai.errors import ClientError

logger = logging.getLogger(__name__)

# ── Cache directory ────────────────────────────────────────────────────────────
CACHE_DIR = Path(".cache") / "summaries"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Gemini settings ────────────────────────────────────────────────────────────
# Updated to Gemini 3.0 Preview as requested
MODEL_NAME = "gemini-3-flash-preview" 
MAX_OUTPUT_TOKENS = 1500 # Smaller for faster generation
TEMPERATURE = 0.1 # Very deterministic

# ── Optimized PROMPT ───────────────────────────────────────────────────────────
ANALYSIS_PROMPT = """\
You are a 'Plain English' privacy advocate. Analyze the privacy policy below for a typical consumer who does not understand legal jargon.

Your goal is to be honest, simple, and direct.

Return ONLY a JSON object (no markdown fences) with this schema:
{{
  "summary": "<1-2 sentences in very simple English>",
  "risk_level": "<Low | Medium | High>",
  "risk_reason": "<Short sentence explaining why>",
  "data_collection": ["<what they take, e.g. 'Your location'>", "<...more items...>"],
  "third_party_sharing": ["<who they give it to, e.g. 'Advertisers'>"],
  "tracking_cookies": ["<e.g. 'Tracks you across other websites'>"],
  "user_rights": ["<e.g. 'You can delete your data anytime'>"],
  "suspicious_clauses": ["<vague or sneaky wording found, or 'None'>"],
  "key_risks": ["<The biggest danger to the user's privacy>"]
}}

Guidelines:
- Avoid 'data', 'entities', 'clauses' where possible. Use 'info', 'companies', 'sentences'.
- Be brutal about 'High' risk: if they sell data or track across sites, it is High or Medium.
- Low risk is only for sites with minimal collection and no sharing.

Text:
---
{policy_text}
---
"""

def _cache_key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]

def _load_cache(key: str) -> dict | None:
    path = CACHE_DIR / f"{key}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except: pass
    return None

def _save_cache(key: str, data: dict) -> None:
    path = CACHE_DIR / f"{key}.json"
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")

def _parse_response(raw: str) -> dict:
    # Aggressively strip everything except the JSON object
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        raise SummarizerError("AI did not return a valid structured response.")
    
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        raise SummarizerError("AI output was not valid JSON.")

class SummarizerError(Exception):
    """Raised when summarization fails."""

def analyze_policy(policy_text: str, *, use_cache: bool = True, api_key: str | None = None) -> dict:
    if not policy_text or len(policy_text.strip()) < 50:
        raise SummarizerError("Policy text is too short to analyze.")

    effective_key = api_key or os.getenv("GEMINI_API_KEY", "")
    if not effective_key:
        raise SummarizerError("Missing Gemini API key.")
    
    cache_key = _cache_key(policy_text)
    if use_cache:
        cached = _load_cache(cache_key)
        if cached:
            cached["_from_cache"] = True
            return cached

    prompt = ANALYSIS_PROMPT.format(policy_text=policy_text)

    try:
        client = genai.Client(api_key=effective_key)
        
        logger.info(f"Summarizing with {MODEL_NAME}...")
        
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=TEMPERATURE,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            )
        )
        
        if not response.text:
            raise SummarizerError("Received empty response from AI.")
            
        result = _parse_response(response.text)
        
        # Ensure all keys exist
        for k in ["summary", "risk_level", "risk_reason", "data_collection", "third_party_sharing", "tracking_cookies", "user_rights", "suspicious_clauses", "key_risks"]:
            if k not in result: 
                result[k] = "No info available." if k in ["summary", "risk_level", "risk_reason"] else []

        result["_from_cache"] = False
        if use_cache:
            _save_cache(cache_key, result)
        
        return result

    except ClientError as e:
        raise SummarizerError(f"Gemini API Error: {str(e)}")
    except Exception as e:
        raise SummarizerError(f"Unexpected Error: {str(e)}")
