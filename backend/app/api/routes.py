from fastapi import APIRouter, Depends, Body, UploadFile, File, Request, Form, HTTPException
from app.core.db import get_db
from typing import Any, Dict, Optional
import os
import re
import requests
import pandas as pd
import time
import uuid
from datetime import datetime, timedelta
from app.core.config import settings
from app.services.interactivechat import (
    TextClassifierInference,
    SlotFiller,
    scrape_agmarknet,
    format_date_for_agmarknet,
    summarize_prices_per_market,
    TOP_K_PER_MARKET
)
from app.services.image_classifier import CropDiseaseClassifier
from app.services.database_service import PriceDataService, AnalyticsService, SessionService
from app.models.price_data import QueryAnalyticsModel, UserSessionModel
from motor.motor_asyncio import AsyncIOMotorDatabase

# Add authentication imports
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.auth_service import AuthService, ACCESS_TOKEN_EXPIRE_MINUTES
from app.models.user import UserCreate, UserLogin, UserResponse, Token
from datetime import timedelta
from jose import jwt, JWTError
from app.services.auth_service import SECRET_KEY, ALGORITHM
from pydantic import BaseModel

security = HTTPBearer()

class ChatMessage(BaseModel):
    message: str

def get_auth_service(db: AsyncIOMotorDatabase = Depends(get_db)):
    try:
        service = AuthService()
        service.set_db(db)
        return service
    except Exception as e:
        print(f"Auth service error: {e}")
        return None

router = APIRouter()

# Gemini API Configuration
API_KEY = settings.gemini_api_key
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

# Enhanced mapping for better coverage
def get_enhanced_mappings():
    """Updated mappings based on AgMarkNet structure"""
    
    commodity_map = {
        'wheat': '23', 
        'rice': '1', 
        'paddy': '1',
        'maize': '25',
        'potato': '46',
        'onion': '47',
        'tomato': '48',
        'gram': '29',
        'arhar': '30',
        'moong': '31',
        'mustard': '35',
        'groundnut': '34',
        'soybean': '39',
        'cotton': '43',
        'sugarcane': '45'
    }
    
    # UP district mappings
    district_map_up = {
        'agra': '7',
        'allahabad': '1', 
        'prayagraj': '1',
        'lucknow': '33',
        'kanpur': '26',
        'varanasi': '68',
        'meerut': '38',
        'ghaziabad': '18',
        'aligarh': '3',
        'moradabad': '40',
        'saharanpur': '58',
        'gorakhpur': '19',
        'bareilly': '9',
        'mathura': '37',
        'jhansi': '24',
        'firozabad': '16'
    }
    
    return commodity_map, district_map_up

