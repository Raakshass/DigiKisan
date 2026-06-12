"""
KisanMitra AI API — Shared Dependencies
=====================================
Centralized dependency injection for all routers.
Lazy-loaded model singletons, database services, and multi-provider LLM client.
"""
import os
import re
import time
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import Depends

from app.core.config import settings
from app.services.database_service import PriceDataService, AnalyticsService, SessionService


# ---------------------------------------------------------------------------
# Multi-Provider LLM Client — HF Inference + OpenRouter round-robin
# ---------------------------------------------------------------------------
class OpenRouterChat:
    """
    Multi-provider LLM client with automatic failover:

    1. HF Inference API (primary — generous free tier, OpenAI-compatible)
    2. OpenRouter Key 1 → 6 free models
    3. OpenRouter Key 2 → 6 free models
    4. Retry with exponential backoff

    Total: ~18 model slots before "busy" — practically impossible to exhaust.
    """

    OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
    HF_INFERENCE_URL = "https://api-inference.huggingface.co/v1/chat/completions"

    # HF Inference API models (free tier, fast)
    HF_MODELS = [
        "meta-llama/Llama-3.2-3B-Instruct",
        "microsoft/Phi-3.5-mini-instruct",
        "Qwen/Qwen2.5-1.5B-Instruct",
    ]

    # OpenRouter free models
    OPENROUTER_MODELS = [
        "google/gemma-4-31b-it:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen3-coder:free",
        "moonshotai/kimi-k2.6:free",
        "nvidia/nemotron-nano-9b-v2:free",
    ]

    def __init__(self, api_key: str, model: str = "google/gemma-4-31b-it:free"):
        self.api_key = api_key  # Primary OpenRouter key
        self.model = model
        self.chat_history: list = []

        # Load additional keys from environment
        self.hf_token = os.environ.get("HF_INFERENCE_TOKEN", "")
        self.openrouter_keys = [k for k in [
            self.api_key,
            os.environ.get("OPENROUTER_API_KEY_2", ""),
            os.environ.get("OPENROUTER_API_KEY_3", ""),
        ] if k]

    def _strip_markdown(self, s: str) -> str:
        s = re.sub(r"[*`#>•\\-]+", "", s)
        s = re.sub(r"\s+\n", "\n", s)
        s = re.sub(r"\n{2,}", "\n", s)
        s = re.sub(r" {2,}", " ", s)
        return s.strip()

    def _strip_thinking(self, s: str) -> str:
        """Remove chain-of-thought reasoning leaked by thinking models."""
        # Pattern: lines starting with reasoning prefixes
        thinking_patterns = [
            r"^(?:We need to|Let me|I need to|Let's|I should|I will|The user|The farmer|Thinking|Step \d|First,? I).*$",
            r"^(?:Provide |Use reference|Reply in plain|Max \d|End with|Keep under).*$",
            r"^(?:We can give|Here is|Here's|Okay,|So,?).*$",
        ]
        lines = s.split("\n")
        cleaned = []
        for line in lines:
            is_thinking = False
            for pattern in thinking_patterns:
                if re.match(pattern, line.strip(), re.IGNORECASE):
                    is_thinking = True
                    break
            if not is_thinking and line.strip():
                cleaned.append(line)
        result = "\n".join(cleaned).strip()
        # If everything was stripped, return original (better than empty)
        return result if result else s

    def _crisp(self, s: str, max_chars: int = 350) -> str:
        s = self._strip_markdown(s)
        s = self._strip_thinking(s)
        if len(s) <= max_chars:
            return s
        cut = s[:max_chars]
        dot = cut.rfind(".")
        return (cut[: dot + 1] if dot > 120 else cut).strip()

    def _build_messages(self, message: str, system_prompt: Optional[str] = None) -> list:
        concise_rule = (
            "Reply in plain text only (no markdown). Max 4 short sentences total. "
            "End with ONE brief follow-up question if helpful. Keep under 350 characters. "
            "Do NOT include internal reasoning, thinking steps, or planning. "
            "Output ONLY the final answer for the farmer."
        )
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": f"{system_prompt.strip()}\n\n{concise_rule}"})
        else:
            messages.append({"role": "system", "content": concise_rule})
        messages.append({"role": "user", "content": message})
        return messages

    def _try_hf_inference(self, messages: list) -> Optional[str]:
        """Try HF Inference API (primary provider)."""
        if not self.hf_token:
            return None

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.hf_token}",
        }

        for model_id in self.HF_MODELS:
            payload = {
                "model": model_id,
                "messages": messages,
                "temperature": 0.4,
                "top_p": 0.9,
                "max_tokens": 256,
                "stream": False,
            }
            try:
                resp = httpx.post(
                    self.HF_INFERENCE_URL,
                    headers=headers,
                    json=payload,
                    timeout=30.0,
                )
                if resp.status_code in (429, 503, 404):
                    print(f"HF Inference {resp.status_code} on {model_id}, trying next...")
                    continue
                if resp.status_code != 200:
                    print(f"HF Inference HTTP {resp.status_code}: {resp.text[:200]}")
                    continue

                data = resp.json()
                reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if reply:
                    print(f"HF Inference OK: {model_id}")
                    return reply
            except httpx.TimeoutException:
                print(f"HF Inference timeout on {model_id}")
                continue
            except Exception as e:
                print(f"HF Inference error on {model_id}: {e}")
                continue
        return None

    def _try_openrouter(self, messages: list) -> Optional[str]:
        """Try OpenRouter with round-robin across multiple API keys."""
        models_to_try = [self.model] + [m for m in self.OPENROUTER_MODELS if m != self.model]

        for api_key in self.openrouter_keys:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://kisanmitra.ai",
                "X-Title": "KisanMitra AI",
            }

            for model_id in models_to_try:
                payload = {
                    "model": model_id,
                    "messages": messages,
                    "temperature": 0.4,
                    "top_p": 0.9,
                    "max_tokens": 256,
                }
                try:
                    resp = httpx.post(
                        self.OPENROUTER_URL,
                        headers=headers,
                        json=payload,
                        timeout=25.0,
                    )
                    if resp.status_code == 429:
                        print(f"OpenRouter 429 on {model_id} (key ...{api_key[-6:]}), trying next...")
                        continue
                    if resp.status_code == 404:
                        print(f"OpenRouter 404 on {model_id}, skipping...")
                        continue
                    if resp.status_code != 200:
                        print(f"OpenRouter HTTP {resp.status_code}: {resp.text[:200]}")
                        continue

                    data = resp.json()
                    reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if reply:
                        print(f"OpenRouter OK: {model_id} (key ...{api_key[-6:]})")
                        return reply
                except httpx.TimeoutException:
                    print(f"OpenRouter timeout on {model_id}")
                    continue
                except Exception as e:
                    print(f"OpenRouter error on {model_id}: {e}")
                    continue

            print(f"All models exhausted for OpenRouter key ...{api_key[-6:]}")

        return None

    def send_message(self, message: str, system_prompt: Optional[str] = None) -> str:
        """Send message with multi-provider failover and retry."""
        messages = self._build_messages(message, system_prompt)

        # Retry the entire provider chain up to 2 times with backoff
        for attempt in range(2):
            # Provider 1: HF Inference API
            reply = self._try_hf_inference(messages)
            if reply:
                clean = self._crisp(reply)
                self.chat_history.append({
                    "user": message, "assistant": clean,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                return clean

            # Provider 2: OpenRouter (multi-key round-robin)
            reply = self._try_openrouter(messages)
            if reply:
                clean = self._crisp(reply)
                self.chat_history.append({
                    "user": message, "assistant": clean,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                return clean

            # All providers exhausted — backoff before retry
            if attempt < 1:
                wait = 3
                print(f"All providers exhausted. Waiting {wait}s before retry...")
                time.sleep(wait)

        return "All AI models are busy right now. Please try again in a minute."

    def get_disease_summary(self, disease_name: str) -> str:
        system_prompt = (
            f"You are an agriculture advisor. Detected disease: {disease_name}. "
            "Give a brief actionable summary and end with one short follow-up question."
        )
        return self.send_message("How should I deal with it briefly?", system_prompt)

    def continue_conversation(self, user_message: str, disease_context: str) -> str:
        system_prompt = (
            f"You are advising a farmer about {disease_context}. "
            "Answer briefly with concrete next steps; end with one short follow-up question if needed."
        )
        return self.send_message(user_message, system_prompt)

    def agricultural_chat(self, user_message: str) -> str:
        """Handle general agricultural queries."""
        system_prompt = (
            "You are KisanMitra AI, an agricultural advisor helping Indian farmers. "
            "Provide practical, actionable advice for farming in India. "
            "Cover topics like crop management, soil health, weather, government schemes, "
            "and best farming practices. Keep responses concise and helpful."
        )
        return self.send_message(user_message, system_prompt)


# Backward-compatible alias — all existing imports of GeminiChat keep working
GeminiChat = OpenRouterChat

# ---------------------------------------------------------------------------
# Model Singleton — lazy-loaded, config-aware
# ---------------------------------------------------------------------------
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ModelSingleton:
    """Lazy-loaded model instances. Thread-safe via GIL for single-worker uvicorn."""

    _text_clf: Optional[Any] = None
    _slot_filler: Optional[Any] = None
    _img_clf: Optional[Any] = None
    _llm_chat: Optional[OpenRouterChat] = None

    @classmethod
    def get_text_clf(cls) -> Any:
        if cls._text_clf is None:
            from app.services.interactivechat import TextClassifierInference
            model_dir = os.path.join(_BACKEND_DIR, settings.text_classifier_dir)
            cls._text_clf = TextClassifierInference(model_dir=model_dir)
        return cls._text_clf

    @classmethod
    def get_slot_filler(cls) -> Any:
        if cls._slot_filler is None:
            from app.services.interactivechat import SlotFiller
            commodity_file = os.path.join(_BACKEND_DIR, settings.commodity_mappings_csv)
            district_file = os.path.join(_BACKEND_DIR, settings.district_mappings_csv)
            cls._slot_filler = SlotFiller(
                commodity_file=commodity_file,
                district_file=district_file,
            )
        return cls._slot_filler

    @classmethod
    def get_img_clf(cls) -> Any:
        if cls._img_clf is None:
            from app.services.image_classifier import CropDiseaseClassifier
            checkpoint = os.path.join(_BACKEND_DIR, settings.image_classifier_checkpoint)
            classes = os.path.join(_BACKEND_DIR, settings.image_classifier_classes)
            cls._img_clf = CropDiseaseClassifier(
                checkpoint_path=checkpoint,
                class_names_path=classes,
            )
        return cls._img_clf

    @classmethod
    def get_llm_chat(cls) -> OpenRouterChat:
        if cls._llm_chat is None:
            cls._llm_chat = OpenRouterChat(
                api_key=settings.openrouter_api_key,
                model=settings.openrouter_model,
            )
        return cls._llm_chat

    # Backward-compatible alias
    @classmethod
    def get_gemini_chat(cls) -> OpenRouterChat:
        return cls.get_llm_chat()


# ---------------------------------------------------------------------------
# FastAPI dependency functions
# ---------------------------------------------------------------------------
def get_text_clf() -> Any:
    return ModelSingleton.get_text_clf()

def get_slot_filler() -> Any:
    return ModelSingleton.get_slot_filler()

def get_img_clf() -> Any:
    return ModelSingleton.get_img_clf()

def get_llm_chat() -> OpenRouterChat:
    return ModelSingleton.get_llm_chat()

# Backward-compatible alias
def get_gemini_chat() -> OpenRouterChat:
    return get_llm_chat()

def get_price_service() -> Optional[PriceDataService]:
    return PriceDataService()

def get_analytics_service() -> Optional[AnalyticsService]:
    return AnalyticsService()

def get_session_service() -> Optional[SessionService]:
    return SessionService()
