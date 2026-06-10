"""
KisanMitra AI API — Voice Router
==============================
Handles voice input/output via Sarvam AI:
- /voice/stt        — speech-to-text
- /voice/tts        — text-to-speech
- /voice/translate   — translate text between languages
"""
from typing import Dict, Any

from fastapi import APIRouter, Depends, Body

from app.services.voice_service import SarvamVoiceService

router = APIRouter(prefix="/voice", tags=["Voice"])


def get_voice_service() -> SarvamVoiceService:
    return SarvamVoiceService()


@router.post("/stt")
async def speech_to_text(
    payload: Dict[str, Any] = Body(...),
    voice_service: SarvamVoiceService = Depends(get_voice_service),
):
    """Convert speech audio (base64) to text."""
    audio_base64 = payload.get("audio_base64", "")
    language_code = payload.get("language_code", "en-IN")

    if not audio_base64:
        return {"ok": False, "error": "audio_base64 is required"}

    result = await voice_service.speech_to_text(audio_base64, language_code)
    return result


@router.post("/tts")
async def text_to_speech(
    payload: Dict[str, Any] = Body(...),
    voice_service: SarvamVoiceService = Depends(get_voice_service),
):
    """Convert text to speech audio (base64)."""
    text = payload.get("text", "")
    language_code = payload.get("language_code", "en-IN")

    if not text.strip():
        return {"ok": False, "error": "text is required"}

    result = await voice_service.text_to_speech(text, language_code)
    return result


@router.post("/translate")
async def translate_text(
    payload: Dict[str, Any] = Body(...),
    voice_service: SarvamVoiceService = Depends(get_voice_service),
):
    """Translate text between languages using Sarvam AI."""
    text = payload.get("text", "")
    source_lang = payload.get("source_language", "en-IN")
    target_lang = payload.get("target_language", "hi-IN")

    if not text.strip():
        return {"ok": False, "error": "text is required"}

    # Sarvam translate endpoint
    import requests
    try:
        headers = {
            "Authorization": f"Bearer {voice_service.api_key}",
            "Content-Type": "application/json",
        }
        resp = requests.post(
            f"{voice_service.base_url}/translate",
            headers=headers,
            json={
                "input": text,
                "source_language_code": source_lang,
                "target_language_code": target_lang,
                "speaker_gender": "Female",
                "mode": "formal",
                "model": "mayura:v1",
                "enable_preprocessing": True,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            result = resp.json()
            return {
                "ok": True,
                "translated_text": result.get("translated_text", ""),
                "source_language": source_lang,
                "target_language": target_lang,
            }
        else:
            return {
                "ok": False,
                "error": f"Translation API error: {resp.status_code}",
                "details": resp.text,
            }
    except Exception as e:
        return {"ok": False, "error": f"Translation error: {str(e)}"}
