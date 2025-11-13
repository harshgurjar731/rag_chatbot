# visrag/file_processing_pipeline.py
import pymupdf
from tqdm import tqdm
from pathlib import Path
from Services.VisRag.config import cfg
from Services.VisRag.common_components import (
    CLIPEmbedder,
    VisionRAGStore,
    semantic_chunk_text,
    is_image_relevant,
    print_summary,
    extract_and_save_image,
    extract_and_save_block_image,
    
)


# def process_file_pipeline(pdf_path: str, file_id: str):
#     """
#     Extract text + relevant images from PDF and store embeddings in per-file FAISS vectorstore.
#     Relevance check uses Pixtral model based on page content only (no query).
#     """
#     embedder = CLIPEmbedder()
#     store = VisionRAGStore(embedder)

#     doc = pymupdf.open(pdf_path)
#     total_pages = len(doc)
#     print(f"📘 Processing '{pdf_path}' ({total_pages} pages)")

#     stats = {
#         "pages": total_pages,
#         "embedded": 0,
#         "filtered": 0,
#         "errors": 0,
#     }

#     for page_num in tqdm(range(total_pages), desc="Extracting pages"):
#         page = doc[page_num]
#         text = page.get_text("text")
#         images = []

#         # Extract embedded images with relevance filtering
#         for img_idx, img in enumerate(page.get_images(full=True)):
#             try:
#                 xref = img[0]
#                 base_image = doc.extract_image(xref)
#                 image_bytes = base_image["image"]
#                 ext = base_image.get("ext", "png")

#                 if not is_image_relevant(image_bytes, text):
#                     stats["filtered"] += 1
#                     continue

#                 filename = f"{file_id}_p{page_num+1:04d}_{img_idx}.{ext}"
#                 path = Path(cfg.extracted_images_dir) / filename
#                 with open(path, "wb") as f:
#                     f.write(image_bytes)
#                 images.append(str(path.resolve()))
#                 stats["embedded"] += 1

#             except Exception as e:
#                 print(f"⚠️ Error extracting image on page {page_num+1}: {e}")
#                 stats["errors"] += 1

#         # --- Embeddings ---
#         if text.strip():
#             chunks = semantic_chunk_text(text)
#             text_vecs = embedder.embed_text(chunks)
#             text_meta = [
#                 {"type": "text", "page_num": page_num + 1, "content": chunk, "embedding_type": "text"}
#                 for chunk in chunks
#             ]
#             store.add_embeddings(text_vecs, text_meta)

#         if images:
#             img_vecs = embedder.embed_images(images)
#             img_meta = [
#                 {"type": "image", "page_num": page_num + 1, "page_path": path, "embedding_type": "image"}
#                 for path in images
#             ]
#             store.add_embeddings(img_vecs, img_meta)

#     store.save(file_id)
#     doc.close()

#     print("\n" + "="*60)
#     print("✅ File Processing Summary")
#     print("="*60)
#     print(f"📄 Pages: {stats['pages']}")
#     print(f"🖼️ Images Extracted: {stats['embedded']}")
#     print(f"🚫 Filtered (Non-Relevant): {stats['filtered']}")
#     print(f"⚠️ Errors: {stats['errors']}")
#     print("="*60 + "\n")

# def process_file_pipeline(pdf_path: str, file_id: str):
#     """
#     Extract text + relevant images (embedded & block) from PDF and store embeddings
#     in a per-file FAISS vectorstore.
#     Uses Pixtral model for image relevance (based on page text only, no query).
#     """
#     embedder = CLIPEmbedder()
#     store = VisionRAGStore(embedder)

#     doc = pymupdf.open(pdf_path)
#     total_pages = len(doc)
#     print(f"📘 Processing '{pdf_path}' ({total_pages} pages)")

#     # Stats tracking
#     stats = {
#         "pages": total_pages,
#         "embedded": 0,
#         "blocks": 0,
#         "filtered": 0,
#         "skipped_small": 0,
#         "errors": 0,
#     }

#     output_dir = Path(cfg.extracted_images_dir)
#     output_dir.mkdir(parents=True, exist_ok=True)

#     for page_num in tqdm(range(total_pages), desc="Extracting pages"):
#         page = doc[page_num]
#         text = page.get_text("text") or ""
#         page_images = []

#         # ======================================================
#         # 1️⃣ Extract Embedded Images
#         # ======================================================
#         for img_idx, img in enumerate(page.get_images(full=True)):
#             try:
#                 xref = img[0]
#                 base_image = doc.extract_image(xref)
#                 image_bytes = base_image["image"]
#                 ext = base_image.get("ext", "png")
#                 width = base_image.get("width", 0)
#                 height = base_image.get("height", 0)

