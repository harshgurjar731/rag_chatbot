# from pathlib import Path
# import json
# from Services.VisRag.config import cfg, client
# from Services.VisRag.common_components import CLIPEmbedder, VisionRAGStore, encode_image_base64
# from models.FileRecord import FileRecord
# from models.datastore import DataStore
# from database import get_session
# from fastapi import HTTPException
# from sqlmodel import Session, select
# from typing import Tuple

# # -----------------------------
# # Helper: get datastore + filename
# # -----------------------------
# def get_datastore_and_filename_by_file_id(file_id: int) -> Tuple[str, str]:
#     session = next(get_session())
#     try:
#         statement = select(FileRecord).where(FileRecord.id == file_id)
#         file_record = session.exec(statement).first()
#         if not file_record:
#             raise HTTPException(status_code=404, detail="File record not found")
#         datastore = session.get(DataStore, file_record.datastore_id)
#         if not datastore:
#             raise HTTPException(status_code=404, detail="Datastore not found")
#         return file_record.filename
#     finally:
#         session.close()


# # -----------------------------------------------
# # Optimized Multi-file Vision Query Pipeline
# # -----------------------------------------------
# def query_pipeline(file_ids: list[str], query: str) -> dict:
#     """
#     Multi-file multimodal query pipeline optimized for Pixtral VLM.
#     Uses both retrieved text and image embeddings to generate the most context-aware answer.
#     """
#     print(f"\n🔍 Running multi-file query pipeline for {len(file_ids)} files...")
#     embedder = CLIPEmbedder()

#     # -----------------------------
#     # Load and merge FAISS stores
#     # -----------------------------
#     combined_store = VisionRAGStore(embedder)
#     for fid in file_ids:
#         try:
#             store = VisionRAGStore.load(embedder, fid)
#             vectors = store.index.reconstruct_n(0, store.index.ntotal)
#             combined_store.index.add(vectors)
#             combined_store.metadata.extend(store.metadata)
#             print(f"📂 Merged store: {fid} ({len(store.metadata)} embeddings)")
#         except Exception as e:
#             print(f"⚠️ Failed to load store for '{fid}': {e}")

#     total_embeds = len(combined_store.metadata)
#     print(f"✅ Total merged embeddings: {total_embeds}")

#     # -----------------------------
#     # Hybrid Retrieval (Text + Image)
#     # -----------------------------
#     query_vec = embedder.embed_text([query])
#     text_results = combined_store.search(query_vec, search_type="text")
#     image_results = combined_store.search(query_vec, search_type="image")

#     combined = text_results + image_results
#     combined.sort(key=lambda x: x[1], reverse=True)
#     print(f"🧠 Retrieved {len(text_results)} text results, {len(image_results)} image results")

#     # -----------------------------
#     # Build multimodal evidence set
#     # -----------------------------
#     image_msgs, text_context, citation_map = [], [], {}
#     sources, document_pages = set(), {}

#     for i, (meta, score) in enumerate(combined[:cfg.top_k], start=1):
#         cid = f"chunk_{i}"
#         citation_map[cid] = meta

#         # ✅ Image context
#         if meta["type"] == "image":
#             b64 = encode_image_base64(meta["page_path"])
#             if b64:
#                 image_msgs.append({
#                     "type": "image_url",
#                     "image_url": f"data:image/jpeg;base64,{b64}",
#                 })
#                 sources.add(Path(meta["page_path"]).name)
#                 for fid in file_ids:
#                     if fid in meta["page_path"]:
#                         document_pages.setdefault(get_datastore_and_filename_by_file_id(int(fid.split("_")[-1])), set()).add(meta["page_num"])
#                         break

#         # ✅ Text context
#         elif meta["type"] == "text":
#             snippet = meta["content"].strip()
#             if snippet:
#                 text_context.append(
#                     f"[FileChunk {i}] Page {meta['page_num']} → {snippet}"
#                 )
#                 src_fid = next((fid for fid in file_ids if fid in meta.get("content", "")), fid)
#                 src_fid=get_datastore_and_filename_by_file_id(int(src_fid.split("_")[-1]))
#                 document_pages.setdefault(src_fid, set()).add(meta["page_num"])

#     # -----------------------------
#     # 🧠 Structured Pixtral Input (Proper multimodal formatting)
#     # -----------------------------
#     context_text = "\n\n".join(text_context) if text_context else "No textual context available."

#     system_message = {
#         "role": "system",
#         "content": [
#             {
#                 "type": "text",
#                 "text": (
#                     "You are a professional multimodal reasoning assistant that interprets both text and images.\n"
#                     "Your task is to analyze the provided document content and answer the user's question as accurately as possible.\n"
#                     "Do **not** mention phrases like 'context', 'chunk', or 'provided text'."
#                     "If information is not found, say 'Information not found.'"
#                 )
#             }
#         ],
#     }

#     # 🧩 Combine all user content
#     user_content = [{"type": "text", "text": f"Question: {query}"}]

#     # Add text context as a single structured block
#     user_content.append({"type": "text", "text": f"Document text excerpts:\n{context_text}"})

#     # Append image contexts
#     user_content.extend(image_msgs)

#     # -----------------------------
#     # 🔥 Pixtral Inference
#     # -----------------------------
#     try:
#         response = client.chat.complete(
#             model=cfg.pixtral_model,
#             messages=[system_message, {"role": "user", "content": user_content}],
#             temperature=0.0,  # Low temp = high factual consistency
#         )
#         answer = response.choices[0].message.content.strip()
#     except Exception as e:
#         answer = f"❌ Error generating answer: {e}"

#     # -----------------------------
#     # Resolve file names (KEEP logic intact)
#     # -----------------------------
#     document_pages_list = []
#     for fid, pages in document_pages.items():
#         document_pages_list.append({
#             "source": fid,
#             "pages": sorted(list(pages)),
#         })

#     # -----------------------------
#     # Unified output
#     # -----------------------------
#     result = {
#         "answer": answer,
#         "sources": sorted(list(sources)),
#         "document_pages_dict": document_pages_list,
#         "citation_map": citation_map,
#         "chunks_used": [meta for meta, _ in combined],
#     }