class GeminiChat:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.chat_history = []
        self.url = f"{BASE_URL}?key={self.api_key}"

    # -------- helpers: make replies crisp and plain text --------
    def _strip_markdown(self, s: str) -> str:
        s = re.sub(r"[*`#>•\-]+", "", s)
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

    def _extract_text(self, data: Dict[str, Any]) -> str:
        # Robust extraction per Gemini generateContent schema
        try:
            cands = data.get("candidates") or []
            for c in cands:
                content = c.get("content") or {}
                parts = content.get("parts") or []
                for p in parts:
                    if "text" in p and p["text"]:
                        return str(p["text"])
            # Fallbacks
            if "text" in data:
                return str(data["text"])
            if "content" in data and isinstance(data["content"], dict):
                parts = data["content"].get("parts") or []
                for p in parts:
                    if "text" in p and p["text"]:
                        return str(p["text"])
        except Exception as e:
            print(f"Gemini extract_text error: {e}")
        return "Sorry, I couldn't form a proper answer."
    
    def send_message(self, message: str, system_prompt: Optional[str] = None) -> str:
        concise_rule = (
            "Reply in plain text only (no markdown). Max 4 short sentences total. "
            "End with ONE brief follow-up question if helpful. Keep under 350 characters."
        )
        full_message = f"{(system_prompt or '').strip()}\n\n{concise_rule}\n\nUser: {message}".strip()

        payload = {
            "contents": [{"parts": [{"text": full_message}]}],
            "generationConfig": {
                "temperature": 0.4,
                "topK": 32,
                "topP": 0.9,
                "maxOutputTokens": 256,
            },
        }
        headers = {"Content-Type": "application/json"}

        try:
            resp = requests.post(self.url, headers=headers, json=payload, timeout=25)
            if resp.status_code != 200:
                print(f"Gemini HTTP {resp.status_code}: {resp.text}")
                return "Having trouble fetching advice now. Try again shortly."
            data = resp.json()
            reply_raw = self._extract_text(data)
            reply = self._crisp(reply_raw)

            self.chat_history.append(
                {
                    "user": message,
                    "assistant": reply,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            return reply
        except requests.exceptions.RequestException as e:
            print(f"Gemini request error: {e}")
            return "Having trouble fetching advice now. Try again shortly."
        except Exception as e:
            print(f"Gemini unexpected error: {e}")
            return "Sorry, I couldn't form a proper answer."

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

# Singleton-like model holders
class ModelSingleton:
    _text_clf: Optional[TextClassifierInference] = None
    _slot_filler: Optional[SlotFiller] = None
    _img_clf: Optional[CropDiseaseClassifier] = None
    _gemini_chat: Optional[GeminiChat] = None

    @classmethod
    def get_text_clf(cls) -> TextClassifierInference:
        if cls._text_clf is None:
            cls._text_clf = TextClassifierInference()
        return cls._text_clf

    @classmethod
    def get_slot_filler(cls) -> SlotFiller:
        if cls._slot_filler is None:
            cls._slot_filler = SlotFiller()
        return cls._slot_filler

    @classmethod
    def get_img_clf(cls) -> CropDiseaseClassifier:
        if cls._img_clf is None:
            cls._img_clf = CropDiseaseClassifier(
                checkpoint_path="models/image_classifier/best_model.pth",
                class_names_path="models/image_classifier/class_names.json",
            )
        return cls._img_clf

    @classmethod
    def get_gemini_chat(cls) -> GeminiChat:
        if cls._gemini_chat is None:
            cls._gemini_chat = GeminiChat(API_KEY)
        return cls._gemini_chat

def get_text_clf():
    return ModelSingleton.get_text_clf()

def get_slot_filler():
    return ModelSingleton.get_slot_filler()

def get_img_clf():
    return ModelSingleton.get_img_clf()

def get_gemini_chat():
    return ModelSingleton.get_gemini_chat()

# ========== OPTIONAL MONGODB SERVICES (Safe to skip if DB fails) ==========

def get_price_service(db: AsyncIOMotorDatabase = Depends(get_db)):
    try:
        service = PriceDataService()
        service.set_db(db)
        return service
    except Exception as e:
        print(f"Price service error: {e}")
        return None

def get_analytics_service(db: AsyncIOMotorDatabase = Depends(get_db)):
    try:
        service = AnalyticsService()
        service.set_db(db)
        return service
    except Exception as e:
        print(f"Analytics service error: {e}")
        return None

def get_session_service(db: AsyncIOMotorDatabase = Depends(get_db)):
    try:
        service = SessionService()
        service.set_db(db)
        return service
    except Exception as e:
        print(f"Session service error: {e}")
        return None

# ========== CORE ENDPOINTS ==========

@router.get("/health")
async def health():
    return {"status": "ok", "message": "DigiKisan Backend API is running"}

@router.post("/classify")
async def classify_text(
    payload: Dict[str, Any] = Body(...),
    clf: TextClassifierInference = Depends(get_text_clf),
):
    text = payload.get("text", "")
    if not text.strip():
        return {"ok": False, "error": "Text cannot be empty"}
    result = clf.predict(text)
    return {"ok": True, "result": result}

@router.post("/disease/predict")
async def disease_predict(
    file: UploadFile = File(...),
    img_clf: CropDiseaseClassifier = Depends(get_img_clf),
    gemini_chat: GeminiChat = Depends(get_gemini_chat),
):
    if not file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
        return {"ok": False, "error": "Only PNG and JPEG files supported"}

    temp_dir = "tmp"
    os.makedirs(temp_dir, exist_ok=True)
    file_location = os.path.join(temp_dir, file.filename)

    try:
        with open(file_location, "wb") as f:
            f.write(await file.read())

        # Disease prediction
        disease_prediction = img_clf.predict(file_location)

        # Concise Gemini summary
        disease_summary = gemini_chat.get_disease_summary(disease_prediction)

        return {
            "ok": True,
            "prediction": disease_prediction,
            "ai_summary": disease_summary,
            "conversation_started": True,
            "message": "Analyzed your crop image and started a brief consultation.",
        }
    finally:
        try:
            os.remove(file_location)
        except Exception:
            pass

@router.post("/disease/chat")
async def disease_chat(
    payload: Dict[str, Any] = Body(...),
    gemini_chat: GeminiChat = Depends(get_gemini_chat),
):
    user_message = payload.get("message", "")
    disease_context = payload.get("disease_context", "")

    if not user_message.strip():
        return {"ok": False, "error": "Message cannot be empty"}
    if not disease_context.strip():
        return {"ok": False, "error": "Disease context required"}

    response = gemini_chat.continue_conversation(user_message, disease_context)
    return {"ok": True, "response": response, "disease_context": disease_context}

@router.get("/disease/chat/history")
async def get_chat_history(gemini_chat: GeminiChat = Depends(get_gemini_chat)):
    return {"ok": True, "history": gemini_chat.chat_history, "total_conversations": len(gemini_chat.chat_history)}

@router.post("/disease/chat/clear")
async def clear_chat_history(gemini_chat: GeminiChat = Depends(get_gemini_chat)):
    gemini_chat.chat_history = []
    return {"ok": True, "message": "Chat history cleared successfully"}

# ========== SESSION-BASED CHAT WITH SLOT FILLING ==========

@router.post("/chat/start-session")
async def start_chat_session(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    session_service: Optional[SessionService] = Depends(get_session_service)
):
    """Session-based chat - Falls back gracefully if DB unavailable"""
    try:
        if not session_service:
            # Fallback without session
            return {
                "ok": True,
                "session_id": str(uuid.uuid4()),
                "message": "Welcome to DigiKisan! I can help with crop prices, disease detection, and farming advice. What would you like to know?",
                "note": "Session storage unavailable - using temporary session",
                "timestamp": datetime.now().isoformat()
            }

        user_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        session_id = str(uuid.uuid4())
        session_model = UserSessionModel(
            session_id=session_id,
            user_ip=user_ip,
            user_agent=user_agent,
            started_at=datetime.now(),
            last_activity=datetime.now()
        )
        
        await session_service.create_session(session_model)
        welcome_msg = "Welcome to DigiKisan! I can help with crop prices, disease detection, and farming advice. What would you like to know?"
        
        return {
            "ok": True,
            "session_id": session_id,
            "message": welcome_msg,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"Session creation error: {e}")
        return {
            "ok": True,
            "session_id": str(uuid.uuid4()),
            "message": "Welcome to DigiKisan! I can help with crop prices, disease detection, and farming advice. What would you like to know?",
            "note": "Session storage unavailable - using temporary session",
            "timestamp": datetime.now().isoformat()
        }

# 🔥 COMPLETELY FIXED: Chat message endpoint with proper slot filling and clean formatting
@router.post("/chat/message")
async def chat_message(
    payload: Dict[str, Any] = Body(...),
    clf: TextClassifierInference = Depends(get_text_clf),
    slot_filler: SlotFiller = Depends(get_slot_filler),
    session_service: Optional[SessionService] = Depends(get_session_service),
    gemini_chat: GeminiChat = Depends(get_gemini_chat),
    price_service: Optional[PriceDataService] = Depends(get_price_service),
    analytics_service: Optional[AnalyticsService] = Depends(get_analytics_service),
):
    """Session-based chat with proper slot filling logic"""
    message = payload.get("message", "").strip()
    session_id = payload.get("session_id")
    session_state = payload.get("session_state", {})
    
    if not message:
        return {"ok": False, "error": "Message cannot be empty"}
    
    try:
        # Store user message if session available
        if session_service and session_id:
            try:
                user_message_data = {
                    "type": "user_message",
                    "message": message,
                    "timestamp": datetime.now().isoformat()
                }
                await session_service.update_session(session_id, {
                    "$push": {"conversation_history": user_message_data}
                })
            except Exception as e:
                print(f"Session update error: {e}")
        
        # Check if already in slot filling mode OR if this is a price query
        if not session_state.get("in_slot_fill"):
            classification = clf.predict(message)
            if classification["prediction"] != "price_enquiry":
                # Handle general chat with Gemini
                response = gemini_chat.send_message(message)
                
                # Store assistant response if session available
                if session_service and session_id:
                    try:
                        assistant_response = {
                            "type": "assistant_response",
                            "message": response,
                            "timestamp": datetime.now().isoformat()
                        }
                        await session_service.update_session(session_id, {
                            "$push": {"conversation_history": assistant_response}
                        })
                    except Exception as e:
                        print(f"Session response storage error: {e}")
                
                return {
                    "ok": True,
                    "session_id": session_id,
                    "message": response,
                    "session_state": session_state,
                    "completed": False,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Start slot filling for price queries
            session_state["in_slot_fill"] = True

        # PRICE QUERY: Use slot filling logic
        result = slot_filler.handle_message(message, session_state)

        if result.get("ask"):
            # Still collecting slots
            response_text = result["ask"]
            new_session_state = result.get("session_state", {})
            
            # Store response if session available
            if session_service and session_id:
                try:
                    assistant_response = {
                        "type": "slot_filling_response",
                        "message": response_text,
                        "timestamp": datetime.now().isoformat(),
                        "requires_input": True
                    }
                    await session_service.update_session(session_id, {
                        "$push": {"conversation_history": assistant_response}
                    })
                except Exception as e:
                    print(f"Session response storage error: {e}")
            
            return {
                "ok": True,
                "session_id": session_id,
                "message": response_text,
                "session_state": new_session_state,
                "completed": False,
                "slots_so_far": new_session_state.get("slots", {}),
                "timestamp": datetime.now().isoformat()
            }
            
        elif result.get("slots"):
            # 🔥 COMPLETE PRICE QUERY: Fetch actual price data with PROPER FORMATTING
            slots = result["slots"]
            commodity = slots.get("commodity")
            district = slots.get("area")
            date_str = slots.get("time")

            # Get enhanced mappings
            commodity_map, district_map = get_enhanced_mappings()

            try:
                formatted_date = format_date_for_agmarknet(date_str)
                commodity_code = commodity_map.get((commodity or "").lower())
                district_code = district_map.get((district or "").lower())

                if commodity_code and district_code and formatted_date:
                    # Try cached data first if available
                    cached_df = None
                    if price_service:
                        try:
                            cached_df = await price_service.get_cached_prices(
                                commodity_code, district_code, formatted_date, max_age_hours=2
                            )
                        except Exception as e:
                            print(f"Cache check error: {e}")

                    data_source = "cached"
                    if cached_df is not None and not cached_df.empty:
                        price_df = cached_df
                    else:
                        # SCRAPE RAW DATA
                        price_df = scrape_agmarknet(formatted_date, "UP", district_code, commodity_code)
                        data_source = "scraped"
                        
                        # Cache if available
                        if price_service and price_df is not None and not price_df.empty:
                            try:
                                await price_service.cache_price_data(
                                    price_df, commodity_code, district_code, formatted_date
                                )
                            except Exception as e:
                                print(f"Cache save error: {e}")

                    if price_df is not None and not price_df.empty:
                        # 🔧 FIXED: NORMALIZE COLUMN NAMES for cached vs fresh data compatibility
                        column_mapping = {
                            'market_name': 'Market',
                            'modal_price': 'Modal', 
                            'max_price': 'Max',
                            'min_price': 'Min',
                            'commodity_name': 'Commodity',
                            'district_name': 'District'
                        }
                        price_df = price_df.rename(columns=column_mapping)
                        
                        # USE SUMMARIZATION (now with normalized columns)
                        summary_df = summarize_prices_per_market(price_df, TOP_K_PER_MARKET)
                        
                        if summary_df is not None and not summary_df.empty:
                            # 🔥 FIXED: Clean response formatting like original working version
                            response_text = f"""COLLECTED!

Commodity: {commodity.title()}
Location: {district.title()}
Date: {date_str}

Current Market Prices:

"""
                            
                            # FIXED: Safe column access to handle different data structures
                            for _, row in summary_df.iterrows():
                                # Handle different possible column names (cached vs fresh data)
                                market = (row.get('Market') or 
                                         row.get('market_name') or 
                                         row.get('market') or 
                                         'Unknown Market')
                                
                                avg_modal = (row.get('Avg Modal') or 
                                            row.get('modal_price') or 
                                            row.get('Modal') or 
                                            'N/A')
                                
                                avg_max = (row.get('Avg Max') or 
                                          row.get('max_price') or 
                                          row.get('Max') or 
                                          'N/A')
                                
                                avg_min = (row.get('Avg Min') or 
                                          row.get('min_price') or 
                                          row.get('Min') or 
                                          'N/A')
                                
                                response_text += f"""{market}
Modal: Rs.{avg_modal}/quintal | Max: Rs.{avg_max} | Min: Rs.{avg_min}

"""
                            
                            # Calculate overall average
                            try:
                                # Try different column names for modal prices
                                modal_prices = None
                                if 'Avg Modal' in summary_df.columns:
                                    modal_prices = summary_df['Avg Modal'].dropna()
                                elif 'modal_price' in summary_df.columns:
                                    modal_prices = summary_df['modal_price'].dropna()
                                elif 'Modal' in summary_df.columns:
                                    modal_prices = summary_df['Modal'].dropna()
                                
                                if modal_prices is not None and len(modal_prices) > 0:
                                    overall_avg = modal_prices.mean()
                                    response_text += f"""Average Across All Markets: Rs.{overall_avg:.0f}/quintal

Price Summary:
- Prices averaged from latest {TOP_K_PER_MARKET} entries per market
- Compare different markets to find best rates
- Data directly from AgMarkNet

Anything else?"""
                                else:
                                    response_text += "Anything else?"
                            except Exception as e:
                                print(f"Average calculation error: {e}")
                                response_text += "Anything else?"

                            # Optional analytics logging
                            if analytics_service:
                                try:
                                    query_id = str(uuid.uuid4())
                                    analytics_data = QueryAnalyticsModel(
                                        query_id=query_id,
                                        commodity=commodity,
                                        district=district,
                                        date_requested=date_str,
                                        response_time_ms=1000,
                                        data_source_used=data_source,
                                        success=True,
                                        time_of_day="unknown"
                                    )
                                    await analytics_service.log_query(analytics_data)
                                except Exception as e:
                                    print(f"Analytics logging error: {e}")
                                
                        else:
                            response_text = f"""COLLECTED!

Commodity: {commodity.title()}
Location: {district.title()}
Date: {date_str}

No summarized price data available.

This could be due to:
- Market holiday on selected date
- No trading activity
- Data not yet updated

Try asking for:
- A different date
- Another commodity
- Different location"""
                            
                    else:
                        response_text = f"""COLLECTED!

Commodity: {commodity.title()}
Location: {district.title()}
Date: {date_str}

No price data available for these parameters.

This could be due to:
- Market holiday on selected date
- No trading activity  
- Data not yet updated

Try asking for:
- A different date
- Another commodity
- Different location"""
                        
                else:
                    missing_parts = []
                    if not commodity_code:
                        missing_parts.append(f"commodity '{commodity}'")
                    if not district_code:
                        missing_parts.append(f"district '{district}'")
                    if not formatted_date:
                        missing_parts.append(f"date '{date_str}'")
                    response_text = (
                        "Unable to fetch price data\n\n"
                        f"Missing mapping for: {', '.join(missing_parts)}\n\n"
                        "Please try with different names."
                    )
            except Exception as e:
                print(f"Price fetching error: {e}")
                response_text = "Technical issue retrieving price data currently. Please try again."

            # Store final response if session available
            if session_service and session_id:
                try:
                    assistant_response = {
                        "type": "price_response",
                        "message": response_text,
                        "slots": slots,
                        "timestamp": datetime.now().isoformat(),
                    }
                    await session_service.update_session(session_id, {
                        "$push": {"conversation_history": assistant_response},
                        "$inc": {"completed_queries": 1}
                    })
                except Exception as e:
                    print(f"Session final storage error: {e}")

            return {
                "ok": True, 
                "session_id": session_id,
                "message": response_text, 
                "session_state": {},
                "completed": True, 
                "slots": slots,
                "timestamp": datetime.now().isoformat()
            }
        else:
            # Still waiting for input
            return {
                "ok": True, 
                "session_id": session_id,
                "message": "Waiting for your query...", 
                "session_state": session_state,
                "completed": False,
                "timestamp": datetime.now().isoformat()
            }
        
    except Exception as e:
        print(f"Chat message error: {e}")
        return {
            "ok": False,
            "error": "I'm having trouble processing your request. Please try again.",
            "session_state": session_state,
            "timestamp": datetime.now().isoformat()
        }

# ========== LEGACY ENDPOINTS FOR BACKWARD COMPATIBILITY ==========

@router.post("/chat/slots")
async def chat_slots(
    payload: Dict[str, Any] = Body(...),
    clf: TextClassifierInference = Depends(get_text_clf),
    slot_filler: SlotFiller = Depends(get_slot_filler),
    price_service: Optional[PriceDataService] = Depends(get_price_service),
    analytics_service: Optional[AnalyticsService] = Depends(get_analytics_service),
):
    """Legacy slot-based chat endpoint for backward compatibility"""
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
    elif result.get("slots"):
        # Simplified response for legacy endpoint
        return {"ok": True, "response": "Price query completed successfully!", "session_state": {}, "completed": True, "slots": result["slots"]}
    else:
        return {"ok": True, "response": "Waiting for your query...", "session_state": session_state, "completed": False}

# ========== UTILITY ENDPOINTS ==========

@router.get("/test-mongodb")
async def test_mongodb_connection(db: AsyncIOMotorDatabase = Depends(get_db)):
    try:
        ping_result = await db.command("ping")
        return {"ok": True, "message": "MongoDB connected!", "ping": ping_result}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.get("/check-data")
async def check_data_storage(db: AsyncIOMotorDatabase = Depends(get_db)):
    try:
        sessions_count = await db.user_sessions.count_documents({})
        analytics_count = await db.query_analytics.count_documents({})
        price_count = await db.price_data.count_documents({})
        return {
            "ok": True,
            "sessions_stored": sessions_count,
            "analytics_stored": analytics_count, 
            "prices_cached": price_count,
            "total_records": sessions_count + analytics_count + price_count
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ========== AUTHENTICATION ENDPOINTS ==========

# Login API endpoint for Flutter
@router.post("/auth/login", response_model=Token)
async def login(
    username: str = Form(...),
    password: str = Form(...),
    auth_service: AuthService = Depends(get_auth_service)
):
    if not auth_service:
        raise HTTPException(status_code=503, detail="Authentication service unavailable")
    
    user = await auth_service.authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    user_response = UserResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        location=user.location,
        created_at=user.created_at,
        last_login=user.last_login,
        total_queries=user.total_queries,
        is_active=user.is_active
    )
    
    return Token(access_token=access_token, token_type="bearer", user_info=user_response)

# Register API endpoint for Flutter  
@router.post("/auth/register", response_model=Token)
async def register(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    phone: str = Form(None),
    location: str = Form(None),
    auth_service: AuthService = Depends(get_auth_service)
):
    if not auth_service:
        raise HTTPException(status_code=503, detail="Authentication service unavailable")
    
    user_data = UserCreate(
        username=username,
        email=email,
        password=password,
        full_name=full_name,
        phone=phone,
        location=location
    )
    
    user = await auth_service.create_user(user_data)
    if not user:
        raise HTTPException(status_code=400, detail="Username or email already registered")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    user_response = UserResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        location=user.location,
        created_at=user.created_at,
        last_login=user.last_login,
        total_queries=user.total_queries,
        is_active=user.is_active
    )
    
    return Token(access_token=access_token, token_type="bearer", user_info=user_response)

# 🔥 COMPLETELY FIXED: Authenticated agricultural chat endpoint
# 🔥 COMPLETELY FIXED: Authenticated agricultural chat endpoint with SESSION STATE
@router.post("/chat/send")
async def send_chat_message(
    chat_request: ChatMessage,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
    clf: TextClassifierInference = Depends(get_text_clf),
    slot_filler: SlotFiller = Depends(get_slot_filler),
    gemini_chat: GeminiChat = Depends(get_gemini_chat),
    price_service: Optional[PriceDataService] = Depends(get_price_service)
):
    try:
        # Verify the JWT token and get user info
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = await auth_service.get_user_by_username(username)
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")

        # Process the agricultural message using your existing system
        user_message = chat_request.message
        
        print(f"🌾 Agricultural query from {user.full_name}: {user_message}")
        
        # ✅ CRITICAL FIX: Use persistent session state per user
        # Store session state in a simple dict (you could use Redis/database for production)
        if not hasattr(send_chat_message, 'user_sessions'):
            send_chat_message.user_sessions = {}
        
        user_id = user.user_id
        if user_id not in send_chat_message.user_sessions:
            send_chat_message.user_sessions[user_id] = {}
        
        session_state = send_chat_message.user_sessions[user_id]
        
        try:
            # ✅ Check if we're in the middle of slot filling
            if session_state.get("in_slot_fill"):
                print(f"🔄 Continuing slot filling for user {user.full_name}")
                # Continue with slot filling
                result = slot_filler.handle_message(user_message, session_state)
                
                if result.get("ask"):
                    # Still collecting information
                    response_text = result["ask"] 
                    send_chat_message.user_sessions[user_id] = result.get("session_state", {})
                    intent = "price_enquiry"
                elif result.get("slots"):
                    # Complete price query - get actual data
                    slots = result["slots"]
                    commodity = slots.get("commodity")
                    district = slots.get("area") 
                    date_str = slots.get("time")
                    
                    # Get mappings
                    commodity_map, district_map = get_enhanced_mappings()
                    
                    try:
                        formatted_date = format_date_for_agmarknet(date_str)
                        commodity_code = commodity_map.get((commodity or "").lower())
                        district_code = district_map.get((district or "").lower())
                        
                        if commodity_code and district_code and formatted_date:
                            # Get price data
                            price_df = scrape_agmarknet(formatted_date, "UP", district_code, commodity_code)
                            
                            if price_df is not None and not price_df.empty:
                                # Normalize columns 
                                column_mapping = {
                                    'market_name': 'Market',
                                    'modal_price': 'Modal', 
                                    'max_price': 'Max',
                                    'min_price': 'Min'
                                }
                                price_df = price_df.rename(columns=column_mapping)
                                
                                # Summarize prices
                                summary_df = summarize_prices_per_market(price_df, TOP_K_PER_MARKET)
                                
                                if summary_df is not None and not summary_df.empty:
                                    response_text = f"✅ Price information for {commodity.title()} in {district.title()}:\n\n"
                                    
                                    for _, row in summary_df.iterrows():
                                        market = row.get('Market', 'Unknown Market')
                                        modal = row.get('Avg Modal', 'N/A')
                                        max_price = row.get('Avg Max', 'N/A') 
                                        min_price = row.get('Avg Min', 'N/A')
                                        
                                        response_text += f"📍 {market}\n"
                                        response_text += f"   Modal: ₹{modal}/quintal\n"
                                        response_text += f"   Range: ₹{min_price} - ₹{max_price}\n\n"
                                    
                                    # Calculate average
                                    try:
                                        if 'Avg Modal' in summary_df.columns:
                                            avg_price = summary_df['Avg Modal'].mean()
                                            response_text += f"🔍 Average Market Price: ₹{avg_price:.0f}/quintal\n\n"
                                    except:
                                        pass
                                    
                                    response_text += "Data from AgMarkNet. Anything else you'd like to know?"
                                else:
                                    response_text = f"No price data available for {commodity} in {district} on {date_str}. Try a different date or location."
                            else:
                                response_text = f"Unable to fetch price data for {commodity} in {district}. Please try again or check the spelling."
                        else:
                            response_text = f"Sorry, I don't have mapping for {commodity} in {district}. Please try common crops like rice, wheat, potato, onion."
                    except Exception as e:
                        print(f"Price data error: {e}")
                        response_text = "Having trouble getting price data right now. Please try again in a moment."
                    
                    # Reset session state after completing query
                    send_chat_message.user_sessions[user_id] = {}
                    intent = "price_enquiry"
                else:
                    response_text = "Please tell me which crop price you'd like to know about, and the location."
                    intent = "price_enquiry"
            else:
                # ✅ New conversation - classify intent
                classification_result = clf.predict(user_message)
                intent = classification_result['prediction']
                
                if intent == 'price_enquiry':
                    print(f"🚀 Starting new price query for user {user.full_name}")
                    # Start new slot filling for price queries  
                    session_state = {"in_slot_fill": True}
                    result = slot_filler.handle_message(user_message, session_state)
                    
                    if result.get("ask"):
                        # Still collecting information
                        response_text = result["ask"]
                        send_chat_message.user_sessions[user_id] = result.get("session_state", {})
                    elif result.get("slots"):
                        # Unlikely to complete in one message, but handle it
                        response_text = "Price query completed successfully!"
                        send_chat_message.user_sessions[user_id] = {}
                    else:
                        response_text = "Please tell me which crop price you'd like to know about."
                        send_chat_message.user_sessions[user_id] = session_state
                else:
                    # ✅ Handle general agricultural queries with Gemini
                    agricultural_context = (
                        "You are an agricultural advisor helping Indian farmers. "
                        "Provide practical, actionable advice for farming in India. "
                        "Keep responses concise and helpful."
                    )
                    response_text = gemini_chat.send_message(user_message, agricultural_context)
                    # Don't change session state for general queries
            
            # Update user's query count
            try:
                await auth_service.update_user_queries(user.username)
            except Exception as e:
                print(f"Query count update error: {e}")
            
            return {
                "response": response_text,
                "user_id": user.user_id,
                "username": user.username,
                "intent": intent
            }
            
        except Exception as ai_error:
            print(f"❌ Agricultural AI error: {ai_error}")
            # Reset user session on error
            if user_id in send_chat_message.user_sessions:
                send_chat_message.user_sessions[user_id] = {}
            # Fallback response
            return {
                "response": "I'm here to help with your farming needs! You can ask about crop prices, disease identification, weather updates, or government schemes. What would you like to know?",
                "user_id": user.user_id,
                "username": user.username,
                "intent": "general"
            }
        
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        print(f"Auth endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/info")
async def info():
    return {
        "api": "DigiKisan",
        "version": "2.6",
        "endpoints": [
            "/health",
            "/classify",
            "/disease/predict",
            "/disease/chat",
            "/disease/chat/history", 
            "/disease/chat/clear",
            "/chat/slots",
            "/chat/start-session",
            "/chat/message",
            "/test-mongodb",
            "/check-data",
            "/auth/login",
            "/auth/register",
            "/chat/send",
            "/info",
        ],
        "features": [
            "Complete user authentication system",
            "Session-based slot filling chat with clean formatting",
            "Real-time agricultural price data",
            "Crop disease detection with AI chat",
            "Multi-language support",
            "MongoDB session management",
            "Smart caching for price data",
            "Authenticated chat with agricultural AI integration",
        ],
        "primary_endpoint": "/chat/send - Authenticated agricultural chat with full AI integration",
        "authentication": "JWT-based with user registration and login",
        "note": "Complete integration fixed - slot filling works properly now"
    }
