from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from ragas import evaluate
from langchain_openai import ChatOpenAI
from datasets import Dataset
from config import CONFIG
from sentence_transformers import SentenceTransformer
from pathlib import Path
from typing import List, Dict, Any
import json
import pandas as pd
import numpy as np
from langchain_openai import AzureChatOpenAI
from langchain_community.embeddings import HuggingFaceEmbeddings


def perform_ragaas_evaluation(
    datastore_id: int,
    metrics: List[str],
    session
) -> Dict[str, Any]:
    """
    Perform RAGAS evaluation using:
      - Questions and ground truths from the database
      - Contexts (reference) and answers (response) from the generated JSON file
    Automatically resolves the JSON path from datastore name.
    Returns results as a dictionary with per-metric outputs.
    """

    try:
        # -------------------- LLM + Embedding Setup --------------------
        llm_model_name = "llama-3.1-8b-instant"
        temperature = CONFIG.get("default_temperature", 0.2)
        token_size = 2048
        GROQ_API_KEY = CONFIG.get("groq_api_key")
        GROQ_API_BASE = CONFIG.get("groq_api_base")

        # azure_api_key =str("BCTqm4bq9ThjGQ1witJEJthrMp8UT321zttAcrkDMam3nROaJgd9JQQJ99BJACYeBjFXJ3w3AAABACOGIP1X")

        azure_api_key =str("DwfHJZLpeTow2gr41penTNTdmQL4YVmaBIhxuQSEqFAjV2R3WbKRJQQJ99BKACYeBjFXJ3w3AAAAACOGNgkY")
        azure_endpoint= str("https://rupali123.openai.azure.com/")
        azure_api_version= str("2025-01-01-preview")


        # llm = ChatOpenAI(
        #     openai_api_base=GROQ_API_BASE,
        #     openai_api_key=GROQ_API_KEY,
        #     model=llm_model_name,
        #     temperature=temperature,
        #     max_tokens=token_size,
        #     n=1,
        # )

        llm = AzureChatOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=azure_api_key,
            api_version=azure_api_version,
            azure_deployment="gpt-4o-mini",
            temperature=0,
            max_completion_tokens=token_size,
        )




        # embeddings = SentenceTransformer("BAAI/bge-small-en-v1.5")
        embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")

        # -------------------- Load Datastore Info --------------------
        from models.datastore import DataStore
        datastore = session.get(DataStore, datastore_id)
        if not datastore:
            raise ValueError(f"Datastore with ID {datastore_id} not found.")

        # -------------------- Resolve Dynamic File Path --------------------
        data_folder = Path(CONFIG["project_root"]) / CONFIG["datastore_data_folder"]
        file_path = data_folder / datastore.name / f"{datastore.name}_evaluation_qa.json"

        if not file_path.exists():
            raise FileNotFoundError(f"Generated JSON file not found at path: {file_path}")

        # -------------------- Load Data from DB --------------------
        from models.FileRecord import QuestionAnswer
        from sqlmodel import select

        qa_records = session.exec(
            select(QuestionAnswer).where(QuestionAnswer.datastore_id == datastore_id)
        ).all()

        if not qa_records:
            raise ValueError("No QA pairs found in datastore for evaluation.")

        db_map = {qa.question.strip(): qa for qa in qa_records}

        # -------------------- Load JSON Data --------------------
        with open(file_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)

        if not isinstance(json_data, list):
            raise ValueError("Invalid JSON format: expected a list of entries.")

        # -------------------- Combine DB + JSON into Ragas Rows --------------------
        ragas_rows = []
        for entry in json_data:
            query = entry.get("query", "").strip()
            reference = entry.get("reference", "")
            response = entry.get("response", "")

            if query not in db_map:
                continue

            db_record = db_map[query]

            # If question is empty, replace it with query
            question_text = db_record.question.strip() if db_record.question.strip() else query
            answer_text = response.replace("\n", " ").strip() if response else ""
            context_text = reference.replace("\n", " ").strip() if reference else ""
            ground_truth_text = db_record.answer.replace("\n", " ").strip() if db_record.answer else ""

            # Skip incomplete rows
            if not question_text or not answer_text or not context_text or not ground_truth_text:
                continue

            ragas_rows.append(
                {
                    "question": question_text,
                    "answer": answer_text,
                    "contexts": [context_text],
                    "ground_truth": ground_truth_text,
                }
            )

        if not ragas_rows:
            raise ValueError("No valid rows found for RAGAS evaluation after filtering empty fields.")

        # -------------------- Prepare Dataset --------------------
        ds = Dataset.from_list(ragas_rows)

        # -------------------- Metric Mapping --------------------
        metric_map = {
            "faithfulness": faithfulness,
            "answer relevancy": answer_relevancy,
            "context precision": context_precision,
            "context recall": context_recall,
        }

        selected_metrics = [
            (name, metric_map[name.lower()])
            for name in metrics
            if name.lower() in metric_map
        ]

        if not selected_metrics:
            raise ValueError("No valid metrics found in request for RAGAS evaluation.")

        # -------------------- Run Evaluation --------------------
        print(f"[INFO] Running RAGAS evaluation for datastore {datastore.name} with metrics: {metrics}")
        metric_results = {}

        for metric_name, metric_obj in selected_metrics:
            try:
                res = evaluate(ds, metrics=[metric_obj], llm=llm, embeddings=embeddings)
                df = res.to_pandas()

                # 🧹 Clean up invalid numbers for JSON serialization safely
                df.replace([np.inf, -np.inf], np.nan, inplace=True)
                df = df.apply(lambda col: col.map(lambda x: None if (isinstance(x, float) and np.isnan(x)) else x))

                # Convert safely to JSON-serializable dictionary
                metric_results[metric_name] = json.loads(df.to_json(orient="records"))
            except Exception as e:
                print(f"[WARN] Metric {metric_name} failed: {e}")
                metric_results[metric_name] = [{"error": str(e)}]


        return metric_results

    except FileNotFoundError as e:
        print(f"[ERROR] File not found: {e}")
        return {"error": str(e), "status": "failed"}

    except ValueError as e:
        print(f"[ERROR] Validation error: {e}")
        return {"error": str(e), "status": "failed"}

    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON decoding error: {e}")
        return {"error": "Invalid JSON file format.", "status": "failed"}

    except Exception as e:
        import traceback
        print(f"[ERROR] Unexpected error in perform_ragaas_evaluation: {e}")
        traceback.print_exc()
        return {"error": str(e), "status": "failed"}
