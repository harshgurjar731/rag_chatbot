# visrag/common_components.py
import io
import base64
import pickle
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
import faiss
import torch
from PIL import Image, ImageStat
from transformers import CLIPProcessor, CLIPModel
from langchain.text_splitter import RecursiveCharacterTextSplitter
from Services.VisRag.config import cfg, client
import pymupdf

# ======================================================
# Utility Functions
# ======================================================
def encode_image_base64(image_path: str) -> str:
    """Convert image to base64-encoded string for VLM prompts."""
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None


def semantic_chunk_text(text: str) -> List[str]:
    """Split long text into semantically coherent chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
        separators=["\n\n", "\n", ".", "!", "?", " "],
    )
    chunks = splitter.split_text(text)
    return [chunk.strip() for chunk in chunks if chunk.strip()]



# ======================================================
# Enhanced Pixtral Relevance Check
# ======================================================
# def is_low_quality_image(image_bytes: bytes, brightness_threshold: float = cfg.brightness_threshold, contrast_threshold: float = 10.0) -> bool:
#     """
#     Checks for low-quality or mostly blank images using brightness + contrast.
#     Returns True if the image is likely too dark, too bright, or has low contrast.
#     """
#     try:
#         image = Image.open(io.BytesIO(image_bytes)).convert("L")  # grayscale
#         stat = ImageStat.Stat(image)
#         brightness = stat.mean[0]
#         contrast = stat.stddev[0]

#         # Consider both brightness extremes and flatness (low contrast)
#         if brightness < brightness_threshold or brightness > 245 or contrast < contrast_threshold:
#             return True
#         return False
#     except Exception as e:
#         print(f"⚠️ Image quality check failed: {e}")
#         return True


# def is_image_relevant(image_bytes: bytes, page_text: str, query: str = None) -> bool:
#     """
#     Uses Pixtral Vision-Language Model (VLM) to assess whether an image
#     is relevant to the page context (text). Works even without explicit query.
#     """
#     try:
#         # --- Skip low-quality or blank images early ---
#         if is_low_quality_image(image_bytes):
#             print("⚠️ Skipped low-quality or blank image (auto-marked not relevant).")
#             return False

#         b64_image = base64.b64encode(image_bytes).decode("utf-8")

#         # --- Build structured multimodal input ---
#         prompt_text = (
#             "You are an expert vision-language model analyzing PDF documents.\n"
#             "Your task is to determine if the given image contains visual or textual information "
#             "that contributes meaningfully to the nearby text content of a document page.\n\n"
#             "Consider charts, graphs, tables, scanned text, signatures, or figures as relevant "
#             "if they help explain, illustrate, or provide data related to the text.\n"
#             "Only say 'relevant' if the image supports or relates to the text; otherwise say 'not relevant'.\n\n"
#             f"Page text (trimmed):\n{page_text[:1200]}"
#         )

#         # --- Prepare multimodal content ---
#         content = [
#             {"type": "text", "text": prompt_text},
#             {"type": "image_url", "image_url": f"data:image/jpeg;base64,{b64_image}"}
#         ]

#         # --- Query Pixtral model ---
#         response = client.chat.complete(
#             model=cfg.pixtral_model,
#             messages=[{"role": "user", "content": content}],
#             temperature=0.0,
#         )

#         answer = response.choices[0].message.content.strip().lower()
#         print(f"🖼️ Pixtral relevance response: {answer}")

#         # --- Flexible relevance interpretation ---
#         positive_signals = ["relevant", "yes", "related", "useful", "important", "contains data", "supports"]
#         negative_signals = ["not relevant", "no", "unrelated", "irrelevant", "blank", "none"]

#         # ✅ Strong inclusion logic
#         if any(pos in answer for pos in positive_signals) and not any(neg in answer for neg in negative_signals):
#             return True

#         return False

#     except Exception as e:
#         print(f"⚠️ Pixtral relevance check failed: {e}")
#         # --- Fallback heuristic ---
#         # Non-blank images on text-heavy pages are often relevant
#         if not is_low_quality_image(image_bytes) and len(page_text.strip()) > 200:
#             print("⚙️ Using fallback heuristic: marking image as relevant (page has rich text).")
#             return True
#         return False

