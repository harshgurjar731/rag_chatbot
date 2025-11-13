"""
optimized_visrag_pipeline.py

Enhanced VisRAG pipeline combining Code 1 structure with Code 2 improvements:
- LLM-based image filtering (Pixtral)
- Semantic text chunking (LangChain)
- Dual-stage retrieval (text + image embeddings)
- Type-aware FAISS indexing
- Pixtral VLM for answer generation

Optimized for VS Code with proper path management and error handling.
"""

import os
import io
import sys
import json
import base64
import pickle
from pathlib import Path
from typing import List, Dict, Tuple, Any
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageStat
# import pymupdf  # PyMuPDF
import pymupdf
import faiss
from tqdm import tqdm

# Transformers / models
import torch
from transformers import CLIPProcessor, CLIPModel

# Mistral API
from mistralai import Mistral

# LangChain for semantic chunking
from langchain.text_splitter import RecursiveCharacterTextSplitter
# from .config import CONFIG

# Optional OCR
try:
    import pytesseract
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

# -----------------------
# Config
# -----------------------
@dataclass
class Config:
    # Paths (VS Code compatible)
    page_images_dir: str = "./page_images"
    extracted_images_dir: str = "./extracted_images"
    faiss_index_path: str = "./faiss_index.faiss"
    metadata_path: str = "./faiss_metadata.pkl"
    
    # Model configuration
    clip_model_name: str = "openai/clip-vit-large-patch14"
    pixtral_model: str = "pixtral-12b-2409"
    
    # Processing parameters
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    page_dpi: int = 150
    top_k: int = 5
    
    # Image filtering
    min_image_width: int = 50
    min_image_height: int = 50
    brightness_threshold: float = 10.0
    
    # Text chunking
    chunk_size: int = 800
    chunk_overlap: int = 150
    
    # API Keys (load from environment)
    # mistral_api_key: str = CONFIG["mistral_api_key_visrag"]
    mistral_api_key: str = "ZpuwhInKUMLpkFTtA9zKmu7n0vxhLFRJ"

cfg = Config()

# Create necessary directories
for directory in [cfg.page_images_dir, cfg.extracted_images_dir]:
    Path(directory).mkdir(parents=True, exist_ok=True)

# Initialize Mistral client
if not cfg.mistral_api_key:
    print("⚠️ WARNING: MISTRAL_API_KEY not found in environment variables!")
    print("Set it with: export MISTRAL_API_KEY='your_key_here'")
    client = None
else:
    client = Mistral(api_key=cfg.mistral_api_key)

# -----------------------
# Image Relevance Filtering
# -----------------------
def is_black_image(image_bytes: bytes, threshold: float = cfg.brightness_threshold) -> bool:
    """
    Check if image is mostly black/blank using brightness threshold.
    Returns True if brightness < threshold (likely irrelevant).
    """
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("L")
        stat = ImageStat.Stat(image)
        brightness = stat.mean[0]  # 0=black, 255=white
        return brightness < threshold
    except Exception:
        return True  # Treat corrupted images as black

def is_image_relevant(image_bytes: bytes, page_text: str, query: str = None) -> bool:
    """
    Use Pixtral VLM to determine image relevance based on context.
    Falls back to brightness check if API unavailable.
    """
    if client is None:
        # Fallback: only filter obviously black images
        return not is_black_image(image_bytes)
    
    try:
        # Skip black/blank images
        if is_black_image(image_bytes):
            return False
        
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        
        # Build prompt
        prompt_text = (
            f"Determine if this image is relevant to the document context.\n\n"
            f"Text context: {page_text[:1000]}\n\n"
        )
        if query:
            prompt_text += f"User query: {query}\n\n"
        prompt_text += "Respond only with 'relevant' or 'not relevant'."
        
        content = [
            {"type": "text", "text": prompt_text},
            {"type": "image_url", "image_url": f"data:image/jpeg;base64,{b64_image}"}
        ]
        
        response = client.chat.complete(
            model=cfg.pixtral_model,
            messages=[{"role": "user", "content": content}],
            temperature=0.0
        )
        
        answer = response.choices[0].message.content.strip().lower()
        return "relevant" in answer and "not" not in answer
        
    except Exception as e:
        print(f"⚠️ Relevance check failed: {e}")
        return not is_black_image(image_bytes)

