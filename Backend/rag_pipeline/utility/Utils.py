
def get_final_prompt(prompt: str, use_knowledge_base: bool, include_sources: bool) -> str:
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
