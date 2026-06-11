"""
KisanMitra AI API — Chat Router
==============================
Handles all chat endpoints:
- /chat/start-session  — create a new chat session
- /chat/message        — session-based chat with slot filling + Gemini
- /chat/send           — authenticated chat (JWT required)
- /chat/slots          — legacy backward-compatible endpoint
"""
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, Body, Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.services.database_service import SessionService, PriceDataService, AnalyticsService
from app.models.price_data import QueryAnalyticsModel, UserSessionModel
from app.services.price_scraper import (
    get_market_prices, summarize_prices, format_price_response,
    get_commodity_code, get_district_code, COMMODITY_MAP, DISTRICT_MAP_UP,
)
from app.services.chat_orchestrator import get_orchestrator
from app.services.auth_service import verify_firebase_token
from app.api.deps import (
    GeminiChat, get_text_clf, get_slot_filler, get_gemini_chat,
    get_session_service, get_price_service, get_analytics_service,
)

router = APIRouter(prefix="/chat", tags=["Chat"])
security = HTTPBearer()


class ChatMessage(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Per-user session state store (in-memory; replace with Redis for production)
# ---------------------------------------------------------------------------
_user_sessions: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# POST /chat/start-session
# ---------------------------------------------------------------------------
@router.post("/start-session")
async def start_chat_session(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    session_service: Optional[SessionService] = Depends(get_session_service),
):
    """Create a new chat session. Gracefully falls back if DB is unavailable."""
    try:
        session_id = str(uuid.uuid4())

        if session_service:
            user_ip = request.client.host if request.client else "unknown"
            user_agent = request.headers.get("user-agent", "unknown")
            session_model = UserSessionModel(
                session_id=session_id,
                user_ip=user_ip,
                user_agent=user_agent,
                started_at=datetime.now(),
                last_activity=datetime.now(),
            )
            await session_service.create_session(session_model)

        return {
            "ok": True,
            "session_id": session_id,
            "message": (
                "Welcome to KisanMitra AI! I can help with crop prices, "
                "disease detection, and farming advice. What would you like to know?"
            ),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"Session creation error: {e}")
        return {
            "ok": True,
            "session_id": str(uuid.uuid4()),
            "message": (
                "Welcome to KisanMitra AI! I can help with crop prices, "
                "disease detection, and farming advice. What would you like to know?"
            ),
            "note": "Session storage unavailable — using temporary session",
            "timestamp": datetime.now().isoformat(),
        }


# ---------------------------------------------------------------------------
# POST /chat/message — main session-based chat
# ---------------------------------------------------------------------------
@router.post("/message")
async def chat_message(
    payload: Dict[str, Any] = Body(...),
    clf: Any = Depends(get_text_clf),
    slot_filler: Any = Depends(get_slot_filler),
    session_service: Optional[SessionService] = Depends(get_session_service),
    gemini_chat: GeminiChat = Depends(get_gemini_chat),
    price_service: Optional[PriceDataService] = Depends(get_price_service),
    analytics_service: Optional[AnalyticsService] = Depends(get_analytics_service),
):
    """Session-based chat with intent classification, slot filling, and price retrieval."""
    message = payload.get("message", "").strip()
    session_id = payload.get("session_id")
    session_state = payload.get("session_state", {})

    if not message:
        return {"ok": False, "error": "Message cannot be empty"}

    try:
        # Store user message in session
        await _store_message(session_service, session_id, "user_message", message)

        # --- Intent classification with pre-filter ---
        if not session_state.get("in_slot_fill"):
            # Pre-filter: override the ML classifier for known patterns
            # This prevents crop names (wheat, maize) from triggering price_enquiry
            # when the question is actually about farming or schemes
            is_price = _is_price_query(message)

            if is_price:
                # Confirmed price query → go to slot filler
                classification = {"prediction": "price_enquiry"}
            else:
                classification = clf.predict(message)
                # Double-check: if classifier says price but pre-filter says no,
                # trust the pre-filter (it's more precise)
                if classification["prediction"] == "price_enquiry" and _should_override_price(message):
                    classification["prediction"] = "general"

            if classification["prediction"] != "price_enquiry":
                # General chat → RAG-augmented ChatOrchestrator
                orchestrator = get_orchestrator(gemini_chat)

                # Extract location from payload for region-specific advice
                user_location = payload.get("location")  # {"state": "UP", "district": "Lucknow"}
                language = payload.get("language", "en")

                orch_result = orchestrator.chat(
                    message=message,
                    session_id=session_id or "anonymous",
                    language=language,
                    user_location=user_location,
                )
                response = orch_result.get("response", "Sorry, I couldn't process that.")
                await _store_message(session_service, session_id, "assistant_response", response)
                return _chat_response(session_id, response, session_state, completed=False)

            session_state["in_slot_fill"] = True

        # --- Slot filling for price queries ---
        result = slot_filler.handle_message(message, session_state)

        if result.get("ask"):
            # Still collecting slots
            response_text = result["ask"]
            new_state = result.get("session_state", {})
            await _store_message(session_service, session_id, "slot_filling_response", response_text)
            return _chat_response(
                session_id, response_text, new_state,
                completed=False, slots_so_far=new_state.get("slots", {}),
            )

        if result.get("slots"):
            # All slots filled — fetch prices
            slots = result["slots"]
            response_text = await _fetch_and_format_prices(
                slots, price_service, analytics_service, session_id,
            )

            await _store_message(session_service, session_id, "price_response", response_text)
            return _chat_response(session_id, response_text, {}, completed=True, slots=slots)

        # Waiting for input
        return _chat_response(session_id, "Waiting for your query...", session_state, completed=False)

    except Exception as e:
        print(f"Chat message error: {e}")
        return {
            "ok": False,
            "error": "I'm having trouble processing your request. Please try again.",
            "session_state": session_state,
            "timestamp": datetime.now().isoformat(),
        }


# ---------------------------------------------------------------------------
# POST /chat/send — authenticated chat (JWT required)
# ---------------------------------------------------------------------------
@router.post("/send")
async def send_chat_message(
    chat_request: ChatMessage,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    clf: Any = Depends(get_text_clf),
    slot_filler: Any = Depends(get_slot_filler),
    gemini_chat: GeminiChat = Depends(get_gemini_chat),
    price_service: Optional[PriceDataService] = Depends(get_price_service),
):
    """Authenticated chat endpoint — requires Firebase ID token."""
    try:
        # Verify Firebase token
        token = credentials.credentials
        user_info = await verify_firebase_token(token)
        if user_info is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        user_message = chat_request.message
        user_id = user_info["uid"]

        # Get/create persistent session state for this user
        if user_id not in _user_sessions:
            _user_sessions[user_id] = {}
        session_state = _user_sessions[user_id]

        try:
            if session_state.get("in_slot_fill"):
                # Continue slot filling
                result = slot_filler.handle_message(user_message, session_state)

                if result.get("ask"):
                    _user_sessions[user_id] = result.get("session_state", {})
                    return _auth_response(result["ask"], user_info, "price_enquiry")

                if result.get("slots"):
                    slots = result["slots"]
                    response_text = await _fetch_and_format_prices(slots, price_service)
                    _user_sessions[user_id] = {}
                    return _auth_response(response_text, user_info, "price_enquiry")

                return _auth_response("Please tell me which crop price you'd like to know about.", user_info, "price_enquiry")

            else:
                # New query — classify intent
                classification = clf.predict(user_message)
                intent = classification["prediction"]

                if intent == "price_enquiry":
                    session_state["in_slot_fill"] = True
                    result = slot_filler.handle_message(user_message, session_state)

                    if result.get("ask"):
                        _user_sessions[user_id] = result.get("session_state", {})
                        return _auth_response(result["ask"], user_info, "price_enquiry")
                    if result.get("slots"):
                        slots = result["slots"]
                        response_text = await _fetch_and_format_prices(slots, price_service)
                        _user_sessions[user_id] = {}
                        return _auth_response(response_text, user_info, "price_enquiry")

                    _user_sessions[user_id] = session_state
                    return _auth_response("Please tell me which crop price you'd like to know about.", user_info, "price_enquiry")
                else:
                    # General agricultural query → RAG-augmented ChatOrchestrator
                    orchestrator = get_orchestrator(gemini_chat)
                    orch_result = orchestrator.chat(
                        message=user_message,
                        session_id=user_id,
                    )
                    response_text = orch_result.get("response", "Sorry, I couldn't process that.")
                    return _auth_response(response_text, user_info, orch_result.get("intent", "general"))

        except Exception as ai_error:
            print(f"AI processing error: {ai_error}")
            _user_sessions.pop(user_id, None)
            return _auth_response(
                "I'm here to help with your farming needs! Ask about crop prices, diseases, or farming advice.",
                user_info, "general",
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Auth endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# POST /chat/slots — legacy endpoint
# ---------------------------------------------------------------------------
@router.post("/slots")
async def chat_slots(
    payload: Dict[str, Any] = Body(...),
    clf: Any = Depends(get_text_clf),
    slot_filler: Any = Depends(get_slot_filler),
):
    """Legacy slot-based chat endpoint for backward compatibility."""
    message = payload.get("message", "")
    session_state = payload.get("session_state", {})

    if not message.strip():
        return {"ok": False, "error": "Message cannot be empty"}

    if not session_state.get("in_slot_fill"):
        classification = clf.predict(message)
        if classification["prediction"] != "price_enquiry":
            return {
                "ok": True,
                "response": "I currently support price enquiries only. Please ask about prices.",
                "session_state": {},
                "completed": False,
                "classification": classification,
            }
        session_state["in_slot_fill"] = True

    result = slot_filler.handle_message(message, session_state)

    if result.get("ask"):
        return {
            "ok": True,
            "response": result["ask"],
            "session_state": result.get("session_state", {}),
            "completed": False,
            "slots_so_far": result.get("session_state", {}).get("slots", {}),
        }
    if result.get("slots"):
        return {
            "ok": True,
            "response": "Price query completed successfully!",
            "session_state": {},
            "completed": True,
            "slots": result["slots"],
        }
    return {
        "ok": True,
        "response": "Waiting for your query...",
        "session_state": session_state,
        "completed": False,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _fetch_and_format_prices(
    slots: Dict[str, Any],
    price_service: Optional[PriceDataService] = None,
    analytics_service: Optional[AnalyticsService] = None,
    session_id: Optional[str] = None,
) -> str:
    """Fetch prices using the new production scraper and format the response."""
    commodity = slots.get("commodity", "")
    district = slots.get("area", "")
    date_str = slots.get("time", "")

    commodity_code = get_commodity_code(commodity) or COMMODITY_MAP.get(commodity.lower())
    district_code = get_district_code(district) or DISTRICT_MAP_UP.get(district.lower())

    if not commodity_code or not district_code:
        missing = []
        if not commodity_code:
            missing.append(f"commodity '{commodity}'")
        if not district_code:
            missing.append(f"district '{district}'")
        return (
            f"Unable to fetch price data.\n\n"
            f"Missing mapping for: {', '.join(missing)}\n\n"
            "Please try with different names."
        )

    try:
        # Use production scraper (async, no Selenium!)
        from app.core.config import settings as _settings
        result = await get_market_prices(
            commodity_code, district_code, date_str,
            data_gov_api_key=_settings.data_gov_api_key or "",
        )

        if result["ok"] and result["data"] is not None and not result["data"].empty:
            summary_df = summarize_prices(result["data"])
            response_text = format_price_response(
                summary_df,
                result["commodity"],
                result["district"],
                result["date"],
                result["source"],
            )

            # Log analytics if available
            if analytics_service:
                try:
                    analytics_data = QueryAnalyticsModel(
                        query_id=str(uuid.uuid4()),
                        session_id=session_id,
                        commodity=commodity,
                        district=district,
                        date_requested=date_str,
                        response_time_ms=100,
                        data_source_used=result["source"],
                        success=True,
                        time_of_day="unknown",
                    )
                    await analytics_service.log_query(analytics_data)
                except Exception as e:
                    print(f"Analytics logging error: {e}")

            return response_text
        else:
            return (
                f"No price data available for {commodity.title()} in {district.title()} on {date_str}.\n\n"
                "Try a different date or location."
            )
    except Exception as e:
        print(f"Price fetch error: {e}")
        return "Technical issue retrieving price data. Please try again."


async def _store_message(
    session_service: Optional[SessionService],
    session_id: Optional[str],
    msg_type: str,
    message: str,
):
    """Store a message in the session (best-effort, non-blocking)."""
    if not session_service or not session_id:
        return
    try:
        await session_service.update_session(session_id, {
            "$push": {"conversation_history": {
                "type": msg_type,
                "message": message,
                "timestamp": datetime.now().isoformat(),
            }}
        })
    except Exception as e:
        print(f"Session storage error: {e}")


def _chat_response(
    session_id: Optional[str],
    message: str,
    session_state: Dict,
    completed: bool = False,
    slots: Optional[Dict] = None,
    slots_so_far: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Build a standardized chat response dict."""
    resp = {
        "ok": True,
        "session_id": session_id,
        "message": message,
        "session_state": session_state,
        "completed": completed,
        "timestamp": datetime.now().isoformat(),
    }
    if slots:
        resp["slots"] = slots
    if slots_so_far:
        resp["slots_so_far"] = slots_so_far
    return resp


def _auth_response(response_text: str, user_info: Dict[str, Any], intent: str) -> Dict[str, Any]:
    """Build authenticated chat response."""
    return {
        "response": response_text,
        "user_id": user_info.get("uid"),
        "email": user_info.get("email"),
        "intent": intent,
    }


# ---------------------------------------------------------------------------
# Intent Pre-Filter (overrides ML classifier for known patterns)
# ---------------------------------------------------------------------------
# Keywords that indicate a NON-price query (farming advice, schemes, knowledge)
_SCHEME_KEYWORDS = {
    "pm-kisan", "pmfby", "kcc", "kisan credit", "subsidy", "yojana",
    "scheme", "insurance", "e-nam", "soil health card", "shc",
    "government", "sarkari", "pradhan mantri", "pkvy",
}
_FARMING_KEYWORDS = {
    "urea", "fertilizer", "npk", "dap", "seed rate", "sowing",
    "harvest", "variety", "irrigation", "msp", "spacing", "nursery",
    "compost", "vermicompost", "organic", "jeevamrut", "crop rotation",
    "soil ph", "drip", "mulching", "pruning", "grafting", "intercropping",
    "planting", "transplanting", "weed", "storage", "seed treatment",
    "how to", "kaise", "kab", "kitna", "best time", "symptoms",
    "identify", "treat", "control", "prevent", "protect", "manage",
    "improve", "difference", "benefit", "recommended", "ideal",
    "solar pump", "grow", "uga", "buvai",
}
# Hindi/Hinglish price keywords that MUST be paired with a location
_HINDI_PRICE_KEYWORDS = {"bhav", "rate", "daam", "kimat", "mol"}
# Known UP district names for Hindi price query detection
_DISTRICT_NAMES = set(DISTRICT_MAP_UP.keys())


def _is_price_query(message: str) -> bool:
    """
    Detect if a message is genuinely a price/market rate query.
    Must have BOTH a price intent keyword AND a location/commodity in price context.
    Hindi: "potato ka rate kya hai agra mein?" → True
    English: "wheat price in lucknow today" → True
    NOT: "what is the MSP for wheat" → False (MSP is knowledge, not live price)
    """
    msg_lower = message.lower()

    # Hindi price detection: price keyword + city name
    if any(k in msg_lower for k in _HINDI_PRICE_KEYWORDS):
        if any(city in msg_lower for city in _DISTRICT_NAMES):
            return True

    # English price detection: explicit "price in <city>" or "rate in <city>"
    price_words = {"price", "rate", "cost", "bhav", "daam"}
    has_price_word = any(w in msg_lower for w in price_words)
    has_location = any(city in msg_lower for city in _DISTRICT_NAMES)
    has_mandi = "mandi" in msg_lower or "market" in msg_lower

    if has_price_word and (has_location or has_mandi):
        return True

    return False


def _should_override_price(message: str) -> bool:
    """
    Returns True if the message should NOT go to the price slot filler,
    even if the ML classifier says price_enquiry.
    Catches: "MSP for wheat", "urea per acre for wheat", "PM-KISAN scheme",
             "NPK vs DAP", "seed rate for maize", "solar pump subsidy"
    """
    msg_lower = message.lower()

    # If message contains scheme/government keywords → not a price query
    if any(k in msg_lower for k in _SCHEME_KEYWORDS):
        return True

    # If message contains farming/knowledge keywords → not a price query
    if any(k in msg_lower for k in _FARMING_KEYWORDS):
        return True

    return False
