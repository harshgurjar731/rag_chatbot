from guardrails import Guard
from guardrails.hub import ToxicLanguage, DetectPII
from guardrails.types import OnFailAction

def setup_guard(guardrail_level: str):
    """
    Returns a Guard object depending on the guardrail level.
    Supports ToxicLanguage and PII detection.
    """
    guard = None

    # ✅ Setup Guardrails depending on level
    if guardrail_level == "none":
        guard = None  # no validation

    elif guardrail_level == "basic":
        # Lenient toxic language detection
        guard = Guard().use(ToxicLanguage(threshold=0.9))

    elif guardrail_level == "strict":
        # Strict toxic language + PII detection
        guard = Guard().use(
            ToxicLanguage(threshold=0.5)
        ).use(
            DetectPII(
                pii_entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN"],
                on_fail=OnFailAction.FIX
            )
        )

    elif guardrail_level == "custom":
        # Custom thresholds and selective PII detection
        guard = Guard().use(
            ToxicLanguage(threshold=0.7, validation_method="sentence")
        ).use(
            DetectPII(
                pii_entities=["EMAIL_ADDRESS", "CREDIT_CARD"],
                on_fail=OnFailAction.FIX
            )
        )

    return guard


def validate_output(final_answer: str, guardrail_level: str):
    """
    Validates LLM output against the selected guardrail.
    Returns either sanitized output or a blocked message.
    """
    guard = setup_guard(guardrail_level)

    if guard:
        try:
            validated = guard.validate(final_answer)

            # ✅ Use validated/sanitized output
            final_answer = validated.validated_output.strip()

        except Exception as e:
            return {"answer": f"⚠️ Response blocked by guardrail: {str(e)}"}

    return {"answer": final_answer}
