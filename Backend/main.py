from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load env file to pick up OTEL configs locally
load_dotenv(override=True)

# Standard OpenTelemetry Imports
from openinference.instrumentation.langchain import LangChainInstrumentor
from openinference.instrumentation.openai import OpenAIInstrumentor
import phoenix.otel

# ================= PHOENIX SETUP =================
def configure_opentelemetry_for_phoenix():
    """
    Configures OpenTelemetry with a standard OTLP exporter pointing to Phoenix.
    """
    endpoint = "http://localhost:6006/v1/traces"
    project_name = "RAGBOT"

    print(f"📡 Configuring Phoenix Tracing to: {endpoint} (Project: {project_name})")

    # Use phoenix.otel.register to setup the provider with the correct project name
    tracer_provider = phoenix.otel.register(
        project_name=project_name,
        endpoint=endpoint
    )

    # Instrument Libraries
    try:
        LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
        OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)
        print("✅ Instrumentation Complete: LangChain & OpenAI")
    except Exception as e:
        print(f"⚠️ Instrumentation Error: {e}")

# Execute instrumentation BEFORE anything else
configure_opentelemetry_for_phoenix()
# =================================================

from database import init_db, list_tables, list_tables_content, list_file_content
from routes import translate, frontend_config, evaluation, feedback, chatbot_settings
import requests
from ingestion_pipleline.ingestion_datastore_router import router as ingestion_datastore_router
from ingestion_pipleline.ingestion_document_loader_router import router as ingestion_document_router, router_root as ingestion_document_root_router
from ingestion_pipleline.ingestion_chunks_router import router as ingestion_chunking_router
from rag_pipeline.rag_router import router as rag_knowledge_asst_router


app = FastAPI(title="RAG Document Store")


# Add CORS middleware to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include all the different API routers
app.include_router(translate.router, prefix="/translate")
app.include_router(frontend_config.router, prefix="/frontend")
app.include_router(evaluation.router, prefix="/evaluation")
app.include_router(feedback.router, prefix="")




app.include_router(ingestion_datastore_router, prefix="/ingestion")
app.include_router(ingestion_document_router, prefix="/ingestion")
app.include_router(ingestion_document_root_router, prefix="")
app.include_router(ingestion_chunking_router, prefix="/ingestion")

app.include_router(rag_knowledge_asst_router, prefix="/rag")
app.include_router(chatbot_settings.router, prefix="/rag", tags=["Settings"])

# app.include_router(image_reranking_router, prefix='/rag')


@app.get("/health")
def health_check():
    return {"status": "ok"}

# Initialize database and list contents on startup
init_db()
list_tables()
list_tables_content()
list_file_content()