# -----------------------
# PDF Extraction with Filtering
# -----------------------
def extract_text_and_images_from_pdf(
    pdf_path: str,
    output_dir: str = None,
    prefix: str = "page",
    query: str = None
) -> List[Dict]:
    """
    Extract text and relevant images from PDF with LLM-based filtering.
    
    Returns:
        List[Dict]: Each element contains:
            {
                "page_num": int,
                "text": str,
                "images": List[str]  # paths to extracted images
            }
    """
    if output_dir is None:
        output_dir = cfg.extracted_images_dir
    
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    pages_data = []
    
    stats = {
        "total_pages": total_pages,
        "embedded_count": 0,
        "block_count": 0,
        "skipped_small": 0,
        "filtered_non_relevant": 0
    }
    
    print(f"📘 Processing '{pdf_path}' — {total_pages} pages")
    
    for page_num in tqdm(range(total_pages), desc="Extracting pages"):
        page = doc[page_num]
        text = page.get_text("text")
        page_images = []
        
        # Extract embedded images
        for img_idx, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                width = base_image.get("width", 0)
                height = base_image.get("height", 0)
                ext = base_image.get("ext", "png")
                
                # Size filter
                if width < cfg.min_image_width or height < cfg.min_image_height:
                    stats["skipped_small"] += 1
                    continue
                
                # Relevance filter
                if not is_image_relevant(image_bytes, text, query):
                    stats["filtered_non_relevant"] += 1
                    continue
                
                # Save image
                filename = f"{prefix}_p{page_num+1:04d}_embed{img_idx}.{ext}"
                output_file = out_path / filename
                with open(output_file, "wb") as f:
                    f.write(image_bytes)
                
                page_images.append(str(output_file.resolve()))
                stats["embedded_count"] += 1
                
            except Exception as e:
                print(f"⚠️ Error extracting embedded image (page {page_num+1}): {e}")
        
        # Extract image blocks (rendered regions)
        text_dict = page.get_text("dict")
        blocks = text_dict.get("blocks", [])
        image_blocks = [b for b in blocks if b.get("type") == 1]
        
        if image_blocks:
            mat = pymupdf.Matrix(2.0, 2.0)  # High-res rendering
            for block_idx, block in enumerate(image_blocks):
                try:
                    bbox = pymupdf.Rect(block.get("bbox"))
                    if bbox.width < cfg.min_image_width or bbox.height < cfg.min_image_height:
                        stats["skipped_small"] += 1
                        continue
                    
                    pix = page.get_pixmap(matrix=mat, clip=bbox, alpha=False)
                    image_bytes = pix.tobytes("png")
                    
                    # Relevance filter
                    if not is_image_relevant(image_bytes, text, query):
                        stats["filtered_non_relevant"] += 1
                        continue
                    
                    filename = f"{prefix}_p{page_num+1:04d}_block{block_idx}.png"
                    output_file = out_path / filename
                    pix.save(str(output_file))
                    
                    page_images.append(str(output_file.resolve()))
                    stats["block_count"] += 1
                    
                except Exception as e:
                    print(f"⚠️ Error extracting block image (page {page_num+1}): {e}")
        
        pages_data.append({
            "page_num": page_num + 1,
            "text": text,
            "images": page_images
        })
    
    doc.close()
    
    # Print summary
    print("\n" + "="*60)
    print("✅ Extraction Complete!")
    print("="*60)
    print(f"📄 Pages processed: {stats['total_pages']}")
    print(f"📦 Embedded images: {stats['embedded_count']}")
    print(f"🧩 Block images: {stats['block_count']}")
    print(f"🚫 Filtered (non-relevant): {stats['filtered_non_relevant']}")
    print(f"⚠️ Skipped (too small): {stats['skipped_small']}")
    print(f"📂 Output: {out_path.resolve()}")
    print("="*60 + "\n")
    
    return pages_data

