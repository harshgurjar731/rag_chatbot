import os
import subprocess
import tempfile
from mistralai import Mistral
from dotenv import load_dotenv
from rag_pipeline.Config.rag_config import RAG_CONFIG
from langchain_core.prompts import PromptTemplate
from rag_pipeline.Services.intent_service import create_llm_model
import json

# Load environment variables
load_dotenv()

# Initialize Mistral Client
# MISTRAL_API_KEY should be passed or in env
mistral_api_key = "ZpuwhInKUMLpkFTtA9zKmu7n0vxhLFRJ"
mistral_model = "voxtral-mini-latest"

def get_mistral_client():
    if not mistral_api_key:
        print("Warning: MISTRAL_API_KEY not found in environment variables.")
        return None
    return Mistral(api_key=mistral_api_key)

def extract_audio_to_mp3(video_path, output_audio_path):
    """Extract audio from video and convert to MP3"""
    # Verify ffmpeg presence (optional, subprocess will fail otherwise)
    command = [
        'ffmpeg',
        '-i', video_path,
        '-vn',
        '-acodec', 'libmp3lame',
        '-ab', '128k',
        '-ar', '44100',
        '-y',
        output_audio_path
    ]
    
    print(f"[INFO] Extracting audio from {video_path}...")
    try:
        subprocess.run(command, check=True, capture_output=True)
        print(f"[INFO] Audio extracted to {output_audio_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] ffmpeg failed: {e.stderr.decode()}")
        return False
    except FileNotFoundError:
        print("[ERROR] ffmpeg not found. Please install ffmpeg.")
        return False


def transcribe_audio(audio_path):
    """Upload audio to Mistral and get transcription"""
    client = get_mistral_client()
    if not client:
        raise ValueError("Mistral Client not initialized. Check API Key.")

    print(f"[INFO] Uploading audio to Mistral API...")
    
    # Upload the audio file
    with open(audio_path, "rb") as f:
        uploaded_audio = client.files.upload(
            file={
                "content": f,
                "file_name": os.path.basename(audio_path),
            },
            purpose="audio"
        )
    
    print(f"[INFO] Audio uploaded. File ID: {uploaded_audio.id}")
    
    # Get signed URL
    signed_url = client.files.get_signed_url(file_id=uploaded_audio.id)
    print(f"[INFO] Got signed URL. Requesting transcription...")
    
    # Get transcription
    transcription_response = client.audio.transcriptions.complete(
        model=mistral_model,
        file_url=signed_url.url,
        language="en"
    )
    
    return transcription_response.text

async def generate_intent_and_description(transcription: str):
    """
    Use the system's LLM to summarize the transcription into an Intent and Description.
    Returns dict: {"intent": str, "description": str}
    """
    
    provider = RAG_CONFIG.get("default_llm_provider", "groq")
    model_name = RAG_CONFIG.get("default_llm_model", "llama-3.3-70b-versatile")
    temperature = 0.1
    max_tokens = 512
    
    try:
        llm = create_llm_model(provider, model_name, temperature, max_tokens)
    except Exception as e:
        print(f"Error creating LLM: {e}")
        return {"intent": "Video Transcription", "description": transcription[:500]}

    prompt_template = """
    You are an expert content analyzer. 
    Analyze the following video transcription and extract a concise "Intent" (a short category title, 2-5 words) and a "Description" (a helpful summary or instruction for an AI assistant on how to handle this topic, 1-3 sentences).
    
    Transcription:
    {transcription}
    
    Return the result as a VALID JSON object with keys "intent" and "description".
    Do NOT add any markdown formatting like ```json.
    """
    
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | llm
    
    try:
        response = await chain.ainvoke({"transcription": transcription})
        content = response.content.strip()
        
        # Clean potential markdown
        if content.startswith('```json'):
            content = content.replace('```json', '').replace('```', '')
        
        return json.loads(content)
    except Exception as e:
        print(f"Error generating intent: {e}")
        # Fallback
        return {
            "intent": "Video Content", 
            "description": f"Transcription: {transcription[:200]}..."
        }

async def process_video(video_path: str):
    """
    Main orchestration function.
    1. Extract Audio
    2. Transcribe
    3. Generate Intent/Description
    Returns: dict with intent, description, transcription
    """
    
    # Create temp audio path
    base, _ = os.path.splitext(video_path)
    audio_path = f"{base}_audio.mp3"
    
    audio_extracted = extract_audio_to_mp3(video_path, audio_path)
    if not audio_extracted:
        raise Exception("Failed to extract audio from video.")
        
    try:
        transcription = transcribe_audio(audio_path)
        print(f"[INFO] Transcription length: {len(transcription)}")
        
        metadata = await generate_intent_and_description(transcription)
        metadata["transcription"] = transcription # Optional: return full text if needed
        
        return metadata
    finally:
        # Cleanup audio file
        if os.path.exists(audio_path):
            os.remove(audio_path)
