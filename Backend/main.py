from fastapi import FastAPI
from database import init_db, list_tables, list_tables_content, list_file_content
from routes import datastore, upload, preview, chunking, embedding, retriever, delete, url_scraper, translate, frontend_config , feedback
from fastapi.middleware.cors import CORSMiddleware
import phoenix as px
import threading
from phoenix.otel import register
from openinference.instrumentation.langchain import LangChainInstrumentor

def run_phoenix():
    px.launch_app()

def initialize_phoenix():
    threading.Thread(target=run_phoenix, daemon=True).start()
    tracer_provider = register()
    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
    print("Phoenix instrumented and ready.")

initialize_phoenix()

app = FastAPI(title="RAG Document Store")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(feedback.router)

init_db()
list_tables()
list_tables_content()
list_file_content()