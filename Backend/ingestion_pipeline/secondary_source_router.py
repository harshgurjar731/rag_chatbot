from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from database import get_session
from models.datastore import DataStore, SecondarySource
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter()

class SecondarySourceRequest(BaseModel):
    intent: str
    description: str
    file_path: Optional[str] = None

class SecondarySourceResponse(SecondarySourceRequest):
    id: int
    datastore_id: int

@router.post("/datastore/{datastore_id}/secondary_sources", response_model=List[SecondarySourceResponse])
async def add_secondary_sources(
    datastore_id: int,
    sources: List[SecondarySourceRequest],
    session: Session = Depends(get_session)
):
    datastore = session.exec(select(DataStore).where(DataStore.id == datastore_id)).first()
    if not datastore:
        raise HTTPException(status_code=404, detail="Datastore not found")

    print(f"Adding {len(sources)} secondary sources to datastore {datastore_id}")
    
    new_records = []
    for source in sources:
        clean_intent = source.intent.strip() if source.intent else ""
        new_source = SecondarySource(
            datastore_id=datastore_id,
            intent=clean_intent,
            description=source.description,
            file_path=source.file_path
        )
        session.add(new_source)
        new_records.append(new_source)
    
    # Update datastore flag
    datastore.has_secondary_sources = True
    session.add(datastore)
    
    try:
        session.commit()
        for record in new_records:
            session.refresh(record)
            
        # Logging tables as requested
        print("\n--- Current DataStore Table ---")
        all_datastores = session.exec(select(DataStore)).all()
        for ds in all_datastores:
            print(f"ID: {ds.id}, Name: {ds.name}, HasSecondary: {ds.has_secondary_sources}")
            
        print("\n--- Current SecondarySource Table ---")
        all_sources = session.exec(select(SecondarySource)).all()
        for src in all_sources:
             print(f"ID: {src.id}, DS_ID: {src.datastore_id}, Intent: {src.intent}, File: {src.file_path}")
        print("--------------------------------\n")

        return new_records
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/datastore/{datastore_id}/secondary_sources", response_model=List[SecondarySourceResponse])
async def get_secondary_sources(
    datastore_id: int,
    session: Session = Depends(get_session)
):
    query = select(SecondarySource).where(SecondarySource.datastore_id == datastore_id)
    results = session.exec(query).all()
    return results

@router.delete("/secondary_sources/{source_id}")
async def delete_secondary_source(
    source_id: int,
    session: Session = Depends(get_session)
):
    source = session.exec(select(SecondarySource).where(SecondarySource.id == source_id)).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    datastore_id = source.datastore_id
    session.delete(source)
    
    # Check if there are any remaining sources
    remaining = session.exec(select(SecondarySource).where(SecondarySource.datastore_id == datastore_id)).all()
    if not remaining:
        datastore = session.exec(select(DataStore).where(DataStore.id == datastore_id)).first()
        if datastore:
            datastore.has_secondary_sources = False
            session.add(datastore)
            
    session.commit()
    return {"message": "Deleted successfully"}
