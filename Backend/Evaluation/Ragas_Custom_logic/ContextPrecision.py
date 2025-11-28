
import json
import re
import numpy as np
import pandas as pd
import google.generativeai as genai
from datasets import Dataset

STATEMENT_PROMPT = '''
Given QUESTION, CONTEXT and ANSWER determine whether the CONTEXT was useful in arriving at the ANSWER.
Return ONLY a JSON object with two keys:
"verdict": 1 if useful else 0,
"reason": a short explanation string.
QUESTION: {question}
CONTEXT: {context}
ANSWER: {answer}
Return ONLY JSON like: {{"verdict":1,"reason":"..."}}
'''

def extract_json_obj(text: str):
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except:
        pass
    return {}

def flatten_contexts(contexts):
    flat = []
    for c in contexts:
        if isinstance(c, list):
            flat.extend(flatten_contexts(c))
        else:
            flat.append(str(c))
    return flat

class GeminiVerifier:
    def __init__(self, client, model="gemini-2.0-flash"):
        self.client = client
        self.model = model

    def verify(self, question: str, context: str, answer: str) -> dict:
        prompt = STATEMENT_PROMPT.format(question=question, context=context, answer=answer)
        resp = self.client.models.generate_content(model=self.model, contents=prompt)
        return extract_json_obj(resp.text)

def average_precision_from_verdicts(verdict_list):
    if not isinstance(verdict_list, list) or len(verdict_list) == 0:
        return np.nan
    vl = [1 if int(v) else 0 for v in verdict_list]
    denom = sum(vl) + 1e-10
    numer = sum([ (sum(vl[:i+1])/(i+1)) * vl[i] for i in range(len(vl)) ])
    return numer / denom

def compute_context_precision_for_row(verifier: GeminiVerifier, row: dict, use_reference_key="ground_truths"):
    q = row.get("question") or row.get("user_input") or ""
    answer = None
    if "reference" in row:
        answer = row["reference"]
    elif use_reference_key in row and row[use_reference_key] is not None:
        answer = row[use_reference_key]
    else:
        answer = row.get("answer") or row.get("response") or ""
    contexts = flatten_contexts(row.get("contexts") or row.get("retrieved_contexts") or [])
    verifications = []
    for ctx in contexts:
        out = verifier.verify(q, ctx, answer)
        verdict = out.get("verdict")
        try:
            verdict = int(verdict)
        except:
            verdict = 0
        verifications.append(verdict)
    return average_precision_from_verdicts(verifications)

def compute_context_precision_dataset(client_chk, dataset: Dataset, project_id=None, location=None):
    verifier = GeminiVerifier(client_chk)
    records = []
    for i in range(len(dataset)):
        row = dataset[i]
        score = compute_context_precision_for_row(verifier, row)
        records.append({"question": row.get("question") or row.get("user_input"), "context_precision_score": score})
    df = pd.DataFrame(records)
    df.to_csv("context_precision_scores.csv", index=False)
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

df = compute_context_precision_dataset(client_chk, dataset)
df