# -----------------------
# Semantic Text Chunking
# -----------------------
def semantic_chunk_text(text: str) -> List[str]:
    """
    Break text into semantically coherent chunks using RecursiveCharacterTextSplitter.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
        separators=["\n\n", "\n", ".", "!", "?", " "]
    )
    chunks = splitter.split_text(text)
    return [chunk.strip() for chunk in chunks if chunk.strip()]

# -----------------------
# CLIP Embedder
# -----------------------
class CLIPEmbedder:
    """Enhanced CLIP embedder with proper dimension management."""
    
    def __init__(self, model_name: str = None):
        if model_name is None:
            model_name = cfg.clip_model_name
        
        self.device = cfg.device
        self.model_name = model_name
        self.model = CLIPModel.from_pretrained(model_name).to(self.device)
        self.processor = CLIPProcessor.from_pretrained(model_name)
        
        # Get actual embedding dimension
        dummy_text = ["test"]
        with torch.no_grad():
            inputs = self.processor(text=dummy_text, return_tensors="pt", padding=True).to(self.device)
            test_emb = self.model.get_text_features(**inputs)
        self.dim = test_emb.shape[1]
        
        print(f"[INIT] CLIP model: {model_name}")
        print(f"[INIT] Embedding dimension: {self.dim}")
        print(f"[INIT] Device: {self.device}")
    
    def embed_text(self, texts: List[str]) -> np.ndarray:
        """Compute normalized CLIP text embeddings."""
        inputs = self.processor(
            text=texts,
            return_tensors="pt",
            padding=True,
            truncation=True
        ).to(self.device)
        
        with torch.no_grad():
            embeddings = self.model.get_text_features(**inputs)
        
        embeddings = embeddings.cpu().numpy().astype("float32")
        faiss.normalize_L2(embeddings)
        return embeddings
    
    def embed_images(self, image_paths: List[str]) -> np.ndarray:
        """Compute normalized CLIP image embeddings."""
        images = [Image.open(p).convert("RGB") for p in image_paths]
        inputs = self.processor(
            images=images,
            return_tensors="pt",
            padding=True
        ).to(self.device)
        
        with torch.no_grad():
            embeddings = self.model.get_image_features(**inputs)
        
        embeddings = embeddings.cpu().numpy().astype("float32")
        faiss.normalize_L2(embeddings)
        return embeddings

# -----------------------
# Enhanced FAISS Store with Type-Aware Retrieval
# -----------------------
class VisionRAGStore:
    """
    FAISS-backed vector store with type-aware indexing (text vs image embeddings).
    Uses cosine similarity (IndexFlatIP with normalized vectors).
    """
    
    def __init__(self, embedder: CLIPEmbedder):
        self.dim = embedder.dim
        self.index = faiss.IndexFlatIP(self.dim)  # Cosine similarity
        self.metadata: List[Dict[str, Any]] = []
        print(f"✅ FAISS index initialized (dim={self.dim}, metric=cosine)")
    
    def add_embeddings(self, embeddings: np.ndarray, meta: List[Dict[str, Any]]):
        """Add embeddings with metadata to the index."""
        embeddings = embeddings.astype("float32")
        
        if embeddings.shape[1] != self.dim:
            raise ValueError(
                f"Embedding dimension mismatch: got {embeddings.shape[1]}, expected {self.dim}"
            )
        
        self.index.add(embeddings)
        self.metadata.extend(meta)
    
    def search(
        self,
        query_vec: np.ndarray,
        top_k: int = None,
        search_type: str = None
    ) -> List[Tuple[Dict, float]]:
        """
        Search the index with optional type filtering.
        
        Args:
            query_vec: Query embedding (1, dim)
            top_k: Number of results to return
            search_type: Filter by "text" or "image", None for all
        
        Returns:
            List of (metadata, score) tuples
        """
        if top_k is None:
            top_k = cfg.top_k
        
        query_vec = query_vec.astype("float32")
        faiss.normalize_L2(query_vec)
        
        # Type-aware filtering
        if search_type:
            filtered_indices = [
                i for i, m in enumerate(self.metadata)
                if m.get("embedding_type") == search_type
            ]
            
            if not filtered_indices:
                return []
            
            # Create temporary index for filtered search
            vectors = np.array([
                self.index.reconstruct(i) for i in filtered_indices
            ]).astype("float32")
            
            temp_index = faiss.IndexFlatIP(self.dim)
            temp_index.add(vectors)
            
            distances, indices = temp_index.search(query_vec, min(top_k, len(vectors)))
            
            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx >= 0:
                    global_idx = filtered_indices[idx]
                    results.append((self.metadata[global_idx], float(dist)))
            
            return results
        else:
            # Search all
            distances, indices = self.index.search(query_vec, top_k)
            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx >= 0:
                    results.append((self.metadata[idx], float(dist)))
            return results
    
    def save(self, index_path: str = None, metadata_path: str = None):
        """Save index and metadata to disk."""
        if index_path is None:
            index_path = cfg.faiss_index_path
        if metadata_path is None:
            metadata_path = cfg.metadata_path
        
        faiss.write_index(self.index, index_path)
        with open(metadata_path, "wb") as f:
            pickle.dump(self.metadata, f)
        
        print(f"💾 Index saved: {index_path}")
        print(f"💾 Metadata saved: {metadata_path}")
    
    @classmethod
    def load(cls, embedder: CLIPEmbedder, index_path: str = None, metadata_path: str = None):
        """Load index and metadata from disk."""
        if index_path is None:
            index_path = cfg.faiss_index_path
        if metadata_path is None:
            metadata_path = cfg.metadata_path
        
        store = cls(embedder)
        store.index = faiss.read_index(index_path)
        with open(metadata_path, "rb") as f:
            store.metadata = pickle.load(f)
        
        print(f"📂 Index loaded: {index_path}")
        print(f"📂 Metadata loaded: {metadata_path}")
        return store

# -----------------------
# Build Index with Semantic Chunking
# -----------------------
def build_index(
    pages_data: List[Dict],
    embedder: CLIPEmbedder,
    store: VisionRAGStore,
    use_semantic_chunking: bool = True
):
    """
    Build FAISS index from extracted text and images.
    
    Args:
        pages_data: Output from extract_text_and_images_from_pdf
        embedder: CLIPEmbedder instance
        store: VisionRAGStore instance
        use_semantic_chunking: If True, uses semantic text chunking
    """
    print("🔨 Building index...")
    
    for page in tqdm(pages_data, desc="Indexing pages"):
        # Text embeddings with semantic chunking
        if page["text"].strip():
            if use_semantic_chunking:
                text_chunks = semantic_chunk_text(page["text"])
            else:
                text_chunks = [page["text"]]
            
            if text_chunks:
                text_vecs = embedder.embed_text(text_chunks)
                meta = [
                    {
                        "type": "text",
                        "page_num": page["page_num"],
                        "content": chunk,
                        "embedding_type": "text"
                    }
                    for chunk in text_chunks
                ]
                store.add_embeddings(text_vecs, meta)
        
        # Image embeddings
        if page["images"]:
            img_vecs = embedder.embed_images(page["images"])
            meta = [
                {
                    "type": "image",
                    "page_path": img_path,
                    "page_num": page["page_num"],
                    "embedding_type": "image"
                }
                for img_path in page["images"]
            ]
            store.add_embeddings(img_vecs, meta)
    
    print("✅ Index built successfully!")
    print(f"   Total vectors: {store.index.ntotal}")
    print(f"   Text chunks: {sum(1 for m in store.metadata if m['type'] == 'text')}")
    print(f"   Images: {sum(1 for m in store.metadata if m['type'] == 'image')}")

# -----------------------
# Hybrid Retrieval (Text + Image)
# -----------------------
def retrieve_relevant_pages(
    query: str,
    embedder: CLIPEmbedder,
    store: VisionRAGStore,
    top_k: int = None
) -> List[Tuple[Dict, float]]:
    """
    Hybrid retrieval: search text and image embeddings, then merge and rerank.
    
    Returns:
        List of (metadata, score) tuples sorted by relevance
    """
    if top_k is None:
        top_k = cfg.top_k
    
    query_vec = embedder.embed_text([query])
    
    # Search text embeddings
    text_results = store.search(query_vec, top_k=top_k, search_type="text")
    print(f"🧠 Retrieved {len(text_results)} text results")
    
    # Search image embeddings
    image_results = store.search(query_vec, top_k=top_k, search_type="image")
    print(f"🖼️ Retrieved {len(image_results)} image results")
    
    # Merge and rerank by score (higher is better for cosine similarity)
    combined = text_results + image_results
    combined.sort(key=lambda x: x[1], reverse=True)
    
    print(f"✅ Combined and reranked {len(combined)} results")
    return combined[:top_k]

# -----------------------
# Pixtral Answer Generation
# -----------------------
def encode_image_base64(image_path: str) -> str:
    """Encode image file to base64 string."""
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"⚠️ Error encoding {image_path}: {e}")
        return None

# def generate_answer_with_pixtral(
#     query: str,
#     retrieved_pages: List[Tuple[Dict, float]]
# ) -> str:
#     """
#     Generate answer using Pixtral VLM with retrieved context.
    
