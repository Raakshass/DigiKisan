"""
KisanMitra AI — Chat Orchestrator (Production-Grade)
==================================================
Replaces the raw GeminiChat with an intelligent orchestrator that:

1. Classifies user intent (price query, disease question, general farming)
2. Routes to the appropriate handler
3. Augments responses with RAG knowledge base context
4. Maintains conversation memory per session
5. Applies guardrails (topic fencing, input validation, response limits)

This does NOT use LangChain Agents (which add complexity and latency).
Instead, it uses a clean "router + RAG augmentation" pattern that's
faster, more reliable, and easier to debug.
"""
import re
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, List
from collections import OrderedDict

from app.services.rag_pipeline import get_knowledge_base
from app.api.deps import GeminiChat


# ---------------------------------------------------------------------------
# Conversation Memory (per-session, in-memory with LRU eviction)
# ---------------------------------------------------------------------------
class ConversationMemory:
    """
    Per-session conversation memory with auto-summarization.
    Stores last N messages and provides context for Gemini.
    """

    def __init__(self, max_messages: int = 20):
        self.messages: List[Dict[str, str]] = []
        self.max_messages = max_messages
        self.summary: str = ""

    def add_message(self, role: str, content: str):
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        # Evict oldest messages if over limit
        if len(self.messages) > self.max_messages:
            # Summarize evicted messages (simplified — in production, use Gemini to summarize)
            evicted = self.messages[: len(self.messages) - self.max_messages]
            if evicted:
                topics = set()
                for msg in evicted:
                    words = msg["content"].lower().split()
                    for w in ["wheat", "rice", "price", "disease", "fertilizer", "water", "pest"]:
                        if w in words:
                            topics.add(w)
                if topics:
                    self.summary = f"Earlier in this conversation, we discussed: {', '.join(topics)}."
            self.messages = self.messages[-self.max_messages:]

    def get_context_string(self, last_n: int = 6) -> str:
        """Get recent conversation history as a formatted string."""
        recent = self.messages[-last_n:]
        if not recent and not self.summary:
            return ""

        parts = []
        if self.summary:
            parts.append(f"[Previous context: {self.summary}]")
        for msg in recent:
            prefix = "Farmer" if msg["role"] == "user" else "KisanMitra AI"
            parts.append(f"{prefix}: {msg['content']}")
        return "\n".join(parts)


class _SessionStore:
    """LRU session store with max capacity to prevent memory leaks."""

    def __init__(self, max_sessions: int = 1000):
        self._store: OrderedDict[str, ConversationMemory] = OrderedDict()
        self.max_sessions = max_sessions

    def get(self, session_id: str) -> ConversationMemory:
        if session_id in self._store:
            self._store.move_to_end(session_id)
            return self._store[session_id]
        # Create new session
        if len(self._store) >= self.max_sessions:
            self._store.popitem(last=False)  # Remove oldest
        memory = ConversationMemory()
        self._store[session_id] = memory
        return memory


_sessions = _SessionStore()


# ---------------------------------------------------------------------------
# Input Guardrails
# ---------------------------------------------------------------------------
_AGRICULTURAL_TOPICS = {
    "crop", "farming", "agriculture", "soil", "seed", "fertilizer", "pesticide",
    "irrigation", "harvest", "wheat", "rice", "maize", "potato", "onion", "tomato",
    "disease", "pest", "weed", "organic", "compost", "manure", "tractor",
    "mandi", "market", "price", "msp", "apmc", "government", "scheme", "subsidy",
    "kisan", "weather", "rain", "drought", "flood", "monsoon", "sowing", "rabi",
    "kharif", "zaid", "horticulture", "vegetable", "fruit", "dairy", "cattle",
    "poultry", "fishery", "mushroom", "beekeeping", "sericulture", "pm-kisan",
    "pmfby", "kcc", "urea", "dap", "npk", "zinc", "nitrogen", "phosphorus",
    "potassium", "gram", "arhar", "moong", "mustard", "sugarcane", "cotton",
    "loan", "credit", "insurance", "animal", "livestock", "goat", "buffalo",
    "cow", "hen", "egg", "milk", "ghee", "neem", "tulsi", "vermicompost",
    "drip", "sprinkler", "bore", "tubewell", "canal", "dam", "water",
    "temperature", "humidity", "frost", "hail", "cyclone", "plantation",
    "nursery", "grafting", "pruning", "mulching", "intercropping",
    "crop rotation", "yield", "quintal", "hectare", "acre", "bigha",
}

