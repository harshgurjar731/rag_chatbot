"""
This module defines custom actions for NeMo Guardrails.

It includes actions for jailbreak detection (using Groq), content safety checks (using NVIDIA API),
topic control, and formatting safety violations for the frontend.
"""

from nemoguardrails.actions import action
from openai import AsyncOpenAI

from groq import AsyncGroq #type: ignore
import os
from dotenv import load_dotenv


load_dotenv()

# Initialize the NVIDIA API client
nvidia_client = AsyncOpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY")
)


groq_client = AsyncGroq(
    api_key=os.getenv("GROQ_API_KEY")
)

def get_model_name_from_config(context, config_name, default_model):
    """
    Retrieve user-configured model name from the context or return default.
    
    Args:
        context (dict): The current execution context containing config.
        config_name (str): The configuration key to look for (e.g., 'groq_jailbreak_model').
        default_model (str): The default model to use if not found.
        
    Returns:
        str: The resolved model name.
    """
    try:
        config = context.get("config")
        if config and hasattr(config, "models"):
            for model_config in config.models:
                if model_config.name == config_name:
                    return model_config.model
    except Exception:
        pass
    return default_model

# ---------------------------------------------------------------------------
# JAILBREAK CHECK (Input)
# ---------------------------------------------------------------------------
@action(name="check_jailbreak_groq")
async def check_jailbreak_groq(context: dict):
    """
    Check if the user input attempts to jailbreak the LLM using Llama Prompt Guard (via Groq).
    
    Args:
        context (dict): The current execution context containing the user message.
        
    Returns:
        bool: True if jailbreak is detected, False otherwise.
    """
    model_name = get_model_name_from_config(context, "groq_jailbreak_model", "meta-llama/llama-prompt-guard-2-86m")
    user_message = context.get("last_user_message") or context.get("user_message", "")
    print("In JailBreak GROQ", user_message)
    if not user_message: return False

    try:
        completion = await groq_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": user_message}],
            temperature=0.0,
            max_tokens=10
        )
        result = completion.choices[0].message.content.strip()
        # print(f"\n[DEBUG] Jailbreak ({model_name}) Output: {result}")

        # Check Float Score (Groq)
        try:
            if float(result) > 0.5: return True
        except ValueError:
            pass
            
        # Check Text Labels
        if "LABEL_1" in result or "unsafe" in result.lower(): return True
        
        return False
    except Exception as e:
        print(f"[ERROR] Jailbreak check failed: {e}")
        return False

# ---------------------------------------------------------------------------
# NEW: NVIDIA CONTENT SAFETY ACTION (Direct API Call)
# ---------------------------------------------------------------------------
import json # Ensure json is imported at top of file
# ... (Keep other imports)
@action(name="check_nvidia_content_safety")
async def check_nvidia_content_safety(context: dict):
    """
    Check content safety using NVIDIA's Content Safety model.
    
    Args:
        context (dict): The current execution context.
        
    Returns:
        str: 'safe' if content is safe, or a formatted 'BLOCK_PAYLOAD: ...' string with violation categories.
    """
    user_message = context.get("last_user_message") or context.get("user_message", "")
    if not user_message: return "safe"

    try:
        response = await nvidia_client.chat.completions.create(
            model="nvidia/llama-3.1-nemoguard-8b-content-safety",
            messages=[{"role": "user", "content": user_message}],
            max_tokens=50,
            temperature=0.0
        )
        
        result = response.choices[0].message.content.strip()
        
        # 1. Handle JSON
        if result.startswith("{") and "Safety Categories" in result:
            try:
                data = json.loads(result)
                if data.get("User Safety") == "unsafe":
                    categories = data.get("Safety Categories", "Unsafe Content")
                    # FIX: Use ||| separator to be safe for NeMo variables
                    return f"BLOCK_PAYLOAD: unsafe|||{categories}"
            except json.JSONDecodeError:
                pass

        # 2. Handle Plain Text
        if "unsafe" in result.lower():
            # FIX: Sanitize newlines
            clean_result = result.replace("\n", "|||")
            return f"BLOCK_PAYLOAD: {clean_result}"
            
        return "safe"

    except Exception as e:
        print(f"[ERROR] NVIDIA Safety Action failed: {e}")
        return "safe"
    

@action(name="topic_control_check")
async def topic_control_check(context: dict):
    """
    Check if user input is on-topic for a medical assistant using NVIDIA's topic control model.
    
    Retrieves system instructions from the config and compares the user input against allowed topics.
    
    Args:
        context (dict): The current execution context.
        
    Returns:
        str: 'on-topic' or 'off-topic'.
    """
    # Get the last user message from context
    # NeMo provides this as 'last_user_message'
    user_message = context.get("last_user_message", "")
    
    # Fallback: try getting from user_message key as well
    if not user_message:
        user_message = context.get("user_message", "")
    
    # Extract system instruction from config
    config = context.get("config")
    system_instruction = "You are a medical assistant chatbot. Provide responses related to medical topics, medicines, diagnosis, and others ."
    
    if config and hasattr(config, 'instructions'):
        for instruction in config.instructions:
            if hasattr(instruction, 'type') and instruction.type == "general":
                system_instruction = instruction.content
                break
    
    # print(f"[DEBUG] Topic control checking: '{user_message[:50]}...'")
    
    try:
        # Call NVIDIA's topic control model
        # This model expects the system instruction and conversation context
        response = await nvidia_client.chat.completions.create(
            model="nvidia/llama-3.1-nemoguard-8b-topic-control",
            messages=[
                {
                    "role": "system",
                    "content": system_instruction
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            max_tokens=10,
            temperature=0.0  # Deterministic output
        )
        
        result = response.choices[0].message.content.strip().lower()
        # print(f"[DEBUG] Topic control result: {result}")
        
        # Ensure we return a clean string
        if "off-topic" in result:
            return "off-topic"
        else:
            return "on-topic"
            
    except Exception as e:
        print(f"[ERROR] Topic control check failed: {e}")
        # On error, allow the message (fail open for safety)
        return "on-topic"
    

@action(name="format_safety_violation")
def format_safety_violation(data: dict) -> str:
    """
    Format a safety violation-payload into a user-facing blocking message.
    
    Args:
        data (dict): Dictionary containing violation details (e.g. "policy_violations").
        
    Returns:
        str: A formatted string starting with BLOCKED_SAFETY.
    """
    violations = data.get("policy_violations", [])
    
    if not violations:
        reason = "Unsafe Content"
    else:
        reason = ", ".join(violations)
        
    # FIX: Add the prefix HERE so Colang doesn't have to combine strings
    return f"BLOCKED_SAFETY: The query falls in the unsafe categories - {reason}"