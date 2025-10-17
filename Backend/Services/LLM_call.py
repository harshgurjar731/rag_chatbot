from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
# from ragas.output_parsers import StrOutputParser
from langchain_core.output_parsers import StrOutputParser
# from config import CONFIG
from typing import List
import os
from phoenix.otel import register
from fastapi import Path
from opentelemetry import trace
from  fastapi import Query
# Placeholder for your validate_output function
def validate_output(answer: str, guardrail_level: str):
    # Dummy implementation; replace with your actual logic
    return {"answer": answer}

app = FastAPI(title="Embedded LLM API")


  

class LLMRequest(BaseModel):
    
    query: str
    llm_model_name: str
    temperature: float = 0.7
    token_size: Optional[int] = 256
    include_sources: Optional[bool] = False
    guardrail_level: Optional[str] = "none"

class LLMResponse(BaseModel):
    answer: str



def update_phoenix_project_name(chatbot_id: str):
    os.environ["PHOENIX_PROJECT_NAME"] = chatbot_id

    tracer_provider = register(project_name=chatbot_id,endpoint="http://localhost:6006/v1/traces",auto_instrument=True)
    return tracer_provider



@app.post("/ask/{chatbot_id}", response_model=LLMResponse)
def ask_llm(chatbot_id: str = Path(..., description="The ID of the chatbot being queried"),query: str="",
    query_optimizer: str = Query(
        "", description="Query optimizer to use"
    ),
    embedding_model_name: str = Query(
        "", description="Embedding model"
    ),
    llm_model_name: str = Query(
       "", description="LLM model name"
    ),
    vector_db: str = Query(["default_vector_db"], description="Vector DB name"),
    file_id: List[int] = Query(..., description="File IDs to search within"),
    temperature: float = Query(
        "", description="LLM temperature"
    ),
    guardrailOption: str = Query(
        "", description="Guardrail option"
    ),
    token_size: int = Query(
        "",
        ge=256,
        le=2048,
        description="Token size (between 256 and 2048)",
    ),
    sources: bool = Query(False, description="Include that context which was used  in the response"),
    rerankerOption: str = Query(
        "", description="Reranker option to use"
    ),):
    
    
    
    tracer_provider = update_phoenix_project_name(chatbot_id)
    try:
        # --- Embedded LLM function logic ---
        # query = request.query
        # llm_model_name = request.llm_model_name
        # temperature = request.temperature
        # token_size = request.token_size
        # include_sources = request.include_sources
        # guardrail_level = request.guardrail_level

        groq_api_key = "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"
        groq_api_base = "https://api.groq.com/openai/v1"

        if not groq_api_key:
            raise ValueError("Groq API key not set. Please update your .env file.")

        if not llm_model_name:
            raise ValueError("LLM model name must be provided")

        # Initialize LLM
        llm = ChatOpenAI(
            openai_api_base=groq_api_base,
            openai_api_key=groq_api_key,
            model=llm_model_name,
            temperature=temperature,
            max_tokens=token_size
        )

        # Prompt template
        chatbot_template = """
        You are a helpful and friendly AI assistant.
        Answer the following question clearly and concisely.
        """ + (
            """
            After the answer, provide a section called "Sources" listing any references,
            even if they are hypothetical or inferred.
            """ if include_sources else ""
        ) + "\n\nQuestion: {question}"

        prompt = ChatPromptTemplate.from_template(chatbot_template)

        # Chat chain
        chatbot_chain = (
            {"question": lambda x: x["question"]}
            | prompt
            | llm
            | StrOutputParser()
        )

        # Get answer
        final_answer = chatbot_chain.invoke({"question": query})

        # Apply guardrails
        validated = validate_output(final_answer, guardrail_level)
        if "⚠️ Response blocked" in validated["answer"]:
            return validated

        final_answer = validated["answer"]

        # Handle sources
        if include_sources and "Sources:" in final_answer:
            parts = final_answer.split("Sources:")
            answer_text = parts[0].strip()
            sources_text = parts[1].strip() if len(parts) > 1 else ""
            return {"answer": answer_text + "\n\nSources: " + str(sources_text.split("\n") if sources_text else [])}

        return {"answer": final_answer.strip()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Clean up tracer provider to avoid conflicts in future requests
        if tracer_provider:
            tracer_provider.shutdown()
            del tracer_provider