#     Args:
#         query: User question
#         retrieved_pages: List of (metadata, score) from retrieval
    
#     Returns:
#         Generated answer string
#     """
#     if client is None:
#         return "❌ Mistral API client not initialized. Set MISTRAL_API_KEY environment variable."
    
#     # Collect images
#     image_msgs = []
#     text_context = []
    
#     for meta, score in retrieved_pages:
#         if meta["type"] == "image":
#             b64 = encode_image_base64(meta["page_path"])
#             if b64:
#                 image_msgs.append({
#                     "type": "image_url",
#                     "image_url": f"data:image/jpeg;base64,{b64}"
#                 })
#         elif meta["type"] == "text":
#             text_context.append(f"[Page {meta['page_num']}] {meta['content'][:500]}")
    
#     # Build prompt
#     context_str = "\n\n".join(text_context) if text_context else "No text context available."
    
#     prompt = f"""Context from document:
# {context_str}

# Question: {query}

# Please answer the question based on the provided context and images. Be concise and cite specific pages when possible."""
    
#     # Build message
#     content = [{"type": "text", "text": prompt}] + image_msgs
    
#     try:
#         response = client.chat.complete(
#             model=cfg.pixtral_model,
#             messages=[{"role": "user", "content": content}],
#             temperature=0.1
#         )
#         return response.choices[0].message.content
#     except Exception as e:
#         return f"❌ Error generating answer: {e}"