def is_black_image(image_bytes: bytes, threshold: float = 10.0) -> bool:
    """
    Check if the image is mostly black or blank using brightness threshold.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("L")  # grayscale
        stat = ImageStat.Stat(image)
        brightness = stat.mean[0]  # 0 = black, 255 = white
        return brightness < threshold
    except Exception:
        return True  # treat unreadable/corrupt images as black


def is_image_relevant(image_bytes: bytes, page_text: str, query: str = None) -> bool:
    """
    Uses Pixtral to decide if the image is relevant based on surrounding text and query.
    Returns True if the image is relevant, False otherwise.
    """
    try:
        # Skip black/blank images to avoid useless LLM calls
        if is_black_image(image_bytes):
            print("⚠️ Skipped dark or blank image (auto-marked not relevant).")
            return False

        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        # Build message content
        content = [
            {
                "type": "text",
                "text": (
                    f"Determine whether this image is relevant to the document context.\n\n"
                    f"Text near the image:\n{page_text[:1000]}\n\n"
                    f"User query (if provided): {query or 'None'}\n\n"
                    "Respond only with 'relevant' or 'not relevant'."
                ),
            },
            {"type": "image_url", "image_url": f"data:image/jpeg;base64,{b64_image}"},
        ]

        # Send to model
        response = client.chat.complete(
            model=cfg.pixtral_model,
            messages=[{"role": "user", "content": content}],
            temperature=0.0,
        )

        # Normalize response
        answer = response.choices[0].message.content.strip().lower()
        if "relevant" in answer and "not" not in answer:
            return True
        return False

    except Exception as e:
        print(f"⚠️ LLM relevance check failed: {e}")
        # Fallback: assume relevant only if it's a valid non-black image
        return not is_black_image(image_bytes)

def extract_and_save_image(doc, img_info, page_num, file_id, text, output_dir, stats, mode="embed"):
    """Extract, filter, summarize, and save embedded image."""
    xref = img_info[0]
    base_image = doc.extract_image(xref)
    image_bytes = base_image["image"]
    ext = base_image.get("ext", "png")
    width, height = base_image.get("width", 0), base_image.get("height", 0)

    if width < 50 or height < 50:
        stats["skipped_small"] += 1
        return None

    if not is_image_relevant(image_bytes, text):
        stats["filtered"] += 1
        return None

    filename = f"{file_id}_p{page_num+1:04d}_{mode}{xref}.{ext}"
    img_path = output_dir / filename
    with open(img_path, "wb") as f:
        f.write(image_bytes)
    stats[mode + "ded"] += 1

    # ✅ Generate image summary via Pixtral
    summary = generate_image_summary(image_bytes, text)

    return {
        "type": "image",
        "page_num": page_num + 1,
        "page_path": str(img_path.resolve()),
        "embedding_type": "image",
        "summary": summary,
    }


def extract_and_save_block_image(page, block, block_idx, page_num, file_id, text, output_dir, stats):
    """Extract, filter, summarize, and save block image."""
    bbox = pymupdf.Rect(block.get("bbox"))
    if bbox.width < 50 or bbox.height < 50:
        stats["skipped_small"] += 1
        return None

    pix = page.get_pixmap(matrix=pymupdf.Matrix(2.0, 2.0), clip=bbox, alpha=False)
    image_bytes = pix.tobytes("png")

    if not is_image_relevant(image_bytes, text):
        stats["filtered"] += 1
        return None

    filename = f"{file_id}_p{page_num+1:04d}_block{block_idx}.png"
    img_path = output_dir / filename
    pix.save(str(img_path))
    stats["blocks"] += 1

    # ✅ Generate image summary via Pixtral
    summary = generate_image_summary(image_bytes, text)

    return {
        "type": "image",
        "page_num": page_num + 1,
        "page_path": str(img_path.resolve()),
        "embedding_type": "image",
        "summary": summary,
    }

def generate_image_summary(image_bytes: bytes, context_text: str) -> str:
    """
    Uses Pixtral model to generate a short descriptive summary of the relevant image.
    """
    try:
        b64_img = base64.b64encode(image_bytes).decode("utf-8")
        content = [
            {"type": "text", "text": f"Summarize this image in the context of the following text:\n{context_text[:1000]}"},
            {"type": "image_url", "image_url": f"data:image/png;base64,{b64_img}"},
        ]

        response = client.chat.complete(
            model=cfg.pixtral_model,
            messages=[{"role": "user", "content": content}],
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"⚠️ Failed to generate image summary: {e}")
        return "No summary available."
    

def print_summary(stats, output_dir):
    """Pretty-print file processing summary."""
    print("\n" + "=" * 60)
    print("✅ File Processing Summary")
    print("=" * 60)
    print(f"📄 Pages processed: {stats['pages']}")
    print(f"🖼️ Embedded images saved: {stats['embedded']}")
    print(f"🧩 Block images saved: {stats['blocks']}")
    print(f"🚫 Filtered (non-relevant): {stats['filtered']}")
    print(f"⚠️ Skipped (too small): {stats['skipped_small']}")
    print(f"❌ Errors: {stats['errors']}")
    print(f"📂 Output path: {output_dir.resolve()}")
    print("=" * 60 + "\n")


# ======================================================
# CLIP Embedder
# ======================================================
class CLIPEmbedder:
    """Handles CLIP model for multimodal embeddings (text + image)."""
    def __init__(self, model_name: str = None):
        model_name = model_name or cfg.clip_model_name
        self.device = cfg.device
        self.model = CLIPModel.from_pretrained(model_name).to(self.device)
        self.processor = CLIPProcessor.from_pretrained(model_name)

        # Determine embedding dimension
        with torch.no_grad():
            dummy_text = ["test"]
            inputs = self.processor(text=dummy_text, return_tensors="pt", padding=True).to(self.device)
            test_emb = self.model.get_text_features(**inputs)
        self.dim = test_emb.shape[1]
        print(f"[INIT] CLIP model loaded ({model_name}) — dim={self.dim}")

    def embed_text(self, texts: List[str]) -> np.ndarray:
        inputs = self.processor(text=texts, return_tensors="pt", padding=True, truncation=True).to(self.device)
        with torch.no_grad():
            embeddings = self.model.get_text_features(**inputs)
        arr = embeddings.cpu().numpy().astype("float32")
        faiss.normalize_L2(arr)
        return arr

    def embed_images(self, image_paths: List[str]) -> np.ndarray:
        images = [Image.open(p).convert("RGB") for p in image_paths]
        inputs = self.processor(images=images, return_tensors="pt", padding=True).to(self.device)
        with torch.no_grad():
            embeddings = self.model.get_image_features(**inputs)
        arr = embeddings.cpu().numpy().astype("float32")
        faiss.normalize_L2(arr)
        return arr


# ======================================================
# FAISS Vector Store
# ======================================================
class VisionRAGStore:
    """Type-aware FAISS store for text + image embeddings."""
    def __init__(self, embedder: CLIPEmbedder):
        self.dim = embedder.dim
        self.index = faiss.IndexFlatIP(self.dim)
        self.metadata: List[Dict[str, Any]] = []

    def add_embeddings(self, embeddings: np.ndarray, meta: List[Dict[str, Any]]):
        self.index.add(embeddings.astype("float32"))
        self.metadata.extend(meta)

    def save(self, file_id: str):
        index_path = Path(cfg.faiss_dir) / f"{file_id}_index.faiss"
        meta_path = Path(cfg.faiss_dir) / f"{file_id}_metadata.pkl"
        faiss.write_index(self.index, str(index_path))
        with open(meta_path, "wb") as f:
            pickle.dump(self.metadata, f)
        print(f"💾 Stored FAISS index and metadata for {file_id}")

    @classmethod
    def load(cls, embedder: CLIPEmbedder, file_id: str):
        store = cls(embedder)
        index_path = Path(cfg.faiss_dir) / f"{file_id}_index.faiss"
        meta_path = Path(cfg.faiss_dir) / f"{file_id}_metadata.pkl"
        store.index = faiss.read_index(str(index_path))
        with open(meta_path, "rb") as f:
            store.metadata = pickle.load(f)
        return store

    def search(self, query_vec: np.ndarray, top_k: int = None, search_type: str = None):
        top_k = top_k or cfg.top_k
        faiss.normalize_L2(query_vec)

        if search_type:
            indices = [i for i, m in enumerate(self.metadata) if m["embedding_type"] == search_type]
            if not indices:
                return []
            vectors = np.array([self.index.reconstruct(i) for i in indices]).astype("float32")
            temp_index = faiss.IndexFlatIP(self.dim)
            temp_index.add(vectors)
            distances, idxs = temp_index.search(query_vec, min(top_k, len(vectors)))
            return [(self.metadata[indices[i]], float(dist)) for i, dist in zip(idxs[0], distances[0]) if i >= 0]
        else:
            distances, idxs = self.index.search(query_vec, top_k)
            return [(self.metadata[i], float(dist)) for i, dist in zip(idxs[0], distances[0]) if i >= 0]