#     print("\n" + "=" * 60)
#     print("💡 Unified Multi-File Output (optimized multimodal reasoning):")
#     print("=" * 60)
#     print(json.dumps(result, indent=2, default=str)[:1500])
#     print("=" * 60 + "\n")

#     return result


# from pathlib import Path
# import json
# from Services.VisRag.config import cfg, client
# from Services.VisRag.common_components import CLIPEmbedder, VisionRAGStore, encode_image_base64
# from models.FileRecord import FileRecord
# from models.datastore import DataStore
# from database import get_session
# from fastapi import HTTPException
# from sqlmodel import Session, select
# from typing import Tuple, Dict

# # -----------------------------
# # Helper: Batch resolve file IDs to filenames
# # -----------------------------
# def get_filenames_for_file_ids(file_ids: list[str]) -> Dict[str, str]:
#     """
#     Resolve all file IDs to filenames in a single DB query.
#     Returns: {file_id: filename}
#     """
#     session = next(get_session())
#     try:
#         # Extract numeric IDs
#         numeric_ids = []
#         for fid in file_ids:
#             try:
#                 # Handle both "file_123" and "123" formats
#                 numeric_id = int(fid.split("_")[-1]) if "_" in fid else int(fid)
#                 numeric_ids.append(numeric_id)
#             except ValueError:
#                 print(f"⚠️ Invalid file_id format: {fid}")
#                 continue
        
#         if not numeric_ids:
#             return {}
        
#         # Batch query
#         statement = select(FileRecord).where(FileRecord.id.in_(numeric_ids))
#         file_records = session.exec(statement).all()
        
#         # Build mapping
#         id_to_filename = {}
#         for record in file_records:
#             # Store with original format
#             for fid in file_ids:
#                 if str(record.id) in fid:
#                     id_to_filename[fid] = record.filename
#                     break
        
#         return id_to_filename
#     finally:
#         session.close()


# # -----------------------------
# # Helper: Extract file_id from metadata
# # -----------------------------
# def extract_file_id_from_metadata(meta: dict, file_ids: list[str]) -> str:
#     """
#     Determine which file this metadata chunk belongs to.
#     Priority: 
#     1. meta["file_id"] (if stored during indexing)
#     2. meta["page_path"] contains file_id
#     3. meta["source"] field
#     4. Fallback to first file_id
#     """
#     # Direct file_id in metadata (best case)
#     if "file_id" in meta:
#         return meta["file_id"]
    
#     # Check page_path for file_id pattern
#     if "page_path" in meta:
#         path_str = str(meta["page_path"])
#         for fid in file_ids:
#             if fid in path_str:
#                 return fid
    
#     # Check source field
#     if "source" in meta:
#         source_str = str(meta["source"])
#         for fid in file_ids:
#             if fid in source_str:
#                 return fid
    
#     # Fallback (shouldn't happen if metadata is proper)
#     print(f"⚠️ Could not determine file_id for metadata: {meta}")
#     return file_ids[0] if file_ids else "unknown"


# # -----------------------------------------------
# # Fixed Multi-file Vision Query Pipeline
# # -----------------------------------------------
# def query_pipeline(file_ids: list[str], query: str) -> dict:
#     """
#     Multi-file multimodal query pipeline with fixed file tracking and context optimization.
    
#     Key fixes:
#     1. Batch filename resolution (single DB query)
#     2. Proper file_id extraction from metadata
#     3. Context window management for Pixtral
#     4. Better source tracking
#     """
#     print(f"\n🔍 Running multi-file query pipeline for {len(file_ids)} files...")
#     print(f"📁 File IDs: {file_ids}")
    
#     # -----------------------------
#     # Batch resolve filenames upfront
#     # -----------------------------
#     file_id_to_filename = get_filenames_for_file_ids(file_ids)
#     print(f"📋 Resolved filenames: {file_id_to_filename}")
    
#     embedder = CLIPEmbedder()

#     # -----------------------------
#     # Load and merge FAISS stores
#     # -----------------------------
#     combined_store = VisionRAGStore(embedder)
#     for fid in file_ids:
#         try:
#             store = VisionRAGStore.load(embedder, fid)
#             vectors = store.index.reconstruct_n(0, store.index.ntotal)
#             combined_store.index.add(vectors)
#             combined_store.metadata.extend(store.metadata)
#             print(f"📂 Merged store: {fid} ({len(store.metadata)} embeddings)")
#         except Exception as e:
#             print(f"⚠️ Failed to load store for '{fid}': {e}")

#     total_embeds = len(combined_store.metadata)
#     print(f"✅ Total merged embeddings: {total_embeds}")

#     if total_embeds == 0:
#         return {
#             "answer": "❌ No embeddings found for the provided files.",
#             "sources": [],
#             "document_pages_dict": [],
#             "citation_map": {},
#             "chunks_used": [],
#         }

#     # -----------------------------
#     # Hybrid Retrieval (Text + Image)
#     # -----------------------------
#     query_vec = embedder.embed_text([query])
    
#     # Retrieve more initially, then filter
#     retrieval_k = min(cfg.top_k * 2, total_embeds)
#     text_results = combined_store.search(query_vec, top_k=retrieval_k, search_type="text")
#     image_results = combined_store.search(query_vec, top_k=retrieval_k, search_type="image")

#     # Merge and rerank
#     combined = text_results + image_results
#     combined.sort(key=lambda x: x[1], reverse=True)
    
#     # Take top-k from combined results
#     combined = combined[:cfg.top_k]
    
#     print(f"🧠 Retrieved {len(text_results)} text, {len(image_results)} image results")
#     print(f"📊 Using top {len(combined)} results after merging")

#     # -----------------------------
#     # Build multimodal evidence set
#     # -----------------------------
#     image_msgs = []
#     text_context = []
#     citation_map = {}
#     document_pages = {}  # {filename: set(page_nums)}
    
#     max_images = 10  # Pixtral limit
#     max_text_chars = 8000  # Context window management
#     current_text_length = 0
#     image_count = 0

#     for i, (meta, score) in enumerate(combined, start=1):
#         # Determine which file this chunk belongs to
#         source_file_id = extract_file_id_from_metadata(meta, file_ids)
#         source_filename = file_id_to_filename.get(source_file_id, "Unknown File")
#         page_num = meta.get("page_num", "N/A")
        