#                 # Skip small or low-quality images
#                 if width < 50 or height < 50:
#                     stats["skipped_small"] += 1
#                     continue

#                 # Relevance filtering
#                 if not is_image_relevant(image_bytes, text):
#                     stats["filtered"] += 1
#                     continue

#                 # Save relevant image
#                 filename = f"{file_id}_p{page_num+1:04d}_embed{img_idx}.{ext}"
#                 img_path = output_dir / filename
#                 with open(img_path, "wb") as f:
#                     f.write(image_bytes)

#                 page_images.append(str(img_path.resolve()))
#                 stats["embedded"] += 1

#             except Exception as e:
#                 print(f"⚠️ Embedded image error (page {page_num+1}): {e}")
#                 stats["errors"] += 1

#         # ======================================================
#         # 2️⃣ Extract Image Blocks (Rendered regions)
#         # ======================================================
#         try:
#             text_dict = page.get_text("dict")
#             blocks = text_dict.get("blocks", [])
#             mat = pymupdf.Matrix(2.0, 2.0)  # High-resolution scaling

#             for block_idx, block in enumerate(b for b in blocks if b.get("type") == 1):
#                 try:
#                     bbox = pymupdf.Rect(block.get("bbox"))
#                     if bbox.width < 50 or bbox.height < 50:
#                         stats["skipped_small"] += 1
#                         continue

#                     pix = page.get_pixmap(matrix=mat, clip=bbox, alpha=False)
#                     image_bytes = pix.tobytes("png")

#                     if not is_image_relevant(image_bytes, text):
#                         stats["filtered"] += 1
#                         continue

#                     filename = f"{file_id}_p{page_num+1:04d}_block{block_idx}.png"
#                     img_path = output_dir / filename
#                     pix.save(str(img_path))

#                     page_images.append(str(img_path.resolve()))
#                     stats["blocks"] += 1

#                 except Exception as e:
#                     print(f"⚠️ Block image error (page {page_num+1}): {e}")
#                     stats["errors"] += 1

#         except Exception as e:
#             print(f"⚠️ Error reading block data (page {page_num+1}): {e}")

#         # ======================================================
#         # 3️⃣ Generate Embeddings (Text + Images)
#         # ======================================================
#         try:
#             # Text embeddings
#             if text.strip():
#                 chunks = semantic_chunk_text(text)
#                 if chunks:
#                     text_vecs = embedder.embed_text(chunks)
#                     text_meta = [
#                         {
#                             "type": "text",
#                             "page_num": page_num + 1,
#                             "content": chunk,
#                             "embedding_type": "text",
#                         }
#                         for chunk in chunks
#                     ]
#                     store.add_embeddings(text_vecs, text_meta)

#             # Image embeddings
#             if page_images:
#                 img_vecs = embedder.embed_images(page_images)
#                 img_meta = [
#                     {
#                         "type": "image",
#                         "page_num": page_num + 1,
#                         "page_path": path,
#                         "embedding_type": "image",
#                     }
#                     for path in page_images
#                 ]
#                 store.add_embeddings(img_vecs, img_meta)

#         except Exception as e:
#             print(f"⚠️ Embedding generation error (page {page_num+1}): {e}")
#             stats["errors"] += 1

#     # ======================================================
#     # 4️⃣ Save FAISS Index and Wrap-up
#     # ======================================================
#     store.save(file_id)
#     doc.close()

#     print("\n" + "=" * 60)
#     print("✅ File Processing Summary")
#     print("=" * 60)
#     print(f"📄 Pages processed: {stats['pages']}")
#     print(f"🖼️ Embedded images saved: {stats['embedded']}")
#     print(f"🧩 Block images saved: {stats['blocks']}")
#     print(f"🚫 Filtered (non-relevant): {stats['filtered']}")
#     print(f"⚠️ Skipped (too small): {stats['skipped_small']}")
#     print(f"❌ Errors: {stats['errors']}")
#     print(f"📂 Output path: {output_dir.resolve()}")
#     print("=" * 60 + "\n")

