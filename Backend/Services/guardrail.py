from guardrails import Guard
from guardrails.hub import ToxicLanguage, DetectPII
from guardrails.types import OnFailAction
from config import CONFIG
from guardrails.hub import RegexMatch

def setup_guard(guardrail_level: str = None):
    """
    Returns a Guard object depending on the guardrail level.
    Fully driven from .env via CONFIG.
    """
    if guardrail_level is None:
        guardrail_level = CONFIG["default_guardrail_option"]

    guard = None

    if guardrail_level == "none":
        guard = None

    elif guardrail_level == "basic":
        guard = Guard().use(
            ToxicLanguage(threshold=CONFIG["toxicity_threshold_basic"])
        )

    elif guardrail_level == "strict":
        guard = Guard().use(
            ToxicLanguage(threshold=CONFIG["toxicity_threshold_strict"])
        ).use(
            DetectPII(
                pii_entities=CONFIG["pii_entities_strict"],
                on_fail=getattr(OnFailAction, CONFIG["onfailaction_strict"].upper())
            )
        )

    elif guardrail_level == "custom":
        guard = Guard().use(
            ToxicLanguage(
                threshold=CONFIG["toxicity_threshold_custom"],
                validation_method="sentence"
            )
        ).use(
            DetectPII(
                pii_entities=CONFIG["pii_entities_custom"],
                on_fail=getattr(OnFailAction, CONFIG["onfailaction_custom"].upper())
            )
        )

    else:
        raise ValueError(f"Invalid guardrail level: {guardrail_level}")

    return guard


def validate_output(final_answer: str, guardrail_level: str = None):
    """
    Validates LLM output against the selected guardrail.
    Fully driven from .env via CONFIG.
    Returns sanitized output or a blocked message.
    """
    guard = setup_guard(guardrail_level)

    if guard:
        try:
            validated = guard.validate(final_answer)
            final_answer = validated.validated_output.strip()
        except Exception as e:
            return {"answer": f"⚠️ Response blocked by guardrail: {str(e)}"}

    return {"answer": final_answer}