#         # Track in citation map
#         citation_key = f"chunk_{i}"
#         citation_map[citation_key] = {
#             **meta,
#             "file_id": source_file_id,
#             "filename": source_filename,
#             "score": score
#         }
        
#         # Initialize page tracking for this file
#         if source_filename not in document_pages:
#             document_pages[source_filename] = set()
        
#         # ✅ Image context
#         if meta["type"] == "image" and image_count < max_images:
#             page_path = meta.get("page_path")
#             if page_path and Path(page_path).exists():
#                 b64 = encode_image_base64(page_path)
#                 if b64:
#                     image_msgs.append({
#                         "type": "image_url",
#                         "image_url": f"data:image/jpeg;base64,{b64}",
#                     })
#                     image_count += 1
                    
#                     # Track page
#                     if page_num != "N/A":
#                         document_pages[source_filename].add(page_num)
                    
#                     print(f"🖼️ Added image from {source_filename}, page {page_num}")

#         # ✅ Text context
#         elif meta["type"] == "text":
#             snippet = meta.get("content", "").strip()
#             if snippet and current_text_length < max_text_chars:
#                 # Format with file and page info
#                 chunk_text = f"[File: {source_filename}, Page {page_num}]\n{snippet}"
#                 text_context.append(chunk_text)
#                 current_text_length += len(chunk_text)
                
#                 # Track page
#                 if page_num != "N/A":
#                     document_pages[source_filename].add(page_num)
                
#                 print(f"📄 Added text from {source_filename}, page {page_num}")

#     print(f"\n📊 Context stats:")
#     print(f"   - Images: {image_count}")
#     print(f"   - Text chunks: {len(text_context)}")
#     print(f"   - Text length: {current_text_length} chars")

#     # -----------------------------
#     # 🧠 Structured Pixtral Input
#     # -----------------------------
#     context_text = "\n\n".join(text_context) if text_context else "No textual context available."

#     system_message = {
#         "role": "system",
#         "content": [
#             {
#                 "type": "text",
#                 "text": (
#                     "You are a professional document analysis assistant that interprets both text and images.\n"
#                     "You have been provided with content from multiple documents.\n\n"
#                     "Instructions:\n"
#                     "1. Answer the question based on ALL provided evidence (text and images)\n"
#                     "2. When information comes from multiple files, synthesize them into a coherent answer\n"
#                     "3. If you reference specific information, mention which file it came from\n"
#                     "4. Be concise but comprehensive\n"
#                     "5. If information is insufficient, clearly state what's missing\n"
#                     "6. Do not mention 'context', 'chunks', or 'provided text' - answer naturally"
#                 )
#             }
#         ],
#     }

#     # Build user message
#     user_content = [
#         {"type": "text", "text": f"Question: {query}\n\n"},
#         {"type": "text", "text": f"Document excerpts:\n\n{context_text}"}
#     ]
    
#     # Add images
#     if image_msgs:
#         user_content.append({"type": "text", "text": "\n\nRelevant images from the documents:"})
#         user_content.extend(image_msgs)

#     # -----------------------------
#     # 🔥 Pixtral Inference
#     # -----------------------------
#     try:
#         response = client.chat.complete(
#             model=cfg.pixtral_model,
#             messages=[
#                 system_message,
#                 {"role": "user", "content": user_content}
#             ],
#             temperature=0.1,  # Slightly increased for better synthesis
#             max_tokens=2000,
#         )
#         answer = response.choices[0].message.content.strip()
#     except Exception as e:
#         print(f"❌ Pixtral error: {e}")
#         answer = f"❌ Error generating answer: {e}"

#     # -----------------------------
#     # Build document_pages_dict
#     # -----------------------------
#     document_pages_list = []
#     for filename, pages in document_pages.items():
#         if pages:  # Only include files with actual page references
#             document_pages_list.append({
#                 "source": filename,
#                 "pages": sorted(list(pages)),
#             })
    
#     # Sort by filename for consistency
#     document_pages_list.sort(key=lambda x: x["source"])

#     # -----------------------------
#     # Unified output
#     # -----------------------------
#     result = {
#         "answer": answer,
#         "sources": sorted(list(file_id_to_filename.values())),
#         "document_pages_dict": document_pages_list,
#         "citation_map": citation_map,
#         "chunks_used": [meta for meta, _ in combined],
#     }

#     print("\n" + "=" * 60)
#     print("💡 Multi-File Query Result:")
#     print("=" * 60)
#     print(f"Answer length: {len(answer)} chars")
#     print(f"Sources: {result['sources']}")
#     print(f"Pages referenced: {document_pages_list}")
#     print("=" * 60 + "\n")

#     return result

from pathlib import Path
import json
import re  # For citation parsing
from Services.VisRag.config import cfg, client
from Services.VisRag.common_components import CLIPEmbedder, VisionRAGStore, encode_image_base64
from models.FileRecord import FileRecord
from models.datastore import DataStore
from database import get_session
from fastapi import HTTPException
from sqlmodel import Session, select
from typing import Tuple, Dict

# -----------------------------
# Helper: Batch resolve file IDs to filenames
# -----------------------------
def get_filenames_for_file_ids(file_ids: list[str]) -> Dict[str, str]:
    """
    Resolve all file IDs to filenames in a single DB query.
    Returns: {file_id: filename}
    """
    session = next(get_session())
    try:
        # Extract numeric IDs
        numeric_ids = []
        for fid in file_ids:
            try:
                # Handle both "file_123" and "123" formats
                numeric_id = int(fid.split("_")[-1]) if "_" in fid else int(fid)
                numeric_ids.append(numeric_id)
            except ValueError:
                print(f"⚠️ Invalid file_id format: {fid}")
                continue
        
        if not numeric_ids:
            return {}
        
        # Batch query
        statement = select(FileRecord).where(FileRecord.id.in_(numeric_ids))
        file_records = session.exec(statement).all()
        
        # Build mapping
        id_to_filename = {}
        for record in file_records:
            # Store with original format
            for fid in file_ids:
                if str(record.id) in fid:
                    id_to_filename[fid] = record.filename
                    break
        
        return id_to_filename
    finally:
        session.close()


