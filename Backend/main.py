from fastapi import FastAPI
from database import init_db, list_tables, list_tables_content,list_file_content
from routes import datastore, upload, preview, chunking,embedding, retriever,delete,url_scraper,translate,frontend_config,evaluation
from fastapi.middleware.cors import CORSMiddleware

# from Backend.db.database import init_db
# import os
# os.environ["OTEL_SDK_DISABLED"] = "true"   # disables OpenTelemetry
# os.environ["GUARDRAILS_DISABLE_TELEMETRY"] = "1"
# In your main application file (e.g., main.py or app.py)
import phoenix as px
import threading
from phoenix.otel import register
from openinference.instrumentation.langchain import LangChainInstrumentor


def run_phoenix():
    px.launch_app()


def initialize_phoenix():
    # Launch Phoenix in a separate thread
    threading.Thread(target=run_phoenix, daemon=True).start()


    # Register OpenTelemetry tracer with Phoenix
    tracer_provider = register()


    # Instrument LangChain with Phoenix
    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
    print("Phoenix instrumented and ready.")


# Call this function at the start of your application
initialize_phoenix()


app = FastAPI(title="RAG Document Store")






# Allow all origins (development only!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or specify: ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(datastore.router, prefix="/datastore")
app.include_router(upload.router)
# app.include_router(upload.router, prefix="/datastore")
app.include_router(preview.router, prefix="/datastore")
app.include_router(chunking.router, prefix="/datastore")
app.include_router(embedding.router, prefix="/datastore")
app.include_router(retriever.router, prefix="/retriever")
app.include_router(delete.router, prefix="/datastore")
app.include_router(url_scraper.router, prefix="/urlscraper")
app.include_router(translate.router, prefix="/translate")
app.include_router(frontend_config.router, prefix="/frontend")
app.include_router(evaluation.router, prefix="/evaluation")


init_db()  # 👈 add this right after app initialization
list_tables()  # 👈 this will print the tables in the database
list_tables_content()
list_file_content()  # 👈 this will print the content of the datastorefiles table





