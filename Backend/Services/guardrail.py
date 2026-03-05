import os
from nemoguardrails import LLMRails, RailsConfig

def validate_output(final_answer: str, guardrail_level: str = None):
    """
    Backend stub for validate_output. The actual validation happens in the worker_pool.
    """
    return {"answer": final_answer}
