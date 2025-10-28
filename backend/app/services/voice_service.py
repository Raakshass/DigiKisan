import requests
import base64
from typing import Optional, Dict, Any
import tempfile
import os
from app.core.config import settings

class SarvamVoiceService:
    def __init__(self):
        self.api_key = getattr(settings, 'sarvam_api_key', 'your-sarvam-api-key')
        self.base_url = "https://api.sarvam.ai"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    # Language code mappings for Sarvam
    def get_sarvam_language_code(self, flutter_lang_code: str) -> str:
        """Map Flutter language codes to Sarvam language codes"""
        mapping = {
            'en-IN': 'en-IN',
            'hi-IN': 'hi-IN',
            'bn-IN': 'bn-IN',
            'ta-IN': 'ta-IN',
            'te-IN': 'te-IN',
            'mr-IN': 'mr-IN',
            'gu-IN': 'gu-IN',
            'kn-IN': 'kn-IN',
            'ml-IN': 'ml-IN',
            'pa-IN': 'pa-IN',
            'or-IN': 'or-IN'
        }
        return mapping.get(flutter_lang_code, 'en-IN')

    async def speech_to_text(self, audio_base64: str, language_code: str = 'en-IN') -> Dict[str, Any]:
        """Convert speech to text using Sarvam STT"""
        try:
            sarvam_lang = self.get_sarvam_language_code(language_code)
            
            payload = {
                "language_code": sarvam_lang,
                "audio_base64": audio_base64,
                "model": "saaras:v1"  # Sarvam's STT model
            }

            response = requests.post(
                f"{self.base_url}/speech-to-text",
                headers=self.headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "ok": True,
                    "text": result.get("transcript", ""),
                    "language": sarvam_lang,
                    "confidence": result.get("confidence", 0.0)
                }
            else:
                return {
                    "ok": False,
                    "error": f"STT API error: {response.status_code}",
                    "details": response.text
                }

        except Exception as e:
            return {
                "ok": False,
                "error": f"STT processing error: {str(e)}"
            }

    async def text_to_speech(self, text: str, language_code: str = 'en-IN') -> Dict[str, Any]:
        """Convert text to speech using Sarvam TTS"""
        try:
            sarvam_lang = self.get_sarvam_language_code(language_code)
            
            # Select appropriate voice based on language
            voice_mapping = {
                'en-IN': 'meera',
                'hi-IN': 'aditi',
                'bn-IN': 'rashika',
                'ta-IN': 'amala',
                'te-IN': 'shreya',
                'mr-IN': 'shantanu',
                'gu-IN': 'kinjal',
                'kn-IN': 'nayana',
                'ml-IN': 'nandu',
                'pa-IN': 'kamaljeet',
                'or-IN': 'sibani'
            }
            
            payload = {
                "inputs": [text],
                "target_language_code": sarvam_lang,
                "speaker": voice_mapping.get(sarvam_lang, 'meera'),
                "pitch": 0,
                "pace": 1.65,
                "loudness": 1.5,
                "speech_sample_rate": 8000,
                "enable_preprocessing": True,
                "model": "bulbul:v1"  # Sarvam's TTS model
            }

            response = requests.post(
                f"{self.base_url}/text-to-speech",
                headers=self.headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "ok": True,
                    "audio_base64": result.get("audios", [""])[0],
                    "language": sarvam_lang,
                    "speaker": voice_mapping.get(sarvam_lang, 'meera')
                }
            else:
                return {
                    "ok": False,
                    "error": f"TTS API error: {response.status_code}",
                    "details": response.text
                }

        except Exception as e:
            return {
                "ok": False,
                "error": f"TTS processing error: {str(e)}"
            }