# -----------------------------
# Helper: Extract file_id from metadata
# -----------------------------
def extract_file_id_from_metadata(meta: dict, file_ids: list[str]) -> str:
    """
    Determine which file this metadata chunk belongs to.
    Priority: 
    1. meta["file_id"] (if stored during indexing)
    2. meta["page_path"] contains file_id
    3. meta["source"] field
    4. Fallback to first file_id
    """
    # Direct file_id in metadata (best case)
    if "file_id" in meta:
        return meta["file_id"]
    
    # Check page_path for file_id pattern
    if "page_path" in meta:
        path_str = str(meta["page_path"])
        for fid in file_ids:
            if fid in path_str:
                return fid
    
    # Check source field
    if "source" in meta:
        source_str = str(meta["source"])
        for fid in file_ids:
            if fid in source_str:
                return fid
    
    # Fallback (shouldn't happen if metadata is proper)
    print(f"⚠️ Could not determine file_id for metadata: {meta}")
    return file_ids[0] if file_ids else "unknown"


# -----------------------------
# Citation Parsing (from unified_rag_pipeline)
# -----------------------------
def parse_citations_from_answer(answer: str, citation_map: dict) -> dict:
    """
    Parses [Chunk ID] tags from the LLM's answer and creates a
    new, filtered citation_map containing only the cited sources.
    """
    # Find all unique chunk IDs cited in the answer
    chunk_ids_found = re.findall(r"\[Chunk (\d+)\]", answer)
    unique_chunk_ids = sorted(list(set(chunk_ids_found)))

    # Build the filtered map
    filtered_map = {}
    for chunk_id in unique_chunk_ids:
        chunk_key = str(chunk_id)
        if chunk_key in citation_map:
            filtered_map[chunk_key] = citation_map[chunk_key]
        else:
            # This case should rarely happen if the prompt is good
            print(f"⚠️ Warning: LLM cited chunk ID ({chunk_id}) not in citation_map.")

    # If no citations were found, return the full map as a fallback
    if not filtered_map:
        print("ℹ️ No citations found in answer, returning all chunks as fallback")
        return citation_map

    return filtered_map

import re

def remove_chunk_references(answer: str) -> str:
    """
    Removes any '[Chunk n]', '[chunk n]', '[CHUNK 1, Chunk 2]', etc. patterns from an answer string.
    Handles multiple chunks in a single bracket and cleans leftover spaces/punctuation.

    Examples:
    ---------
    Input:  "Revenue rose by 10% [Chunk 1, Chunk 4]. Costs declined [chunk 5]."
    Output: "Revenue rose by 10%. Costs declined."
    """
    # Regex matches:
    # - [Chunk 1]
    # - [chunk 1, Chunk 4]
    # - [CHUNK 2 , CHUNK 3 , Chunk 5]
    cleaned = re.sub(
        r"\[\s*(?:[Cc]hunk\s*\d+\s*(?:,\s*)?)+\]",
        "",
        answer
    )

    # Remove any double spaces or space before punctuation
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([.,;:])", r"\1", cleaned)
    cleaned = cleaned.strip()

    return cleaned

def extract_sources_and_pages_from_citations(citation_map: dict) -> tuple[list[dict], list[str]]:
    """
    Prepares document_pages_dict and source_links from citation map.
    Returns: (document_pages_list, source_links)
    """
    document_pages = {}
    
    for citation_metadata in citation_map.values():
        source = citation_metadata.get("filename") or citation_metadata.get("source")
        page_number = citation_metadata.get("page_num") or citation_metadata.get("page_number")

        if source and page_number is not None:
            if source not in document_pages:
                document_pages[source] = set()
            document_pages[source].add(page_number)

    # Build document_pages_list
    document_pages_list = []
    for source, pages in document_pages.items():
        document_pages_list.append({
            "source": source,
            "pages": sorted(list(pages))
        })
    
    # Sort by source name
    document_pages_list.sort(key=lambda x: x["source"])
    
    # Extract unique source links
    source_links = sorted(list({doc["source"] for doc in document_pages_list}))
    
    return document_pages_list, source_links


# -----------------------------------------------
# Fixed Multi-file Vision Query Pipeline with Citations
# -----------------------------------------------
# def query_pipeline(file_ids: list[str], query: str) -> dict:
#     """
#     Multi-file multimodal query pipeline with proper citation tracking.
    
#     Key features:
#     1. Batch filename resolution (single DB query)
#     2. Proper file_id extraction from metadata
#     3. Context window management for Pixtral
#     4. Citation parsing from LLM answer
#     5. Only returns sources actually cited in the answer
#     """
#     print(f"\n🔍 Running multi-file query pipeline for {len(file_ids)} files...")
#     print(f"📁 File IDs: {file_ids}")
    
#     # -----------------------------
#     # Batch resolve filenames upfront
#     # -----------------------------
#     file_id_to_filename = get_filenames_for_file_ids(file_ids)
#     print(f"📋 Resolved filenames: {file_id_to_filename}")
    
#     embedder = CLIPEmbedder()

#     # -----------------------------
#     # Load and merge FAISS stores
#     # -----------------------------
#     combined_store = VisionRAGStore(embedder)
#     for fid in file_ids:
#         try:
#             store = VisionRAGStore.load(embedder, fid)
#             vectors = store.index.reconstruct_n(0, store.index.ntotal)
#             combined_store.index.add(vectors)
#             combined_store.metadata.extend(store.metadata)
#             print(f"📂 Merged store: {fid} ({len(store.metadata)} embeddings)")
#         except Exception as e:
#             print(f"⚠️ Failed to load store for '{fid}': {e}")

#     total_embeds = len(combined_store.metadata)
#     print(f"✅ Total merged embeddings: {total_embeds}")

#     if total_embeds == 0:
#         return {
#             "answer": "❌ No embeddings found for the provided files.",
#             "sources": [],
#             "document_pages_dict": [],
#             "citation_map": {},
#             "chunks_used": [],
#         }

#     # -----------------------------
#     # Hybrid Retrieval (Text + Image)
#     # -----------------------------
#     query_vec = embedder.embed_text([query])
    
