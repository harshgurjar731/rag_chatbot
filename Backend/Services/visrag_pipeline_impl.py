"""
visrag_pipeline_impl.py

VisRAG-style pipeline (practical implementation).
- Render PDF -> page images
- Embed page images (vision encoder)
- Index in FAISS
- Given a text query, embed query and retrieve top-k pages
- Generate answer with a VLM (BLIP-2) OR LLM using retrieved page captions+OCR

Swap-in notes: you can replace the CLIP encoders with the official
openbmb/VisRAG-Ret (Hugging Face) models for closer fidelity to the paper.
"""

import os
import io
import sys
import math
from pathlib import Path
from typing import List, Dict, Tuple, Any

import numpy as np
from PIL import Image
import fitz  # PyMuPDF -- render PDF pages to images
import faiss
from tqdm import tqdm
import pymupdf

# Transformers / models
import torch
from transformers import (
    CLIPProcessor, CLIPModel,
    Blip2Processor, Blip2ForConditionalGeneration,
    AutoTokenizer, AutoModelForSeq2SeqLM
)

# Optional OCR
try:
    import pytesseract
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

# Sentence transformer optional (for hybrid text embeddings)
from sentence_transformers import SentenceTransformer

# -----------------------
# Config
# -----------------------
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
PAGE_DPI = 150  # PDF page render DPI; upsize for better layout capture
EMBED_DIM = 512  # default for CLIP ViT-B/32
TOP_K = 5

# Choose models (defaults)
CLIP_MODEL = "openai/clip-vit-base-patch32"  # retrieval (image + text encoders)
BLIP2_MODEL = "Salesforce/blip2-flan-t5-xl"  # generation VLM (smaller; or use flan-t5-xl/xxl if you have)
# Optionally: official VisRAG retriever (Hugging Face) -- faster/better if you want to replicate paper exactly
OFFICIAL_VISRAG_RETRIEVER = "openbmb/VisRAG-Ret"  # *optional swap*