# # -----------------------
# # Complete Pipeline
# # -----------------------
# def run_pipeline(pdf_path: str, query: str, rebuild_index: bool = True):
#     """
#     Complete VisRAG pipeline:
#     1. Extract text + images from PDF (with filtering)
#     2. Build/load FAISS index with semantic chunking
#     3. Retrieve relevant pages
#     4. Generate answer with Pixtral
    
#     Args:
#         pdf_path: Path to PDF document
#         query: User question
#         rebuild_index: If False, tries to load existing index
#     """
#     print("\n" + "="*60)
#     print("🚀 Enhanced VisRAG Pipeline")
#     print("="*60 + "\n")
    
#     # Initialize embedder
#     embedder = CLIPEmbedder()
    
#     # Extract or load index
#     if rebuild_index or not os.path.exists(cfg.faiss_index_path):
#         # Extract from PDF
#         pages_data = extract_text_and_images_from_pdf(pdf_path, query=query)
        
#         # Build index
#         store = VisionRAGStore(embedder)
#         build_index(pages_data, embedder, store)
        
#         # Save for future use
#         store.save()
#     else:
#         # Load existing index
#         print("📂 Loading existing index...")
#         store = VisionRAGStore.load(embedder)
    
#     # Retrieve
#     print(f"\n🔍 Query: {query}")
#     retrieved = retrieve_relevant_pages(query, embedder, store)
    
#     # Display retrieved results
#     print("\n📋 Top Retrieved Results:")
#     for i, (meta, score) in enumerate(retrieved[:5], 1):
#         if meta["type"] == "text":
#             preview = meta["content"][:100] + "..."
#             print(f"  {i}. [TEXT] Page {meta['page_num']} (score={score:.4f})")
#             print(f"     {preview}")
#         else:
#             print(f"  {i}. [IMAGE] Page {meta['page_num']} (score={score:.4f})")
#             print(f"     {meta['page_path']}")
    
#     # Generate answer
#     print("\n🤖 Generating answer with Pixtral...")
#     answer = generate_answer_with_pixtral(query, retrieved)
    
#     print("\n" + "="*60)
#     print("💡 Generated Answer:")
#     print("="*60)
#     print(answer)
#     print("="*60 + "\n")
    
#     return answer

