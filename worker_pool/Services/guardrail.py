import os
import nest_asyncio
from nemoguardrails import LLMRails, RailsConfig

nest_asyncio.apply()

_rails = None

def get_nemo_rails():
    """Lazy initialize NeMo Guardrails"""
    global _rails
    if _rails is None:
        try:
            # We locate the nemo_guardrails config directory within the rag_pipeline folder
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "rag_pipeline", "nemo_guardrails")
            config = RailsConfig.from_path(config_path)
            _rails = LLMRails(config, verbose=False)
            
            # Note: We do not need to register all custom actions here unless NeMo blocks on missing them,
            # because we are just using it to pass the output text as a user prompt to see if NeMo's
            # standard topic/jailbreak/safety rails block it.
            # To be safe, let's register the basic NVIDIA safety check.
            from rag_pipeline.nemo_guardrails.actions import check_nvidia_content_safety, topic_control_check, check_jailbreak_groq
            _rails.register_action(check_nvidia_content_safety)
            _rails.register_action(topic_control_check)
            _rails.register_action(check_jailbreak_groq)
        except Exception as e:
            print(f"[WARNING] Nemo Guardrails failed to initialize in output validator: {e}")
    return _rails

def validate_output(final_answer: str, guardrail_level: str = None):
    """
    Validates the LLM output using NeMo Guardrails instead of guardrails-ai.
    """
    if guardrail_level is None or guardrail_level.lower() in ["none", "off", "false"]:
        return {"answer": final_answer}

    rails = get_nemo_rails()
    if rails:
        try:
            # Run the output through NeMo as if it were a user prompt to detect any toxicity/PII/jailbreaks
            response = rails.generate(messages=[{"role": "user", "content": final_answer}])
            res_str = response.get("content", "") if isinstance(response, dict) else str(response)

            # Check if NeMo triggered a safety block
            if "BLOCKED_SAFETY:" in res_str or "unsafe" in res_str.lower() or "jailbreak" in res_str.lower() or "I'm not able to help" in res_str:
                return {"answer": f"⚠️ Response blocked by guardrail: The generated output violated safety policies."}
                
        except Exception as e:
            return {"answer": f"⚠️ Response blocked by guardrail: {str(e)}"}

    return {"answer": final_answer}