#     # Retrieve more initially, then filter
#     retrieval_k = min(cfg.top_k * 2, total_embeds)
#     text_results = combined_store.search(query_vec, top_k=retrieval_k, search_type="text")
#     image_results = combined_store.search(query_vec, top_k=retrieval_k, search_type="image")

#     # Merge and rerank
#     combined = text_results + image_results
#     combined.sort(key=lambda x: x[1], reverse=True)
    
#     # Take top-k from combined results
#     combined = combined[:cfg.top_k]
    
#     print(f"🧠 Retrieved {len(text_results)} text, {len(image_results)} image results")
#     print(f"📊 Using top {len(combined)} results after merging")

#     # -----------------------------
#     # Build multimodal evidence set WITH citation IDs
#     # -----------------------------
#     image_msgs = []
#     text_context = []
#     citation_map = {}  # {chunk_id: metadata}
    
#     max_images = 10  # Pixtral limit
#     max_text_chars = 8000  # Context window management
#     current_text_length = 0
#     image_count = 0

#     for i, (meta, score) in enumerate(combined, start=1):
#         # Determine which file this chunk belongs to
#         source_file_id = extract_file_id_from_metadata(meta, file_ids)
#         source_filename = file_id_to_filename.get(source_file_id, "Unknown File")
#         page_num = meta.get("page_num", "N/A")
        
#         # Create citation key
#         citation_id = str(i)
        
#         # Store in citation map with enhanced metadata
#         citation_map[citation_id] = {
#             **meta,
#             "file_id": source_file_id,
#             "filename": source_filename,
#             "page_num": page_num,
#             "score": score,
#             "citation_id": citation_id
#         }
        
#         # ✅ Image context
#         if meta["type"] == "image" and image_count < max_images:
#             page_path = meta.get("page_path")
#             if page_path and Path(page_path).exists():
#                 b64 = encode_image_base64(page_path)
#                 if b64:
#                     image_msgs.append({
#                         "type": "image_url",
#                         "image_url": f"data:image/jpeg;base64,{b64}",
#                     })
#                     image_count += 1
#                     print(f"🖼️ [Chunk {citation_id}] Image from {source_filename}, page {page_num}")

#         # ✅ Text context WITH chunk citation
#         elif meta["type"] == "text":
#             snippet = meta.get("content", "").strip()
#             if snippet and current_text_length < max_text_chars:
#                 # Format with citation ID, file, and page
#                 chunk_text = (
#                     f"[Chunk {citation_id}] "
#                     f"Source: {source_filename}, Page {page_num}\n"
#                     f"Content: {snippet}"
#                 )
#                 text_context.append(chunk_text)
#                 current_text_length += len(chunk_text)
#                 print(f"📄 [Chunk {citation_id}] Text from {source_filename}, page {page_num}")

#     print(f"\n📊 Context stats:")
#     print(f"   - Images: {image_count}")
#     print(f"   - Text chunks: {len(text_context)}")
#     print(f"   - Text length: {current_text_length} chars")
#     print(f"   - Total chunks indexed: {len(citation_map)}")

#     # -----------------------------
#     # 🧠 Structured Pixtral Input with Citation Instructions
#     # -----------------------------
#     context_text = "\n\n".join(text_context) if text_context else "No textual context available."

#     system_message = {
#         "role": "system",
#         "content": [
#             {
#                 "type": "text",
#                 "text": (
#                     "You are a professional document analysis assistant that interprets both text and images.\n"
#                     "You have been provided with content from multiple documents.\n\n"
#                     "CITATION RULES:\n"
#                     "1. Answer the question based on ALL provided evidence (text and images)\n"
#                     "2. After each factual statement, cite the specific [Chunk ID] you used\n"
#                     "3. Example: 'The revenue was $5M [Chunk 2]'\n"
#                     "4. If using multiple chunks, cite all: 'Revenue grew 10% [Chunk 2] while costs fell [Chunk 5]'\n"
#                     "5. When information comes from multiple files, synthesize them naturally\n"
#                     "6. If you cannot answer based on the context, say 'I cannot answer this based on the provided documents'\n"
#                     "7. Be concise but comprehensive\n"
#                     "8. Do NOT mention 'context', '[chunk n]', '[page]' or 'provided text' - answer naturally with citations"
#                 )
#             }
#         ],
#     }

#     # Build user message
#     user_content = [
#         {"type": "text", "text": f"Question: {query}\n\n"},
#         {"type": "text", "text": f"Document excerpts:\n\n{context_text}"}
#     ]
    
#     # Add images with instruction
#     if image_msgs:
#         user_content.append({
#             "type": "text", 
#             "text": "\n\nRelevant images from the documents (cite the Chunk ID when referencing visual information):"
#         })
#         user_content.extend(image_msgs)

#     # -----------------------------
#     # 🔥 Pixtral Inference
#     # -----------------------------
#     try:
#         response = client.chat.complete(
#             model=cfg.pixtral_model,
#             messages=[
#                 system_message,
#                 {"role": "user", "content": user_content}
#             ],
#             temperature=0.1,
#             max_tokens=2000,
#         )
#         answer = response.choices[0].message.content.strip()
#     except Exception as e:
#         print(f"❌ Pixtral error: {e}")
#         answer = f"❌ Error generating answer: {e}"

#     # -----------------------------
#     # Parse Citations from Answer
#     # -----------------------------
#     print("\n🔍 Parsing citations from answer...")
#     print(f"Raw answer length: {len(answer)} chars")
    
#     # Extract only the chunks that were actually cited
#     filtered_citation_map = parse_citations_from_answer(answer, citation_map)
    
#     print(f"📊 Citations found: {len(filtered_citation_map)} out of {len(citation_map)} chunks")
#     print(f"   Cited chunks: {list(filtered_citation_map.keys())}")

#     # -----------------------------
#     # Build document_pages_dict from CITED chunks only
#     # -----------------------------
#     document_pages_list, source_links = extract_sources_and_pages_from_citations(
#         filtered_citation_map
#     )

#     # -----------------------------
#     # Unified output
#     # -----------------------------
#     result = {
#         "answer": remove_chunk_references(answer),
#         "sources": source_links,  # Only cited sources
#         "document_pages_dict": document_pages_list,  # Only cited pages
#         "citation_map": filtered_citation_map,  # Only cited chunks
#         "chunks_used": [meta for meta, _ in combined],  # All retrieved chunks (for debugging)
#     }