# -----------------------
# Utilities
# -----------------------
def pdf_to_page_images(pdf_path: str, out_dir: str = "./page_images", dpi: int = PAGE_DPI) -> List[str]:
    """
    Render PDF pages to images using PyMuPDF (fitz).

    Args:
        pdf_path (str): Path to the source PDF file.
        out_dir (str): Directory where page images will be saved.
        dpi (int): Dots per inch for rendering quality.

    Returns:
        List[str]: List of paths to the saved page images.
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(pdf_path)
    img_paths = []
    for i in range(len(doc)):
        page = doc[i]
        mat = fitz.Matrix(dpi/72, dpi/72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_path = os.path.join(out_dir, f"page_{i+1:04d}.png")
        pix.save(img_path)
        img_paths.append(img_path)
    return img_paths

# -----------------------
# Embedding: CLIP (image + text)
# -----------------------
class ClipIndexer:
    """
    A class to index and search images/text using CLIP embeddings.
    """
    def __init__(self, model_name: str = CLIP_MODEL, device: str = DEVICE):
        """
        Initializes the ClipIndexer with a specified model.
        
        Args:
            model_name (str): The name of the CLIP model to load.
            device (str): Computation device ('cuda' or 'cpu').
        """
        self.device = device
        self.model_name = model_name
        self.model = CLIPModel.from_pretrained(model_name).to(self.device)
        self.processor = CLIPProcessor.from_pretrained(model_name)

        # ✅ Use text encoder dimension (PDF → text embeddings)
        self.dim = self.model.text_model.config.hidden_size

        # ✅ FAISS index for cosine similarity
        self.index = faiss.IndexFlatIP(self.dim)
        self.metadatas: List[Dict[str, Any]] = []

        print(f"[INIT] CLIP model loaded: {model_name}")
        print(f"[INIT] Using text embedding dimension = {self.dim}")

    # ---------------------- Embedding Functions ----------------------

    def embed_images(self, pil_images: List[Image.Image]) -> np.ndarray:
        """
        Compute normalized CLIP image embeddings.

        Args:
            pil_images (List[Image.Image]): List of PIL Image objects.

        Returns:
            np.ndarray: Normalized image embeddings of shape (N, dim).
        """
        inputs = self.processor(images=pil_images, return_tensors="pt").to(self.device)
        with torch.no_grad():
            img_embeds = self.model.get_image_features(**inputs)
        img_embeds = img_embeds.cpu().numpy().astype("float32")
        faiss.normalize_L2(img_embeds)
        return img_embeds

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Compute normalized CLIP text embeddings.

        Args:
            texts (List[str]): List of text strings.

        Returns:
            np.ndarray: Normalized text embeddings of shape (N, dim).
        """
        inputs = self.processor(text=texts, return_tensors="pt", padding=True, truncation=True).to(self.device)
        with torch.no_grad():
            txt_embeds = self.model.get_text_features(**inputs)
        txt_embeds = txt_embeds.cpu().numpy().astype("float32")
        faiss.normalize_L2(txt_embeds)
        return txt_embeds

    # ---------------------- Index Management ----------------------

    def add(self, vectors: np.ndarray, metas: List[Dict[str, Any]]):
        """
        Add new embeddings and metadata to the FAISS index.
        Automatically validates vector dimensionality.

        Args:
            vectors (np.ndarray): Embeddings array.
            metas (List[Dict[str, Any]]): List of metadata dictionaries corresponding to vectors.

        Raises:
            ValueError: If vector dimension matches FAISS index dimension.
        """
        vectors = np.array(vectors).astype("float32")

        # Lazily initialize FAISS index if missing
        if not hasattr(self, "index") or self.index is None:
            self.index = faiss.IndexFlatIP(vectors.shape[1])
            print(f"[INFO] Created new FAISS index with dim={vectors.shape[1]}")

        # Validate dimensions
        if vectors.shape[1] != self.index.d:
            raise ValueError(
                f"[ERROR] Vector dimension ({vectors.shape[1]}) != FAISS index dimension ({self.index.d}). "
                "Ensure you're using the same encoder for both indexing and querying."
            )

        # Add vectors and metadata
        self.index.add(vectors)
        self.metadatas.extend(metas)
        print(f"[INFO] Added {len(vectors)} vectors to FAISS index (dim={self.index.d})")

    # ---------------------- Search ----------------------

    def search_by_vector(self, qvec: np.ndarray, top_k: int = TOP_K) -> List[Tuple[Dict, float]]:
        """
        Search the FAISS index by query vector and return top_k results.

        Args:
           qvec (np.ndarray): Query vector.
           top_k (int): Number of top results to return.

        Returns:
           List[Tuple[Dict, float]]: List of (metadata, score) tuples.
        """
        faiss.normalize_L2(qvec)
        D, I = self.index.search(qvec, top_k)

        results = []
        for dist, idx in zip(D[0], I[0]):
            if idx < 0:
                continue
            results.append((self.metadatas[idx], float(dist)))
        return results
    

# -----------------------
# Simple OCR + caption helper
# -----------------------
def ocr_image(path: str) -> str:
    if not OCR_AVAILABLE:
        return ""
    img = Image.open(path).convert("RGB")
    txt = pytesseract.image_to_string(img)
    return txt.strip()

def caption_image_with_blip2(image: Image.Image, blip_processor, blip_model, device=DEVICE) -> str:
    inputs = blip_processor(images=image, return_tensors="pt").to(device)
    with torch.no_grad():
        generated_ids = blip_model.generate(**inputs, max_new_tokens=128)
        caption = blip_processor.decode(generated_ids[0], skip_special_tokens=True)
    return caption

# -----------------------
# Pipeline: build index from PDF pages
# -----------------------
def build_index_from_pdf(pdf_path: str, tmp_img_dir: str = "./page_images") -> Tuple[ClipIndexer, List[str]]:
    print("Rendering PDF -> page images...")
    page_paths = pdf_to_page_images(pdf_path, out_dir=tmp_img_dir)
    print(f"Rendered {len(page_paths)} page images.")

    # Initialize indexer
    indexer = ClipIndexer(model_name=CLIP_MODEL)

    # embed images in batches
    B = 8
    all_metas = []
    for i in range(0, len(page_paths), B):
        batch_paths = page_paths[i:i+B]
        pil_imgs = [Image.open(p).convert("RGB") for p in batch_paths]
        vecs = indexer.embed_images(pil_imgs)
        metas = []
        for p in batch_paths:
            metas.append({"page_path": p})
        indexer.add(vecs, metas)
        all_metas.extend(metas)
    print("Index built (CLIP).")
    return indexer, page_paths