def process_file_pipeline(pdf_path: str, file_id: str):
    """
    Extract text and relevant images (embedded & block) from PDF,
    store their embeddings, and generate summaries for relevant images.
    """
    embedder = CLIPEmbedder()
    store = VisionRAGStore(embedder)

    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    print(f"📘 Processing '{pdf_path}' ({total_pages} pages)")

    stats = {
        "pages": total_pages,
        "embedded": 0,
        "blocks": 0,
        "filtered": 0,
        "skipped_small": 0,
        "errors": 0,
    }

    output_dir = Path(cfg.extracted_images_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for page_num in tqdm(range(total_pages), desc="Extracting pages"):
        page = doc[page_num]
        text = page.get_text("text") or ""
        page_images_meta = []

        # ======================================================
        # 1️⃣ Extract Embedded Images
        # ======================================================
        for img_idx, img in enumerate(page.get_images(full=True)):
            try:
                image_meta = extract_and_save_image(
                    doc=doc,
                    img_info=img,
                    page_num=page_num,
                    file_id=file_id,
                    text=text,
                    output_dir=output_dir,
                    stats=stats,
                    mode="embed",
                )
                if image_meta:
                    page_images_meta.append(image_meta)
            except Exception as e:
                print(f"⚠️ Embedded image error (page {page_num+1}): {e}")
                stats["errors"] += 1

        # ======================================================
        # 2️⃣ Extract Block Images (Rendered)
        # ======================================================
        try:
            blocks = page.get_text("dict").get("blocks", [])
            for block_idx, block in enumerate(b for b in blocks if b.get("type") == 1):
                try:
                    image_meta = extract_and_save_block_image(
                        page=page,
                        block=block,
                        block_idx=block_idx,
                        page_num=page_num,
                        file_id=file_id,
                        text=text,
                        output_dir=output_dir,
                        stats=stats,
                    )
                    if image_meta:
                        page_images_meta.append(image_meta)
                except Exception as e:
                    print(f"⚠️ Block image error (page {page_num+1}): {e}")
                    stats["errors"] += 1
        except Exception as e:
            print(f"⚠️ Error reading block data (page {page_num+1}): {e}")

        # ======================================================
        # 3️⃣ Generate Embeddings (Text + Image)
        # ======================================================
        try:
            # --- Text embeddings ---
            if text.strip():
                chunks = semantic_chunk_text(text)
                if chunks:
                    text_vecs = embedder.embed_text(chunks)
                    text_meta = [
                        {
                            "type": "text",
                            "page_num": page_num + 1,
                            "content": chunk,
                            "embedding_type": "text",
                        }
                        for chunk in chunks
                    ]
                    store.add_embeddings(text_vecs, text_meta)

            # --- Image embeddings (with summaries) ---
            if page_images_meta:
                image_paths = [m["page_path"] for m in page_images_meta]
                img_vecs = embedder.embed_images(image_paths)
                store.add_embeddings(img_vecs, page_images_meta)

        except Exception as e:
            print(f"⚠️ Embedding generation error (page {page_num+1}): {e}")
            stats["errors"] += 1

    # ======================================================
    # 4️⃣ Save Index & Wrap Up
    # ======================================================
    store.save(file_id)
    doc.close()

    print_summary(stats, output_dir)



# ============================================================
# 🔥 NEW FUNCTION: Delete all generated files for a given file_id
# ============================================================
def delete_file_pipeline_outputs(file_id: str) -> dict:
    """
    Delete all files generated by process_file_pipeline for a given file_id.
    Removes:
      - Extracted images from cfg.extracted_images_dir
      - FAISS index and metadata from cfg.faiss_dir
    Returns a dict summary of what was deleted.
    """
    deleted_files = []
    missing_files = []

    # 1️⃣ Delete extracted images
    images_dir = Path(cfg.extracted_images_dir)
    for img_file in images_dir.glob(f"{file_id}_p*.png"):
        try:
            img_file.unlink()
            deleted_files.append(str(img_file))
        except Exception as e:
            print(f"⚠️ Failed to delete {img_file}: {e}")
    for img_file in images_dir.glob(f"{file_id}_p*.jpg"):
        try:
            img_file.unlink()
            deleted_files.append(str(img_file))
        except Exception as e:
            print(f"⚠️ Failed to delete {img_file}: {e}")

    # 2️⃣ Delete FAISS index and metadata
    faiss_dir = Path(cfg.faiss_dir)
    index_path = faiss_dir / f"{file_id}_index.faiss"
    meta_path = faiss_dir / f"{file_id}_metadata.pkl"

    for fpath in [index_path, meta_path]:
        if fpath.exists():
            try:
                fpath.unlink()
                deleted_files.append(str(fpath))
            except Exception as e:
                print(f"⚠️ Failed to delete {fpath}: {e}")
        else:
            missing_files.append(str(fpath))

    print("\n" + "=" * 60)
    print(f"🗑️ Cleanup Summary for {file_id}")
    print("=" * 60)
    print(f"✅ Deleted {len(deleted_files)} files")
    if missing_files:
        print(f"⚠️ Missing {len(missing_files)} files (already removed or not created)")
    print("=" * 60 + "\n")

    return {
        "file_id": file_id,
        "deleted_files": deleted_files,
        "missing_files": missing_files,
        "deleted_count": len(deleted_files),
        "missing_count": len(missing_files),
    }