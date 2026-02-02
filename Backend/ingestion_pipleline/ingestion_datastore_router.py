
from fastapi import APIRouter, HTTPException, Depends, Query
from pathlib import Path
from sqlmodel import Session, select
from models.FileRecord import FileRecord, DocumentRecord, ChunkRecord, Folder
from database import get_session
# from Services.chunking_service import chunk_documents, save_chunks_to_json, load_docs_from_json
# from ingestion_pipleline.VectorStores.vector_store_generator import create_vector_store
from models.datastore import DataStore
import os
import shutil
import time
import redis
import json
from typing import List
from config import CONFIG  # Load .env variables
from ingestion_pipleline.ingestion_models import DataStoreCreate, DataStoreResponse
from ingestion_pipleline.Config.Config import INGESTION_CONFIG

# Redis Setup
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

router = APIRouter()

@router.post("/createDatastore" , response_model=DataStore)
async def create_new_datastore(data: DataStoreCreate, session: Session = Depends(get_session)):
    print("Creating new datastore with name:", data.name)
    # 1️⃣ Check for duplicate name
    existing = session.exec(select(DataStore).where(DataStore.name == data.name)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Datastore already exists")

    print("No existing datastore found, proceeding to create.")

    try:
        # 2️⃣ Create datastore record
        new_store = DataStore(name=data.name, description=data.description)
        session.add(new_store)
        session.commit()
        session.refresh(new_store)

         # 2️⃣ Create virtual root folder in the DB
        root = Folder(
            name="root",
            parent_id=None,
            datastore_id=new_store.id
        )

        session.add(root)
        session.commit()
        session.refresh(root)

        # 3️⃣ OPTIONAL: set path if you're using path optimization
        root.path = f"/{root.id}/"
        session.add(root)
        session.commit()

        # 🔗 link root folder to datastore
        new_store.root_folder_id = root.id
        session.add(new_store)
        session.commit()


        print("Datastore record created in DB with ID:", new_store.id)
        # 3️⃣ Create physical datastore + chunks folders
        datastore_root = INGESTION_CONFIG["ingestion_root"] / INGESTION_CONFIG["ingestion_data_folder_name"]
        datastore_root.mkdir(exist_ok=True)
        ds_folder = datastore_root / str(new_store.name)
        ds_folder.mkdir(parents=True, exist_ok=True)

        return new_store
    except Exception as e:
        session.rollback()
        # Clean up any created directories if they were created before the error
        if 'ds_folder' in locals() and ds_folder.exists():
             shutil.rmtree(ds_folder, ignore_errors=True)
        print(f"Error creating datastore: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create datastore: {str(e)}")

@router.get("/getDatastores" , response_model=List[DataStoreResponse])
async def get_datastores(session: Session = Depends(get_session)):
    try:
        datastores = session.exec(select(DataStore)).all()
        return_datastores: List[DataStoreResponse] = []
        for datastore in datastores:
            docs = session.exec(select(DocumentRecord.id).where(DocumentRecord.datastore_id == datastore.id)).all()
            # datastore["documentCount"] = len(docs)
            return_datastores.append( DataStoreResponse(
                **datastore.model_dump(),
                document_count=len(docs)
            ))

        print(f"Found datastores.", return_datastores)
        return return_datastores
    except Exception as e:
        print(f"Error getting datastores: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch datastores: {str(e)}")

@router.post("/deleteDatastore/{datastore_id}" , response_model=DataStore)
async def delete_datastore(
    datastore_id: int, 
    session: Session = Depends(get_session)):
                
    try:            
        datastore = session.exec(select(DataStore).where(DataStore.id == datastore_id)).first()
        if not datastore:
             raise HTTPException(status_code=404, detail="Datastore not found")

        # chunk_ids = session.exec(select(ChunkRecord.id).where(ChunkRecord.datastore_id == datastore_id)).all()
        
        if (datastore.vector_store_provider):
            # Dispatch delete collection job
            job_payload = {
                "job_type": "delete_collection",
                "datastore_id": datastore_id,
                "vector_store_provider": datastore.vector_store_provider
            }
            r.rpush("ingestion:inbox", json.dumps(job_payload))
            print(f"[*] Queued collection deletion for datastore {datastore_id}")
        
        datastore_folder = INGESTION_CONFIG["ingestion_root"] / INGESTION_CONFIG["ingestion_data_folder_name"] / datastore.name
        if os.path.exists(datastore_folder):
            shutil.rmtree(datastore_folder, ignore_errors=True)

        session.delete(datastore)
        session.commit()
        return datastore
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        print(f"Error deleting datastore: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete datastore: {str(e)}")

