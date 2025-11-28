
import json
import re
import numpy as np
import pandas as pd
import google.generativeai as genai
from datasets import Dataset


RELEVANCY_PROMPT = '''
Generate a question for the given ANSWER and classify whether the answer is noncommittal.
Return ONLY a JSON object:
{
  "question": "...",
  "noncommittal": 1 or 0
}

Noncommittal answers are vague, evasive, uncertain, like:
"I don't know", "I'm not sure", "It depends", "Cannot say"

ANSWER: {answer}
'''


def extract_json_obj(text: str):
    try:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
    except:
        pass
    return {}


def embed_text(client, text: str):
    out = client.models.embed_content(
        model="models/embedding-001",
        content=text
    )
    return np.array(out.embedding)


def cosine_similarity(a, bs):
    a = a.reshape(1, -1)
    bs = np.asarray(bs)
    denom = np.linalg.norm(bs, axis=1) * np.linalg.norm(a)
    return (np.dot(bs, a.T).reshape(-1,) / denom)


class GeminiRelevancy:
    def __init__(self, client, n=3, model="gemini-2.0-flash"):
        self.client = client
        self.n = n
        self.model = model

    def generate(self, answer: str):
        outs = []
        for _ in range(self.n):
            p = RELEVANCY_PROMPT.format(answer=answer)
            r = self.client.models.generate_content(model=self.model, contents=p)
            j = extract_json_obj(r.text)
            q = j.get("question", "").strip()
            nc = int(j.get("noncommittal", 0))
            outs.append({"question": q, "noncommittal": nc})
        return outs


def answer_relevancy_score(client, generated, user_question):
    gen_qs = [x["question"] for x in generated]
    non_committal = any(x["noncommittal"] == 1 for x in generated)
    if all(q.strip() == "" for q in gen_qs):
        return np.nan
    q_vec = embed_text(client, user_question)
    gen_vecs = [embed_text(client, q) for q in gen_qs]
    sim = cosine_similarity(q_vec, gen_vecs)
    return sim.mean() * (1 - int(non_committal))


def compute_relevancy_for_row(client_chk, verifier: GeminiRelevancy, row: dict):
    answer = row["answer"]
    user_q = row["question"]
    outputs = verifier.generate(answer)
    return answer_relevancy_score(client_chk, outputs, user_q)


def compute_relevancy_dataset(client_chk, dataset: Dataset, n=3):
    verifier = GeminiRelevancy(client_chk, n=n)
    records = []
    for i in range(len(dataset)):
        row = dataset[i]
        score = compute_relevancy_for_row(client_chk, verifier, row)
        records.append({
            "question": row["question"],
            "answer": row["answer"],
            "answer_relevancy_score": score
        })
    df = pd.DataFrame(records)
    df.to_csv("answer_relevancy_scores.csv", index=False)
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

df = compute_relevancy_dataset(client_chk, dataset)
df
