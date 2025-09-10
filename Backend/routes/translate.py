# rag_app/backend/routes/translation.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from deep_translator import GoogleTranslator
from config import CONFIG  # ✅ centralized config

router = APIRouter()

class TranslateRequest(BaseModel):
    q: str
    source: str = CONFIG["default_translation_source"]   # ✅ pulled from .env
    target: str
    format: str = CONFIG["default_translation_format"]   # ✅ pulled from .env


@router.post("/translate")
def translate_text(request: TranslateRequest):
    """
    Translate text using deep_translator (Google Translate).
    Defaults (source, format) are read from .env via config.py
    """
    try:
        translated = GoogleTranslator(
            source=request.source,
            target=request.target
        ).translate(request.q)

        return {
            "sourceLang": request.source,
            "targetLang": request.target,
            "originalText": request.q,
            "translatedText": translated,
            "format": request.format,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")
