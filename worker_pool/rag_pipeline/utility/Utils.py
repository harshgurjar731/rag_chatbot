"""
Shared Utility Functions

This module contains helper functions used across the RAG pipeline, such as prompt formatting.
"""

def get_final_prompt(prompt: str, use_knowledge_base: bool, include_sources: bool) -> str:
    """
    Construct the final prompt string by appending instructions for source citation if needed.

    Args:
        prompt (str): The base system prompt.
        use_knowledge_base (bool): Whether the knowledge base is being used.
        include_sources (bool): Whether the user requested source citations.

    Returns:
        str: The fully constructed prompt string.
    """
    base_prompt = prompt
    sources_instruction = (
        "\n\nAfter the main answer, include a section titled Sources listing "
        + (
            "the documents, filenames, or context snippets from the knowledge base that were used."
            if use_knowledge_base
            else "any references or factual materials you relied on."
        )
        if include_sources
        else ""
    )
    return base_prompt #+ sources_instruction
