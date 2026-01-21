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
    # api_key="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",
)


groq_client = AsyncGroq(
    api_key=os.getenv("GROQ_API_KEY")
    #api_key="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",
)

def get_model_name_from_config(context, config_name, default_model):
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

# [Keep existing imports at the top]

# ---------------------------------------------------------------------------
# NEW: NVIDIA CONTENT SAFETY ACTION (Direct API Call)
# ---------------------------------------------------------------------------
import json # Ensure json is imported at top of file
# ... (Keep other imports)
@action(name="check_nvidia_content_safety")
async def check_nvidia_content_safety(context: dict):
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
    
      # ---------------------------------------------------------------------------
# CONTENT SAFETY CHECK (Input)
# # ---------------------------------------------------------------------------
# @action(name="check_content_safety_groq")
# async def check_content_safety_groq(context: dict):
#     model_name = get_model_name_from_config(context, "groq_content_safety_model", "meta-llama/llama-guard-4-12b")
#     user_message = context.get("last_user_message") or context.get("user_message", "")
    
#     if not user_message: return "safe"

#     try:
#         completion = await groq_client.chat.completions.create(
#             model=model_name,
#             messages=[{"role": "user", "content": user_message}],
#             temperature=0.0
#         )
#         result = completion.choices[0].message.content.strip().lower()
#         if result.startswith("unsafe"): return "unsafe"
#         return "safe"
#     except Exception as e:
#         print(f"[ERROR] Input Safety check failed: {e}")
#         return "safe"

# ---------------------------------------------------------------------------
# CONTENT SAFETY CHECK (Output) - NEW
# ---------------------------------------------------------------------------
# @action(name="check_content_safety_output_groq")
# async def check_content_safety_output_groq(context: dict):
#     model_name = get_model_name_from_config(context, "groq_content_safety_model", "meta-llama/llama-guard-4-12b")
    
#     # CRITICAL: For output rails, we need the BOT's message
#     bot_message = context.get("bot_message", "")
    
#     if not bot_message: return "safe"

#     try:
#         # Llama Guard expects "Agent" role for bot output checking usually, 
#         # but simpler user-role check works for general toxicity.
#         # Ideally, Llama Guard Prompt format: 
#         # User: [Msg]
#         # Agent: [Msg]
#         # But here we just check the bot message content for safety.
#         completion = await groq_client.chat.completions.create(
#             model=model_name,
#             messages=[{"role": "user", "content": bot_message}],
#             temperature=0.0
#         )
#         result = completion.choices[0].message.content.strip().lower()
        
#         # print(f"[DEBUG] Output Safety Check: {result}")
        
#         if result.startswith("unsafe"): return "unsafe"
#         return "safe"
#     except Exception as e:
#         print(f"[ERROR] Output Safety check failed: {e}")
#         return "safe"




@action(name="topic_control_check")
async def topic_control_check(context: dict):
    """
    Check if user input is on-topic for a medical assistant using NVIDIA's topic control model.
    Returns 'on-topic' or 'off-topic'.
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
    


# In actions.py

# In actions.py
# In actions.py
# In actions.py

@action(name="format_safety_violation")
def format_safety_violation(data: dict) -> str:
    violations = data.get("policy_violations", [])
    
    if not violations:
        reason = "Unsafe Content"
    else:
        reason = ", ".join(violations)
        
    # FIX: Add the prefix HERE so Colang doesn't have to combine strings
    return f"BLOCKED_SAFETY: The query falls in the unsafe categories - {reason}"