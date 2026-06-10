"""
KisanMitra AI API — Shared Dependencies
=====================================
Centralized dependency injection for all routers.
Lazy-loaded model singletons, database services, and OpenRouter LLM client.
"""
import os
import re
import httpx
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import Depends

from app.core.config import settings
from app.services.database_service import PriceDataService, AnalyticsService, SessionService
# ---------------------------------------------------------------------------
# OpenRouterChat — Vendor-unlocked LLM via OpenRouter (OpenAI-compatible API)
# ---------------------------------------------------------------------------
class OpenRouterChat:
    """
    LLM chat client via OpenRouter (https://openrouter.ai).

    Uses the OpenAI-compatible /api/v1/chat/completions endpoint.
    Includes automatic model fallback: if primary model returns 429,
    retries with next available free model.
    """

    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    # Fallback chain: tried in order on 429
    FREE_MODELS = [
        "google/gemma-4-31b-it:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen3-coder:free",
        "moonshotai/kimi-k2.6:free",
        "nvidia/nemotron-nano-9b-v2:free",
    ]

    def __init__(self, api_key: str, model: str = "google/gemma-4-31b-it:free"):
        self.api_key = api_key
        self.model = model
        self.chat_history: list = []

    def _strip_markdown(self, s: str) -> str:
        s = re.sub(r"[*`#>•\\-]+", "", s)
        s = re.sub(r"\s+\n", "\n", s)
        s = re.sub(r"\n{2,}", "\n", s)
        s = re.sub(r" {2,}", " ", s)
        return s.strip()

    def _crisp(self, s: str, max_chars: int = 350) -> str:
        s = self._strip_markdown(s)
        if len(s) <= max_chars:
            return s
        cut = s[:max_chars]
        dot = cut.rfind(".")
        return (cut[: dot + 1] if dot > 120 else cut).strip()

    def send_message(self, message: str, system_prompt: Optional[str] = None) -> str:
        """Send a message to OpenRouter with automatic model fallback on 429."""
        concise_rule = (
            "Reply in plain text only (no markdown). Max 4 short sentences total. "
            "End with ONE brief follow-up question if helpful. Keep under 350 characters."
        )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": f"{system_prompt.strip()}\n\n{concise_rule}"})
        else:
            messages.append({"role": "system", "content": concise_rule})
        messages.append({"role": "user", "content": message})

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://kisanmitra.ai",
            "X-Title": "KisanMitra AI",
        }

        # Build model order: primary first, then fallbacks
        models_to_try = [self.model] + [m for m in self.FREE_MODELS if m != self.model]

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
                    self.BASE_URL,
                    headers=headers,
                    json=payload,
                    timeout=25.0,
                )
                if resp.status_code in (429, 404):
                    print(f"OpenRouter {resp.status_code} on {model_id}, trying next...")
                    continue
                if resp.status_code != 200:
                    print(f"OpenRouter HTTP {resp.status_code}: {resp.text[:200]}")
                    return "Having trouble fetching advice now. Try again shortly."

                data = resp.json()
                reply_raw = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                if not reply_raw:
                    return "Sorry, I couldn't form a proper answer."

                reply = self._crisp(reply_raw)

                self.chat_history.append({
                    "user": message,
                    "assistant": reply,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                return reply

            except httpx.TimeoutException:
                print(f"OpenRouter timeout on {model_id}, trying next...")
                continue
            except Exception as e:
                print(f"OpenRouter error on {model_id}: {e}")
                continue

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
