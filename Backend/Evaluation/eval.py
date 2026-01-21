from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from ragas import evaluate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
# from ragas.embeddings import OpenAIEmbeddings
import openai
from datasets import Dataset
# from Backend.config import CONFIG
import os
from sentence_transformers import SentenceTransformer
from langchain_community.embeddings import HuggingFaceEmbeddings
from pathlib import Path
from typing import List, Dict, Any
import json
import pandas as pd
import numpy as np
from langchain_openai import AzureChatOpenAI

# NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
# MODEL_NAME = "meta/llama-3.1-8b-instruct"  # open-source instruct model
# os.environ["NVIDIA_API_KEY"]= CONFIG['NVIDIA_API_KEY']
# EMB_MODEL = "BAAI/bge-small-en-v1.5"   # open-source, efficient
embedder = SentenceTransformer("BAAI/bge-small-en-v1.5")
# ✅ Point Ragas to NVIDIA endpoint (OpenAI-compatible)
# llm = ChatOpenAI(
#     model="llama-3.1-8b-instant",
#     api_key="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",    # use your NVIDIA key
#     base_url="https://api.groq.com/openai/v1",
#     temperature=0.2,
#     max_tokens=800
# )
# openai_client = openai.OpenAI(api_key=NVIDIA_API_KEY, base_url=NVIDIA_BASE_URL)
# embeddings = OpenAIEmbeddings(client=openai_client)
azure_api_key =str("BCTqm4bq9ThjGQ1witJEJthrMp8UT321zttAcrkDMam3nROaJgd9JQQJ99BJACYeBjFXJ3w3AAABACOGIP1X")
azure_endpoint= str("https://knowldgebotapi.openai.azure.com/")
azure_api_version= str("2024-12-01-preview")

llm = AzureChatOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=azure_api_key,
            api_version=azure_api_version,
            azure_deployment="gpt-5-mini",
            max_completion_tokens=1024,
            temperature=0,
        )


ragas_rows = [
    {
        "question": "Who developed the theory of relativity?",
        "answer": "Einstein developed the theory of relativity.",
        "contexts": [
            "Albert Einstein, a German-born physicist, developed the theory of relativity in the early 20th century.",
            "Isaac Newton is famous for the laws of motion and universal gravitation."
        ],
        "ground_truth": "Albert Einstein developed the theory of relativity."
    },
    {
        "question": "What is the capital of France?",
        "answer": "The capital of France is Paris.",
        "contexts": [
            "France is a European country. Its capital city is Paris, which is known for the Eiffel Tower.",
            "Berlin is the capital of Germany."
        ],
        "ground_truth": "Paris"
    },
    {
        "question": "In which year did the first man land on the moon?",
        "answer": "The first moon landing happened in 1969.",
        "contexts": [
            "Apollo 11 was the spaceflight that first landed humans on the Moon on July 20, 1969.",
            "Neil Armstrong and Buzz Aldrin walked on the lunar surface while Michael Collins remained in orbit."
        ],
        "ground_truth": "1969"
    },
    {
        "question": "What is the largest mammal on Earth?",
        "answer": "The blue whale is the largest mammal on Earth.",
        "contexts": [
            "The blue whale is the largest animal known to have ever existed, growing up to 30 meters in length.",
            "Elephants are the largest land mammals."
        ],
        "ground_truth": "Blue whale"
    }
]

ds = Dataset.from_list(ragas_rows)
print(ds)

from langchain_community.embeddings import HuggingFaceEmbeddings
embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")

result = evaluate(
    ds,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    llm=llm,
    embeddings=embeddings,
)

df = result.to_pandas()
print(df)