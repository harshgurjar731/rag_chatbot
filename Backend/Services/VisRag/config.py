# visrag/config.py
import os
from pathlib import Path
from dataclasses import dataclass
from mistralai import Mistral
import torch

@dataclass
class Config:
    base_dir: str = "./visrag_data"
    page_images_dir: str = "./visrag_data/page_images"
    extracted_images_dir: str = "./visrag_data/extracted_images"
    faiss_dir: str = "./visrag_data/faiss_stores"

    clip_model_name: str = "openai/clip-vit-large-patch14"
    pixtral_model: str = "pixtral-12b-2409"
    mistral_api_key: str = "ZpuwhInKUMLpkFTtA9zKmu7n0vxhLFRJ"

    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    chunk_size: int = 800
    chunk_overlap: int = 150
    min_image_width: int = 50
    min_image_height: int = 50
    brightness_threshold: float = 10.0
    top_k: int = 5

cfg = Config()

# Create required directories
for d in [cfg.base_dir, cfg.page_images_dir, cfg.extracted_images_dir, cfg.faiss_dir]:
    Path(d).mkdir(parents=True, exist_ok=True)

# Initialize Mistral client
client = Mistral(api_key=cfg.mistral_api_key)
