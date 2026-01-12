from fastapi import APIRouter, UploadFile, File, Form
from typing import List
from transformers import AutoProcessor, AutoModel
from PIL import Image
import torch
import tempfile
import base64
import io

router = APIRouter()

@router.post("/imageRerank")
async def rerank_image_search(
    textQuery: str = Form(...),
    queryImage: UploadFile = File(...),
    top_k_images: List[str] = Form(...)
):
    model_name = "google/siglip2-base"
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Load model + processor once per request (can optimize later)
    processor = AutoProcessor.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name).to(device)
    model.eval()

    # Convert uploaded query image to PIL
    query_bytes = await queryImage.read()
    query_img_pil = Image.open(io.BytesIO(query_bytes)).convert("RGB")

    def get_embedding(text=None, image=None):
        inputs = processor(
            text=text,
            images=image,
            return_tensors="pt",
            padding=True
        ).to(device)

        with torch.no_grad():
            outputs = model(**inputs)

        emb = outputs.pooler_output
        return emb / emb.norm(dim=-1, keepdim=True)  # normalize

    # Query embedding using both text + image
    query_embedding = get_embedding(text=textQuery, image=query_img_pil)

    # -------------------------------
    # Decode base64 candidate images
    # -------------------------------
    image_embeddings = []

    for img_b64 in top_k_images:
        try:
            img_bytes = base64.b64decode(img_b64)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        except Exception as e:
            return {"error": f"Invalid base64 image: {str(e)}"}

        emb = get_embedding(image=img)
        image_embeddings.append((img_b64, emb))

    # -------------------------------
    # Compute similarity scores
    # -------------------------------
    scores = [
        (img_b64, (emb @ query_embedding.T).item())
        for img_b64, emb in image_embeddings
    ]

    # Sort by similarity
    reranked = sorted(scores, key=lambda x: x[1], reverse=True)

    # Return results
    return {
        "query": textQuery,
        "reranked_results": [
            {"image_base64": img_b64, "score": float(score)}
            for img_b64, score in reranked
        ]
    }