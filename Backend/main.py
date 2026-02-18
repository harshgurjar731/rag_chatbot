"""
Main entry point for the RAG Backend API.

This module initializes the FastAPI application, sets up OpenTelemetry tracing,
configures CORS middleware, and includes API routers for various services.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load env file to pick up OTEL configs locally (don't override Docker envs)
load_dotenv(override=False)

# Standard OpenTelemetry Imports
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from openinference.instrumentation.langchain import LangChainInstrumentor
from openinference.instrumentation.openai import OpenAIInstrumentor

# ================= PHOENIX SETUP =================
def configure_opentelemetry_for_phoenix():
    """
    Configures OpenTelemetry with a standard OTLP exporter pointing to Phoenix.

    This function sets up the tracer provider, OTLP exporter with project headers,
    and instruments LangChain and OpenAI libraries for tracing.
    """
    import os
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    project_name = os.getenv("OTEL_PROJECT_NAME", "RAGBOT")

    print(f"📡 Configuring Phoenix Tracing to: {endpoint} (Project: {project_name})")

    # 1. Define Resource
    resource = Resource(attributes={
        "service.name": "rag_backend",
        "project_name": project_name 
    })

    # 2. Setup Provider
    tracer_provider = TracerProvider(resource=resource)
    
    # 3. Setup OTLP Exporter with HEADERS
    otlp_exporter = OTLPSpanExporter(
        endpoint=endpoint,
        headers={"project_name": project_name} 
    )
    
    # 4. Use BatchSpanProcessor for production
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # 5. Set as Global Provider
    try:
        trace.set_tracer_provider(tracer_provider)
    except Exception as e:
        print(f"⚠️ Failed to set tracer provider: {e}")
    
    # 6. Instrument Libraries
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
# from routes import upload, preview, chunking, embedding, retriever, delete, url_scraper, translate, frontend_config
import requests
from fastapi.responses import Response


app = FastAPI(title="RAG Document Store")

# Add CORS middleware BEFORE anything else
# Important: middleware added last executes first (LIFO order)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# Global exception handler to ensure CORS headers are always present
# (FastAPI's CORSMiddleware doesn't add headers to unhandled 500 errors)
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "*",
        },
    )

# # Add explicit OPTIONS handler for root and all paths
# @app.options("/{full_path:path}")
# async def preflight_handler(full_path: str):
#     """Handle preflight requests for all routes"""
#     return Response(status_code=200)

from ingestion_pipleline.ingestion_datastore_router import router as ingestion_datastore_router
from ingestion_pipleline.ingestion_document_loader_router import router as ingestion_document_router
from ingestion_pipleline.ingestion_chunks_router import router as ingestion_chunking_router
from ingestion_pipeline.secondary_source_router import router as secondary_source_router # Added
from rag_pipeline.rag_router import router as rag_knowledge_asst_router
from authentication.authentication_router import router as authentication_router
from routes import translate, frontend_config, embedding
from routes.evaluation import router as evaluation_router
# # Include all the different API routers
# app.include_router(datastore.router, prefix="/datastore")
# app.include_router(upload.router)
# app.include_router(preview.router, prefix="/datastore")
# app.include_router(chunking.router, prefix="/datastore")
app.include_router(embedding.router, prefix="/datastore")
# app.include_router(retriever.router, prefix="/retriever")
# app.include_router(delete.router, prefix="/datastore")
# app.include_router(url_scraper.router, prefix="/urlscraper")
app.include_router(translate.router, prefix="/translate")
app.include_router(frontend_config.router, prefix="/frontend")
app.include_router(authentication_router, prefix="/auth")
app.include_router(evaluation_router, prefix="/evaluation", tags=["Evaluation"])




app.include_router(ingestion_datastore_router, prefix="/ingestion")
app.include_router(ingestion_document_router, prefix="/ingestion")
app.include_router(ingestion_chunking_router, prefix="/ingestion")
app.include_router(secondary_source_router, prefix="/ingestion", tags=["Secondary Sources"]) # Added

app.include_router(rag_knowledge_asst_router, prefix="/rag")

# app.include_router(image_reranking_router, prefix='/rag')


# Initialize database and list contents on startup
init_db()
list_tables()
list_tables_content()
list_file_content()