#     print("\n" + "=" * 60)
#     print("💡 Multi-File Query Result with Citations:")
#     print("=" * 60)
#     print(f"Answer length: {len(answer)} chars")
#     print(f"Sources cited: {source_links}")
#     print(f"Pages referenced: {document_pages_list}")
#     print(f"Chunks cited: {len(filtered_citation_map)}/{len(citation_map)}")
#     print("=" * 60 + "\n")

#     return result
# def query_pipeline(file_ids: list[str], query: str) -> dict:
#     """
#     Replacement query_pipeline that retrieves per-file, then merges & re-ranks results.
#     More robust than trying to merge FAISS indices directly.
#     """
#     print(f"\n🔍 Running multi-file query pipeline for {len(file_ids)} files...")
#     print(f"📁 File IDs: {file_ids}")
    
#     # -----------------------------
#     # Batch resolve filenames upfront
#     # -----------------------------
#     file_id_to_filename = get_filenames_for_file_ids(file_ids)
#     print(f"📋 Resolved filenames: {file_id_to_filename}")
    
#     embedder = CLIPEmbedder()

#     # -----------------------------
#     # PER-FILE retrieval then global merge
#     # -----------------------------
#     all_results: list[tuple[dict, float]] = []  # list of (meta, score)
#     retrieval_k_per_file = max(cfg.top_k * 2, 10)  # retrieve more per-file to allow good global rerank

#     for fid in file_ids:
#         try:
#             store = VisionRAGStore.load(embedder, fid)
#         except Exception as e:
#             print(f"⚠️ Failed to load store for '{fid}': {e}")
#             continue

#         # ensure filename is available on metadata if possible
#         filename = file_id_to_filename.get(fid, "Unknown File")

#         # embed query once (embedder may be cheap, but do once globally ideally)
#         query_vec = embedder.embed_text([query])

#         # text search
#         try:
#             text_results = store.search(query_vec, top_k=retrieval_k_per_file, search_type="text")
#         except Exception as e:
#             print(f"⚠️ Text search failed for {fid}: {e}")
#             text_results = []

#         # image search
#         try:
#             image_results = store.search(query_vec, top_k=retrieval_k_per_file, search_type="image")
#         except Exception as e:
#             print(f"⚠️ Image search failed for {fid}: {e}")
#             image_results = []

#         # tag results with file id & enrich metadata where missing
#         for meta, score in (text_results + image_results):
#             # ensure file id exists on meta (store-level sources sometimes inconsistent)
#             meta = dict(meta)  # copy to avoid mutating original store objects in place
#             if "file_id" not in meta:
#                 meta["file_id"] = fid
#             # prefer explicit filename if store didn't include it
#             if "filename" not in meta and filename:
#                 meta["filename"] = filename
#             # normalize page_num keys
#             if "page_num" not in meta and "page_number" in meta:
#                 meta["page_num"] = meta["page_number"]
#             all_results.append((meta, float(score)))

#         print(f"📂 Retrieved {len(text_results)} text + {len(image_results)} image results from {fid}")

#     total_embeds = len(all_results)
#     print(f"✅ Total retrieved candidate embeddings across files: {total_embeds}")

#     if total_embeds == 0:
#         return {
#             "answer": "❌ No embeddings found for the provided files.",
#             "sources": [],
#             "document_pages_dict": [],
#             "citation_map": {},
#             "chunks_used": [],
#         }

#     # -----------------------------
#     # Global dedupe & rerank
#     # -----------------------------
#     # Optionally dedupe by (filename, page_num, type, content snippet) to avoid repeated chunks
#     seen_keys = set()
#     deduped_results = []
#     for meta, score in sorted(all_results, key=lambda x: x[1], reverse=True):
#         # create a stable key for dedupe
#         key = (
#             str(meta.get("filename") or meta.get("source") or meta.get("file_id")),
#             str(meta.get("page_num", meta.get("page_number", "N/A"))),
#             str(meta.get("type", "unknown")),
#             (meta.get("content") or "")[:200]  # first 200 chars of content as part of key
#         )
#         if key in seen_keys:
#             continue
#         seen_keys.add(key)
#         deduped_results.append((meta, score))

#     # final top-k selection
#     top_k = min(cfg.top_k, len(deduped_results))
#     combined = deduped_results[:top_k]
#     print(f"📊 Using top {len(combined)} deduped results after merging from all files")

#     # -----------------------------
#     # Build multimodal evidence set WITH citation IDs
#     # -----------------------------
#     image_msgs = []
#     text_context = []
#     citation_map = {}  # {chunk_id: metadata}
    
#     max_images = 10  # Pixtral limit
#     max_text_chars = 8000  # Context window management
#     current_text_length = 0
#     image_count = 0

#     for i, (meta, score) in enumerate(combined, start=1):
#         # Ensure meta has file id and filename
#         source_file_id = str(meta.get("file_id", file_ids[0] if file_ids else "unknown"))
#         source_filename = str(meta.get("filename") or meta.get("source") or file_id_to_filename.get(source_file_id, "Unknown File"))
#         page_num = meta.get("page_num", meta.get("page_number", "N/A"))
        
#         # Create citation key
#         citation_id = str(i)
        
#         # Store in citation map with enhanced metadata
#         citation_map[citation_id] = {
#             **meta,
#             "file_id": source_file_id,
#             "filename": source_filename,
#             "page_num": page_num,
#             "score": score,
#             "citation_id": citation_id
#         }
        
#         # Image context
#         if meta.get("type") == "image" and image_count < max_images:
#             page_path = meta.get("page_path")
#             try:
#                 if page_path and Path(page_path).exists():
#                     b64 = encode_image_base64(page_path)
#                     if b64:
#                         image_msgs.append({
#                             "type": "image_url",
#                             "image_url": f"data:image/jpeg;base64,{b64}",
#                             "citation_id": citation_id
#                         })
#                         image_count += 1
#                         print(f"🖼️ [Chunk {citation_id}] Image from {source_filename}, page {page_num}")
#             except Exception as e:
#                 print(f"⚠️ Could not add image for chunk {citation_id}: {e}")

