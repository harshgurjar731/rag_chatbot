from fastapi import FastAPI
from database import init_db, list_tables, list_tables_content, list_file_content
from routes import datastore, upload, preview, chunking, embedding, retriever, delete, url_scraper, translate, frontend_config,evaluation
from fastapi.middleware.cors import CORSMiddleware
# You no longer need to import threading here for phoenix
import phoenix as px
from phoenix.otel import register
import requests
# ================= PHOENIX SETUP START =================






def configure_opentelemetry_for_phoenix():
    """
    Configures the OpenTelemetry tracer to send data to a running
    Phoenix instance. It does NOT launch the Phoenix UI.
    """
    # Configure the OpenTelemetry tracer to send data to Phoenix
    # This assumes Phoenix is running on its default endpoint.
    tracer_provider = register(
        project_name="citation2",
        endpoint="http://localhost:6006/v1/traces",
        auto_instrument=True  # Automatically instruments supported libraries
    )
    print("✅ OpenTelemetry tracer configured to send data to Phoenix.")


# Call the setup function BEFORE creating the FastAPI app
# configure_opentelemetry_for_phoenix()


# ================= PHOENIX SETUP END =================




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
app.include_router(datastore.router, prefix="/datastore")
app.include_router(upload.router)
app.include_router(preview.router, prefix="/datastore")
app.include_router(chunking.router, prefix="/datastore")
app.include_router(embedding.router, prefix="/datastore")
app.include_router(retriever.router, prefix="/retriever")
app.include_router(delete.router, prefix="/datastore")
app.include_router(url_scraper.router, prefix="/urlscraper")
app.include_router(translate.router, prefix="/translate")
app.include_router(frontend_config.router, prefix="/frontend")
app.include_router(evaluation.router, prefix="/evaluation")


# Initialize database and list contents on startup
init_db()
list_tables()
list_tables_content()
list_file_content()