# -----------------------
# Query -> retrieve -> generate
# -----------------------
def retrieve_pages_for_query(query: str, indexer: ClipIndexer, top_k: int = TOP_K):
    # embed query as CLIP text
    qvec = indexer.embed_texts([query])  # shape (1,dim)
    hits = indexer.search_by_vector(qvec, top_k=top_k)
    return hits

def generate_answer_with_blip2(query: str, retrieved_pages: List[Tuple[Dict,float]], blip_processor, blip_model, device=DEVICE):
    """
    Strategy: For each retrieved page, feed the image to BLIP-2 and ask the VLM to answer
    while also conditioning on the query and other images. This requires a VLM that can
    accept multiple images or serially condition. We'll implement a simple serial approach:
    - For top-N retrieved pages, form a prompt that includes: query + per-page caption (from BLIP) + simple note.
    - Use BLIP-2 to generate response over the aggregated context.
    """
    # Build multimodal inputs: images + query via BLIP processor -> generation
    # This simplified approach concatenates images as separate inputs and uses the processor accordingly.
    # NOTE: BLIP-2 generation with multiple images in a single forward may require special handling depending on model. We do serial conditioning here.
    page_images = [Image.open(hit[0]["page_path"]).convert("RGB") for hit in retrieved_pages]
    # Option: produce captions first and then pass captions + query to an LLM
    captions = []
    for img in page_images:
        caption = caption_image_with_blip2(img, blip_processor, blip_model, device=device)
        captions.append(caption)
    # Compose prompt text
    context_text = "\n\n".join([f"[Page {i+1}] {cap}" for i, cap in enumerate(captions)])
    user_prompt = f"Context (captions from retrieved pages):\n{context_text}\n\nQuestion: {query}\nAnswer concisely and cite which page caption(s) you used."
    # Now generate answer using the BLIP-2 model as text-only (processor supports text input)
    inputs = blip_processor(text=user_prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        gen_ids = blip_model.generate(**inputs, max_new_tokens=256, do_sample=False)
        ans = blip_processor.decode(gen_ids[0], skip_special_tokens=True)
    return ans

# -----------------------
# Helper: switch to official VisRAG retriever (optional)
# -----------------------
def load_official_visrag_retriever(hf_model_name: str = OFFICIAL_VISRAG_RETRIEVER, device: str = DEVICE):
    """
    The paper authors published VisRAG-Ret on Hugging Face. If you want to exactly
    replicate the retriever architecture and weights, load it here.
    Example (pseudo): many VisRAG models expose a feature extractor and a torch model.
    You may need to adapt usage depending on the model card.
    """
    # NOTE: Implementation details depend on the HF model repo. Often they provide
    # a 'feature_extractor' and 'model'. Example usage might be:
    # from transformers import AutoFeatureExtractor, AutoModel
    # fe = AutoFeatureExtractor.from_pretrained(hf_model_name)
    # model = AutoModel.from_pretrained(hf_model_name).to(device)
    # Then use the model to produce embeddings for images and the corresponding text query encoder for text.
    raise NotImplementedError("See notes below for instructions to swap in official VisRAG retriever from HF.")

# -----------------------
# Main example usage
# -----------------------
def demo(pdf_path: str, query: str):
    indexer, page_paths = build_index_from_pdf(pdf_path)
    hits = retrieve_pages_for_query(query, indexer, top_k=TOP_K)
    print("Top retrieved pages (CLIP scores):")
    for meta, score in hits:
        print(f"  {meta['page_path']}  score={score:.4f}")
    # Load BLIP-2 generator
    print("Loading BLIP-2 generator (this may download weights)...")
    blip_processor = Blip2Processor.from_pretrained(BLIP2_MODEL)
    blip_model = Blip2ForConditionalGeneration.from_pretrained(BLIP2_MODEL).to(DEVICE)
    # Prepare retrieved pages as list of (meta,score)
    retrieved = hits
    ans = generate_answer_with_blip2(query, retrieved, blip_processor, blip_model)
    print("\n=== Generated Answer ===\n")
    print(ans)

# -----------------------
# If run as script
# -----------------------
if __name__ == "__main__":
    # if len(sys.argv) < 3:
    #     print("Usage: python visrag_pipeline_impl.py path/to/doc.pdf \"your query\"")
    #     sys.exit(1)
    pdf ="Fact Sheet.pdf"
    q = "Explain Mitigation Strategies mentioned in the document."
    demo(pdf, q)