#         # Text context WITH chunk citation
#         elif meta.get("type") == "text":
#             snippet = (meta.get("content") or meta.get("text") or "").strip()
#             if snippet and current_text_length < max_text_chars:
#                 # Format with citation ID, file, and page
#                 chunk_text = (
#                     f"[Chunk {citation_id}] "
#                     f"Source: {source_filename}, Page {page_num}\n"
#                     f"Content: {snippet}"
#                 )
#                 text_context.append(chunk_text)
#                 current_text_length += len(chunk_text)
#                 print(f"📄 [Chunk {citation_id}] Text from {source_filename}, page {page_num}")

#     print(f"\n📊 Context stats:")
#     print(f"   - Images: {image_count}")
#     print(f"   - Text chunks: {len(text_context)}")
#     print(f"   - Text length: {current_text_length} chars")
#     print(f"   - Total chunks indexed in citation_map: {len(citation_map)}")

#     # -----------------------------
#     # Structured Pixtral Input with Citation Instructions
#     # -----------------------------
#     context_text = "\n\n".join(text_context) if text_context else "No textual context available."

#     system_message = {
#         "role": "system",
#         "content": [
#             {
#                 "type": "text",
#                 "text": (
#                     "You are a professional document analysis assistant that interprets both text and images.\n"
#                     "You have been provided with content from multiple documents.\n\n"
#                     "CITATION RULES:\n"
#                     "1. Answer the question based on ALL provided evidence (text and images)\n"
#                     "2. After each factual statement, cite the specific [Chunk ID] you used\n"
#                     "3. Example: 'The revenue was $5M [Chunk 2]'\n"
#                     "4. If using multiple chunks, cite all: 'Revenue grew 10% [Chunk 2] while costs fell [Chunk 5]'\n"
#                     "5. When information comes from multiple files, synthesize them naturally\n"
#                     "6. If you cannot answer based on the context, say 'I cannot answer this based on the provided documents'\n"
#                     "7. Be concise but comprehensive\n"
#                     "8. Do NOT mention 'context', '[chunk n]', '[page]' or 'provided text' - answer naturally with citations"
#                 )
#             }
#         ],
#     }

#     # Build user message
#     user_content = [
#         {"type": "text", "text": f"Question: {query}\n\n"},
#         {"type": "text", "text": f"Document excerpts:\n\n{context_text}"}
#     ]
    
#     # Add images with instruction
#     if image_msgs:
#         user_content.append({
#             "type": "text", 
#             "text": "\n\nRelevant images from the documents (cite the Chunk ID when referencing visual information):"
#         })
#         # add only image messages (pixtral expects images separated)
#         user_content.extend(image_msgs)

#     # -----------------------------
#     # Pixtral Inference
#     # -----------------------------
#     try:
#         response = client.chat.complete(
#             model=cfg.pixtral_model,
#             messages=[
#                 system_message,
#                 {"role": "user", "content": user_content}
#             ],
#             temperature=0.1,
#             max_tokens=2000,
#         )
#         answer = response.choices[0].message.content.strip()
#     except Exception as e:
#         print(f"❌ Pixtral error: {e}")
#         answer = f"❌ Error generating answer: {e}"

#     # -----------------------------
#     # Parse Citations from Answer
#     # -----------------------------
#     print("\n🔍 Parsing citations from answer...")
#     print(f"Raw answer length: {len(answer)} chars")
    
#     # Extract only the chunks that were actually cited
#     filtered_citation_map = parse_citations_from_answer(answer, citation_map)
    
#     print(f"📊 Citations found: {len(filtered_citation_map)} out of {len(citation_map)} chunks")
#     print(f"   Cited chunks: {list(filtered_citation_map.keys())}")

#     # -----------------------------
#     # Build document_pages_dict from CITED chunks only
#     # -----------------------------
#     document_pages_list, source_links = extract_sources_and_pages_from_citations(
#         filtered_citation_map
#     )

#     # -----------------------------
#     # Unified output
#     # -----------------------------
#     # chunks_used: return the actual chunk metadata used (from the selected combined set) for debugging
#     chunks_used = [citation_map[cid] for cid in citation_map.keys()]

#     result = {
#         "answer": remove_chunk_references(answer),
#         "sources": source_links,  # Only cited sources
#         "document_pages_dict": document_pages_list,  # Only cited pages
#         "citation_map": filtered_citation_map,  # Only cited chunks
#         "chunks_used": chunks_used,  # All chunks that were in the selected combined set (for debugging)
#     }

#     print("\n" + "=" * 60)
#     print("💡 Multi-File Query Result with Citations:")
#     print("=" * 60)
#     print(f"Answer length: {len(answer)} chars")
#     print(f"Sources cited: {source_links}")
#     print(f"Pages referenced: {document_pages_list}")
#     print(f"Chunks cited: {len(filtered_citation_map)}/{len(citation_map)}")
#     print("=" * 60 + "\n")

#     return result

