from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from deep_translator import GoogleTranslator

router = APIRouter()

class TranslateRequest(BaseModel):
    q: str
    source: str = "auto"
    target: str
    format: str = "text"

@router.post("/")
def translate_text(request: TranslateRequest):
    """
    Translate text using deep_translator (Google Translate).
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
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")