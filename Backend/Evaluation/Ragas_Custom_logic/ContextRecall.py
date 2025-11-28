
import json
import re
import numpy as np
import pandas as pd
import google.generativeai as genai
from datasets import Dataset


CONTEXT_RECALL_PROMPT = '''
Split the ANSWER into individual sentences.
For each sentence, determine if it is supported by the CONTEXT.
Return ONLY a JSON array of objects like:
[
  {"statement":"...","reason":"...","attributed":1},
  {"statement":"...","reason":"...","attributed":0}
]

QUESTION: {question}
CONTEXT: {context}
ANSWER: {answer}
'''


def extract_json_list(text: str):
    try:
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
    except:
        pass
    return []


def flatten_contexts(contexts):
    out = []
    for c in contexts:
        if isinstance(c, list):
            out.extend(flatten_contexts(c))
        else:
            out.append(str(c))
    return out


class GeminiRecall:
    def __init__(self, client, model="gemini-2.0-flash"):
        self.client = client
        self.model = model

    def classify(self, question: str, context: str, answer: str):
        prompt = CONTEXT_RECALL_PROMPT.format(question=question, context=context, answer=answer)
        r = self.client.models.generate_content(model=self.model, contents=prompt)
        j = extract_json_list(r.text)
        return j if isinstance(j, list) else []


def compute_context_recall_for_row(verifier: GeminiRecall, row: dict):
    q = row["question"]
    answer = row["answer"]
    context = "\n".join(flatten_contexts(row["contexts"]))
    classifications = verifier.classify(q, context, answer)
    if not classifications:
        return np.nan
    verdicts = [1 if int(item.get("attributed", 0)) == 1 else 0 for item in classifications]
    return sum(verdicts) / len(verdicts)


def compute_context_recall_dataset(client_chk, dataset: Dataset):
    verifier = GeminiRecall(client_chk)
    records = []
    for i in range(len(dataset)):
        row = dataset[i]
        score = compute_context_recall_for_row(verifier, row)
        records.append({
            "question": row["question"],
            "context_recall_score": score
        })
    df = pd.DataFrame(records)
    df.to_csv("context_recall_scores.csv", index=False)
    return df


project_id = "YOUR_PROJECT_ID"
location = "us-central1"
client_chk = genai.Client(vertexai=True, project=project_id, location=location)

data = {
    "question": query_list,
    "answer": answer_list,
    "contexts": reference_list,
    "ground_truths": ground_truth_list
}

dataset = Dataset.from_dict(data)
df = compute_context_recall_dataset(client_chk, dataset)
df