# -----------------------
# Pixtral Answer Generation (Updated)
# -----------------------
def generate_answer_with_pixtral(
    query: str,
    retrieved_pages: List[Tuple[Dict, float]],
    pdf_path: str = None
) -> Tuple[str, Dict, List[Dict], List[str]]:
    """
    Generate answer using Pixtral VLM with retrieved context.
    Returns: (answer_text, citation_map, document_pages_list, source_links)
    """
    if client is None:
        return (
            "❌ Mistral API client not initialized. Set MISTRAL_API_KEY environment variable.",
            {},
            [],
            []
        )
    
    # Collect context
    image_msgs = []
    text_context = []
    citation_map = {}
    document_pages = {}
    source_links = []

    for i, (meta, score) in enumerate(retrieved_pages, start=1):
        citation_id = f"chunk_{i}"
        citation_map[citation_id] = meta

        if meta["type"] == "image":
            b64 = encode_image_base64(meta["page_path"])
            if b64:
                image_msgs.append({
                    "type": "image_url",
                    "image_url": f"data:image/jpeg;base64,{b64}"
                })
                src = Path(meta["page_path"]).name
                source_links.append(src)
                document_pages.setdefault(pdf_path, set()).add(meta["page_num"])
        elif meta["type"] == "text":
            page = meta["page_num"]
            snippet = meta["content"][:500]
            text_context.append(f"[Chunk {i}] Page {page}: {snippet}")
            document_pages.setdefault(pdf_path, set()).add(page)

    context_str = "\n\n".join(text_context) if text_context else "No textual context found."

    # Build Pixtral prompt
    prompt = f"""Answer the following question using the provided multimodal context.
Context:
{context_str}

Question: {query}
Be concise and provide page-based references when possible."""

    content = [{"type": "text", "text": prompt}] + image_msgs

    try:
        response = client.chat.complete(
            model=cfg.pixtral_model,
            messages=[{"role": "user", "content": content}],
            temperature=0.1
        )
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        answer = f"❌ Error generating answer: {e}"

    # Convert pages dict into structured list for unified format
    document_pages_list = [
        {"source": pdf_path, "pages": sorted(list(pages))}
        for src, pages in document_pages.items()
    ]

    return answer, citation_map, document_pages_list, source_links


# -----------------------
# Complete Pipeline (Unified Return Type)
# -----------------------
def run_pipeline(pdf_path: str, query: str, rebuild_index: bool = True) -> Dict[str, Any]:
    """
    Complete VisRAG pipeline aligned with UnifiedRAGPipeline return structure.
    Returns:
        {
            "answer": str,
            "sources": list[str],
            "document_pages_dict": list[dict],
            "citation_map": dict,
            "chunks_used": list[dict]
        }
    """
    print("\n" + "="*60)
    print("🚀 Enhanced VisRAG Pipeline (Unified Format)")
    print("="*60 + "\n")

    # Initialize embedder
    embedder = CLIPEmbedder()

    # Extract or load index
    if rebuild_index or not os.path.exists(cfg.faiss_index_path):
        pages_data = extract_text_and_images_from_pdf(pdf_path, query=query)
        store = VisionRAGStore(embedder)
        build_index(pages_data, embedder, store)
        store.save()
    else:
        print("📂 Loading existing index...")
        store = VisionRAGStore.load(embedder)

    # Retrieve relevant results
    print(f"\n🔍 Query: {query}")
    retrieved = retrieve_relevant_pages(query, embedder, store)

    # Display top results (debug)
    print("\n📋 Top Retrieved Results:")
    for i, (meta, score) in enumerate(retrieved[:5], 1):
        if meta["type"] == "text":
            preview = meta["content"][:100] + "..."
            print(f"  {i}. [TEXT] Page {meta['page_num']} (score={score:.4f}) — {preview}")
        else:
            print(f"  {i}. [IMAGE] Page {meta['page_num']} (score={score:.4f}) — {meta['page_path']}")

    # Generate answer and unified metadata
    print("\n🤖 Generating answer with Pixtral...")
    answer, citation_map, document_pages_list, source_links = generate_answer_with_pixtral(query, retrieved,pdf_path)
    

    # Unified return structure (matches UnifiedRAGPipeline)
    result = {
        "answer": answer,
        "sources": source_links,
        "document_pages_dict": document_pages_list,
        "citation_map": citation_map,
        "chunks_used": [meta for meta, _ in retrieved]
    }

    print("\n" + "="*60)
    print("💡 Unified Output Format:")
    print("="*60)
    print(json.dumps(result, indent=2,default=str)[:1500])  # Preview (truncated)
    print("="*60 + "\n")

    return result


# -----------------------
# Main
# -----------------------
if __name__ == "__main__":
    # Example usage
    pdf_path = "../Fact Sheet.pdf"
    query = "what is the operating margin in Q3FY25 from growth summary charts(inr)?"
    # query = "what is growth by market in north america in q1fy26? Give the exact value"
    
    # Run pipeline
    answer = run_pipeline(pdf_path, query, rebuild_index=True)