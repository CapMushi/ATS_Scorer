"""
LLM client with Groq primary (insanely fast inference) + Gemini fallback.
Handles rate limiting, retries, and graceful degradation.

v2: temperature=0.0, seed=42 for deterministic outputs.
"""

import re
import time
import json
import hashlib
import logging
from typing import Optional

from config import (
    GEMINI_API_KEY, GROQ_API_KEY, LLM_DISABLED,
    LLM_RETRY_DELAY_SECONDS, LLM_INTER_CALL_DELAY_SECONDS,
)

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Unified LLM client.
    Uses Groq (qwen3.8-27b) as primary for extreme speed.
    Falls back to Gemini if Groq fails.
    Falls back to None (regex-only) if both fail.
    
    v2: Deterministic settings (temp=0, seed=42) + response caching.
    """

    def __init__(self):
        self._groq_client = None
        self._gemini_client = None 
        self._groq_available = False
        self._gemini_available = False
        
        self._last_call_time = 0.0
        self._consecutive_failures = 0
        self._max_failures_before_disable = 5
        
        self._groq_rate_limit_until = 0.0
        self._gemini_rate_limit_until = 0.0
        
        # Response cache: hash(prompt) -> parsed response
        self._cache: dict[str, dict] = {}
        
        self._init_clients()

    def _init_clients(self):
        """Initialize LLM clients lazily."""
        if LLM_DISABLED:
            logger.info("LLM disabled via config")
            return

        # Init Groq (Primary)
        if GROQ_API_KEY:
            try:
                from openai import OpenAI
                self._groq_client = OpenAI(
                    base_url="https://api.groq.com/openai/v1",
                    api_key=GROQ_API_KEY,
                    max_retries=0, # Disable auto-retries to instantly trigger Gemini fallback
                )
                self._groq_available = True
                logger.info("Groq client initialized (qwen3.8-27b primary, temp=0, seed=42)")
            except ImportError:
                logger.warning("openai package not installed. Run: pip install openai")
            except Exception as e:
                logger.warning(f"Groq init failed: {e}")

        # Init Gemini using new google-genai SDK
        if GEMINI_API_KEY:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=GEMINI_API_KEY)
                self._gemini_available = True
                logger.info("Gemini client initialized (fallback)")
            except ImportError:
                logger.warning("google-genai package not installed.")
            except Exception as e:
                logger.warning(f"Gemini init failed: {e}")

    @property
    def is_available(self) -> bool:
        """Check if LLM is available."""
        if LLM_DISABLED:
            return False
        if self._consecutive_failures >= self._max_failures_before_disable:
            return False
        now = time.time()
        groq_ok = self._groq_available and now >= self._groq_rate_limit_until
        gemini_ok = self._gemini_available and now >= self._gemini_rate_limit_until
        return groq_ok or gemini_ok

    @property
    def active_provider(self) -> str:
        """Return active LLM provider."""
        if not self.is_available:
            return "offline"
        now = time.time()
        if self._groq_available and now >= self._groq_rate_limit_until:
            return "groq"
        if self._gemini_available and now >= self._gemini_rate_limit_until:
            return "gemini"
        return "offline"

    def _throttle(self):
        """Enforce minimum delay between calls to respect RPM limits."""
        elapsed = time.time() - self._last_call_time
        if elapsed < LLM_INTER_CALL_DELAY_SECONDS:
            time.sleep(LLM_INTER_CALL_DELAY_SECONDS - elapsed)

    def _cache_key(self, prompt: str) -> str:
        """Generate a cache key from the prompt."""
        return hashlib.md5(prompt.encode()).hexdigest()

    def _call_groq(self, prompt: str) -> Optional[str]:
        """Call Groq API with deterministic settings. Returns response text or None."""
        if not self._groq_client:
            return None
        if time.time() < self._groq_rate_limit_until:
            return None

        try:
            response = self._groq_client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,       # DETERMINISTIC: no randomness
                seed=42,               # DETERMINISTIC: fixed seed
                max_tokens=3000,
                response_format={"type": "json_object"},
            )
            result = response.choices[0].message.content
            if result and len(result.strip()) > 50:
                return result
            return None
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate" in error_str:
                logger.warning("Groq rate limited, cooling down 5s")
                self._groq_rate_limit_until = time.time() + 5
            else:
                logger.warning(f"Groq call failed: {e}")
            return None

    def _call_gemini(self, prompt: str) -> Optional[str]:
        """Call Gemini API. Returns response text or None."""
        if not self._gemini_client:
            return None
        if time.time() < self._gemini_rate_limit_until:
            return None

        try:
            from google.genai import types

            response = self._gemini_client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,       # DETERMINISTIC
                    max_output_tokens=3000,
                    response_mime_type="application/json",
                ),
            )
            result_text = response.text
            if not result_text or len(result_text.strip()) < 80:
                return None
            return result_text
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate" in error_str or "quota" in error_str or "resource_exhausted" in error_str:
                logger.warning(f"Gemini rate limited, cooling down 90s.")
                self._gemini_rate_limit_until = time.time() + 90
            else:
                logger.warning(f"Gemini call failed: {e}")
            return None

    def call(self, prompt: str) -> Optional[str]:
        """
        Call LLM — tries Groq first, falls back to Gemini.
        Returns raw JSON string response, or None if failed.
        """
        if not self.is_available:
            return None

        self._throttle()
        self._last_call_time = time.time()

        now = time.time()

        if self._groq_available and now >= self._groq_rate_limit_until:
            result = self._call_groq(prompt)
            if result:
                self._consecutive_failures = 0
                return result

        if self._gemini_available and time.time() >= self._gemini_rate_limit_until:
            result = self._call_gemini(prompt)
            if result:
                self._consecutive_failures = 0
                return result

        self._consecutive_failures += 1
        return None

    def call_json(self, prompt: str) -> Optional[dict]:
        """
        Call LLM and parse response as JSON.
        Uses cache: same prompt = same result (no re-calling LLM).
        Returns parsed dict or None on failure.
        """
        # Check cache first
        cache_key = self._cache_key(prompt)
        if cache_key in self._cache:
            logger.info("LLM cache HIT — returning cached result")
            return self._cache[cache_key]

        raw = self.call(prompt)
        if not raw:
            return None

        raw = raw.strip()

        parsed = None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            pass

        if parsed is None:
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL | re.IGNORECASE)
            if match:
                raw = match.group(1).strip()
            else:
                start = raw.find('{')
                end = raw.rfind('}')
                if start != -1 and end != -1:
                    raw = raw[start:end + 1]

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                pass

        if parsed is None:
            repaired = self._repair_json(raw)
            try:
                parsed = json.loads(repaired)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse primary LLM JSON response: {e}")
                pass
                
        # If Groq gave us invalid JSON, force a fallback to Gemini
        if parsed is None and self._gemini_available and time.time() >= self._gemini_rate_limit_until:
            logger.warning("Primary LLM returned malformed JSON. Forcing fallback to Gemini.")
            raw_fallback = self._call_gemini(prompt)
            if raw_fallback:
                try:
                    parsed = json.loads(raw_fallback)
                except json.JSONDecodeError:
                    match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw_fallback, re.DOTALL | re.IGNORECASE)
                    if match:
                        try:
                            parsed = json.loads(match.group(1).strip())
                        except:
                            pass
                
                if parsed is None:
                     logger.warning("Gemini fallback also returned malformed JSON.")
        
        if parsed is None:
            return None

        # Cache successful result
        if parsed:
            self._cache[cache_key] = parsed
            logger.info(f"LLM cache STORED (cache size: {len(self._cache)})")

        return parsed

    def clear_cache(self):
        """Clear the response cache (call when skills list changes)."""
        size = len(self._cache)
        self._cache.clear()
        logger.info(f"LLM cache CLEARED ({size} entries removed)")

    @staticmethod
    def _repair_json(text: str) -> str:
        text = re.sub(r'//[^\n"]*(?=\n|$)', '', text)
        text = re.sub(r'(?<![""])#[^\n"]*(?=\n|$)', '', text)
        text = re.sub(r',\s*([\]}])', r'\1', text)
        text = re.sub(r'\.\.\.', '""', text)
        text = re.sub(r"(?<=[{,:\[])(\s*)'([^']*)'(?=\s*[,:\]}])", r'\1"\2"', text)
        text = re.sub(r',\s*([\]}])', r'\1', text)
        return text.strip()

    def reset_rate_limits(self):
        self._groq_available = bool(self._groq_client)
        self._gemini_available = bool(self._gemini_client)
        self._consecutive_failures = 0
        self._groq_rate_limit_until = 0.0
        self._gemini_rate_limit_until = 0.0