_BLOCKED_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
    re.compile(r"you\s+are\s+now\s+a", re.I),
    re.compile(r"system\s*:\s*", re.I),
    re.compile(r"forget\s+(everything|all)", re.I),
    re.compile(r"act\s+as\s+(if\s+you\s+are|a)\s+", re.I),
]


def _is_agricultural(text: str) -> bool:
    """Check if the query is agriculture-related."""
    words = set(text.lower().split())
    return bool(words & _AGRICULTURAL_TOPICS)


def _check_injection(text: str) -> bool:
    """Check for prompt injection attempts."""
    return any(p.search(text) for p in _BLOCKED_PATTERNS)


def _validate_input(text: str) -> Optional[str]:
    """Validate user input. Returns error message if invalid, None if ok."""
    if not text or not text.strip():
        return "Please enter a message."
    if len(text) > 2000:
        return "Message is too long. Please keep it under 2000 characters."
    if _check_injection(text):
        return "I can only help with agricultural queries. How can I assist you with farming?"
    return None


# ---------------------------------------------------------------------------
# Chat Orchestrator
# ---------------------------------------------------------------------------
class ChatOrchestrator:
    """
    Production-grade chat orchestrator with RAG augmentation.

    Flow:
    1. Validate input (length, injection, topic)
    2. Load conversation memory
    3. Search knowledge base for relevant context
    4. Build augmented prompt with context + memory
    5. Send to Gemini with agricultural system prompt
    6. Store response in memory
    7. Return formatted response with sources
    """

    def __init__(self, gemini_chat: GeminiChat):
        self.gemini = gemini_chat

    def chat(
        self,
        message: str,
        session_id: str = "default",
        language: str = "en",
        user_location: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Process a user message and return a response.

        Args:
            message: User's message text
            session_id: Session identifier for memory
            language: Language code (en, hi, etc.)
            user_location: Optional dict with 'state' and/or 'district'
                           e.g. {"state": "UP", "district": "Lucknow"}

        Returns:
            {
                "ok": True/False,
                "response": str,
                "sources": [{"file": str, "category": str}],
                "intent": str,
                "session_id": str,
            }
        """
        # Step 1: Validate input
        error = _validate_input(message)
        if error:
            return self._error_response(error, session_id)

        # Step 2: Get conversation memory
        memory = _sessions.get(session_id)
        memory.add_message("user", message)

        # Step 3: Extract location
        loc_state = (user_location or {}).get("state")
        loc_district = (user_location or {}).get("district")

        # Step 4: Search knowledge base with location filtering
        kb = get_knowledge_base()
        rag_context = ""
        sources = []
        if kb.is_available:
            if loc_state or loc_district:
                results = kb.search_with_location(
                    message, state=loc_state, district=loc_district, k=3
                )
            else:
                results = kb.search(message, k=3)

            if results:
                rag_context = "\n\n".join(
                    f"[Reference: {r['source']}]\n{r['content']}" for r in results
                )
                sources = [
                    {"file": r["source"], "category": r["category"]}
                    for r in results
                ]

        # Step 5: Determine intent
        intent = self._classify_intent(message)

        # Step 6: Build augmented prompt
        conversation_history = memory.get_context_string(last_n=4)
        system_prompt = self._build_system_prompt(
            intent=intent,
            rag_context=rag_context,
            conversation_history=conversation_history,
            language=language,
            user_location=user_location,
        )

        # Step 7: Get Gemini response
        response_text = self.gemini.send_message(message, system_prompt)

        # Step 8: Store in memory
        memory.add_message("assistant", response_text)

        # Step 9: Append source citations if RAG was used
        if sources and rag_context:
            source_names = list(set(s["file"].replace(".md", "").replace("_", " ").title() for s in sources))
            if source_names:
                response_text += f"\n\n(Sources: {', '.join(source_names[:3])})"

        return {
            "ok": True,
            "response": response_text,
            "sources": sources,
            "intent": intent,
            "session_id": session_id,
        }

    def _classify_intent(self, message: str) -> str:
        """Simple keyword-based intent classification."""
        msg_lower = message.lower()

        price_keywords = {"price", "rate", "mandi", "market", "cost", "msp", "kya bhav", "bhav", "daam"}
        disease_keywords = {"disease", "pest", "blight", "rust", "wilt", "rot", "fungus", "insect", "spray", "rog"}
        scheme_keywords = {"scheme", "yojana", "subsidy", "pm-kisan", "pmfby", "kcc", "loan", "insurance", "government"}
        weather_keywords = {"weather", "rain", "monsoon", "temperature", "forecast", "mausam"}

        words = set(msg_lower.split())

        if words & price_keywords:
            return "price_query"
        if words & disease_keywords:
            return "disease_query"
        if words & scheme_keywords:
            return "scheme_query"
        if words & weather_keywords:
            return "weather_query"
        if _is_agricultural(msg_lower):
            return "farming_query"
        return "general"

    def _build_system_prompt(
        self,
        intent: str,
        rag_context: str,
        conversation_history: str,
        language: str,
        user_location: Optional[Dict[str, str]] = None,
    ) -> str:
        """Build an augmented system prompt with RAG context, memory, and location."""
        base = (
            "You are KisanMitra AI, an expert agricultural advisor for Indian farmers. "
            "You provide practical, actionable advice based on ICAR recommendations "
            "and best farming practices in India. "
            "Be helpful, empathetic, and speak in simple language that any farmer can understand. "
        )

        # Intent-specific instructions
        intent_prompts = {
            "price_query": "The farmer is asking about crop prices or market rates. ",
            "disease_query": (
                "The farmer is asking about crop diseases or pest problems. "
                "Provide specific disease identification tips, treatment options "
                "(both organic and chemical), and prevention measures. "
            ),
            "scheme_query": (
                "The farmer is asking about government schemes or subsidies. "
                "Provide accurate information about eligibility, benefits, and how to apply. "
                "Include helpline numbers when available. "
            ),
            "weather_query": "The farmer is asking about weather or its impact on farming. ",
            "farming_query": (
                "The farmer is asking about general farming practices. "
                "Provide specific, practical advice with quantities and timings. "
            ),
            "general": (
                "If the query is about agriculture, answer helpfully. "
                "If it's completely unrelated, gently redirect to farming topics. "
            ),
        }
        base += intent_prompts.get(intent, "")

        # Add location context
        if user_location:
            loc_state = user_location.get("state", "")
            loc_district = user_location.get("district", "")
            if loc_district and loc_state:
                base += (
                    f"The farmer is located in {loc_district} district, {loc_state} state. "
                    "Tailor your advice to this specific region's climate, soil, and cropping patterns. "
                )
            elif loc_state:
                base += (
                    f"The farmer is in {loc_state} state. "
                    "Consider this state's agro-climatic conditions in your advice. "
                )

        # Add language instruction
        if language != "en":
            lang_names = {"hi": "Hindi", "bn": "Bengali", "ta": "Tamil", "te": "Telugu", "mr": "Marathi"}
            lang_name = lang_names.get(language, language)
            base += f"Respond in {lang_name} language. "

        # Add RAG context
        if rag_context:
            base += (
                "\n\nUse the following reference information to answer accurately. "
                "Cite specific numbers, varieties, and recommendations from the references:\n\n"
                f"{rag_context}\n\n"
            )

        # Add conversation history
        if conversation_history:
            base += f"\nConversation so far:\n{conversation_history}\n\n"

        # Response formatting
        base += (
            "Reply in plain text (no markdown). Keep response under 400 characters. "
            "Be specific with numbers, timings, and quantities. "
            "End with one relevant follow-up question if appropriate."
        )

        return base

    def _error_response(self, error: str, session_id: str) -> Dict[str, Any]:
        return {
            "ok": False,
            "response": error,
            "sources": [],
            "intent": "error",
            "session_id": session_id,
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
_orchestrator: Optional[ChatOrchestrator] = None


def get_orchestrator(gemini_chat: GeminiChat) -> ChatOrchestrator:
    """Get or create the ChatOrchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ChatOrchestrator(gemini_chat)
    return _orchestrator