def query_pipeline(file_ids: list[str], query: str) -> dict:
    """
    Enhanced multi-file query pipeline.
    Improvements:
      - Unified query embedding (only once)
      - Weighted reranking across files
      - Document-aware chunk balancing
      - Better context trimming (relevance + diversity)
      - Stronger citation alignment
    """
    print(f"\n🔍 Running enhanced multi-file query pipeline for {len(file_ids)} files...")
    file_id_to_filename = get_filenames_for_file_ids(file_ids)
    embedder = CLIPEmbedder()
    query_vec = embedder.embed_text([query])

    # Parameters
    retrieval_k_per_file = max(cfg.top_k * 3, 15)
    max_text_chars = 8000
    max_images = 10
    min_doc_diversity = 2  # ensure chunks from at least 2 docs when possible

    all_results = []
    # =========================================================
    # Step 1: Per-file retrieval (both text + image)
    # =========================================================
    for fid in file_ids:
        try:
            store = VisionRAGStore.load(embedder, fid)
        except Exception as e:
            print(f"⚠️ Skipping {fid}: {e}")
            continue

        filename = file_id_to_filename.get(fid, "Unknown File")

        results = []
        for search_type in ("text", "image"):
            try:
                res = store.search(query_vec, top_k=retrieval_k_per_file, search_type=search_type)
                results.extend(res)
            except Exception as e:
                print(f"⚠️ {search_type.capitalize()} search failed for {fid}: {e}")

        for meta, score in results:
            meta = dict(meta)
            meta.setdefault("file_id", fid)
            meta.setdefault("filename", filename)
            meta.setdefault("page_num", meta.get("page_number", "N/A"))
            meta.setdefault("type", meta.get("type", "text"))
            all_results.append((meta, float(score)))

        print(f"📂 Retrieved {len(results)} candidates from {filename}")

    if not all_results:
        return {
            "answer": "❌ No embeddings found for the provided files.",
            "sources": [],
            "document_pages_dict": [],
            "citation_map": {},
            "chunks_used": [],
        }

    # =========================================================
    # Step 2: Normalize & rerank globally by weighted score
    # =========================================================
    # Score normalization per document to avoid single-file dominance
    from collections import defaultdict
    doc_scores = defaultdict(list)
    for meta, s in all_results:
        doc_scores[meta["file_id"]].append(s)
    doc_means = {fid: (sum(v) / len(v)) for fid, v in doc_scores.items()}

    reranked = []
    for meta, s in all_results:
        doc_mean = doc_means.get(meta["file_id"], 1)
        norm_score = s / (doc_mean + 1e-6)
        reranked.append((meta, norm_score))

    reranked = sorted(reranked, key=lambda x: x[1], reverse=True)

    # Deduplicate similar chunks
    seen_keys, deduped = set(), []
    for meta, s in reranked:
        key = (
            meta["filename"],
            meta["page_num"],
            meta["type"],
            (meta.get("content") or meta.get("text") or "")[:200],
        )
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append((meta, s))

    # =========================================================
    # Step 3: Ensure balanced sampling across documents
    # =========================================================
    by_doc = defaultdict(list)
    for meta, s in deduped:
        by_doc[meta["file_id"]].append((meta, s))

    combined = []
    while len(combined) < cfg.top_k and any(by_doc.values()):
        for fid in list(by_doc.keys()):
            if by_doc[fid]:
                combined.append(by_doc[fid].pop(0))
            if len(combined) >= cfg.top_k:
                break

    print(f"📊 Selected top {len(combined)} chunks across {len(file_ids)} files")

    # =========================================================
    # Step 4: Build multimodal evidence & citation mapping
    # =========================================================
    image_msgs, text_context, citation_map = [], [], {}
    current_len, image_count = 0, 0

    for i, (meta, score) in enumerate(combined, 1):
        citation_id = str(i)
        citation_map[citation_id] = {
            **meta,
            "score": score,
            "citation_id": citation_id,
        }

        if meta["type"] == "image" and image_count < max_images:
            page_path = meta.get("page_path")
            if page_path and Path(page_path).exists():
                try:
                    b64 = encode_image_base64(page_path)
                    image_msgs.append({
                        "type": "image_url",
                        "image_url": f"data:image/jpeg;base64,{b64}",
                        "citation_id": citation_id,
                    })
                    image_count += 1
                except Exception as e:
                    print(f"⚠️ Could not add image for chunk {citation_id}: {e}")

        elif meta["type"] == "text":
            snippet = (meta.get("content") or meta.get("text") or "").strip()
            if snippet and current_len < max_text_chars:
                chunk_text = (
                    f"[Chunk {citation_id}] "
                    f"Source: {meta['filename']}, Page {meta['page_num']}\n"
                    f"Content: {snippet}"
                )
                text_context.append(chunk_text)
                current_len += len(chunk_text)

    # =========================================================
    # Step 5: Build structured LLM prompt
    # =========================================================
    context_text = "\n\n".join(text_context)
    system_message = {
        "role": "system",
        "content": [{
            "type": "text",
            "text": (
    "You are a professional multi-document analysis assistant.\n"
    "Your goal is to generate an accurate, concise answer using evidence from multiple documents and images.\n\n"
    "INSTRUCTIONS:\n"
    "1. Read all the provided [Chunk N] excerpts carefully.\n"
    "2. Use the information from any relevant chunks to form your answer.\n"
    "3. Write your final answer naturally — do NOT include [Chunk IDs] or citations inside the answer text.\n"
    "4. After completing the answer, create a separate 'Citations' section listing every [Chunk ID] that contributed factual information.\n"
    "   - Include **every** chunk that influenced your answer.\n"
    "   - Ensure at least one chunk from each document used is cited.\n"
    "   - List them as: 'Citations: [Chunk 1], [Chunk 2], [Chunk 5], [Chunk 8]', etc.\n"
    "5. If multiple chunks or documents contribute, include them all in the Citations section.\n"
    "6. If the provided context does not contain enough information to answer, respond exactly with:\n"
    "   'I cannot answer this based on the provided documents.'\n\n"
    "Be factual, concise, and ensure full citation coverage for all used evidence."
)

        }]
    }

    user_content = [
        {"type": "text", "text": f"Question: {query}\n\n"},
        {"type": "text", "text": f"Document excerpts:\n\n{context_text}"}
    ]
    if image_msgs:
        user_content.append({
            "type": "text",
            "text": "\nRelevant images (refer by [Chunk ID]):"
        })
        user_content.extend(image_msgs)

    # =========================================================
    # Step 6: Pixtral Inference
    # =========================================================
    try:
        response = client.chat.complete(
            model=cfg.pixtral_model,
            messages=[system_message, {"role": "user", "content": user_content}],
            temperature=0.1,
            max_tokens=2000,
        )
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Pixtral error: {e}")
        answer = f"❌ Error generating answer: {e}"

    # =========================================================
    # Step 7: Parse citations and finalize result
    # =========================================================
    filtered_citation_map = parse_citations_from_answer(answer, citation_map)
    document_pages_list, source_links = extract_sources_and_pages_from_citations(filtered_citation_map)

    result = {
        "answer": remove_chunk_references(answer),
        "sources": source_links,
        "document_pages_dict": document_pages_list,
        "citation_map": filtered_citation_map,
        "chunks_used": list(citation_map.values()),
    }

    print(f"✅ Multi-document synthesis complete. Used {len(filtered_citation_map)} chunks.")
    return result
    
