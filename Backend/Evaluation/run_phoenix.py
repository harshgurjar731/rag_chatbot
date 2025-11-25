from phoenix.evals import llm_classify, HALLUCINATION_PROMPT_TEMPLATE, HALLUCINATION_PROMPT_RAILS_MAP, MistralAIModel
from Evaluation.phoenix import *
from typing import List, Dict
from sqlmodel import Session, select
from models.FileRecord import QuestionAnswer
from Services.retriever_service import retrieve_documents
from Evaluation.add_qna_into_db import insert_qna_for_datastore
import json
from pathlib import Path

# List of fallback LLMs
FALLBACK_LLMS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
    "deepseek-r1-distill-llama-70b",
    "openai/gpt-oss-120b"
]
# FALLBACK_LLMS = [
#    "gpt-4o-mini"
# ]



def generate_qna_with_retrieval(datastore_id: int, session: Session, output_file: str = None) -> list[dict]:
    """
    Retrieve documents and answers for new questions in the datastore and return
    structured QA pairs in JSON format.
    - Only calls retriever for new rows not already in the JSON file.
    - Appends new content to existing JSON file (if present).
    """
    insert_qna_for_datastore(session, datastore_id)

    print(f"[INFO] Fetching all QA pairs for datastore {datastore_id}")

    qas = session.exec(
        select(QuestionAnswer).where(QuestionAnswer.datastore_id == datastore_id)
    ).all()

    if not qas:
        return []

    json_output = []
    existing_data = []

    # --- Load existing JSON file if it exists ---
    if output_file:
        output_path = Path(output_file)
        if output_path.exists():
            with open(output_path, "r", encoding="utf-8") as f:
                try:
                    existing_data = json.load(f)
                except json.JSONDecodeError:
                    existing_data = []

    # Create a lookup set of existing queries to avoid duplicate retriever calls
    existing_queries = {item["query"] for item in existing_data}

    for row in qas:
        question = row.question

        # Skip if this question already exists in JSON file
        if question in existing_queries:
            continue

        file_id = [row.file_id] if row.file_id else [0]

        llm_used = None
        retriever_output = None

        # Try retriever with fallback models
        for llm_model in FALLBACK_LLMS:
            try:
                retriever_output = retrieve_documents(
                    query=question,
                    file_id=file_id,
                    llm_model_name=llm_model
                )
                llm_used = llm_model
                break
            except Exception as e:
                print(f"LLM '{llm_model}' failed: {str(e)}. Trying next model...")
                continue

        if retriever_output is None:
            reference_text = ""
            retrieved_answer = ""
        else:
            reference_text = retriever_output.get("chunks_used", "")
            retrieved_answer = retriever_output.get("answer", "")

        json_output.append({
            "reference": reference_text,
            "query": question,
            "response": retrieved_answer,
            "llm_used": llm_used
        })

    # --- Merge new and old results ---
    combined_data = existing_data + json_output

    # --- Save to JSON if file specified ---
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(combined_data, f, indent=4, ensure_ascii=False)
        print(f"[INFO] QA JSON updated at {output_file}")

    return combined_data
