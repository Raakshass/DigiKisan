"""
KisanMitra AI API — Disease Detection Router
==========================================
Handles crop disease detection and follow-up conversation:
- /disease/predict       — upload image → disease classification + Gemini summary
- /disease/chat          — follow-up conversation about detected disease
- /disease/chat/history  — get conversation history
- /disease/chat/clear    — clear conversation history
"""
import os
from typing import Dict, Any

from fastapi import APIRouter, Depends, Body, UploadFile, File

from app.services.image_classifier import CropDiseaseClassifier
from app.api.deps import GeminiChat, get_img_clf, get_gemini_chat

router = APIRouter(prefix="/disease", tags=["Disease Detection"])


@router.post("/predict")
async def disease_predict(
    file: UploadFile = File(...),
    img_clf: CropDiseaseClassifier = Depends(get_img_clf),
    gemini_chat: GeminiChat = Depends(get_gemini_chat),
):
    """Upload a crop image for disease detection. Returns prediction + AI summary."""
    if not file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
        return {"ok": False, "error": "Only PNG and JPEG files supported"}

    temp_dir = "tmp"
    os.makedirs(temp_dir, exist_ok=True)
    file_location = os.path.join(temp_dir, file.filename)

    try:
        with open(file_location, "wb") as f:
            f.write(await file.read())

        if img_clf.available:
            disease_prediction = img_clf.predict(file_location)
        else:
            # Fallback: use Gemini vision if classifier unavailable
            disease_prediction = "Unknown (classifier unavailable — run git lfs pull)"

        disease_summary = gemini_chat.get_disease_summary(disease_prediction)

        return {
            "ok": True,
            "prediction": disease_prediction,
            "ai_summary": disease_summary,
            "conversation_started": True,
            "message": "Analyzed your crop image and started a brief consultation.",
            "classifier_available": img_clf.available,
        }
    finally:
        try:
            os.remove(file_location)
        except Exception:
            pass


@router.post("/chat")
async def disease_chat(
    payload: Dict[str, Any] = Body(...),
    gemini_chat: GeminiChat = Depends(get_gemini_chat),
):
    """Continue conversation about a detected disease."""
    user_message = payload.get("message", "")
    disease_context = payload.get("disease_context", "")

    if not user_message.strip():
        return {"ok": False, "error": "Message cannot be empty"}
    if not disease_context.strip():
        return {"ok": False, "error": "Disease context required"}

    response = gemini_chat.continue_conversation(user_message, disease_context)
    return {"ok": True, "response": response, "disease_context": disease_context}


@router.get("/chat/history")
async def get_chat_history(gemini_chat: GeminiChat = Depends(get_gemini_chat)):
    """Get disease chat conversation history."""
    return {
        "ok": True,
        "history": gemini_chat.chat_history,
        "total_conversations": len(gemini_chat.chat_history),
    }


@router.post("/chat/clear")
async def clear_chat_history(gemini_chat: GeminiChat = Depends(get_gemini_chat)):
    """Clear disease chat conversation history."""
    gemini_chat.chat_history = []
    return {"ok": True, "message": "Chat history cleared successfully"}
