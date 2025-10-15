import openai
from langchain_openai import ChatOpenAI
from ragas.embeddings import OpenAIEmbeddings
from config import NVIDIA_API_KEY
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from ragas import evaluate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from sentence_transformers import SentenceTransformer


NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL_NAME = "meta/llama-3.1-8b-instruct"  # open-source instruct model
EMB_MODEL = "BAAI/bge-small-en-v1.5"   # open-source, efficient
embedder = SentenceTransformer(EMB_MODEL)

# ✅ Point Ragas to NVIDIA endpoint (OpenAI-compatible)
llm = ChatOpenAI(
    model=MODEL_NAME,
    api_key=NVIDIA_API_KEY,    # use your NVIDIA key
    base_url=NVIDIA_BASE_URL,
    temperature=0.2
)

# ✅ For embeddings, we already used SentenceTransformers above,
# but Ragas needs an embeddings class with LangChain interface.
# We'll wrap ours with OpenAIEmbeddings but still pointing to NVIDIA endpoint
# OR just use sentence-transformers wrapper from LangChain.
from langchain_community.embeddings import HuggingFaceEmbeddings

# Use CPU embeddings or small models
from sentence_transformers import SentenceTransformer

# CPU-compatible embedding
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
embeddings = lambda texts: model.encode(texts, convert_to_tensor=True)


ragas_rows = [
    {
        "user_input": "Where is the Eiffel Tower located?",
        "retrieved_contexts": [
            "The Eiffel Tower is in Paris, France. It is famous for its architectural design and attracts millions of tourists every year.",
            "The Eiffel Tower was constructed in 1889 and remains one of the most visited monuments in the world."
        ],
        "response": "The Eiffel Tower is located in Paris, France.",
        "reference": "Paris, France"
    },
    {
        "user_input": "Who created Python programming language?",
        "retrieved_contexts": [
            "Python was created by Guido van Rossum in 1991. It's widely used for web development, data science, and scripting.",
            "Python emphasizes code readability and simplicity."
        ],
        "response": "Guido van Rossum created Python in 1991.",
        "reference": "Guido van Rossum"
    },
    {
        "user_input": "Why was the Great Wall of China built?",
        "retrieved_contexts": [
            "The Great Wall was constructed to defend Chinese states and empires against raids and invasions from nomadic groups.",
            "It stretches over 13,000 miles and construction started in the 7th century BC."
        ],
        "response": "It was built to protect China from invasions.",
        "reference": "To protect against invasions"
    }
]

from ragas import EvaluationDataset
evaluation_dataset = EvaluationDataset.from_list(ragas_rows)

result = evaluate(
    evaluation_dataset,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    llm=llm,
    embeddings=embeddings
)

df = result.to_pandas()
print(df)
